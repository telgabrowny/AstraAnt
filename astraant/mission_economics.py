"""Full mission economics model for a single mothership site.

Calculates expected material output, revenue, and net economics over the
mission lifetime for a specific asteroid target. Uses real composition
data from the catalog and extraction efficiencies from species profiles.

This is the "billionaire pitch" module -- the numbers that answer:
"If I fund one site, what do I get back?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml
from pathlib import Path

from .catalog import Catalog


# Material values at different destinations ($/kg)
# Conservative estimates for serious feasibility study
MATERIAL_VALUES = {
    "lunar_orbit": {
        "water": 50000,        # Launch cost avoidance (Starship era)
        "iron": 2000,          # Structural use in cislunar construction
        "nickel": 5000,        # High-value structural alloy component
        "copper": 8000,        # Wiring, thermal management
        "cobalt": 12000,       # Battery cathodes, superalloys
        "platinum": 35000,     # Catalysts + inherent value
        "palladium": 45000,    # Catalysts
        "iridium": 55000,      # Extreme corrosion resistance
        "rare_earths": 25000,  # Electronics, magnets
    },
    "mars_orbit": {
        "water": 200000,       # Even more valuable at Mars
        "iron": 50000,
        "nickel": 80000,
        "copper": 70000,
        "cobalt": 100000,
        "platinum": 100000,
        "palladium": 120000,
        "iridium": 150000,
        "rare_earths": 80000,
    },
}

# Bioreactor extraction efficiencies (from species catalog)
EXTRACTION_EFFICIENCIES = {
    # Vat 1: Sulfide metals
    "iron": 0.85,      # A. ferrooxidans is very effective on iron
    "nickel": 0.85,    # Good extraction from pentlandite
    "copper": 0.85,    # Well-studied on chalcopyrite
    "cobalt": 0.80,    # Slightly lower
    # Vat 2: REE
    "rare_earths": 0.60,  # A. niger, lower efficiency
    # Vat 3: PGM
    "platinum": 0.40,   # C. violaceum, immature technology
    "palladium": 0.40,
    "iridium": 0.30,    # Hardest to extract biologically
}


@dataclass
class MissionEconomics:
    """Complete economic breakdown for a single site over its lifetime."""
    asteroid_name: str = ""
    destination: str = "lunar_orbit"
    track: str = "bioleaching"

    # Mission parameters
    mission_lifetime_years: float = 5.0
    startup_months: float = 3.0        # Drilling, sealing, pressurizing before production

    # Production rates
    crusher_throughput_kg_per_day: float = 120.0  # From bioreactor config
    water_recovery_kg_per_day: float = 8.6        # From thermal sorter on Bennu
    operational_uptime: float = 0.85               # 85% uptime (maintenance, failures)

    # Costs
    total_launch_cost_usd: float = 0.0
    total_hardware_cost_usd: float = 0.0
    total_consumables_cost_usd: float = 0.0
    total_mission_cost_usd: float = 0.0

    # Production totals
    total_regolith_processed_kg: float = 0.0
    total_water_recovered_kg: float = 0.0
    metals_extracted_kg: dict[str, float] = field(default_factory=dict)
    total_metals_kg: float = 0.0

    # Revenue
    revenue_by_material: dict[str, float] = field(default_factory=dict)
    total_revenue_usd: float = 0.0
    net_profit_usd: float = 0.0
    roi_pct: float = 0.0

    # Delivery
    pods_launched: int = 0
    kg_delivered: float = 0.0
    kg_in_transit: float = 0.0


def calculate_site_economics(
    asteroid_id: str = "bennu",
    destination: str = "lunar_orbit",
    track: str = "bioleaching",
    workers: int = 100,
    taskmasters: int = 5,
    surface_ants: int = 3,
    mission_years: float = 5.0,
    launch_vehicle: str = "starship_conservative",
    catalog: Catalog | None = None,
) -> MissionEconomics:
    """Calculate full economics for a single mothership site."""

    if catalog is None:
        catalog = Catalog()

    econ = MissionEconomics(
        destination=destination,
        track=track,
        mission_lifetime_years=mission_years,
    )

    # Get asteroid data
    asteroid = catalog.get_asteroid(asteroid_id)
    if asteroid is None:
        econ.asteroid_name = asteroid_id
        return econ
    econ.asteroid_name = asteroid.get("name", asteroid_id)

    composition = asteroid.get("composition", {})
    metals_ppm = composition.get("metals_ppm", {})
    bulk = composition.get("bulk", {})
    water_pct = bulk.get("water_hydrated", 0) / 100.0

    # Material values for this destination
    values = MATERIAL_VALUES.get(destination, MATERIAL_VALUES["lunar_orbit"])

    # --- Production Timeline ---
    startup_days = econ.startup_months * 30
    production_days = (mission_years * 365.25) - startup_days
    effective_production_days = production_days * econ.operational_uptime

    # --- Regolith Processing ---
    econ.total_regolith_processed_kg = (
        econ.crusher_throughput_kg_per_day * effective_production_days
    )

    # --- Water Recovery ---
    # Water is in hydrated minerals — released by thermal sorting
    econ.water_recovery_kg_per_day = (
        econ.crusher_throughput_kg_per_day * water_pct * 0.90  # 90% recovery
    )
    econ.total_water_recovered_kg = (
        econ.water_recovery_kg_per_day * effective_production_days
    )

    # --- Metal Extraction ---
    for metal, ppm in metals_ppm.items():
        if metal == "iron" and track == "mechanical":
            # Mechanical track: mechanical separation, lower purity
            efficiency = 0.30  # Much lower than bioleaching
        else:
            efficiency = EXTRACTION_EFFICIENCIES.get(metal, 0.50)

        if track == "mechanical":
            efficiency *= 0.5  # Mechanical track has lower overall extraction

        metal_fraction = ppm / 1_000_000  # ppm to fraction
        extracted_kg = (
            econ.total_regolith_processed_kg * metal_fraction * efficiency
        )
        if extracted_kg > 0.001:
            econ.metals_extracted_kg[metal] = round(extracted_kg, 3)

    econ.total_metals_kg = sum(econ.metals_extracted_kg.values())

    # --- Revenue ---
    # Water revenue
    econ.revenue_by_material["water"] = econ.total_water_recovered_kg * values.get("water", 0)

    # Metal revenue
    for metal, kg in econ.metals_extracted_kg.items():
        price = values.get(metal, values.get("iron", 1000))
        econ.revenue_by_material[metal] = kg * price

    econ.total_revenue_usd = sum(econ.revenue_by_material.values())

    # --- Costs ---
    # Get mission cost from feasibility calculator
    from .feasibility import MissionConfig, SwarmConfig, analyze_mission
    mission = MissionConfig(
        swarm=SwarmConfig(workers=workers, taskmasters=taskmasters,
                          surface_ants=surface_ants, track=track),
        asteroid_id=asteroid_id,
        destination=destination,
        launch_vehicle=launch_vehicle,
    )
    report = analyze_mission(mission, catalog)

    econ.total_launch_cost_usd = report.cost_estimate.launch_cost_usd
    econ.total_hardware_cost_usd = (
        report.cost_estimate.swarm_hardware_usd +
        report.cost_estimate.mothership_hardware_usd
    )
    # Consumables over mission lifetime
    cycles = int(production_days / 30)  # 30-day processing cycles
    econ.total_consumables_cost_usd = (
        report.cost_estimate.consumables_per_cycle_usd * cycles
    )
    econ.total_mission_cost_usd = (
        econ.total_launch_cost_usd +
        econ.total_hardware_cost_usd +
        econ.total_consumables_cost_usd
    )

    # --- Delivery ---
    # Micro-pods: 2 kg each, 3 per day
    pods_per_day = 3
    econ.pods_launched = int(effective_production_days * pods_per_day)
    econ.kg_delivered = min(
        econ.pods_launched * 2,  # 2 kg per pod
        econ.total_metals_kg + econ.total_water_recovered_kg  # Can't deliver more than produced
    )
    # Material in transit (launched but not yet arrived — ~2.5 year transit)
    transit_days = 2.5 * 365.25
    if production_days > transit_days:
        econ.kg_in_transit = min(transit_days * pods_per_day * 2,
                                 econ.kg_delivered * 0.5)

    # --- Net Economics ---
    econ.net_profit_usd = econ.total_revenue_usd - econ.total_mission_cost_usd
    if econ.total_mission_cost_usd > 0:
        econ.roi_pct = (econ.net_profit_usd / econ.total_mission_cost_usd) * 100

    return econ


def format_economics_report(econ: MissionEconomics) -> str:
    """Format the full economics report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SINGLE SITE MISSION ECONOMICS")
    lines.append(f"Asteroid: {econ.asteroid_name}")
    lines.append(f"Destination: {econ.destination}  |  Track: {econ.track.upper()}")
    lines.append(f"Mission lifetime: {econ.mission_lifetime_years:.0f} years"
                 f" ({econ.startup_months:.0f} months startup + production)")
    lines.append("=" * 70)

    # Production
    lines.append(f"\n--- PRODUCTION OVER {econ.mission_lifetime_years:.0f} YEARS ---")
    lines.append(f"  Regolith processed:  {econ.total_regolith_processed_kg:,.0f} kg"
                 f" ({econ.total_regolith_processed_kg/1000:,.0f} tonnes)")
    lines.append(f"  Water recovered:     {econ.total_water_recovered_kg:,.0f} kg"
                 f" ({econ.total_water_recovered_kg/1000:,.1f} tonnes)")

    lines.append(f"\n  Metals extracted:")
    sorted_metals = sorted(econ.metals_extracted_kg.items(), key=lambda x: -x[1])
    for metal, kg in sorted_metals:
        if kg >= 0.001:
            lines.append(f"    {metal:20s} {kg:10.1f} kg")
    lines.append(f"    {'TOTAL METALS':20s} {econ.total_metals_kg:10.1f} kg")

    # Revenue
    lines.append(f"\n--- REVENUE AT {econ.destination.upper().replace('_', ' ')} PRICES ---")
    sorted_rev = sorted(econ.revenue_by_material.items(), key=lambda x: -x[1])
    for material, rev in sorted_rev:
        if rev > 0:
            pct = (rev / econ.total_revenue_usd * 100) if econ.total_revenue_usd > 0 else 0
            lines.append(f"    {material:20s} ${rev:>15,.0f}  ({pct:4.1f}%)")
    lines.append(f"    {'':20s} {'':>15s}")
    lines.append(f"    {'TOTAL REVENUE':20s} ${econ.total_revenue_usd:>15,.0f}")

    # Costs
    lines.append(f"\n--- COSTS ---")
    lines.append(f"    Hardware:          ${econ.total_hardware_cost_usd:>15,.0f}")
    lines.append(f"    Launch:            ${econ.total_launch_cost_usd:>15,.0f}")
    lines.append(f"    Consumables:       ${econ.total_consumables_cost_usd:>15,.0f}")
    lines.append(f"    {'':20s} {'':>15s}")
    lines.append(f"    {'TOTAL COST':20s} ${econ.total_mission_cost_usd:>15,.0f}")

    # Bottom line
    lines.append(f"\n--- BOTTOM LINE ---")
    lines.append(f"    Revenue:           ${econ.total_revenue_usd:>15,.0f}")
    lines.append(f"    Cost:              ${econ.total_mission_cost_usd:>15,.0f}")
    lines.append(f"    ----------------------------------------")
    profit_label = "NET PROFIT" if econ.net_profit_usd >= 0 else "NET LOSS"
    lines.append(f"    {profit_label:20s} ${econ.net_profit_usd:>15,.0f}")
    lines.append(f"    ROI:               {econ.roi_pct:>14.0f}%")

    # Delivery
    lines.append(f"\n--- DELIVERY ---")
    lines.append(f"    Micro-pods launched:  {econ.pods_launched:,}")
    lines.append(f"    Material shipped:     {econ.kg_delivered:,.0f} kg")
    lines.append(f"    Estimated in-transit: {econ.kg_in_transit:,.0f} kg"
                 f" (~2.5 year transit time)")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
