"""Phase 2 missions — what to build inside the excavated chamber.

After the ant colony excavates a pressurized chamber, follow-up missions
can install facilities using standard (non-space-rated) equipment.
Each facility has costs, mass, power requirements, and revenue/value generation.

This is the "what comes next" module — the endgame content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Facility:
    """A facility that can be installed inside the chamber."""
    id: str
    name: str
    category: str                    # "habitat", "industrial", "fuel", "comms", "science"
    description: str

    # Costs
    equipment_mass_kg: float         # Shipped from Earth
    equipment_cost_usd: float        # Hardware cost
    launch_cost_per_kg_usd: float = 500  # Starship-era to asteroid
    installation_time_days: float = 30
    requires_chamber_m3: float = 50  # Volume needed inside chamber

    # Operations
    power_draw_w: float = 0
    crew_required: int = 0           # 0 = fully autonomous
    annual_operating_cost_usd: float = 0

    # Revenue / value generation
    annual_revenue_usd: float = 0
    revenue_source: str = ""
    strategic_value: str = ""        # Non-monetary value

    # Dependencies
    requires: list[str] = field(default_factory=list)  # Other facility IDs needed first


# === FACILITY CATALOG ===

FACILITIES = [
    # --- FUEL DEPOT ---
    Facility(
        id="fuel_depot",
        name="Water Electrolysis Fuel Depot",
        category="fuel",
        description=(
            "Electrolyzes asteroid water into LH2+LOX propellant. "
            "Ships passing through refuel here instead of carrying "
            "propellant from Earth. The asteroid becomes a gas station."
        ),
        equipment_mass_kg=500,
        equipment_cost_usd=2_000_000,
        requires_chamber_m3=100,
        power_draw_w=2000,
        installation_time_days=60,
        annual_revenue_usd=50_000_000,
        revenue_source=(
            "Sell propellant at $20K/kg to passing spacecraft. "
            "Water from asteroid ice costs near-zero. "
            "Electrolysis is the only cost (power from solar array). "
            "At 2500 kg propellant/year sold: $50M/year."
        ),
        strategic_value="Enables deep space missions that couldn't carry enough fuel from Earth.",
    ),

    # --- MANUFACTURING ---
    Facility(
        id="manufacturing_full",
        name="Full Manufacturing Plant",
        category="industrial",
        description=(
            "Industrial-scale manufacturing using asteroid metals. "
            "CNC mill, large 3D printers (metal + polymer), welding station, "
            "wire drawing, sheet metal forming. All standard Earth equipment — "
            "works fine in the pressurized chamber."
        ),
        equipment_mass_kg=2000,
        equipment_cost_usd=5_000_000,
        requires_chamber_m3=200,
        power_draw_w=5000,
        installation_time_days=90,
        annual_revenue_usd=20_000_000,
        revenue_source=(
            "Build spacecraft components, structural beams, pressure vessels, "
            "and tools from asteroid iron/nickel. Sell to other missions at "
            "1/10th the cost of launching from Earth."
        ),
        strategic_value="Self-expanding infrastructure. Can build anything from local materials.",
    ),

    # --- HABITAT ---
    Facility(
        id="habitat_module",
        name="Crew Habitat Module",
        category="habitat",
        description=(
            "Pressurized living space for 4-6 crew. Life support, sleeping "
            "quarters, galley, exercise area. Standard ISS-heritage hardware. "
            "The chamber provides radiation shielding and thermal stability — "
            "the habitat module just needs to be a comfortable pressure vessel."
        ),
        equipment_mass_kg=5000,
        equipment_cost_usd=20_000_000,
        requires_chamber_m3=150,
        power_draw_w=3000,
        crew_required=0,             # Autonomous until crew arrives
        installation_time_days=120,
        annual_operating_cost_usd=2_000_000,
        annual_revenue_usd=0,        # No direct revenue — enables everything else
        strategic_value=(
            "Enables human presence for oversight, repairs, and decision-making. "
            "30m of rock = better radiation protection than ISS. "
            "Stable temperature = less life support power. "
            "Gravity: zero (or small centrifuge for crew comfort)."
        ),
        requires=["fuel_depot"],     # Need fuel depot for crew transit
    ),

    # --- CENTRIFUGE ---
    Facility(
        id="centrifuge_ring",
        name="Artificial Gravity Centrifuge Ring",
        category="habitat",
        description=(
            "5m radius rotating ring inside the chamber for artificial gravity. "
            "At 4 RPM provides 0.09g — enough for comfortable sleeping, eating, "
            "and fluid handling. Crew sleeps in the ring, works in zero-g. "
            "Bearings mounted to chamber walls (solid rock anchoring)."
        ),
        equipment_mass_kg=3000,
        equipment_cost_usd=15_000_000,
        requires_chamber_m3=300,     # Needs room to spin
        power_draw_w=500,            # Just bearing friction + air circulation
        installation_time_days=90,
        strategic_value="Crew health for long-duration stays. Reduces bone/muscle loss.",
        requires=["habitat_module"],
    ),

    # --- COMMS RELAY ---
    Facility(
        id="comms_relay",
        name="Deep Space Communication Relay",
        category="comms",
        description=(
            "High-power communication station using the chamber as a "
            "thermally stable, vibration-free platform. Large dish antenna "
            "on the asteroid surface, electronics protected underground. "
            "Relays data for other deep space missions."
        ),
        equipment_mass_kg=200,
        equipment_cost_usd=3_000_000,
        requires_chamber_m3=20,
        power_draw_w=500,
        installation_time_days=30,
        annual_revenue_usd=5_000_000,
        revenue_source="Charge other missions for relay bandwidth. $5M/year.",
        strategic_value="Deep space internet node. Enables the cislunar communication network.",
    ),

    # --- SERVER FARM ---
    Facility(
        id="server_farm",
        name="Deep Space Computing Node",
        category="comms",
        description=(
            "Rack-mounted servers in a radiation-shielded, thermally stable environment. "
            "Computers don't care about microgravity. Low cooling costs (radiate to rock). "
            "Process data for deep space missions, AI inference, scientific computing."
        ),
        equipment_mass_kg=500,
        equipment_cost_usd=2_000_000,
        requires_chamber_m3=30,
        power_draw_w=3000,
        installation_time_days=30,
        annual_revenue_usd=10_000_000,
        revenue_source="Cloud computing in space. Sell compute cycles to other missions.",
        requires=["comms_relay"],
    ),

    # --- BIOREACTOR FARM ---
    Facility(
        id="bioreactor_farm",
        name="Industrial Bioreactor Farm",
        category="industrial",
        description=(
            "Scale up bioleaching from mothership-sized vats to industrial tanks. "
            "10x the extraction capacity. Also expand algae production for "
            "food (spirulina) and oxygen generation. The chamber's stable "
            "temperature and pressure make this much easier than mothership ops."
        ),
        equipment_mass_kg=1000,
        equipment_cost_usd=3_000_000,
        requires_chamber_m3=200,
        power_draw_w=2000,
        installation_time_days=60,
        annual_revenue_usd=100_000_000,
        revenue_source=(
            "10x metal extraction rate. At Bennu water/metal prices: "
            "$100M/year from expanded processing capacity."
        ),
        strategic_value="Becomes a food source if crew is present (spirulina, fresh water).",
    ),

    # --- SHIPYARD ---
    Facility(
        id="shipyard",
        name="Spacecraft Assembly Bay",
        category="industrial",
        description=(
            "Build entire spacecraft from asteroid materials inside the chamber. "
            "The chamber is a naturally pressurized clean room. Assemble "
            "structural frames, pressure vessels, propellant tanks from local "
            "iron/nickel. Only electronics shipped from Earth. "
            "Launch through tunnel to surface."
        ),
        equipment_mass_kg=3000,
        equipment_cost_usd=10_000_000,
        requires_chamber_m3=500,
        power_draw_w=5000,
        installation_time_days=180,
        annual_revenue_usd=200_000_000,
        revenue_source=(
            "Build and sell spacecraft at 1/100th Earth launch cost. "
            "A ship built from asteroid materials and launched from "
            "an asteroid surface costs almost nothing vs Earth launch."
        ),
        strategic_value="The ultimate self-replication: the factory that builds spacecraft.",
        requires=["manufacturing_full", "fuel_depot"],
    ),
]


@dataclass
class Phase2Plan:
    """A plan for Phase 2 facilities."""
    selected_facilities: list[Facility]
    total_equipment_mass_kg: float = 0
    total_equipment_cost_usd: float = 0
    total_launch_cost_usd: float = 0
    total_cost_usd: float = 0
    total_annual_revenue_usd: float = 0
    total_annual_operating_cost_usd: float = 0
    total_power_draw_w: float = 0
    total_volume_needed_m3: float = 0
    installation_timeline_days: float = 0
    break_even_years: float = 0
    notes: list[str] = field(default_factory=list)


def plan_phase2(facility_ids: list[str] | None = None,
                chamber_volume_m3: float = 2572,
                available_power_w: float = 10000) -> Phase2Plan:
    """Plan a Phase 2 installation given selected facilities.

    Args:
        facility_ids: List of facility IDs to install. None = recommend best combo.
        chamber_volume_m3: Available chamber volume (from mining phase).
        available_power_w: Power budget from solar arrays.
    """
    if facility_ids is None:
        # Recommend: fuel depot + bioreactor farm + comms relay (best ROI)
        facility_ids = ["fuel_depot", "bioreactor_farm", "comms_relay"]

    fac_map = {f.id: f for f in FACILITIES}
    selected = []
    for fid in facility_ids:
        if fid in fac_map:
            selected.append(fac_map[fid])

    plan = Phase2Plan(selected_facilities=selected)

    # Check dependencies
    installed_ids = set()
    for fac in selected:
        for req in fac.requires:
            if req not in facility_ids:
                plan.notes.append(f"WARNING: {fac.name} requires {req} which is not selected")
        installed_ids.add(fac.id)

    # Totals
    for fac in selected:
        plan.total_equipment_mass_kg += fac.equipment_mass_kg
        plan.total_equipment_cost_usd += fac.equipment_cost_usd
        plan.total_annual_revenue_usd += fac.annual_revenue_usd
        plan.total_annual_operating_cost_usd += fac.annual_operating_cost_usd
        plan.total_power_draw_w += fac.power_draw_w
        plan.total_volume_needed_m3 += fac.requires_chamber_m3
        plan.installation_timeline_days = max(plan.installation_timeline_days,
                                               fac.installation_time_days)

    plan.total_launch_cost_usd = plan.total_equipment_mass_kg * 500  # $500/kg Starship
    plan.total_cost_usd = plan.total_equipment_cost_usd + plan.total_launch_cost_usd

    # Volume check
    if plan.total_volume_needed_m3 > chamber_volume_m3:
        plan.notes.append(
            f"WARNING: Need {plan.total_volume_needed_m3:.0f} m3 but chamber is only "
            f"{chamber_volume_m3:.0f} m3. Excavate more or select fewer facilities."
        )

    # Power check
    if plan.total_power_draw_w > available_power_w:
        plan.notes.append(
            f"WARNING: Need {plan.total_power_draw_w:.0f}W but only "
            f"{available_power_w:.0f}W available. Add more solar panels."
        )

    # Break-even
    net_annual = plan.total_annual_revenue_usd - plan.total_annual_operating_cost_usd
    if net_annual > 0:
        plan.break_even_years = plan.total_cost_usd / net_annual
    else:
        plan.break_even_years = -1

    return plan


def format_phase2_report(plan: Phase2Plan, phase1_revenue: float = 0) -> str:
    """Format Phase 2 plan as a report."""
    lines = []
    lines.append("=" * 70)
    lines.append("PHASE 2 MISSION PLAN -- Chamber Facilities")
    lines.append("What to build inside the excavated asteroid chamber")
    lines.append("=" * 70)

    lines.append(f"\n--- SELECTED FACILITIES ({len(plan.selected_facilities)}) ---")
    for fac in plan.selected_facilities:
        lines.append(f"\n  [{fac.category.upper()}] {fac.name}")
        lines.append(f"    {fac.description[:80]}...")
        lines.append(f"    Mass: {fac.equipment_mass_kg:,.0f} kg  "
                     f"Cost: ${fac.equipment_cost_usd:,.0f}  "
                     f"Power: {fac.power_draw_w:,.0f}W")
        lines.append(f"    Volume: {fac.requires_chamber_m3:.0f} m3  "
                     f"Install: {fac.installation_time_days:.0f} days")
        if fac.annual_revenue_usd > 0:
            lines.append(f"    Revenue: ${fac.annual_revenue_usd:,.0f}/year")
        if fac.strategic_value:
            lines.append(f"    Strategic: {fac.strategic_value[:70]}...")

    lines.append(f"\n--- TOTALS ---")
    lines.append(f"  Equipment mass:     {plan.total_equipment_mass_kg:,.0f} kg")
    lines.append(f"  Equipment cost:     ${plan.total_equipment_cost_usd:,.0f}")
    lines.append(f"  Launch cost:        ${plan.total_launch_cost_usd:,.0f}")
    lines.append(f"  TOTAL COST:         ${plan.total_cost_usd:,.0f}")
    lines.append(f"  Volume needed:      {plan.total_volume_needed_m3:,.0f} m3")
    lines.append(f"  Power draw:         {plan.total_power_draw_w:,.0f}W")
    lines.append(f"  Installation time:  {plan.installation_timeline_days:.0f} days")
    lines.append(f"  Annual revenue:     ${plan.total_annual_revenue_usd:,.0f}")
    lines.append(f"  Annual opex:        ${plan.total_annual_operating_cost_usd:,.0f}")

    if plan.break_even_years > 0:
        lines.append(f"  Break-even:         {plan.break_even_years:.1f} years")
    else:
        lines.append(f"  Break-even:         NEVER (no revenue from selected facilities)")

    if phase1_revenue > 0:
        lines.append(f"\n--- COMBINED ECONOMICS (Phase 1 + Phase 2) ---")
        combined_annual = plan.total_annual_revenue_usd + phase1_revenue / 5  # Phase 1 over 5 yr
        lines.append(f"  Phase 1 mining revenue (5yr): ${phase1_revenue:,.0f}")
        lines.append(f"  Phase 2 annual revenue:       ${plan.total_annual_revenue_usd:,.0f}")
        lines.append(f"  Combined annual:              ${combined_annual:,.0f}")

    if plan.notes:
        lines.append(f"\n--- WARNINGS ---")
        for note in plan.notes:
            lines.append(f"  * {note}")

    # Show all available facilities
    lines.append(f"\n--- ALL AVAILABLE FACILITIES ---")
    for fac in FACILITIES:
        selected = "[X]" if fac.id in [f.id for f in plan.selected_facilities] else "[ ]"
        rev = f"${fac.annual_revenue_usd/1e6:.0f}M/yr" if fac.annual_revenue_usd > 0 else "strategic"
        lines.append(f"  {selected} {fac.id:25s} {fac.equipment_mass_kg:>6,.0f}kg  "
                     f"${fac.equipment_cost_usd/1e6:.0f}M  {rev}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
