"""Mothership Landing Simulation

Tests touchdown dynamics across all 7 asteroids:
  - Does the mothership bounce off, stick, or sink?
  - How fast must anchors engage to prevent escape?
  - What approach velocity is safe?
  - Can the drill operate without pushing the mothership off?

Real-world context:
  Philae bounced for 2 hours on comet 67P (harpoons failed)
  OSIRIS-REx sank 50cm into Bennu (near-zero cohesion)
  Approach velocities: 5 mm/s (spec) to 1 m/s (Philae)

Usage:
    python landing_sim.py                  # Full test suite
    python landing_sim.py --render bennu   # Visualize landing on Bennu
"""

import argparse
import math
import os
import sys
import time

import numpy as np

try:
    import mujoco
except ImportError:
    print("ERROR: pip install mujoco")
    sys.exit(1)

DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(DIR, "mothership.xml")

MOTHERSHIP_MASS_KG = 900
ANCHOR_FORCE_N = 50              # Per anchor, pull-out force in regolith
N_ANCHORS = 4
DRILL_REACTION_FORCE_N = 50     # Max drill thrust (limited by anchor hold)
ANCHOR_DEPLOY_TIME_S = 10       # Time to fully engage screw anchors

ASTEROIDS = [
    {"name": "Bennu",    "gravity": 5.80e-06, "escape_v": 0.20,
     "surface": "rubble_pile",  "solref": [0.05, 0.9],  "friction": [0.4, 0.01, 0.001]},
    {"name": "Itokawa",  "gravity": 8.60e-06, "escape_v": 0.16,
     "surface": "rubble_pile",  "solref": [0.04, 0.9],  "friction": [0.5, 0.01, 0.001]},
    {"name": "2008 EV5", "gravity": 1.40e-05, "escape_v": 0.15,
     "surface": "rubble_pile",  "solref": [0.05, 0.9],  "friction": [0.4, 0.01, 0.001]},
    {"name": "Ryugu",    "gravity": 1.10e-04, "escape_v": 0.38,
     "surface": "rubble_pile",  "solref": [0.04, 0.9],  "friction": [0.4, 0.01, 0.001]},
    {"name": "Didymos",  "gravity": 3.60e-04, "escape_v": 0.45,
     "surface": "rubble_pile",  "solref": [0.03, 0.9],  "friction": [0.5, 0.01, 0.001]},
    {"name": "Eros",     "gravity": 5.90e-03, "escape_v": 10.0,
     "surface": "monolithic",   "solref": [0.01, 1.0],  "friction": [0.7, 0.01, 0.001]},
    {"name": "Psyche",   "gravity": 6.00e-02, "escape_v": 180.0,
     "surface": "metallic",     "solref": [0.005, 1.0], "friction": [0.6, 0.01, 0.001]},
]


def setup_model(gravity, solref, friction):
    """Load model and configure for specific asteroid."""
    model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    model.opt.gravity[:] = [0, 0, -gravity]

    gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
    model.geom_solref[gid] = solref
    model.geom_friction[gid] = friction

    return model


def detect_contact(data, model):
    """Check if mothership is touching the ground."""
    ground_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
    for c in range(data.ncon):
        contact = data.contact[c]
        if contact.geom1 == ground_id or contact.geom2 == ground_id:
            return True
    return False


def run_landing(model, approach_velocity_ms, anchor_enabled=True,
                sim_time_s=60.0):
    """Simulate a landing attempt.

    Args:
        approach_velocity_ms: downward velocity at start (m/s)
        anchor_enabled: whether to apply anchor forces after contact
        sim_time_s: how long to simulate

    Returns dict with landing outcome.
    """
    data = mujoco.MjData(model)
    dt = model.opt.timestep
    n_steps = int(sim_time_s / dt)

    # Start mothership 2m above surface, descending
    data.qpos[2] = 2.0  # z position
    data.qvel[2] = -approach_velocity_ms  # downward velocity

    mothership_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "mothership")

    first_contact_time = None
    anchored = False
    anchor_start_time = None
    max_bounce_height = 0.0
    min_z = 999.0
    final_settled = False
    escaped = False

    z_at_contact = None
    max_rebound_v = 0.0

    for step in range(n_steps):
        t = step * dt
        z = float(data.qpos[2])
        vz = float(data.qvel[2])

        # Track extremes
        if z_at_contact is not None:
            max_bounce_height = max(max_bounce_height, z - z_at_contact)
        min_z = min(min_z, z)

        # Detect first contact
        in_contact = detect_contact(data, model)
        if in_contact and first_contact_time is None:
            first_contact_time = t
            z_at_contact = z
            anchor_start_time = t

        # Track rebound velocity (upward after first contact)
        if first_contact_time is not None and vz > 0:
            max_rebound_v = max(max_rebound_v, vz)

        # Apply anchor forces (ramp up over ANCHOR_DEPLOY_TIME_S)
        data.xfrc_applied[mothership_id] = 0
        if anchor_enabled and anchor_start_time is not None:
            elapsed_anchor = t - anchor_start_time
            if elapsed_anchor < ANCHOR_DEPLOY_TIME_S:
                # Ramp from 0 to full force over deployment time
                ramp = elapsed_anchor / ANCHOR_DEPLOY_TIME_S
            else:
                ramp = 1.0
                anchored = True

            # Total anchor force: 4 anchors x 50 N each, pulling down
            total_anchor_force = N_ANCHORS * ANCHOR_FORCE_N * ramp
            data.xfrc_applied[mothership_id, 2] = -total_anchor_force

        # Check escape (above starting height + moving up)
        if z > 5.0 and vz > 0:
            escaped = True
            break

        # Check settled (on ground, low velocity, anchored)
        if anchored and in_contact and abs(vz) < 0.001:
            final_settled = True

        mujoco.mj_step(model, data)

    final_z = float(data.qpos[2])
    final_vz = float(data.qvel[2])
    tilt_deg = 0
    if first_contact_time is not None:
        # Compute tilt from quaternion
        quat = data.qpos[3:7]
        # Simple tilt estimate from z-component of up vector
        w, x, y, qz = quat
        up_z = 1 - 2*(x*x + y*y)
        tilt_deg = math.degrees(math.acos(max(-1, min(1, up_z))))

    # Determine outcome
    if escaped:
        outcome = "ESCAPED"
    elif final_settled:
        outcome = "LANDED"
    elif max_bounce_height > 0.5:
        outcome = "BOUNCING"
    else:
        outcome = "SETTLING"

    sink_depth = 0
    if z_at_contact is not None:
        sink_depth = max(0, z_at_contact - min_z)

    return {
        "outcome": outcome,
        "approach_v_cms": approach_velocity_ms * 100,
        "first_contact_s": first_contact_time,
        "bounce_height_m": max_bounce_height,
        "rebound_v_cms": max_rebound_v * 100,
        "sink_depth_m": sink_depth,
        "tilt_deg": tilt_deg,
        "final_z": final_z,
        "final_vz_cms": final_vz * 100,
        "anchored": anchored,
    }


def run_drill_stability(model, drill_force_N, test_time_s=30.0):
    """After landing+anchoring, apply drill reaction force upward.
    Tests if anchors hold against drilling.
    """
    data = mujoco.MjData(model)
    dt = model.opt.timestep

    # Start on ground, already anchored
    data.qpos[2] = 0.95  # ~ground level for the base
    mothership_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "mothership")

    # Let it settle with anchors
    for _ in range(int(5.0 / dt)):
        data.xfrc_applied[mothership_id, 2] = -(N_ANCHORS * ANCHOR_FORCE_N)
        mujoco.mj_step(model, data)

    initial_z = float(data.qpos[2])
    max_lift = 0

    # Apply drill reaction force (upward)
    for _ in range(int(test_time_s / dt)):
        # Anchors pull down, drill pushes up
        net_force = -(N_ANCHORS * ANCHOR_FORCE_N) + drill_force_N
        data.xfrc_applied[mothership_id, 2] = net_force
        mujoco.mj_step(model, data)
        lift = float(data.qpos[2]) - initial_z
        max_lift = max(max_lift, lift)

    return {
        "drill_force_N": drill_force_N,
        "anchor_force_N": N_ANCHORS * ANCHOR_FORCE_N,
        "net_force_N": drill_force_N - N_ANCHORS * ANCHOR_FORCE_N,
        "max_lift_mm": max_lift * 1000,
        "stable": max_lift < 0.01,
    }


def find_max_safe_velocity(model, escape_v):
    """Binary search for maximum approach velocity that results in LANDED."""
    lo, hi = 0.001, min(escape_v * 0.5, 1.0)  # Cap at 1 m/s
    for _ in range(12):
        mid = (lo + hi) / 2
        r = run_landing(model, mid, anchor_enabled=True, sim_time_s=30.0)
        if r["outcome"] == "LANDED" or r["outcome"] == "SETTLING":
            lo = mid
        else:
            hi = mid
    return lo


def main():
    parser = argparse.ArgumentParser(description="Mothership landing simulation")
    parser.add_argument("--render", type=str, default=None)
    args = parser.parse_args()

    if args.render:
        try:
            import mujoco.viewer
        except ImportError:
            print("ERROR: MuJoCo viewer not available")
            return

        name = args.render.lower()
        ast = next((a for a in ASTEROIDS if a["name"].lower().startswith(name)), None)
        if not ast:
            print(f"Unknown: {args.render}")
            return

        model = setup_model(ast["gravity"], ast["solref"], ast["friction"])
        data = mujoco.MjData(model)
        data.qpos[2] = 2.0
        data.qvel[2] = -0.005  # 5 mm/s approach

        mid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "mothership")
        contacted = False

        print(f"\n  Landing on {ast['name']} at 5 mm/s")
        print(f"  Gravity: {ast['gravity']:.2e} m/s^2, Surface: {ast['surface']}")
        print(f"  Close viewer to exit.\n")

        with mujoco.viewer.launch_passive(model, data) as viewer:
            t = 0
            while viewer.is_running():
                dt = model.opt.timestep
                t += dt
                if detect_contact(data, model) and not contacted:
                    contacted = True
                    print(f"  Contact at t={t:.1f}s!")

                data.xfrc_applied[mid] = 0
                if contacted:
                    ramp = min(1.0, (t - t) / ANCHOR_DEPLOY_TIME_S) if t > 0 else 0
                    data.xfrc_applied[mid, 2] = -(N_ANCHORS * ANCHOR_FORCE_N)

                mujoco.mj_step(model, data)
                viewer.sync()
        return

    # === FULL TEST SUITE ===
    print("=" * 85)
    print("  AstraAnt Mothership Landing Simulation")
    print("=" * 85)
    print(f"  Mass: {MOTHERSHIP_MASS_KG} kg | Anchors: {N_ANCHORS}x {ANCHOR_FORCE_N} N")
    print(f"  Spec approach: 5 mm/s | Anchor deploy: {ANCHOR_DEPLOY_TIME_S}s")
    print()

    # --- Test 1: Landing at spec velocity (5 mm/s) with anchors ---
    print("--- TEST 1: Landing at 5 mm/s (spec velocity) with anchors ---")
    hdr = (f"{'Asteroid':>10} | {'Surface':>12} | {'Gravity':>12} | "
           f"{'Outcome':>10} | {'Bounce m':>9} | {'Sink mm':>8} | {'Tilt deg':>8}")
    print(hdr)
    print("-" * len(hdr))

    for ast in ASTEROIDS:
        model = setup_model(ast["gravity"], ast["solref"], ast["friction"])
        r = run_landing(model, 0.005, anchor_enabled=True, sim_time_s=60.0)
        print(f"{ast['name']:>10} | {ast['surface']:>12} | {ast['gravity']:>12.2e} | "
              f"{r['outcome']:>10} | {r['bounce_height_m']:>9.3f} | "
              f"{r['sink_depth_m']*1000:>8.1f} | {r['tilt_deg']:>8.1f}")

    # --- Test 2: Landing WITHOUT anchors (what happens if they fail?) ---
    print()
    print("--- TEST 2: Landing at 5 mm/s WITHOUT anchors (Philae scenario) ---")
    hdr2 = (f"{'Asteroid':>10} | {'Outcome':>10} | {'Rebound cm/s':>12} | "
            f"{'Escape v cm/s':>14} | {'Escapes?':>8}")
    print(hdr2)
    print("-" * len(hdr2))

    for ast in ASTEROIDS:
        model = setup_model(ast["gravity"], ast["solref"], ast["friction"])
        r = run_landing(model, 0.005, anchor_enabled=False, sim_time_s=120.0)
        escapes = r["rebound_v_cms"] > ast["escape_v"] * 100
        esc_str = "YES" if r["outcome"] == "ESCAPED" else "no"
        print(f"{ast['name']:>10} | {r['outcome']:>10} | "
              f"{r['rebound_v_cms']:>12.2f} | {ast['escape_v']*100:>14.1f} | "
              f"{esc_str:>8}")

    # --- Test 3: Maximum safe approach velocity ---
    print()
    print("--- TEST 3: Maximum Safe Approach Velocity (with anchors) ---")
    hdr3 = (f"{'Asteroid':>10} | {'Max Safe v':>12} | {'Escape v':>12} | "
            f"{'Safety ratio':>12}")
    print(hdr3)
    print("-" * len(hdr3))

    for ast in ASTEROIDS:
        model = setup_model(ast["gravity"], ast["solref"], ast["friction"])
        max_v = find_max_safe_velocity(model, ast["escape_v"])
        ratio = ast["escape_v"] / max_v if max_v > 0 else float("inf")
        print(f"{ast['name']:>10} | {max_v*100:>10.2f} cm/s | "
              f"{ast['escape_v']*100:>10.1f} cm/s | {ratio:>12.1f}x")

    # --- Test 4: Drill stability (can we bore without pushing off?) ---
    print()
    print("--- TEST 4: Drill Reaction Force vs Anchor Hold ---")
    hdr4 = (f"{'Asteroid':>10} | {'Drill F':>8} | {'Anchor F':>9} | "
            f"{'Net F':>8} | {'Lift mm':>8} | {'Stable':>6}")
    print(hdr4)
    print("-" * len(hdr4))

    for ast in ASTEROIDS:
        model = setup_model(ast["gravity"], ast["solref"], ast["friction"])
        r = run_drill_stability(model, DRILL_REACTION_FORCE_N)
        stable = "YES" if r["stable"] else "NO"
        print(f"{ast['name']:>10} | {r['drill_force_N']:>6.0f} N | "
              f"{r['anchor_force_N']:>7.0f} N | {r['net_force_N']:>6.0f} N | "
              f"{r['max_lift_mm']:>8.1f} | {stable:>6}")

    # --- Summary ---
    print()
    print("=" * 85)
    print("  LANDING SEQUENCE SUMMARY")
    print("=" * 85)
    print()
    print("  T+0s       Approach at 5 mm/s (gentle kiss)")
    print("  T+0s       Contact sensors trigger on base plate")
    print("  T+0-10s    4 screw anchors deploy (ramp to 200 N total)")
    print("  T+10s      Anchors verified (pull test)")
    print("  T+10-40s   Gasket seal inflates (15 kPa)")
    print("  T+40s      Pressure test (verify seal)")
    print("  T+30min    Drill begins (200mm bore, 50 N reaction)")
    print("  T+6.5hr    Bore complete (3m deep), power rail installed")
    print("  T+7hr      Wave 1: taskmaster + 5 workers deploy")
    print("  T+10hr     Bore widened to 400mm, sealed, pressurized")
    print("  T+18hr     Wave 2: 20 workers, tunnel extension begins")
    print("  T+24hr     Full mining operations")
    print()
    print("  Critical: anchors MUST fire within seconds of contact.")
    print("  Without anchors, the mothership WILL bounce on most asteroids.")
    print("=" * 85)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n  Total time: {time.time() - t0:.1f}s")
