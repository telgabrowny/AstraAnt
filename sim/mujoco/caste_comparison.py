"""All Three Castes - Asteroid Gravity Verification

Compares worker (8-leg, 120g, SG90), taskmaster (8-leg, 165g, SG90),
and surface ant (6-leg, 430g, Maxon) across all 7 asteroids.

Key question for surface ant: Maxon actuators produce 5.7x more torque
than SG90. Does it need proportionally more grip? Or does the 3.6x
heavier mass help? Should it also go to 8 legs?
"""

import math
import os
import sys
import time

try:
    import mujoco
except ImportError:
    print("ERROR: pip install mujoco")
    sys.exit(1)

DIR = os.path.dirname(__file__)

ASTEROIDS = [
    {"name": "Bennu",    "gravity": 5.80e-06},
    {"name": "Itokawa",  "gravity": 8.60e-06},
    {"name": "2008 EV5", "gravity": 1.40e-05},
    {"name": "Ryugu",    "gravity": 1.10e-04},
    {"name": "Didymos",  "gravity": 3.60e-04},
    {"name": "Eros",     "gravity": 5.90e-03},
    {"name": "Psyche",   "gravity": 6.00e-02},
]

CASTES = [
    {
        "name": "Worker (8-leg)",
        "model": "worker_ant_8leg.xml",
        "n_legs": 8,
        "gait": "alternating_quad",
        "stall_torque_Nm": 0.176,
        "mass_kg": 0.120,
        "cost_usd": 39,
        "lever_m": 0.080,
    },
    {
        "name": "Taskmaster (8-leg)",
        "model": "taskmaster_ant.xml",
        "n_legs": 8,
        "gait": "alternating_quad",
        "stall_torque_Nm": 0.176,
        "mass_kg": 0.165,
        "cost_usd": 80,
        "lever_m": 0.090,
    },
    {
        "name": "Surface Ant (6-leg)",
        "model": "surface_ant.xml",
        "n_legs": 6,
        "gait": "alternating_tripod",
        "stall_torque_Nm": 1.0,
        "mass_kg": 0.430,
        "cost_usd": 1500,
        "lever_m": 0.110,
    },
    {
        "name": "Surface Ant (8-leg)",
        "model": "surface_ant_8leg.xml",
        "n_legs": 8,
        "gait": "alternating_quad",
        "stall_torque_Nm": 1.0,
        "mass_kg": 0.430,
        "cost_usd": 1800,
        "lever_m": 0.110,
    },
]


def gait_alternating(phase, amplitude_rad, n_legs):
    """Generic alternating gait for N legs."""
    if n_legs == 8:
        GROUP_A = [0, 3, 4, 7]
    else:  # 6 legs
        GROUP_A = [0, 3, 4]

    angles = [0.0] * n_legs
    for i in range(n_legs):
        gp = phase if i in GROUP_A else (phase + 0.5) % 1.0
        angles[i] = amplitude_rad * math.sin(gp * 2 * math.pi)
    return angles


def run_test(model_path, n_legs, gravity, grip_force, walk_time=5.0):
    model = mujoco.MjModel.from_xml_path(os.path.join(DIR, model_path))
    data = mujoco.MjData(model)
    model.opt.gravity[:] = [0, 0, -gravity]

    foot_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"foot_{i}")
                for i in range(n_legs)]

    dt = model.opt.timestep
    amplitude = math.radians(30)
    phase = 0.0

    # Settle
    for _ in range(int(0.5 / dt)):
        data.ctrl[:n_legs] = 0.0
        mujoco.mj_step(model, data)

    initial_x = float(data.qpos[0])
    initial_z = float(data.qpos[2])
    max_z = initial_z
    max_slip = 0.0

    for _ in range(int(walk_time / dt)):
        phase = (phase + dt / 0.4) % 1.0
        angles = gait_alternating(phase, amplitude, n_legs)
        for i in range(n_legs):
            data.ctrl[i] = angles[i]

        data.xfrc_applied[:] = 0.0
        for fid in foot_ids:
            if data.xpos[fid, 2] < 0.015:
                data.xfrc_applied[fid, 2] = -grip_force

        mujoco.mj_step(model, data)
        max_z = max(max_z, float(data.qpos[2]))
        max_slip = max(max_slip, abs(float(data.qpos[1])))

    return {
        "forward_mm": (float(data.qpos[0]) - initial_x) * 1000,
        "lift_mm": (max_z - initial_z) * 1000,
        "slip_mm": max_slip * 1000,
        "grounded": (max_z - initial_z) < 0.010,
    }


def find_min_grip(model_path, n_legs, gravity):
    lo, hi = 0.0, 5.0
    for _ in range(14):
        mid = (lo + hi) / 2
        r = run_test(model_path, n_legs, gravity, mid, walk_time=3.0)
        if r["grounded"]:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    # Load and verify all models
    print("Loading models...")
    for c in CASTES:
        m = mujoco.MjModel.from_xml_path(os.path.join(DIR, c["model"]))
        actual_mass = sum(m.body_mass)
        tip_force = c["stall_torque_Nm"] / c["lever_m"]
        print(f"  {c['name']:25s}  mass={actual_mass:.3f} kg  "
              f"actuators={m.nu}  tip_force={tip_force:.1f} N")
    print()

    # === Test 1: Minimum grip force per caste per asteroid ===
    print("=" * 90)
    print("  All Castes - Minimum Grip Force for Stable Walking")
    print("=" * 90)
    print()

    hdr = (f"{'Caste':>25} | {'Asteroid':>10} | {'Weight (N)':>12} | "
           f"{'Tip Force':>10} | {'Ratio':>10} | {'Min Grip':>10} | {'Per Foot':>10}")
    print(hdr)
    print("-" * len(hdr))

    all_results = {}
    for c in CASTES:
        tip_force = c["stall_torque_Nm"] / c["lever_m"]
        caste_results = {}
        for ast in ASTEROIDS:
            weight = c["mass_kg"] * ast["gravity"]
            ratio = tip_force / weight if weight > 1e-12 else float("inf")
            min_g = find_min_grip(c["model"], c["n_legs"], ast["gravity"])
            total = min_g * c["n_legs"]

            ratio_str = f"{ratio:.0e}" if ratio > 1e5 else f"{ratio:,.0f}x"
            print(f"{c['name']:>25} | {ast['name']:>10} | {weight:>12.2e} | "
                  f"{tip_force:>8.1f} N | {ratio_str:>10} | "
                  f"{total:>8.3f} N | {min_g:>8.4f} N")

            caste_results[ast["name"]] = {
                "min_per_foot_N": min_g,
                "min_total_N": total,
            }
        all_results[c["name"]] = caste_results
        print("-" * len(hdr))

    # === Test 2: Walking at 0.15 N/foot (standard foot pad) ===
    print()
    print("=" * 90)
    print("  Walking Stability at 0.15 N/foot Uniform Grip (3 asteroids)")
    print("=" * 90)
    print()

    test_asteroids = [ASTEROIDS[0], ASTEROIDS[3], ASTEROIDS[6]]  # Bennu, Ryugu, Psyche
    hdr2 = (f"{'Caste':>25} | {'Asteroid':>10} | {'Stable':>6} | "
            f"{'Forward':>10} | {'Lift mm':>8} | {'Slip mm':>8}")
    print(hdr2)
    print("-" * len(hdr2))

    for c in CASTES:
        for ast in test_asteroids:
            r = run_test(c["model"], c["n_legs"], ast["gravity"], 0.15)
            stable = "YES" if r["grounded"] else "NO"
            print(f"{c['name']:>25} | {ast['name']:>10} | {stable:>6} | "
                  f"{r['forward_mm']:>8.1f} mm | {r['lift_mm']:>8.1f} | "
                  f"{r['slip_mm']:>8.1f}")
        print("-" * len(hdr2))

    # === Summary ===
    print()
    print("=" * 90)
    print("  SUMMARY & RECOMMENDATIONS")
    print("=" * 90)

    for c in CASTES:
        tip = c["stall_torque_Nm"] / c["lever_m"]
        cr = all_results[c["name"]]
        max_min = max(v["min_per_foot_N"] for v in cr.values())
        foot_pad_force = 0.20  # C-type rubble minimum from foot pad spec
        margin = foot_pad_force / max_min if max_min > 0 else float("inf")
        print(f"\n  {c['name']}  (${c['cost_usd']}, {c['mass_kg']*1000:.0f}g, "
              f"tip_force={tip:.1f}N)")
        print(f"    Max min grip needed: {max_min:.4f} N/foot")
        print(f"    Foot pad provides:   {foot_pad_force:.2f} N (C-type worst case)")
        print(f"    Safety margin:       {margin:.0f}x")
        if margin >= 5:
            print(f"    Verdict:             SELF-SUFFICIENT on all surfaces")
        elif margin >= 2:
            print(f"    Verdict:             OK with foot pads, consider 8-leg upgrade")
        else:
            print(f"    Verdict:             NEEDS STRONGER GRIP or 8-leg upgrade")

    print()
    print("=" * 90)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n  Total time: {time.time() - t0:.1f}s")
