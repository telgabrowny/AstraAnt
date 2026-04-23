"""Tests for patterned electrodeposition simulator."""

from __future__ import annotations

import numpy as np
import pytest

from astraant.deposition_sim import (
    COPPER_KINETICS,
    COPPER_SULFATE,
    IRON_KINETICS,
    IRON_SULFATE,
    DepositionConfig,
    ElectrodeKinetics,
    SimSnapshot,
    _compute_current_density,
    _solve_potential,
    compare_gravity,
    compute_wagner_number,
    make_channel_mask,
    make_ibeam_mask,
    make_rectangular_mask,
    run_pool_simulation,
    run_simulation,
)


def _quick_config(**overrides) -> DepositionConfig:
    """Small fast config for unit tests."""
    defaults = dict(
        width_mm=10.0,
        gap_mm=2.0,
        nx=50,
        nz=25,
        voltage_v=0.3,
        duration_s=60.0,
        dt_s=0.1,
        snapshot_interval_s=30.0,
        pattern=[(0.2, 0.8)],
        gravity_m_s2=0.0,
    )
    defaults.update(overrides)
    return DepositionConfig(**defaults)


# ---------------------------------------------------------------
# Potential field
# ---------------------------------------------------------------
class TestPotentialField:

    def test_cathode_grounded(self):
        cfg = _quick_config()
        phi = _solve_potential(cfg)
        np.testing.assert_allclose(phi[:, 0], 0.0, atol=1e-10)

    def test_active_electrode_at_voltage(self):
        cfg = _quick_config()
        phi = _solve_potential(cfg)
        mask = cfg.electrode_mask()
        np.testing.assert_allclose(
            phi[mask, -1], cfg.voltage_v, atol=1e-6,
        )

    def test_potential_monotonic_full_coverage(self):
        cfg = _quick_config(pattern=[(0.0, 1.0)])
        phi = _solve_potential(cfg)
        for i in range(2, cfg.nx - 2):
            assert np.all(np.diff(phi[i, :]) >= -1e-10), (
                f"Potential not monotonic at x index {i}"
            )

    def test_potential_shape(self):
        cfg = _quick_config()
        phi = _solve_potential(cfg)
        assert phi.shape == (cfg.nx, cfg.nz)


# ---------------------------------------------------------------
# Deposition behavior
# ---------------------------------------------------------------
class TestDeposition:

    def test_no_voltage_no_deposition(self):
        cfg = _quick_config(voltage_v=0.0)
        results = run_simulation(cfg, COPPER_SULFATE)
        assert np.max(results[-1].deposit_um) < 1e-6

    def test_deposit_grows_with_time(self):
        cfg = _quick_config(duration_s=120.0, snapshot_interval_s=60.0)
        results = run_simulation(cfg, COPPER_SULFATE)
        assert len(results) >= 2
        assert results[-1].deposit_mean_um > results[0].deposit_mean_um

    def test_concentration_stays_positive(self):
        cfg = _quick_config(duration_s=120.0)
        results = run_simulation(cfg, COPPER_SULFATE)
        for snap in results:
            assert np.all(snap.concentration >= 0.0), (
                f"Negative concentration at t={snap.time_s}s"
            )

    def test_uniform_electrode_uniform_deposit_0g(self):
        cfg = _quick_config(pattern=[(0.0, 1.0)], duration_s=60.0)
        results = run_simulation(cfg, COPPER_SULFATE)
        final = results[-1]
        interior = final.deposit_um[5:-5]
        std = float(np.std(interior))
        mean = float(np.mean(interior))
        assert mean > 0.001, "Deposit should be non-zero"
        uniformity = 100.0 * (1.0 - std / mean) if mean > 0 else 100.0
        assert uniformity > 95.0, (
            f"Uniformity {uniformity:.1f}% < 95% for full-coverage 0g"
        )

    def test_snapshot_count(self):
        cfg = _quick_config(duration_s=60.0, snapshot_interval_s=20.0)
        results = run_simulation(cfg, COPPER_SULFATE)
        assert len(results) >= 3


# ---------------------------------------------------------------
# Pattern fidelity
# ---------------------------------------------------------------
class TestPattern:

    def test_deposit_concentrated_under_active(self):
        cfg = _quick_config(
            pattern=[(0.3, 0.7)], gap_mm=0.5, nz=25,
            duration_s=30.0, snapshot_interval_s=30.0,
        )
        results = run_simulation(cfg, COPPER_SULFATE)
        final = results[-1]
        mask = cfg.electrode_mask()
        active_mean = float(np.mean(final.deposit_um[mask]))
        inactive_mean = float(np.mean(final.deposit_um[~mask]))
        assert active_mean > 2 * inactive_mean, (
            f"Active ({active_mean:.4f}) should be >> inactive ({inactive_mean:.4f})"
        )

    def test_electrode_mask_shape(self):
        cfg = _quick_config()
        mask = cfg.electrode_mask()
        assert mask.shape == (cfg.nx,)
        assert mask.dtype == bool

    def test_electrode_mask_coverage(self):
        cfg = _quick_config(pattern=[(0.0, 0.5)])
        mask = cfg.electrode_mask()
        frac = np.sum(mask) / len(mask)
        assert 0.45 < frac < 0.55


# ---------------------------------------------------------------
# Gravity comparison
# ---------------------------------------------------------------
class TestGravityComparison:

    def test_zero_g_more_uniform(self):
        cfg = _quick_config(duration_s=300.0, snapshot_interval_s=300.0)
        r0, r1 = compare_gravity(COPPER_SULFATE, cfg)
        f0 = r0[-1]
        f1 = r1[-1]
        assert f0.uniformity_pct > f1.uniformity_pct, (
            f"0g uniformity ({f0.uniformity_pct:.1f}%) should exceed "
            f"1g ({f1.uniformity_pct:.1f}%)"
        )

    def test_one_g_deposits_more(self):
        cfg = _quick_config(duration_s=300.0, snapshot_interval_s=300.0)
        r0, r1 = compare_gravity(COPPER_SULFATE, cfg)
        assert r1[-1].deposit_mean_um > r0[-1].deposit_mean_um, (
            f"1g ({r1[-1].deposit_mean_um:.4f} um) should exceed "
            f"0g ({r0[-1].deposit_mean_um:.4f} um)"
        )

    def test_both_produce_deposit(self):
        cfg = _quick_config(duration_s=120.0, snapshot_interval_s=120.0)
        r0, r1 = compare_gravity(COPPER_SULFATE, cfg)
        assert r0[-1].deposit_mean_um > 0.001
        assert r1[-1].deposit_mean_um > 0.001


# ---------------------------------------------------------------
# Snapshot properties
# ---------------------------------------------------------------
class TestSnapshot:

    def test_uniformity_range(self):
        snap = SimSnapshot(
            time_s=0,
            concentration=np.ones((10, 10)),
            potential=np.zeros((10, 10)),
            deposit_um=np.array([1.0, 1.0, 1.0, 1.0, 1.0]),
            current_density_a_m2=np.zeros(5),
        )
        assert snap.uniformity_pct == 100.0

    def test_uniformity_with_variation(self):
        dep = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        snap = SimSnapshot(
            time_s=0,
            concentration=np.ones((5, 5)),
            potential=np.zeros((5, 5)),
            deposit_um=dep,
            current_density_a_m2=np.zeros(5),
        )
        assert snap.uniformity_pct < 100.0
        assert snap.uniformity_pct > 0.0


# ---------------------------------------------------------------
# Geometry masks
# ---------------------------------------------------------------
class TestGeometryMask:

    def test_rectangular_mask_all_true(self):
        geo = make_rectangular_mask(50, 25)
        assert geo.shape == (50, 25)
        assert np.all(geo)

    def test_ibeam_mask_shape(self):
        geo = make_ibeam_mask(50, 30)
        assert geo.shape == (50, 30)
        assert not np.all(geo), "I-beam should not fill entire rectangle"

    def test_ibeam_mask_symmetric(self):
        geo = make_ibeam_mask(50, 30)
        cx = 25
        for j in range(30):
            left = geo[:cx, j]
            right = geo[cx:, j][::-1]
            min_len = min(len(left), len(right))
            np.testing.assert_array_equal(left[:min_len], right[:min_len],
                                          err_msg=f"Asymmetric at z={j}")

    def test_ibeam_flanges_wider_than_web(self):
        geo = make_ibeam_mask(50, 30, flange_width_frac=1.0, web_width_frac=0.3)
        flange_width = int(np.sum(geo[:, 0]))   # bottom row
        web_width = int(np.sum(geo[:, 15]))      # middle row
        assert flange_width > web_width

    def test_channel_mask(self):
        geo = make_channel_mask(50, 25, channel_width_frac=0.5)
        assert geo.shape == (50, 25)
        assert np.sum(geo[:, 0]) < 50  # not full width

    def test_rectangular_mask_same_as_no_mask(self):
        """Full rectangular mask should produce same results as no mask."""
        cfg = _quick_config(pattern=[(0.0, 1.0)], duration_s=30.0,
                            snapshot_interval_s=30.0)
        geo = make_rectangular_mask(cfg.nx, cfg.nz)
        r_nomask = run_simulation(cfg, COPPER_SULFATE)
        r_mask = run_simulation(cfg, COPPER_SULFATE, geometry_mask=geo)
        np.testing.assert_allclose(
            r_nomask[-1].deposit_um, r_mask[-1].deposit_um, rtol=0.05,
        )


# ---------------------------------------------------------------
# Pool simulation
# ---------------------------------------------------------------
class TestPoolSimulation:

    def test_ibeam_produces_results(self):
        snaps, geo = run_pool_simulation(
            "ibeam", IRON_SULFATE,
            config=DepositionConfig(
                width_mm=20.0, gap_mm=12.0, nx=40, nz=24,
                voltage_v=0.3, duration_s=30.0, dt_s=0.1,
                snapshot_interval_s=30.0, pattern=[(0.0, 1.0)],
            ),
        )
        assert len(snaps) >= 1
        assert geo.shape == (40, 24)
        assert snaps[-1].deposit_mean_um > 0

    def test_ibeam_current_nonuniform(self):
        """Web center should have higher current than flange tips (shorter path to anode)."""
        cfg = DepositionConfig(
            width_mm=20.0, gap_mm=12.0, nx=60, nz=30,
            voltage_v=0.3, duration_s=10.0, dt_s=0.1,
            snapshot_interval_s=10.0, pattern=[(0.0, 1.0)],
        )
        geo = make_ibeam_mask(60, 30, flange_width_frac=1.0, web_width_frac=0.3)
        snaps = run_simulation(cfg, IRON_SULFATE, geometry_mask=geo)
        j = snaps[-1].current_density_a_m2
        cathode = geo[:, 0]
        j_active = j[cathode]
        j_max = float(np.max(j_active))
        j_min = float(np.min(j_active[j_active > 0.01]))
        assert j_max > 2 * j_min, (
            f"Current should be non-uniform: max={j_max:.2f}, min={j_min:.2f}"
        )

    def test_no_deposit_outside_geometry(self):
        cfg = DepositionConfig(
            width_mm=20.0, gap_mm=12.0, nx=40, nz=24,
            voltage_v=0.3, duration_s=30.0, dt_s=0.1,
            snapshot_interval_s=30.0, pattern=[(0.0, 1.0)],
        )
        geo = make_channel_mask(40, 24, channel_width_frac=0.5)
        snaps = run_simulation(cfg, IRON_SULFATE, geometry_mask=geo)
        outside_cathode = ~geo[:, 0]
        assert np.all(snaps[-1].deposit_um[outside_cathode] < 1e-6)


# ---------------------------------------------------------------
# Butler-Volmer kinetics
# ---------------------------------------------------------------
class TestButlerVolmer:

    def test_kinetics_dataclass(self):
        ek = ElectrodeKinetics(j0_a_m2=5.0, alpha_a=0.4, alpha_c=0.6)
        assert ek.j0_a_m2 == 5.0
        assert ek.alpha_a == 0.4

    def test_wagner_number_positive(self):
        cfg = _quick_config()
        wa = compute_wagner_number(COPPER_SULFATE, COPPER_KINETICS, cfg)
        assert wa > 0

    def test_higher_j0_gives_lower_wagner(self):
        """Higher j0 = faster kinetics = less activation resistance = lower Wa."""
        cfg = _quick_config()
        wa_low = compute_wagner_number(COPPER_SULFATE,
                                        ElectrodeKinetics(j0_a_m2=0.1), cfg)
        wa_high = compute_wagner_number(COPPER_SULFATE,
                                         ElectrodeKinetics(j0_a_m2=100.0), cfg)
        assert wa_low > wa_high

    def test_bv_produces_deposit(self):
        cfg = DepositionConfig(
            width_mm=10.0, gap_mm=5.0, nx=30, nz=15,
            voltage_v=0.3, duration_s=30.0, dt_s=0.1,
            snapshot_interval_s=30.0, pattern=[(0.0, 1.0)],
        )
        results = run_simulation(cfg, IRON_SULFATE, kinetics=IRON_KINETICS)
        assert results[-1].deposit_mean_um > 0

    def test_no_kinetics_same_as_primary(self):
        """kinetics=None should give same result as before."""
        cfg = _quick_config(pattern=[(0.0, 1.0)], duration_s=30.0,
                            snapshot_interval_s=30.0)
        r1 = run_simulation(cfg, COPPER_SULFATE)
        r2 = run_simulation(cfg, COPPER_SULFATE, kinetics=None)
        np.testing.assert_allclose(
            r1[-1].deposit_um, r2[-1].deposit_um, rtol=1e-10,
        )
