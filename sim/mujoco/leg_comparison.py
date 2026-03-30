"""6-Leg vs 8-Leg Comparison Test

Both use UNIFORM grip on all feet (proven approach from gravity_test.py).
Tests which configuration walks more stably with the hybrid foot pads.

6-leg: alternating tripod (Group A: 0,3,4 / Group B: 1,2,5)
8-leg: alternating quadruplets (Group A: 0,3,4,7 / Group B: 1,2,5,6)

Same total mass (120g) -- 8-leg has lighter chassis to compensate.
"""

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

# Asteroid subset for comparison (lightest, medium, heaviest)
ASTEROIDS = [
    {"name": "Bennu",   "gravity": 5.80e-06, "label": "weakest gravity"},
    {"name": "Ryugu",   "gravity": 1.10e-04, "label": "medium gravity"},
    {"name": "Psyche",  "gravity": 6.00e-02, "label": "strongest gravity"},
]

# Surface types: raw regolith vs steel-backed power rail
SURFACES = [
    {"name": "raw regolith",   "friction": [0.4, 0.01, 0.001],
     "grip_N": 0.15, "desc": "C-type rubble, spines+studs only"},
    {"name": "steel rail",     "friction": [0.8, 0.01, 0.001],
     "grip_N": 1.50, "desc": "Steel foil backing, magnet dominant"},
]


# ---------------------------------------------------------------------------
# Gait generators
# ---------------------------------------------------------------------------
def gait_6leg_tripod(phase, amplitude_rad):
    """Alternating tripod for 6 legs. Returns list of 6 angles (rad)."""
    GROUP_A = [0, 3, 4]
    angles = [0.0] * 6
    for i in range(6):
        gp = phase if i in GROUP_A else (phase + 0.5) % 1.0
        angles[i] = amplitude_rad * math.sin(gp * 2 * math.pi)
    return angles


def gait_8leg_quad(phase, amplitude_rad):
    """Alternating quadruplets for 8 legs.
    Group A: 0(FL), 3(M1R), 4(M2L), 7(RR) - diagonal pattern
    Group B: 1(FR), 2(M1L), 5(M2R), 6(RL)
    """
    GROUP_A = [0, 3, 4, 7]
    angles = [0.0] * 8
    for i in range(8):
        gp = phase if i in GROUP_A else (phase + 0.5) % 1.0
        angles[i] = amplitude_rad * math.sin(gp * 2 * math.pi)
    return angles


def gait_8leg_wave(phase, amplitude_rad):
    """Wave gait for 8 legs. Each pair offset by 1/4 cycle.
    Only ~2 legs swing at a time, 6 always in stance.
    """
    pair_offsets = [0.0, 0.25, 0.5, 0.75]  # 4 pairs
    angles = [0.0] * 8
    for pair_idx in range(4):
        offset = pair_offsets[pair_idx]
        gp = (phase + offset) % 1.0
        left_idx = pair_idx * 2
        right_idx = pair_idx * 2 + 1
        angle = amplitude_rad * math.sin(gp * 2 * math.pi)
        angles[left_idx] = angle
        angles[right_idx] = angle
    return angles


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def run_test(model_path, n_legs, gait_fn, gravity, grip_force,
             walk_time=5.0, settle_time=0.5, ground_friction=None):
    """Run a walking test. Returns stats dict."""
    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)
    model.opt.gravity[:] = [0, 0, -gravity]

    if ground_friction is not None:
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "ground")
        model.geom_friction[gid] = ground_friction

    # Get foot body IDs
    foot_ids = []
    for i in range(n_legs):
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"foot_{i}")
        foot_ids.append(bid)

    dt = model.opt.timestep
    amplitude = math.radians(30)
    step_period = 0.400
    phase = 0.0

    # Settle
    for _ in range(int(settle_time / dt)):
        data.ctrl[:n_legs] = 0.0
        mujoco.mj_step(model, data)

    initial_x = float(data.qpos[0])
    initial_z = float(data.qpos[2])
    max_z = initial_z
    max_y_drift = 0.0

    # Walk with uniform grip on ALL feet
    for step in range(int(walk_time / dt)):
        phase += (dt / step_period)
        phase %= 1.0
        angles = gait_fn(phase, amplitude)

        for i in range(n_legs):
            data.ctrl[i] = angles[i]

        # Uniform grip on all feet near ground
        data.xfrc_applied[:] = 0.0
        for i, fid in enumerate(foot_ids):
            if data.xpos[fid, 2] < 0.012:
                data.xfrc_applied[fid, 2] = -grip_force

        mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        max_z = max(max_z, z)
        y_drift = abs(float(data.qpos[1]))
        max_y_drift = max(max_y_drift, y_drift)

    final_x = float(data.qpos[0])
    return {
        "forward_mm": (final_x - initial_x) * 1000,
        "lift_mm": (max_z - initial_z) * 1000,
        "slip_mm": max_y_drift * 1000,
        "grounded": (max_z - initial_z) < 0.010,
    }


def find_min_grip(model_path, n_legs, gait_fn, gravity, ground_friction=None):
    """Binary search for minimum uniform grip force."""
    lo, hi = 0.0, 2.0
    for _ in range(12):
        mid = (lo + hi) / 2
        r = run_test(model_path, n_legs, gait_fn, gravity, mid,
                     walk_time=3.0, ground_friction=ground_friction)
        if r["grounded"]:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    model_6 = os.path.join(DIR, "worker_ant_gripfoot.xml")
    model_8 = os.path.join(DIR, "worker_ant_8leg.xml")

    # Verify both load
    m6 = mujoco.MjModel.from_xml_path(model_6)
    m8 = mujoco.MjModel.from_xml_path(model_8)
    print(f"6-leg model: {sum(m6.body_mass):.4f} kg, {m6.nu} actuators")
    print(f"8-leg model: {sum(m8.body_mass):.4f} kg, {m8.nu} actuators")
    print()

    configs = [
        ("6-leg tripod",     model_6, 6, gait_6leg_tripod),
        ("8-leg alternating", model_8, 8, gait_8leg_quad),
        ("8-leg wave",       model_8, 8, gait_8leg_wave),
    ]

    print("=" * 85)
    print("  6-Leg vs 8-Leg Comparison -- Uniform Grip, Hybrid Foot Pads")
    print("=" * 85)
    print()

    # --- Test 1: Walking at 0.15 N/foot uniform grip ---
    grip = 0.15  # modest uniform grip
    print(f"--- Walking Stability at {grip:.2f} N/foot uniform grip ---")
    hdr = (f"{'Config':>20} | {'Asteroid':>8} | {'Stable':>6} | "
           f"{'Forward':>10} | {'Lift mm':>8} | {'Slip mm':>8}")
    print(hdr)
    print("-" * len(hdr))

    for name, mpath, nlegs, gfn in configs:
        for ast in ASTEROIDS:
            r = run_test(mpath, nlegs, gfn, ast["gravity"], grip)
            stable = "YES" if r["grounded"] else "NO"
            print(f"{name:>20} | {ast['name']:>8} | {stable:>6} | "
                  f"{r['forward_mm']:>8.1f} mm | {r['lift_mm']:>8.1f} | "
                  f"{r['slip_mm']:>8.1f}")
        print("-" * len(hdr))

    # --- Test 2: Minimum grip force ---
    print()
    print("--- Minimum Grip Force for Stable Walking ---")
    hdr2 = f"{'Config':>20} | {'Asteroid':>8} | {'Min Grip/Foot':>14} | {'Total Grip':>11}"
    print(hdr2)
    print("-" * len(hdr2))

    for name, mpath, nlegs, gfn in configs:
        for ast in ASTEROIDS:
            min_g = find_min_grip(mpath, nlegs, gfn, ast["gravity"])
            total = min_g * nlegs
            print(f"{name:>20} | {ast['name']:>8} | {min_g:>12.3f} N | "
                  f"{total:>9.3f} N")
        print("-" * len(hdr2))

    # --- Test 3: Steel rail vs raw regolith (Bennu, worst case) ---
    print()
    print("--- Steel-Backed Rail vs Raw Regolith (Bennu, 8-leg alternating) ---")
    hdr3 = (f"{'Surface':>16} | {'Grip/Foot':>10} | {'Stable':>6} | "
            f"{'Forward':>10} | {'Lift mm':>8} | {'Slip mm':>8} | {'Min Grip':>10}")
    print(hdr3)
    print("-" * len(hdr3))

    for surf in SURFACES:
        r = run_test(model_8, 8, gait_8leg_quad, 5.80e-06, surf["grip_N"],
                     ground_friction=surf["friction"])
        mg = find_min_grip(model_8, 8, gait_8leg_quad, 5.80e-06,
                           ground_friction=surf["friction"])
        stable = "YES" if r["grounded"] else "NO"
        print(f"{surf['name']:>16} | {surf['grip_N']:>8.2f} N | {stable:>6} | "
              f"{r['forward_mm']:>8.1f} mm | {r['lift_mm']:>8.1f} | "
              f"{r['slip_mm']:>8.1f} | {mg:>8.3f} N")

    print()
    print("  Steel rail adds 11.3 kg of foil for 1.2 km tunnel (0.04% of Starship).")
    print("  Magnet grip on steel: 1.5 N/foot = 188x the minimum needed.")
    print("  Ants walk the rail like a magnetic highway -- power AND grip.")
    print()

    # --- Test 4: Ant chain concept (anchor + 1-3 link ants) ---
    print("--- Ant Chain Stability (anchor on rail, tip on raw regolith) ---")
    print("  Simulating chain as: tip ant gets fraction of anchor's rail grip")
    print("  (mandible link transmits 1.5 N per link, degrading with chain length)")
    hdr4 = f"{'Chain Length':>14} | {'Effective Grip':>14} | {'Stable':>6} | {'Forward':>10}"
    print(hdr4)
    print("-" * len(hdr4))

    for chain_len in [0, 1, 2, 3, 4, 5]:
        # Each link transmits mandible grip force (1.5 N) minus loss
        # Chain of N links: tip ant gets min(1.5, rail_grip) degraded by N links
        # Model: effective_grip = rail_grip / (1 + 0.3 * chain_len)
        # (30% loss per link from flex, angle, mandible compliance)
        rail_grip = 1.50
        if chain_len == 0:
            eff_grip = rail_grip  # directly on rail
            label = "on rail"
        else:
            eff_grip = min(1.5, rail_grip / (1 + 0.3 * chain_len))
            label = f"{chain_len} links"

        r = run_test(model_8, 8, gait_8leg_quad, 5.80e-06, eff_grip,
                     ground_friction=[0.4, 0.01, 0.001])  # raw regolith at tip
        stable = "YES" if r["grounded"] else "NO"
        print(f"{label:>14} | {eff_grip:>12.3f} N | {stable:>6} | "
              f"{r['forward_mm']:>8.1f} mm")

    print()

    # --- Summary ---
    print()
    print("=" * 85)
    print("  COST COMPARISON")
    print("=" * 85)
    print(f"  6-leg: 6x SG90 ($18) + 6x foot pad ($1.80) = $19.80 locomotion")
    print(f"  8-leg: 8x SG90 ($24) + 8x foot pad ($2.40) = $26.40 locomotion")
    print(f"  Delta: +$6.60 per ant (+2 servos, +2 foot pads)")
    print(f"  Mass:  Both 120g (8-leg has thinner chassis walls)")
    print(f"  Power: 8-leg draws 33% more servo power (8 vs 6 servos)")
    print("=" * 85)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n  Total time: {time.time() - t0:.1f}s")
