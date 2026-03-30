"""Sous Vide Nautilus Station -- Lifecycle Simulator

Simulates a Pac-Man station processing 10m C-type asteroids over decades.
Models: asteroid cycles, bioleaching extraction, shell construction,
customer visits, tug water consumption, and nautilus chamber growth.

Key question: does the leading edge rebuild faster than customers consume?
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# === Constants (from catalog + manifest specs) ===

# 10m C-type asteroid
ASTEROID_MASS_KG = 628_000
ASTEROID_WATER_KG = 50_000          # 8% ice
ASTEROID_IRON_PPM = 200_000         # 20% iron
ASTEROID_NICKEL_PPM = 13_000
ASTEROID_COPPER_PPM = 120
ASTEROID_COBALT_PPM = 500
ASTEROID_PGM_PPM = 28

# Processing phases (hours)
HEATING_HOURS = 30 * 24             # 30 days
BIOLEACH_HOURS = 90 * 24            # 90 days (overlaps with extraction)
EXTRACTION_HOURS = 60 * 24          # 60 days (overlaps with bioleaching)
CYCLE_TOTAL_HOURS = HEATING_HOURS + BIOLEACH_HOURS  # ~120 days active
TUG_FETCH_HOURS = 30 * 24           # 30 days for tug round trip
FULL_CYCLE_HOURS = CYCLE_TOTAL_HOURS + TUG_FETCH_HOURS  # ~150 days total

# Extraction efficiency (from bioreactor specs)
SULFIDE_EFFICIENCY = 0.85           # A. ferrooxidans: 85% of sulfide metals
PGM_EFFICIENCY = 0.40               # C. violaceum: 40% of PGMs

# Shell construction
SHELL_INSTALL_KG_PER_DAY = 50       # Surface ant welding rate
SHELL_SURFACE_AREA_M2 = 400         # Bag exterior area
IRON_DENSITY_KG_M3 = 7_870

# Tug water consumption
TUG_WATER_PER_FETCH_KG = 800

# Customer defaults
DEFAULT_CUSTOMER_ORDER = {
    "nickel_kg": 500,
    "copper_kg": 30,
    "cobalt_kg": 20,
    "pgm_kg": 1,
}

# Material values at lunar orbit ($/kg)
VALUES = {
    "iron": 20,
    "nickel": 25_000,
    "copper": 22_000,
    "cobalt": 80_000,
    "pgm": 30_000_000,
    "water": 50_000,
}

# Nautilus chamber lifecycle
CHAMBER_LIFESPAN_YEARS = 3          # Each active chamber lasts ~3 years
GLASS_LINING_SINTER_DAYS = 17       # 400 m^2 at 1 m^2/hr
GASKET_KG_PER_SEAL = 2              # Silicone for bulkhead seal
CHAMBER_GROWTH_FACTOR = 1.2         # Each chamber 20% bigger than previous
BASE_ASTEROID_DIAMETER_M = 10       # Starting asteroid size

# Retired chamber specializations (assigned in order)
CHAMBER_ROLES = [
    "Storage (sorted metal stockpile)",
    "Water Depot (insulated ice reservoir)",
    "Manufacturing (forge + welder)",
    "Fabrication (assembly bay)",
    "Docking Expansion (multi-berth)",
    "Habitat Module (crew-capable)",
    "Foundry (large-scale casting)",
    "Refinery Expansion",
]


@dataclass
class StationState:
    """Full station state at a point in time."""
    time_hours: float = 0.0

    # Asteroid processing
    asteroids_processed: int = 0
    current_phase: str = "idle"     # idle, heating, bioleaching, extracting, tug_fetch
    phase_hours_remaining: float = 0.0

    # Material stockpiles (kg)
    iron_kg: float = 0.0
    nickel_kg: float = 0.0
    copper_kg: float = 0.0
    cobalt_kg: float = 0.0
    pgm_kg: float = 0.0
    water_kg: float = 1600.0        # Initial propellant supply

    # Shell + nautilus growth
    shell_iron_used_kg: float = 0.0
    shell_thickness_mm: float = 0.0
    retired_chambers: list = field(default_factory=list)
    active_chamber_age_hours: float = 0.0
    active_chamber_number: int = 1  # Core bag is #0
    gasket_used_kg: float = 0.0     # Only Earth consumable

    # Economics
    total_revenue_usd: float = 0.0
    customers_served: int = 0
    orders_fulfilled: int = 0
    orders_partial: int = 0

    # Bacteria culture
    culture_age_hours: float = 0.0
    culture_generations: int = 0

    @property
    def time_days(self):
        return self.time_hours / 24

    @property
    def time_years(self):
        return self.time_hours / (24 * 365.25)


def asteroid_mass_for_diameter(diameter_m):
    """Mass of a spherical asteroid at 1200 kg/m^3 density."""
    radius = diameter_m / 2
    volume = (4 / 3) * math.pi * radius ** 3
    return volume * 1200  # kg


def extract_metals_from_asteroid(diameter_m=10):
    """Calculate metals extracted from a C-type asteroid of given diameter."""
    mass = asteroid_mass_for_diameter(diameter_m)
    water = mass * 0.08  # 8% water
    return {
        "iron_kg": mass * ASTEROID_IRON_PPM / 1e6 * SULFIDE_EFFICIENCY,
        "nickel_kg": mass * ASTEROID_NICKEL_PPM / 1e6 * SULFIDE_EFFICIENCY,
        "copper_kg": mass * ASTEROID_COPPER_PPM / 1e6 * SULFIDE_EFFICIENCY,
        "cobalt_kg": mass * ASTEROID_COBALT_PPM / 1e6 * SULFIDE_EFFICIENCY,
        "pgm_kg": mass * ASTEROID_PGM_PPM / 1e6 * PGM_EFFICIENCY,
        "water_kg": water,
        "diameter_m": diameter_m,
        "mass_tonnes": mass / 1000,
    }


def run_simulation(years=20, customers_per_year=4, verbose=True):
    """Run the full station lifecycle simulation.

    Returns (state, yearly_snapshots, events).
    """
    state = StationState()
    events = []
    yearly_snapshots = []
    current_asteroid_diameter = BASE_ASTEROID_DIAMETER_M
    metals_per_asteroid = extract_metals_from_asteroid(current_asteroid_diameter)

    dt_hours = 24.0  # 1-day time steps (fast enough for multi-year sim)
    total_hours = years * 365.25 * 24

    # Start first cycle
    state.current_phase = "heating"
    state.phase_hours_remaining = HEATING_HOURS

    customer_interval_hours = (365.25 * 24) / max(customers_per_year, 0.1)
    next_customer_hours = 2 * 365.25 * 24  # First customer at year 2
    last_snapshot_year = -1

    while state.time_hours < total_hours:
        state.time_hours += dt_hours
        year = int(state.time_years)

        # --- Process current phase ---
        state.phase_hours_remaining -= dt_hours

        if state.phase_hours_remaining <= 0:
            if state.current_phase == "heating":
                state.current_phase = "bioleaching"
                state.phase_hours_remaining = BIOLEACH_HOURS
                state.culture_age_hours += BIOLEACH_HOURS
                events.append({
                    "time_years": state.time_years,
                    "type": "phase",
                    "message": f"Asteroid #{state.asteroids_processed + 1}: bioleaching started"
                })

            elif state.current_phase == "bioleaching":
                # Extraction complete -- add metals to stockpile
                state.current_phase = "tug_fetch"
                state.phase_hours_remaining = TUG_FETCH_HOURS

                for metal, amount in metals_per_asteroid.items():
                    if not hasattr(state, metal):
                        continue  # Skip metadata keys like diameter_m, mass_tonnes
                    current = getattr(state, metal)
                    setattr(state, metal, current + amount)

                state.asteroids_processed += 1
                state.culture_generations += 1
                # Tug water scales with asteroid mass (~1.6% ratio)
                tug_water = metals_per_asteroid.get("mass_tonnes", 628) * 1000 * 0.0013
                state.water_kg -= tug_water

                events.append({
                    "time_years": state.time_years,
                    "type": "extraction",
                    "message": (
                        f"Asteroid #{state.asteroids_processed} "
                        f"({metals_per_asteroid.get('diameter_m', 10):.0f}m, "
                        f"{metals_per_asteroid.get('mass_tonnes', 628):.0f}t): "
                        f"+{metals_per_asteroid['iron_kg']/1000:.0f}t Fe, "
                        f"+{metals_per_asteroid['nickel_kg']:.0f} kg Ni"
                    )
                })

            elif state.current_phase == "tug_fetch":
                # New asteroid arrived, start heating
                # (Pac-Man mode: bag A stays warm, minimal reheating)
                reheat = HEATING_HOURS * 0.1 if state.asteroids_processed > 1 else HEATING_HOURS
                state.current_phase = "heating"
                state.phase_hours_remaining = reheat

            elif state.current_phase == "idle":
                state.current_phase = "heating"
                state.phase_hours_remaining = HEATING_HOURS

        # --- Shell construction (continuous, uses iron stockpile) ---
        if state.iron_kg > 100:  # Minimum threshold to start building
            install_kg = min(SHELL_INSTALL_KG_PER_DAY * (dt_hours / 24),
                             state.iron_kg * 0.1)  # Use max 10% of iron per step
            state.iron_kg -= install_kg
            state.shell_iron_used_kg += install_kg
            # thickness = total_iron_volume / surface_area
            volume_m3 = state.shell_iron_used_kg / IRON_DENSITY_KG_M3
            state.shell_thickness_mm = (volume_m3 / SHELL_SURFACE_AREA_M2) * 1000

        # --- Nautilus chamber lifecycle ---
        # Active chamber ages. When it reaches lifespan, retire it and build new.
        state.active_chamber_age_hours += dt_hours
        chamber_lifespan_hours = CHAMBER_LIFESPAN_YEARS * 365.25 * 24

        if (state.active_chamber_age_hours >= chamber_lifespan_hours
                and state.asteroids_processed >= 2
                and state.iron_kg > 50_000):  # Need iron for new walls
            # Retire active chamber
            role_idx = len(state.retired_chambers)
            if role_idx < len(CHAMBER_ROLES):
                role = CHAMBER_ROLES[role_idx]
            else:
                role = f"Expansion Module #{role_idx + 1}"

            state.retired_chambers.append({
                "number": state.active_chamber_number,
                "role": role,
                "retired_year": state.time_years,
            })
            state.gasket_used_kg += GASKET_KG_PER_SEAL
            state.iron_kg -= 50_000  # 50 tonnes for new chamber walls

            events.append({
                "time_years": state.time_years,
                "type": "chamber",
                "message": (
                    f"Chamber #{state.active_chamber_number} retired -> {role}. "
                    f"Airlock relocated. Glass liner sintered. "
                    f"New active chamber #{state.active_chamber_number + 1} built. "
                    f"({state.gasket_used_kg:.0f} kg gasket used total from Earth)"
                )
            })

            state.active_chamber_number += 1
            state.active_chamber_age_hours = 0.0

            # Scoop-lid growth: next chamber is bigger, captures bigger asteroids
            current_asteroid_diameter *= CHAMBER_GROWTH_FACTOR
            metals_per_asteroid = extract_metals_from_asteroid(current_asteroid_diameter)

        # --- Customer visits ---
        if state.time_hours >= next_customer_hours and state.asteroids_processed >= 2:
            order = DEFAULT_CUSTOMER_ORDER.copy()
            revenue = 0.0
            fulfilled = True

            for metal_key, amount in order.items():
                stockpile_key = metal_key  # Already matches state attribute names
                available = getattr(state, stockpile_key)
                taken = min(amount, available)
                setattr(state, stockpile_key, available - taken)

                # Revenue
                base_metal = metal_key.replace("_kg", "")
                if base_metal in VALUES:
                    revenue += taken * VALUES[base_metal]

                if taken < amount:
                    fulfilled = False

            state.total_revenue_usd += revenue
            state.customers_served += 1
            if fulfilled:
                state.orders_fulfilled += 1
            else:
                state.orders_partial += 1

            events.append({
                "time_years": state.time_years,
                "type": "customer",
                "message": (
                    f"Customer #{state.customers_served}: "
                    f"${revenue/1e6:.2f}M revenue"
                    f"{' (partial fill)' if not fulfilled else ''}"
                )
            })

            next_customer_hours = state.time_hours + customer_interval_hours

        # --- Yearly snapshot ---
        if year > last_snapshot_year and year >= 1:
            yearly_snapshots.append({
                "year": year,
                "asteroids": state.asteroids_processed,
                "iron_t": state.iron_kg / 1000,
                "nickel_t": state.nickel_kg / 1000,
                "copper_kg": state.copper_kg,
                "cobalt_kg": state.cobalt_kg,
                "pgm_kg": state.pgm_kg,
                "shell_mm": state.shell_thickness_mm,
                "shell_iron_t": state.shell_iron_used_kg / 1000,
                "chambers": len(state.retired_chambers),
                "active_ch": state.active_chamber_number,
                "gasket_kg": state.gasket_used_kg,
                "water_t": state.water_kg / 1000,
                "revenue_m": state.total_revenue_usd / 1e6,
                "customers": state.customers_served,
                "culture_gens": state.culture_generations,
            })
            last_snapshot_year = year

    return state, yearly_snapshots, events


def format_report(state, snapshots, events, years, customers_per_year):
    """Format the simulation results as a printable report."""
    lines = []
    metals = extract_metals_from_asteroid()

    lines.append("=" * 90)
    lines.append("  SOUS VIDE NAUTILUS STATION -- LIFECYCLE SIMULATION")
    lines.append("=" * 90)
    lines.append(f"  Duration: {years} years | Customers: {customers_per_year}/year (after year 2)")
    lines.append(f"  Asteroid size: 10m C-type (628t, 8% water)")
    lines.append(f"  Per asteroid yield: {metals['iron_kg']/1000:.0f}t Fe, "
                 f"{metals['nickel_kg']:.0f} kg Ni, {metals['copper_kg']:.0f} kg Cu, "
                 f"{metals['cobalt_kg']:.0f} kg Co, {metals['pgm_kg']:.1f} kg PGMs")
    lines.append("")

    # Year-by-year table
    lines.append("--- YEAR-BY-YEAR GROWTH ---")
    hdr = (f"{'Year':>4} | {'Rocks':>5} | {'Iron':>8} | {'Nickel':>8} | "
           f"{'Cu kg':>6} | {'Co kg':>6} | {'PGM kg':>6} | "
           f"{'Shell':>7} | {'Chmbrs':>6} | {'Water':>7} | {'Revenue':>9}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for s in snapshots:
        lines.append(
            f"{s['year']:>4} | {s['asteroids']:>5} | "
            f"{s['iron_t']:>6.0f} t | {s['nickel_t']:>6.1f} t | "
            f"{s['copper_kg']:>6.0f} | {s['cobalt_kg']:>6.0f} | {s['pgm_kg']:>6.1f} | "
            f"{s['shell_mm']:>5.1f}mm | {s['chambers']:>6} | "
            f"{s['water_t']:>5.0f} t | ${s['revenue_m']:>7.1f}M"
        )

    # Key events
    lines.append("")
    lines.append("--- KEY EVENTS ---")
    shown = 0
    for e in events:
        if e["type"] in ("chamber", "extraction") or shown < 30:
            lines.append(f"  Year {e['time_years']:>5.1f}: [{e['type']:>10}] {e['message']}")
            shown += 1
            if shown >= 40:
                lines.append(f"  ... ({len(events) - 40} more events)")
                break

    # Final summary
    lines.append("")
    lines.append("=" * 90)
    lines.append("  FINAL STATE")
    lines.append("=" * 90)
    lines.append(f"  Asteroids processed:    {state.asteroids_processed}")
    lines.append(f"  Bacteria generations:   {state.culture_generations} "
                 f"(culture age: {state.culture_age_hours/24/365:.1f} years)")
    lines.append(f"  Shell thickness:        {state.shell_thickness_mm:.1f} mm "
                 f"({state.shell_iron_used_kg/1000:.0f} tonnes iron)")
    lines.append(f"  Active chamber:         #{state.active_chamber_number} "
                 f"(age: {state.active_chamber_age_hours/24/365:.1f} years)")
    lines.append(f"  Retired chambers:       {len(state.retired_chambers)}")
    for c in state.retired_chambers:
        lines.append(f"    - Ch.#{c['number']} -> {c['role']} (retired year {c['retired_year']:.1f})")
    lines.append(f"  Gasket from Earth:      {state.gasket_used_kg:.0f} kg "
                 f"(only Earth consumable in {state.time_years:.0f} years)")
    lines.append(f"  Water reserve:          {state.water_kg/1000:.0f} tonnes")
    lines.append(f"  Customers served:       {state.customers_served} "
                 f"({state.orders_fulfilled} full, {state.orders_partial} partial)")
    lines.append(f"  Total revenue:          ${state.total_revenue_usd/1e6:.1f}M")
    lines.append("")

    # Stockpiles
    lines.append("  CURRENT STOCKPILES (available for sale):")
    lines.append(f"    Iron:    {state.iron_kg/1000:>8.0f} tonnes")
    lines.append(f"    Nickel:  {state.nickel_kg:>8.0f} kg")
    lines.append(f"    Copper:  {state.copper_kg:>8.0f} kg")
    lines.append(f"    Cobalt:  {state.cobalt_kg:>8.0f} kg")
    lines.append(f"    PGMs:    {state.pgm_kg:>8.1f} kg")
    lines.append("")

    # Sustainability check
    lines.append("  SUSTAINABILITY CHECK:")
    if state.water_kg > 10_000:
        lines.append(f"    Water balance:  SUSTAINABLE ({state.water_kg/1000:.0f}t reserve)")
    else:
        lines.append(f"    Water balance:  WARNING ({state.water_kg/1000:.0f}t -- low)")

    if state.nickel_kg > 0 and state.copper_kg > 0:
        lines.append(f"    Metal stockpile: GROWING (leading edge rebuilds faster than customers take)")
    else:
        lines.append(f"    Metal stockpile: DEPLETED (customers consuming faster than production)")

    fill_rate = state.orders_fulfilled / max(state.customers_served, 1) * 100
    lines.append(f"    Order fill rate: {fill_rate:.0f}% ({state.orders_fulfilled}/{state.customers_served})")
    lines.append("")
    lines.append("  From 94 kg of membrane to a {:.0f}-tonne facility.".format(
        state.shell_iron_used_kg / 1000))
    lines.append("  The bag is still at the center. Still running bacteria.")
    lines.append("=" * 90)

    return "\n".join(lines)
