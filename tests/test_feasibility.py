"""Tests for the feasibility calculator."""

from astraant.feasibility import MissionConfig, SwarmConfig, analyze_mission, format_report
from astraant.catalog import Catalog


def test_basic_analysis_runs():
    """Feasibility analysis completes without errors."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, surface_ants=1, track="mechanical"),
        asteroid_id="bennu",
        destination="lunar_orbit",
    )
    report = analyze_mission(mission)
    assert report.mass_budget.total_wet_kg > 0
    assert report.cost_estimate.total_first_cycle_usd > 0


def test_track_bioleaching_includes_water_mass():
    """Bioleaching track should include 300 kg water in mass budget."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, surface_ants=1, track="bioleaching"),
    )
    report = analyze_mission(mission)
    assert report.mass_budget.water_mass_kg == 300
    assert "bioreactor" in report.mission.mothership_modules


def test_track_mechanical_no_water():
    """Mechanical track should not include bioreactor water."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, surface_ants=1, track="mechanical"),
    )
    report = analyze_mission(mission)
    assert report.mass_budget.water_mass_kg == 0


def test_more_workers_more_mass():
    """More workers should increase total mass."""
    small = MissionConfig(swarm=SwarmConfig(workers=10, taskmasters=1, surface_ants=1, track="mechanical"))
    large = MissionConfig(swarm=SwarmConfig(workers=100, taskmasters=5, surface_ants=3, track="mechanical"))
    r_small = analyze_mission(small)
    r_large = analyze_mission(large)
    assert r_large.mass_budget.swarm_mass_kg > r_small.mass_budget.swarm_mass_kg


def test_mars_orbit_more_expensive_to_launch():
    """Mars orbit should have higher launch cost than lunar orbit."""
    lunar = MissionConfig(
        swarm=SwarmConfig(workers=50, taskmasters=3, surface_ants=2, track="mechanical"),
        destination="lunar_orbit",
    )
    mars = MissionConfig(
        swarm=SwarmConfig(workers=50, taskmasters=3, surface_ants=2, track="mechanical"),
        destination="mars_orbit",
    )
    r_lunar = analyze_mission(lunar)
    r_mars = analyze_mission(mars)
    assert r_mars.cost_estimate.launch_cost_usd > r_lunar.cost_estimate.launch_cost_usd


def test_report_formatting():
    """Report formats without errors."""
    mission = MissionConfig(
        swarm=SwarmConfig(workers=10, taskmasters=1, surface_ants=1, track="mechanical"),
    )
    report = analyze_mission(mission)
    text = format_report(report)
    assert "MASS BUDGET" in text
    assert "COST ESTIMATE" in text
    assert "ECONOMICS" in text
