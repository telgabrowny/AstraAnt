"""Trajectory following and position estimation.

Handles orbit propagation, dead reckoning between ground updates,
thrust planning, and range-to-target computation.

The mothership uses a BIT-3 class ion thruster (1.4 mN, Isp 2200s)
with 5 kg iodine propellant. Transit from Earth to Bennu takes
~18-24 months on a low-thrust spiral.

Position is maintained as a state vector in heliocentric ecliptic
coordinates: (x, y, z, vx, vy, vz) in meters and m/s.

Ground updates arrive every 4-32 minutes (light time) via UHF.
Between updates, the navigator dead-reckons using the last known
state plus integrated thrust history.

Simplified Kepler propagation (no perturbations) is adequate for
the ESP32-S3 -- the ground station does the precision work.
"""

import math
import time

# -- Physical constants --
MU_SUN = 1.32712440018e20     # m^3/s^2, solar gravitational parameter
AU_M = 1.496e11               # meters per AU
BENNU_MU = 4.89               # m^3/s^2, Bennu gravitational parameter
BENNU_RADIUS = 245.0          # m


def init_navigator(cfg):
    """Initialize navigator state from config.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict with navigation state and config.
    """
    nav_cfg = cfg.get("navigation", {})

    return {
        # State vector: heliocentric ecliptic (m, m/s)
        "position": (AU_M, 0.0, 0.0),      # Start at 1 AU (Earth)
        "velocity": (0.0, 29784.0, 0.0),    # Earth orbital velocity
        "epoch_ms": time.ticks_ms(),

        # Thrust parameters
        "ion_thrust_n": nav_cfg.get("ion_thrust_n", 0.0014),
        "isp_s": nav_cfg.get("isp_s", 2200),
        "propellant_kg": nav_cfg.get("propellant_mass_kg", 5.0),
        "dry_mass_kg": nav_cfg.get("dry_mass_kg", 35.8),
        "propellant_used_kg": 0.0,

        # Target state (set by ground command)
        "target_position": (0.0, 0.0, 0.0),
        "target_set": False,

        # Approach parameters
        "approach_phase": False,
        "range_to_target_m": -1.0,

        # Thrust tracking
        "thrusting": False,
        "thrust_direction": (1.0, 0.0, 0.0),
        "total_dv_applied": 0.0,

        # Ground update
        "last_ground_update_ms": 0,
    }


def propagate_orbit(nav, dt_s):
    """Propagate orbit using Keplerian two-body dynamics.

    Simple Euler integration of the two-body equation of motion:
      a = -mu * r / |r|^3

    Adequate for coarse onboard estimation between ground updates.
    The ground station handles precision ephemeris.

    Args:
        nav: Navigator state dict.
        dt_s: Time step in seconds.

    Returns:
        Updated (position, velocity) tuples.
    """
    x, y, z = nav["position"]
    vx, vy, vz = nav["velocity"]

    r_mag = math.sqrt(x * x + y * y + z * z)
    if r_mag < 1.0:
        r_mag = 1.0  # Prevent division by zero

    # Gravitational acceleration (heliocentric)
    r3 = r_mag * r_mag * r_mag
    ax = -MU_SUN * x / r3
    ay = -MU_SUN * y / r3
    az = -MU_SUN * z / r3

    # Euler integration
    vx += ax * dt_s
    vy += ay * dt_s
    vz += az * dt_s

    x += vx * dt_s
    y += vy * dt_s
    z += vz * dt_s

    nav["position"] = (x, y, z)
    nav["velocity"] = (vx, vy, vz)
    nav["epoch_ms"] = time.ticks_ms()

    return (x, y, z), (vx, vy, vz)


def apply_thrust(nav, dt_s):
    """Apply ion thrust to state vector.

    The BIT-3 thruster provides 1.4 mN continuously. Direction is
    set by the ADCS pointing the spacecraft.

    Updates propellant mass and total delta-v.

    Args:
        nav: Navigator state dict.
        dt_s: Duration of thrust in seconds.

    Returns:
        Delta-v applied (m/s) as float.
    """
    if not nav.get("thrusting", False):
        return 0.0

    thrust_n = nav.get("ion_thrust_n", 0.0014)
    isp = nav.get("isp_s", 2200)
    prop_remaining = nav["propellant_kg"] - nav["propellant_used_kg"]

    if prop_remaining <= 0:
        nav["thrusting"] = False
        return 0.0

    # Current total mass
    total_mass = nav["dry_mass_kg"] + prop_remaining

    # Acceleration
    accel = thrust_n / total_mass  # m/s^2

    # Propellant consumed: m_dot = F / (Isp * g0)
    g0 = 9.80665
    m_dot = thrust_n / (isp * g0)  # kg/s
    dm = m_dot * dt_s

    if dm > prop_remaining:
        dm = prop_remaining
        dt_s = dm / m_dot  # Adjust time step to remaining propellant

    # Apply delta-v in thrust direction
    dx, dy, dz = nav["thrust_direction"]
    mag = math.sqrt(dx * dx + dy * dy + dz * dz)
    if mag > 0.001:
        dx, dy, dz = dx / mag, dy / mag, dz / mag

    dv = accel * dt_s
    vx, vy, vz = nav["velocity"]
    vx += dx * dv
    vy += dy * dv
    vz += dz * dv
    nav["velocity"] = (vx, vy, vz)

    nav["propellant_used_kg"] += dm
    nav["total_dv_applied"] += dv

    return dv


def estimate_position(nav, elapsed_s):
    """Dead-reckon position from last known state.

    Between ground updates, propagate orbit forward by elapsed time.

    Args:
        nav: Navigator state dict.
        elapsed_s: Seconds since last ground update.

    Returns:
        Estimated (x, y, z) position in meters.
    """
    # Save current state
    saved_pos = nav["position"]
    saved_vel = nav["velocity"]

    # Propagate forward
    steps = max(1, int(elapsed_s / 60.0))  # 1-minute steps
    dt = elapsed_s / steps
    for _ in range(steps):
        propagate_orbit(nav, dt)

    result = nav["position"]

    # Restore (we don't want to double-integrate)
    nav["position"] = saved_pos
    nav["velocity"] = saved_vel

    return result


def apply_ground_update(nav, position, velocity):
    """Apply a position/velocity update from ground station.

    Replaces the onboard estimate with the ground truth.

    Args:
        nav: Navigator state dict.
        position: (x, y, z) in meters, heliocentric ecliptic.
        velocity: (vx, vy, vz) in m/s.
    """
    nav["position"] = tuple(position)
    nav["velocity"] = tuple(velocity)
    nav["last_ground_update_ms"] = time.ticks_ms()
    nav["epoch_ms"] = time.ticks_ms()


def set_target(nav, position):
    """Set the target asteroid position.

    Args:
        nav: Navigator state dict.
        position: (x, y, z) in meters, heliocentric ecliptic.
    """
    nav["target_position"] = tuple(position)
    nav["target_set"] = True


def get_distance_to_target(nav):
    """Compute current range to target asteroid.

    Returns:
        Distance in meters, or -1.0 if no target set.
    """
    if not nav.get("target_set", False):
        return -1.0

    px, py, pz = nav["position"]
    tx, ty, tz = nav["target_position"]
    dx = tx - px
    dy = ty - py
    dz = tz - pz
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)

    nav["range_to_target_m"] = dist
    return dist


def compute_burn_direction(nav):
    """Compute thrust direction toward target (simplified).

    For low-thrust spiral, the optimal direction is tangential to
    the orbit. For final approach, it is directly toward the target.

    Returns:
        (dx, dy, dz) unit vector for thrust direction.
    """
    if not nav.get("target_set", False):
        return (1.0, 0.0, 0.0)

    dist = get_distance_to_target(nav)

    if dist < 10000.0:  # Within 10 km -- direct approach
        px, py, pz = nav["position"]
        tx, ty, tz = nav["target_position"]
        dx = tx - px
        dy = ty - py
        dz = tz - pz
        mag = math.sqrt(dx * dx + dy * dy + dz * dz)
        if mag < 0.001:
            return (0.0, 0.0, 0.0)
        return (dx / mag, dy / mag, dz / mag)

    else:
        # Low-thrust spiral: thrust along velocity direction
        # (simplified -- real trajectory uses ground-computed waypoints)
        vx, vy, vz = nav["velocity"]
        mag = math.sqrt(vx * vx + vy * vy + vz * vz)
        if mag < 0.001:
            return (1.0, 0.0, 0.0)
        return (vx / mag, vy / mag, vz / mag)


def get_propellant_remaining(nav):
    """Get remaining propellant mass.

    Returns:
        Remaining propellant in kg.
    """
    return max(0.0, nav["propellant_kg"] - nav["propellant_used_kg"])


def get_total_dv_remaining(nav):
    """Estimate remaining delta-v using Tsiolkovsky equation.

    dv = Isp * g0 * ln(m_wet / m_dry)

    Returns:
        Remaining delta-v in m/s.
    """
    prop_left = get_propellant_remaining(nav)
    m_dry = nav["dry_mass_kg"]
    m_wet = m_dry + prop_left
    isp = nav["isp_s"]
    g0 = 9.80665

    if m_wet <= m_dry:
        return 0.0

    return isp * g0 * math.log(m_wet / m_dry)


def get_nav_summary(nav):
    """Get a compact navigation summary for telemetry.

    Returns:
        Dict with key navigation values.
    """
    return {
        "position": nav["position"],
        "velocity": nav["velocity"],
        "range_to_target_m": nav.get("range_to_target_m", -1.0),
        "propellant_remaining_kg": round(get_propellant_remaining(nav), 3),
        "dv_remaining_mps": round(get_total_dv_remaining(nav), 1),
        "total_dv_applied_mps": round(nav.get("total_dv_applied", 0.0), 1),
        "thrusting": nav.get("thrusting", False),
    }
