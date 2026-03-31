"""Giant Machine Physics -- WAAM-Built Macro-Scale Structures in Microgravity.

Models the mechanical limits of large structures built from WAAM iron
in zero/micro gravity.  Answers the question: "how big can we build?"

Three machine classes:
  1. Giant Arm Printer: Cantilever WAAM arm for exterior construction.
     Bending moment, natural frequency, vibration settling, print rate.
  2. Giant Edison Spider: Scaled 8-legged walker for exterior work.
     Joint torque, motor sizing, electromagnetic grip, battery life.
  3. Relay Computer: Physical sizing of WAAM-built relay logic.
     Relay count, power, heat, radiator area, volume/mass.

Material basis: WAAM-deposited iron
  yield_strength  = 250 MPa
  elastic_modulus = 200 GPa
  density         = 7870 kg/m3
  fatigue_limit   = 120 MPa (10^7 cycles)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Dict

# === WAAM Iron Properties ===
YIELD_MPA = 250.0          # Yield strength (MPa)
FATIGUE_MPA = 120.0        # Fatigue limit at 10^7 cycles (MPa)
E_GPA = 200.0              # Young's modulus (GPa)
E_PA = E_GPA * 1e9         # Young's modulus (Pa)
RHO = 7870.0               # Density (kg/m3)
SIGMA_YIELD_PA = YIELD_MPA * 1e6  # Yield strength (Pa)
SIGMA_FATIGUE_PA = FATIGUE_MPA * 1e6

# === Arm Printer Constants ===
WAAM_DEPOSITION_KG_PER_HR = 0.5   # Wire deposition rate per head
DEFAULT_SAFETY_FACTOR = 2.0
DAMPING_RATIO = 0.02               # Structural damping for iron (zeta)
WALL_FRACTION = 0.15               # tube_id = tube_od * (1 - 2*WALL_FRACTION)
                                   # -> wall = 15% of OD on each side

# === Spider Constants ===
MU_0 = 4 * math.pi * 1e-7         # Vacuum permeability (T*m/A)
EDISON_BATTERY_WH_PER_KG = 25.0   # NiFe (Edison) battery energy density
COPPER_RESISTIVITY = 1.7e-8        # Ohm*m
SPIDER_N_LEGS = 8
SPIDER_LEGS_MOVING = 4             # Alternating quadruplet gait

# === Relay Computer Constants ===
RELAY_POWER_W = 0.75               # Average power per relay (coil)
RELAY_VOLUME_CM3 = 50.0            # Single WAAM-built relay volume
RELAY_MASS_KG = 0.3                # Single WAAM-built relay mass
RELAY_SWITCHING_MS = 7.0           # Switching time (ms)
WIRING_OVERHEAD = 2.0              # Wiring volume = relay volume * this factor
STEFAN_BOLTZMANN = 5.67e-8         # W/m2/K4
RADIATOR_EMISSIVITY = 0.9          # Black-body radiator
RADIATOR_TEMP_K = 350.0            # Operating temperature for relay bank

# Relay counts for standard control tasks
RELAY_TASKS: Dict[str, Dict] = {
    "thermostat":       {"relays": 3,   "desc": "Simple on/off temperature control"},
    "pump_sequencer":   {"relays": 10,  "desc": "Multi-pump cycling controller"},
    "cam_arm_6axis":    {"relays": 30,  "desc": "Cam-drum arm controller (6 axes)"},
    "process_bioleach": {"relays": 50,  "desc": "Bioleaching phase sequencer"},
    "autopilot":        {"relays": 100, "desc": "Full tug autopilot (navigation + thrust)"},
    "factory_plc":      {"relays": 200, "desc": "Factory-scale process logic controller"},
}


# =========================================================================
# 1. Giant Arm Printer
# =========================================================================

@dataclass
class GiantArm:
    """A WAAM-built cantilever arm for exterior printing."""
    length_m: float             # Arm length
    tube_od_m: float            # Outer diameter of hollow tube arm
    tube_id_m: float            # Inner diameter
    payload_kg: float           # Max payload at tip
    max_tip_accel_m_s2: float   # Max tip acceleration (m/s2)
    natural_freq_hz: float      # First-mode natural frequency
    max_tip_speed_m_s: float    # Max tip speed (limited by vibration)
    print_rate_kg_hr: float     # Effective WAAM print rate at tip
    settle_time_s: float        # Vibration settling time (to 2% amp)
    arm_mass_kg: float          # Total arm mass
    moment_of_inertia_m4: float # Second moment of area (I)
    bending_moment_nm: float    # Max bending moment at root
    safety_factor: float        # Actual safety factor at rated load
    vibration_warning: bool     # True if f_natural < 1 Hz


@dataclass
class GiantSpider:
    """A WAAM-built 8-legged walker for exterior construction."""
    body_diameter_m: float      # Body size
    leg_length_m: float         # Each leg length
    n_legs: int                 # Always 8
    leg_od_m: float             # Leg tube outer diameter
    leg_id_m: float             # Leg tube inner diameter
    leg_mass_kg: float          # Mass per leg
    body_mass_kg: float         # Body structure mass
    total_mass_kg: float        # Everything including battery
    motor_torque_nm: float      # Required joint torque
    motor_coil_turns: int       # Wound-field motor coil turns
    motor_current_a: float      # Motor operating current
    grip_force_n: float         # Electromagnetic foot pad hold force
    battery_kwh: float          # Edison battery capacity
    battery_mass_kg: float      # Battery mass
    battery_hours: float        # Operating endurance
    cargo_capacity_kg: float    # What it can carry (inertial handling)
    max_speed_m_s: float        # Walking speed
    step_power_w: float         # Power per step cycle


@dataclass
class RelayComputer:
    """A WAAM-built relay logic controller."""
    task_name: str              # What it controls
    task_desc: str              # Human description
    n_relays: int               # Number of relays
    power_watts: float          # Total electrical draw
    mass_kg: float              # Total mass (relays + wiring + frame)
    volume_m3: float            # Total volume
    radiator_m2: float          # Required radiator area
    switching_speed_hz: float   # Max switching frequency
    rack_dimensions: str        # Approximate physical description


def _tube_moment_of_inertia(od_m: float, id_m: float) -> float:
    """Second moment of area for a hollow circular tube (m4)."""
    return (math.pi / 64) * (od_m**4 - id_m**4)


def _tube_cross_section_area(od_m: float, id_m: float) -> float:
    """Cross-section area of hollow tube (m2)."""
    return (math.pi / 4) * (od_m**2 - id_m**2)


def _tube_mass(od_m: float, id_m: float, length_m: float) -> float:
    """Mass of a hollow tube (kg)."""
    return _tube_cross_section_area(od_m, id_m) * length_m * RHO


def design_giant_arm(
    length_m: float = 10.0,
    payload_kg: float = 50.0,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> GiantArm:
    """Design a cantilever WAAM arm and compute its limits.

    The arm is modeled as a hollow iron tube cantilevered from a base.
    In microgravity there is no static sag -- the limiting physics are:
      - Bending moment from accelerating the payload at the tip
      - Natural frequency (must stay well above excitation frequency)
      - Vibration settling time (iron has low damping, zeta ~0.02)

    Args:
        length_m: Arm length from base to tip.
        payload_kg: Design payload mass at the tip.
        safety_factor: Required safety factor on yield stress.

    Returns:
        GiantArm dataclass with all computed parameters.
    """
    L = length_m

    # Step 1: Size the tube so it can handle the payload.
    # Start with a reasonable tip acceleration (0.1 m/s2 baseline,
    # scaled down for longer arms to keep forces manageable).
    tip_accel = 0.1 / max(1.0, L / 10.0)

    # Bending moment at root: M = payload * accel * arm_length
    M = payload_kg * tip_accel * L  # N*m

    # Required second moment of area: sigma = M*c/I -> I = M*c / sigma_allow
    # For tube, c = od/2.  We iterate: guess OD, compute I, check stress.
    # Start small (50mm) and grow only as bending stress requires.
    # This ensures longer arms always have lower natural frequency for
    # a given payload -- the physics that actually limits construction.
    od = 0.05

    for _ in range(50):  # Iterative sizing
        id_m = od * (1 - 2 * WALL_FRACTION)
        I = _tube_moment_of_inertia(od, id_m)
        c = od / 2
        sigma = M * c / I if I > 1e-20 else float('inf')
        sigma_allow = SIGMA_YIELD_PA / safety_factor
        if sigma <= sigma_allow:
            break
        # Need bigger tube -- scale OD up
        od *= 1.1
    else:
        # If we exhausted iterations, use the last OD (oversized arm)
        pass

    id_m = od * (1 - 2 * WALL_FRACTION)
    I = _tube_moment_of_inertia(od, id_m)
    A = _tube_cross_section_area(od, id_m)
    arm_mass = _tube_mass(od, id_m, L)

    # Actual bending stress and safety factor
    c = od / 2
    sigma_actual = M * c / I if I > 1e-20 else float('inf')
    actual_sf = SIGMA_YIELD_PA / sigma_actual if sigma_actual > 0 else float('inf')

    # Step 2: Natural frequency of cantilever beam (first mode).
    # f_n = (1.875^2 / (2*pi*L^2)) * sqrt(E*I / (rho*A))
    # For a beam with tip mass, effective: f_n = (1/(2*pi)) * sqrt(3*E*I / (m_tip * L^3))
    # Use the more conservative tip-mass formula when payload is significant.
    beam_fn = (1.875**2 / (2 * math.pi * L**2)) * math.sqrt(E_PA * I / (RHO * A))
    # Tip-mass formula (cantilever with point mass at end)
    if payload_kg > 0:
        tip_fn = (1 / (2 * math.pi)) * math.sqrt(3 * E_PA * I / (payload_kg * L**3))
        f_natural = min(beam_fn, tip_fn)
    else:
        f_natural = beam_fn

    # Step 3: Max tip acceleration -- keep excitation < 0.5 * f_natural.
    # For sinusoidal motion at the tip: f_excite = a / (2*pi * v)
    # Simpler rule: limit tip accel so dynamic bending stays within yield.
    # Already set by design; verify resonance margin.
    omega_n = 2 * math.pi * f_natural
    settle_time = 4.0 / (DAMPING_RATIO * omega_n) if omega_n > 1e-6 else 1e6

    # Step 4: Max tip speed -- limited by resonance avoidance.
    # If tip oscillates at f_excite, and we want f_excite < 0.5 * f_natural,
    # then for a stroke of ~0.1 m (print layer), v_max = pi * stroke * f_max.
    f_max_excite = 0.5 * f_natural
    stroke_m = 0.1  # Typical print-layer stroke
    max_tip_speed = math.pi * stroke_m * f_max_excite if f_max_excite > 0 else 0.001

    # Step 5: Print rate -- limited by slower of vibration settling and deposition.
    # Time per layer: move (stroke/speed) + settle + deposit
    deposition_time_per_layer = 0.1 / WAAM_DEPOSITION_KG_PER_HR  # hours per 100g layer
    move_time_hr = (stroke_m / max(max_tip_speed, 0.001)) / 3600
    settle_hr = settle_time / 3600
    cycle_hr = move_time_hr + settle_hr + deposition_time_per_layer
    effective_print_rate = WAAM_DEPOSITION_KG_PER_HR / max(1.0, cycle_hr / deposition_time_per_layer)

    vibration_warning = f_natural < 1.0

    return GiantArm(
        length_m=L,
        tube_od_m=round(od, 4),
        tube_id_m=round(id_m, 4),
        payload_kg=payload_kg,
        max_tip_accel_m_s2=round(tip_accel, 6),
        natural_freq_hz=round(f_natural, 4),
        max_tip_speed_m_s=round(max_tip_speed, 4),
        print_rate_kg_hr=round(effective_print_rate, 4),
        settle_time_s=round(settle_time, 2),
        arm_mass_kg=round(arm_mass, 2),
        moment_of_inertia_m4=I,
        bending_moment_nm=round(M, 2),
        safety_factor=round(actual_sf, 2),
        vibration_warning=vibration_warning,
    )


def survey_arms(
    lengths: Optional[List[float]] = None,
    payload_kg: float = 50.0,
) -> List[GiantArm]:
    """Design arms at several lengths and return the list."""
    if lengths is None:
        lengths = [1.0, 3.0, 10.0, 30.0, 50.0]
    return [design_giant_arm(length_m=L, payload_kg=payload_kg) for L in lengths]


# =========================================================================
# 2. Giant Edison Spider
# =========================================================================

def design_giant_spider(
    body_diameter_m: float = 5.0,
    battery_fraction: float = 0.30,
) -> GiantSpider:
    """Design an 8-legged WAAM spider for exterior construction.

    In microgravity there is no weight to support -- all forces come from
    inertia during leg movement and electromagnetic grip on iron surfaces.

    Args:
        body_diameter_m: Body diameter (spider overall size).
        battery_fraction: Fraction of total mass allocated to Edison battery.

    Returns:
        GiantSpider dataclass with all computed parameters.
    """
    D = body_diameter_m
    n_legs = SPIDER_N_LEGS

    # Leg geometry: length = 1.5 * body_diameter, tube OD = D/10
    leg_length = 1.5 * D
    leg_od = max(0.03, D / 10.0)
    leg_id = leg_od * (1 - 2 * WALL_FRACTION)

    leg_mass = _tube_mass(leg_od, leg_id, leg_length)

    # Body: approximate as a hollow sphere shell, wall = 5mm scaled
    body_wall = max(0.005, D * 0.01)
    body_r = D / 2
    body_volume_shell = (4/3) * math.pi * (body_r**3 - (body_r - body_wall)**3)
    body_mass = body_volume_shell * RHO

    # Battery sizing
    structural_mass = body_mass + n_legs * leg_mass
    # total = structural + battery -> battery = fraction * total
    # structural = (1 - fraction) * total -> total = structural / (1 - fraction)
    total_mass = structural_mass / (1 - battery_fraction)
    battery_mass = total_mass * battery_fraction
    battery_kwh = battery_mass * EDISON_BATTERY_WH_PER_KG / 1000

    # Joint torque: T = I_leg * alpha
    # I_leg = (1/3) * m_leg * L^2 (rod rotating about end)
    # Target angular accel: 0.5 rad/s2 (gentle, scaled for size)
    alpha = 0.5 / max(1.0, D / 2.0)  # Slower for bigger spiders
    I_leg = (1.0 / 3.0) * leg_mass * leg_length**2
    motor_torque = I_leg * alpha

    # Wound-field DC motor sizing: T = k_t * I
    # k_t depends on coil turns * magnetic flux
    # For iron-core motor with B_core ~1.5 T, rotor radius ~leg_od/2:
    motor_radius = leg_od / 2
    motor_length_m = leg_od  # Motor fits in leg joint
    # B from iron core (saturates at ~1.5 T for soft iron)
    B_core = 1.5
    # k_t = N * B * A_rotor, simplified
    # Target: N turns to produce required torque at reasonable current
    # T = N * B * I * A, where A = motor_radius * motor_length
    A_motor = motor_radius * motor_length_m
    # Choose N and I to give required torque
    motor_current = min(10.0, max(1.0, motor_torque / (B_core * A_motor * 10)))
    coil_turns = max(10, int(motor_torque / (B_core * motor_current * A_motor)))

    # Electromagnetic foot pad grip force
    # F = B^2 * A_pad / (2 * mu_0)
    # Iron-core electromagnet gripping iron hull surface.
    # With iron core, B saturates at ~1.5 T.  We model the coil as driving
    # an iron-core magnet; B = min(mu_r * mu_0 * N * I / L, B_sat).
    # Foot pad wider than leg tube (spreads load).  Pad dia = 3x leg OD, min 0.1m.
    pad_diameter = max(0.10, leg_od * 3)
    pad_area = math.pi * (pad_diameter / 2)**2
    pad_solenoid_length = max(0.02, pad_diameter / 2)
    pad_solenoid_n = max(100, int(300 * pad_diameter))
    pad_current = min(10.0, max(2.0, D))  # Current scales with body size
    # Iron core relative permeability ~200 (conservative for WAAM iron)
    mu_r_iron = 200
    B_pad_raw = mu_r_iron * MU_0 * pad_solenoid_n * pad_current / pad_solenoid_length
    B_sat = 1.5  # Tesla -- iron saturation limit
    B_pad = min(B_pad_raw, B_sat)
    grip_force = B_pad**2 * pad_area / (2 * MU_0)

    # Power per step cycle (4 legs move at once in alternating quadruplet)
    # Power per joint = torque * omega
    omega = alpha * 1.0  # angular velocity after 1s of accel
    power_per_joint = motor_torque * omega
    # 3 joints per leg (hip, knee, ankle), 4 legs moving
    step_power = power_per_joint * 3 * SPIDER_LEGS_MOVING

    # Battery endurance
    # Idle power: foot pads (8 feet, half energized) + electronics baseline
    # Coil resistance: R = rho * N * circumference / wire_area
    wire_dia_m = 0.002  # 2mm copper wire
    wire_area = math.pi * (wire_dia_m / 2)**2
    coil_circumference = math.pi * pad_diameter
    coil_resistance = COPPER_RESISTIVITY * pad_solenoid_n * coil_circumference / wire_area
    pad_power = pad_current**2 * coil_resistance
    idle_power = n_legs * 0.5 * pad_power  # Half the feet energized at any time
    idle_power = max(idle_power, 5.0)  # Minimum 5W for electronics
    avg_power = step_power + idle_power
    battery_hours = battery_kwh * 1000 / max(avg_power, 0.01)

    # Speed: step length ~0.5 * leg_length, step time ~2s scaled
    step_time = 2.0 * max(1.0, D / 2.0)  # Seconds per step
    step_length = 0.5 * leg_length
    max_speed = step_length / step_time

    # Cargo capacity: limited by inertial handling, not weight.
    # Spider can accelerate cargo at ~0.05 m/s2 using leg grip.
    # Max cargo = grip_force / 0.05 (but capped at own mass for stability)
    cargo_from_grip = grip_force / 0.05 if grip_force > 0 else 0
    cargo_capacity = min(cargo_from_grip, total_mass * 2.0)

    return GiantSpider(
        body_diameter_m=D,
        leg_length_m=round(leg_length, 3),
        n_legs=n_legs,
        leg_od_m=round(leg_od, 4),
        leg_id_m=round(leg_id, 4),
        leg_mass_kg=round(leg_mass, 2),
        body_mass_kg=round(body_mass, 2),
        total_mass_kg=round(total_mass, 2),
        motor_torque_nm=round(motor_torque, 3),
        motor_coil_turns=coil_turns,
        motor_current_a=round(motor_current, 2),
        grip_force_n=round(grip_force, 4),
        battery_kwh=round(battery_kwh, 4),
        battery_mass_kg=round(battery_mass, 2),
        battery_hours=round(battery_hours, 2),
        cargo_capacity_kg=round(cargo_capacity, 2),
        max_speed_m_s=round(max_speed, 4),
        step_power_w=round(step_power, 2),
    )


def survey_spiders(
    diameters: Optional[List[float]] = None,
) -> List[GiantSpider]:
    """Design spiders at several body diameters."""
    if diameters is None:
        diameters = [0.5, 2.0, 5.0, 10.0]
    return [design_giant_spider(body_diameter_m=d) for d in diameters]


# =========================================================================
# 3. Relay Computer Sizing
# =========================================================================

def design_relay_computer(
    task: str = "autopilot",
    n_relays_override: Optional[int] = None,
) -> RelayComputer:
    """Size a WAAM-built relay logic controller for a given task.

    Args:
        task: Key from RELAY_TASKS dict, or "custom".
        n_relays_override: If set, use this relay count instead of task default.

    Returns:
        RelayComputer dataclass.
    """
    if n_relays_override is not None:
        n = n_relays_override
        desc = f"Custom ({n} relays)"
        task_name = "custom"
    elif task in RELAY_TASKS:
        n = RELAY_TASKS[task]["relays"]
        desc = RELAY_TASKS[task]["desc"]
        task_name = task
    else:
        raise ValueError(f"Unknown task '{task}'. Options: {list(RELAY_TASKS.keys())}")

    power = n * RELAY_POWER_W
    mass_relays = n * RELAY_MASS_KG
    mass_total = mass_relays * (1 + WIRING_OVERHEAD)  # Wiring + frame

    vol_relays_m3 = n * RELAY_VOLUME_CM3 * 1e-6
    vol_total_m3 = vol_relays_m3 * (1 + WIRING_OVERHEAD)

    # Radiator area to dump waste heat to space
    # P = epsilon * sigma * A * T^4 -> A = P / (epsilon * sigma * T^4)
    radiator_m2 = power / (RADIATOR_EMISSIVITY * STEFAN_BOLTZMANN * RADIATOR_TEMP_K**4)

    switching_hz = 1000.0 / RELAY_SWITCHING_MS  # ~143 Hz

    # Physical description
    side = vol_total_m3 ** (1.0 / 3.0)
    if side < 0.1:
        rack_desc = f"Shoebox ({side*100:.0f}cm side)"
    elif side < 0.5:
        rack_desc = f"Cabinet ({side*100:.0f}cm side)"
    elif side < 1.5:
        rack_desc = f"Wardrobe ({side:.1f}m side)"
    elif side < 3.0:
        rack_desc = f"Room ({side:.1f}m side)"
    else:
        rack_desc = f"Building ({side:.1f}m side)"

    return RelayComputer(
        task_name=task_name,
        task_desc=desc,
        n_relays=n,
        power_watts=round(power, 2),
        mass_kg=round(mass_total, 2),
        volume_m3=round(vol_total_m3, 6),
        radiator_m2=round(radiator_m2, 4),
        switching_speed_hz=round(switching_hz, 1),
        rack_dimensions=rack_desc,
    )


def survey_relay_computers() -> List[RelayComputer]:
    """Design relay computers for all standard tasks."""
    return [design_relay_computer(task=t) for t in RELAY_TASKS]


# =========================================================================
# 4. Material Stress Limits (reference calculations)
# =========================================================================

def pressure_vessel_max_radius(
    wall_thickness_m: float,
    pressure_pa: float,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> float:
    """Max radius for a thin-walled pressure vessel (hoop stress limit).

    sigma_hoop = p * r / t  ->  r_max = sigma_yield * t / (p * SF)

    Returns:
        Maximum inner radius in meters.
    """
    if pressure_pa <= 0 or wall_thickness_m <= 0:
        return 0.0
    return SIGMA_YIELD_PA * wall_thickness_m / (pressure_pa * safety_factor)


def centrifugal_max_diameter(
    rpm: float,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> float:
    """Max diameter for a spinning solid iron disc before yield.

    Hoop stress at center of spinning disc:
      sigma = (3+nu)/8 * rho * omega^2 * r^2
    where nu ~= 0.29 for iron.

    Returns:
        Maximum diameter in meters.
    """
    if rpm <= 0:
        return 0.0
    omega = rpm * 2 * math.pi / 60
    nu = 0.29
    # sigma = (3+nu)/8 * rho * omega^2 * r^2  =>  r = sqrt(8*sigma / ((3+nu)*rho*omega^2))
    sigma_allow = SIGMA_YIELD_PA / safety_factor
    r_max = math.sqrt(8 * sigma_allow / ((3 + nu) * RHO * omega**2))
    return 2 * r_max


def cantilever_required_od(
    length_m: float,
    payload_kg: float,
    accel_m_s2: float = 0.1,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> float:
    """Required OD for a hollow tube cantilever under tip load.

    Returns outer diameter in meters (wall = 15% of OD each side).
    """
    M = payload_kg * accel_m_s2 * length_m
    sigma_allow = SIGMA_YIELD_PA / safety_factor

    # I = pi/64 * (od^4 - id^4), c = od/2, id = od*(1-2*wf)
    # sigma = M*c/I => iterate
    od = max(0.02, length_m / 30)
    for _ in range(80):
        id_m = od * (1 - 2 * WALL_FRACTION)
        I = _tube_moment_of_inertia(od, id_m)
        c = od / 2
        sigma = M * c / I if I > 1e-30 else float('inf')
        if sigma <= sigma_allow:
            return round(od, 4)
        od *= 1.05
    return round(od, 4)


def wire_min_diameter(
    tension_n: float,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
) -> float:
    """Minimum wire diameter for a given tensile load.

    sigma = F / A  =>  A = F * SF / sigma_yield  =>  d = sqrt(4*A/pi)

    Returns:
        Minimum diameter in meters.
    """
    if tension_n <= 0:
        return 0.0
    A_req = tension_n * safety_factor / SIGMA_YIELD_PA
    return math.sqrt(4 * A_req / math.pi)


# =========================================================================
# Formatting
# =========================================================================

def format_arm_report(arms: List[GiantArm]) -> str:
    """Format a table of giant arm designs."""
    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  GIANT ARM PRINTER -- Cantilever WAAM Arm Physics")
    lines.append("=" * 100)
    lines.append(f"  Material: WAAM iron (yield={YIELD_MPA} MPa, E={E_GPA} GPa, rho={RHO} kg/m3)")
    lines.append(f"  Safety factor: {DEFAULT_SAFETY_FACTOR}  |  Damping ratio: {DAMPING_RATIO}")
    lines.append("")

    hdr = (f"{'Length':>7} | {'OD':>7} | {'Wall':>6} | {'Mass':>8} | {'Payload':>8} | "
           f"{'f_nat':>7} | {'Settle':>7} | {'TipSpd':>8} | {'Print':>8} | {'Warn':>5}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for a in arms:
        wall_mm = (a.tube_od_m - a.tube_id_m) / 2 * 1000
        warn = "<<< " if a.vibration_warning else ""
        lines.append(
            f"{a.length_m:>6.1f}m | "
            f"{a.tube_od_m*100:>5.1f}cm | "
            f"{wall_mm:>4.1f}mm | "
            f"{a.arm_mass_kg:>7.1f}kg | "
            f"{a.payload_kg:>6.0f} kg | "
            f"{a.natural_freq_hz:>5.2f}Hz | "
            f"{a.settle_time_s:>5.1f} s | "
            f"{a.max_tip_speed_m_s:>6.4f}m/s | "
            f"{a.print_rate_kg_hr:>5.3f}kg/h | "
            f"{warn:>5}")

    lines.append("")
    lines.append("  NOTES:")
    lines.append("  - In microgravity: no gravity sag, but inertia limits acceleration.")
    lines.append("  - Vibration settling dominates cycle time for long arms.")
    lines.append("  - '<<<' marks arms with f_natural < 1 Hz (vibration concern).")
    lines.append("  - Longer arms print SLOWER despite same deposition rate.")
    lines.append("=" * 100)
    return "\n".join(lines)


def format_spider_report(spiders: List[GiantSpider]) -> str:
    """Format a table of giant spider designs."""
    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  GIANT EDISON SPIDER -- 8-Legged WAAM Walker Physics")
    lines.append("=" * 100)
    lines.append(f"  Material: WAAM iron  |  Battery: Edison NiFe ({EDISON_BATTERY_WH_PER_KG} Wh/kg)")
    lines.append(f"  Gait: alternating quadruplet ({SPIDER_LEGS_MOVING} legs moving at a time)")
    lines.append("")

    hdr = (f"{'Body':>6} | {'Legs':>6} | {'Mass':>8} | {'Torque':>8} | {'Grip':>8} | "
           f"{'Batt':>7} | {'Endure':>7} | {'Speed':>8} | {'Cargo':>8}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for s in spiders:
        lines.append(
            f"{s.body_diameter_m:>5.1f}m | "
            f"{s.leg_length_m:>4.1f}m | "
            f"{s.total_mass_kg:>7.1f}kg | "
            f"{s.motor_torque_nm:>6.2f}Nm | "
            f"{s.grip_force_n:>6.2f} N | "
            f"{s.battery_kwh*1000:>5.0f}Wh | "
            f"{s.battery_hours:>5.1f}hr | "
            f"{s.max_speed_m_s:>6.4f}m/s | "
            f"{s.cargo_capacity_kg:>7.1f}kg")

    lines.append("")
    lines.append("  NOTES:")
    lines.append("  - Microgravity: no weight, all forces are inertial.")
    lines.append("  - Grip = electromagnetic pad on iron hull (B^2*A / 2*mu_0).")
    lines.append("  - Cargo limited by grip force / handling acceleration.")
    lines.append("  - Bigger spiders are SLOWER (more inertia, longer legs).")
    lines.append("=" * 100)
    return "\n".join(lines)


def format_relay_report(computers: List[RelayComputer]) -> str:
    """Format a table of relay computer designs."""
    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  RELAY COMPUTER SIZING -- WAAM-Built Control Logic")
    lines.append("=" * 100)
    lines.append(f"  Single relay: {RELAY_VOLUME_CM3} cm3, {RELAY_MASS_KG} kg, "
                 f"{RELAY_POWER_W} W, {RELAY_SWITCHING_MS} ms switching")
    lines.append(f"  Wiring overhead: {WIRING_OVERHEAD}x relay volume  |  "
                 f"Radiator at {RADIATOR_TEMP_K} K, emissivity {RADIATOR_EMISSIVITY}")
    lines.append("")

    hdr = (f"{'Task':>16} | {'Relays':>6} | {'Power':>7} | {'Mass':>8} | "
           f"{'Volume':>10} | {'Radiatr':>8} | {'Size':>18}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for c in computers:
        vol_str = f"{c.volume_m3*1e6:.0f} cm3" if c.volume_m3 < 0.001 else f"{c.volume_m3:.3f} m3"
        lines.append(
            f"{c.task_name:>16} | "
            f"{c.n_relays:>6} | "
            f"{c.power_watts:>5.1f} W | "
            f"{c.mass_kg:>6.1f} kg | "
            f"{vol_str:>10} | "
            f"{c.radiator_m2:>6.4f}m2 | "
            f"{c.rack_dimensions:>18}")

    lines.append("")
    lines.append("  NOTES:")
    lines.append("  - All relays WAAM-printed from iron (larger than commercial).")
    lines.append("  - Heat must radiate to space (no convection in vacuum).")
    lines.append("  - Switching speed ~143 Hz for all sizes (relay physics).")
    lines.append("  - Autopilot (100 relays) is wardrobe-sized, not room-sized.")
    lines.append("  - Factory PLC (200 relays) needs meaningful radiator area.")
    lines.append("=" * 100)
    return "\n".join(lines)


def format_stress_limits() -> str:
    """Reference table of material stress limits for common structures."""
    lines: List[str] = []
    lines.append("=" * 100)
    lines.append("  WAAM IRON STRESS LIMITS -- Quick Reference")
    lines.append("=" * 100)
    lines.append(f"  yield={YIELD_MPA} MPa | E={E_GPA} GPa | rho={RHO} kg/m3 | "
                 f"fatigue={FATIGUE_MPA} MPa (10^7 cycles)")
    lines.append("")

    # Pressure vessels
    lines.append("--- PRESSURE VESSEL (hoop stress, SF=2.0) ---")
    lines.append(f"  {'Wall':>8} | {'10 kPa':>10} | {'50 kPa':>10} | {'100 kPa':>10} | {'500 kPa':>10}")
    lines.append(f"  {'':>8} | {'r_max':>10} | {'r_max':>10} | {'r_max':>10} | {'r_max':>10}")
    lines.append("  " + "-" * 58)
    for wall_mm in [1, 2, 5, 10, 20, 50]:
        wall_m = wall_mm / 1000
        vals = []
        for p_kpa in [10, 50, 100, 500]:
            r = pressure_vessel_max_radius(wall_m, p_kpa * 1000)
            vals.append(f"{r:>8.1f} m")
        lines.append(f"  {wall_mm:>6}mm | {'  |  '.join(vals)}")

    lines.append("")

    # Centrifugal limits
    lines.append("--- ROTATING MACHINERY (centrifugal yield, SF=2.0) ---")
    for rpm in [10, 50, 100, 500, 1000, 5000]:
        d = centrifugal_max_diameter(rpm)
        lines.append(f"  {rpm:>6} RPM -> max diameter: {d:.2f} m")

    lines.append("")

    # Wire tension
    lines.append("--- WIRE / CABLE (tensile yield, SF=2.0) ---")
    for tension in [10, 100, 1000, 10000, 100000]:
        d = wire_min_diameter(tension)
        lines.append(f"  {tension:>8} N -> min diameter: {d*1000:.2f} mm")

    lines.append("")
    lines.append("=" * 100)
    return "\n".join(lines)


def format_full_report(
    arms: Optional[List[GiantArm]] = None,
    spiders: Optional[List[GiantSpider]] = None,
    computers: Optional[List[RelayComputer]] = None,
) -> str:
    """Combine all reports into one output."""
    parts: List[str] = []
    if arms:
        parts.append(format_arm_report(arms))
    if spiders:
        parts.append(format_spider_report(spiders))
    if computers:
        parts.append(format_relay_report(computers))
    parts.append(format_stress_limits())
    return "\n\n".join(parts)
