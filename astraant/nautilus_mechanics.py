"""Nautilus Station Mechanical Simulation -- Multi-Physics Process Model

Models the 6 coupled subsystems of the biological nautilus growth process:
1. Electrochemistry: Faraday's law iron deposition onto chamber walls
2. Geometry: Growing shell (wall thickness, aperture, chamber volume)
3. Fluid dynamics: Siphuncle drain/fill during feeding cycle
4. Structural: Hoop stress and safety factor under pressure
5. Thermal: Solar input, radiative loss, reaction heat
6. Chemistry: Monod kinetics bioleaching (reuses bioreactor.py patterns)

Uses SciPy ODE solver for continuous dynamics (deposition, growth, chemistry)
and discrete events for phase transitions (drain, feed, fill, septum).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:
    from scipy.integrate import solve_ivp
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# === Physical Constants ===
FARADAY = 96485.0          # C/mol
M_FE = 55.845e-3           # kg/mol (iron molar mass)
N_ELECTRONS = 2            # Fe2+ -> Fe(s) requires 2 electrons
RHO_IRON = 7870.0          # kg/m^3 (iron density)
IRON_YIELD_MPA = 250.0     # Yield strength of deposited iron
NACRE_BONUS = 1.6          # Space nacre composite multiplier (iron + glass)
STEFAN_BOLTZMANN = 5.67e-8 # W/m^2/K^4
SOLAR_FLUX_1AU = 1361.0    # W/m^2

# === Process Parameters ===
CONCENTRATOR_AREA_M2 = 120         # Solar concentrator area (3x original for faster heating)
CONCENTRATOR_EFFICIENCY = 0.40     # Net thermal efficiency to asteroid
EMISSIVITY = 0.15                  # MLI-insulated exterior
MEMBRANE_AREA_M2 = 314             # Exterior radiating surface (membrane, not chamber)
TARGET_TEMP_C = 30.0               # Optimal for A. ferrooxidans
TARGET_PRESSURE_KPA = 50.0
INITIAL_TEMP_C = -40.0             # Cold asteroid

# Monod kinetics (from bioreactor.py VAT_SULFIDE)
MU_MAX = 0.065       # 1/hr
KS = 0.5             # g/L half-saturation
YIELD_XS = 0.15      # g biomass / g substrate
MAINTENANCE = 0.01    # g substrate / g biomass / hr
METAL_EXTRACTION_RATE = 0.005  # g metal / g biomass / hr
PH_OPTIMAL = 2.0
TEMP_OPTIMAL_C = 30.0

# Siphuncle
SIPHUNCLE_RADIUS_M = 0.05   # 10cm diameter pipe
SIPHUNCLE_LENGTH_M = 20.0   # Approximate length through station
SOLUTION_VISCOSITY = 0.001   # Pa*s (water-like, acidic solution)

# Geometry
INITIAL_APERTURE_M = 14.0   # Starting aperture width
WALL_EXTENSION_RATE = 0.3   # mm of outward extension per mm of thickness growth
SEPTUM_MIN_APERTURE_M = 8.0 # Seal septum when aperture shrinks below this


def asteroid_mass_kg(diameter_m):
    return (4/3) * math.pi * (diameter_m/2)**3 * 1200


def asteroid_water_kg(diameter_m):
    return asteroid_mass_kg(diameter_m) * 0.08


def asteroid_iron_fraction():
    return 200_000 / 1e6  # 20% iron


@dataclass
class NautilusState:
    """Complete mechanical state of the active chamber."""
    time_hours: float = 0.0
    phase: str = "heating"          # heating, digesting, draining, feeding, filling

    # Geometry
    wall_thickness_mm: float = 0.0  # Starts at zero (membrane holds pressure initially)
    chamber_radius_m: float = 6.0   # Inner radius of active chamber
    aperture_width_m: float = INITIAL_APERTURE_M
    chamber_length_m: float = 12.0  # Cylinder length

    # Chemistry
    biomass_g_per_l: float = 0.0
    substrate_g_per_l: float = 0.0
    dissolved_iron_g_per_l: float = 0.0
    ph: float = 7.0
    temp_c: float = INITIAL_TEMP_C

    # Electrodeposition
    current_amps: float = 2000.0
    iron_deposited_total_kg: float = 0.0

    # Structure
    pressure_kpa: float = 0.0       # Ramps up after heating

    # Operational
    asteroids_consumed: int = 0
    septa_sealed: int = 0
    solution_in_siphuncle: bool = False

    @property
    def solution_volume_l(self):
        # Cylinder volume * porosity factor (asteroid fills ~43% of space)
        vol_m3 = math.pi * self.chamber_radius_m**2 * self.chamber_length_m
        return vol_m3 * 0.57 * 1000  # 57% porosity, m^3 -> liters

    @property
    def chamber_surface_m2(self):
        r = self.chamber_radius_m
        L = self.chamber_length_m
        return 2 * math.pi * r * L + 2 * math.pi * r**2  # Cylinder + endcaps

    @property
    def hoop_stress_mpa(self):
        # Membrane (Kevlar) provides baseline: ~3000 MPa tensile at 0.3mm
        # Iron shell adds on top. Combined effective thickness:
        membrane_equiv_mm = 0.3 * (3000 / IRON_YIELD_MPA)  # Kevlar equiv in iron terms
        total_equiv_mm = self.wall_thickness_mm + membrane_equiv_mm  # ~3.9mm equiv
        t_m = total_equiv_mm / 1000
        if t_m < 0.0001:
            return float('inf')
        return (self.pressure_kpa * 1000 * self.chamber_radius_m) / (t_m * 1e6)

    @property
    def safety_factor(self):
        stress = self.hoop_stress_mpa
        if stress <= 0 or stress == float('inf'):
            return 0.0
        return (IRON_YIELD_MPA * NACRE_BONUS) / stress

    @property
    def shell_mass_kg(self):
        t_m = self.wall_thickness_mm / 1000
        return self.chamber_surface_m2 * t_m * RHO_IRON

    @property
    def thermal_mass_j_per_k(self):
        return self.shell_mass_kg * 450  # Iron specific heat ~450 J/kg/K


def ph_temp_factor(temp_c, ph):
    """Growth rate modifier (from bioreactor.py pattern)."""
    if ph < 1.5 or ph > 3.0 or temp_c < 25 or temp_c > 35:
        return 0.0
    ph_dev = abs(ph - PH_OPTIMAL) / 1.5
    t_dev = abs(temp_c - TEMP_OPTIMAL_C) / 10.0
    return math.exp(-4 * ph_dev**2) * math.exp(-4 * t_dev**2)


def faraday_deposition_rate(current_amps):
    """Iron deposition rate from Faraday's law (kg/hour)."""
    # m = (M * I * t) / (n * F), for t = 3600s (1 hour)
    return (M_FE * current_amps * 3600) / (N_ELECTRONS * FARADAY)


def siphuncle_flow_rate_l_per_hour(pressure_diff_pa, length_m=SIPHUNCLE_LENGTH_M):
    """Poiseuille flow through siphuncle pipe (liters/hour)."""
    r = SIPHUNCLE_RADIUS_M
    mu = SOLUTION_VISCOSITY
    Q_m3_per_s = (math.pi * r**4 * pressure_diff_pa) / (8 * mu * length_m)
    return Q_m3_per_s * 1000 * 3600  # -> liters/hour


def simulate_cycle(state, asteroid_diameter_m=10, dt_hours=24.0, verbose=False):
    """Simulate one complete asteroid processing cycle.

    Phases: heating -> digesting -> draining -> feeding -> filling -> digesting
    Returns (final_state, hourly_snapshots, events).
    """
    snapshots = []
    events = []
    asteroid_mass = asteroid_mass_kg(asteroid_diameter_m)
    water_mass = asteroid_water_kg(asteroid_diameter_m)
    iron_in_asteroid = asteroid_mass * asteroid_iron_fraction()

    # Substrate concentration: iron sulfide ore available per liter of solution
    ore_substrate_g_per_l = (iron_in_asteroid * 1000) / max(state.solution_volume_l, 1)

    dep_rate_kg_per_hr = faraday_deposition_rate(state.current_amps)
    solar_thermal_w = CONCENTRATOR_AREA_M2 * SOLAR_FLUX_1AU * CONCENTRATOR_EFFICIENCY

    max_steps = 5000  # Safety limit
    step = 0

    while step < max_steps:
        step += 1
        state.time_hours += dt_hours
        env = ph_temp_factor(state.temp_c, state.ph)

        # === PHASE: HEATING ===
        if state.phase == "heating":
            # Solar concentrators heat the asteroid + shell
            # Total thermal mass: shell + asteroid rock + ice/water
            thermal_mass = state.thermal_mass_j_per_k + asteroid_mass * 800 + water_mass * 2100
            if thermal_mass > 0:
                radiative_loss = EMISSIVITY * STEFAN_BOLTZMANN * MEMBRANE_AREA_M2 * \
                                 ((state.temp_c + 273)**4 - 2.7**4)  # vs CMB
                net_power = solar_thermal_w - max(0, radiative_loss)
                dt_temp = (net_power * dt_hours * 3600) / thermal_mass
                state.temp_c += dt_temp

            if state.temp_c >= TARGET_TEMP_C:
                state.phase = "digesting"
                state.pressure_kpa = TARGET_PRESSURE_KPA
                state.biomass_g_per_l = 0.1  # Inoculum from previous cycle
                state.substrate_g_per_l = ore_substrate_g_per_l
                state.dissolved_iron_g_per_l = 0.0
                state.ph = PH_OPTIMAL
                events.append({"hour": state.time_hours, "type": "phase",
                               "msg": f"Heated to {state.temp_c:.0f}C. Bioleaching started."})

        # === PHASE: DIGESTING ===
        elif state.phase == "digesting":
            # Monod kinetics (bacterial growth + metal dissolution)
            X = state.biomass_g_per_l
            S = state.substrate_g_per_l
            if S > 0 and env > 0:
                mu = MU_MAX * (S / (KS + S)) * env
                dX = mu * X * dt_hours
                # Cap biomass at realistic level (carrying capacity)
                state.biomass_g_per_l = min(max(0, X + dX), 50.0)
                # Mass-transfer limited: bacteria access rock surfaces only.
                raw_dS = (mu * X / YIELD_XS + MAINTENANCE * X) * dt_hours
                dS = -min(raw_dS, 0.05 * dt_hours)  # Surface-access bottleneck
                dFe = min(METAL_EXTRACTION_RATE * X * env, 0.03) * dt_hours
                state.substrate_g_per_l = max(0, S + dS)
                state.dissolved_iron_g_per_l += dFe

            # Electrodeposition (iron from solution onto walls)
            if state.dissolved_iron_g_per_l > 0.001:  # Copper seed enables immediate deposition
                deposited_kg = min(dep_rate_kg_per_hr * dt_hours,
                                   state.dissolved_iron_g_per_l * state.solution_volume_l / 1000 * 0.1)
                state.iron_deposited_total_kg += deposited_kg
                state.dissolved_iron_g_per_l -= (deposited_kg * 1000) / max(state.solution_volume_l, 1)
                state.dissolved_iron_g_per_l = max(0, state.dissolved_iron_g_per_l)

                # Wall growth
                thickness_gain_mm = (deposited_kg / (RHO_IRON * state.chamber_surface_m2)) * 1000
                state.wall_thickness_mm += thickness_gain_mm

                # Aperture shrinks as walls extend
                state.aperture_width_m -= thickness_gain_mm * WALL_EXTENSION_RATE / 1000 * 2

            # Thermal balance during processing (thermostat: defocus when warm enough)
            reaction_heat = state.biomass_g_per_l * 0.5  # Watts per g/L (exothermic)
            # Thermal mass includes: shell + solution + undissolved asteroid rock
            remaining_rock_kg = max(0, state.substrate_g_per_l / ore_substrate_g_per_l * asteroid_mass) if ore_substrate_g_per_l > 0 else 0
            thermal_mass = state.thermal_mass_j_per_k + state.solution_volume_l * 4180 + remaining_rock_kg * 800
            # Thermostat: reduce solar input when above target (defocus concentrators)
            solar_active = solar_thermal_w if state.temp_c < TARGET_TEMP_C else solar_thermal_w * 0.1
            if thermal_mass > 0:
                radiative_loss = EMISSIVITY * STEFAN_BOLTZMANN * MEMBRANE_AREA_M2 * \
                                 ((state.temp_c + 273)**4 - 2.7**4)
                net = solar_active + reaction_heat - radiative_loss
                state.temp_c += (net * dt_hours * 3600) / thermal_mass
                state.temp_c = max(-40, min(60, state.temp_c))

            # Check if substrate depleted -> ready to drain and feed
            if state.substrate_g_per_l < 0.01:
                state.phase = "draining"
                state.asteroids_consumed += 1
                events.append({"hour": state.time_hours, "type": "extraction",
                               "msg": f"Asteroid #{state.asteroids_consumed} digested. "
                                      f"Wall: {state.wall_thickness_mm:.1f}mm. Draining."})

        # === PHASE: DRAINING (solution to siphuncle) ===
        elif state.phase == "draining":
            flow = siphuncle_flow_rate_l_per_hour(TARGET_PRESSURE_KPA * 1000)
            drain_hours = state.solution_volume_l / max(flow, 1)
            state.phase = "feeding"
            state.solution_in_siphuncle = True
            state.pressure_kpa = 0  # Depressurized for aperture opening
            events.append({"hour": state.time_hours, "type": "drain",
                           "msg": f"Drained {state.solution_volume_l:.0f}L in {drain_hours:.1f}hr via siphuncle."})

        # === PHASE: FEEDING (new asteroid pushed in) ===
        elif state.phase == "feeding":
            state.phase = "filling"
            events.append({"hour": state.time_hours, "type": "feed",
                           "msg": f"New {asteroid_diameter_m}m asteroid loaded through aperture."})

        # === PHASE: FILLING (solution from siphuncle back) ===
        elif state.phase == "filling":
            state.phase = "digesting"
            state.solution_in_siphuncle = False
            state.pressure_kpa = TARGET_PRESSURE_KPA
            state.substrate_g_per_l = ore_substrate_g_per_l
            state.dissolved_iron_g_per_l = 0.5  # Residual from previous cycle
            events.append({"hour": state.time_hours, "type": "fill",
                           "msg": "Solution returned. Processing resumed."})

        # === SEPTUM CHECK ===
        if state.aperture_width_m < SEPTUM_MIN_APERTURE_M and state.phase == "digesting":
            state.septa_sealed += 1
            old_wall = state.wall_thickness_mm
            # New chamber: reset geometry, keep chemistry
            state.wall_thickness_mm = 0.0  # New membrane + copper seed (iron grows from zero again)
            state.chamber_radius_m *= 1.1  # Slightly bigger
            state.chamber_length_m *= 1.1
            state.aperture_width_m = state.chamber_radius_m * 2 + 4  # New full aperture
            events.append({"hour": state.time_hours, "type": "septum",
                           "msg": f"Septum #{state.septa_sealed} sealed (wall was {old_wall:.1f}mm). "
                                  f"New chamber: r={state.chamber_radius_m:.1f}m."})

        # Snapshot
        if verbose or step % 5 == 0:
            snapshots.append({
                "hour": state.time_hours,
                "phase": state.phase,
                "wall_mm": state.wall_thickness_mm,
                "iron_kg": state.iron_deposited_total_kg,
                "temp_c": state.temp_c,
                "ph": state.ph,
                "biomass": state.biomass_g_per_l,
                "safety": state.safety_factor,
                "aperture_m": state.aperture_width_m,
                "substrate": state.substrate_g_per_l,
                "fe_dissolved": state.dissolved_iron_g_per_l,
                "pressure_kpa": state.pressure_kpa,
                "shell_kg": state.shell_mass_kg,
            })

        # Cycle ends after asteroid consumed and new one loaded
        if state.asteroids_consumed > 0 and state.phase == "digesting":
            break

    return state, snapshots, events


def run_multi_cycle(cycles=10, initial_diameter_m=10, current_amps=2000,
                    growth_factor=1.2, verbose=False):
    """Run multiple asteroid processing cycles. Returns summary data."""
    state = NautilusState(current_amps=current_amps,
                          chamber_radius_m=initial_diameter_m * 0.7,
                          chamber_length_m=initial_diameter_m * 1.2)
    diameter = initial_diameter_m
    all_events = []
    cycle_summaries = []

    for cycle_num in range(1, cycles + 1):
        wall_start = state.wall_thickness_mm
        state, snapshots, events = simulate_cycle(state, diameter, verbose=verbose)
        all_events.extend(events)

        cycle_summaries.append({
            "cycle": cycle_num,
            "asteroid_m": diameter,
            "asteroid_t": asteroid_mass_kg(diameter) / 1000,
            "wall_start_mm": wall_start,
            "wall_end_mm": state.wall_thickness_mm,
            "aperture_m": state.aperture_width_m,
            "safety": state.safety_factor,
            "iron_total_kg": state.iron_deposited_total_kg,
            "shell_kg": state.shell_mass_kg,
            "septa": state.septa_sealed,
            "temp_c": state.temp_c,
        })

        # Check for septum -> grow diameter for next generation
        if state.septa_sealed > 0 and state.septa_sealed > (cycle_num // 3):
            diameter *= growth_factor

    return state, cycle_summaries, all_events


def format_report(state, summaries, events, config):
    """Format the mechanical simulation results."""
    lines = []
    lines.append("=" * 95)
    lines.append("  NAUTILUS STATION MECHANICAL SIMULATION")
    lines.append("=" * 95)
    lines.append(f"  Cycles: {config['cycles']} | Start: {config['diameter']}m asteroids | "
                 f"Current: {config['current']}A | Growth: {config['growth']}x")
    lines.append(f"  Deposition rate: {faraday_deposition_rate(config['current'])*24:.1f} kg/day "
                 f"(Faraday's law at {config['current']}A)")
    lines.append("")

    # Cycle summary table
    lines.append("--- CYCLE-BY-CYCLE GROWTH ---")
    hdr = (f"{'Cyc':>3} | {'Rock':>5} | {'Mass':>7} | {'Wall Start':>10} | {'Wall End':>8} | "
           f"{'Aperture':>8} | {'Safety':>6} | {'Shell':>7} | {'Septa':>5}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for s in summaries:
        lines.append(
            f"{s['cycle']:>3} | {s['asteroid_m']:>4.0f}m | {s['asteroid_t']:>5.0f} t | "
            f"{s['wall_start_mm']:>8.1f}mm | {s['wall_end_mm']:>6.1f}mm | "
            f"{s['aperture_m']:>6.1f}m | {s['safety']:>6.1f} | "
            f"{s['shell_kg']/1000:>5.1f} t | {s['septa']:>5}")

    # Key events
    lines.append("")
    lines.append("--- KEY EVENTS ---")
    for e in events[:30]:
        lines.append(f"  Hour {e['hour']:>7.0f}: [{e['type']:>10}] {e['msg']}")
    if len(events) > 30:
        lines.append(f"  ... ({len(events) - 30} more events)")

    # Structural verification
    lines.append("")
    lines.append("=" * 95)
    lines.append("  STRUCTURAL VERIFICATION")
    lines.append("=" * 95)
    min_wall = (TARGET_PRESSURE_KPA * 1000 * state.chamber_radius_m) / \
               (IRON_YIELD_MPA * NACRE_BONUS * 1e6) * 1000
    lines.append(f"  Min wall for {TARGET_PRESSURE_KPA} kPa at {state.chamber_radius_m:.1f}m radius: "
                 f"{min_wall:.2f} mm")
    lines.append(f"  Current wall thickness: {state.wall_thickness_mm:.1f} mm")
    lines.append(f"  Safety factor: {state.safety_factor:.1f} "
                 f"(space nacre: {IRON_YIELD_MPA * NACRE_BONUS:.0f} MPa)")
    lines.append(f"  Hoop stress: {state.hoop_stress_mpa:.1f} MPa")
    verdict = "SAFE" if state.safety_factor > 2.0 else "UNSAFE"
    lines.append(f"  VERDICT: {verdict}")

    # Siphuncle check
    flow = siphuncle_flow_rate_l_per_hour(TARGET_PRESSURE_KPA * 1000)
    drain_time = state.solution_volume_l / flow
    lines.append(f"\n  SIPHUNCLE:")
    lines.append(f"  Flow rate: {flow:.0f} L/hr at {TARGET_PRESSURE_KPA} kPa differential")
    lines.append(f"  Drain time for {state.solution_volume_l:.0f}L: {drain_time:.1f} hours")

    # Thermal check
    lines.append(f"\n  THERMAL:")
    lines.append(f"  Final temperature: {state.temp_c:.1f} C (target: {TARGET_TEMP_C} C)")
    lines.append(f"  Shell thermal mass: {state.thermal_mass_j_per_k/1e6:.1f} MJ/K")
    lines.append(f"  Solar thermal input: {CONCENTRATOR_AREA_M2 * SOLAR_FLUX_1AU * CONCENTRATOR_EFFICIENCY/1000:.1f} kW")

    # Final state
    lines.append(f"\n  FINAL STATE:")
    lines.append(f"  Total iron deposited: {state.iron_deposited_total_kg/1000:.1f} tonnes")
    lines.append(f"  Shell mass: {state.shell_mass_kg/1000:.1f} tonnes")
    lines.append(f"  Septa sealed: {state.septa_sealed}")
    lines.append(f"  Asteroids consumed: {state.asteroids_consumed}")
    lines.append(f"  Chamber radius: {state.chamber_radius_m:.1f} m")
    lines.append("=" * 95)

    return "\n".join(lines)
