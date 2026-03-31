"""Tests for the garbage bag bootstrap simulator."""

from astraant.bootstrap_sim import (
    SeedPackage, run_bootstrap, rock_mass, iron_from_rock,
    max_rock_for_iron, shell_mass_for_rock, format_report,
)


def test_seed_fits_in_garbage_bag():
    """Seed package must be under 15 kg (fits in a hefty bag)."""
    seed = SeedPackage()
    assert seed.total_kg < 15


def test_first_rock_produces_iron():
    """A 2m C-type rock must yield meaningful iron."""
    iron = iron_from_rock(2.0)
    assert iron > 500  # At least 500 kg


def test_iron_can_build_bigger_shell():
    """Iron from a 2m rock must contain a bigger rock."""
    iron = iron_from_rock(2.0)
    next_d = max_rock_for_iron(iron * 0.65)
    assert next_d > 2.0  # Must grow


def test_exponential_growth():
    """Each generation must produce a bigger rock capacity."""
    gens = run_bootstrap(max_steps=5)
    for i in range(1, len(gens)):
        assert gens[i].rock_diameter_m > gens[i - 1].rock_diameter_m


def test_reaches_10m_in_reasonable_time():
    """Must reach 10m scale within 5 years."""
    gens = run_bootstrap(max_steps=10)
    reached_10m = [g for g in gens if g.rock_diameter_m >= 9]
    assert len(reached_10m) > 0
    first_10m = reached_10m[0]
    assert first_10m.cumulative_days / 365.25 < 5


def test_concentrators_grow():
    """Concentrator array must grow each generation."""
    gens = run_bootstrap(max_steps=5)
    for i in range(1, len(gens)):
        assert gens[i].concentrator_m2 > gens[i - 1].concentrator_m2


def test_deposition_rate_increases():
    """Deposition rate must increase after first generation."""
    gens = run_bootstrap(max_steps=4)
    assert gens[-1].dep_rate_kg_day > gens[0].dep_rate_kg_day


def test_format_report_no_crash():
    """Report formatter must not crash."""
    gens = run_bootstrap(max_steps=4)
    report = format_report(gens)
    assert "GARBAGE BAG" in report
    assert "FINAL STATE" in report


def test_custom_first_rock():
    """Must work with different starting rock sizes."""
    seed = SeedPackage(first_rock_m=3.0)
    gens = run_bootstrap(seed=seed, max_steps=4)
    assert gens[0].rock_diameter_m == 3.0
    assert len(gens) >= 2
