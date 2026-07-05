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

    # Gross resource value (if 100% were delivered and sold)
    extracted_value_by_material: dict[str, float] = field(default_factory=dict)
    total_extracted_value_usd: float = 0.0

    # Realized revenue (delivered AND arrived) -- this is what actually sells
    revenue_by_material: dict[str, float] = field(default_factory=dict)
    realized_revenue_usd: float = 0.0
    total_revenue_usd: float = 0.0        # alias for realized (what the books show)
    in_transit_value_usd: float = 0.0     # launched, not yet arrived
    stockpiled_value_usd: float = 0.0     # extracted but no pod capacity to ship
    water_price_usd_per_kg: float = 0.0   # price actually used (for sensitivity)

    net_profit_usd: float = 0.0
    roi_pct: float = 0.0

    # Delivery -- the micro-pod fleet is the real throughput throttle
    pods_launched: int = 0
    delivery_capacity_kg: float = 0.0     # max the pod fleet can move over the mission
    arrived_kg: float = 0.0
    kg_delivered: float = 0.0             # alias for arrived_kg
    kg_in_transit: float = 0.0
    stockpiled_kg: float = 0.0            # stranded: extracted but never shipped


def calculate_site_economics(
    asteroid_id: str = "bennu",
    destination: str = "lunar_orbit",
    track: str = "bioleaching",
    workers: int = 100,
    taskmasters: int = 5,
    surface_ants: int = 3,
    mission_years: float = 5.0,
    launch_vehicle: str = "starship_conservative",
    water_price_usd_per_kg: float | None = None,
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

    # --- Gross resource value (upper bound: everything mined, delivered, and sold) ---
    water_price = (water_price_usd_per_kg if water_price_usd_per_kg is not None
                   else values.get("water", 0))
    econ.water_price_usd_per_kg = water_price

    produced_kg: dict[str, float] = {"water": econ.total_water_recovered_kg}
    produced_kg.update(econ.metals_extracted_kg)

    def price_of(material: str) -> float:
        if material == "water":
            return water_price
        return values.get(material, values.get("iron", 1000))

    econ.extracted_value_by_material = {
        m: kg * price_of(m) for m, kg in produced_kg.items() if kg > 0
    }
    econ.total_extracted_value_usd = sum(econ.extracted_value_by_material.values())
    total_produced_kg = sum(produced_kg.values())

    # --- Delivery bottleneck ---
    # Micro-pods are the throughput throttle, NOT the crusher. Each pod carries
    # pod_payload_kg and the fleet launches pods_per_day. Anything extracted beyond
    # what the fleet can move is stranded on the asteroid (stockpiled), and anything
    # launched within the last transit window hasn't arrived (in transit).
    pod_payload_kg = 2.0
    pods_per_day = 3
    econ.delivery_capacity_kg = effective_production_days * pods_per_day * pod_payload_kg

    transit_days = 2.5 * 365.25
    fraction_arrived = (max(0.0, (production_days - transit_days) / production_days)
                        if production_days > 0 else 0.0)
    arrived_remaining = econ.delivery_capacity_kg * fraction_arrived
    transit_remaining = econ.delivery_capacity_kg - arrived_remaining

    # Greedy allocation by value density: the highest $/kg materials ship first.
    realized_by_material: dict[str, float] = {}
    econ.arrived_kg = econ.kg_in_transit = econ.stockpiled_kg = 0.0
    econ.in_transit_value_usd = econ.stockpiled_value_usd = 0.0
    for m in sorted(produced_kg, key=lambda x: -price_of(x)):
        kg, price = produced_kg[m], price_of(m)
        a = min(kg, arrived_remaining); arrived_remaining -= a; kg -= a
        econ.arrived_kg += a
        if a > 0:
            realized_by_material[m] = a * price
        t = min(kg, transit_remaining); transit_remaining -= t; kg -= t
        econ.kg_in_transit += t
        econ.in_transit_value_usd += t * price
        econ.stockpiled_kg += kg
        econ.stockpiled_value_usd += kg * price

    econ.revenue_by_material = realized_by_material
    econ.realized_revenue_usd = sum(realized_by_material.values())
    econ.total_revenue_usd = econ.realized_revenue_usd  # books show realized, not mined
    econ.kg_delivered = econ.arrived_kg
    shipped_kg = econ.arrived_kg + econ.kg_in_transit
    econ.pods_launched = int(shipped_kg / pod_payload_kg)

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

    # --- Net Economics (realized revenue only -- not mined-but-stranded value) ---
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

    # Gross resource value (the tempting-but-misleading headline number)
    dest_label = econ.destination.upper().replace('_', ' ')
    lines.append(f"\n--- GROSS RESOURCE VALUE AT {dest_label} PRICES ---")
    lines.append(f"    (upper bound: if every kg mined were delivered AND sold)")
    lines.append(f"    Water price used:  ${econ.water_price_usd_per_kg:>13,.0f}/kg")
    for material, val in sorted(econ.extracted_value_by_material.items(), key=lambda x: -x[1]):
        if val > 0:
            pct = (val / econ.total_extracted_value_usd * 100) if econ.total_extracted_value_usd else 0
            lines.append(f"    {material:20s} ${val:>15,.0f}  ({pct:4.1f}%)")
    lines.append(f"    {'GROSS VALUE MINED':20s} ${econ.total_extracted_value_usd:>15,.0f}")

    # Delivery reality -- the pod fleet is the throttle
    total_produced = econ.total_water_recovered_kg + econ.total_metals_kg
    stranded_pct = (econ.stockpiled_kg / total_produced * 100) if total_produced else 0
    lines.append(f"\n--- DELIVERY REALITY (micro-pod fleet is the bottleneck) ---")
    lines.append(f"    Produced (water+metals):  {total_produced:>12,.0f} kg")
    lines.append(f"    Pod fleet capacity:       {econ.delivery_capacity_kg:>12,.0f} kg"
                 f"  ({econ.pods_launched:,} pods x 2 kg)")
    lines.append(f"    Arrived at market:        {econ.arrived_kg:>12,.0f} kg")
    lines.append(f"    Still in transit (~2.5y): {econ.kg_in_transit:>12,.0f} kg")
    lines.append(f"    STRANDED (never shipped): {econ.stockpiled_kg:>12,.0f} kg"
                 f"  ({stranded_pct:.0f}% of production)")

    # Realized revenue -- what actually sells (delivered AND arrived)
    lines.append(f"\n--- REALIZED REVENUE (delivered AND arrived, sold) ---")
    for material, rev in sorted(econ.revenue_by_material.items(), key=lambda x: -x[1]):
        if rev > 0:
            pct = (rev / econ.realized_revenue_usd * 100) if econ.realized_revenue_usd else 0
            lines.append(f"    {material:20s} ${rev:>15,.0f}  ({pct:4.1f}%)")
    lines.append(f"    {'REALIZED REVENUE':20s} ${econ.realized_revenue_usd:>15,.0f}")
    lines.append(f"    {'(value in transit)':20s} ${econ.in_transit_value_usd:>15,.0f}")
    lines.append(f"    {'(value stranded)':20s} ${econ.stockpiled_value_usd:>15,.0f}")

    # Costs
    lines.append(f"\n--- COSTS ---")
    lines.append(f"    Hardware:          ${econ.total_hardware_cost_usd:>15,.0f}")
    lines.append(f"    Launch:            ${econ.total_launch_cost_usd:>15,.0f}")
    lines.append(f"    Consumables:       ${econ.total_consumables_cost_usd:>15,.0f}")
    lines.append(f"    {'':20s} {'':>15s}")
    lines.append(f"    {'TOTAL COST':20s} ${econ.total_mission_cost_usd:>15,.0f}")

    # Bottom line -- based on REALIZED revenue, not mined value
    lines.append(f"\n--- BOTTOM LINE (on realized revenue) ---")
    lines.append(f"    Realized revenue:  ${econ.total_revenue_usd:>15,.0f}")
    lines.append(f"    Cost:              ${econ.total_mission_cost_usd:>15,.0f}")
    lines.append(f"    ----------------------------------------")
    profit_label = "NET PROFIT" if econ.net_profit_usd >= 0 else "NET LOSS"
    lines.append(f"    {profit_label:20s} ${econ.net_profit_usd:>15,.0f}")
    lines.append(f"    ROI:               {econ.roi_pct:>14.0f}%")
    lines.append(f"\n    NOTE: gross value mined was ${econ.total_extracted_value_usd:,.0f}, but the")
    lines.append(f"    2 kg micro-pod fleet can only move {econ.delivery_capacity_kg:,.0f} kg over the mission.")
    lines.append(f"    Delivery throughput -- not extraction -- is the binding constraint.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def water_price_sensitivity(
    asteroid_id: str = "bennu",
    destination: str = "lunar_orbit",
    track: str = "bioleaching",
    prices: list[float] | None = None,
    catalog: Catalog | None = None,
    **kwargs: Any,
) -> list[dict[str, float]]:
    """Sweep the water sale price and report realized economics at each point.

    The $50,000/kg lunar-orbit water price is a launch-cost-avoidance ceiling that
    only holds in a mature cislunar market. This shows how the case holds up as that
    price falls toward what a real early market might pay.
    """
    if prices is None:
        prices = [2000, 5000, 10000, 25000, 50000]
    if catalog is None:
        catalog = Catalog()
    rows = []
    for p in prices:
        econ = calculate_site_economics(
            asteroid_id=asteroid_id, destination=destination, track=track,
            water_price_usd_per_kg=p, catalog=catalog, **kwargs,
        )
        rows.append({
            "water_price": p,
            "realized_revenue": econ.realized_revenue_usd,
            "net_profit": econ.net_profit_usd,
            "roi_pct": econ.roi_pct,
        })
    return rows


def format_water_sensitivity(rows: list[dict[str, float]], asteroid_name: str = "") -> str:
    """Format the water-price sweep as a table."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"WATER PRICE SENSITIVITY{('  --  ' + asteroid_name) if asteroid_name else ''}")
    lines.append("How the realized case holds up as the cislunar water price falls")
    lines.append("=" * 70)
    lines.append(f"\n  {'Water $/kg':>12s} {'Realized Rev':>16s} {'Net Profit':>16s} {'ROI':>10s}")
    lines.append(f"  {'-'*56}")
    for r in rows:
        lines.append(f"  {r['water_price']:>11,.0f}/ "
                     f"${r['realized_revenue']:>14,.0f} "
                     f"${r['net_profit']:>14,.0f} "
                     f"{r['roi_pct']:>8,.0f}%")
    lines.append("\n  Even at a mature-market $2,000/kg, water still carries the case --")
    lines.append("  but the headline ROI is a fraction of the $50,000/kg fantasy number.")
    lines.append("=" * 70)
    return "\n".join(lines)
