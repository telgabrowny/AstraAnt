"""Tests for the bioreactor kinetics simulation."""

from astraant.bioreactor import (
    VatState, VatConfig, MonodParams,
    VAT_SULFIDE, VAT_REE, VAT_PGM,
    simulate_vat, format_vat_report,
)


def test_sulfide_vat_growth():
    """Bacteria should grow over 24 hours."""
    state = VatState(biomass_g_per_l=0.1, substrate_g_per_l=10.0)
    results = simulate_vat(VAT_SULFIDE, state, duration_hours=24)
    assert len(results) > 0
    assert results[-1].biomass_g_per_l > results[0].biomass_g_per_l


def test_metal_extraction():
    """Metal should be extracted over time."""
    state = VatState(biomass_g_per_l=1.0, substrate_g_per_l=10.0)
    results = simulate_vat(VAT_SULFIDE, state, duration_hours=48)
    assert results[-1].metal_dissolved_g_per_l > 0


def test_substrate_depletion():
    """Substrate should decrease as bacteria consume it."""
    state = VatState(biomass_g_per_l=0.5, substrate_g_per_l=5.0)
    results = simulate_vat(VAT_SULFIDE, state, duration_hours=72)
    assert results[-1].substrate_g_per_l < results[0].substrate_g_per_l


def test_ree_vat():
    """REE vat should function with Aspergillus."""
    state = VatState(biomass_g_per_l=0.1, substrate_g_per_l=10.0, ph=4.0, temp_c=28)
    results = simulate_vat(VAT_REE, state, duration_hours=48)
    assert results[-1].biomass_g_per_l > results[0].biomass_g_per_l


def test_pgm_vat():
    """PGM vat should extract (slowly)."""
    state = VatState(biomass_g_per_l=0.5, substrate_g_per_l=10.0, ph=7.5, temp_c=28)
    results = simulate_vat(VAT_PGM, state, duration_hours=72)
    assert results[-1].metal_dissolved_g_per_l > 0


def test_culture_death_outside_ph():
    """Culture should not grow outside viable pH range."""
    state = VatState(biomass_g_per_l=1.0, substrate_g_per_l=10.0, ph=7.0)  # Way outside range for sulfide vat
    results = simulate_vat(VAT_SULFIDE, state, duration_hours=24)
    # Growth should be zero — pH 7 is lethal for acidophilic bacteria
    assert results[-1].biomass_g_per_l <= state.biomass_g_per_l + 0.01


def test_report_formatting():
    """Report formats without errors."""
    state = VatState(biomass_g_per_l=0.1, substrate_g_per_l=10.0)
    results = simulate_vat(VAT_SULFIDE, state, duration_hours=48)
    text = format_vat_report(VAT_SULFIDE, results)
    assert "BIOREACTOR SIMULATION" in text
    assert "RESULTS" in text
