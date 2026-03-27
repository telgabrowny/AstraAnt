"""Feasibility calculator --mass budgets, power budgets, cost estimates, break-even analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog, CatalogEntry
from .configs import (
    compute_ant_cost,
    compute_ant_mass,
    compute_ant_power,
    load_all_ant_configs,
    load_all_mothership_modules,
)


# Launch costs in $/kg to LEO --user can override
LAUNCH_VEHICLES = {
    "falcon_9": {"cost_per_kg_usd": 2700, "payload_leo_kg": 22800},
    "falcon_heavy": {"cost_per_kg_usd": 1500, "payload_leo_kg": 63800},
    "starship": {"cost_per_kg_usd": 200, "payload_leo_kg": 150000},  # Projected
    "starship_conservative": {"cost_per_kg_usd": 500, "payload_leo_kg": 100000},
}

# Destination delta-v multipliers (rough, from LEO)
# These multiply the launch mass via the rocket equation or a simpler mass penalty
DESTINATION_MASS_MULTIPLIER = {
    "leo": 1.0,
    "lunar_orbit": 2.5,    # ~4 km/s additional from LEO
    "earth_moon_l2": 2.3,
    "mars_orbit": 3.5,     # ~5.5 km/s additional
    "nea_direct": 3.0,     # Varies hugely by target
}

# Material values by destination ($/kg)
MATERIAL_VALUES = {
    "earth_return": {
        "water": 0.001,
        "iron": 0.50,
        "nickel": 18.0,
        "copper": 9.0,
        "cobalt": 30.0,
        "platinum": 30000.0,
        "palladium": 40000.0,
        "iridium": 50000.0,
        "rare_earths": 100.0,  # Average, varies widely
    },
    "lunar_orbit": {
        "water": 100000.0,    # Launch cost avoidance
        "iron": 20000.0,
        "nickel": 25000.0,
        "copper": 22000.0,
        "cobalt": 25000.0,
        "platinum": 50000.0,
        "palladium": 60000.0,
        "iridium": 70000.0,
        "rare_earths": 30000.0,
    },
    "mars_orbit": {
        "water": 500000.0,
        "iron": 200000.0,
        "nickel": 250000.0,
        "copper": 220000.0,
        "cobalt": 250000.0,
        "platinum": 200000.0,
        "palladium": 250000.0,
        "iridium": 300000.0,
        "rare_earths": 200000.0,
    },
}


@dataclass
class SwarmConfig:
    """Define a swarm composition — all 6 castes."""
    workers: int = 100
    taskmasters: int = 5
    couriers: int = 3
    sorters: int = 2
    plasterers: int = 3
    tenders: int = 2
    track: str = "a"  # a, b, or c

    @property
    def total_ants(self) -> int:
        return (self.workers + self.taskmasters + self.couriers +
                self.sorters + self.plasterers + self.tenders)


# Default mothership modules per track
TRACK_MODULES = {
    "a": ["drill", "power", "comms", "sealing", "cargo", "thermal_sorter",
          "exterior_maintenance"],
    "b": ["drill", "power", "comms", "sealing", "cargo", "thermal_sorter",
          "exterior_maintenance", "bioreactor", "sugar_production"],
    "c": ["drill", "power", "comms", "sealing", "cargo", "thermal_sorter",
          "exterior_maintenance", "bioreactor", "sugar_production"],
}


@dataclass
class MissionConfig:
    """Full mission configuration."""
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    asteroid_id: str = "bennu"
    destination: str = "lunar_orbit"
    launch_vehicle: str = "starship_conservative"
    mothership_modules: list[str] | None = None  # Auto-set from track if None
    mission_cycles: int = 3


@dataclass
class MassBudget:
    """Detailed mass budget breakdown."""
    swarm_mass_kg: float = 0.0
    worker_mass_g: float = 0.0
    taskmaster_mass_g: float = 0.0
    courier_mass_g: float = 0.0
    mothership_dry_mass_kg: float = 0.0
    bioreactor_dry_mass_kg: float = 0.0
    water_mass_kg: float = 0.0
    consumables_mass_kg: float = 0.0
    return_vehicles_mass_kg: float = 0.0
    margin_pct: float = 0.15  # 15% mass margin

    @property
    def total_dry_kg(self) -> float:
        return (self.swarm_mass_kg + self.mothership_dry_mass_kg +
                self.bioreactor_dry_mass_kg + self.return_vehicles_mass_kg +
                self.consumables_mass_kg)

    @property
    def total_wet_kg(self) -> float:
        return self.total_dry_kg + self.water_mass_kg

    @property
    def total_with_margin_kg(self) -> float:
        return self.total_wet_kg * (1 + self.margin_pct)


@dataclass
class CostEstimate:
    """Mission cost breakdown."""
    swarm_hardware_usd: float = 0.0
    mothership_hardware_usd: float = 0.0
    launch_cost_usd: float = 0.0
    consumables_per_cycle_usd: float = 0.0
    total_first_cycle_usd: float = 0.0


@dataclass
class FeasibilityReport:
    """Complete feasibility analysis output."""
    mission: MissionConfig = field(default_factory=MissionConfig)
    mass_budget: MassBudget = field(default_factory=MassBudget)
    cost_estimate: CostEstimate = field(default_factory=CostEstimate)
    power_budget: dict[str, Any] = field(default_factory=dict)
    revenue_per_cycle_usd: float = 0.0
    break_even_cycles: int = 0
    notes: list[str] = field(default_factory=list)


def _get_module_mass(mod: dict[str, Any]) -> float:
    """Extract mass from a mothership module config (handles various key names)."""
    return (mod.get("total_mass_kg")
            or mod.get("total_mass_with_consumables_kg")
            or mod.get("mass_summary", {}).get("total_mass_kg")
            or mod.get("mass_summary", {}).get("total_dry_mass_kg")
            or 0)


def analyze_mission(mission: MissionConfig, catalog: Catalog | None = None) -> FeasibilityReport:
    """Run a complete feasibility analysis for a mission configuration."""
    if catalog is None:
        catalog = Catalog()

    report = FeasibilityReport(mission=mission)

    # Auto-set mothership modules from track if not explicitly provided
    if mission.mothership_modules is None:
        mission.mothership_modules = list(TRACK_MODULES.get(mission.swarm.track,
                                                            TRACK_MODULES["a"]))

    # Load configs
    ant_configs = load_all_ant_configs()
    has_bioreactor = "bioreactor" in mission.mothership_modules
    has_sugar_production = "sugar_production" in mission.mothership_modules

    # --- Mass Budget ---
    mass = report.mass_budget

    # All ant castes with their counts
    caste_counts = {
        "worker": mission.swarm.workers,
        "taskmaster": mission.swarm.taskmasters,
        "courier": mission.swarm.couriers,
        "sorter": mission.swarm.sorters,
        "plasterer": mission.swarm.plasterers,
        "tender": mission.swarm.tenders,
    }

    # Per-caste mass and total swarm mass
    caste_masses: dict[str, float] = {}
    for caste, count in caste_counts.items():
        if caste in ant_configs and count > 0:
            caste_mass_g = compute_ant_mass(ant_configs[caste])
            caste_masses[caste] = caste_mass_g
            mass.swarm_mass_kg += (caste_mass_g * count) / 1000

    # Store primary caste masses for report display
    mass.worker_mass_g = caste_masses.get("worker", 0)
    mass.taskmaster_mass_g = caste_masses.get("taskmaster", 0)
    mass.courier_mass_g = caste_masses.get("courier", 0)

    # Mothership modules (excluding bioreactor which is handled separately)
    modules = load_all_mothership_modules()
    for mod_name in mission.mothership_modules:
        if mod_name == "bioreactor":
            continue  # Handled below with wet mass
        if mod_name in modules:
            mass.mothership_dry_mass_kg += _get_module_mass(modules[mod_name])

    # Bioreactor wet mass (water dominates)
    if has_bioreactor:
        bio_mod = modules.get("bioreactor", {})
        bio_summary = bio_mod.get("mass_summary", {})
        mass.bioreactor_dry_mass_kg = bio_summary.get("total_dry_mass_kg", 110)
        mass.water_mass_kg = bio_summary.get("water_mass_kg", 300)
        report.notes.append(
            "CRITICAL: Bioreactor wet mass includes 300 kg water. "
            "Total bioprocessing: 410 kg (not 110 kg dry)."
        )

    # Consumables — Track B/C with sugar production are nearly self-sustaining
    if has_bioreactor and has_sugar_production:
        # Sugar produced on-site from asteroid CO2 + sunlight — no resupply needed
        # Only consumables: precipitation reagents (~8 kg/yr) + filter replacements
        mass.consumables_mass_kg = 10  # First year reagents only
        report.notes.append(
            "Sugar production on-site (algae photobioreactor). "
            "Bacteria self-replicate. Only precipitation reagents need resupply."
        )
    elif has_bioreactor:
        mass.consumables_mass_kg = 25  # Includes sucrose from Earth
    else:
        mass.consumables_mass_kg = 5  # Track A: minimal (replacement drill bits)

    # Return vehicles (from cargo module config if available)
    cargo_mod = modules.get("cargo", {})
    rv_count = cargo_mod.get("return_vehicle_inventory", {}).get("vehicles_per_mission", 10)
    rv_mass = cargo_mod.get("return_vehicle_inventory", {}).get("vehicle_empty_mass_kg", 6.5)
    mass.return_vehicles_mass_kg = rv_count * rv_mass

    # --- Cost Estimate ---
    cost = report.cost_estimate

    # Swarm hardware — all castes
    for caste, count in caste_counts.items():
        if caste in ant_configs and count > 0:
            cost.swarm_hardware_usd += compute_ant_cost(ant_configs[caste]) * count

    # Mothership hardware (rough: $5k/kg for custom space hardware)
    total_mothership_dry = mass.mothership_dry_mass_kg + mass.bioreactor_dry_mass_kg
    cost.mothership_hardware_usd = total_mothership_dry * 5000

    # Return vehicles
    rv_cost_each = cargo_mod.get("return_vehicle_inventory", {}).get("vehicle_cost_usd", 1500)
    cost.mothership_hardware_usd += rv_count * rv_cost_each

    # Launch cost
    vehicle = LAUNCH_VEHICLES.get(mission.launch_vehicle, LAUNCH_VEHICLES["starship_conservative"])
    dest_multiplier = DESTINATION_MASS_MULTIPLIER.get(mission.destination, 3.0)
    effective_mass = mass.total_with_margin_kg * dest_multiplier
    cost.launch_cost_usd = effective_mass * vehicle["cost_per_kg_usd"]

    # Consumables cost per cycle
    if has_bioreactor and has_sugar_production:
        # Self-sustaining biology — only reagent resupply
        cost.consumables_per_cycle_usd = 500  # Minimal reagent cost
        report.notes.append(
            "Near-zero consumables: bacteria self-replicate, sugar grown on-site, "
            "water recovered at 95%, waste becomes tunnel sealant."
        )
    elif has_bioreactor:
        cost.consumables_per_cycle_usd = 25 * 200  # Sucrose from Earth at $200/kg delivered
    else:
        cost.consumables_per_cycle_usd = 1000  # Track A: drill bit replacement

    cost.total_first_cycle_usd = (
        cost.swarm_hardware_usd +
        cost.mothership_hardware_usd +
        cost.launch_cost_usd +
        cost.consumables_per_cycle_usd
    )

    # --- Power Budget ---
    power = {}
    for caste, cfg in ant_configs.items():
        power[caste] = compute_ant_power(cfg)
    report.power_budget = power

    # --- Revenue Estimate ---
    material_values = MATERIAL_VALUES.get(mission.destination, MATERIAL_VALUES["lunar_orbit"])

    swarm = mission.swarm
    cycle_days = 30

    if swarm.track == "a":
        # Track A: mechanical mining
        # Workers dig 200g/load, ~10 loads/day
        regolith_kg_per_day = swarm.workers * 0.2 * 10 / 1000
        kg_per_cycle = regolith_kg_per_day * cycle_days
        # Mechanical sorting — lower purity, mostly bulk metals
        revenue_per_kg = (material_values.get("nickel", 25000) * 0.05 +
                          material_values.get("iron", 20000) * 0.20)
    elif swarm.track == "b":
        # Track B: bioleaching — worker hauling rate vs bioreactor throughput
        hauling_kg_per_day = swarm.workers * 0.35 * 8 / 1000
        bioreactor_max_kg_per_day = 120  # Crusher throughput limit
        effective_kg_per_day = min(hauling_kg_per_day, bioreactor_max_kg_per_day)
        kg_per_cycle = effective_kg_per_day * cycle_days
        # Higher purity from bioleaching — dissolved metals precipitated as concentrates
        revenue_per_kg = (material_values.get("copper", 22000) * 0.10 +
                          material_values.get("nickel", 25000) * 0.05 +
                          material_values.get("rare_earths", 30000) * 0.01 +
                          material_values.get("cobalt", 25000) * 0.02)
    else:  # Track C — hybrid
        # Mechanical mining speed + bioleaching purity
        hauling_kg_per_day = swarm.workers * 0.2 * 10 / 1000
        bioreactor_max_kg_per_day = 120
        effective_kg_per_day = min(hauling_kg_per_day, bioreactor_max_kg_per_day)
        kg_per_cycle = effective_kg_per_day * cycle_days
        # Best purity: mechanical pre-crushing + biological extraction
        revenue_per_kg = (material_values.get("copper", 22000) * 0.12 +
                          material_values.get("nickel", 25000) * 0.06 +
                          material_values.get("rare_earths", 30000) * 0.015 +
                          material_values.get("cobalt", 25000) * 0.025)

    # Water recovery value (C-type asteroids with thermal sorter)
    if "thermal_sorter" in mission.mothership_modules:
        # ~8.6 L/day water recovered on Bennu = ~258 kg/cycle
        water_kg_per_cycle = 8.6 * cycle_days
        water_value = water_kg_per_cycle * material_values.get("water", 0)
        report.revenue_per_cycle_usd = kg_per_cycle * revenue_per_kg + water_value
        if water_value > 0:
            report.notes.append(
                f"Water recovery: {water_kg_per_cycle:.0f} kg/cycle "
                f"(${water_value:,.0f} at {mission.destination})."
            )
    else:
        report.revenue_per_cycle_usd = kg_per_cycle * revenue_per_kg

    # Break-even
    if report.revenue_per_cycle_usd > cost.consumables_per_cycle_usd:
        net_per_cycle = report.revenue_per_cycle_usd - cost.consumables_per_cycle_usd
        report.break_even_cycles = max(1, int(cost.total_first_cycle_usd / net_per_cycle) + 1)
    else:
        report.break_even_cycles = -1
        report.notes.append("WARNING: Revenue per cycle does not cover consumables. Not viable at this scale.")

    return report


def format_report(report: FeasibilityReport) -> str:
    """Format a feasibility report as human-readable text."""
    lines = []
    m = report.mission
    mb = report.mass_budget
    ce = report.cost_estimate

    lines.append("=" * 70)
    lines.append("ASTRAANT FEASIBILITY REPORT")
    lines.append("=" * 70)

    s = m.swarm
    lines.append(f"\nSwarm: {s.workers}W + {s.taskmasters}T + {s.couriers}C"
                 f" + {s.sorters}So + {s.plasterers}P + {s.tenders}Te"
                 f" = {s.total_ants} ants")
    lines.append(f"Target: {m.asteroid_id} -> {m.destination}")
    lines.append(f"Track: {m.swarm.track.upper()} | Vehicle: {m.launch_vehicle}")
    lines.append(f"Modules: {', '.join(m.mothership_modules or [])}")

    lines.append(f"\n--- MASS BUDGET ---")
    caste_info = [
        ("Worker", mb.worker_mass_g, s.workers),
        ("Taskmaster", mb.taskmaster_mass_g, s.taskmasters),
        ("Courier", mb.courier_mass_g, s.couriers),
    ]
    for name, mass_g, count in caste_info:
        if count > 0:
            lines.append(f"  {name:14s} {mass_g:.0f}g x{count} = "
                         f"{mass_g * count / 1000:.1f} kg")
    # Specialized castes (use swarm total minus primaries)
    specialist_mass = mb.swarm_mass_kg - sum(m * c / 1000 for _, m, c in caste_info)
    specialist_count = s.sorters + s.plasterers + s.tenders
    if specialist_count > 0:
        lines.append(f"  {'Specialists':14s} ({s.sorters}So+{s.plasterers}P+{s.tenders}Te)"
                     f" = {specialist_mass:.1f} kg")
    lines.append(f"  Swarm total:     {mb.swarm_mass_kg:.1f} kg")
    lines.append(f"  Mothership dry:  {mb.mothership_dry_mass_kg:.1f} kg")
    has_bioreactor = "bioreactor" in (m.mothership_modules or [])
    if has_bioreactor:
        lines.append(f"  Bioreactor dry:  {mb.bioreactor_dry_mass_kg:.1f} kg")
        lines.append(f"  Water:           {mb.water_mass_kg:.0f} kg  *** DOMINATES TRACK B/C LAUNCH MASS ***")
    lines.append(f"  Consumables:     {mb.consumables_mass_kg:.0f} kg")
    lines.append(f"  Return vehicles: {mb.return_vehicles_mass_kg:.1f} kg")
    lines.append(f"  -------------------------")
    lines.append(f"  Total dry:       {mb.total_dry_kg:.1f} kg")
    lines.append(f"  Total wet:       {mb.total_wet_kg:.1f} kg")
    lines.append(f"  With 15% margin: {mb.total_with_margin_kg:.1f} kg")

    lines.append(f"\n--- COST ESTIMATE ---")
    lines.append(f"  Swarm hardware:  ${ce.swarm_hardware_usd:,.0f}")
    lines.append(f"  Mothership:      ${ce.mothership_hardware_usd:,.0f}")
    lines.append(f"  Launch cost:     ${ce.launch_cost_usd:,.0f}")
    lines.append(f"  Consumables/cyc: ${ce.consumables_per_cycle_usd:,.0f}")
    lines.append(f"  -------------------------")
    lines.append(f"  TOTAL 1st cycle: ${ce.total_first_cycle_usd:,.0f}")

    lines.append(f"\n--- POWER BUDGET (per ant) ---")
    for caste, pw in report.power_budget.items():
        lines.append(f"  {caste:12s}  idle: {pw['idle_mw']:,.0f} mW  "
                     f"active: {pw['active_mw']:,.0f} mW  peak: {pw['peak_mw']:,.0f} mW")

    lines.append(f"\n--- ECONOMICS ---")
    lines.append(f"  Revenue/cycle:   ${report.revenue_per_cycle_usd:,.0f}")
    if report.break_even_cycles > 0:
        lines.append(f"  Break-even:      {report.break_even_cycles} cycles")
    else:
        lines.append(f"  Break-even:      NEVER (not viable at this scale)")

    if report.notes:
        lines.append(f"\n--- NOTES ---")
        for note in report.notes:
            lines.append(f"  * {note}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
