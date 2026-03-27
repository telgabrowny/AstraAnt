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
class MiningPriority:
    """Player-set mining priority — what materials to focus on."""
    target_metal: str = ""           # "" = no priority (mine everything)
    preferred_zone: str = ""         # Zone type to dig toward
    discovered_zones: list = field(default_factory=list)  # Zones found by taskmasters

    # Revenue tracking for gamification
    total_revenue_usd: float = 0.0
    revenue_by_material: dict = field(default_factory=dict)
    profitable: bool = False         # Have we broken even yet?
    time_to_profit_hours: float = 0.0
    mission_cost_usd: float = 3_000_000.0  # From feasibility model


@dataclass
class ManufacturingState:
    """State of the in-situ manufacturing bay."""
    enabled: bool = False
    iron_stockpile_kg: float = 0.0
    copper_stockpile_kg: float = 0.0
    # Build queue
    ants_queued: int = 0             # Player-ordered ants to build
    ants_in_progress: int = 0        # Currently being assembled
    ants_completed: int = 0          # Finished and deployed
    pods_queued: int = 0
    pods_completed: int = 0
    # Pipeline tracking
    parts_sintering: int = 0         # Parts in the furnace right now
    parts_ready: int = 0             # Sintered, waiting for assembly
    parts_per_ant: int = 20          # Parts needed for one ant
    sinter_time_hours: float = 2.0   # Hours per part
    assembly_time_hours: float = 1.0
    # Timers
    current_sinter_timer: float = 0.0
    current_assembly_timer: float = 0.0
    # Workers assigned to manufacturing
    workers_assigned: int = 0


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
        self.manufacturing = ManufacturingState()
        self.mining = MiningPriority()
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

        # Tool assignment per role
        role_tools = {
            "worker": "drill_head",
            "sorter": "thermal_rake",
            "plasterer": "paste_nozzle",
            "tender": "sampling_probe",
        }

        worker_ids = []
        for i in range(self._worker_count):
            role = roles[i]
            agent = AntAgent(
                id=agent_id,
                caste=role,
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
            agent._current_tool = role_tools.get(role, "drill_head")
            self.agents.append(agent)
            worker_ids.append(agent_id)
            agent_id += 1

        # Taskmasters — patrol the tunnel, each leads a squad of workers
        tm_ids = []
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
            tm_ids.append(agent_id)
            agent_id += 1

        # Assign workers to taskmaster squads (round-robin)
        if tm_ids:
            for i, wid in enumerate(worker_ids):
                tm_id = tm_ids[i % len(tm_ids)]
                worker = next(a for a in self.agents if a.id == wid)
                worker._squad_leader_id = tm_id
                tm = next(a for a in self.agents if a.id == tm_id)
                tm._squad_member_ids.append(wid)

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
                    # If mining priority targets a specific zone, bias toward it
                    zones = self._comp_zones
                    sample = sample_regolith(
                        self._bulk_metals, self._bulk_water_pct,
                        kg, zones,
                        depth_m=self.tunnel.total_length_m,
                    )
                    self._zone_hits[sample.zone] = self._zone_hits.get(sample.zone, 0) + 1

                    # Assign zone to current tunnel segment
                    active_seg = None
                    for seg in self.tunnel.segments:
                        if seg.id == self.tunnel.active_work_face_id:
                            active_seg = seg
                            break
                    if active_seg and not active_seg.zone_type:
                        active_seg.zone_type = sample.zone

                    # Taskmaster "discovers" valuable zones
                    if sample.zone in ("sulfide_pocket", "metal_grain"):
                        if sample.zone not in [d["zone"] for d in self.mining.discovered_zones]:
                            self.mining.discovered_zones.append({
                                "zone": sample.zone,
                                "segment_id": self.tunnel.active_work_face_id,
                                "depth_m": self.tunnel.total_length_m,
                                "time": self.clock.sim_time,
                            })
                            events.append({
                                "type": "zone_discovered",
                                "time": self.clock.sim_time,
                                "message": f"ZONE FOUND: {sample.zone} at {self.tunnel.total_length_m:.0f}m depth!",
                                "zone": sample.zone,
                            })

                    # Track revenue from this batch at lunar orbit prices
                    # (simplified: use the sample's metal content)
                    lunar_prices = {
                        "iron": 2000, "nickel": 5000, "copper": 8000,
                        "cobalt": 12000, "platinum": 35000, "palladium": 45000,
                        "iridium": 55000, "rare_earths_total": 25000,
                    }
                    batch_revenue = 0.0
                    for metal, ppm in sample.metals_ppm.items():
                        metal_kg = kg * ppm / 1_000_000 * 0.85  # extraction efficiency
                        price = lunar_prices.get(metal, 1000)
                        rev = metal_kg * price
                        batch_revenue += rev
                        self.mining.revenue_by_material[metal] = (
                            self.mining.revenue_by_material.get(metal, 0) + rev
                        )
                    # Water revenue
                    water_kg = kg * sample.water_pct / 100 * 0.90
                    water_rev = water_kg * 50000  # $50K/kg at lunar orbit
                    batch_revenue += water_rev
                    self.mining.revenue_by_material["water"] = (
                        self.mining.revenue_by_material.get("water", 0) + water_rev
                    )
                    self.mining.total_revenue_usd += batch_revenue

                    # Check profitability
                    if not self.mining.profitable and self.mining.total_revenue_usd > self.mining.mission_cost_usd:
                        self.mining.profitable = True
                        self.mining.time_to_profit_hours = self.clock.sim_time / 3600
                        events.append({
                            "type": "profitable",
                            "time": self.clock.sim_time,
                            "message": f"PROFITABLE! Revenue ${self.mining.total_revenue_usd:,.0f} exceeds "
                                       f"cost ${self.mining.mission_cost_usd:,.0f} at "
                                       f"{self.clock.format_elapsed()}",
                        })

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

        # Auto-branch tunnels periodically and contribute to chamber
        if len(self.tunnel.segments) > 0:
            # Branch every ~50m of tunnel growth
            if self.tunnel.total_length_m > (len(self.tunnel.segments) * 5):
                if random.random() < 0.01:  # Small chance each tick
                    self.tunnel.branch_tunnel(self.tunnel.active_work_face_id)

            # If digging toward common chamber, contribute material
            if self.tunnel.common_chamber and self.tunnel.deepest_point_m > 25:
                # Once deep enough, material goes toward chamber excavation
                chamber_contribution = sim_dt * 0.001  # Slow chamber growth
                self.tunnel.contribute_to_chamber(chamber_contribution)

        # Feed extracted material into manufacturing stockpile
        # A fraction of mined material becomes iron/copper powder after bioleaching
        mfg = self.manufacturing
        if mfg.enabled:
            # Iron is ~20% of regolith on Bennu, extraction efficiency ~85%
            iron_this_tick = self.stats.total_dump_cycles * 0.001  # Rough: small increment per dump
            mfg.iron_stockpile_kg = max(0, self.stats.total_material_extracted_kg * 0.003)  # ~0.3% yield as usable iron powder
            mfg.copper_stockpile_kg = max(0, self.stats.total_material_extracted_kg * 0.00001)  # Very little copper

        # Process manufacturing queue
        if mfg.enabled and (mfg.ants_queued > 0 or mfg.pods_queued > 0):
            events.extend(self._tick_manufacturing(sim_dt))

        # Process communication queues
        arrived_commands, arrived_telemetry = self.comms.tick(self.clock.sim_time)
        for cmd in arrived_commands:
            self._handle_command(cmd.content, events)
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

    def _tick_manufacturing(self, sim_dt: float) -> list[dict[str, Any]]:
        """Process the manufacturing pipeline each tick."""
        events = []
        mfg = self.manufacturing
        dt_hours = sim_dt / 3600.0

        # SINTERING: convert iron stockpile into parts
        if mfg.ants_queued > 0 and mfg.iron_stockpile_kg >= 0.025:
            mfg.current_sinter_timer += dt_hours
            if mfg.current_sinter_timer >= mfg.sinter_time_hours:
                mfg.current_sinter_timer = 0.0
                mfg.parts_ready += 1
                mfg.iron_stockpile_kg -= 0.025  # ~25g iron per part
                mfg.parts_sintering = min(mfg.ants_queued * mfg.parts_per_ant - mfg.parts_ready, 1)

        # ASSEMBLY: when enough parts ready, start assembling an ant
        if (mfg.parts_ready >= mfg.parts_per_ant and
                mfg.ants_queued > 0 and mfg.ants_in_progress < 3):  # 3 jigs max
            mfg.parts_ready -= mfg.parts_per_ant
            mfg.ants_in_progress += 1
            mfg.ants_queued -= 1
            mfg.current_assembly_timer = 0.0
            events.append({
                "type": "manufacturing",
                "time": self.clock.sim_time,
                "message": f"Assembly started: ant #{mfg.ants_completed + mfg.ants_in_progress}",
            })

        # ASSEMBLY PROGRESS: tick assembly timers
        if mfg.ants_in_progress > 0:
            mfg.current_assembly_timer += dt_hours
            if mfg.current_assembly_timer >= mfg.assembly_time_hours:
                mfg.current_assembly_timer = 0.0
                mfg.ants_in_progress -= 1
                mfg.ants_completed += 1
                # SPAWN THE NEW ANT
                new_ant = self._spawn_new_ant()
                events.append({
                    "type": "ant_built",
                    "time": self.clock.sim_time,
                    "message": f"NEW ANT ONLINE: {new_ant.caste} #{new_ant.id}",
                    "ant_id": new_ant.id,
                })

        # PODS: simpler — just need waste paste, no sintering
        if mfg.pods_queued > 0:
            # One pod every 5 sim-hours from ferrocement
            mfg.pods_queued -= 1
            mfg.pods_completed += 1

        return events

    def _spawn_new_ant(self) -> AntAgent:
        """Create a new worker ant from manufacturing and add to the swarm."""
        agent_id = max((a.id for a in self.agents), default=0) + 1

        # Assign a role (same distribution as initial setup)
        role = random.choice(["worker"] * 6 + ["sorter"] + ["plasterer"] * 2 + ["tender"] * 2)

        agent = AntAgent(
            id=agent_id,
            caste=role,
            position=Position(
                random.uniform(-1, 1),
                random.uniform(-1, 1),
                random.uniform(2, 4),  # Near the manufacturing bay
            ),
            max_cargo_g=200,
            speed=random.uniform(0.25, 0.4),
            mtbf_hours=8000,
        )
        agent._assigned_segment_id = self.tunnel.active_work_face_id
        agent._target = Position(random.uniform(-3, 3), random.uniform(-3, 3), 0)
        self.agents.append(agent)
        return agent

    def _handle_command(self, command: dict[str, Any], events: list) -> None:
        """Process a command that arrived from ground control."""
        cmd_type = command.get("type", "")

        if cmd_type == "build_ants":
            count = command.get("count", 10)
            self.manufacturing.enabled = True
            self.manufacturing.ants_queued += count
            events.append({
                "type": "manufacturing",
                "time": self.clock.sim_time,
                "message": f"BUILD ORDER: {count} new ants queued for manufacturing",
            })

        elif cmd_type == "build_pods":
            count = command.get("count", 50)
            self.manufacturing.enabled = True
            self.manufacturing.pods_queued += count

        elif cmd_type == "prioritize":
            metal = command.get("metal", "")
            self.mining.target_metal = metal
            events.append({
                "type": "priority_set",
                "time": self.clock.sim_time,
                "message": f"MINING PRIORITY: {metal if metal else 'none (balanced)'}",
            })

        elif cmd_type == "emergency_stop":
            # Stop all workers
            for agent in self.agents:
                if agent.caste not in ("taskmaster", "surface_ant"):
                    agent.state = AntState.IDLE

        elif cmd_type == "retarget":
            # Just log it — actual retargeting would change tunnel segment assignments
            pass

        elif cmd_type == "dig_toward":
            # Player directs dig toward specific coordinates
            from .tunnel_state import Vec3 as TV3
            x = command.get("x", 0)
            y = command.get("y", -50)
            z = command.get("z", 0)
            self.tunnel.set_dig_target(TV3(x, y, z))
            events.append({
                "type": "dig_redirect",
                "time": self.clock.sim_time,
                "message": f"DIG TARGET SET: ({x}, {y}, {z})",
            })

        elif cmd_type == "branch_tunnel":
            self.tunnel.branch_tunnel(self.tunnel.active_work_face_id)
            events.append({
                "type": "branch",
                "time": self.clock.sim_time,
                "message": f"New tunnel branch started from segment {self.tunnel.active_work_face_id}",
            })

        elif cmd_type == "set_chamber_goal":
            from .tunnel_state import Vec3 as TV3, CommonChamber
            radius = command.get("radius_m", 8)
            purpose = command.get("purpose", "common operations hub")
            self.tunnel.common_chamber = CommonChamber(
                center=TV3(0, -30, 0),  # Deep inside asteroid
                target_radius_m=radius,
                purpose=purpose,
            )
            events.append({
                "type": "chamber_goal",
                "time": self.clock.sim_time,
                "message": f"CHAMBER GOAL: {radius}m radius sphere at 30m depth -- {purpose}",
            })

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
            "mining": {
                "priority": self.mining.target_metal or "balanced",
                "revenue_usd": round(self.mining.total_revenue_usd, 0),
                "profitable": self.mining.profitable,
                "time_to_profit": self.mining.time_to_profit_hours,
                "zones_discovered": len(self.mining.discovered_zones),
                "top_revenue": sorted(
                    self.mining.revenue_by_material.items(),
                    key=lambda x: -x[1]
                )[:3] if self.mining.revenue_by_material else [],
            },
            "manufacturing": {
                "enabled": self.manufacturing.enabled,
                "iron_stockpile_kg": round(self.manufacturing.iron_stockpile_kg, 2),
                "ants_queued": self.manufacturing.ants_queued,
                "ants_in_progress": self.manufacturing.ants_in_progress,
                "ants_completed": self.manufacturing.ants_completed,
                "parts_ready": self.manufacturing.parts_ready,
                "pods_completed": self.manufacturing.pods_completed,
            },
        }
