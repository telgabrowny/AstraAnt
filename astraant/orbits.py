"""Orbital mechanics -- real asteroid positions and redirection modeling.

Uses Keplerian orbital elements from the asteroid catalog to compute
positions at specific dates. Models slow orbital modification via
continuous ion thrust over years.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .catalog import Catalog


# Constants
AU_TO_KM = 1.496e8
YEAR_TO_SEC = 365.25 * 86400
MU_SUN = 1.327e11  # km^3/s^2, gravitational parameter of the Sun


@dataclass
class OrbitalState:
    """Position and velocity of an object at a specific time."""
    epoch: str               # Date string
    semi_major_axis_au: float
    eccentricity: float
    inclination_deg: float
    perihelion_au: float
    aphelion_au: float
    period_years: float
    # Computed position
    true_anomaly_deg: float = 0.0
    heliocentric_distance_au: float = 1.0
    solar_power_factor: float = 1.0  # 1/r^2 relative to 1 AU


@dataclass
class RedirectionResult:
    """Result of asteroid redirection analysis."""
    asteroid_name: str
    asteroid_mass_kg: float
    fleet_thrust_n: float
    duration_years: float
    delta_v_m_per_s: float
    orbital_period_change_s: float
    semi_major_axis_change_km: float
    feasibility: str          # "trivial", "feasible", "decades", "impractical"
    notes: list[str]


def get_orbital_state(asteroid_id: str, date_str: str = "2030-01-01",
                      catalog: Catalog | None = None) -> OrbitalState | None:
    """Get the orbital state of an asteroid at a given date.

    Uses mean anomaly propagation from catalog orbital elements.
    """
    if catalog is None:
        catalog = Catalog()

    ast = catalog.get_asteroid(asteroid_id)
    if ast is None:
        return None

    orbit = ast.get("orbit", {})
    phys = ast.get("physical", {})

    a = orbit.get("semi_major_axis_au", 1.0)
    e = orbit.get("eccentricity", 0.0)
    i = orbit.get("inclination_deg", 0.0)
    period = orbit.get("orbital_period_years", 1.0)

    # Mean anomaly at epoch (simplified -- assume epoch is 2025-01-01)
    # Propagate forward to requested date
    try:
        year_parts = date_str.split("-")
        target_year = float(year_parts[0]) + float(year_parts[1]) / 12
    except (ValueError, IndexError):
        target_year = 2030.0

    epoch_year = 2025.0
    elapsed_years = target_year - epoch_year
    # Mean anomaly advances by 360/period degrees per year
    mean_anomaly_deg = (elapsed_years / period * 360) % 360

    # Solve Kepler's equation for true anomaly (simplified -- use mean anomaly as approx)
    # For low eccentricity this is close enough
    E_rad = math.radians(mean_anomaly_deg)  # Eccentric anomaly approx
    for _ in range(10):  # Newton's method for Kepler's equation
        E_rad = E_rad - (E_rad - e * math.sin(E_rad) - math.radians(mean_anomaly_deg)) / (1 - e * math.cos(E_rad))

    # True anomaly from eccentric anomaly
    true_anomaly = 2 * math.atan2(
        math.sqrt(1 + e) * math.sin(E_rad / 2),
        math.sqrt(1 - e) * math.cos(E_rad / 2),
    )
    true_anomaly_deg = math.degrees(true_anomaly) % 360

    # Heliocentric distance
    r_au = a * (1 - e * math.cos(E_rad))

    return OrbitalState(
        epoch=date_str,
        semi_major_axis_au=a,
        eccentricity=e,
        inclination_deg=i,
        perihelion_au=a * (1 - e),
        aphelion_au=a * (1 + e),
        period_years=period,
        true_anomaly_deg=true_anomaly_deg,
        heliocentric_distance_au=r_au,
        solar_power_factor=1.0 / (r_au ** 2),
    )


def analyze_redirection(asteroid_id: str, n_motherships: int = 16,
                        thrust_per_mothership_n: float = 2.0,
                        duration_years: float = 5.0,
                        power_source: str = "nuclear_10kw",
                        catalog: Catalog | None = None) -> RedirectionResult:
    """Analyze the feasibility of redirecting an asteroid with ion thrusters."""
    if catalog is None:
        catalog = Catalog()

    ast = catalog.get_asteroid(asteroid_id)
    if ast is None:
        return RedirectionResult(
            asteroid_name=asteroid_id, asteroid_mass_kg=0,
            fleet_thrust_n=0, duration_years=0,
            delta_v_m_per_s=0, orbital_period_change_s=0,
            semi_major_axis_change_km=0, feasibility="unknown",
            notes=["Asteroid not found in catalog"],
        )

    name = ast.get("name", asteroid_id)
    phys = ast.get("physical", {})
    mass_raw = phys.get("mass_kg", 1e10)
    mass_kg = float(mass_raw) if mass_raw else 1e10
    diameter_m = phys.get("diameter_m", 500)
    orbit = ast.get("orbit", {})
    a_au = orbit.get("semi_major_axis_au", 1.0)
    period_yr = orbit.get("orbital_period_years", 1.0)

    # Power source affects available thrust
    if power_source == "solar":
        r_au = a_au
        solar_factor = 1.0 / (r_au ** 2)
        effective_thrust = thrust_per_mothership_n * solar_factor
        notes = [f"Solar power at {r_au:.1f} AU: {solar_factor*100:.0f}% of 1 AU output"]
    else:
        effective_thrust = thrust_per_mothership_n
        notes = [f"Nuclear power: constant thrust regardless of solar distance"]

    fleet_thrust = effective_thrust * n_motherships

    # Delta-v over duration
    accel = fleet_thrust / mass_kg
    duration_s = duration_years * YEAR_TO_SEC
    delta_v = accel * duration_s

    # Orbital effects (vis-viva approximation)
    # dv applied tangentially changes semi-major axis:
    # da/a ~= 2 * dv / v_orbital
    v_orbital = math.sqrt(MU_SUN / (a_au * AU_TO_KM)) * 1000  # m/s
    da_fraction = 2 * delta_v / v_orbital
    da_km = da_fraction * a_au * AU_TO_KM

    # Period change: dT/T = 1.5 * da/a
    dT_fraction = 1.5 * da_fraction
    dT_seconds = dT_fraction * period_yr * YEAR_TO_SEC

    # Feasibility assessment
    if delta_v > 10:
        feasibility = "trivial"
        notes.append(f"Large delta-v ({delta_v:.1f} m/s) -- can redirect to any nearby orbit")
    elif delta_v > 1:
        feasibility = "feasible"
        notes.append(f"Meaningful delta-v ({delta_v:.2f} m/s) -- significant orbit modification")
    elif delta_v > 0.01:
        feasibility = "decades"
        notes.append(f"Small delta-v ({delta_v*1000:.1f} mm/s) -- useful over decades of pushing")
    else:
        feasibility = "impractical"
        notes.append(f"Negligible delta-v ({delta_v*1000:.3f} mm/s) -- asteroid too massive")

    # Size comparison
    if diameter_m < 50:
        notes.append(f"Small asteroid ({diameter_m}m) -- easy to redirect")
    elif diameter_m < 200:
        notes.append(f"Medium asteroid ({diameter_m}m) -- redirectable with patience")
    else:
        notes.append(f"Large asteroid ({diameter_m}m) -- mine in place, don't try to move")

    return RedirectionResult(
        asteroid_name=name,
        asteroid_mass_kg=mass_kg,
        fleet_thrust_n=fleet_thrust,
        duration_years=duration_years,
        delta_v_m_per_s=delta_v,
        orbital_period_change_s=dT_seconds,
        semi_major_axis_change_km=da_km,
        feasibility=feasibility,
        notes=notes,
    )


def format_orbital_report(state: OrbitalState, redirection: RedirectionResult | None = None) -> str:
    """Format orbital state and redirection analysis."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"ORBITAL ANALYSIS")
    lines.append("=" * 70)

    lines.append(f"\n--- ORBITAL STATE at {state.epoch} ---")
    lines.append(f"  Semi-major axis:    {state.semi_major_axis_au:.3f} AU")
    lines.append(f"  Eccentricity:       {state.eccentricity:.3f}")
    lines.append(f"  Inclination:        {state.inclination_deg:.1f} deg")
    lines.append(f"  Period:             {state.period_years:.3f} years")
    lines.append(f"  Perihelion:         {state.perihelion_au:.3f} AU")
    lines.append(f"  Aphelion:           {state.aphelion_au:.3f} AU")
    lines.append(f"  True anomaly:       {state.true_anomaly_deg:.1f} deg")
    lines.append(f"  Distance from Sun:  {state.heliocentric_distance_au:.3f} AU")
    lines.append(f"  Solar power factor: {state.solar_power_factor:.2f}x (vs 1 AU)")

    if redirection:
        r = redirection
        lines.append(f"\n--- REDIRECTION ANALYSIS ---")
        lines.append(f"  Asteroid: {r.asteroid_name}")
        lines.append(f"  Mass: {r.asteroid_mass_kg:.2e} kg")
        lines.append(f"  Fleet thrust: {r.fleet_thrust_n:.1f} N")
        lines.append(f"  Duration: {r.duration_years:.0f} years")
        lines.append(f"  Delta-v achieved: {r.delta_v_m_per_s*1000:.1f} mm/s ({r.delta_v_m_per_s:.4f} m/s)")
        lines.append(f"  Orbit period change: {r.orbital_period_change_s:.0f} seconds")
        lines.append(f"  Semi-major axis change: {r.semi_major_axis_change_km:.1f} km")
        lines.append(f"  Feasibility: {r.feasibility.upper()}")
        for note in r.notes:
            lines.append(f"    - {note}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
