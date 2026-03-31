"""Garbage Bag Bootstrap Simulator.

Models growth from a minimal seed package to a nautilus station.
Three modes reflecting different levels of capability:

  Mode A ("bag-only"): Passive chemistry. No mechanical construction.
    - Bag inflates by bioleaching gas pressure + electrodeposition
    - Power fixed at initial PV panel (136W). No fabrication.
    - Slow (~8 years to 5m) but requires zero mechanical capability.

  Mode B ("bag + arm"): Small robotic arm for construction.
    - Can deposit plates, bend thin iron, spot-weld with the cell
    - Can aim/position concentrator mirrors (power scales up)
    - Moderate (~3 years to 10m). Adds ~3 kg to package.

  Mode C ("cubesat seed"): Full CubeSat with propulsion + arm.
    - The existing 51 kg design. Full mechanical capability.
    - Fast (~1 year to 10m). Reference baseline.

Key honest constraints:
  - No robots = no fabrication (can't build turbines or pumps)
  - Power is FIXED unless you can aim new concentrators (needs arm)
  - Moving rocks requires propulsion (can't fetch anything passively)
  - The pump and electronics fail after 5-15 years (needs resupply)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

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

CONC_FOIL_KG_PER_M2 = 0.39   # 0.05mm iron foil reflectors

# Faraday's law: ~1.04 g Fe per amp-hour at 2V
DEPOSITION_KG_PER_AMP_DAY = 0.02496
BIO_DAYS = 90                 # Bioleaching time per rock (mass-transfer limited)
CELL_VOLTAGE = 2.0            # V per electro-winning cell
PV_EFFICIENCY = 0.20          # Thin-film solar panel
IRON_ELONGATION = 0.15        # 15% ductile elongation before fracture
WALL_DEPOSIT_MM = 0.5         # Iron deposited on walls per cycle


@dataclass
class SeedPackage:
    """The initial package launched from Earth."""
    membrane_kg: float = 3.8       # Kapton for 2m rock
    concentrator_m2: float = 0.5   # Mylar reflector (thermal only)
    pv_panel_m2: float = 0.5       # Thin-film PV (electrical)
    bacteria_kg: float = 1.1       # Culture + nutrients
    electrolyzer_kg: float = 1.0   # Electro-winning cell
    pump_kg: float = 1.5           # Peristaltic micro pump + tubing
    electronics_kg: float = 0.5    # ESP32 + radio + spectral sensor
    solar_panel_kg: float = 0.8    # 0.5 m2 thin-film (1.5 kg/m2)
    copper_seed_kg: float = 0.1    # Tape for first deposition
    bladder_kg: float = 0.2        # Collapsible fluid bladder
    gasket_structure_kg: float = 1.0
    # Mode B additions (zero if bag-only)
    arm_kg: float = 0.0            # Robotic arm (Mode B: 3 kg)
    propulsion_kg: float = 0.0     # Cold-gas thrusters (Mode C only)
    first_rock_m: float = 2.0

    @property
    def total_kg(self):
        return (self.membrane_kg + self.concentrator_m2 * 0.1 +
                self.bacteria_kg + self.electrolyzer_kg +
                self.pump_kg + self.electronics_kg +
                self.solar_panel_kg + self.copper_seed_kg +
                self.bladder_kg + self.gasket_structure_kg +
                self.arm_kg + self.propulsion_kg)

    @property
    def pv_watts(self):
        return self.pv_panel_m2 * 1361 * PV_EFFICIENCY

    @property
    def initial_current_a(self):
        return self.pv_watts / CELL_VOLTAGE


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
    wall_deposit_kg: float
    next_rock_m: float
    concentrator_m2: float
    current_a: float
    dep_rate_kg_day: float
    heat_days: float
    bio_days: float
    form_days: float
    total_days: float
    cumulative_days: float
    growth_method: str


def rock_mass(d: float) -> float:
    return (4 / 3) * math.pi * (d / 2) ** 3 * ROCK_DENSITY


def iron_from_rock(d: float) -> float:
    return rock_mass(d) * IRON_FRACTION * EXTRACTION_EFF


def heating_energy(d: float) -> float:
    m = rock_mass(d)
    w = m * WATER_FRACTION
    r = m - w
    return r * ROCK_CP * DELTA_T + w * WATER_CP * DELTA_T


def run_bootstrap(
    mode: str = "A",
    seed: SeedPackage | None = None,
    max_steps: int = 15,
    max_rock_m: float = 12,
) -> List[GenState]:
    """Simulate bootstrap growth.

    mode:
      "A" = bag-only (passive inflation, fixed power)
      "B" = bag + arm (can build concentrators, weld shells)
      "C" = cubesat seed (full capability, reference baseline)
    """
    if seed is None:
        seed = SeedPackage()
        if mode == "B":
            seed.arm_kg = 3.0
        elif mode == "C":
            seed.arm_kg = 3.0
            seed.propulsion_kg = 5.0
            seed.concentrator_m2 = 2.0
            seed.pv_panel_m2 = 2.0
            seed.solar_panel_kg = 3.0
            seed.membrane_kg = 8.0
            seed.first_rock_m = 5.0

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

        # --- Heating ---
        e = heating_energy(rock_d)
        heat_w = concentrator_m2 * SOLAR_FLUX_NET
        heat_days = (e / heat_w) / 86400 if heat_w > 0 else 99999

        # --- Deposition rate ---
        dep_rate = current_a * DEPOSITION_KG_PER_AMP_DAY

        # --- Wall reinforcement (deposit iron on bag interior) ---
        bag_r = rock_d * 0.7  # bag ~1.4x rock dia
        bag_area = 4 * math.pi * bag_r ** 2
        wall_iron = bag_area * (WALL_DEPOSIT_MM / 1000) * IRON_DENSITY
        dep_days = wall_iron / dep_rate if dep_rate > 0 else 99999

        # --- Growth method depends on mode ---
        if mode == "A":
            # Passive inflation: gas pressure expands iron-lined bag 15%
            next_rock_d = rock_d * (1 + IRON_ELONGATION)
            form_days = dep_days  # just deposition time, no construction
            growth_method = "Inflation"
            # Power is FIXED -- can't build or aim new concentrators
            # Concentrator stays the same forever
        elif mode == "B":
            # Arm can build iron-foil concentrators and aim them
            # Arm can deposit plates, bend, spot-weld into sphere
            iron_for_conc = iron * 0.20
            iron_for_shell = iron * 0.65
            # Shell: bend + weld plates
            shell_thickness = 0.0015  # 1.5mm
            clearance = 1.4
            max_d2 = iron_for_shell / (
                math.pi * clearance ** 2 * shell_thickness * IRON_DENSITY)
            next_rock_d = math.sqrt(max_d2) if max_d2 > 0 else rock_d
            inner_r = (next_rock_d * clearance) / 2
            shell_area = 4 * math.pi * inner_r ** 2
            shell_mass = shell_area * shell_thickness * IRON_DENSITY
            plate_dep_days = shell_mass / dep_rate if dep_rate > 0 else 99999
            # Welding: arm does it, 1 seam per 2 hours
            weld_days = shell_area * 0.1  # faster with arm than manual
            form_days = plate_dep_days + weld_days
            growth_method = "Welded shell"
            # Upgrade concentrators
            concentrator_m2 += iron_for_conc / CONC_FOIL_KG_PER_M2
            # Upgrade current (arm can build bigger electrode arrays)
            thermal_w = concentrator_m2 * SOLAR_FLUX_NET
            # With arm: can build a simple thermoelectric or Stirling generator
            # Stirling from iron: ~5% efficient, not 10% turbine
            electrical_w = thermal_w * 0.05
            current_a = min(electrical_w / CELL_VOLTAGE, 50000)
        else:  # mode C
            # Full capability (existing cubesat seed model)
            iron_for_conc = iron * 0.20
            iron_for_shell = iron * 0.65
            shell_thickness = 0.0015
            clearance = 1.4
            max_d2 = iron_for_shell / (
                math.pi * clearance ** 2 * shell_thickness * IRON_DENSITY)
            next_rock_d = math.sqrt(max_d2) if max_d2 > 0 else rock_d
            inner_r = (next_rock_d * clearance) / 2
            shell_area = 4 * math.pi * inner_r ** 2
            shell_mass = shell_area * shell_thickness * IRON_DENSITY
            plate_dep_days = shell_mass / dep_rate if dep_rate > 0 else 99999
            n_welders = max(1, min(step * 4, 20))
            weld_days = (shell_area * 0.1) / n_welders
            form_days = plate_dep_days + weld_days
            growth_method = "Welded shell"
            concentrator_m2 += iron_for_conc / CONC_FOIL_KG_PER_M2
            thermal_w = concentrator_m2 * SOLAR_FLUX_NET
            electrical_w = thermal_w * 0.10  # Stirling/turbine
            current_a = min(electrical_w / CELL_VOLTAGE, 50000)

        total = heat_days + BIO_DAYS + form_days
        cumulative_days += total

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
            wall_deposit_kg=wall_iron,
            next_rock_m=next_rock_d,
            concentrator_m2=concentrator_m2,
            current_a=current_a,
            dep_rate_kg_day=dep_rate,
            heat_days=heat_days,
            bio_days=BIO_DAYS,
            form_days=form_days,
            total_days=total,
            cumulative_days=cumulative_days,
            growth_method=growth_method,
        )
        generations.append(gen)

        rock_d = next_rock_d

    return generations


def format_report(generations: List[GenState], seed: SeedPackage | None = None,
                  mode: str = "A") -> str:
    if seed is None:
        seed = SeedPackage()

    mode_names = {"A": "Bag-Only (passive inflation)",
                  "B": "Bag + Arm (can build + aim)",
                  "C": "CubeSat Seed (full capability)"}

    lines = []
    lines.append("=" * 100)
    lines.append(f"  BOOTSTRAP MODE {mode}: {mode_names.get(mode, mode)}")
    lines.append("=" * 100)
    lines.append(f"  Package mass: {seed.total_kg:.1f} kg | First rock: {seed.first_rock_m:.1f}m")
    lines.append(f"  PV panel: {seed.pv_panel_m2} m2 = {seed.pv_watts:.0f}W | "
                 f"Initial current: {seed.initial_current_a:.0f}A")
    if mode == "A":
        lines.append("  Power: FIXED (no fabrication capability)")
        lines.append("  Growth: inflation (gas pressure + ductile iron)")
        lines.append("  Cannot: build turbines, pumps, concentrators, or move rocks")
    elif mode == "B":
        lines.append("  Robotic arm: 2-DOF, SG90 servos, can bend/weld thin iron")
        lines.append("  Growth: welded iron shells + iron-foil concentrators")
        lines.append("  Cannot: build complex machinery (but can build Stirling engine)")
    lines.append("")

    # Table
    hdr = (f"{'Gen':>3} | {'Rock':>5} | {'Mass':>7} | {'Iron':>7} | {'Conc':>7} | "
           f"{'Amps':>6} | {'kg/day':>6} | {'Heat':>6} | {'Bio':>4} | {'Build':>6} | "
           f"{'Step':>6} | {'Cumul':>7} | {'Next':>5} | {'Method':<12}")
    lines.append(hdr)
    lines.append("-" * 110)

    total_iron = 0
    total_water = 0
    total_pgm = 0

    for g in generations:
        total_iron += g.iron_extracted_kg
        total_water += g.water_kg
        total_pgm += g.pgm_kg

        rock_str = f"{g.rock_diameter_m:.1f}m"
        mass_str = f"{g.rock_mass_kg / 1000:.1f} t" if g.rock_mass_kg >= 1000 else f"{g.rock_mass_kg:.0f}kg"

        lines.append(
            f"{g.step:>3} | {rock_str:>5} | {mass_str:>7} | "
            f"{g.iron_extracted_kg:>5.0f}kg | {g.concentrator_m2:>5.0f}m2 | "
            f"{g.current_a:>5.0f}A | {g.dep_rate_kg_day:>4.0f}kg | "
            f"{g.heat_days:>4.0f} d | {g.bio_days:>2.0f} d | {g.form_days:>4.0f} d | "
            f"{g.total_days / 365.25:>4.1f}yr | {g.cumulative_days / 365.25:>5.1f}yr | "
            f"{g.next_rock_m:>4.1f}m | {g.growth_method:<12}"
        )

    lines.append("")
    last = generations[-1]
    lines.append(f"  RESULT: {last.rock_diameter_m:.1f}m in {last.cumulative_days / 365.25:.1f} years | "
                 f"{total_iron / 1000:.1f}t iron | {total_pgm:.1f} kg PGMs | "
                 f"{total_water / 1000:.1f}t water")
    lines.append("=" * 100)

    return "\n".join(lines)
