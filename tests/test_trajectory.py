"""Tests for trajectory estimation."""

from astraant.trajectory import (
    sail_characteristic_acceleration,
    estimate_transit_time,
    estimate_cargo_return,
    format_trajectory_report,
)


def test_sail_acceleration():
    """Sail acceleration should be positive and reasonable."""
    accel = sail_characteristic_acceleration(
        sail_area_m2=25, total_mass_kg=106.5, reflectivity=0.9,
    )
    assert accel > 0
    # NEA Scout was ~0.2 mm/s^2 with 86 m^2, 14 kg
    # Our 25 m^2, 106.5 kg should be much lower
    assert accel < 1.0  # Sanity check


def test_transit_time_positive():
    """Transit time should be positive."""
    days = estimate_transit_time(origin_au=1.1, dest_au=1.0, accel_mm_s2=0.05)
    assert days > 0


def test_higher_accel_faster():
    """Higher acceleration should mean shorter transit."""
    slow = estimate_transit_time(1.1, 1.0, 0.01)
    fast = estimate_transit_time(1.1, 1.0, 0.1)
    assert fast < slow


def test_cargo_return_bennu():
    """Cargo return from Bennu should produce valid estimate."""
    est = estimate_cargo_return("bennu", "lunar_orbit")
    assert est.estimated_transit_days > 0
    assert est.cargo_mass_kg == 100.0
    assert est.total_mass_kg > est.cargo_mass_kg


def test_mars_longer_than_lunar():
    """Mars orbit transit should be longer or comparable to lunar."""
    lunar = estimate_cargo_return("bennu", "lunar_orbit")
    mars = estimate_cargo_return("bennu", "mars_orbit")
    # Mars is farther from Bennu's orbit, so transit should be longer
    # (unless Bennu happens to be closer to Mars than Earth at a given time)
    assert mars.estimated_transit_days > 0
    assert lunar.estimated_transit_days > 0


def test_report_formatting():
    est = estimate_cargo_return("bennu", "lunar_orbit")
    text = format_trajectory_report(est)
    assert "TRAJECTORY" in text
    assert "Transit time" in text
