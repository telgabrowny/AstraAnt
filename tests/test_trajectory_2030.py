"""Tests for the 2030-launch trajectory design module."""

import math

import pytest

from astraant.trajectory_2030 import (
    _solve_kepler,
    _true_anomaly,
    _orbital_pos_au,
    _earth_pos_au,
    _asteroid_pos_au,
    _earth_vel_km_s,
    _hohmann_dv,
    _low_thrust_transfer_dv,
    _lambert_dv_estimate,
    _propellant_for_dv,
    _year_frac_to_date,
    _date_to_year_frac,
    _survey_asteroid,
    _evaluate_asteroid,
    compute_trajectory_2030,
    format_trajectory_report,
    TOTAL_DV,
    WET_MASS_KG,
    DRY_MASS_KG,
    PROPELLANT_KG,
    ISP_S,
    VE,
    DV_AVAILABLE_HELIO,
    AU,
    MU_SUN,
)
from astraant.catalog import Catalog


# -----------------------------------------------------------------------
# Kepler solver
# -----------------------------------------------------------------------

class TestKeplerSolver:
    """Test the Kepler equation solver."""

    def test_circular_orbit(self):
        """For e=0, eccentric anomaly equals mean anomaly."""
        M = 1.23
        E = _solve_kepler(M, 0.0)
        assert abs(E - M) < 1e-10

    def test_known_values(self):
        """Check against known M, e, E solutions."""
        # e=0.5, M=pi/4 => iterate to convergence
        M = math.pi / 4
        e = 0.5
        E = _solve_kepler(M, e)
        # Verify: M = E - e*sin(E)
        residual = E - e * math.sin(E) - M
        assert abs(residual) < 1e-12

    def test_high_eccentricity(self):
        """Solver converges for high eccentricity."""
        M = 0.5
        e = 0.9
        E = _solve_kepler(M, e)
        residual = E - e * math.sin(E) - M
        assert abs(residual) < 1e-10

    def test_true_anomaly_perihelion(self):
        """At perihelion (E=0), true anomaly is 0."""
        nu = _true_anomaly(0.0, 0.3)
        assert abs(nu) < 1e-12

    def test_true_anomaly_aphelion(self):
        """At aphelion (E=pi), true anomaly is pi."""
        nu = _true_anomaly(math.pi, 0.3)
        assert abs(nu - math.pi) < 1e-10


# -----------------------------------------------------------------------
# Earth position
# -----------------------------------------------------------------------

class TestEarthPosition:
    """Test Earth position calculations."""

    def test_earth_near_1_au(self):
        """Earth should always be near 1 AU from the Sun."""
        for year in [2025.0, 2028.5, 2030.0, 2035.7]:
            x, y, z, r = _earth_pos_au(year)
            assert 0.95 < r < 1.05, f"Earth at {year}: r={r} AU (expected ~1)"

    def test_earth_orbits(self):
        """Earth position should change over a year."""
        p1 = _earth_pos_au(2030.0)
        p2 = _earth_pos_au(2030.5)
        # Should be in different positions
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(p1[:3], p2[:3])))
        assert dist > 0.5, "Earth should move significantly in 6 months"

    def test_earth_velocity_magnitude(self):
        """Earth orbital velocity should be ~29.8 km/s."""
        vx, vy, vz = _earth_vel_km_s(2030.0)
        v_mag = math.sqrt(vx ** 2 + vy ** 2 + vz ** 2)
        assert 28.0 < v_mag < 32.0, f"Earth v={v_mag} km/s (expected ~29.8)"


# -----------------------------------------------------------------------
# Asteroid positions
# -----------------------------------------------------------------------

class TestAsteroidPositions:
    """Test asteroid position propagation."""

    @pytest.fixture
    def catalog(self):
        return Catalog()

    def test_bennu_distance_range(self, catalog):
        """Bennu should be between 0.9 and 1.36 AU (peri/aphelion)."""
        ast = catalog.get_asteroid("bennu")
        for yr in [2029.0, 2030.0, 2031.0]:
            x, y, z, r = _asteroid_pos_au(ast, yr)
            assert 0.85 < r < 1.40, f"Bennu at {yr}: r={r} AU"

    def test_psyche_far_from_earth(self, catalog):
        """Psyche (main belt) should be at ~2.5-3.3 AU."""
        ast = catalog.get_asteroid("psyche")
        x, y, z, r = _asteroid_pos_au(ast, 2030.0)
        assert 2.4 < r < 3.4, f"Psyche at 2030: r={r} AU"

    def test_ev5_near_earth(self, catalog):
        """2008 EV5 (Aten class) should be near 0.88-1.04 AU."""
        ast = catalog.get_asteroid("2008_ev5")
        x, y, z, r = _asteroid_pos_au(ast, 2030.0)
        assert 0.85 < r < 1.10, f"EV5 at 2030: r={r} AU"


# -----------------------------------------------------------------------
# Transfer delta-V
# -----------------------------------------------------------------------

class TestTransferDeltaV:
    """Test transfer delta-V calculations."""

    def test_hohmann_earth_to_mars(self):
        """Earth-Mars Hohmann dV should be ~0.9 + 0.9 km/s."""
        dv1, dv2, tof = _hohmann_dv(1.0, 1.524)
        assert 0.5 < dv1 < 4.0, f"Departure dV: {dv1}"
        assert 0.5 < dv2 < 4.0, f"Arrival dV: {dv2}"
        assert 200 < tof < 300, f"Transfer time: {tof} days"

    def test_hohmann_same_orbit(self):
        """Same orbit should require zero dV."""
        dv1, dv2, tof = _hohmann_dv(1.0, 1.0)
        assert dv1 < 0.001
        assert dv2 < 0.001

    def test_low_thrust_nearby(self):
        """Transfer to similar orbit should be cheap."""
        dv = _low_thrust_transfer_dv(1.0, 1.05, 2.0, 300)
        assert 0.0 < dv < 3.0, f"Low-thrust dV to nearby orbit: {dv}"

    def test_low_thrust_far(self):
        """Transfer to 3 AU should be expensive."""
        dv = _low_thrust_transfer_dv(1.0, 3.0, 3.0, 700)
        assert dv > 5.0, f"Low-thrust dV to 3 AU: {dv}"

    def test_low_thrust_inclination_costs(self):
        """Higher inclination should cost more dV."""
        dv_low = _low_thrust_transfer_dv(1.0, 1.1, 2.0, 400)
        dv_high = _low_thrust_transfer_dv(1.0, 1.1, 15.0, 400)
        assert dv_high > dv_low, "Higher inclination should cost more"

    def test_lambert_returns_positive(self):
        """Lambert estimate should return positive dV values."""
        dv_dep, dv_arr = _lambert_dv_estimate(
            (1.0, 0.0, 0.0), (1.1, 0.3, 0.01),
            (0, 29.78, 0), (0, 28.5, 0),
            300, inc_target_deg=5.0,
        )
        assert dv_dep >= 0
        assert dv_arr >= 0


# -----------------------------------------------------------------------
# Propellant
# -----------------------------------------------------------------------

class TestPropellant:
    """Test propellant calculations."""

    def test_tsiolkovsky_total(self):
        """Total dV from Tsiolkovsky should match the constant."""
        dv = VE * math.log(WET_MASS_KG / DRY_MASS_KG)
        assert abs(dv - TOTAL_DV) < 0.1

    def test_propellant_zero_dv(self):
        """Zero dV requires zero propellant."""
        p = _propellant_for_dv(0.0, 41.0)
        assert p == 0.0

    def test_propellant_positive(self):
        """Positive dV requires positive propellant."""
        p = _propellant_for_dv(500.0, 41.0)
        assert 0 < p < 5.0

    def test_propellant_total_equals_budget(self):
        """Using all dV should consume all propellant."""
        p = _propellant_for_dv(TOTAL_DV, WET_MASS_KG)
        assert abs(p - PROPELLANT_KG) < 0.01

    def test_propellant_monotonic(self):
        """More dV requires more propellant."""
        p1 = _propellant_for_dv(500.0, 41.0)
        p2 = _propellant_for_dv(1000.0, 41.0)
        assert p2 > p1


# -----------------------------------------------------------------------
# Date utilities
# -----------------------------------------------------------------------

class TestDateUtilities:
    """Test date conversion functions."""

    def test_roundtrip(self):
        """Year fraction -> date -> year fraction should be close."""
        yr = 2030.5
        date_str = _year_frac_to_date(yr)
        yr2 = _date_to_year_frac(date_str)
        assert abs(yr - yr2) < 0.1  # within ~1 month

    def test_date_format(self):
        """Date string should be YYYY-MM-DD."""
        s = _year_frac_to_date(2030.0)
        assert len(s) == 10
        assert s[4] == "-" and s[7] == "-"

    def test_year_start(self):
        """Year 2030.0 should give January."""
        s = _year_frac_to_date(2030.0)
        assert s.startswith("2030-01")


# -----------------------------------------------------------------------
# Asteroid survey
# -----------------------------------------------------------------------

class TestAsteroidSurvey:
    """Test the full asteroid survey pipeline."""

    @pytest.fixture
    def catalog(self):
        return Catalog()

    def test_survey_returns_windows(self, catalog):
        """Survey should return transfer windows."""
        ast = catalog.get_asteroid("bennu")
        windows = _survey_asteroid(ast, 2029.5, 2031.5)
        assert len(windows) > 0

    def test_survey_window_fields(self, catalog):
        """Each window should have required fields."""
        ast = catalog.get_asteroid("bennu")
        windows = _survey_asteroid(ast, 2029.5, 2030.5, step_months=3)
        w = windows[0]
        assert w.asteroid_id == "bennu"
        assert w.tof_days > 0
        assert w.dv_total_km_s > 0
        assert w.asteroid_r_au > 0

    def test_survey_has_feasible_windows(self, catalog):
        """At least one NEA should have feasible windows."""
        budget = DV_AVAILABLE_HELIO / 1000.0
        found_feasible = False
        for ast in catalog.asteroids:
            dv = ast.get("mining_relevance", {}).get(
                "accessibility", {}).get("delta_v_from_leo_km_per_s", 99)
            if dv > 8:
                continue  # skip main belt
            windows = _survey_asteroid(ast, 2029.5, 2031.5)
            for w in windows:
                if w.dv_total_km_s <= budget:
                    found_feasible = True
                    break
            if found_feasible:
                break
        assert found_feasible, "No feasible windows found for any NEA"


# -----------------------------------------------------------------------
# Candidate evaluation
# -----------------------------------------------------------------------

class TestCandidateEvaluation:
    """Test asteroid candidate scoring."""

    @pytest.fixture
    def catalog(self):
        return Catalog()

    def test_c_type_scores_higher_than_s_type(self, catalog):
        """C-type asteroids should score higher than S-type (water)."""
        bennu = catalog.get_asteroid("bennu")
        itokawa = catalog.get_asteroid("itokawa")

        w_bennu = _survey_asteroid(bennu, 2029.5, 2031.5)
        w_itokawa = _survey_asteroid(itokawa, 2029.5, 2031.5)

        c_bennu = _evaluate_asteroid(bennu, w_bennu)
        c_itokawa = _evaluate_asteroid(itokawa, w_itokawa)

        assert c_bennu.composition_score > c_itokawa.composition_score

    def test_psyche_infeasible(self, catalog):
        """Psyche (main belt) should be scored as infeasible."""
        psyche = catalog.get_asteroid("psyche")
        windows = _survey_asteroid(psyche, 2029.5, 2031.5)
        cand = _evaluate_asteroid(psyche, windows)
        assert not cand.feasible

    def test_scores_in_range(self, catalog):
        """All scores should be 0-100."""
        for ast in catalog.asteroids:
            windows = _survey_asteroid(ast, 2030.0, 2031.0, step_months=6)
            cand = _evaluate_asteroid(ast, windows)
            assert 0 <= cand.dv_score <= 100
            assert 0 <= cand.composition_score <= 100
            assert 0 <= cand.solar_score <= 100
            assert 0 <= cand.time_score <= 100


# -----------------------------------------------------------------------
# Full trajectory computation
# -----------------------------------------------------------------------

class TestFullTrajectory:
    """Test the complete trajectory computation."""

    @pytest.fixture
    def design(self):
        return compute_trajectory_2030(launch_year=2030)

    def test_design_returns_result(self, design):
        """Should return a TrajectoryDesign object."""
        assert design is not None
        assert design.target is not None

    def test_selected_target_is_feasible(self, design):
        """Selected target should be feasible if any are."""
        feasible_count = sum(1 for c in design.all_candidates if c.feasible)
        if feasible_count > 0:
            assert design.target.feasible

    def test_dv_budget_check(self, design):
        """Total dV should not massively exceed budget."""
        # Allow 50% overshoot (model is +/- 30% accurate)
        assert design.dv_total < design.dv_budget * 1.5

    def test_propellant_physical(self, design):
        """Propellant usage should be physically reasonable."""
        assert design.prop_total_kg > 0
        assert design.prop_total_kg <= PROPELLANT_KG * 1.5  # allow some overshoot

    def test_seven_candidates(self, design):
        """Should evaluate all 7 catalog asteroids."""
        assert len(design.all_candidates) == 7

    def test_candidates_sorted_by_score(self, design):
        """Candidates should be sorted by score (descending)."""
        scores = [c.total_score for c in design.all_candidates]
        assert scores == sorted(scores, reverse=True)

    def test_arrival_solar_flux(self, design):
        """Solar flux at arrival should be positive and reasonable."""
        assert design.solar_power_w_per_m2 > 0
        # Should be between 10% (3 AU) and 200% (0.7 AU) of 1 AU
        assert 100 < design.solar_power_w_per_m2 < 3000

    def test_tof_reasonable(self, design):
        """Transfer time should be under 2 years."""
        assert 30 < design.tof_days < 730

    def test_launch_date_in_range(self, design):
        """Launch date should be within the search window."""
        yr = _date_to_year_frac(design.launch_date)
        assert 2029.0 < yr < 2032.0


# -----------------------------------------------------------------------
# Report formatting
# -----------------------------------------------------------------------

class TestReportFormatting:
    """Test the report output."""

    @pytest.fixture
    def report(self):
        design = compute_trajectory_2030(launch_year=2030)
        return format_trajectory_report(design)

    def test_report_is_string(self, report):
        assert isinstance(report, str)

    def test_report_contains_key_sections(self, report):
        assert "SPACECRAFT" in report
        assert "SELECTED TARGET" in report
        assert "TRANSFER ORBIT" in report
        assert "DELTA-V BREAKDOWN" in report
        assert "PROPELLANT BREAKDOWN" in report
        assert "ARRIVAL CONDITIONS" in report
        assert "MISSION TIMELINE" in report
        assert "ALL CANDIDATES COMPARISON" in report

    def test_ascii_only(self, report):
        """Report should be ASCII-only (Windows cp1252 compatibility)."""
        for i, ch in enumerate(report):
            assert ord(ch) < 128, (
                f"Non-ASCII char at position {i}: {ch!r} (ord={ord(ch)})"
            )

    def test_report_contains_target_name(self, report):
        """Report should mention the selected asteroid by name."""
        # At least one catalog asteroid name should appear
        names = ["Bennu", "Ryugu", "Itokawa", "Eros", "Psyche", "EV5", "Didymos"]
        assert any(n in report for n in names)

    def test_different_launch_year(self):
        """Should work with a different launch year."""
        design = compute_trajectory_2030(launch_year=2032)
        report = format_trajectory_report(design)
        assert "TRAJECTORY" in report
        assert len(design.all_candidates) == 7


# -----------------------------------------------------------------------
# Physical sanity checks
# -----------------------------------------------------------------------

class TestPhysicsSanity:
    """Verify the physics constants and computations are sane."""

    def test_total_dv_in_range(self):
        """5 kg iodine at 2200s Isp should give ~2800 m/s."""
        assert 2500 < TOTAL_DV < 3200

    def test_dv_available_helio(self):
        """Heliocentric budget should be less than total."""
        assert DV_AVAILABLE_HELIO < TOTAL_DV
        assert DV_AVAILABLE_HELIO > 0

    def test_earth_orbital_speed(self):
        """Earth orbital speed should be ~29.78 km/s."""
        v = math.sqrt(MU_SUN / (1.0 * AU)) / 1000.0
        assert 29.0 < v < 31.0

    def test_hohmann_earth_mars_tof(self):
        """Earth-Mars Hohmann should be ~259 days."""
        _, _, tof = _hohmann_dv(1.0, 1.524)
        assert 240 < tof < 280

    def test_wet_dry_mass_consistent(self):
        """Wet - dry = propellant."""
        assert abs(WET_MASS_KG - DRY_MASS_KG - PROPELLANT_KG) < 0.001
