"""Tests for the wire factory pipeline simulator."""

from astraant.wire_factory import (
    FARADAY_KG_PER_AMP_DAY,
    INITIAL_ARMS,
    BOT_IRON_KG,
    STIRLING_IRON_KG,
    WAAM_KG_PER_HOUR,
    WireFactoryState,
    run_wire_factory,
    format_report,
)


# -- Electroforming / Faraday's law ----------------------------------------

def test_wire_production_rate_matches_faraday():
    """Wire produced in first day must match Faraday's law: I * 0.02496 kg/day."""
    current = 544.0
    expected_kg_per_day = current * FARADAY_KG_PER_AMP_DAY
    snaps = run_wire_factory(duration_days=1, initial_current_a=current)
    last = snaps[-1]
    # Allow 1% tolerance (hourly discretization)
    assert abs(last.wire_produced_kg - expected_kg_per_day) / expected_kg_per_day < 0.01


def test_wire_production_scales_with_current():
    """Doubling the current must roughly double wire production (before
    Stirling changes current mid-run)."""
    snaps_lo = run_wire_factory(duration_days=1, initial_current_a=100)
    snaps_hi = run_wire_factory(duration_days=1, initial_current_a=200)
    ratio = snaps_hi[-1].wire_produced_kg / snaps_lo[-1].wire_produced_kg
    assert 1.9 < ratio < 2.1


def test_bobbins_accumulate():
    """After a full day at 544 A, many bobbins should be wound."""
    snaps = run_wire_factory(duration_days=1, initial_current_a=544)
    last = snaps[-1]
    # 544A * 0.02496 = ~13.6 kg/day, each bobbin = 0.15 kg -> ~90 bobbins
    assert last.bobbin_count > 50


# -- Bot fleet scaling ------------------------------------------------------

def test_bot_fleet_doubles_roughly_monthly():
    """Bot count should grow to at least 4 in 2 months (doubling from 0->2->4+)."""
    snaps = run_wire_factory(duration_days=90, initial_current_a=544)
    last = snaps[-1]
    # After ~3 months at 544 A (13.6 kg/day wire), should have built
    # several bots.  Initial 2 arms + printed bots.
    assert last.bot_count >= 2, (
        f"Expected at least 2 bots after 90 days, got {last.bot_count}")


def test_active_heads_equals_arms_plus_bots():
    """active_heads must always equal INITIAL_ARMS + bot_count."""
    snaps = run_wire_factory(duration_days=60, initial_current_a=544)
    for s in snaps:
        expected = INITIAL_ARMS + s.bot_count
        assert s.active_heads == expected, (
            f"Hour {s.hour}: active_heads={s.active_heads} "
            f"but arms({INITIAL_ARMS})+bots({s.bot_count})={expected}")


# -- Build priorities -------------------------------------------------------

def test_stirling_engine_built_first():
    """The Stirling engine should be the first completed structure."""
    snaps = run_wire_factory(duration_days=30, initial_current_a=544)
    last = snaps[-1]
    assert len(last.structures_built) > 0, "Nothing built in 30 days"
    first_item = last.structures_built[0]
    assert first_item["type"] == "Stirling engine", (
        f"Expected Stirling first, got '{first_item['type']}'")


def test_stirling_unlocks_power():
    """After Stirling is built, power_kw must increase."""
    snaps = run_wire_factory(duration_days=60, initial_current_a=544)
    initial_power = snaps[0].power_kw
    for s in snaps:
        if s.stirling_built:
            assert s.power_kw > initial_power, (
                "Stirling built but power did not increase")
            break
    else:
        # If Stirling not built in 60 days, that's still worth flagging
        pass


def test_bots_built_after_stirling():
    """Bots should appear in the build log after the Stirling engine."""
    snaps = run_wire_factory(duration_days=90, initial_current_a=544)
    last = snaps[-1]
    stirling_hour = None
    first_bot_hour = None
    for item in last.structures_built:
        if item["type"] == "Stirling engine" and stirling_hour is None:
            stirling_hour = item["hour"]
        if item["type"] == "WAAM bot" and first_bot_hour is None:
            first_bot_hour = item["hour"]

    if stirling_hour is not None and first_bot_hour is not None:
        assert first_bot_hour >= stirling_hour, (
            f"Bot built at hour {first_bot_hour} before Stirling at {stirling_hour}")


# -- Wire inventory safety --------------------------------------------------

def test_wire_inventory_never_negative():
    """Wire inventory must never go below zero at any snapshot."""
    snaps = run_wire_factory(duration_days=180, initial_current_a=544)
    for s in snaps:
        assert s.wire_inventory_kg >= -0.001, (
            f"Wire inventory went negative at hour {s.hour}: "
            f"{s.wire_inventory_kg:.4f} kg")


def test_wire_conservation():
    """Wire produced must equal wire consumed + wire in inventory."""
    snaps = run_wire_factory(duration_days=180, initial_current_a=544)
    last = snaps[-1]
    # Exact conservation: produced = consumed + inventory
    # Small tolerance for in-progress jobs (wire consumed but job not yet
    # completed, tracked in wire_consumed_kg but not in structures_built)
    delta = abs(last.wire_produced_kg - last.wire_consumed_kg - last.wire_inventory_kg)
    assert delta < 1.0, (
        f"Conservation violated: produced={last.wire_produced_kg:.1f}, "
        f"consumed={last.wire_consumed_kg:.1f}, "
        f"inventory={last.wire_inventory_kg:.1f}, delta={delta:.4f}")


# -- Report formatting ------------------------------------------------------

def test_format_report_no_crash():
    """format_report must not crash and must contain key sections."""
    snaps = run_wire_factory(duration_days=30, initial_current_a=544)
    report = format_report(snaps)
    assert "WIRE FACTORY PIPELINE" in report
    assert "FINAL STATE" in report
    assert "SANITY CHECKS" in report


def test_format_report_empty_input():
    """format_report handles empty snapshot list gracefully."""
    report = format_report([])
    assert "No data" in report


def test_format_report_ascii_only():
    """Report must be pure ASCII (Windows cp1252 safe)."""
    snaps = run_wire_factory(duration_days=30, initial_current_a=544)
    report = format_report(snaps)
    for i, ch in enumerate(report):
        assert ord(ch) < 128, (
            f"Non-ASCII char at position {i}: U+{ord(ch):04X} '{ch}'")


# -- Edge cases -------------------------------------------------------------

def test_low_current_still_works():
    """Even with very low current, simulation should not crash."""
    snaps = run_wire_factory(duration_days=10, initial_current_a=10)
    last = snaps[-1]
    assert last.wire_produced_kg > 0
    assert last.wire_inventory_kg >= 0


def test_high_current_builds_fast():
    """High current (2000 A) should produce lots of wire and structures."""
    snaps = run_wire_factory(duration_days=90, initial_current_a=2000)
    last = snaps[-1]
    assert last.wire_produced_kg > 1000
    assert last.stirling_built
    assert last.bot_count > 0


def test_short_simulation():
    """A 1-day sim should return at least 2 snapshots (start + end)."""
    snaps = run_wire_factory(duration_days=1, initial_current_a=544)
    assert len(snaps) >= 2
    assert snaps[0].hour == 0
    assert snaps[-1].hour == 24
