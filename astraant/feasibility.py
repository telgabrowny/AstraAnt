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
    """Define a swarm composition."""
    workers: int = 100
    taskmasters: int = 5
    couriers: int = 3
    track: str = "a"  # a, b, or c


@dataclass
class MissionConfig:
    """Full mission configuration."""
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    asteroid_id: str = "bennu"
    destination: str = "lunar_orbit"
    launch_vehicle: str = "starship_conservative"
    mothership_modules: list[str] = field(
        default_factory=lambda: ["drill", "power", "comms", "sealing", "cargo"]
    )
    include_bioreactor: bool = False  # Auto-set for Track B/C
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


def analyze_mission(mission: MissionConfig, catalog: Catalog | None = None) -> FeasibilityReport:
    """Run a complete feasibility analysis for a mission configuration."""
    if catalog is None:
        catalog = Catalog()

    report = FeasibilityReport(mission=mission)

    # Load configs
    ant_configs = load_all_ant_configs()

    # Auto-enable bioreactor for Track B/C
    if mission.swarm.track in ("b", "c"):
        mission.include_bioreactor = True

    # --- Mass Budget ---
    mass = report.mass_budget

    # Worker mass
    if "worker" in ant_configs:
        worker_cfg = ant_configs["worker"]
        mass.worker_mass_g = compute_ant_mass(worker_cfg)
        mass.swarm_mass_kg += (mass.worker_mass_g * mission.swarm.workers) / 1000

    # Taskmaster mass
    if "taskmaster" in ant_configs:
        tm_cfg = ant_configs["taskmaster"]
        mass.taskmaster_mass_g = compute_ant_mass(tm_cfg)
        mass.swarm_mass_kg += (mass.taskmaster_mass_g * mission.swarm.taskmasters) / 1000

    # Courier mass
    if "courier" in ant_configs:
        courier_cfg = ant_configs["courier"]
        mass.courier_mass_g = compute_ant_mass(courier_cfg)
        mass.swarm_mass_kg += (mass.courier_mass_g * mission.swarm.couriers) / 1000

    # Mothership modules
    modules = load_all_mothership_modules()
    for mod_name in mission.mothership_modules:
        if mod_name in modules:
            mod = modules[mod_name]
            # Try multiple keys for mass — configs use different names
            mod_mass = (mod.get("total_mass_kg")
                        or mod.get("total_mass_with_consumables_kg")
                        or mod.get("mass_summary", {}).get("total_dry_mass_kg")
                        or 0)
            mass.mothership_dry_mass_kg += mod_mass

    # Bioreactor (read from module config if available, otherwise use defaults)
    if mission.include_bioreactor:
        bio_mod = modules.get("bioreactor", {})
        bio_summary = bio_mod.get("mass_summary", {})
        mass.bioreactor_dry_mass_kg = bio_summary.get("total_dry_mass_kg", 110)
        mass.water_mass_kg = bio_summary.get("water_mass_kg", 300)
        mass.consumables_mass_kg = 25  # Per year
        report.notes.append(
            "CRITICAL: Bioreactor wet mass includes 300 kg water. "
            "Total bioprocessing: 410 kg (not 110 kg dry)."
        )

    # Return vehicles (5 per cycle, ~6.5 kg each empty)
    mass.return_vehicles_mass_kg = 5 * 6.5

    # --- Cost Estimate ---
    cost = report.cost_estimate

    # Swarm hardware
    if "worker" in ant_configs:
        cost.swarm_hardware_usd += compute_ant_cost(ant_configs["worker"]) * mission.swarm.workers
    if "taskmaster" in ant_configs:
        cost.swarm_hardware_usd += compute_ant_cost(ant_configs["taskmaster"]) * mission.swarm.taskmasters
    if "courier" in ant_configs:
        cost.swarm_hardware_usd += compute_ant_cost(ant_configs["courier"]) * mission.swarm.couriers

    # Mothership hardware (rough estimate --detailed costing comes later)
    cost.mothership_hardware_usd = mass.mothership_dry_mass_kg * 5000  # $5k/kg estimate

    # Launch cost
    vehicle = LAUNCH_VEHICLES.get(mission.launch_vehicle, LAUNCH_VEHICLES["starship_conservative"])
    dest_multiplier = DESTINATION_MASS_MULTIPLIER.get(mission.destination, 3.0)
    effective_mass = mass.total_with_margin_kg * dest_multiplier
    cost.launch_cost_usd = effective_mass * vehicle["cost_per_kg_usd"]

    # Consumables per cycle
    if mission.include_bioreactor:
        cost.consumables_per_cycle_usd = 25 * 200  # 25 kg x$200/kg launch to destination
    else:
        cost.consumables_per_cycle_usd = 1000  # Minimal for Track A

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

    # --- Revenue Estimate (very rough) ---
    # This will be refined significantly in later phases
    material_values = MATERIAL_VALUES.get(mission.destination, MATERIAL_VALUES["lunar_orbit"])

    # Rough extraction rate: workers xcapacity xcycles per day xdays per cycle
    swarm = mission.swarm
    if swarm.track == "a":
        # Track A: mechanical --200g/load, ~10 loads/day per worker
        kg_per_cycle = swarm.workers * 0.2 * 10 * 30 / 1000  # 30-day cycle
        # Assume mix of metals (mostly iron/nickel with traces of valuable metals)
        revenue_per_kg = material_values.get("nickel", 25000) * 0.05  # 5% nickel by mass
        revenue_per_kg += material_values.get("iron", 20000) * 0.20  # 20% iron
    elif swarm.track == "b":
        # Track B: bioleaching --350g/load, ~8 loads/day, but bioreactor is the bottleneck
        # Bioreactor throughput: ~5 kg/hr crusher x24 hr = 120 kg/day
        kg_per_cycle = min(
            swarm.workers * 0.35 * 8 * 30 / 1000,
            120 * 30  # Bioreactor max
        )
        # Higher purity output from bioleaching
        revenue_per_kg = material_values.get("copper", 22000) * 0.10
        revenue_per_kg += material_values.get("nickel", 25000) * 0.05
        revenue_per_kg += material_values.get("rare_earths", 30000) * 0.01
    else:  # Track C
        # Track C: hybrid --mechanical throughput, bioleaching purity
        kg_per_cycle = min(
            swarm.workers * 0.2 * 10 * 30 / 1000,
            120 * 30
        )
        revenue_per_kg = material_values.get("copper", 22000) * 0.12
        revenue_per_kg += material_values.get("nickel", 25000) * 0.06
        revenue_per_kg += material_values.get("rare_earths", 30000) * 0.015

    report.revenue_per_cycle_usd = kg_per_cycle * revenue_per_kg

    # Break-even
    if report.revenue_per_cycle_usd > cost.consumables_per_cycle_usd:
        net_per_cycle = report.revenue_per_cycle_usd - cost.consumables_per_cycle_usd
        report.break_even_cycles = max(1, int(cost.total_first_cycle_usd / net_per_cycle) + 1)
    else:
        report.break_even_cycles = -1  # Never breaks even
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

    lines.append(f"\nMission: {m.swarm.workers}W + {m.swarm.taskmasters}T + {m.swarm.couriers}C"
                 f" ->{m.asteroid_id} ->{m.destination}")
    lines.append(f"Track: {m.swarm.track.upper()} | Vehicle: {m.launch_vehicle}")

    lines.append(f"\n--- MASS BUDGET ---")
    lines.append(f"  Worker ant:      {mb.worker_mass_g:.0f} g x{m.swarm.workers} = "
                 f"{mb.worker_mass_g * m.swarm.workers / 1000:.1f} kg")
    lines.append(f"  Taskmaster ant:  {mb.taskmaster_mass_g:.0f} g x{m.swarm.taskmasters} = "
                 f"{mb.taskmaster_mass_g * m.swarm.taskmasters / 1000:.1f} kg")
    lines.append(f"  Courier ant:     {mb.courier_mass_g:.0f} g x{m.swarm.couriers} = "
                 f"{mb.courier_mass_g * m.swarm.couriers / 1000:.1f} kg")
    lines.append(f"  Swarm total:     {mb.swarm_mass_kg:.1f} kg")
    lines.append(f"  Mothership dry:  {mb.mothership_dry_mass_kg:.1f} kg")
    if m.include_bioreactor:
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
