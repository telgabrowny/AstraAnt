"""Tests for the UHF link budget calculator."""

import math

from astraant.link_budget import (
    LinkBudgetParams,
    compute_fspl,
    compute_link_budget,
    sweep_distances,
    format_link_budget,
    format_distance_sweep,
    AU_METERS,
    C_LIGHT,
    DEFAULT_FREQ_HZ,
)


def test_fspl_at_1au():
    """FSPL at 1 AU / 437 MHz should be approximately 249 dB.

    Exact: 20*log10(4*pi*1AU / lambda_437MHz)
    lambda = 299792458 / 437e6 = 0.6860 m
    FSPL = 20*log10(4*pi*1.496e11 / 0.6860) ~ 248.8 dB
    """
    wavelength = C_LIGHT / DEFAULT_FREQ_HZ
    distance = 1.0 * AU_METERS
    fspl = compute_fspl(distance, wavelength)
    # Should be in the 248-250 dB range (verified analytically)
    assert 248.0 < fspl < 250.0, f"FSPL at 1 AU = {fspl:.1f} dB, expected ~249"


def test_link_closes_at_1au():
    """At 1 AU with default UHF CubeSat params, the link does NOT close.

    This is physically correct -- a 2W UHF CubeSat with a 14 dBi Yagi
    cannot bridge interplanetary distances.  Real deep-space missions use
    X-band (8 GHz) with 34-metre DSN dishes.  The calculator correctly
    shows the UHF limitation, which is a key engineering insight for the
    AstraAnt mission design (mothership needs a better comms module for
    Earth contact; UHF is for ant-to-mothership short-range only).
    """
    params = LinkBudgetParams(distance_au=1.0)
    result = compute_link_budget(params, data_rate_bps=1200.0)
    # CubeSat UHF does NOT close at 1 AU -- this is correct physics
    assert result.link_margin_db < 0, (
        f"Link unexpectedly closes at 1 AU with CubeSat UHF: "
        f"margin = {result.link_margin_db:.1f} dB"
    )
    assert result.link_closes is False


def test_link_closes_at_short_range():
    """UHF link should close easily at LEO-to-ground range (~500 km)."""
    leo_au = 500_000.0 / AU_METERS  # 500 km in AU
    params = LinkBudgetParams(distance_au=leo_au)
    result = compute_link_budget(params, data_rate_bps=9600.0)
    assert result.link_closes, (
        f"CubeSat UHF should close at 500 km: margin = {result.link_margin_db:.1f} dB"
    )
    assert result.link_margin_db > 10  # Comfortable margin at LEO


def test_link_fails_at_10au():
    """At 10 AU the link should fail or have extremely low max data rate.

    10 AU means 20 dB additional path loss vs 1 AU, which kills the budget.
    """
    params = LinkBudgetParams(distance_au=10.0)
    result = compute_link_budget(params, data_rate_bps=1200.0)
    # Deeply negative margin at interplanetary distance with small antennas
    assert result.link_margin_db < 0 or result.max_data_rate_bps < 1.0, (
        f"Link unexpectedly closes at 10 AU: margin={result.link_margin_db:.1f} dB, "
        f"max rate={result.max_data_rate_bps:.1f} bps"
    )


def test_data_rate_decreases_with_distance():
    """Max data rate must decrease monotonically with distance.

    Uses short ranges where the link actually closes so we get nonzero
    rates to compare.
    """
    # Distances in AU that correspond to 1000 km to 100,000 km
    distances = [
        1_000_000 / AU_METERS,
        5_000_000 / AU_METERS,
        10_000_000 / AU_METERS,
        50_000_000 / AU_METERS,
        100_000_000 / AU_METERS,
    ]
    params = LinkBudgetParams()
    results = sweep_distances(params, distances)
    rates = [r.max_data_rate_bps for r in results]
    for i in range(1, len(rates)):
        assert rates[i] <= rates[i - 1], (
            f"Data rate increased from {distances[i-1]:.6f} AU ({rates[i-1]:.0f} bps) "
            f"to {distances[i]:.6f} AU ({rates[i]:.0f} bps)"
        )
    # Closest distance should have a substantial rate
    assert rates[0] > 1000, "Expected >1000 bps at 1000 km"


def test_fspl_increases_with_distance():
    """FSPL must increase as distance increases."""
    wavelength = C_LIGHT / DEFAULT_FREQ_HZ
    fspl_01 = compute_fspl(0.1 * AU_METERS, wavelength)
    fspl_10 = compute_fspl(1.0 * AU_METERS, wavelength)
    assert fspl_10 > fspl_01
    # Specifically, 10x distance = +20 dB FSPL
    assert abs((fspl_10 - fspl_01) - 20.0) < 0.1


def test_format_link_budget_ascii():
    """Formatted output contains expected sections and is ASCII-only."""
    params = LinkBudgetParams(distance_au=1.0)
    result = compute_link_budget(params)
    text = format_link_budget(result)
    assert "TRANSMIT" in text
    assert "PATH" in text
    assert "RECEIVE" in text
    assert "PERFORMANCE" in text
    # ASCII-only check
    for ch in text:
        assert ord(ch) < 128, f"Non-ASCII character: {ch!r} (ord={ord(ch)})"


def test_format_distance_sweep_ascii():
    """Distance sweep table is ASCII-only."""
    results = sweep_distances()
    text = format_distance_sweep(results)
    assert "DISTANCE" in text
    for ch in text:
        assert ord(ch) < 128, f"Non-ASCII character: {ch!r} (ord={ord(ch)})"


def test_higher_tx_power_improves_margin():
    """Doubling TX power should add ~3 dB to the link margin."""
    p1 = LinkBudgetParams(distance_au=1.0, tx_power_w=2.0)
    p2 = LinkBudgetParams(distance_au=1.0, tx_power_w=4.0)
    r1 = compute_link_budget(p1)
    r2 = compute_link_budget(p2)
    improvement = r2.link_margin_db - r1.link_margin_db
    assert abs(improvement - 3.0) < 0.2, f"Expected ~3 dB improvement, got {improvement:.2f} dB"


def test_close_distance_high_rate():
    """At very short range (500 km) with default params, link should close
    and support high data rates."""
    leo_au = 500_000.0 / AU_METERS  # 500 km
    params = LinkBudgetParams(distance_au=leo_au)
    result = compute_link_budget(params, data_rate_bps=9600.0)
    assert result.link_closes, (
        f"CubeSat UHF should close at 500 km: "
        f"margin = {result.link_margin_db:.1f} dB"
    )
    assert result.max_data_rate_bps > 100_000, (
        f"Expected >100 kbps at 500 km, got {result.max_data_rate_bps:.0f} bps"
    )


def test_inverse_square_law_on_rate():
    """Halving the distance should quadruple the max data rate.

    Since max_rate ~ 10^((Prx - N0 - Eb/N0_req - 3) / 10) and Prx gains
    6 dB when distance halves, the rate should increase by ~4x (6 dB).
    """
    d1 = 2_000_000.0 / AU_METERS  # 2000 km
    d2 = 1_000_000.0 / AU_METERS  # 1000 km
    r1 = compute_link_budget(LinkBudgetParams(distance_au=d1))
    r2 = compute_link_budget(LinkBudgetParams(distance_au=d2))
    if r1.max_data_rate_bps > 0 and r2.max_data_rate_bps > 0:
        ratio = r2.max_data_rate_bps / r1.max_data_rate_bps
        # Should be approximately 4x (inverse square on power -> linear on rate)
        assert 3.5 < ratio < 4.5, f"Expected ~4x rate increase, got {ratio:.2f}x"
