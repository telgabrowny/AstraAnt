"""Tests for composition variability model."""

from astraant.composition import (
    sample_regolith, simulate_mining_variability,
    format_variability_report, get_zones_for_asteroid,
    C_TYPE_ZONES, S_TYPE_ZONES, RegolithSample,
)


def test_zone_fractions_sum_to_one():
    """Zone fractions should sum to approximately 1.0."""
    c_total = sum(z.fraction for z in C_TYPE_ZONES)
    s_total = sum(z.fraction for z in S_TYPE_ZONES)
    assert abs(c_total - 1.0) < 0.01, f"C-type zones sum to {c_total}"
    assert abs(s_total - 1.0) < 0.01, f"S-type zones sum to {s_total}"


def test_sample_returns_regolith():
    """Sampling should return a valid RegolithSample."""
    metals = {"iron": 200000, "nickel": 13000, "copper": 120}
    sample = sample_regolith(metals, 8.0, 10.0, C_TYPE_ZONES)
    assert isinstance(sample, RegolithSample)
    assert sample.mass_kg == 10.0
    assert len(sample.metals_ppm) == 3
    assert sample.zone in [z.name for z in C_TYPE_ZONES]


def test_variability_exists():
    """Multiple samples should show variation in composition."""
    metals = {"iron": 200000, "nickel": 13000}
    iron_values = []
    for _ in range(50):
        s = sample_regolith(metals, 8.0, 10.0, C_TYPE_ZONES)
        iron_values.append(s.metals_ppm["iron"])
    # Should NOT all be identical (that would mean no variability)
    assert len(set(round(v, 0) for v in iron_values)) > 3


def test_metal_grain_zone_enriches_pgm():
    """Metal grain zone should have elevated PGM levels."""
    metals = {"platinum": 20, "iron": 200000}
    # Force metal_grain zone by running many samples
    pt_values = []
    for _ in range(200):
        s = sample_regolith(metals, 8.0, 10.0, C_TYPE_ZONES)
        pt_values.append(s.metals_ppm["platinum"])
    # Some samples should be significantly above bulk average
    assert max(pt_values) > 20 * 3  # At least 3x enrichment in some batch


def test_simulate_mining_variability():
    """Full variability simulation should return valid stats."""
    result = simulate_mining_variability("bennu", n_batches=50, batch_kg=10.0)
    assert "metal_stats" in result
    assert "zone_distribution" in result
    assert len(result["metal_stats"]) > 0


def test_c_type_vs_s_type_zones():
    """C-type and S-type should use different zone models."""
    c_zones = get_zones_for_asteroid("bennu")
    s_zones = get_zones_for_asteroid("itokawa")
    assert c_zones == C_TYPE_ZONES
    assert s_zones == S_TYPE_ZONES


def test_variability_report_formatting():
    result = simulate_mining_variability("bennu", n_batches=30)
    text = format_variability_report(result)
    assert "VARIABILITY" in text
    assert "ZONE DISTRIBUTION" in text
