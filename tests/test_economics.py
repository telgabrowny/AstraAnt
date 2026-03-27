"""Tests for mission economics, reality check, and scaling."""

from astraant.mission_economics import calculate_site_economics, format_economics_report
from astraant.reality_check import reality_check, REALITY_COSTS, TECHNOLOGY_GAPS
from astraant.scaling import _crowding_factor, ScalingResult


def test_bennu_economics():
    """Bennu 5-year Track B should produce positive revenue."""
    econ = calculate_site_economics("bennu", "lunar_orbit", "b", workers=100, mission_years=5)
    assert econ.total_revenue_usd > 0
    assert econ.total_mission_cost_usd > 0
    assert econ.total_regolith_processed_kg > 0


def test_water_dominates_revenue():
    """Water should be the largest revenue source for C-type asteroids."""
    econ = calculate_site_economics("bennu", "lunar_orbit", "b", workers=100, mission_years=5)
    water_rev = econ.revenue_by_material.get("water", 0)
    total_rev = econ.total_revenue_usd
    assert water_rev > total_rev * 0.5, "Water should be >50% of revenue on C-type"


def test_dry_asteroid_less_profitable():
    """S-type (dry) asteroids should have much less revenue than C-type."""
    bennu = calculate_site_economics("bennu", "lunar_orbit", "b", workers=100, mission_years=5)
    itokawa = calculate_site_economics("itokawa", "lunar_orbit", "b", workers=100, mission_years=5)
    assert bennu.total_revenue_usd > itokawa.total_revenue_usd * 2


def test_economics_report_formatting():
    econ = calculate_site_economics("bennu", "lunar_orbit", "b", workers=50)
    text = format_economics_report(econ)
    assert "BOTTOM LINE" in text
    assert "REVENUE" in text


def test_reality_check_costs():
    """Reality costs should exist and sum to reasonable range."""
    total_low = sum(c.cost_low_usd for c in REALITY_COSTS)
    total_high = sum(c.cost_high_usd for c in REALITY_COSTS)
    assert total_low > 5_000_000   # At least $5M in hidden costs
    assert total_high < 500_000_000  # Less than $500M


def test_reality_check_report():
    econ = calculate_site_economics("bennu", "lunar_orbit", "b", workers=50)
    text = reality_check(econ)
    assert "REALITY CHECK" in text
    assert "TECHNOLOGY GAPS" in text


def test_technology_gaps_exist():
    assert len(TECHNOLOGY_GAPS) >= 3


def test_crowding_factor():
    """Crowding should reduce efficiency at large N."""
    small = _crowding_factor(10)
    medium = _crowding_factor(500)
    large = _crowding_factor(10000)
    assert small > medium > large
    assert small == 1.0  # No crowding at small N
    assert large > 0.3   # Not zero even at large N
