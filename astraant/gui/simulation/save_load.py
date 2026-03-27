"""Save/load game state to JSON files.

Serializes the complete simulation state including:
- All agent positions, health, roles, tools
- Tunnel network topology
- Material ledger (every kg)
- Game economy (cash, revenue, pods in transit)
- Manufacturing state
- Mining priorities and discovered zones
- Endgame habitat progress
- Anomalies found
- Random event history
- Upgrade purchases
- Mission clock (elapsed time, speed)

Auto-save fires every N minutes of real time.
Save files go to output/saves/ directory.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

SAVE_DIR = Path(__file__).parent.parent.parent.parent / "output" / "saves"


def _serialize_agent(agent) -> dict:
    """Serialize one ant agent to a dict."""
    return {
        "id": agent.id,
        "caste": agent.caste,
        "position": {"x": agent.position.x, "y": agent.position.y, "z": agent.position.z},
        "state": agent.state.value if hasattr(agent.state, 'value') else int(agent.state),
        "health": agent.health,
        "cargo_g": agent.cargo_g,
        "max_cargo_g": agent.max_cargo_g,
        "speed": agent.speed,
        "power_level": agent.power_level,
        "hours_operated": agent.hours_operated,
        "mtbf_hours": agent.mtbf_hours,
        "_current_tool": agent._current_tool,
        "_squad_leader_id": agent._squad_leader_id,
        "_surface_angle": agent._surface_angle,
        "_tunnel_depth": agent._tunnel_depth,
        "_cycle_count": agent._cycle_count,
    }


def _serialize_tunnel(tunnel) -> dict:
    """Serialize the tunnel network."""
    nodes = []
    for n in tunnel.nodes:
        nodes.append({
            "id": n.id,
            "position": {"x": n.position.x, "y": n.position.y, "z": n.position.z},
            "is_entrance": n.is_entrance,
            "is_chamber": n.is_chamber,
        })

    segments = []
    for s in tunnel.segments:
        segments.append({
            "id": s.id,
            "from_node_id": s.from_node_id,
            "to_node_id": s.to_node_id,
            "length_m": s.length_m,
            "diameter_m": s.diameter_m,
            "sealed": s.sealed,
            "seal_quality": s.seal_quality,
            "pressurized": s.pressurized,
            "pressure_kpa": s.pressure_kpa,
            "material_extracted_kg": s.material_extracted_kg,
            "zone_type": s.zone_type,
            "zone_richness": s.zone_richness,
            "rail_installed": s.rail_installed,
        })

    chamber = None
    if tunnel.common_chamber:
        c = tunnel.common_chamber
        chamber = {
            "center": {"x": c.center.x, "y": c.center.y, "z": c.center.z},
            "target_radius_m": c.target_radius_m,
            "current_radius_m": c.current_radius_m,
            "material_removed_kg": c.material_removed_kg,
            "sealed": c.sealed,
            "purpose": c.purpose,
        }

    return {
        "site_id": tunnel.site_id,
        "nodes": nodes,
        "segments": segments,
        "total_material_extracted_kg": tunnel.total_material_extracted_kg,
        "total_water_recovered_kg": tunnel.total_water_recovered_kg,
        "common_chamber": chamber,
    }


def save_game(engine, filepath: Path | str | None = None,
              slot_name: str = "quicksave") -> Path:
    """Save the complete game state to a JSON file.

    Args:
        engine: SimEngine instance
        filepath: Explicit path, or None to auto-generate
        slot_name: Name for the save slot (used in auto-generated filename)

    Returns: Path to the saved file
    """
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    if filepath is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{slot_name}_{timestamp}.json"
        filepath = SAVE_DIR / filename

    filepath = Path(filepath)

    state = {
        "version": "0.1.0",
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "slot_name": slot_name,

        # Mission clock
        "clock": {
            "sim_time": engine.clock.sim_time,
            "speed": engine.clock.speed,
            "paused": engine.clock.paused,
            "total_real_time": engine.clock.total_real_time,
        },

        # Agents
        "agents": [_serialize_agent(a) for a in engine.agents],

        # Tunnel
        "tunnel": _serialize_tunnel(engine.tunnel),

        # Stats
        "stats": {
            "total_material_extracted_kg": engine.stats.total_material_extracted_kg,
            "total_water_recovered_kg": engine.stats.total_water_recovered_kg,
            "total_area_sealed_m2": engine.stats.total_area_sealed_m2,
            "total_dump_cycles": engine.stats.total_dump_cycles,
            "total_drum_cycles": engine.stats.total_drum_cycles,
            "total_vat_checks": engine.stats.total_vat_checks,
            "anomalies_detected": engine.stats.anomalies_detected,
            "ants_failed": engine.stats.ants_failed,
            "metals_extracted_kg": engine.stats.metals_extracted_kg,
            "biomass_g_per_l": engine.stats.biomass_g_per_l,
        },

        # Mining priorities
        "mining": {
            "target_metal": engine.mining.target_metal,
            "total_revenue_usd": engine.mining.total_revenue_usd,
            "revenue_by_material": dict(engine.mining.revenue_by_material),
            "profitable": engine.mining.profitable,
            "time_to_profit_hours": engine.mining.time_to_profit_hours,
            "discovered_zones": engine.mining.discovered_zones,
        },

        # Manufacturing
        "manufacturing": {
            "enabled": engine.manufacturing.enabled,
            "ants_queued": engine.manufacturing.ants_queued,
            "ants_in_progress": engine.manufacturing.ants_in_progress,
            "ants_completed": engine.manufacturing.ants_completed,
            "pods_queued": engine.manufacturing.pods_queued,
            "pods_completed": engine.manufacturing.pods_completed,
            "parts_ready": engine.manufacturing.parts_ready,
        },

        # Economy
        "economy": {
            "initial_budget_usd": engine.economy.initial_budget_usd,
            "cash_on_hand_usd": engine.economy.cash_on_hand_usd,
            "total_spent_usd": engine.economy.total_spent_usd,
            "total_revenue_received_usd": engine.economy.total_revenue_received_usd,
            "pods_delivered": engine.economy.pods_delivered,
            "resupply_missions_sent": engine.economy.resupply_missions_sent,
            "profitable": engine.economy.profitable,
        },

        # Material ledger
        "ledger": engine.ledger.summary(),

        # Fleet
        "mothership_count": engine.mothership_count,
        "_fleet_multiplier": engine._fleet_multiplier,
        "_dig_position": list(engine._dig_position),

        # Endgame
        "endgame": engine.habitat_goal.summary() if engine.habitat_goal else None,

        # Upgrades purchased
        "upgrades": engine.upgrade_manager.summary(),

        # Event history
        "event_history": engine.event_system.event_history[-50:],

        # Anomaly count
        "anomaly_count": len(engine.anomaly_detector.anomalies),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)

    return filepath


def load_game(filepath: Path | str, engine) -> bool:
    """Load a saved game state into an existing engine instance.

    Args:
        filepath: Path to the save file
        engine: SimEngine instance to restore state into

    Returns: True if loaded successfully
    """
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"Save file not found: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Restore clock
    clock = state.get("clock", {})
    engine.clock.sim_time = clock.get("sim_time", 0)
    engine.clock.speed = clock.get("speed", 1.0)
    engine.clock.paused = clock.get("paused", False)
    engine.clock.total_real_time = clock.get("total_real_time", 0)

    # Restore agents
    from .ant_agent import AntAgent, AntState, Position
    engine.agents.clear()
    for adata in state.get("agents", []):
        pos = adata.get("position", {})
        agent = AntAgent(
            id=adata["id"],
            caste=adata["caste"],
            position=Position(pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)),
            health=adata.get("health", 1.0),
            cargo_g=adata.get("cargo_g", 0),
            max_cargo_g=adata.get("max_cargo_g", 200),
            speed=adata.get("speed", 0.3),
            power_level=adata.get("power_level", 1.0),
        )
        agent.hours_operated = adata.get("hours_operated", 0)
        agent.mtbf_hours = adata.get("mtbf_hours", 8000)
        agent._current_tool = adata.get("_current_tool", "")
        agent._squad_leader_id = adata.get("_squad_leader_id", -1)
        agent._surface_angle = adata.get("_surface_angle", 0)
        agent._tunnel_depth = adata.get("_tunnel_depth", 0)
        agent._cycle_count = adata.get("_cycle_count", 0)
        # Restore state enum
        state_val = adata.get("state", 1)
        try:
            agent.state = AntState(state_val)
        except (ValueError, KeyError):
            agent.state = AntState.IDLE
        engine.agents.append(agent)

    engine._next_agent_id = max((a.id for a in engine.agents), default=0) + 1

    # Restore stats
    stats = state.get("stats", {})
    engine.stats.total_material_extracted_kg = stats.get("total_material_extracted_kg", 0)
    engine.stats.total_water_recovered_kg = stats.get("total_water_recovered_kg", 0)
    engine.stats.total_area_sealed_m2 = stats.get("total_area_sealed_m2", 0)
    engine.stats.total_dump_cycles = stats.get("total_dump_cycles", 0)
    engine.stats.total_drum_cycles = stats.get("total_drum_cycles", 0)
    engine.stats.total_vat_checks = stats.get("total_vat_checks", 0)
    engine.stats.anomalies_detected = stats.get("anomalies_detected", 0)
    engine.stats.ants_failed = stats.get("ants_failed", 0)
    engine.stats.metals_extracted_kg = stats.get("metals_extracted_kg", 0)
    engine.stats.biomass_g_per_l = stats.get("biomass_g_per_l", 0.1)

    # Restore mining
    mining = state.get("mining", {})
    engine.mining.target_metal = mining.get("target_metal", "")
    engine.mining.total_revenue_usd = mining.get("total_revenue_usd", 0)
    engine.mining.revenue_by_material = mining.get("revenue_by_material", {})
    engine.mining.profitable = mining.get("profitable", False)
    engine.mining.time_to_profit_hours = mining.get("time_to_profit_hours", 0)
    engine.mining.discovered_zones = mining.get("discovered_zones", [])

    # Restore manufacturing
    mfg = state.get("manufacturing", {})
    engine.manufacturing.enabled = mfg.get("enabled", False)
    engine.manufacturing.ants_queued = mfg.get("ants_queued", 0)
    engine.manufacturing.ants_completed = mfg.get("ants_completed", 0)
    engine.manufacturing.pods_completed = mfg.get("pods_completed", 0)
    engine.manufacturing.parts_ready = mfg.get("parts_ready", 0)

    # Restore economy
    econ = state.get("economy", {})
    engine.economy.initial_budget_usd = econ.get("initial_budget_usd", 163_000_000)
    engine.economy.cash_on_hand_usd = econ.get("cash_on_hand_usd", 0)
    engine.economy.total_spent_usd = econ.get("total_spent_usd", 0)
    engine.economy.total_revenue_received_usd = econ.get("total_revenue_received_usd", 0)
    engine.economy.pods_delivered = econ.get("pods_delivered", 0)
    engine.economy.resupply_missions_sent = econ.get("resupply_missions_sent", 0)
    engine.economy.profitable = econ.get("profitable", False)

    # Restore fleet
    engine.mothership_count = state.get("mothership_count", 1)
    engine._fleet_multiplier = state.get("_fleet_multiplier", 1.0)
    engine._dig_position = state.get("_dig_position", [0, -3, 0])

    print(f"Game loaded: {filepath.name}")
    print(f"  Sim time: {engine.clock.format_elapsed()}")
    print(f"  Agents: {len(engine.agents)}")
    print(f"  Revenue: ${engine.mining.total_revenue_usd:,.0f}")
    return True


def list_saves() -> list[dict[str, Any]]:
    """List all save files with metadata."""
    if not SAVE_DIR.exists():
        return []

    saves = []
    for f in sorted(SAVE_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            saves.append({
                "filename": f.name,
                "path": str(f),
                "slot_name": data.get("slot_name", "unknown"),
                "saved_at": data.get("saved_at", "?"),
                "sim_time": data.get("clock", {}).get("sim_time", 0),
                "agents": len(data.get("agents", [])),
                "revenue": data.get("mining", {}).get("total_revenue_usd", 0),
            })
        except (json.JSONDecodeError, KeyError):
            saves.append({"filename": f.name, "path": str(f), "error": "corrupt"})

    return saves


class AutoSaver:
    """Auto-saves the game at regular intervals."""

    def __init__(self, interval_seconds: float = 300):  # Every 5 minutes
        self.interval = interval_seconds
        self.last_save_time = time.time()
        self.save_count = 0

    def check(self, engine) -> Path | None:
        """Check if it's time to auto-save. Returns save path if saved."""
        now = time.time()
        if now - self.last_save_time >= self.interval:
            self.last_save_time = now
            self.save_count += 1
            path = save_game(engine, slot_name="autosave")
            return path
        return None
