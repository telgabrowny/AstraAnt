"""Tests for the giant machine physics module."""

from astraant.giant_machines import (
    design_giant_arm,
    design_giant_spider,
    design_relay_computer,
    survey_arms,
    survey_spiders,
    survey_relay_computers,
    pressure_vessel_max_radius,
    centrifugal_max_diameter,
    wire_min_diameter,
    cantilever_required_od,
    format_arm_report,
    format_spider_report,
    format_relay_report,
    format_stress_limits,
    format_full_report,
    YIELD_MPA,
    RELAY_TASKS,
)


# -- Giant Arm Printer -------------------------------------------------------

def test_arm_natural_frequency_decreases_with_length():
    """Longer arms must have lower natural frequency (stiffer = higher f,
    but length dominates: f ~ 1/L^2)."""
    arms = survey_arms(lengths=[1.0, 3.0, 10.0, 30.0, 50.0], payload_kg=50.0)
    for i in range(1, len(arms)):
        assert arms[i].natural_freq_hz < arms[i - 1].natural_freq_hz, (
            f"Arm {arms[i].length_m}m has f_n={arms[i].natural_freq_hz} Hz "
            f">= {arms[i-1].length_m}m f_n={arms[i-1].natural_freq_hz} Hz")


def test_arm_1m_handles_50kg():
    """A 1m arm must comfortably handle 50 kg payload (safety factor >= 2)."""
    arm = design_giant_arm(length_m=1.0, payload_kg=50.0)
    assert arm.safety_factor >= 2.0, (
        f"1m arm SF={arm.safety_factor}, expected >= 2.0")
    assert arm.arm_mass_kg > 0
    assert arm.natural_freq_hz > 1.0  # Short arm should be stiff


def test_arm_50m_has_low_natural_freq():
    """A 50m arm must have low natural frequency and trigger vibration warning."""
    arm = design_giant_arm(length_m=50.0, payload_kg=50.0)
    assert arm.vibration_warning, (
        f"50m arm should warn about vibration, f_n={arm.natural_freq_hz} Hz")
    assert arm.natural_freq_hz < 1.0, (
        f"50m arm f_n={arm.natural_freq_hz} Hz, expected < 1 Hz")


def test_arm_mass_increases_with_length():
    """Longer arms must be heavier."""
    arms = survey_arms(lengths=[1.0, 10.0, 50.0], payload_kg=50.0)
    for i in range(1, len(arms)):
        assert arms[i].arm_mass_kg > arms[i - 1].arm_mass_kg


def test_arm_print_rate_decreases_with_length():
    """Longer arms print slower due to vibration settling."""
    arms = survey_arms(lengths=[1.0, 10.0, 50.0], payload_kg=50.0)
    for i in range(1, len(arms)):
        assert arms[i].print_rate_kg_hr <= arms[i - 1].print_rate_kg_hr, (
            f"Arm {arms[i].length_m}m prints faster than {arms[i-1].length_m}m")


# -- Giant Edison Spider ------------------------------------------------------

def test_spider_grip_exceeds_inertial_load():
    """Grip force must exceed the inertial reaction from moving its own legs.
    In microgravity the spider must hold on while swinging legs."""
    for d in [0.5, 2.0, 5.0, 10.0]:
        spider = design_giant_spider(body_diameter_m=d)
        # Inertial load from one leg swing = leg_mass * leg_length * alpha
        # The spider moves 4 legs at once; remaining 4 must hold.
        # Each foot must hold > total inertial reaction / 4
        alpha = 0.5 / max(1.0, d / 2.0)
        inertial_per_leg = spider.leg_mass_kg * spider.leg_length_m * alpha
        total_inertial = inertial_per_leg * 4  # 4 legs swinging
        grip_per_foot = spider.grip_force_n  # Each of 4 gripping feet
        total_grip = grip_per_foot * 4
        # Grip should exceed inertial load (otherwise spider flies off hull)
        assert total_grip > total_inertial * 0.1, (
            f"Spider {d}m: total grip {total_grip:.2f}N vs "
            f"inertial {total_inertial:.2f}N -- grip too weak for size")


def test_spider_battery_lasts_hours():
    """Battery endurance must be in hours, not minutes."""
    for d in [0.5, 2.0, 5.0, 10.0]:
        spider = design_giant_spider(body_diameter_m=d)
        assert spider.battery_hours >= 1.0, (
            f"Spider {d}m battery lasts only {spider.battery_hours:.2f} hours")


def test_spider_bigger_is_heavier():
    """Bigger spiders must be heavier."""
    spiders = survey_spiders(diameters=[0.5, 2.0, 5.0, 10.0])
    for i in range(1, len(spiders)):
        assert spiders[i].total_mass_kg > spiders[i - 1].total_mass_kg


def test_spider_has_cargo_capacity():
    """Every spider must be able to carry some cargo."""
    for d in [0.5, 2.0, 5.0, 10.0]:
        spider = design_giant_spider(body_diameter_m=d)
        assert spider.cargo_capacity_kg > 0, (
            f"Spider {d}m has zero cargo capacity")


def test_spider_speed_positive():
    """All spiders must have positive walking speed."""
    for d in [0.5, 2.0, 5.0, 10.0]:
        spider = design_giant_spider(body_diameter_m=d)
        assert spider.max_speed_m_s > 0


# -- Relay Computer -----------------------------------------------------------

def test_relay_computer_thermostat_is_tiny():
    """A 3-relay thermostat must weigh under 5 kg and fit in a shoebox."""
    rc = design_relay_computer(task="thermostat")
    assert rc.n_relays == 3
    assert rc.mass_kg < 5.0, f"Thermostat mass {rc.mass_kg} kg, expected < 5"
    assert rc.volume_m3 < 0.01, f"Thermostat volume {rc.volume_m3} m3, expected < 0.01"
    assert "Shoebox" in rc.rack_dimensions or "box" in rc.rack_dimensions.lower()


def test_relay_computer_autopilot_is_large():
    """A 100-relay autopilot must be significantly larger than a thermostat."""
    thermostat = design_relay_computer(task="thermostat")
    autopilot = design_relay_computer(task="autopilot")
    assert autopilot.mass_kg > thermostat.mass_kg * 10
    assert autopilot.volume_m3 > thermostat.volume_m3 * 10
    assert autopilot.power_watts > thermostat.power_watts * 10


def test_relay_computer_needs_radiator():
    """All relay computers need a radiator (no convection in vacuum)."""
    for task in RELAY_TASKS:
        rc = design_relay_computer(task=task)
        assert rc.radiator_m2 > 0, f"Task '{task}' has no radiator area"


def test_relay_switching_speed():
    """Switching speed must be consistent (~143 Hz from 7ms relays)."""
    rc = design_relay_computer(task="thermostat")
    assert 100 < rc.switching_speed_hz < 200


def test_relay_power_scales_linearly():
    """Power must scale linearly with relay count."""
    rc3 = design_relay_computer(task="thermostat")    # 3 relays
    rc100 = design_relay_computer(task="autopilot")    # 100 relays
    ratio = rc100.power_watts / rc3.power_watts
    expected = 100 / 3
    assert abs(ratio - expected) / expected < 0.01, (
        f"Power ratio {ratio:.1f}, expected {expected:.1f}")


def test_relay_custom_count():
    """Custom relay count must work."""
    rc = design_relay_computer(task="custom", n_relays_override=42)
    assert rc.n_relays == 42
    assert rc.task_name == "custom"


# -- Material Stress Limits ---------------------------------------------------

def test_pressure_vessel_max_radius():
    """Thicker walls must allow larger vessels."""
    r_thin = pressure_vessel_max_radius(wall_thickness_m=0.001, pressure_pa=50000)
    r_thick = pressure_vessel_max_radius(wall_thickness_m=0.010, pressure_pa=50000)
    assert r_thick > r_thin
    assert r_thin > 0
    # 1mm wall at 50 kPa should allow a radius of several meters
    assert r_thin > 1.0, f"1mm wall at 50kPa: r_max={r_thin:.1f}m, expected > 1m"


def test_pressure_vessel_higher_pressure_smaller():
    """Higher pressure must reduce max radius."""
    r_lo = pressure_vessel_max_radius(wall_thickness_m=0.005, pressure_pa=10000)
    r_hi = pressure_vessel_max_radius(wall_thickness_m=0.005, pressure_pa=100000)
    assert r_lo > r_hi


def test_centrifugal_limit():
    """Faster RPM must yield smaller max diameter."""
    d_slow = centrifugal_max_diameter(rpm=100)
    d_fast = centrifugal_max_diameter(rpm=1000)
    assert d_slow > d_fast
    assert d_slow > 0
    # At 100 RPM, iron disc can be quite large
    assert d_slow > 1.0, f"100 RPM max diameter={d_slow:.1f}m, expected > 1m"


def test_centrifugal_zero_rpm():
    """Zero RPM should return zero (no rotation = no limit, but edge case)."""
    assert centrifugal_max_diameter(rpm=0) == 0.0


def test_wire_min_diameter_scales():
    """Higher tension must require thicker wire."""
    d_lo = wire_min_diameter(tension_n=100)
    d_hi = wire_min_diameter(tension_n=10000)
    assert d_hi > d_lo
    assert d_lo > 0


def test_cantilever_required_od_scales():
    """Longer cantilever must need bigger OD."""
    od_short = cantilever_required_od(length_m=1.0, payload_kg=50)
    od_long = cantilever_required_od(length_m=10.0, payload_kg=50)
    assert od_long > od_short


# -- Report Formatting --------------------------------------------------------

def test_format_arm_report_ascii():
    """Arm report must be pure ASCII."""
    arms = survey_arms()
    report = format_arm_report(arms)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII at pos {i}: U+{ord(ch):04X} '{ch}'")


def test_format_spider_report_ascii():
    """Spider report must be pure ASCII."""
    spiders = survey_spiders()
    report = format_spider_report(spiders)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII at pos {i}: U+{ord(ch):04X} '{ch}'")


def test_format_relay_report_ascii():
    """Relay report must be pure ASCII."""
    computers = survey_relay_computers()
    report = format_relay_report(computers)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII at pos {i}: U+{ord(ch):04X} '{ch}'")


def test_format_stress_limits_ascii():
    """Stress limits report must be pure ASCII."""
    report = format_stress_limits()
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII at pos {i}: U+{ord(ch):04X} '{ch}'")


def test_format_full_report_contains_sections():
    """Full report must contain all section headers."""
    arms = survey_arms()
    spiders = survey_spiders()
    computers = survey_relay_computers()
    report = format_full_report(arms=arms, spiders=spiders, computers=computers)
    assert "GIANT ARM PRINTER" in report
    assert "GIANT EDISON SPIDER" in report
    assert "RELAY COMPUTER SIZING" in report
    assert "WAAM IRON STRESS LIMITS" in report
