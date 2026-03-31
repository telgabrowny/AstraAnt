"""WAAM-Built Relay Systems -- Physics Simulation Module.

Models three relay systems for the nautilus station, all constructable via
Wire Arc Additive Manufacturing (WAAM) from asteroid-derived iron and nickel:

  1. Relay Life Support: Bimetallic thermostat + dashpot timer + nickel
     heater keeps bioleaching bacteria alive after ESP32 failure.  Pure
     electromechanical -- no software, no firmware, no radiation-sensitive
     parts.

  2. Edison Battery: Iron-nickel alkaline battery for the retrieval tug.
     Nearly indestructible (10,000+ cycles), fabricable from asteroid iron
     and nickel, low energy density (30 Wh/kg) but doesn't care about
     vacuum, radiation, or temperature extremes.

  3. Retrieval Tug: WAAM-built H2/O2 rocket tug that does asteroid capture
     sorties.  Water electrolysis for propellant, Edison battery for power,
     sun sensor + gyro for navigation.  No microprocessor -- relay sequencer
     fires valves in timed sequence.

Physics references:
  - Bimetallic strip: Timoshenko (1925) beam theory
  - Edison cell: Falk & Salkind, "Alkaline Storage Batteries" (1969)
  - Rocket: Tsiolkovsky (1903), NASA SP-125 for H2/O2 performance
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

# ============================================================================
# Physical constants
# ============================================================================

G0 = 9.80665                  # m/s^2, standard gravity
STEFAN_BOLTZMANN = 5.67e-8    # W/m^2/K^4

# Bimetallic strip materials (iron + copper, WAAM-depositable)
ALPHA_FE = 12.0e-6            # 1/K, CTE of iron
ALPHA_CU = 17.0e-6            # 1/K, CTE of copper
ALPHA_DIFF = ALPHA_CU - ALPHA_FE  # 5e-6 1/K

# Nickel heater wire
RHO_NI = 6.99e-8              # ohm*m, nickel resistivity at ~30C

# Bacteria viability
BACTERIA_TEMP_MIN_C = 20.0
BACTERIA_TEMP_MAX_C = 40.0
BACTERIA_TEMP_OPTIMAL_LOW_C = 28.0
BACTERIA_TEMP_OPTIMAL_HIGH_C = 33.0

# Edison battery chemistry (Fe-Ni)
EDISON_CELL_VOLTAGE_OC = 1.2  # V, open-circuit nominal
EDISON_ENERGY_DENSITY_WH_KG = 30.0
EDISON_CHARGE_EFFICIENCY = 0.65
EDISON_CYCLE_LIFE = 10000
EDISON_R_INT_PER_CELL = 0.01  # ohm

# Rocket propulsion (H2/O2 in vacuum)
ISP_H2O2 = 420.0              # s, specific impulse
V_EXHAUST = ISP_H2O2 * G0     # m/s, exhaust velocity

# Water electrolysis
ELECTROLYSIS_ENERGY_KJ_PER_MOL = 286.0  # kJ/mol H2O
WATER_MOLAR_MASS_KG = 0.018   # kg/mol
H2_MASS_FRACTION = 1.0 / 9.0  # 1 g H2 per 9 g water
O2_MASS_FRACTION = 8.0 / 9.0  # 8 g O2 per 9 g water

# Navigation
SUN_SENSOR_ACCURACY_DEG = 5.0
GYRO_DRIFT_DEG_PER_HR = 0.1


# ============================================================================
# 1. Relay Life Support
# ============================================================================

@dataclass
class LifeSupportState:
    """Snapshot of the relay life support system at a given hour."""
    hour: int = 0
    temp_c: float = 30.0           # Solution temperature
    heater_on: bool = False        # True if thermostat contacts closed
    pump_on: bool = False          # True if dashpot timer has pump running
    bacteria_alive: bool = True    # False if temp exits viable range too long
    bacteria_viability: float = 1.0  # 0.0 = dead, 1.0 = healthy
    heater_duty_cycle: float = 0.0   # Running average (0-1)
    power_watts: float = 0.0        # Instantaneous power draw
    cumulative_energy_wh: float = 0.0


def bimetallic_deflection_mm(delta_t_c: float, strip_length_mm: float = 30.0,
                              strip_thickness_mm: float = 1.0) -> float:
    """Bimetallic strip tip deflection (Timoshenko beam theory).

    delta = (6 * (alpha2 - alpha1) * deltaT * L^2) / t

    where L and t are in consistent units (meters internally).

    Args:
        delta_t_c: Temperature difference from setpoint (positive = warmer).
        strip_length_mm: Free length of the bimetallic strip.
        strip_thickness_mm: Total thickness of the bonded strip.

    Returns:
        Tip deflection in mm (positive = strip curves toward low-CTE side).
    """
    L_m = strip_length_mm / 1000.0
    t_m = strip_thickness_mm / 1000.0
    deflection_m = (6.0 * ALPHA_DIFF * delta_t_c * L_m ** 2) / t_m
    return deflection_m * 1000.0  # -> mm


def nickel_heater_resistance(wire_length_m: float = 2.0,
                              wire_diameter_mm: float = 0.5) -> float:
    """Resistance of a nickel heater wire (ohms).

    R = rho * L / A
    """
    area_m2 = math.pi * (wire_diameter_mm / 2000.0) ** 2
    return RHO_NI * wire_length_m / area_m2


def nickel_heater_power(voltage: float = 12.0, wire_length_m: float = 2.0,
                         wire_diameter_mm: float = 0.5) -> float:
    """Heater power output in watts: P = V^2 / R."""
    R = nickel_heater_resistance(wire_length_m, wire_diameter_mm)
    return voltage ** 2 / R


def dashpot_stroke_time_s(viscosity_pa_s: float = 10.0,
                           piston_length_mm: float = 50.0,
                           piston_area_mm2: float = 200.0,
                           orifice_area_mm2: float = 1.0,
                           delta_p_pa: float = 1000.0) -> float:
    """Time for dashpot piston to complete one stroke.

    t_stroke = (mu * L_piston * A_piston) / (A_orifice * delta_P)

    where mu = dynamic viscosity of the dashpot fluid.

    Args:
        viscosity_pa_s: Dynamic viscosity of dashpot oil.
        piston_length_mm: Piston travel distance.
        piston_area_mm2: Piston cross-section area.
        orifice_area_mm2: Restrictor orifice area (smaller = slower).
        delta_p_pa: Pressure driving the piston (spring force / area).

    Returns:
        Stroke time in seconds.
    """
    L_m = piston_length_mm / 1000.0
    A_piston_m2 = piston_area_mm2 / 1e6
    A_orifice_m2 = orifice_area_mm2 / 1e6
    return (viscosity_pa_s * L_m * A_piston_m2) / (A_orifice_m2 * delta_p_pa)


def simulate_life_support(hours: int = 720,
                           heater_watts: float = 50.0,
                           setpoint_c: float = 30.0,
                           hysteresis_c: float = 2.5,
                           solution_mass_kg: float = 500.0,
                           solution_cp: float = 4180.0,
                           radiation_area_m2: float = 0.5,
                           emissivity: float = 0.15,
                           ambient_temp_c: float = -40.0,
                           contact_gap_mm: float = 0.1,
                           strip_length_mm: float = 80.0,
                           strip_thickness_mm: float = 0.8,
                           pump_on_minutes: float = 10.0,
                           pump_off_minutes: float = 10.0
                           ) -> List[LifeSupportState]:
    """Simulate relay life support hour-by-hour.

    Models bimetallic thermostat bang-bang control of a nickel heater keeping
    bacterial solution at setpoint.  Dashpot timer cycles a circulation pump.

    Thermal model per hour:
      dT = (P_heater - P_radiation) * 3600 / (m * Cp)

    Bacteria viability degrades if temperature exits 20-40C range.

    Args:
        hours: Simulation duration (default 720 = 30 days).
        heater_watts: Nickel heater power output.
        setpoint_c: Thermostat target temperature.
        hysteresis_c: Thermostat deadband (half-width).
        solution_mass_kg: Mass of bacterial solution.
        solution_cp: Specific heat of solution (J/kg/K).
        radiation_area_m2: Exterior radiating surface area.
        emissivity: Surface emissivity for radiative loss.
        ambient_temp_c: Deep space / asteroid background temperature.
        contact_gap_mm: Bimetallic strip must deflect this far to close.
        strip_length_mm: Bimetallic strip free length.
        strip_thickness_mm: Bimetallic strip thickness.
        pump_on_minutes: Dashpot pump ON time per cycle.
        pump_off_minutes: Dashpot pump OFF time per cycle.

    Returns:
        List of LifeSupportState, one per hour.
    """
    thermal_mass = solution_mass_kg * solution_cp  # J/K

    # Thermostat thresholds
    turn_on_temp = setpoint_c - hysteresis_c   # Heater ON below this
    turn_off_temp = setpoint_c + hysteresis_c  # Heater OFF above this

    # Pump cycle timing
    pump_cycle_minutes = pump_on_minutes + pump_off_minutes

    states: List[LifeSupportState] = []
    temp = setpoint_c  # Start at setpoint (system was running before ESP32 died)
    heater_on = False
    bacteria_alive = True
    viability = 1.0
    cum_energy_wh = 0.0
    heater_on_hours = 0

    # Pre-check: can the strip deflect enough at the deadband?
    test_deflection = bimetallic_deflection_mm(
        hysteresis_c, strip_length_mm, strip_thickness_mm)

    for h in range(hours + 1):
        # -- Thermostat logic (bang-bang with hysteresis) --
        # Strip deflection is proportional to (temp - setpoint)
        # When temp drops below turn_on_temp, deflection is negative enough
        # to close the normally-open contact.  When temp rises above
        # turn_off_temp, deflection opens the contact.
        delta_from_setpoint = temp - setpoint_c
        deflection = bimetallic_deflection_mm(
            abs(delta_from_setpoint), strip_length_mm, strip_thickness_mm)

        if not heater_on and temp <= turn_on_temp:
            # Strip deflection from cooling must exceed contact gap
            if deflection >= contact_gap_mm:
                heater_on = True
        elif heater_on and temp >= turn_off_temp:
            if deflection >= contact_gap_mm:
                heater_on = False

        # -- Pump cycle (dashpot timer) --
        cycle_pos_minutes = (h * 60.0) % pump_cycle_minutes
        pump_on = cycle_pos_minutes < pump_on_minutes

        # -- Power --
        p_heater = heater_watts if heater_on else 0.0
        p_pump = 5.0 if pump_on else 0.0  # Small circulation pump ~5 W
        p_total = p_heater + p_pump

        # -- Thermal balance --
        # Radiative loss: P_rad = emissivity * sigma * A * (T^4 - T_amb^4)
        T_k = temp + 273.15
        T_amb_k = ambient_temp_c + 273.15
        p_radiation = emissivity * STEFAN_BOLTZMANN * radiation_area_m2 * (
            T_k ** 4 - T_amb_k ** 4)
        p_radiation = max(0.0, p_radiation)  # Can't gain heat from colder CMB

        if thermal_mass > 0:
            dt_temp = (p_heater - p_radiation) * 3600.0 / thermal_mass
            temp += dt_temp

        # -- Bacteria viability --
        if bacteria_alive:
            if temp < BACTERIA_TEMP_MIN_C or temp > BACTERIA_TEMP_MAX_C:
                # Viability drops 5% per hour outside viable range
                viability -= 0.05
            elif BACTERIA_TEMP_OPTIMAL_LOW_C <= temp <= BACTERIA_TEMP_OPTIMAL_HIGH_C:
                # Slow recovery in optimal range
                viability = min(1.0, viability + 0.01)
            # else: between viable and optimal -- no change
            if viability <= 0.0:
                viability = 0.0
                bacteria_alive = False

        # -- Energy accounting --
        cum_energy_wh += p_total * 1.0  # 1 hour step
        if h > 0 and heater_on:
            heater_on_hours += 1

        duty = heater_on_hours / max(h, 1)

        states.append(LifeSupportState(
            hour=h,
            temp_c=temp,
            heater_on=heater_on,
            pump_on=pump_on,
            bacteria_alive=bacteria_alive,
            bacteria_viability=viability,
            heater_duty_cycle=duty,
            power_watts=p_total,
            cumulative_energy_wh=cum_energy_wh,
        ))

    return states


# ============================================================================
# 2. Edison Battery
# ============================================================================

@dataclass
class EdisonBatteryState:
    """Snapshot of an Edison (Fe-Ni) battery."""
    time_s: float = 0.0
    voltage: float = EDISON_CELL_VOLTAGE_OC
    current_a: float = 0.0
    capacity_remaining_ah: float = 0.0
    capacity_total_ah: float = 0.0
    temperature_c: float = 25.0
    energy_delivered_wh: float = 0.0
    cycles_used: int = 0
    mass_kg: float = 0.0

    @property
    def soc(self) -> float:
        """State of charge (0-1)."""
        if self.capacity_total_ah <= 0:
            return 0.0
        return max(0.0, min(1.0, self.capacity_remaining_ah / self.capacity_total_ah))


def design_edison_battery(energy_wh: float, cells_series: int = 10,
                           plates_per_cell: int = 5) -> EdisonBatteryState:
    """Design an Edison battery for a given energy requirement.

    Args:
        energy_wh: Required energy storage (Wh).
        cells_series: Number of cells in series (sets voltage).
        plates_per_cell: Electrode plates per cell (sets capacity).

    Returns:
        EdisonBatteryState at full charge.
    """
    pack_voltage = cells_series * EDISON_CELL_VOLTAGE_OC
    capacity_ah = energy_wh / pack_voltage
    mass_kg = energy_wh / EDISON_ENERGY_DENSITY_WH_KG
    r_int = EDISON_R_INT_PER_CELL * cells_series / plates_per_cell

    return EdisonBatteryState(
        voltage=pack_voltage,
        current_a=0.0,
        capacity_remaining_ah=capacity_ah,
        capacity_total_ah=capacity_ah,
        mass_kg=mass_kg,
        temperature_c=25.0,
    )


def edison_terminal_voltage(battery: EdisonBatteryState,
                             load_current_a: float,
                             cells_series: int = 10,
                             plates_per_cell: int = 5) -> float:
    """Terminal voltage under load: V = V_oc - I * R_int.

    Internal resistance scales with cells in series and inversely with
    plates per cell (more plate area = lower resistance).
    """
    v_oc = cells_series * EDISON_CELL_VOLTAGE_OC
    r_int = EDISON_R_INT_PER_CELL * cells_series / plates_per_cell
    # SOC affects open-circuit voltage slightly (linear approximation)
    soc_factor = 0.9 + 0.1 * battery.soc  # 90-100% of nominal
    return v_oc * soc_factor - load_current_a * r_int


def discharge_edison(battery: EdisonBatteryState,
                      load_current_a: float,
                      duration_s: float,
                      cells_series: int = 10,
                      plates_per_cell: int = 5) -> EdisonBatteryState:
    """Discharge battery at constant current for a duration.

    Returns updated battery state.
    """
    duration_h = duration_s / 3600.0
    ah_drawn = load_current_a * duration_h
    remaining = max(0.0, battery.capacity_remaining_ah - ah_drawn)
    v_term = edison_terminal_voltage(battery, load_current_a,
                                      cells_series, plates_per_cell)
    v_term = max(0.0, v_term)
    energy = v_term * load_current_a * duration_h

    return EdisonBatteryState(
        time_s=battery.time_s + duration_s,
        voltage=v_term,
        current_a=load_current_a,
        capacity_remaining_ah=remaining,
        capacity_total_ah=battery.capacity_total_ah,
        temperature_c=battery.temperature_c,
        energy_delivered_wh=battery.energy_delivered_wh + energy,
        cycles_used=battery.cycles_used,
        mass_kg=battery.mass_kg,
    )


# ============================================================================
# 3. Retrieval Tug
# ============================================================================

@dataclass
class TugState:
    """Snapshot of the retrieval tug during a sortie."""
    time_s: float = 0.0
    phase: str = "docked"          # docked, undock, burn_out, coast, approach,
                                   # capture, burn_return, dock
    position_m: float = 0.0        # Distance from mothership (1D model)
    velocity_m_s: float = 0.0      # Radial velocity
    propellant_kg: float = 0.0     # H2 + O2 remaining
    dry_mass_kg: float = 0.0       # Structure + payload
    rock_mass_kg: float = 0.0      # Captured asteroid mass (0 until capture)
    battery: EdisonBatteryState = field(default_factory=EdisonBatteryState)
    nav_error_deg: float = 0.0     # Accumulated navigation error
    delta_v_used_m_s: float = 0.0  # Total delta-v expended
    water_electrolyzed_kg: float = 0.0


def water_to_propellant(water_kg: float) -> dict:
    """Calculate H2 and O2 from water electrolysis.

    Per 18g water: 2g H2 + 16g O2 (mass ratio 1:8).
    Energy: 286 kJ/mol = 15.9 MJ/kg water.

    Returns dict with h2_kg, o2_kg, total_propellant_kg, energy_kwh.
    """
    h2_kg = water_kg * H2_MASS_FRACTION
    o2_kg = water_kg * O2_MASS_FRACTION
    moles = water_kg / WATER_MOLAR_MASS_KG
    energy_kj = moles * ELECTROLYSIS_ENERGY_KJ_PER_MOL
    energy_kwh = energy_kj / 3600.0

    return {
        "h2_kg": h2_kg,
        "o2_kg": o2_kg,
        "total_propellant_kg": h2_kg + o2_kg,
        "energy_kwh": energy_kwh,
        "water_kg": water_kg,
    }


def tsiolkovsky_delta_v(m_wet_kg: float, m_dry_kg: float,
                         isp_s: float = ISP_H2O2) -> float:
    """Tsiolkovsky rocket equation: dv = Isp * g0 * ln(m_wet / m_dry).

    Args:
        m_wet_kg: Total mass before burn (dry + propellant).
        m_dry_kg: Mass after all propellant is spent.
        isp_s: Specific impulse in seconds.

    Returns:
        Delta-v in m/s.
    """
    if m_dry_kg <= 0 or m_wet_kg <= m_dry_kg:
        return 0.0
    return isp_s * G0 * math.log(m_wet_kg / m_dry_kg)


def propellant_for_delta_v(delta_v_m_s: float, m_payload_kg: float,
                            isp_s: float = ISP_H2O2) -> float:
    """Propellant mass needed for a given delta-v and payload.

    From Tsiolkovsky: m_prop = m_dry * (exp(dv / (Isp * g0)) - 1)
    """
    if delta_v_m_s <= 0:
        return 0.0
    mass_ratio = math.exp(delta_v_m_s / (isp_s * G0))
    return m_payload_kg * (mass_ratio - 1.0)


def simulate_tug_sortie(target_distance_m: float = 1000.0,
                         rock_mass_kg: float = 5000.0,
                         tug_dry_mass_kg: float = 200.0,
                         water_available_kg: float = 500.0,
                         battery_energy_wh: float = 500.0,
                         burn_time_s: float = 60.0,
                         nav_current_a: float = 0.5,
                         dt_s: float = 60.0) -> List[TugState]:
    """Simulate a retrieval tug sortie: undock -> burn -> coast -> capture -> return.

    1D model along the radial from mothership to target asteroid.

    Propellant budget:
      - Outbound burn: accelerate toward target
      - Outbound brake: decelerate at target
      - Return burn: accelerate toward mothership (with rock mass)
      - Return brake: decelerate at mothership (with rock mass)

    The tug carries all propellant from the start (produced by pre-flight
    water electrolysis, powered by the Edison battery).

    Args:
        target_distance_m: Distance to target asteroid (m).
        rock_mass_kg: Mass of asteroid to capture and return.
        tug_dry_mass_kg: Tug structural mass (no propellant, no rock).
        water_available_kg: Water available for electrolysis.
        battery_energy_wh: Edison battery capacity.
        burn_time_s: Duration of each thrust burn.
        nav_current_a: Navigation system current draw (A).
        dt_s: Simulation timestep (seconds).

    Returns:
        List of TugState snapshots (one per timestep).
    """
    states: List[TugState] = []

    # -- Pre-flight: electrolyze water into propellant --
    prop_data = water_to_propellant(water_available_kg)
    propellant_kg = prop_data["total_propellant_kg"]
    electrolysis_kwh = prop_data["energy_kwh"]

    # Design the battery
    battery = design_edison_battery(battery_energy_wh)

    # Discharge battery for electrolysis (pre-flight, not simulated step-by-step)
    electrolysis_time_s = (electrolysis_kwh * 1000.0) / max(battery.voltage * 10.0, 1.0)
    battery = discharge_edison(battery, 10.0, electrolysis_time_s)

    # -- Calculate delta-v budget --
    # Outbound: tug + all propellant (no rock yet)
    m_wet_total = tug_dry_mass_kg + propellant_kg
    # Return: tug + rock + remaining propellant for return
    # We split propellant roughly: outbound needs to accelerate and brake (tug only),
    # return needs to accelerate and brake (tug + rock).
    # Iterative split: allocate half for outbound, half for return (conservative).

    # More precise: compute required delta-v for each leg.
    # For a simple 1D sortie in micro-gravity (near-zero gravity), the tug
    # needs to accelerate to cruise speed, then decelerate.  Each leg has
    # two burns (accel + decel).  The delta-v per leg is 2 * v_cruise.
    #
    # We solve for the cruise velocity that uses all propellant across 4 burns.

    # Outbound mass (before any burn): tug + all propellant
    # After outbound: tug + remaining propellant
    # After capture: tug + rock + remaining propellant
    # After return: tug + rock

    # Total available delta-v with all propellant (tug only, no rock):
    total_dv_empty = tsiolkovsky_delta_v(m_wet_total, tug_dry_mass_kg)

    # Allocate propellant between outbound and return legs
    # Outbound: tug only (lighter).  Return: tug + rock (heavier).
    # The return leg needs more propellant per m/s of delta-v.
    # Use the constraint that outbound dv = return dv (same distance,
    # accelerate + decelerate symmetrically).

    # Fraction of propellant for outbound vs return:
    # For equal delta-v on both legs, heavier return leg needs more fuel.
    # Approximate: mass ratio determines split.
    return_mass_ratio = (tug_dry_mass_kg + rock_mass_kg) / tug_dry_mass_kg
    outbound_fraction = 1.0 / (1.0 + return_mass_ratio)
    prop_outbound = propellant_kg * outbound_fraction
    prop_return = propellant_kg - prop_outbound

    # Delta-v for outbound (2 burns: accel + decel)
    dv_outbound = tsiolkovsky_delta_v(
        tug_dry_mass_kg + propellant_kg,
        tug_dry_mass_kg + propellant_kg - prop_outbound)
    # Delta-v for return with rock (2 burns: accel + decel)
    dv_return = tsiolkovsky_delta_v(
        tug_dry_mass_kg + rock_mass_kg + prop_return,
        tug_dry_mass_kg + rock_mass_kg)

    # Each leg: half the leg's dv for accel, half for decel
    v_cruise_out = dv_outbound / 2.0
    v_cruise_return = dv_return / 2.0

    # Thrust calculation
    m_dot_out = prop_outbound / (2.0 * burn_time_s) if burn_time_s > 0 else 0
    m_dot_ret = prop_return / (2.0 * burn_time_s) if burn_time_s > 0 else 0
    thrust_out = m_dot_out * V_EXHAUST
    thrust_ret = m_dot_ret * V_EXHAUST

    # -- Simulation state --
    position = 0.0
    velocity = 0.0
    prop_remaining = propellant_kg
    phase = "undock"
    nav_error = 0.0
    dv_used = 0.0
    current_rock = 0.0
    phase_timer = 0.0
    coast_logged = False

    def current_mass():
        return tug_dry_mass_kg + prop_remaining + current_rock

    def record(t):
        states.append(TugState(
            time_s=t,
            phase=phase,
            position_m=position,
            velocity_m_s=velocity,
            propellant_kg=prop_remaining,
            dry_mass_kg=tug_dry_mass_kg,
            rock_mass_kg=current_rock,
            battery=battery,
            nav_error_deg=nav_error,
            delta_v_used_m_s=dv_used,
            water_electrolyzed_kg=water_available_kg,
        ))

    t = 0.0
    record(t)

    # Mission phases
    # 1. undock (brief, t=0)
    # 2. burn_out (accelerate toward target)
    # 3. coast (drift toward target)
    # 4. approach (decelerate at target)
    # 5. capture (attach to rock)
    # 6. burn_return (accelerate toward mothership)
    # 7. coast_return (drift toward mothership)
    # 8. dock (decelerate and dock)

    max_time_s = 3600.0 * 24.0 * 7.0  # Safety: 7-day max mission
    phase = "burn_out"
    phase_timer = 0.0

    while t < max_time_s:
        t += dt_s
        phase_timer += dt_s

        # Navigation error accumulates during coast
        if "coast" in phase:
            nav_error += GYRO_DRIFT_DEG_PER_HR * (dt_s / 3600.0)

        # Battery drain for navigation
        battery = discharge_edison(battery, nav_current_a, dt_s)

        # -- Phase: burn_out (accelerate toward target) --
        if phase == "burn_out":
            if phase_timer <= burn_time_s and prop_remaining > 0:
                consumed = min(m_dot_out * dt_s, prop_remaining)
                prop_remaining -= consumed
                accel = thrust_out / current_mass()
                velocity += accel * dt_s
                dv_used += accel * dt_s
            else:
                phase = "coast_out"
                phase_timer = 0.0

        # -- Phase: coast_out (drift toward target) --
        elif phase == "coast_out":
            # Coast until halfway, then we need to start braking.
            # In zero-g, we coast until close enough to brake.
            remaining_dist = target_distance_m - position
            # Start braking when we need burn_time_s to stop
            brake_dist = velocity * burn_time_s / 2.0  # v*t/2 approximate
            if remaining_dist <= brake_dist or remaining_dist <= 0:
                phase = "approach"
                phase_timer = 0.0

        # -- Phase: approach (decelerate at target) --
        elif phase == "approach":
            if phase_timer <= burn_time_s and prop_remaining > 0 and velocity > 0:
                consumed = min(m_dot_out * dt_s, prop_remaining)
                prop_remaining -= consumed
                decel = thrust_out / current_mass()
                velocity -= decel * dt_s
                dv_used += decel * dt_s
                velocity = max(0.0, velocity)
            else:
                phase = "capture"
                phase_timer = 0.0
                velocity = 0.0  # Matched velocity with target

        # -- Phase: capture (grab the rock) --
        elif phase == "capture":
            if phase_timer >= 300.0:  # 5 minutes to attach
                current_rock = rock_mass_kg
                phase = "burn_return"
                phase_timer = 0.0

        # -- Phase: burn_return (accelerate toward mothership) --
        elif phase == "burn_return":
            if phase_timer <= burn_time_s and prop_remaining > 0:
                consumed = min(m_dot_ret * dt_s, prop_remaining)
                prop_remaining -= consumed
                accel = thrust_ret / current_mass()
                velocity -= accel * dt_s  # Negative = toward mothership
                dv_used += accel * dt_s
            else:
                phase = "coast_return"
                phase_timer = 0.0

        # -- Phase: coast_return (drift toward mothership) --
        elif phase == "coast_return":
            # Brake when close to mothership
            brake_dist = abs(velocity) * burn_time_s / 2.0
            if position <= brake_dist or position <= 0:
                phase = "dock"
                phase_timer = 0.0

        # -- Phase: dock (decelerate and dock) --
        elif phase == "dock":
            if phase_timer <= burn_time_s and prop_remaining > 0 and velocity < 0:
                consumed = min(m_dot_ret * dt_s, prop_remaining)
                prop_remaining -= consumed
                decel = thrust_ret / current_mass()
                velocity += decel * dt_s  # Braking (reducing negative velocity)
                dv_used += decel * dt_s
                if velocity >= 0:
                    velocity = 0.0
            else:
                # Mission complete
                velocity = 0.0
                record(t)
                break

        # -- Position update --
        position += velocity * dt_s

        # Record state
        record(t)

        # Safety: if docked back
        if phase == "dock" and abs(velocity) < 0.01 and position <= 10.0:
            break

    return states


# ============================================================================
# Report Formatting
# ============================================================================

def format_life_support_report(states: List[LifeSupportState]) -> str:
    """Format relay life support simulation report (ASCII-only)."""
    if not states:
        return "No data."

    lines: List[str] = []
    first = states[0]
    last = states[-1]

    lines.append("=" * 95)
    lines.append("  RELAY LIFE SUPPORT -- Bimetallic Thermostat + Dashpot Timer")
    lines.append("=" * 95)
    lines.append(f"  Duration: {last.hour} hours ({last.hour / 24:.0f} days)")
    lines.append(f"  Heater power: {first.power_watts:.0f} W (when ON)")
    lines.append(f"  Bacteria status: {'ALIVE' if last.bacteria_alive else 'DEAD'}")
    lines.append(f"  Final viability: {last.bacteria_viability * 100:.0f}%")
    lines.append("")

    # Temperature history (sample every 24 hours)
    lines.append("--- DAILY TEMPERATURE LOG ---")
    hdr = (f"{'Day':>4} | {'Temp C':>7} | {'Heater':>6} | {'Pump':>4} | "
           f"{'Viability':>9} | {'Duty':>5} | {'Energy Wh':>10}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for s in states:
        if s.hour % 24 == 0:
            heater_str = "ON" if s.heater_on else "off"
            pump_str = "ON" if s.pump_on else "off"
            lines.append(
                f"{s.hour // 24:>4} | {s.temp_c:>7.1f} | {heater_str:>6} | "
                f"{pump_str:>4} | {s.bacteria_viability * 100:>7.0f}% | "
                f"{s.heater_duty_cycle * 100:>4.0f}% | {s.cumulative_energy_wh:>10.0f}")

    # Temperature stats
    temps = [s.temp_c for s in states]
    lines.append("")
    lines.append("--- TEMPERATURE STATISTICS ---")
    lines.append(f"  Min temperature: {min(temps):>7.1f} C")
    lines.append(f"  Max temperature: {max(temps):>7.1f} C")
    lines.append(f"  Mean temperature: {sum(temps)/len(temps):>7.1f} C")
    lines.append(f"  Viable range: {BACTERIA_TEMP_MIN_C:.0f}-{BACTERIA_TEMP_MAX_C:.0f} C")
    lines.append(f"  Optimal range: {BACTERIA_TEMP_OPTIMAL_LOW_C:.0f}-{BACTERIA_TEMP_OPTIMAL_HIGH_C:.0f} C")

    # Thermostat physics
    test_defl = bimetallic_deflection_mm(2.5, 30.0, 1.0)
    lines.append("")
    lines.append("--- THERMOSTAT PHYSICS ---")
    lines.append(f"  Bimetallic strip: Fe-Cu, 30mm x 1mm")
    lines.append(f"  Deflection at 2.5C deadband: {test_defl:.2f} mm")
    lines.append(f"  Contact gap: 0.5 mm")
    lines.append(f"  Sufficient deflection: {'YES' if test_defl >= 0.5 else 'NO'}")

    # Energy summary
    lines.append("")
    lines.append("--- ENERGY SUMMARY ---")
    lines.append(f"  Total energy consumed: {last.cumulative_energy_wh:.0f} Wh "
                 f"({last.cumulative_energy_wh / 1000:.1f} kWh)")
    lines.append(f"  Heater duty cycle: {last.heater_duty_cycle * 100:.1f}%")
    avg_power = last.cumulative_energy_wh / max(last.hour, 1)
    lines.append(f"  Average power: {avg_power:.1f} W")

    # Verdict
    lines.append("")
    lines.append("=" * 95)
    if last.bacteria_alive:
        lines.append("  VERDICT: BACTERIA ALIVE after {:.0f} days. Relay life support works.".format(
            last.hour / 24))
    else:
        death_hour = next(
            (s.hour for s in states if not s.bacteria_alive), last.hour)
        lines.append(
            f"  VERDICT: BACTERIA DIED at hour {death_hour} "
            f"({death_hour / 24:.0f} days). System failed.")
    lines.append("=" * 95)

    return "\n".join(lines)


def format_tug_sortie_report(states: List[TugState]) -> str:
    """Format retrieval tug sortie report (ASCII-only)."""
    if not states:
        return "No data."

    lines: List[str] = []
    first = states[0]
    last = states[-1]

    lines.append("=" * 95)
    lines.append("  RETRIEVAL TUG SORTIE -- WAAM-Built H2/O2 Rocket")
    lines.append("=" * 95)

    mission_hours = last.time_s / 3600.0
    lines.append(f"  Mission duration: {mission_hours:.1f} hours ({mission_hours / 24:.1f} days)")
    lines.append(f"  Target distance: {max(s.position_m for s in states):.0f} m")
    lines.append(f"  Rock captured: {last.rock_mass_kg:.0f} kg")
    lines.append(f"  Tug dry mass: {last.dry_mass_kg:.0f} kg")
    lines.append(f"  Water electrolyzed: {last.water_electrolyzed_kg:.0f} kg")
    lines.append(f"  Total delta-v used: {last.delta_v_used_m_s:.1f} m/s")
    lines.append(f"  Propellant remaining: {last.propellant_kg:.1f} kg")
    lines.append(f"  Navigation error: {last.nav_error_deg:.2f} deg")
    lines.append("")

    # Phase timeline
    lines.append("--- MISSION PHASES ---")
    current_phase = states[0].phase
    phase_start = 0.0
    for s in states:
        if s.phase != current_phase:
            lines.append(
                f"  {phase_start / 3600:>7.2f}h - {s.time_s / 3600:>7.2f}h: "
                f"{current_phase}")
            current_phase = s.phase
            phase_start = s.time_s
    lines.append(
        f"  {phase_start / 3600:>7.2f}h - {last.time_s / 3600:>7.2f}h: "
        f"{current_phase}")

    # Propulsion summary
    lines.append("")
    lines.append("--- PROPULSION ---")
    lines.append(f"  Propellant type: H2/O2 (from water electrolysis)")
    lines.append(f"  Isp: {ISP_H2O2} s (vacuum)")
    lines.append(f"  Exhaust velocity: {V_EXHAUST:.0f} m/s")
    prop_used = first.propellant_kg - last.propellant_kg
    lines.append(f"  Propellant consumed: {prop_used:.1f} kg")
    lines.append(f"  Propellant remaining: {last.propellant_kg:.1f} kg")
    if first.propellant_kg > 0:
        lines.append(f"  Propellant efficiency: {prop_used / max(first.propellant_kg, 1) * 100:.0f}% used")

    # Edison battery status
    lines.append("")
    lines.append("--- EDISON BATTERY ---")
    lines.append(f"  Capacity: {last.battery.capacity_total_ah:.1f} Ah")
    lines.append(f"  Remaining: {last.battery.capacity_remaining_ah:.1f} Ah "
                 f"({last.battery.soc * 100:.0f}% SOC)")
    lines.append(f"  Mass: {last.battery.mass_kg:.1f} kg")
    lines.append(f"  Energy delivered: {last.battery.energy_delivered_wh:.0f} Wh")

    # Navigation
    lines.append("")
    lines.append("--- NAVIGATION ---")
    lines.append(f"  Sun sensor accuracy: {SUN_SENSOR_ACCURACY_DEG} deg")
    lines.append(f"  Gyro drift: {GYRO_DRIFT_DEG_PER_HR} deg/hr")
    lines.append(f"  Total nav error: {last.nav_error_deg:.2f} deg")
    if mission_hours > 0:
        miss_m = math.tan(math.radians(last.nav_error_deg)) * max(
            s.position_m for s in states)
        lines.append(f"  Position uncertainty at target: {miss_m:.0f} m")

    # Verdict
    lines.append("")
    lines.append("=" * 95)
    completed_phases = set(s.phase for s in states)
    mission_success = last.rock_mass_kg > 0 and last.phase == "dock"
    if mission_success:
        lines.append(f"  VERDICT: MISSION SUCCESS. {last.rock_mass_kg:.0f} kg rock retrieved "
                     f"in {mission_hours:.1f} hours.")
    else:
        lines.append(f"  VERDICT: MISSION INCOMPLETE. Final phase: {last.phase}. "
                     f"Rock: {last.rock_mass_kg:.0f} kg.")
    lines.append(f"  Phases completed: {', '.join(sorted(completed_phases))}")
    lines.append("=" * 95)

    return "\n".join(lines)
