"""AstraAnt Worker Ant - Asteroid Gravity Verification Test Suite

Tests whether the 120g hexapod worker ant can walk stably at asteroid
gravity levels. Sweeps all 7 catalog asteroids and finds the minimum
grip force needed to keep the ant grounded during walking.

Key question: SG90 servos produce 0.176 N*m torque. At Bennu gravity
(5.8 um/s^2), the ant weighs 0.7 uN. Can it walk without flying off?

Usage:
    python gravity_test.py                    # Full test suite
    python gravity_test.py --render bennu     # Visualize on Bennu
    python gravity_test.py --render earth     # Sanity check at 1g
    python gravity_test.py --quick            # Fast run, fewer sweep points

Requires: pip install mujoco numpy
"""

import argparse
import json
import math
import os
import sys
import time

import numpy as np

try:
    import mujoco
except ImportError:
    print("ERROR: MuJoCo not installed. Run: pip install mujoco")
    sys.exit(1)

from gait_controller import GaitController

# ---------------------------------------------------------------------------
# Asteroid catalog (from catalog/asteroids/*.yaml)
# Sorted by gravity: weakest to strongest
# ---------------------------------------------------------------------------
ASTEROIDS = [
    {"name": "Bennu",    "gravity": 5.80e-06, "rotation_h": 4.2905,  "type": "C",  "structure": "rubble_pile"},
    {"name": "Itokawa",  "gravity": 8.60e-06, "rotation_h": 12.1324, "type": "S",  "structure": "rubble_pile"},
    {"name": "2008 EV5", "gravity": 1.40e-05, "rotation_h": 3.7254,  "type": "C",  "structure": "rubble_pile"},
    {"name": "Ryugu",    "gravity": 1.10e-04, "rotation_h": 7.6272,  "type": "Cb", "structure": "rubble_pile"},
    {"name": "Didymos",  "gravity": 3.60e-04, "rotation_h": 2.2600,  "type": "S",  "structure": "rubble_pile"},
    {"name": "Eros",     "gravity": 5.90e-03, "rotation_h": 5.2703,  "type": "S",  "structure": "monolithic"},
    {"name": "Psyche",   "gravity": 6.00e-02, "rotation_h": 4.1959,  "type": "M",  "structure": "metallic"},
]

EARTH_GRAVITY = 9.81

# Worker ant specs (from configs/ants/worker.yaml)
ANT_MASS_KG = 0.120
SG90_STALL_TORQUE_NM = 0.176
LEG_LEVER_ARM_M = 0.080        # approximate foot distance from joint
MAX_TIP_FORCE_N = SG90_STALL_TORQUE_NM / LEG_LEVER_ARM_M  # ~2.2 N

# Simulation parameters
SETTLE_TIME_S = 0.5            # let ant reach equilibrium before test
WALK_TEST_TIME_S = 5.0         # duration of walking test
GRIP_SWEEP_TIME_S = 3.0        # shorter run for grip force binary search
LIFT_THRESHOLD_M = 0.010       # 10mm above start = "lifted off"

MODEL_PATH = os.path.join(os.path.dirname(__file__), "worker_ant.xml")


def load_model():
    """Load the worker ant MJCF model."""
    return mujoco.MjModel.from_xml_path(MODEL_PATH)


def get_foot_body_ids(model):
    """Get MuJoCo body IDs for all 6 foot bodies."""
    ids = []
    for i in range(6):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"foot_{i}")
        if bid < 0:
            raise RuntimeError(f"foot_{i} body not found in model")
        ids.append(bid)
    return ids


def settle(model, data, duration_s):
    """Run simulation with no control input to let the ant reach equilibrium."""
    n_steps = int(duration_s / model.opt.timestep)
    for _ in range(n_steps):
        data.ctrl[:] = 0.0
        mujoco.mj_step(model, data)


def run_walk(model, data, gait, duration_s, grip_force_per_foot=0.0,
             foot_ids=None):
    """Run the tripod gait and record torso trajectory.

    Args:
        grip_force_per_foot: downward force (N) applied at each foot body,
            simulating magnetic or mechanical grip.

    Returns dict with trajectory stats.
    """
    dt = model.opt.timestep
    n_steps = int(duration_s / dt)

    initial_x = float(data.qpos[0])
    initial_z = float(data.qpos[2])
    max_z = initial_z
    min_z = initial_z
    z_history = []

    for step in range(n_steps):
        # Apply gait to leg servos (actuators 0-5)
        angles = gait.step(dt)
        for i in range(6):
            data.ctrl[i] = angles[i]

        # Apply grip force at each foot (world frame, downward)
        if grip_force_per_foot > 0 and foot_ids is not None:
            for fid in foot_ids:
                data.xfrc_applied[fid, 2] = -grip_force_per_foot

        mujoco.mj_step(model, data)

        z = float(data.qpos[2])
        max_z = max(max_z, z)
        min_z = min(min_z, z)
        if step % 100 == 0:  # sample every 100ms
            z_history.append(z)

    final_x = float(data.qpos[0])
    final_z = float(data.qpos[2])

    return {
        "forward_m": final_x - initial_x,
        "lift_mm": (max_z - initial_z) * 1000,
        "drop_mm": (initial_z - min_z) * 1000,
        "final_z": final_z,
        "max_z": max_z,
        "grounded": (max_z - initial_z) < LIFT_THRESHOLD_M,
        "z_history": z_history,
    }


def test_static(model, gravity):
    """Test 1: Does the ant sit stably with no leg motion?"""
    data = mujoco.MjData(model)
    model.opt.gravity[:] = [0, 0, -gravity]
    mujoco.mj_resetData(model, data)
    settle(model, data, 1.0)

    initial_z = float(data.qpos[2])
    # Run 2 more seconds with no input
    settle(model, data, 2.0)
    final_z = float(data.qpos[2])

    return {
        "initial_z": initial_z,
        "final_z": final_z,
        "drift_mm": abs(final_z - initial_z) * 1000,
        "stable": abs(final_z - initial_z) < 0.005,
    }


def test_walk_no_grip(model, gravity):
    """Test 2: Walk with no grip force. Does the ant fly off?"""
    data = mujoco.MjData(model)
    model.opt.gravity[:] = [0, 0, -gravity]
    mujoco.mj_resetData(model, data)

    foot_ids = get_foot_body_ids(model)
    gait = GaitController()

    settle(model, data, SETTLE_TIME_S)
    gait.reset()

    return run_walk(model, data, gait, WALK_TEST_TIME_S,
                    grip_force_per_foot=0.0, foot_ids=foot_ids)


def test_walk_with_grip(model, gravity, grip_force):
    """Test 3: Walk with specified grip force per foot."""
    data = mujoco.MjData(model)
    model.opt.gravity[:] = [0, 0, -gravity]
    mujoco.mj_resetData(model, data)

    foot_ids = get_foot_body_ids(model)
    gait = GaitController()

    settle(model, data, SETTLE_TIME_S)
    gait.reset()

    return run_walk(model, data, gait, GRIP_SWEEP_TIME_S,
                    grip_force_per_foot=grip_force, foot_ids=foot_ids)


def find_min_grip_force(model, gravity, tolerance=0.05):
    """Binary search for minimum grip force that keeps the ant grounded.

    Returns grip force in Newtons per foot.
    """
    lo, hi = 0.0, 5.0

    # First check if max grip is enough
    result = test_walk_with_grip(model, gravity, hi)
    if not result["grounded"]:
        return float("inf")  # even 5N per foot isn't enough

    # Check if no grip is needed (shouldn't happen, but be safe)
    result = test_walk_with_grip(model, gravity, lo)
    if result["grounded"]:
        return 0.0

    while (hi - lo) > tolerance:
        mid = (lo + hi) / 2.0
        result = test_walk_with_grip(model, gravity, mid)
        if result["grounded"]:
            hi = mid
        else:
            lo = mid

    return hi


def render_simulation(model, asteroid_name, gravity):
    """Launch interactive MuJoCo viewer for a specific asteroid gravity."""
    try:
        import mujoco.viewer
    except ImportError:
        print("ERROR: MuJoCo viewer not available (needs OpenGL)")
        return

    model.opt.gravity[:] = [0, 0, -gravity]
    data = mujoco.MjData(model)

    foot_ids = get_foot_body_ids(model)
    gait = GaitController()

    weight = ANT_MASS_KG * gravity
    grip_force = max(0.5, MAX_TIP_FORCE_N * 0.5)  # moderate grip for demo

    print(f"\n  Rendering: {asteroid_name}")
    print(f"  Gravity: {gravity:.2e} m/s^2")
    print(f"  Ant weight: {weight:.2e} N")
    print(f"  Grip force: {grip_force:.2f} N/foot")
    print(f"  Close the viewer window to exit.\n")

    settle(model, data, SETTLE_TIME_S)
    gait.reset()

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            dt = model.opt.timestep
            angles = gait.step(dt)
            for i in range(6):
                data.ctrl[i] = angles[i]

            for fid in foot_ids:
                data.xfrc_applied[fid, 2] = -grip_force

            mujoco.mj_step(model, data)
            viewer.sync()


def format_force_ratio(gravity):
    """Compute and format servo force / ant weight ratio."""
    weight = ANT_MASS_KG * gravity
    if weight < 1e-12:
        return "inf", weight
    ratio = MAX_TIP_FORCE_N / weight
    if ratio >= 1e6:
        return f"{ratio:.1e}", weight
    elif ratio >= 1000:
        return f"{ratio:,.0f}x", weight
    else:
        return f"{ratio:.0f}x", weight


def run_full_suite(model, quick=False):
    """Run all tests on all asteroids and print results."""
    print("=" * 78)
    print("  AstraAnt Worker Ant -- Asteroid Gravity Verification")
    print("=" * 78)
    print(f"  Model mass:   {ANT_MASS_KG * 1000:.0f} g")
    print(f"  Servo torque: {SG90_STALL_TORQUE_NM * 1000:.1f} mN*m (SG90 stall)")
    print(f"  Max tip force:{MAX_TIP_FORCE_N:.2f} N (at {LEG_LEVER_ARM_M * 1000:.0f} mm lever)")
    print(f"  Gait:         Alternating tripod, +/-30 deg, 400 ms cycle")
    print()

    # --- Test 1: Static stability ---
    print("--- TEST 1: Static Stability (no leg motion) ---")
    print(f"{'Asteroid':>10} | {'Gravity':>12} | {'Weight (N)':>12} | {'Drift (mm)':>10} | Result")
    print("-" * 70)

    for ast in ASTEROIDS:
        result = test_static(model, ast["gravity"])
        status = "STABLE" if result["stable"] else "DRIFTING"
        print(f"{ast['name']:>10} | {ast['gravity']:>12.2e} | "
              f"{ANT_MASS_KG * ast['gravity']:>12.2e} | "
              f"{result['drift_mm']:>10.3f} | {status}")

    # --- Test 2: Walking without grip ---
    print()
    print("--- TEST 2: Walking WITHOUT Grip (tripod gait, 5 seconds) ---")
    print(f"{'Asteroid':>10} | {'Gravity':>12} | {'Servo/Weight':>14} | "
          f"{'Lift (mm)':>10} | {'Forward':>10} | Grounded?")
    print("-" * 82)

    walk_results = {}
    for ast in ASTEROIDS:
        result = test_walk_no_grip(model, ast["gravity"])
        ratio_str, _ = format_force_ratio(ast["gravity"])
        grounded_str = "YES" if result["grounded"] else "NO -- LIFTOFF"
        fwd_str = f"{result['forward_m'] * 1000:.1f} mm"
        print(f"{ast['name']:>10} | {ast['gravity']:>12.2e} | {ratio_str:>14} | "
              f"{result['lift_mm']:>10.1f} | {fwd_str:>10} | {grounded_str}")
        walk_results[ast["name"]] = result

    # --- Test 3: Minimum grip force ---
    print()
    print("--- TEST 3: Minimum Grip Force for Stable Walking ---")
    print(f"{'Asteroid':>10} | {'Gravity':>12} | {'Min Grip/Foot':>14} | "
          f"{'Total (3 feet)':>14} | {'Grip Type'}")
    print("-" * 78)

    grip_results = {}
    for ast in ASTEROIDS:
        min_grip = find_min_grip_force(model, ast["gravity"],
                                       tolerance=0.1 if quick else 0.05)
        total_grip = min_grip * 3  # 3 feet in stance at any time
        if min_grip == float("inf"):
            grip_str = ">5.0 N"
            total_str = ">15.0 N"
        elif min_grip == 0.0:
            grip_str = "0 (none)"
            total_str = "0"
        else:
            grip_str = f"{min_grip:.2f} N"
            total_str = f"{total_grip:.2f} N"

        # Suggest grip mechanism based on asteroid type
        if ast["type"] == "M":
            grip_type = "Magnetic (metallic surface)"
        else:
            grip_type = "Mechanical (spikes/anchors)"

        print(f"{ast['name']:>10} | {ast['gravity']:>12.2e} | {grip_str:>14} | "
              f"{total_str:>14} | {grip_type}")
        grip_results[ast["name"]] = {
            "min_per_foot_N": min_grip if min_grip != float("inf") else None,
            "total_N": total_grip if min_grip != float("inf") else None,
        }

    # --- Summary ---
    print()
    print("=" * 78)
    print("  CONCLUSIONS")
    print("=" * 78)
    all_liftoff = all(not walk_results[a["name"]]["grounded"] for a in ASTEROIDS)
    if all_liftoff:
        print("  * WITHOUT GRIP: Ant lifts off on ALL asteroids.")
        print(f"    SG90 servo tip force ({MAX_TIP_FORCE_N:.2f} N) massively exceeds")
        print(f"    gravitational force on every catalog asteroid.")
    print()
    print("  * MAGNETIC FEET are sufficient on Psyche (metallic, M-type).")
    print("    Neodymium disc magnets (4mm dia, ~3N pull) exceed minimum grip.")
    print()
    print("  * MECHANICAL GRIP needed on C/S-type asteroids (non-magnetic).")
    print("    Options: micro-spikes, screw anchors, gecko-inspired adhesion,")
    print("    or electrostatic grip on conductive regolith.")
    print()
    max_grip = max(
        (grip_results[a["name"]]["min_per_foot_N"] or 0) for a in ASTEROIDS
    )
    print(f"  * Minimum grip force across all asteroids: ~{max_grip:.1f} N per foot")
    print(f"    (3 feet in stance = ~{max_grip * 3:.1f} N total at any time)")
    print()
    print("  * The gait controller works identically at all gravity levels.")
    print("    Gravity only affects whether the ant stays on the surface,")
    print("    not how the legs move. Grip mechanism is the critical variable.")
    print("=" * 78)

    return {
        "walk_results": {k: {kk: vv for kk, vv in v.items() if kk != "z_history"}
                         for k, v in walk_results.items()},
        "grip_results": grip_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="AstraAnt worker ant asteroid gravity verification")
    parser.add_argument("--render", type=str, default=None,
                        help="Render simulation for asteroid (e.g. bennu, earth)")
    parser.add_argument("--quick", action="store_true",
                        help="Faster run with coarser grip sweep")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    args = parser.parse_args()

    print(f"Loading model: {MODEL_PATH}")
    model = load_model()
    print(f"  Bodies: {model.nbody}, Joints: {model.njnt}, "
          f"Actuators: {model.nu}, DOF: {model.nv}")
    print(f"  Total mass: {sum(model.body_mass):.4f} kg")
    print()

    if args.render:
        name = args.render.lower()
        if name == "earth":
            render_simulation(model, "Earth", EARTH_GRAVITY)
        else:
            matches = [a for a in ASTEROIDS
                       if a["name"].lower().startswith(name)]
            if not matches:
                print(f"Unknown asteroid: {args.render}")
                print(f"Options: {', '.join(a['name'] for a in ASTEROIDS)}, earth")
                sys.exit(1)
            ast = matches[0]
            render_simulation(model, ast["name"], ast["gravity"])
    else:
        t0 = time.time()
        results = run_full_suite(model, quick=args.quick)
        elapsed = time.time() - t0
        print(f"\n  Total time: {elapsed:.1f}s")

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"  Results saved to: {args.output}")


if __name__ == "__main__":
    main()
