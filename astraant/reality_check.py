"""Reality check — the costs our feasibility model doesn't capture yet.

The hardware + LEO launch cost ($3M) is real but it's not the whole story.
This module estimates the FULL mission cost including transit, operations,
landing, qualification, and business overhead.

This is the "why isn't everyone doing this" module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .mission_economics import MissionEconomics


@dataclass
class RealityCostItem:
    """A cost item not captured in the hardware model."""
    category: str
    name: str
    cost_low_usd: float
    cost_high_usd: float
    description: str
    reducible: bool = True     # Can this cost be reduced with technology?
    timeline_years: float = 0  # When in the mission this cost hits


# The costs we've been ignoring
REALITY_COSTS = [
    # --- Getting there ---
    RealityCostItem(
        category="transit",
        name="Deep space propulsion stage",
        cost_low_usd=5_000_000,
        cost_high_usd=50_000_000,
        description="Chemical or solar-electric propulsion to get from LEO to the asteroid. "
                    "Falcon 9 upper stage to TLI is ~$5M marginal. Custom deep space "
                    "stage with ion propulsion: $20-50M. Solar sail transit is free but takes years.",
        timeline_years=0,
    ),
    RealityCostItem(
        category="transit",
        name="Landing system",
        cost_low_usd=2_000_000,
        cost_high_usd=20_000_000,
        description="Soft-landing 750 kg on a body with near-zero gravity. Needs autonomous "
                    "GNC, hazard avoidance, anchoring system. OSIRIS-REx TAG cost ~$800M total "
                    "but only touched the surface briefly. A permanent landing is different.",
        timeline_years=1,
    ),
    RealityCostItem(
        category="transit",
        name="Navigation and trajectory (transit phase)",
        cost_low_usd=500_000,
        cost_high_usd=5_000_000,
        description="Deep Space Network time, trajectory correction maneuvers, "
                    "navigation team during 1-3 year transit.",
        timeline_years=0,
    ),

    # --- Qualification ---
    RealityCostItem(
        category="qualification",
        name="Space qualification testing",
        cost_low_usd=1_000_000,
        cost_high_usd=10_000_000,
        description="Vibration testing, thermal vacuum cycling, EMI testing, radiation testing "
                    "for all flight hardware. Even COTS-based missions need qualification. "
                    "Each unique component type costs $50-200K to qualify.",
        timeline_years=-2,  # Before launch
    ),
    RealityCostItem(
        category="qualification",
        name="Flight software verification",
        cost_low_usd=500_000,
        cost_high_usd=5_000_000,
        description="Formal verification of autonomous control software. "
                    "The mothership must operate without human intervention for years. "
                    "Software bugs in space are mission-ending.",
        timeline_years=-1,
    ),
    RealityCostItem(
        category="qualification",
        name="Prototype development and testing",
        cost_low_usd=500_000,
        cost_high_usd=5_000_000,
        description="Engineering prototypes, integration testing, failure mode analysis. "
                    "Typically 2-3 prototype iterations before flight hardware.",
        timeline_years=-3,
    ),

    # --- Operations ---
    RealityCostItem(
        category="operations",
        name="Mission operations center (5 years)",
        cost_low_usd=2_000_000,
        cost_high_usd=15_000_000,
        description="Ground team monitoring the mission: operators, analysts, facility. "
                    "Supervised autonomy still needs humans watching. "
                    "Small team (5-10 people) for 5 years at $100-200K/yr each.",
        timeline_years=1,
    ),
    RealityCostItem(
        category="operations",
        name="Deep Space Network time (5 years)",
        cost_low_usd=500_000,
        cost_high_usd=3_000_000,
        description="NASA DSN charges ~$1000/hr for antenna time. At 2 hrs/day "
                    "for 5 years: $3.6M. Could use commercial alternatives (cheaper).",
        reducible=True,
        timeline_years=1,
    ),

    # --- Business overhead ---
    RealityCostItem(
        category="business",
        name="Regulatory and licensing",
        cost_low_usd=200_000,
        cost_high_usd=2_000_000,
        description="FCC spectrum licensing, FAA launch licensing, "
                    "space debris mitigation compliance, export controls (ITAR). "
                    "Artemis Accords alignment.",
        timeline_years=-1,
    ),
    RealityCostItem(
        category="business",
        name="Insurance",
        cost_low_usd=500_000,
        cost_high_usd=5_000_000,
        description="Launch insurance, third-party liability, on-orbit insurance. "
                    "Typically 5-15% of mission cost for commercial missions.",
        timeline_years=0,
    ),
    RealityCostItem(
        category="business",
        name="Company overhead (5 years)",
        cost_low_usd=2_000_000,
        cost_high_usd=10_000_000,
        description="Office, legal, accounting, fundraising, travel, conferences. "
                    "A small space startup burns $500K-2M/year.",
        timeline_years=-3,
    ),

    # --- The big one ---
    RealityCostItem(
        category="market",
        name="Market development (finding buyers)",
        cost_low_usd=0,
        cost_high_usd=0,
        description="Water at lunar orbit is worth $50K/kg ONLY IF someone is there to buy it. "
                    "The cislunar economy does not yet exist at scale. Artemis, Gateway, and "
                    "commercial lunar landers are the potential customers but none are currently "
                    "buying asteroid water. This is a market timing risk, not a cost.",
        reducible=False,
        timeline_years=3,
    ),
]

# Technology gap risks
TECHNOLOGY_GAPS = [
    {
        "gap": "Autonomous mining has never been demonstrated in space",
        "current_state": "OSIRIS-REx collected 121g. Hayabusa2 collected 5.4g. "
                         "Both were grab-and-go, not sustained mining.",
        "our_target": "32,000 kg over 5 years (6 orders of magnitude more)",
        "risk": "HIGH -- no precedent for autonomous sustained extraction",
        "mitigation": "Incremental demonstration: first prove 1 kg, then 100 kg, then scale",
    },
    {
        "gap": "Bioleaching has never been tested in microgravity",
        "current_state": "Bacteria grow fine on ISS. Bioleaching is proven on Earth. "
                         "But centrifuge bioreacting in microgravity is untested.",
        "our_target": "85% copper extraction from sulfide ore in centrifuge vats",
        "risk": "MEDIUM -- biology works, engineering is the unknown",
        "mitigation": "ISS experiment or clinostat ground test. $15K-50K.",
    },
    {
        "gap": "Solar sail cargo return at this mass ratio is undemonstrated",
        "current_state": "IKAROS and LightSail 2 proved solar sailing. "
                         "NEA Scout was 14 kg with 86m2 sail. Our pods are 2.5 kg with 10m2.",
        "our_target": "2.5 kg pods with 10m2 sails, 2.5 year transit",
        "risk": "LOW-MEDIUM -- physics is proven, mass ratio is favorable",
        "mitigation": "Cube-sat scale demonstration. $500K-2M.",
    },
    {
        "gap": "No market for asteroid materials exists yet",
        "current_state": "Zero commercial transactions for space-mined resources. "
                         "Planetary Resources went bankrupt. Deep Space Industries acquired.",
        "our_target": "Sell water and metals at lunar orbit",
        "risk": "HIGH -- market timing, not technology",
        "mitigation": "Time entry to coincide with Artemis lunar base operations (~2030+). "
                      "Or pivot to selling materials to commercial space stations.",
    },
]


def reality_check(econ: MissionEconomics | None = None) -> str:
    """Generate a reality check report showing the FULL cost picture."""
    lines = []
    lines.append("=" * 70)
    lines.append("REALITY CHECK -- FULL MISSION COST ESTIMATE")
    lines.append("What the hardware model doesn't capture")
    lines.append("=" * 70)

    if econ:
        lines.append(f"\nHardware model cost: ${econ.total_mission_cost_usd:,.0f}")
        lines.append(f"Hardware model revenue: ${econ.total_revenue_usd:,.0f}")
        lines.append("(These numbers are correct but incomplete)\n")

    # Sum up reality costs
    total_low = sum(c.cost_low_usd for c in REALITY_COSTS)
    total_high = sum(c.cost_high_usd for c in REALITY_COSTS)

    by_category = {}
    for c in REALITY_COSTS:
        if c.category not in by_category:
            by_category[c.category] = []
        by_category[c.category].append(c)

    for cat, items in by_category.items():
        cat_low = sum(i.cost_low_usd for i in items)
        cat_high = sum(i.cost_high_usd for i in items)
        lines.append(f"--- {cat.upper()} ---")
        for item in items:
            if item.cost_high_usd > 0:
                lines.append(f"  {item.name}")
                lines.append(f"    ${item.cost_low_usd/1e6:.1f}M - ${item.cost_high_usd/1e6:.1f}M")
                lines.append(f"    {item.description[:100]}")
            else:
                lines.append(f"  {item.name}")
                lines.append(f"    {item.description[:100]}")
            lines.append("")
        lines.append(f"  Subtotal: ${cat_low/1e6:.1f}M - ${cat_high/1e6:.1f}M\n")

    lines.append("--- TOTAL REALISTIC COST ---")
    if econ:
        total_low += econ.total_mission_cost_usd
        total_high += econ.total_mission_cost_usd
    lines.append(f"  Hardware + launch:    ${econ.total_mission_cost_usd/1e6:.1f}M" if econ else "")
    lines.append(f"  Additional costs:     ${sum(c.cost_low_usd for c in REALITY_COSTS)/1e6:.1f}M"
                 f" - ${sum(c.cost_high_usd for c in REALITY_COSTS)/1e6:.1f}M")
    lines.append(f"  TOTAL (realistic):    ${total_low/1e6:.0f}M - ${total_high/1e6:.0f}M")

    if econ and econ.total_revenue_usd > 0:
        lines.append(f"\n  Revenue (5yr):        ${econ.total_revenue_usd/1e6:.0f}M")
        net_low = econ.total_revenue_usd - total_high
        net_high = econ.total_revenue_usd - total_low
        lines.append(f"  Net profit range:     ${net_low/1e6:.0f}M - ${net_high/1e6:.0f}M")
        roi_low = (net_low / total_high * 100) if total_high > 0 else 0
        roi_high = (net_high / total_low * 100) if total_low > 0 else 0
        lines.append(f"  ROI range:            {roi_low:.0f}% - {roi_high:.0f}%")

    lines.append(f"\n--- TECHNOLOGY GAPS ---")
    for gap in TECHNOLOGY_GAPS:
        lines.append(f"  [{gap['risk']}] {gap['gap']}")
        lines.append(f"    Now: {gap['current_state'][:80]}")
        lines.append(f"    Mitigation: {gap['mitigation'][:80]}")
        lines.append("")

    lines.append("--- WHY ISN'T EVERYONE DOING THIS? ---")
    lines.append("  1. The $3M hardware cost is real. The $15-130M in additional costs is the barrier.")
    lines.append("  2. No market exists yet. Water at lunar orbit has no buyer today.")
    lines.append("  3. 6-8 year timeline from investment to first revenue. Most investors won't wait.")
    lines.append("  4. Autonomous space mining is 6 orders of magnitude beyond demonstrated capability.")
    lines.append("  5. Two companies tried (Planetary Resources, Deep Space Industries). Both failed.")
    lines.append("     But they failed on business model, not technology. The tech is closer now.")
    lines.append("")
    lines.append("  BOTTOM LINE: At $15-50M total realistic cost and $709M potential revenue,")
    lines.append("  the opportunity IS real. The barriers are timeline, market timing, and the")
    lines.append("  leap from lab demo to space operation. That gap is where the risk lives.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
