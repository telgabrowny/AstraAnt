"""Configuration loader for ant castes and mothership modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_ant_config(caste: str) -> dict[str, Any]:
    """Load ant configuration for a given caste (worker, taskmaster, courier)."""
    path = CONFIGS_DIR / "ants" / f"{caste}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No ant config for caste '{caste}' at {path}")
    return _load_yaml(path)


def load_mothership_module(module_name: str) -> dict[str, Any]:
    """Load a mothership module configuration."""
    path = CONFIGS_DIR / "mothership" / f"{module_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No mothership module '{module_name}' at {path}")
    return _load_yaml(path)


def load_all_ant_configs() -> dict[str, dict[str, Any]]:
    """Load all ant caste configs."""
    ant_dir = CONFIGS_DIR / "ants"
    if not ant_dir.exists():
        return {}
    configs = {}
    for filepath in sorted(ant_dir.glob("*.yaml")):
        caste = filepath.stem
        configs[caste] = _load_yaml(filepath)
    return configs


def load_all_mothership_modules() -> dict[str, dict[str, Any]]:
    """Load all mothership module configs."""
    mod_dir = CONFIGS_DIR / "mothership"
    if not mod_dir.exists():
        return {}
    modules = {}
    for filepath in sorted(mod_dir.glob("*.yaml")):
        name = filepath.stem
        modules[name] = _load_yaml(filepath)
    return modules


def compute_ant_mass(config: dict[str, Any], catalog: Any = None) -> float:
    """Compute total mass of an ant from its config (grams)."""
    mass = 0.0

    # Chassis base mass (estimate from config or default)
    mass += config.get("chassis", {}).get("base_mass_g", 30)

    # Compute module
    mass += config.get("compute", {}).get("mass_g", 5)

    # Locomotion
    loco = config.get("locomotion", {})
    n_actuators = loco.get("actuators", 6)
    per_mass = loco.get("per_unit_mass_g", 9)
    mass += n_actuators * per_mass

    # Communication
    for comm in _as_list(config.get("communication", {})):
        mass += comm.get("mass_g", 5)

    # Sensors
    for sensor in config.get("sensors", []):
        mass += sensor.get("mass_g", 2)

    # Tool
    tool = config.get("tool", {})
    mass += tool.get("mass_g", 10)

    # Solar (if present)
    solar = config.get("solar", {})
    mass += solar.get("mass_g", 0)

    # Sail (if present)
    sail = config.get("sail", {})
    mass += sail.get("mass_g", 0)

    # Thermal (if present)
    thermal = config.get("thermal", {})
    mass += thermal.get("mass_g", 0)

    # Battery (if present)
    battery = config.get("battery", {})
    mass += battery.get("mass_g", 0)

    # Hopper
    mass += config.get("storage_hopper", {}).get("hopper_mass_g", 10)

    return mass


def compute_ant_power(config: dict[str, Any]) -> dict[str, float]:
    """Compute power budget for an ant (milliwatts). Returns idle/active/peak."""
    idle = 0.0
    active = 0.0

    # Compute — always on
    compute_power = config.get("compute", {}).get("power_draw_mw", 100)
    idle += compute_power
    active += compute_power

    # Locomotion — active only
    loco = config.get("locomotion", {})
    n_actuators = loco.get("actuators", 6)
    per_power = loco.get("per_unit_power_mw", 600)
    # Assume 50% duty cycle on average for locomotion
    active += n_actuators * per_power * 0.5

    # Sensors — always on
    for sensor in config.get("sensors", []):
        power = sensor.get("power_mw", 5)
        idle += power
        active += power

    # Communication — intermittent
    for comm in _as_list(config.get("communication", {})):
        power = comm.get("power_mw", 40)
        idle += power * 0.1  # 10% duty cycle idle
        active += power * 0.3  # 30% duty cycle active

    # Tool — active only
    tool = config.get("tool", {})
    tool_power = tool.get("power_mw", 0)
    active += tool_power

    # Thermal — duty cycle dependent on environment
    thermal = config.get("thermal", {})
    heater = thermal.get("heater_power_mw", 0)
    active += heater * 0.2  # 20% duty cycle estimate

    return {
        "idle_mw": round(idle, 1),
        "active_mw": round(active, 1),
        "peak_mw": round(active * 1.5, 1),  # Peak estimate
    }


def compute_ant_cost(config: dict[str, Any], catalog: Any = None) -> float:
    """Estimate total cost of an ant from config (USD). Uses catalog prices if available."""
    # Simple estimate from config-embedded costs
    cost = 0.0
    cost += config.get("compute", {}).get("cost_usd", 5)

    loco = config.get("locomotion", {})
    n_actuators = loco.get("actuators", 6)
    cost += n_actuators * loco.get("per_unit_cost_usd", 3)

    for comm in _as_list(config.get("communication", {})):
        cost += comm.get("cost_usd", 5)

    for sensor in config.get("sensors", []):
        cost += sensor.get("cost_usd", 5)

    tool = config.get("tool", {})
    cost += tool.get("cost_usd", 5)

    solar = config.get("solar", {})
    cost += solar.get("cost_usd", 0)

    sail = config.get("sail", {})
    cost += sail.get("cost_usd", 0)

    return cost


def _as_list(val: Any) -> list:
    """Normalize a value to a list (handles both single dict and list of dicts)."""
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val]
    return []
