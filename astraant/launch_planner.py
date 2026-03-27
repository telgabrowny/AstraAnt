"""Single-launch mission planner — can we fit everything in one rocket?

Calculates the complete manifest for achieving self-sustainability
in a single Starship launch: Phase 1 mining + Phase 2 facilities +
enough electronics to bootstrap 500 locally-built ants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ManifestItem:
    """A single item on the launch manifest."""
    name: str
    category: str         # "mothership", "swarm", "consumables", "manufacturing", "phase2", "margin"
    mass_kg: float
    cost_usd: float
    notes: str = ""


@dataclass
class LaunchManifest:
    """Complete single-launch manifest."""
    items: list[ManifestItem] = field(default_factory=list)
    vehicle: str = "starship"
    vehicle_capacity_leo_kg: float = 100000
    vehicle_capacity_nea_kg: float = 25000   # After transit propulsion
    vehicle_cost_usd: float = 100_000_000    # Current Starship estimate
    vehicle_cost_future_usd: float = 20_000_000

    @property
    def total_mass_kg(self) -> float:
        return sum(i.mass_kg for i in self.items)

    @property
    def total_cost_usd(self) -> float:
        return sum(i.cost_usd for i in self.items)

    @property
    def margin_kg(self) -> float:
        return self.vehicle_capacity_nea_kg - self.total_mass_kg

    @property
    def margin_pct(self) -> float:
        return self.margin_kg / self.vehicle_capacity_nea_kg * 100

    def mass_by_category(self) -> dict[str, float]:
        cats: dict[str, float] = {}
        for item in self.items:
            cats[item.category] = cats.get(item.category, 0) + item.mass_kg
        return cats

    def cost_by_category(self) -> dict[str, float]:
        cats: dict[str, float] = {}
        for item in self.items:
            cats[item.category] = cats.get(item.category, 0) + item.cost_usd
        return cats


def plan_single_launch(
    workers: int = 100,
    taskmasters: int = 5,
    surface_ants: int = 3,
    local_ant_capacity: int = 500,     # Electronics for building this many locally
    include_phase2: bool = True,
    phase2_facilities: list[str] | None = None,  # None = all
    extra_solar_kw: float = 15.0,      # Additional solar panels for Phase 2 power
) -> LaunchManifest:
    """Plan a single-launch manifest for full self-sustainability."""

    manifest = LaunchManifest()

    # === PHASE 1: MOTHERSHIP ===
    mothership_items = [
        ("Drill module", 20.5, 50000),
        ("Power module (solar array + 10kWh battery)", 45.2, 200000),
        ("Comms module (X-band + CAN + RF)", 6, 50000),
        ("Sealing module (spray + sintering + compressor + gas)", 33, 80000),
        ("Cargo staging (bins + loading arm)", 35, 30000),
        ("Micro-pods x200 (flat-packed)", 112, 600),
        ("Bioreactor module (3 vats + precipitation, DRY)", 110, 500000),
        ("Sugar production (algae photobioreactor + CO2 kiln)", 62, 150000),
        ("Thermal sorter (drum + condenser)", 13, 30000),
        ("Exterior maintenance (grip rails + tool rack)", 3.5, 5000),
        ("Manufacturing bay (furnace + printer + jigs)", 34, 100000),
    ]
    for name, mass, cost in mothership_items:
        manifest.items.append(ManifestItem(name, "mothership", mass, cost))

    # Water for bioreactors
    manifest.items.append(ManifestItem(
        "Bioreactor water (300L)", "mothership", 300, 100,
        "Dominates Phase 1 mass. Recovered and recycled on-site."
    ))

    # === PHASE 1: SWARM ===
    worker_mass = workers * 0.115
    tm_mass = taskmasters * 0.125
    sa_mass = surface_ants * 0.440
    tool_mass = int(workers * 1.5) * 0.014

    manifest.items.append(ManifestItem(
        f"Worker ants x{workers}", "swarm", worker_mass,
        workers * 33, f"{workers} universal workers at $33 each"
    ))
    manifest.items.append(ManifestItem(
        f"Taskmaster ants x{taskmasters}", "swarm", tm_mass,
        taskmasters * 75
    ))
    manifest.items.append(ManifestItem(
        f"Surface ants x{surface_ants}", "swarm", sa_mass,
        surface_ants * 1242
    ))
    manifest.items.append(ManifestItem(
        f"Tool heads x{int(workers * 1.5)}", "swarm", tool_mass,
        int(workers * 1.5) * 7
    ))

    # === CONSUMABLES (5 year supply) ===
    consumables = [
        ("Nitrogen fill gas", 5, 200),
        ("Polymer sealant (backup)", 10, 500),
        ("Precipitation reagents (5yr)", 40, 2000),
        ("Spare drill bits + filters", 15, 1000),
        ("Backup culture stocks (lyophilized)", 0.5, 500),
        ("Nichrome wire + wax (thruster valves)", 2, 100),
    ]
    for name, mass, cost in consumables:
        manifest.items.append(ManifestItem(name, "consumables", mass, cost))

    # === MANUFACTURING RESUPPLY (for building ants locally) ===
    servos_needed = local_ant_capacity * 8  # 6 legs + 2 mandibles
    manifest.items.append(ManifestItem(
        f"Servo motors x{servos_needed} (SG90+SG51R)", "manufacturing",
        local_ant_capacity * 0.054,  # 54g servos per ant
        local_ant_capacity * 15,
        f"Enough to build {local_ant_capacity} ants locally from asteroid metal"
    ))
    manifest.items.append(ManifestItem(
        f"MCU boards x{local_ant_capacity} (RP2040 Pico)", "manufacturing",
        local_ant_capacity * 0.005, local_ant_capacity * 4
    ))
    manifest.items.append(ManifestItem(
        f"Sensor modules x{local_ant_capacity}", "manufacturing",
        local_ant_capacity * 0.001, local_ant_capacity * 4
    ))
    manifest.items.append(ManifestItem(
        f"Radio modules x{local_ant_capacity}", "manufacturing",
        local_ant_capacity * 0.002, local_ant_capacity * 2
    ))
    manifest.items.append(ManifestItem(
        f"Battery cells x{local_ant_capacity}", "manufacturing",
        local_ant_capacity * 0.015, local_ant_capacity * 3
    ))
    manifest.items.append(ManifestItem(
        f"Neodymium magnets x{local_ant_capacity * 4}", "manufacturing",
        local_ant_capacity * 0.002, local_ant_capacity * 1
    ))
    manifest.items.append(ManifestItem(
        "PETG filament (50 spools)", "manufacturing",
        50, 1000, "For mold printing until PHB bioplastic production starts"
    ))

    # === PHASE 2: CHAMBER FACILITIES ===
    if include_phase2:
        from .phase2 import FACILITIES
        if phase2_facilities is None:
            selected = FACILITIES  # All of them
        else:
            selected = [f for f in FACILITIES if f.id in phase2_facilities]

        for fac in selected:
            manifest.items.append(ManifestItem(
                fac.name, "phase2", fac.equipment_mass_kg, fac.equipment_cost_usd,
                f"Install after chamber excavation. {fac.category} facility."
            ))

    # === EXTRA SOLAR PANELS (Phase 2 needs more power) ===
    if extra_solar_kw > 0:
        # GaAs panels: ~0.3 kg/m2, ~290 W/m2 at 1 AU
        panel_area_m2 = extra_solar_kw * 1000 / 290
        panel_mass = panel_area_m2 * 0.3 + 20  # Panels + deployment mechanism
        manifest.items.append(ManifestItem(
            f"Additional solar panels (+{extra_solar_kw:.0f} kW)", "mothership",
            panel_mass, extra_solar_kw * 5000,
            f"{panel_area_m2:.0f} m2 GaAs array for Phase 2 power needs"
        ))

    return manifest


def format_manifest(manifest: LaunchManifest) -> str:
    """Format the launch manifest as a readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SINGLE-LAUNCH MISSION MANIFEST")
    lines.append("One rocket to self-sustainability")
    lines.append("=" * 70)
    lines.append(f"Vehicle: {manifest.vehicle.upper()}")
    lines.append(f"Capacity to NEA: {manifest.vehicle_capacity_nea_kg:,} kg")

    # Group by category
    categories = {}
    for item in manifest.items:
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)

    cat_order = ["mothership", "swarm", "consumables", "manufacturing", "phase2"]
    cat_labels = {
        "mothership": "MOTHERSHIP & INFRASTRUCTURE",
        "swarm": "ANT SWARM",
        "consumables": "CONSUMABLES (5-YEAR SUPPLY)",
        "manufacturing": "LOCAL MANUFACTURING RESUPPLY",
        "phase2": "PHASE 2 CHAMBER FACILITIES",
    }

    for cat in cat_order:
        if cat not in categories:
            continue
        items = categories[cat]
        cat_mass = sum(i.mass_kg for i in items)
        cat_cost = sum(i.cost_usd for i in items)
        lines.append(f"\n--- {cat_labels.get(cat, cat.upper())} ({cat_mass:,.1f} kg, ${cat_cost:,.0f}) ---")
        for item in items:
            lines.append(f"  {item.name:<50s} {item.mass_kg:>8.1f} kg  ${item.cost_usd:>10,.0f}")
            if item.notes:
                lines.append(f"    {item.notes[:70]}")

    lines.append(f"\n{'=' * 70}")
    lines.append(f"MANIFEST SUMMARY")
    lines.append(f"{'=' * 70}")

    mass_cats = manifest.mass_by_category()
    for cat in cat_order:
        if cat in mass_cats:
            pct = mass_cats[cat] / manifest.total_mass_kg * 100
            lines.append(f"  {cat_labels.get(cat, cat):<40s} {mass_cats[cat]:>8,.1f} kg ({pct:.0f}%)")

    lines.append(f"  {'':40s} {'':>8s}")
    lines.append(f"  {'TOTAL PAYLOAD':<40s} {manifest.total_mass_kg:>8,.1f} kg")
    lines.append(f"  {'Vehicle capacity':<40s} {manifest.vehicle_capacity_nea_kg:>8,} kg")
    lines.append(f"  {'MARGIN':<40s} {manifest.margin_kg:>8,.1f} kg ({manifest.margin_pct:.1f}%)")

    fits = "YES" if manifest.margin_kg >= 0 else "NO"
    lines.append(f"\n  FITS IN ONE LAUNCH: {fits}")

    # Cost breakdown
    lines.append(f"\n--- TOTAL MISSION COST ---")
    hw = manifest.total_cost_usd
    launch_current = manifest.vehicle_cost_usd
    launch_future = manifest.vehicle_cost_future_usd

    lines.append(f"  Hardware:                ${hw:>12,.0f}")
    lines.append(f"  Launch (current):        ${launch_current:>12,.0f}")
    lines.append(f"  Launch (future/volume):  ${launch_future:>12,.0f}")
    lines.append(f"  ----------------------------------------")
    lines.append(f"  TOTAL (current):         ${hw + launch_current:>12,.0f}")
    lines.append(f"  TOTAL (future):          ${hw + launch_future:>12,.0f}")

    # Revenue projection
    annual_mining = 709_000_000 / 5  # Phase 1 annualized
    annual_phase2 = 385_000_000       # All Phase 2 facilities
    total_annual = annual_mining + annual_phase2

    lines.append(f"\n--- REVENUE PROJECTION ---")
    lines.append(f"  Phase 1 mining (annual):   ${annual_mining:>12,.0f}")
    lines.append(f"  Phase 2 facilities:        ${annual_phase2:>12,.0f}")
    lines.append(f"  TOTAL ANNUAL:              ${total_annual:>12,.0f}")
    lines.append(f"")
    be_current = (hw + launch_current) / total_annual
    be_future = (hw + launch_future) / total_annual
    lines.append(f"  Break-even (current):    {be_current:.1f} years ({be_current*12:.0f} months)")
    lines.append(f"  Break-even (future):     {be_future:.1f} years ({be_future*12:.0f} months)")
    lines.append(f"")
    net5_current = total_annual * 5 - (hw + launch_current)
    net5_future = total_annual * 5 - (hw + launch_future)
    lines.append(f"  5-year net (current):    ${net5_current:>12,.0f}")
    lines.append(f"  5-year net (future):     ${net5_future:>12,.0f}")

    # The pitch
    lines.append(f"\n--- THE PITCH ---")
    lines.append(f"  One Starship. ${(hw + launch_future)/1e6:.0f}-{(hw + launch_current)/1e6:.0f}M total investment.")
    lines.append(f"  Self-sustaining asteroid colony in 5 years.")
    lines.append(f"  ${total_annual/1e6:.0f}M annual revenue. ${net5_future/1e9:.1f}-{net5_current/1e9:.1f}B return over 5 years.")
    lines.append(f"  Builds its own replacement ants from asteroid metal.")
    lines.append(f"  Excavates a radiation-shielded habitat inside the asteroid.")
    lines.append(f"  Fuel depot turns the asteroid into a gas station.")
    lines.append(f"  Shipyard builds the next generation of spacecraft.")
    lines.append(f"  One launch. Everything changes.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
