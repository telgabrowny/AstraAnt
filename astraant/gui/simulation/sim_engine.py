"""Core simulation engine — runs headlessly, no Ursina dependency.

The GUI layer observes this engine's state to update visuals.
Can also be run without GUI for batch analysis.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .ant_agent import AntAgent, AntState, Position
from .comms_delay import CommsDelay
from .mission_clock import MissionClock
from .tunnel_state import TunnelNetwork

try:
    from ...configs import load_all_ant_configs, compute_ant_mass
except ImportError:
    load_all_ant_configs = None
    compute_ant_mass = None

try:
    from ...composition import sample_regolith, get_zones_for_asteroid
except ImportError:
    sample_regolith = None
    get_zones_for_asteroid = None


@dataclass
class SimStats:
    """Running statistics for the simulation."""
    total_material_extracted_kg: float = 0.0
    total_water_recovered_kg: float = 0.0
    total_area_sealed_m2: float = 0.0
    total_dump_cycles: int = 0
    total_drum_cycles: int = 0
    total_vat_checks: int = 0
    anomalies_detected: int = 0
    ants_failed: int = 0
    # Bioreactor stats
    metals_extracted_kg: float = 0.0
    biomass_g_per_l: float = 0.1     # Current culture density


class SimEngine:
    """The headless simulation core.

    Usage:
        engine = SimEngine(workers=100, taskmasters=5, ...)
        engine.setup()
        while running:
            events = engine.tick(dt)
            # GUI reads engine.agents, engine.tunnel, engine.stats
    """

    def __init__(self, workers: int = 100, taskmasters: int = 5,
                 surface_ants: int = 3, couriers: int = 0,
                 sorters: int = 0, plasterers: int = 0, tenders: int = 0,
                 track: str = "a", asteroid_distance_au: float = 1.0) -> None:
        self.clock = MissionClock()
        self.tunnel = TunnelNetwork()
        self.comms = CommsDelay(asteroid_distance_au)
        self.stats = SimStats()
        self.agents: list[AntAgent] = []
        self.event_log: list[dict[str, Any]] = []

        self._worker_count = workers
        self._taskmaster_count = taskmasters
        # Support both old 'couriers' param and new 'surface_ants'
        self._surface_ant_count = surface_ants or couriers
        self._track = track

        # Telemetry broadcast interval (sim seconds)
        self._telemetry_interval = 900.0  # Every 15 min sim-time
        self._last_telemetry_time = 0.0

        # Bioreactor state (Track B/C only)
        self._has_bioreactor = track in ("b", "c")
        self._bioreactor_state = None
        self._bioreactor_update_interval = 3600.0
        self._last_bioreactor_update = 0.0

        # Composition variability
        self._comp_zones = None
        self._bulk_metals = {}
        self._bulk_water_pct = 0.0
        self._zone_hits: dict[str, int] = {}  # Count of batches per zone

    def setup(self) -> None:
        """Initialize all agents and place them in the tunnel/surface."""
        agent_id = 0

        # Load ant configs for calibrated parameters
        ant_cfgs = {}
        if load_all_ant_configs is not None:
            try:
                ant_cfgs = load_all_ant_configs()
            except Exception:
                pass

        def _get_cargo(caste: str) -> float:
            cfg = ant_cfgs.get(caste, {})
            hopper = cfg.get("storage_hopper", {})
            track_key = f"track_{self._track}_capacity_g"
            return hopper.get(track_key, hopper.get("capacity_g", 200))

        def _get_mtbf(caste: str) -> float:
            cfg = ant_cfgs.get(caste, {})
            loco = cfg.get("locomotion", {})
            # Use sealed tunnel MTBF for tunnel ants, vacuum for courier
            if caste == "courier":
                return loco.get("mtbf_hours_vacuum", 2000)
            return loco.get("mtbf_hours_sealed", 8000)

        # Workers — modular, assigned initial roles by the sim
        # Role distribution: ~60% miners, ~10% sorters, ~15% plasterers, ~15% tenders
        role_distribution = {
            "worker": 0.60,       # Mining/hauling (uses drill_head or scoop_head)
            "sorter": 0.10,       # Thermal drum ops (uses thermal_rake)
            "plasterer": 0.15,    # Wall sealing (uses paste_nozzle)
            "tender": 0.15,       # Bioreactor monitoring (uses sampling_probe)
        }
        roles = []
        for role, frac in role_distribution.items():
            roles.extend([role] * max(1, int(self._worker_count * frac)))
        # Fill remaining slots with workers
        while len(roles) < self._worker_count:
            roles.append("worker")
        roles = roles[:self._worker_count]
        random.shuffle(roles)

        for i in range(self._worker_count):
            role = roles[i]
            agent = AntAgent(
                id=agent_id,
                caste=role,  # Visual role (for state machine dispatch)
                position=Position(
                    random.uniform(-2, 2),
                    random.uniform(-2, 2),
                    random.uniform(-2, 2),
                ),
                max_cargo_g=_get_cargo("worker"),
                speed=random.uniform(0.25, 0.4),
                mtbf_hours=_get_mtbf("worker"),
            )
            agent._assigned_segment_id = self.tunnel.active_work_face_id
            agent._target = Position(random.uniform(-3, 3), random.uniform(-3, 3), 0)
            self.agents.append(agent)
            agent_id += 1

        # Taskmasters — patrol the tunnel
        for _ in range(self._taskmaster_count):
            agent = AntAgent(
                id=agent_id,
                caste="taskmaster",
                position=Position(random.uniform(-1, 1), random.uniform(-1, 1), 0),
                speed=random.uniform(0.2, 0.3),
                mtbf_hours=_get_mtbf("taskmaster"),
            )
            agent._target = Position(random.uniform(-5, 5), random.uniform(-5, 5), 0)
            self.agents.append(agent)
            agent_id += 1

        # Surface ants — on the asteroid exterior
        for _ in range(self._surface_ant_count):
            agent = AntAgent(
                id=agent_id,
                caste="surface_ant",
                position=Position(random.uniform(-5, 5), 10, random.uniform(-5, 5)),
                speed=random.uniform(0.15, 0.25),
                mtbf_hours=2000,  # Vacuum — shorter life
            )
            agent._target = Position(random.uniform(-8, 8), 10, random.uniform(-8, 8))
            self.agents.append(agent)
            agent_id += 1

        # Initialize composition variability model
        if get_zones_for_asteroid is not None:
            try:
                from ...catalog import Catalog
                cat = Catalog()
                self._comp_zones = get_zones_for_asteroid("bennu", cat)
                ast = cat.get_asteroid("bennu")
                if ast:
                    comp = ast.get("composition", {})
                    self._bulk_metals = comp.get("metals_ppm", {})
                    self._bulk_water_pct = comp.get("bulk", {}).get("water_hydrated", 0)
            except Exception:
                pass

        # Initialize bioreactor if Track B/C
        if self._has_bioreactor:
            try:
                from ...bioreactor import VatState, VAT_SULFIDE
                self._bioreactor_state = VatState(
                    biomass_g_per_l=0.1,
                    substrate_g_per_l=10.0,
                    ph=VAT_SULFIDE.optimal_ph,
                    temp_c=VAT_SULFIDE.optimal_temp_c,
                    volume_liters=VAT_SULFIDE.volume_liters,
                )
            except ImportError:
                self._has_bioreactor = False

    def tick(self, real_dt: float) -> list[dict[str, Any]]:
        """Advance the simulation by real_dt seconds.

        Returns list of events that occurred this tick.
        """
        sim_dt = self.clock.tick(real_dt)
        if sim_dt <= 0:
            return []

        events = []

        # Tick all agents
        for agent in self.agents:
            agent_events = agent.tick(sim_dt, tunnel=self.tunnel)

            if "material_dumped_g" in agent_events:
                kg = agent_events["material_dumped_g"] / 1000.0
                self.stats.total_material_extracted_kg += kg
                self.stats.total_dump_cycles += 1
                # Sample composition variability for this batch
                if self._comp_zones and sample_regolith and self._bulk_metals:
                    sample = sample_regolith(
                        self._bulk_metals, self._bulk_water_pct,
                        kg, self._comp_zones,
                        depth_m=self.tunnel.total_length_m,
                    )
                    self._zone_hits[sample.zone] = self._zone_hits.get(sample.zone, 0) + 1

            if "water_recovered_g" in agent_events:
                kg = agent_events["water_recovered_g"] / 1000.0
                self.stats.total_water_recovered_kg += kg
                self.tunnel.record_water_recovery(kg)
                self.stats.total_drum_cycles += 1

            if "area_sealed_m2" in agent_events:
                self.stats.total_area_sealed_m2 += agent_events["area_sealed_m2"]

            if "vat_checked" in agent_events:
                self.stats.total_vat_checks += 1

            if "anomaly_detected" in agent_events:
                self.stats.anomalies_detected += 1
                events.append({
                    "type": "anomaly",
                    "time": self.clock.sim_time,
                    "message": agent_events["anomaly_detected"],
                    "ant_id": agent.id,
                })

            if "failure" in agent_events:
                self.stats.ants_failed += 1
                events.append({
                    "type": "failure",
                    "time": self.clock.sim_time,
                    "message": agent_events["failure"],
                    "ant_id": agent.id,
                })

            if "drum_cycle_complete" in agent_events:
                events.append({
                    "type": "drum_cycle",
                    "time": self.clock.sim_time,
                })

        # Process communication queues
        arrived_commands, arrived_telemetry = self.comms.tick(self.clock.sim_time)
        for cmd in arrived_commands:
            events.append({
                "type": "command_received",
                "time": self.clock.sim_time,
                "command": cmd.content,
            })

        # Update bioreactor state (hourly in sim-time)
        if (self._has_bioreactor and self._bioreactor_state and
                self.clock.sim_time - self._last_bioreactor_update >= self._bioreactor_update_interval):
            try:
                from ...bioreactor import simulate_vat, VAT_SULFIDE
                results = simulate_vat(VAT_SULFIDE, self._bioreactor_state, duration_hours=1.0)
                if results:
                    self._bioreactor_state = results[-1]
                    # Track metals extracted
                    new_metals = self._bioreactor_state.metal_dissolved_g_per_l * VAT_SULFIDE.volume_liters / 1000
                    self.stats.metals_extracted_kg = new_metals
                    self.stats.biomass_g_per_l = self._bioreactor_state.biomass_g_per_l
            except ImportError:
                pass
            self._last_bioreactor_update = self.clock.sim_time

        # Periodic telemetry broadcast
        if self.clock.sim_time - self._last_telemetry_time >= self._telemetry_interval:
            self._broadcast_telemetry()
            self._last_telemetry_time = self.clock.sim_time

        self.event_log.extend(events)
        return events

    def _broadcast_telemetry(self) -> None:
        """Send status telemetry from asteroid to Earth."""
        active = sum(1 for a in self.agents if a.state != AntState.FAILED)
        failed = sum(1 for a in self.agents if a.state == AntState.FAILED)

        telemetry = {
            "type": "status",
            "sim_time": self.clock.sim_time,
            "elapsed": self.clock.format_elapsed(),
            "ants_active": active,
            "ants_failed": failed,
            "tunnel": self.tunnel.summary(),
            "material_extracted_kg": round(self.stats.total_material_extracted_kg, 1),
            "water_recovered_kg": round(self.stats.total_water_recovered_kg, 1),
            "area_sealed_m2": round(self.stats.total_area_sealed_m2, 1),
        }
        self.comms.send_telemetry(telemetry, self.clock.sim_time)

    def send_player_command(self, command: dict[str, Any]) -> None:
        """Player (Earth ground control) sends a command."""
        self.comms.send_command(command, self.clock.sim_time)

    def status(self) -> dict[str, Any]:
        """Current simulation status (no comm delay — god-view for debugging)."""
        by_caste: dict[str, dict[str, int]] = {}
        for agent in self.agents:
            if agent.caste not in by_caste:
                by_caste[agent.caste] = {"active": 0, "failed": 0}
            if agent.state == AntState.FAILED:
                by_caste[agent.caste]["failed"] += 1
            else:
                by_caste[agent.caste]["active"] += 1

        return {
            "clock": self.clock.format_elapsed(),
            "speed": self.clock.speed,
            "paused": self.clock.paused,
            "ants_by_caste": by_caste,
            "total_ants": len(self.agents),
            "tunnel": self.tunnel.summary(),
            "stats": {
                "material_kg": round(self.stats.total_material_extracted_kg, 1),
                "water_kg": round(self.stats.total_water_recovered_kg, 1),
                "sealed_m2": round(self.stats.total_area_sealed_m2, 1),
                "dump_cycles": self.stats.total_dump_cycles,
                "drum_cycles": self.stats.total_drum_cycles,
                "vat_checks": self.stats.total_vat_checks,
                "anomalies": self.stats.anomalies_detected,
                "failures": self.stats.ants_failed,
                "metals_extracted_kg": round(self.stats.metals_extracted_kg, 3),
                "biomass_g_per_l": round(self.stats.biomass_g_per_l, 3),
            },
            "comms": {
                "delay_minutes": round(self.comms.one_way_delay_minutes, 1),
                "pending_commands": len(self.comms.pending_outbound()),
                "pending_telemetry": len(self.comms.pending_inbound()),
            },
        }
