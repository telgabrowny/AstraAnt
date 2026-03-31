"""Tests for the seed mothership bill of materials."""

import math
import re

from astraant.seed_bom import generate_bom_report


def test_bom_generates_report():
    """generate_bom_report() returns a string with key sections."""
    report = generate_bom_report()
    assert isinstance(report, str)
    assert "SEED MOTHERSHIP" in report
    assert "TOTAL HARDWARE" in report
    assert "PROPULSION BUDGET" in report
    assert "POWER BUDGET" in report
    assert "MISSION COST" in report


def test_bom_total_under_50kg():
    """Total hardware mass must be under 50 kg."""
    report = generate_bom_report()
    # Parse "TOTAL HARDWARE: XX.X kg" line
    match = re.search(r"TOTAL HARDWARE:\s+([\d.]+)\s*kg", report)
    assert match, "Could not find TOTAL HARDWARE mass in report"
    total_kg = float(match.group(1))
    assert total_kg < 50, f"Total mass {total_kg:.1f} kg exceeds 50 kg limit"


def test_bom_cost_under_1m():
    """Total budget cost (hardware + rideshare launch) must be under $1M."""
    report = generate_bom_report()
    # Parse "TOTAL (budget):  $  XXX,XXX" line (may have spaces after $)
    match = re.search(r"TOTAL \(budget\):\s+\$\s*([\d,]+)", report)
    assert match, f"Could not find TOTAL (budget) in report. Lines with TOTAL: {[l for l in report.split(chr(10)) if 'TOTAL' in l]}"
    cost_str = match.group(1).replace(",", "").strip()
    total_cost = float(cost_str)
    assert total_cost < 1_000_000, (
        f"Total budget ${total_cost:,.0f} exceeds $1M limit")


def test_bom_has_all_subsystems():
    """Report must contain all 10+ subsystem sections."""
    report = generate_bom_report()
    expected_sections = [
        "STRUCTURE",
        "POWER SYSTEM",
        "PROPULSION",
        "COMPUTE",
        "ROBOTIC ARMS",
        "CHEMISTRY",
        "FLUID SYSTEM",
        "ELECTRO-WINNING",
        "BIOLOGY",
        "PRINTER BOT",
    ]
    for section in expected_sections:
        assert section in report, f"Missing subsystem section: {section}"


def test_bom_delta_v_positive():
    """Delta-V calculation must be positive and > 2000 m/s."""
    report = generate_bom_report()
    # Parse "Delta-V:      XXXX m/s" line
    match = re.search(r"Delta-V:\s+([\d.]+)\s*m/s", report)
    assert match, "Could not find Delta-V in report"
    dv = float(match.group(1))
    assert dv > 0, "Delta-V must be positive"
    assert dv > 2000, f"Delta-V {dv:.0f} m/s is below 2000 m/s minimum"
