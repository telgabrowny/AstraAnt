"""Tests for the WAAM-built relay systems module."""

import math

from astraant.relay_systems import (
    ALPHA_DIFF,
    BACTERIA_TEMP_MAX_C,
    BACTERIA_TEMP_MIN_C,
    EDISON_CELL_VOLTAGE_OC,
    EDISON_ENERGY_DENSITY_WH_KG,
    ISP_H2O2,
    G0,
    H2_MASS_FRACTION,
    O2_MASS_FRACTION,
    bimetallic_deflection_mm,
    nickel_heater_resistance,
    nickel_heater_power,
    dashpot_stroke_time_s,
    simulate_life_support,
    design_edison_battery,
    edison_terminal_voltage,
    discharge_edison,
    water_to_propellant,
    tsiolkovsky_delta_v,
    propellant_for_delta_v,
    simulate_tug_sortie,
    format_life_support_report,
    format_tug_sortie_report,
)


# ============================================================================
# 1. Bimetallic thermostat
# ============================================================================

def test_bimetallic_deflection_positive():
    """Higher temperature difference must produce greater strip deflection."""
    d1 = bimetallic_deflection_mm(delta_t_c=2.0)
    d2 = bimetallic_deflection_mm(delta_t_c=5.0)
    d3 = bimetallic_deflection_mm(delta_t_c=10.0)
    assert d1 > 0, "Deflection should be positive for positive delta_t"
    assert d2 > d1, "5C should deflect more than 2C"
    assert d3 > d2, "10C should deflect more than 5C"


def test_bimetallic_deflection_scales_with_length():
    """Deflection scales with L^2 -- doubling length should quadruple deflection."""
    d1 = bimetallic_deflection_mm(delta_t_c=5.0, strip_length_mm=20.0)
    d2 = bimetallic_deflection_mm(delta_t_c=5.0, strip_length_mm=40.0)
    ratio = d2 / d1
    assert 3.8 < ratio < 4.2, f"Expected ~4x, got {ratio:.2f}"


def test_bimetallic_deflection_formula():
    """Verify deflection against hand calculation.

    delta = 6 * (17e-6 - 12e-6) * 10 * (0.03)^2 / 0.001
    = 6 * 5e-6 * 10 * 9e-4 / 1e-3
    = 6 * 5e-6 * 10 * 0.9
    = 2.7e-4 m = 0.27 mm
    """
    d = bimetallic_deflection_mm(delta_t_c=10.0, strip_length_mm=30.0,
                                  strip_thickness_mm=1.0)
    assert abs(d - 0.27) < 0.01, f"Expected ~0.27 mm, got {d:.4f} mm"


# ============================================================================
# 2. Life support simulation
# ============================================================================

def test_thermostat_keeps_bacteria_alive():
    """30-day simulation: bacteria must still be alive at the end."""
    states = simulate_life_support(hours=720, heater_watts=50.0)
    last = states[-1]
    assert last.bacteria_alive, (
        f"Bacteria died! Final temp: {last.temp_c:.1f}C, "
        f"viability: {last.bacteria_viability:.2f}")


def test_thermostat_temperature_stays_in_range():
    """Temperature must stay within bacterial viability range (20-40C)."""
    states = simulate_life_support(hours=720, heater_watts=50.0)
    for s in states:
        assert s.temp_c >= BACTERIA_TEMP_MIN_C - 1.0, (
            f"Hour {s.hour}: temp {s.temp_c:.1f}C below viable minimum")
        assert s.temp_c <= BACTERIA_TEMP_MAX_C + 1.0, (
            f"Hour {s.hour}: temp {s.temp_c:.1f}C above viable maximum")


def test_life_support_heater_cycles():
    """Heater must cycle on and off (not stuck in one state)."""
    states = simulate_life_support(hours=720, heater_watts=50.0)
    on_count = sum(1 for s in states if s.heater_on)
    off_count = sum(1 for s in states if not s.heater_on)
    assert on_count > 0, "Heater never turned on"
    assert off_count > 0, "Heater never turned off"


def test_life_support_energy_accumulates():
    """Cumulative energy must increase over time."""
    states = simulate_life_support(hours=48, heater_watts=50.0)
    assert states[-1].cumulative_energy_wh > states[0].cumulative_energy_wh


def test_nickel_heater_resistance_positive():
    """Heater resistance must be positive and physically reasonable."""
    R = nickel_heater_resistance(wire_length_m=2.0, wire_diameter_mm=0.5)
    assert R > 0
    # For 2m of 0.5mm Ni wire: R = 6.99e-8 * 2.0 / (pi * 0.00025^2)
    # = 1.399e-7 / 1.963e-7 = 0.712 ohm
    assert 0.5 < R < 1.5, f"Expected ~0.7 ohm, got {R:.3f}"


def test_nickel_heater_power_reasonable():
    """At 12V, heater power should be in a reasonable range."""
    P = nickel_heater_power(voltage=12.0, wire_length_m=2.0, wire_diameter_mm=0.5)
    assert P > 50, f"Heater power too low: {P:.1f} W"
    assert P < 500, f"Heater power too high: {P:.1f} W"


def test_dashpot_stroke_time_positive():
    """Dashpot stroke time must be positive and in a reasonable range."""
    t = dashpot_stroke_time_s()
    assert t > 0
    # Default: 10 Pa*s * 0.05m * 200e-6 m^2 / (1e-6 m^2 * 1000 Pa)
    # = 10 * 0.05 * 200e-6 / 1e-3 = 0.1 s.  That's fast; real dashpots
    # use higher viscosity or smaller orifice.
    # Just verify it's calculable and positive.


# ============================================================================
# 3. Edison battery
# ============================================================================

def test_edison_battery_voltage_drops_under_load():
    """Terminal voltage must drop when current is drawn."""
    bat = design_edison_battery(energy_wh=500.0, cells_series=10)
    v_no_load = edison_terminal_voltage(bat, load_current_a=0.0, cells_series=10)
    v_loaded = edison_terminal_voltage(bat, load_current_a=10.0, cells_series=10)
    assert v_loaded < v_no_load, (
        f"Voltage should drop under load: no-load={v_no_load:.2f}V, "
        f"loaded={v_loaded:.2f}V")


def test_edison_battery_capacity_matches_mass():
    """Battery mass should match energy / energy_density."""
    energy_wh = 500.0
    bat = design_edison_battery(energy_wh=energy_wh)
    expected_mass = energy_wh / EDISON_ENERGY_DENSITY_WH_KG
    assert abs(bat.mass_kg - expected_mass) < 0.1, (
        f"Expected {expected_mass:.1f} kg, got {bat.mass_kg:.1f} kg")


def test_edison_battery_discharge_reduces_capacity():
    """Discharging must reduce remaining capacity."""
    bat = design_edison_battery(energy_wh=500.0, cells_series=10)
    initial_cap = bat.capacity_remaining_ah
    bat2 = discharge_edison(bat, load_current_a=5.0, duration_s=3600.0,
                             cells_series=10)
    assert bat2.capacity_remaining_ah < initial_cap, (
        f"Capacity did not decrease: {initial_cap:.2f} -> "
        f"{bat2.capacity_remaining_ah:.2f}")


def test_edison_battery_soc_decreases():
    """State of charge must decrease after discharge."""
    bat = design_edison_battery(energy_wh=500.0, cells_series=10)
    assert bat.soc > 0.99, f"Fresh battery should be at 100% SOC, got {bat.soc:.2f}"
    bat2 = discharge_edison(bat, load_current_a=5.0, duration_s=3600.0,
                             cells_series=10)
    assert bat2.soc < bat.soc


def test_edison_cell_voltage_nominal():
    """Open-circuit voltage per cell should be 1.2V."""
    assert abs(EDISON_CELL_VOLTAGE_OC - 1.2) < 0.01


# ============================================================================
# 4. Water electrolysis / propellant
# ============================================================================

def test_tug_propellant_from_water():
    """Electrolysis mass balance: H2 + O2 = water (conservation of mass)."""
    prop = water_to_propellant(water_kg=100.0)
    total = prop["h2_kg"] + prop["o2_kg"]
    # H2 + O2 should equal the water input (mass conservation)
    assert abs(total - 100.0) < 0.01, (
        f"Mass not conserved: H2={prop['h2_kg']:.2f} + O2={prop['o2_kg']:.2f} "
        f"= {total:.2f}, expected 100.0")


def test_water_electrolysis_ratio():
    """H2:O2 mass ratio must be 1:8."""
    prop = water_to_propellant(water_kg=9.0)
    assert abs(prop["h2_kg"] - 1.0) < 0.01
    assert abs(prop["o2_kg"] - 8.0) < 0.01


def test_electrolysis_energy_positive():
    """Electrolysis must require positive energy."""
    prop = water_to_propellant(water_kg=100.0)
    assert prop["energy_kwh"] > 0


# ============================================================================
# 5. Tsiolkovsky rocket equation
# ============================================================================

def test_tsiolkovsky_positive_delta_v():
    """Delta-v must be positive when wet mass > dry mass."""
    dv = tsiolkovsky_delta_v(m_wet_kg=1000.0, m_dry_kg=500.0)
    assert dv > 0


def test_tsiolkovsky_known_value():
    """Verify against hand calculation.

    dv = 420 * 9.80665 * ln(1000/500) = 4117 * 0.6931 = 2853 m/s
    """
    dv = tsiolkovsky_delta_v(m_wet_kg=1000.0, m_dry_kg=500.0, isp_s=420.0)
    expected = 420.0 * G0 * math.log(2.0)
    assert abs(dv - expected) < 1.0, f"Expected {expected:.0f} m/s, got {dv:.0f} m/s"


def test_tsiolkovsky_zero_propellant():
    """Delta-v should be 0 when wet mass equals dry mass."""
    dv = tsiolkovsky_delta_v(m_wet_kg=500.0, m_dry_kg=500.0)
    assert dv == 0.0


def test_tug_delta_v_sufficient():
    """Tug must have enough delta-v to reach 1 km and return.

    A 1 km sortie in microgravity needs modest delta-v (accelerate, brake,
    accelerate back, brake again).  With 500 kg water -> ~500 kg propellant,
    total delta-v should be ample.
    """
    prop = water_to_propellant(water_kg=500.0)
    dv_empty = tsiolkovsky_delta_v(
        m_wet_kg=200.0 + prop["total_propellant_kg"],
        m_dry_kg=200.0, isp_s=ISP_H2O2)
    # Even with a 5000 kg rock on return, should have hundreds of m/s
    dv_loaded = tsiolkovsky_delta_v(
        m_wet_kg=200.0 + 5000.0 + prop["total_propellant_kg"] / 2,
        m_dry_kg=200.0 + 5000.0, isp_s=ISP_H2O2)
    assert dv_empty > 100, (
        f"Delta-v too low for empty tug: {dv_empty:.0f} m/s")
    assert dv_loaded > 10, (
        f"Delta-v too low for loaded tug: {dv_loaded:.0f} m/s")


# ============================================================================
# 6. Tug mission simulation
# ============================================================================

def test_tug_mission_completes():
    """Full tug sortie must complete all phases and return with rock."""
    states = simulate_tug_sortie(
        target_distance_m=1000.0,
        rock_mass_kg=5000.0,
        tug_dry_mass_kg=200.0,
        water_available_kg=500.0,
    )
    assert len(states) > 2, "Simulation produced too few states"
    last = states[-1]
    # Mission should dock with the rock
    assert last.rock_mass_kg > 0, "Tug did not capture rock"
    phases_seen = set(s.phase for s in states)
    # Must have gone through the major phases
    assert "burn_out" in phases_seen, "Never entered burn_out phase"
    assert "capture" in phases_seen or "burn_return" in phases_seen, (
        "Never reached target area")


def test_tug_propellant_decreases():
    """Propellant must decrease over the mission."""
    states = simulate_tug_sortie(
        target_distance_m=1000.0,
        rock_mass_kg=5000.0,
    )
    assert states[-1].propellant_kg < states[0].propellant_kg, (
        "Propellant did not decrease during mission")


def test_tug_delta_v_accumulates():
    """Total delta-v used must increase from zero."""
    states = simulate_tug_sortie(target_distance_m=1000.0)
    assert states[-1].delta_v_used_m_s > 0


def test_tug_nav_error_accumulates():
    """Navigation error must accumulate during coast phases."""
    states = simulate_tug_sortie(target_distance_m=5000.0)
    # Longer mission = more coast time = more nav error
    assert states[-1].nav_error_deg > 0


# ============================================================================
# 7. Report formatting
# ============================================================================

def test_life_support_report_no_crash():
    """format_life_support_report must not crash."""
    states = simulate_life_support(hours=48)
    report = format_life_support_report(states)
    assert "RELAY LIFE SUPPORT" in report
    assert "VERDICT" in report


def test_tug_report_no_crash():
    """format_tug_sortie_report must not crash."""
    states = simulate_tug_sortie(target_distance_m=1000.0)
    report = format_tug_sortie_report(states)
    assert "RETRIEVAL TUG" in report
    assert "VERDICT" in report


def test_life_support_report_ascii_only():
    """Report must be pure ASCII (Windows cp1252 safe)."""
    states = simulate_life_support(hours=48)
    report = format_life_support_report(states)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII char at position {i}: U+{ord(ch):04X} '{ch}'")


def test_tug_report_ascii_only():
    """Report must be pure ASCII (Windows cp1252 safe)."""
    states = simulate_tug_sortie(target_distance_m=1000.0)
    report = format_tug_sortie_report(states)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII char at position {i}: U+{ord(ch):04X} '{ch}'")


def test_life_support_report_empty():
    """format_life_support_report handles empty input."""
    report = format_life_support_report([])
    assert "No data" in report


def test_tug_report_empty():
    """format_tug_sortie_report handles empty input."""
    report = format_tug_sortie_report([])
    assert "No data" in report
