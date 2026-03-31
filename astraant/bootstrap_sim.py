"""Garbage Bag Bootstrap Simulator.

Models exponential growth from an 11 kg seed package to a full-scale
nautilus station.  Each generation:
  1. Bioleach the current asteroid (90 days, fixed)
  2. Electro-win iron from the soup
  3. Build next iron shell + bigger concentrators + upgrade current
  4. Load next (bigger) rock into the new shell

Key insight: concentrators and current grow each generation, so heating
and deposition get dramatically faster.  The Kapton membrane is used
ONCE (Step 0).  Every subsequent container is electroformed iron.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Dict, Any

# -- Physical constants -----------------------------------------------------
ROCK_DENSITY = 1200           # kg/m3 (C-type asteroid)
IRON_DENSITY = 7870           # kg/m3
IRON_FRACTION = 0.20          # 20% iron by mass
NICKEL_FRACTION = 0.013       # 1.3% nickel
COPPER_FRACTION = 0.0012      # 0.12% copper
COBALT_FRACTION = 0.005       # 0.5% cobalt
PGM_FRACTION = 1.3e-5         # 13 ppm PGMs
WATER_FRACTION = 0.08         # 8% water ice
EXTRACTION_EFF = 0.85         # 85% bioleaching efficiency

SOLAR_FLUX_NET = 1361 * 0.85 * 0.60  # W/m2 after reflection + rad losses
ROCK_CP = 800                 # J/kg/K specific heat of rock
WATER_CP = 4186               # J/kg/K
DELTA_T = 83                  # -50C to 33C

SHELL_THICKNESS_M = 0.0015    # 1.5mm iron walls (minimum viable)
CLEARANCE = 1.4               # Shell inner diameter = 1.4x rock diameter
CONC_FOIL_KG_PER_M2 = 0.39   # 0.05mm iron foil reflectors

# Faraday's law: ~1.04 g Fe per amp-hour at 2V
DEPOSITION_KG_PER_AMP_DAY = 0.02496
BIO_DAYS = 90                 # Bioleaching time per rock (mass-transfer limited)
MAX_CURRENT_A = 50000         # Practical electrode limit
CELL_VOLTAGE = 2.0            # V per electro-winning cell


@dataclass
class SeedPackage:
    """The initial package launched from Earth."""
    membrane_kg: float = 3.8    # Kapton for 2m rock
    concentrator_m2: float = 0.5  # Mylar reflector
    bacteria_kg: float = 1.1    # Culture + nutrients
    electrolyzer_kg: float = 1.0  # Mini electro-winning cell
    pump_kg: float = 1.5        # Micro pump + tubing
    electronics_kg: float = 2.0  # ESP32 + radio + solar panel
    copper_seed_kg: float = 0.1  # Tape for first deposition
    gasket_structure_kg: float = 1.2
    initial_current_a: float = 100  # Tiny solar-powered cell
    first_rock_m: float = 2.0

    @property
    def total_kg(self):
        return (self.membrane_kg + self.concentrator_m2 * 0.1 +
                self.bacteria_kg + self.electrolyzer_kg +
                self.pump_kg + self.electronics_kg +
                self.copper_seed_kg + self.gasket_structure_kg)


@dataclass
class GenState:
    """State after processing one generation."""
    step: int
    rock_diameter_m: float
    rock_mass_kg: float
    iron_extracted_kg: float
    nickel_kg: float
    copper_kg: float
    cobalt_kg: float
    pgm_kg: float
    water_kg: float
    shell_built_kg: float
    next_rock_m: float
    concentrator_m2: float
    current_a: float
    dep_rate_kg_day: float
    heat_days: float
    bio_days: float
    form_days: float
    total_days: float
    cumulative_days: float
    container_type: str


def rock_mass(d: float) -> float:
    return (4 / 3) * math.pi * (d / 2) ** 3 * ROCK_DENSITY


def iron_from_rock(d: float) -> float:
    return rock_mass(d) * IRON_FRACTION * EXTRACTION_EFF


def shell_mass_for_rock(rock_d: float) -> float:
    inner_r = (rock_d * CLEARANCE) / 2
    area = 4 * math.pi * inner_r ** 2
    return area * SHELL_THICKNESS_M * IRON_DENSITY


def max_rock_for_iron(iron_kg: float) -> float:
    """What's the biggest rock that iron_kg can contain?"""
    d2 = iron_kg / (math.pi * CLEARANCE ** 2 * SHELL_THICKNESS_M * IRON_DENSITY)
    if d2 <= 0:
        return 0
    return math.sqrt(d2)


def heating_energy(d: float) -> float:
    m = rock_mass(d)
    w = m * WATER_FRACTION
    r = m - w
    return r * ROCK_CP * DELTA_T + w * WATER_CP * DELTA_T


def run_bootstrap(
    seed: SeedPackage | None = None,
    max_steps: int = 10,
    max_rock_m: float = 50,
    shell_fraction: float = 0.65,
    concentrator_fraction: float = 0.20,
    electrolysis_power_fraction: float = 0.30,
) -> List[GenState]:
    """Simulate the garbage-bag bootstrap scaling path.

    Iron allocation per generation:
      shell_fraction       -> next container
      concentrator_fraction -> bigger solar mirrors
      remainder            -> stockpile + electrolysis upgrade
    """
    if seed is None:
        seed = SeedPackage()

    rock_d = seed.first_rock_m
    concentrator_m2 = seed.concentrator_m2
    current_a = seed.initial_current_a
    cumulative_days = 0.0

    generations: List[GenState] = []

    for step in range(max_steps):
        if rock_d > max_rock_m:
            break

        m = rock_mass(rock_d)
        iron = iron_from_rock(rock_d)
        water = m * WATER_FRACTION
        ni = m * NICKEL_FRACTION * EXTRACTION_EFF
        cu = m * COPPER_FRACTION * EXTRACTION_EFF
        co = m * COBALT_FRACTION * EXTRACTION_EFF
        pgm = m * PGM_FRACTION * EXTRACTION_EFF

        # Iron allocation
        iron_for_shell = iron * shell_fraction
        iron_for_conc = iron * concentrator_fraction

        # Size the next rock based on available iron
        next_rock_d = max_rock_for_iron(iron_for_shell)
        actual_shell = shell_mass_for_rock(next_rock_d)

        # Heating
        e = heating_energy(rock_d)
        heat_w = concentrator_m2 * SOLAR_FLUX_NET
        heat_days = (e / heat_w) / 86400 if heat_w > 0 else 99999

        # Deposition
        dep_rate = current_a * DEPOSITION_KG_PER_AMP_DAY
        form_days = actual_shell / dep_rate if dep_rate > 0 else 99999

        total = heat_days + BIO_DAYS + form_days
        cumulative_days += total

        container = "Kapton membrane" if step == 0 else "Iron sphere"

        gen = GenState(
            step=step,
            rock_diameter_m=rock_d,
            rock_mass_kg=m,
            iron_extracted_kg=iron,
            nickel_kg=ni,
            copper_kg=cu,
            cobalt_kg=co,
            pgm_kg=pgm,
            water_kg=water,
            shell_built_kg=actual_shell,
            next_rock_m=next_rock_d,
            concentrator_m2=concentrator_m2,
            current_a=current_a,
            dep_rate_kg_day=dep_rate,
            heat_days=heat_days,
            bio_days=BIO_DAYS,
            form_days=form_days,
            total_days=total,
            cumulative_days=cumulative_days,
            container_type=container,
        )
        generations.append(gen)

        # Upgrade concentrators
        new_conc = iron_for_conc / CONC_FOIL_KG_PER_M2
        concentrator_m2 += new_conc

        # Upgrade current (proportional to concentrator power)
        available_w = concentrator_m2 * SOLAR_FLUX_NET * electrolysis_power_fraction
        current_a = min(available_w / CELL_VOLTAGE, MAX_CURRENT_A)

        rock_d = next_rock_d

    return generations


def format_report(generations: List[GenState], seed: SeedPackage | None = None) -> str:
    if seed is None:
        seed = SeedPackage()

    lines = []
    lines.append("=" * 100)
    lines.append("  GARBAGE BAG BOOTSTRAP -- FROM 11 KG TO SPACE STATION")
    lines.append("=" * 100)
    lines.append(f"  Seed package: {seed.total_kg:.1f} kg | First rock: {seed.first_rock_m:.1f}m")
    lines.append(f"  Initial concentrator: {seed.concentrator_m2} m2 | Initial current: {seed.initial_current_a} A")
    lines.append("")

    # Manifest
    lines.append("  SEED MANIFEST:")
    lines.append(f"    Kapton membrane (wraps {seed.first_rock_m:.0f}m rock): {seed.membrane_kg:.1f} kg")
    lines.append(f"    Mylar concentrator ({seed.concentrator_m2} m2):     {seed.concentrator_m2 * 0.1 + 0.2:.1f} kg")
    lines.append(f"    Bacteria + nutrients:            {seed.bacteria_kg:.1f} kg")
    lines.append(f"    Mini electro-winning cell:       {seed.electrolyzer_kg:.1f} kg")
    lines.append(f"    Micro pump + tubing:             {seed.pump_kg:.1f} kg")
    lines.append(f"    ESP32 + radio + solar panel:     {seed.electronics_kg:.1f} kg")
    lines.append(f"    Copper seed tape:                {seed.copper_seed_kg:.1f} kg")
    lines.append(f"    Gaskets + structure:             {seed.gasket_structure_kg:.1f} kg")
    lines.append(f"    TOTAL:                          {seed.total_kg:.1f} kg")
    lines.append("")

    # Table header
    hdr = (f"{'Gen':>3} | {'Rock':>5} | {'Mass':>7} | {'Iron':>7} | {'Conc':>7} | "
           f"{'Amps':>6} | {'kg/day':>7} | {'Heat':>6} | {'Bio':>4} | {'Form':>6} | "
           f"{'Step':>6} | {'Cumul':>6} | {'Next':>5} | {'Container':<15}")
    lines.append("--- GENERATION-BY-GENERATION GROWTH ---")
    lines.append(hdr)
    lines.append("-" * 115)

    total_iron = 0
    total_ni = 0
    total_cu = 0
    total_co = 0
    total_pgm = 0
    total_water = 0

    for g in generations:
        total_iron += g.iron_extracted_kg
        total_ni += g.nickel_kg
        total_cu += g.copper_kg
        total_co += g.cobalt_kg
        total_pgm += g.pgm_kg
        total_water += g.water_kg

        rock_str = f"{g.rock_diameter_m:.1f}m"
        mass_str = f"{g.rock_mass_kg / 1000:.1f} t" if g.rock_mass_kg >= 1000 else f"{g.rock_mass_kg:.0f}kg"

        lines.append(
            f"{g.step:>3} | {rock_str:>5} | {mass_str:>7} | "
            f"{g.iron_extracted_kg:>5.0f}kg | {g.concentrator_m2:>5.0f}m2 | "
            f"{g.current_a:>5.0f}A | {g.dep_rate_kg_day:>5.0f}kg/d | "
            f"{g.heat_days:>4.0f} d | {g.bio_days:>2.0f} d | {g.form_days:>4.0f} d | "
            f"{g.total_days / 365.25:>4.1f}yr | {g.cumulative_days / 365.25:>4.1f}yr | "
            f"{g.next_rock_m:>4.1f}m | {g.container_type:<15}"
        )

    lines.append("")

    # Final state
    last = generations[-1]
    lines.append("=" * 100)
    lines.append("  FINAL STATE")
    lines.append("=" * 100)
    lines.append(f"  Generations completed:  {len(generations)}")
    lines.append(f"  Time elapsed:           {last.cumulative_days / 365.25:.1f} years")
    lines.append(f"  Current rock scale:     {last.rock_diameter_m:.1f}m ({last.rock_mass_kg / 1000:.1f} t)")
    lines.append(f"  Next rock capacity:     {last.next_rock_m:.1f}m")
    lines.append(f"  Concentrator array:     {last.concentrator_m2 + last.iron_extracted_kg * 0.20 / CONC_FOIL_KG_PER_M2:.0f} m2")
    lines.append(f"  Deposition current:     {last.current_a:.0f} A ({last.dep_rate_kg_day:.0f} kg/day)")
    lines.append("")
    lines.append("  CUMULATIVE EXTRACTION:")
    lines.append(f"    Iron:    {total_iron / 1000:.1f} tonnes")
    lines.append(f"    Nickel:  {total_ni:.0f} kg")
    lines.append(f"    Copper:  {total_cu:.0f} kg")
    lines.append(f"    Cobalt:  {total_co:.0f} kg")
    lines.append(f"    PGMs:    {total_pgm:.2f} kg")
    lines.append(f"    Water:   {total_water / 1000:.1f} tonnes")
    lines.append("")

    # Growth multiplier
    if len(generations) >= 2:
        first_mass = generations[0].rock_mass_kg
        last_mass = last.rock_mass_kg
        multiplier = last_mass / seed.total_kg
        lines.append(f"  GROWTH: {seed.total_kg:.0f} kg seed -> {last_mass / 1000:.0f} t processed = {multiplier:,.0f}x mass multiplier")
    lines.append("")

    # The punchline
    lines.append("  From a garbage bag to a space station.")
    lines.append("  The membrane is used once. Everything after is iron.")
    lines.append("=" * 100)

    return "\n".join(lines)
