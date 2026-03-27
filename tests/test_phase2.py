"""Tests for Phase 2 facilities, launch planner, and manufacturing model."""

from astraant.phase2 import plan_phase2, format_phase2_report, FACILITIES
from astraant.launch_planner import plan_single_launch, format_manifest
from astraant.manufacturing import (
    plan_manufacturing, format_manufacturing_report, MANUFACTURABLE, EARTH_ONLY,
)


# --- Phase 2 ---

def test_phase2_has_facilities():
    """Should have at least 5 facility types."""
    assert len(FACILITIES) >= 5


def test_phase2_default_plan():
    """Default plan should produce valid results."""
    plan = plan_phase2()
    assert len(plan.selected_facilities) > 0
    assert plan.total_cost_usd > 0
    assert plan.total_annual_revenue_usd > 0


def test_phase2_all_facilities():
    """All facilities should fit in the default chamber."""
    fac_ids = [f.id for f in FACILITIES]
    plan = plan_phase2(fac_ids, chamber_volume_m3=2572)
    assert plan.total_equipment_mass_kg > 10000  # > 10 tonnes
    assert plan.break_even_years > 0


def test_phase2_dependency_warning():
    """Selecting a facility without its dependency should warn."""
    plan = plan_phase2(["centrifuge_ring"])  # Needs habitat_module
    assert any("requires" in n for n in plan.notes)


def test_phase2_report_formats():
    plan = plan_phase2()
    text = format_phase2_report(plan)
    assert "PHASE 2" in text
    assert "TOTALS" in text


# --- Launch Planner ---

def test_launch_manifest_fits():
    """Full manifest should fit in one Starship."""
    manifest = plan_single_launch()
    assert manifest.total_mass_kg < manifest.vehicle_capacity_nea_kg
    assert manifest.margin_kg > 0


def test_launch_manifest_categories():
    """Manifest should have items in multiple categories."""
    manifest = plan_single_launch()
    cats = manifest.mass_by_category()
    assert "mothership" in cats
    assert "swarm" in cats
    assert "phase2" in cats


def test_launch_without_phase2():
    """Phase 1 only should be much lighter."""
    with_p2 = plan_single_launch(include_phase2=True)
    without_p2 = plan_single_launch(include_phase2=False)
    assert without_p2.total_mass_kg < with_p2.total_mass_kg * 0.2


def test_launch_manifest_report():
    manifest = plan_single_launch()
    text = format_manifest(manifest)
    assert "FITS IN ONE LAUNCH" in text
    assert "THE PITCH" in text


# --- Manufacturing ---

def test_manufacturable_items_exist():
    assert len(MANUFACTURABLE) >= 10


def test_earth_only_items():
    """Should have items that can only come from Earth."""
    assert len(EARTH_ONLY) >= 5
    total = sum(i["mass_per_100_ants_kg"] for i in EARTH_ONLY)
    assert total > 5  # At least 5 kg per 100 ants


def test_manufacturing_plan():
    """Should produce a valid plan from excess materials."""
    excess = {"iron": 1000, "nickel": 100, "copper": 10, "waste_paste": 5000, "water": 500}
    plan = plan_manufacturing(excess)
    assert plan.new_ants_possible > 0
    assert plan.new_pods_possible > 0


def test_manufacturing_report():
    excess = {"iron": 100, "waste_paste": 1000, "water": 100}
    plan = plan_manufacturing(excess)
    text = format_manufacturing_report(plan, excess)
    assert "MANUFACTURING" in text
    assert "EARTH" in text
