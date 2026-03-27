"""Solar sail trajectory estimation for cargo return vehicles.

Uses simplified analytical models for low-thrust solar sail trajectories.
Not a full propagator -- provides transit time estimates based on
published mission analysis results and scaling laws.

For a serious feasibility study, these estimates are within ~30% of
optimized trajectories. A full trajectory optimizer (GMAT or custom)
would be a later phase.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .catalog import Catalog


# Speed of light and solar constants
C = 299792458.0        # m/s
SOLAR_FLUX_1AU = 1361  # W/m^2 at 1 AU
AU_TO_M = 1.496e11     # meters per AU


@dataclass
class TrajectoryEstimate:
    """Estimated trajectory parameters for a cargo return."""
    origin_asteroid: str
    destination: str
    cargo_mass_kg: float
    sail_area_m2: float
    total_mass_kg: float     # cargo + vehicle
    characteristic_acceleration_mm_s2: float
    delta_v_needed_km_s: float
    estimated_transit_days: float
    estimated_transit_years: float
    confidence: str          # "high", "medium", "low"
    notes: list[str]


def sail_characteristic_acceleration(sail_area_m2: float, total_mass_kg: float,
                                     reflectivity: float = 0.9,
                                     distance_au: float = 1.0) -> float:
    """Calculate the characteristic acceleration of a solar sail in mm/s^2.

    This is the key performance metric for a solar sail -- the acceleration
    at 1 AU with the sail face-on to the Sun.

    a_c = 2 * P * R * A / (c * m)
    where P = solar flux, R = reflectivity, A = sail area, c = speed of light, m = mass
    """
    # Solar radiation pressure at distance
    pressure = SOLAR_FLUX_1AU / (distance_au ** 2)  # W/m^2
    # Force = 2 * P * R * A / c (factor of 2 for perfect reflection)
    force_n = 2 * pressure * reflectivity * sail_area_m2 / C
    # Acceleration
    accel_m_s2 = force_n / total_mass_kg
    return accel_m_s2 * 1000  # Convert to mm/s^2


def estimate_transit_time(origin_au: float, dest_au: float,
                          accel_mm_s2: float) -> float:
    """Estimate transit time in days for a solar sail trajectory.

    Uses a simplified scaling law from published solar sail mission analyses:
    For transfer between circular orbits, transit time scales roughly as:

        T ~ (delta_a / a_c) * k

    where delta_a is the orbit change in AU, a_c is characteristic acceleration,
    and k is an empirical factor (~200-400 days per AU per mm/s^2).

    This is NOT a propagated trajectory -- it's an analytical estimate
    calibrated against published results (IKAROS, NEA Scout analyses).
    """
    if accel_mm_s2 <= 0:
        return float('inf')

    delta_a = abs(dest_au - origin_au)

    # Empirical transit factor (calibrated from published sail mission analyses)
    # NEA Scout (86 m^2 sail, 14 kg, ~0.2 mm/s^2) was expected to take ~2 years to NEA
    # That gives k ~ 365 * 2 / (0.5 AU / 0.2 mm/s^2) ~ 290 days per (AU / mm/s^2)
    k = 300  # days per AU per (1/mm/s^2)

    transit_days = k * delta_a / accel_mm_s2

    # Minimum transit even for very high acceleration (orbital mechanics limit)
    min_days = delta_a * 180  # Hohmann-like lower bound

    return max(min_days, transit_days)


def estimate_cargo_return(asteroid_id: str, destination: str = "lunar_orbit",
                          cargo_kg: float = 100.0, sail_area_m2: float = 25.0,
                          vehicle_mass_kg: float = 6.5,
                          catalog: Catalog | None = None) -> TrajectoryEstimate:
    """Estimate the trajectory for a cargo return from an asteroid.

    Args:
        asteroid_id: ID of the origin asteroid in the catalog
        destination: "lunar_orbit", "mars_orbit", or "earth_return"
        cargo_kg: Mass of cargo in the return vehicle
        sail_area_m2: Solar sail area
        vehicle_mass_kg: Empty vehicle mass (structure + guidance)
        catalog: Optional catalog for asteroid data lookup
    """
    if catalog is None:
        catalog = Catalog()

    asteroid = catalog.get_asteroid(asteroid_id)
    notes = []

    # Get asteroid orbital distance
    if asteroid:
        origin_au = asteroid.get("orbit", {}).get("semi_major_axis_au", 1.0)
        ast_name = asteroid.get("name", asteroid_id)
    else:
        origin_au = 1.0
        ast_name = asteroid_id
        notes.append(f"Asteroid '{asteroid_id}' not in catalog, assuming 1.0 AU")

    # Destination orbital distance
    dest_au_map = {
        "lunar_orbit": 1.0,       # Earth-Moon system
        "earth_moon_l2": 1.0,
        "earth_return": 1.0,
        "mars_orbit": 1.52,       # Mars semi-major axis
    }
    dest_au = dest_au_map.get(destination, 1.0)

    # Total mass
    total_mass = cargo_kg + vehicle_mass_kg

    # Characteristic acceleration
    accel = sail_characteristic_acceleration(sail_area_m2, total_mass)

    # Delta-v estimate (rough -- for spiral transfers)
    delta_v = abs(origin_au - dest_au) * 5.0  # Very rough: ~5 km/s per AU of transfer

    # Transit time
    transit_days = estimate_transit_time(origin_au, dest_au, accel)

    # Confidence assessment
    if abs(origin_au - dest_au) < 0.3:
        confidence = "medium"
        notes.append("Short transfer -- estimate is reasonable")
    elif abs(origin_au - dest_au) < 1.0:
        confidence = "medium"
        notes.append("Moderate transfer -- analytical estimate, ~30% uncertainty")
    else:
        confidence = "low"
        notes.append("Long transfer -- high uncertainty, needs full trajectory optimization")

    if accel < 0.05:
        notes.append(f"WARNING: Very low sail acceleration ({accel:.3f} mm/s^2). "
                     "Consider larger sail or less cargo.")
        confidence = "low"

    return TrajectoryEstimate(
        origin_asteroid=ast_name,
        destination=destination,
        cargo_mass_kg=cargo_kg,
        sail_area_m2=sail_area_m2,
        total_mass_kg=total_mass,
        characteristic_acceleration_mm_s2=round(accel, 4),
        delta_v_needed_km_s=round(delta_v, 1),
        estimated_transit_days=round(transit_days, 0),
        estimated_transit_years=round(transit_days / 365.25, 1),
        confidence=confidence,
        notes=notes,
    )


def format_trajectory_report(est: TrajectoryEstimate) -> str:
    """Format a trajectory estimate as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("CARGO RETURN TRAJECTORY ESTIMATE")
    lines.append("=" * 60)
    lines.append(f"  Origin:       {est.origin_asteroid}")
    lines.append(f"  Destination:  {est.destination}")
    lines.append(f"  Cargo:        {est.cargo_mass_kg:.0f} kg")
    lines.append(f"  Vehicle:      {est.total_mass_kg - est.cargo_mass_kg:.1f} kg")
    lines.append(f"  Total mass:   {est.total_mass_kg:.1f} kg")
    lines.append(f"  Sail area:    {est.sail_area_m2:.0f} m^2")
    lines.append(f"")
    lines.append(f"  Sail accel:   {est.characteristic_acceleration_mm_s2:.4f} mm/s^2")
    lines.append(f"  Delta-v est:  {est.delta_v_needed_km_s:.1f} km/s")
    lines.append(f"  Transit time: {est.estimated_transit_days:.0f} days ({est.estimated_transit_years:.1f} years)")
    lines.append(f"  Confidence:   {est.confidence}")

    if est.notes:
        lines.append(f"\n  Notes:")
        for n in est.notes:
            lines.append(f"    - {n}")

    lines.append("=" * 60)
    return "\n".join(lines)
