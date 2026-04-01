"""Tests for the solar power budget calculator."""

import math

from astraant.power_budget import (
    SolarParams,
    solar_power,
    analyze_power_budget,
    format_power_budget,
    get_mission_phases,
    SOLAR_FLUX_1AU_W_M2,
    DEFAULT_PANEL_AREA_M2,
    DEFAULT_CELL_EFFICIENCY,
    DEFAULT_POINTING_LOSS,
    SUPERCAP_FARAD,
    SUPERCAP_VOLTS,
    BOT_CHARGE_POWER_W,
)


def test_solar_power_at_1au():
    """At 1 AU, 4 m^2 panels at 20% efficiency should produce ~1035 W.

    P = 4 * 0.20 * 1361 * 0.95 = 1033.56 W
    """
    params = SolarParams(distance_au=1.0, years_deployed=0.0)
    power = solar_power(params)
    # 4 * 0.20 * 1361 * 0.95 = 1033.56
    expected = DEFAULT_PANEL_AREA_M2 * DEFAULT_CELL_EFFICIENCY * SOLAR_FLUX_1AU_W_M2 * (1 - DEFAULT_POINTING_LOSS)
    assert abs(power - expected) < 1.0, f"Expected ~{expected:.0f}W, got {power:.0f}W"
    # Should be in the 1030-1040 range
    assert 1030 < power < 1040


def test_solar_scales_with_distance():
    """Solar power at 2 AU should be 1/4 of power at 1 AU (inverse square)."""
    p1 = SolarParams(distance_au=1.0, years_deployed=0.0)
    p2 = SolarParams(distance_au=2.0, years_deployed=0.0)
    power_1au = solar_power(p1)
    power_2au = solar_power(p2)
    ratio = power_1au / power_2au
    assert abs(ratio - 4.0) < 0.01, f"Expected ratio 4.0, got {ratio:.3f}"


def test_degradation_reduces_power():
    """5 years of 2%/yr degradation should reduce power by 10%."""
    fresh = SolarParams(distance_au=1.0, years_deployed=0.0)
    aged = SolarParams(distance_au=1.0, years_deployed=5.0)
    p_fresh = solar_power(fresh)
    p_aged = solar_power(aged)
    # After 5 years: factor = 1 - 0.02*5 = 0.90
    expected_ratio = 0.90
    actual_ratio = p_aged / p_fresh
    assert abs(actual_ratio - expected_ratio) < 0.001


def test_transit_phase_has_margin():
    """Transit phase (76W) should fit within solar budget at 1 AU."""
    solar = SolarParams(distance_au=1.0)
    report = analyze_power_budget(solar)
    transit = next(p for p in report.phases if p.phase_name == "TRANSIT")
    assert not transit.deficit, (
        f"Transit phase has deficit: needs {transit.consumed_w:.0f}W, "
        f"has {transit.available_w:.0f}W"
    )
    assert transit.margin_pct > 0


def test_bioleach_phase_at_target():
    """Bioleach phase (64W base) should have margin at 1.2 AU."""
    solar = SolarParams(distance_au=1.2)
    report = analyze_power_budget(solar)
    bioleach = next(p for p in report.phases if p.phase_name == "BIOLEACH")
    # Base bioleach is 64W, available at 1.2 AU is ~718W
    assert not bioleach.deficit, (
        f"Bioleach has deficit at 1.2 AU: needs {bioleach.consumed_w:.0f}W, "
        f"has {bioleach.available_w:.0f}W"
    )
    # Should have substantial headroom for electrowinning
    assert bioleach.electrowinning_w > 100


def test_waam_phase_flagged_if_insufficient():
    """WAAM ops with many heads at a far distance should exceed power budget."""
    solar = SolarParams(distance_au=3.0)  # Very far, power drops to ~115W
    # 3 WAAM heads = 300W + 10W pump + 5W bot + 3W comms = 318W
    report = analyze_power_budget(solar, waam_heads=3, bots_charging=1)
    waam = next(p for p in report.phases if p.phase_name == "WAAM_OPS")
    assert waam.deficit, (
        f"WAAM at 3 AU with 3 heads should have deficit but has "
        f"{waam.margin_w:+.0f}W margin"
    )
    assert any("DEFICIT" in n and "WAAM" in n for n in report.notes)


def test_all_phases_present():
    """All five mission phases should be included in the analysis."""
    report = analyze_power_budget()
    phase_names = [p.phase_name for p in report.phases]
    for expected in ["TRANSIT", "APPROACH", "CAPTURE", "BIOLEACH", "WAAM_OPS"]:
        assert expected in phase_names, f"Missing phase: {expected}"


def test_supercap_charge_time():
    """Supercap charge: 47F * 5.5V^2 / 2 = 711.375 J at 5W = 142.275 s."""
    report = analyze_power_budget()
    expected_j = 0.5 * SUPERCAP_FARAD * SUPERCAP_VOLTS ** 2
    assert abs(report.supercap_energy_j - expected_j) < 0.1
    expected_s = expected_j / BOT_CHARGE_POWER_W
    assert abs(report.supercap_charge_time_s - expected_s) < 0.1
    # Sanity: should be about 142 seconds
    assert 140 < report.supercap_charge_time_s < 145


def test_format_power_budget_ascii():
    """Formatted output should be ASCII-only."""
    report = analyze_power_budget()
    text = format_power_budget(report)
    assert "SOLAR POWER BUDGET" in text
    assert "PHASE ANALYSIS" in text
    for ch in text:
        assert ord(ch) < 128, f"Non-ASCII character: {ch!r} (ord={ord(ch)})"


def test_larger_panel_more_power():
    """Doubling panel area should double available power."""
    small = SolarParams(panel_area_m2=4.0, distance_au=1.0)
    large = SolarParams(panel_area_m2=8.0, distance_au=1.0)
    ratio = solar_power(large) / solar_power(small)
    assert abs(ratio - 2.0) < 0.001
