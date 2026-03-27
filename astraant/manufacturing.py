"""In-situ manufacturing model -- what can we build from asteroid materials.

When extraction outpaces shipping capacity, excess materials can be used
to expand the mining operation itself. This is the path to self-replication:
the factory that builds copies of itself.

Key insight: electronics are tiny and light (ship from Earth).
Everything else (structure, tools, pods, wiring) can be made locally.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ManufacturableItem:
    """Something that can be built from asteroid materials."""
    name: str
    category: str                     # "ant_part", "infrastructure", "pod", "tool"
    local_materials: dict[str, float] # Material -> kg needed
    earth_materials: dict[str, float] # Material -> kg needed (must be shipped)
    production_time_hours: float
    production_method: str            # "sintering", "casting", "ferrocement", "drawing"
    description: str


# What we can manufacture from extracted materials
MANUFACTURABLE = [
    ManufacturableItem(
        name="Worker Ant Chassis (ferrocement)",
        category="ant_part",
        local_materials={"iron_powder": 0.015, "waste_paste": 0.010, "water": 0.005},
        earth_materials={"petg_filament": 0.005},  # For internal reinforcement
        production_time_hours=6,
        production_method="ferrocement + 3D printed scaffold",
        description="Ant body frame from sintered iron powder + waste paste composite. "
                    "Stronger and more radiation-resistant than pure PETG.",
    ),
    ManufacturableItem(
        name="Worker Ant Chassis (sintered metal)",
        category="ant_part",
        local_materials={"iron_powder": 0.025, "nickel_powder": 0.005},
        earth_materials={},
        production_time_hours=8,
        production_method="metal powder sintering (microwave or solar furnace)",
        description="All-metal chassis. Requires solar furnace for sintering. "
                    "Extremely durable but heavier than ferrocement version.",
    ),
    ManufacturableItem(
        name="Tool Head -- Drill Bit",
        category="tool",
        local_materials={"iron_powder": 0.010, "cobalt_powder": 0.002},
        earth_materials={},
        production_time_hours=4,
        production_method="metal powder sintering",
        description="Replacement drill bit from extracted iron-cobalt alloy. "
                    "Not as hard as tungsten carbide but functional for regolith.",
    ),
    ManufacturableItem(
        name="Tool Head -- Scoop",
        category="tool",
        local_materials={"iron_powder": 0.008},
        earth_materials={},
        production_time_hours=2,
        production_method="sintered metal or cast",
        description="Simple scoop from sintered iron. Easiest tool to make locally.",
    ),
    ManufacturableItem(
        name="Tool Head -- Thermal Rake",
        category="tool",
        local_materials={"iron_powder": 0.012},
        earth_materials={},
        production_time_hours=3,
        production_method="sintered metal",
        description="Rake tines from sintered iron. Heat-resistant for drum operation.",
    ),
    ManufacturableItem(
        name="Tool Head -- Paste Nozzle Body",
        category="tool",
        local_materials={"waste_paste": 0.015, "water": 0.005},
        earth_materials={"silicone_tube": 0.003},
        production_time_hours=2,
        production_method="ferrocement body + purchased silicone reservoir",
        description="Nozzle body from ferrocement. Silicone tube still needed from Earth.",
    ),
    ManufacturableItem(
        name="Cargo Pod Shell",
        category="pod",
        local_materials={"waste_paste": 0.100, "water": 0.025},
        earth_materials={"petg_filament": 0.005},
        production_time_hours=5,
        production_method="ferrocement (PETG lattice + waste paste fill)",
        description="Pod shell from mining waste. Zero effective cost.",
    ),
    ManufacturableItem(
        name="CO2 Thruster Tank",
        category="pod",
        local_materials={"iron_sheet": 0.050},
        earth_materials={},
        production_time_hours=4,
        production_method="rolled + welded iron sheet (or sintered cylinder)",
        description="Thruster tank from extracted iron. Simple pressure vessel.",
    ),
    ManufacturableItem(
        name="Copper Wire (1m, 20 AWG)",
        category="infrastructure",
        local_materials={"copper": 0.001},
        earth_materials={},
        production_time_hours=1,
        production_method="wire drawing through sintered dies",
        description="Copper wire drawn from extracted copper. For power distribution "
                    "and communication backbone in new tunnel sections.",
    ),
    ManufacturableItem(
        name="Tunnel Support Bracket",
        category="infrastructure",
        local_materials={"iron_powder": 0.050},
        earth_materials={},
        production_time_hours=2,
        production_method="sintered metal",
        description="Structural bracket for equipment mounting in tunnels.",
    ),
    ManufacturableItem(
        name="Tool Dock Station",
        category="infrastructure",
        local_materials={"iron_powder": 0.100, "waste_paste": 0.050},
        earth_materials={"neodymium_magnet": 0.005},
        production_time_hours=4,
        production_method="sintered metal frame + ferrocement base",
        description="Tool swap station. Frame is local metal, magnets from Earth.",
    ),
    ManufacturableItem(
        name="Solar Reflector Panel (1 m2)",
        category="infrastructure",
        local_materials={"iron_sheet": 0.200, "nickel_polish": 0.010},
        earth_materials={},
        production_time_hours=6,
        production_method="polished metal sheet",
        description="Polished iron-nickel sheet as solar concentrator or light redirector. "
                    "Not as efficient as proper mirror but functional for supplemental light.",
    ),
    ManufacturableItem(
        name="PHB Bioplastic Filament (1 kg)",
        category="infrastructure",
        local_materials={"phb_from_c_necator": 1.0},
        earth_materials={},
        production_time_hours=8,
        production_method="extrude PHB from C. necator biomass",
        description="3D printable bioplastic produced by Cupriavidus necator from H2+CO2. "
                    "Replaces PETG filament shipped from Earth. Biodegradable but functional.",
    ),
    ManufacturableItem(
        name="Bioreactor Vat (additional, 50L)",
        category="infrastructure",
        local_materials={"iron_sheet": 0.500, "waste_paste": 0.200},
        earth_materials={"gaskets": 0.020, "sensors": 0.050},
        production_time_hours=20,
        production_method="welded iron vessel + ferrocement insulation",
        description="Additional bioreactor vat from local iron. Sensors/gaskets from Earth. "
                    "Doubles extraction capacity per unit shipped from Earth.",
    ),
]

# What must always come from Earth (too complex to manufacture locally)
EARTH_ONLY = [
    {"item": "RP2040 / ESP32-S3 microcontrollers", "mass_per_100_ants_kg": 0.5,
     "reason": "Semiconductor fabrication requires clean room and nanometer-scale lithography"},
    {"item": "SG90 / SG51R servo motors", "mass_per_100_ants_kg": 5.4,
     "reason": "Precision DC motors with gears require specialized manufacturing"},
    {"item": "Sensor modules (VL53L0x, BNO055, etc)", "mass_per_100_ants_kg": 0.5,
     "reason": "Complex optoelectronic and MEMS devices"},
    {"item": "nRF24L01 radio modules", "mass_per_100_ants_kg": 0.2,
     "reason": "RF electronics require precise impedance matching"},
    {"item": "LiPo battery cells", "mass_per_100_ants_kg": 1.5,
     "reason": "Lithium chemistry requires controlled atmosphere manufacturing"},
    {"item": "CP1 polyimide sail film", "mass_per_100_ants_kg": 0.7,
     "reason": "Specialty polymer film with nanometer-scale aluminum coating"},
    {"item": "Neodymium magnets (tool mounts)", "mass_per_100_ants_kg": 0.3,
     "reason": "Rare earth magnets require sintering furnace with specific atmosphere"},
]


@dataclass
class ManufacturingPlan:
    """Plan for using excess materials to expand operations."""
    available_materials_kg: dict[str, float]
    items_buildable: list[tuple[ManufacturableItem, int]]  # Item + quantity possible
    earth_resupply_needed_kg: dict[str, float]
    new_ants_possible: int
    new_pods_possible: int
    expansion_summary: str


def plan_manufacturing(excess_materials_kg: dict[str, float]) -> ManufacturingPlan:
    """Given excess extracted materials, plan what to build.

    Args:
        excess_materials_kg: Dict of material -> kg available
            Expected keys: iron, nickel, copper, cobalt, waste_paste, water
    """
    # Normalize material names
    available = {
        "iron_powder": excess_materials_kg.get("iron", 0),
        "iron_sheet": excess_materials_kg.get("iron", 0) * 0.5,  # Can make sheet from powder
        "nickel_powder": excess_materials_kg.get("nickel", 0),
        "nickel_polish": excess_materials_kg.get("nickel", 0) * 0.1,
        "copper": excess_materials_kg.get("copper", 0),
        "cobalt_powder": excess_materials_kg.get("cobalt", 0),
        "waste_paste": excess_materials_kg.get("waste_paste", 0),
        "water": excess_materials_kg.get("water", 0),
        "phb_from_c_necator": excess_materials_kg.get("phb", 0),
    }

    plan = ManufacturingPlan(
        available_materials_kg=available,
        items_buildable=[],
        earth_resupply_needed_kg={},
        new_ants_possible=0,
        new_pods_possible=0,
        expansion_summary="",
    )

    earth_needs: dict[str, float] = {}

    for item in MANUFACTURABLE:
        # How many can we build with available local materials?
        max_qty = float('inf')
        for mat, needed in item.local_materials.items():
            if needed > 0:
                avail = available.get(mat, 0)
                max_qty = min(max_qty, avail / needed)
        max_qty = int(max_qty) if max_qty != float('inf') else 0

        if max_qty > 0:
            plan.items_buildable.append((item, max_qty))
            # Track earth materials needed
            for mat, needed in item.earth_materials.items():
                earth_needs[mat] = earth_needs.get(mat, 0) + needed * max_qty

        if item.category == "ant_part" and "Chassis" in item.name:
            plan.new_ants_possible = max(plan.new_ants_possible, max_qty)
        if item.name == "Cargo Pod Shell":
            plan.new_pods_possible = max_qty

    plan.earth_resupply_needed_kg = earth_needs

    # Summary
    lines = []
    lines.append(f"With current excess materials, you can build:")
    lines.append(f"  - Up to {plan.new_ants_possible} new ant chassis (need electronics from Earth)")
    lines.append(f"  - Up to {plan.new_pods_possible} new cargo pods (fully local materials)")
    if earth_needs:
        total_earth = sum(earth_needs.values())
        lines.append(f"  - Earth resupply needed: {total_earth:.1f} kg of specialty materials")
        lines.append(f"    (electronics, servos, sensors, magnets)")
    plan.expansion_summary = "\n".join(lines)

    return plan


def format_manufacturing_report(plan: ManufacturingPlan,
                                excess_kg: dict[str, float]) -> str:
    """Format manufacturing plan as readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("IN-SITU MANUFACTURING PLAN")
    lines.append("What to build with excess extracted materials")
    lines.append("=" * 70)

    lines.append(f"\n--- AVAILABLE EXCESS MATERIALS ---")
    for mat, kg in sorted(excess_kg.items(), key=lambda x: -x[1]):
        if kg > 0.001:
            lines.append(f"  {mat:20s} {kg:>10.1f} kg")

    lines.append(f"\n--- BUILDABLE ITEMS ---")
    lines.append(f"  {'Item':<40s} {'Qty':>5s} {'Method'}")
    lines.append(f"  {'-'*65}")
    for item, qty in sorted(plan.items_buildable, key=lambda x: -x[1]):
        lines.append(f"  {item.name:<40s} {qty:>5d}  {item.production_method[:25]}")

    lines.append(f"\n--- EARTH RESUPPLY NEEDED ---")
    if plan.earth_resupply_needed_kg:
        for mat, kg in sorted(plan.earth_resupply_needed_kg.items(), key=lambda x: -x[1]):
            lines.append(f"  {mat:30s} {kg:>8.3f} kg")
    else:
        lines.append(f"  (none -- fully self-sufficient for these items)")

    lines.append(f"\n--- ITEMS THAT MUST COME FROM EARTH ---")
    total_earth_per_100 = 0.0
    for item in EARTH_ONLY:
        lines.append(f"  {item['item']:45s} {item['mass_per_100_ants_kg']:>5.1f} kg/100 ants")
        total_earth_per_100 += item["mass_per_100_ants_kg"]
    lines.append(f"  {'TOTAL per 100 ants':45s} {total_earth_per_100:>5.1f} kg")
    lines.append(f"\n  To build 100 more ants: ship {total_earth_per_100:.1f} kg of electronics from Earth.")
    lines.append(f"  Everything else built locally from asteroid materials.")

    lines.append(f"\n--- EXPANSION SUMMARY ---")
    lines.append(plan.expansion_summary)

    lines.append(f"\n--- SELF-REPLICATION POTENTIAL ---")
    if plan.new_ants_possible >= 10:
        lines.append(f"  With {total_earth_per_100:.1f} kg of electronics shipped from Earth,")
        lines.append(f"  you could build {min(100, plan.new_ants_possible)} new worker ants on-site.")
        lines.append(f"  That doubles the swarm from a {total_earth_per_100:.1f} kg resupply package.")
        lines.append(f"  The factory builds copies of itself.")
    else:
        lines.append(f"  Insufficient excess materials for significant expansion.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
