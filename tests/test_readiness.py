"""Tests for the readiness assessment framework."""

from astraant.readiness import (
    ReadinessLevel,
    ReadinessReport,
    assess_mission,
    format_readiness_report,
)


def test_readiness_runs():
    """Assessment completes without errors and finds items."""
    report = assess_mission()
    assert len(report.items) > 0
    assert report.readiness_score > 0


def test_readiness_has_all_levels():
    """Report should contain items at multiple readiness levels."""
    report = assess_mission()
    levels_found = set(i.level for i in report.items)
    assert ReadinessLevel.PROVEN in levels_found
    assert ReadinessLevel.NEEDS_PHYSICAL_TEST in levels_found


def test_readiness_summary_counts():
    """Summary counts should match item counts."""
    report = assess_mission()
    total_from_summary = sum(report.summary.values())
    assert total_from_summary == len(report.items)


def test_readiness_score_range():
    """Score should be 0-100."""
    report = assess_mission()
    assert 0 <= report.readiness_score <= 100


def test_readiness_report_formatting():
    """Report formats without errors."""
    report = assess_mission()
    text = format_readiness_report(report)
    assert "READINESS ASSESSMENT" in text
    assert "PATH TO FLIGHT READY" in text
    assert "PROVEN" in text
