"""Tests for the garbage bag bootstrap simulator."""

from astraant.bootstrap_sim import (
    SeedPackage, run_bootstrap, rock_mass, iron_from_rock, format_report,
)


def test_seed_fits_in_garbage_bag():
    """Seed package must be under 15 kg (fits in a hefty bag)."""
    seed = SeedPackage()
    assert seed.total_kg < 15


def test_mode_b_heavier_than_a():
    """Mode B (with arm) must be heavier than Mode A."""
    seed_a = SeedPackage()
    seed_b = SeedPackage(arm_kg=3.0)
    assert seed_b.total_kg > seed_a.total_kg


def test_first_rock_produces_iron():
    """A 2m C-type rock must yield meaningful iron."""
    iron = iron_from_rock(2.0)
    assert iron > 500  # At least 500 kg


def test_mode_a_grows_by_inflation():
    """Mode A: each generation grows by ~15% (iron ductility)."""
    gens = run_bootstrap(mode="A", max_steps=5)
    for i in range(1, len(gens)):
        ratio = gens[i].rock_diameter_m / gens[i - 1].rock_diameter_m
        assert 1.10 < ratio < 1.20  # ~15% growth


def test_mode_a_fixed_power():
    """Mode A: concentrator area stays at initial value (no fabrication)."""
    gens = run_bootstrap(mode="A", max_steps=5)
    for g in gens:
        assert g.concentrator_m2 == 0.5  # Fixed, can't build more


def test_mode_b_concentrators_grow():
    """Mode B: arm builds bigger concentrators each generation."""
    gens = run_bootstrap(mode="B", max_steps=4)
    for i in range(1, len(gens)):
        assert gens[i].concentrator_m2 > gens[i - 1].concentrator_m2


def test_mode_b_faster_than_a():
    """Mode B must reach 5m faster than Mode A."""
    gens_a = run_bootstrap(mode="A", max_steps=15, max_rock_m=6)
    gens_b = run_bootstrap(mode="B", max_steps=15, max_rock_m=6)
    time_a = gens_a[-1].cumulative_days
    time_b = gens_b[-1].cumulative_days
    assert time_b < time_a


def test_exponential_growth_mode_b():
    """Mode B: each generation must produce a bigger rock capacity."""
    gens = run_bootstrap(mode="B", max_steps=5)
    for i in range(1, len(gens)):
        assert gens[i].rock_diameter_m > gens[i - 1].rock_diameter_m


def test_seed_package_pv_watts():
    """PV watts = panel_m2 * 1361 * 0.20 = ~136W for default 0.5 m2."""
    seed = SeedPackage()
    expected = 0.5 * 1361 * 0.20  # 136.1 W
    assert abs(seed.pv_watts - expected) < 0.1


def test_seed_package_initial_current():
    """Initial current = pv_watts / cell_voltage (2.0V)."""
    seed = SeedPackage()
    expected = seed.pv_watts / 2.0
    assert abs(seed.initial_current_a - expected) < 0.01


def test_mode_a_power_fixed_forever():
    """Mode A: current_a stays the same across ALL generations (no fabrication)."""
    gens = run_bootstrap(mode="A", max_steps=8)
    first_current = gens[0].current_a
    for g in gens:
        assert g.current_a == first_current, (
            f"Step {g.step}: current_a={g.current_a} differs from "
            f"initial {first_current} -- Mode A should be fixed")


def test_mode_b_power_increases():
    """Mode B: current_a must increase after step 0 (arm builds concentrators)."""
    gens = run_bootstrap(mode="B", max_steps=5)
    initial_current = gens[0].current_a
    # At least one later generation must have higher current
    found_increase = any(g.current_a > initial_current for g in gens[1:])
    assert found_increase, (
        f"Mode B current never increased from {initial_current}A")


def test_format_report_no_crash():
    """Report formatter must not crash for any mode."""
    for m in ["A", "B", "C"]:
        gens = run_bootstrap(mode=m, max_steps=3)
        report = format_report(gens, mode=m)
        assert "BOOTSTRAP MODE" in report
        assert "RESULT" in report
