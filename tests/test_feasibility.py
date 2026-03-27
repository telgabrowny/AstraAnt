"""Tests for the feasibility calculator."""

from astraant.feasibility import MissionConfig, SwarmConfig, analyze_mission, format_report
from astraant.catalog import Catalog


def test_basic_analysis_runs():
    """Feasibility analysis completes without errors."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, couriers=1, track="a"),
        asteroid_id="bennu",
        destination="lunar_orbit",
    )
    report = analyze_mission(mission)
    assert report.mass_budget.total_wet_kg > 0
    assert report.cost_estimate.total_first_cycle_usd > 0


def test_track_b_includes_water_mass():
    """Track B should include 300 kg water in mass budget."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, couriers=1, track="b"),
    )
    report = analyze_mission(mission)
    assert report.mass_budget.water_mass_kg == 300
    assert report.mission.include_bioreactor is True


def test_track_a_no_water():
    """Track A should not include bioreactor water."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, couriers=1, track="a"),
    )
    report = analyze_mission(mission)
    assert report.mass_budget.water_mass_kg == 0


def test_more_workers_more_mass():
    """More workers should increase total mass."""
    small = MissionConfig(swarm=SwarmConfig(workers=10, taskmasters=1, couriers=1, track="a"))
    large = MissionConfig(swarm=SwarmConfig(workers=100, taskmasters=5, couriers=3, track="a"))
    r_small = analyze_mission(small)
    r_large = analyze_mission(large)
    assert r_large.mass_budget.swarm_mass_kg > r_small.mass_budget.swarm_mass_kg


def test_mars_orbit_more_expensive_to_launch():
    """Mars orbit should have higher launch cost than lunar orbit."""
    lunar = MissionConfig(
        swarm=SwarmConfig(workers=50, taskmasters=3, couriers=2, track="a"),
        destination="lunar_orbit",
    )
    mars = MissionConfig(
        swarm=SwarmConfig(workers=50, taskmasters=3, couriers=2, track="a"),
        destination="mars_orbit",
    )
    r_lunar = analyze_mission(lunar)
    r_mars = analyze_mission(mars)
    assert r_mars.cost_estimate.launch_cost_usd > r_lunar.cost_estimate.launch_cost_usd


def test_report_formatting():
    """Report formats without errors."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, couriers=1, track="a"),
    )
    report = analyze_mission(mission)
    text = format_report(report)
    assert "MASS BUDGET" in text
    assert "COST ESTIMATE" in text
    assert "ECONOMICS" in text
