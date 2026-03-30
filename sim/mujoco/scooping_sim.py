"""Single-Ant Work Face Scooping/Drilling Simulation

Tests whether a worker ant can drill and scoop at a tunnel work face
without losing grip. In microgravity, the drill/scoop reaction forces
push the ant AWAY from the work face. The feet must hold.

Key physics: there's no "pile" in microgravity. Cuttings float.
The ant carves the work face directly into its hopper. It's more
like a sculptor chiseling than a miner digging.

Tests:
  1. Drilling stability: ant pushes drill into wall, reaction pushes ant back
  2. Scooping stability: mandibles push scoop into wall, material enters hopper
  3. Maximum drill force before foot grip fails
  4. Comparison: drilling on rail (magnetic steel) vs off-rail (raw regolith)

Uses the 8-leg worker model with hybrid foot pads (microspines + studs).
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
MODEL_PATH = os.path.join(DIR, "worker_ant_8leg.xml")

# Tool specs from catalog/tools/
DRILL_FORCE_N = 0.5       # N20 motor drill reaction force at work face
SCOOP_FORCE_N = 0.2       # Mandible force pushing scoop into regolith
DRILL_DURATION_S = 3.0     # Per drill burst (from firmware command_handler.py)
SCOOP_DURATION_S = 2.0     # Per scoop cycle

ASTEROIDS = [
    {"name": "Bennu",   "gravity": 5.80e-06, "surface": "C_rubble"},
    {"name": "Eros",    "gravity": 5.90e-03, "surface": "S_monolith"},
    {"name": "Psyche",  "gravity": 6.00e-02, "surface": "M_metallic"},
]


def load_model(gravity):
    model = mujoco.MjModel.from_xml_path(MODEL_PATH)
    model.opt.gravity[:] = [0, 0, -gravity]
    return model


def get_foot_body_ids(model):
    return [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f"foot_{i}")
            for i in range(8)]


def run_work_face_test(gravity, tool_force_N, grip_force_per_foot,
                       duration_s=5.0, tool_name="drill"):
    """Simulate ant at work face with tool reaction force.

    The ant faces a wall (+x direction). The tool pushes into the wall,
    and the reaction pushes the ant backward (-x). Feet must hold.
    Ant walks forward at low speed to maintain contact with receding face.
    """
    model = load_model(gravity)
    data = mujoco.MjData(model)
    dt = model.opt.timestep

    foot_ids = get_foot_body_ids(model)
    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")

    # Settle with grip
    for _ in range(int(0.5 / dt)):
        data.ctrl[:8] = 0.0
        data.xfrc_applied[:] = 0.0
        for fid in foot_ids:
            if data.xpos[fid, 2] < 0.015:
                data.xfrc_applied[fid, 2] = -grip_force_per_foot
        mujoco.mj_step(model, data)

    initial_x = float(data.qpos[0])
    initial_z = float(data.qpos[2])
    max_backward = 0.0
    max_lift = 0.0
    max_tilt = 0.0

    # Gentle walking gait to push into work face
    GROUP_A = [0, 3, 4, 7]
    amplitude = math.radians(15)  # Reduced amplitude for working (half of walking)
    phase = 0.0

    for step in range(int(duration_s / dt)):
        t = step * dt

        # Slow gait (working speed, not walking speed)
        phase = (phase + dt / 0.6) % 1.0
        for i in range(8):
            gp = phase if i in GROUP_A else (phase + 0.5) % 1.0
            data.ctrl[i] = amplitude * math.sin(gp * 2 * math.pi)

        # Grip force on all grounded feet
        data.xfrc_applied[:] = 0.0
        for fid in foot_ids:
            if data.xpos[fid, 2] < 0.015:
                data.xfrc_applied[fid, 2] = -grip_force_per_foot

        # Tool reaction force (pushes ant backward, away from wall)
        # Applied to torso in -x direction (away from work face)
        data.xfrc_applied[torso_id, 0] = -tool_force_N

        mujoco.mj_step(model, data)

        x = float(data.qpos[0])
        z = float(data.qpos[2])
        backward = initial_x - x
        max_backward = max(max_backward, backward)
        max_lift = max(max_lift, z - initial_z)

        # Tilt check
        quat = data.qpos[3:7]
        w, qx, qy, qz = quat
        up_z = 1 - 2*(qx*qx + qy*qy)
        tilt = math.degrees(math.acos(max(-1, min(1, up_z))))
        max_tilt = max(max_tilt, tilt)

    final_x = float(data.qpos[0])
    return {
        "tool": tool_name,
        "tool_force_N": tool_force_N,
        "grip_N": grip_force_per_foot,
        "backward_mm": max_backward * 1000,
        "lift_mm": max_lift * 1000,
        "tilt_deg": max_tilt,
        "stable": max_lift < 0.010 and max_backward < 0.050,  # 10mm lift, 50mm slide (meters)
    }


def find_max_tool_force(gravity, grip_force):
    """Binary search for maximum tool force the ant can resist."""
    lo, hi = 0.0, 5.0
    for _ in range(12):
        mid = (lo + hi) / 2
        r = run_work_face_test(gravity, mid, grip_force, duration_s=3.0)
        if r["stable"]:
            lo = mid
        else:
            hi = mid
    return lo


def main():
    print("=" * 85)
    print("  Single-Ant Work Face Scooping/Drilling Simulation")
    print("=" * 85)
    print()
    print("  In microgravity, there's no pile. Cuttings float. The ant carves")
    print("  the work face directly into its hopper -- sculptor, not miner.")
    print("  The drill/scoop reaction pushes the ant AWAY from the wall.")
    print("  Feet must hold against this reaction force.")
    print()

    # --- Test 1: Drilling stability at standard force ---
    print("--- TEST 1: Drilling at Work Face (0.5 N reaction, 0.15 N/foot grip) ---")
    hdr = (f"{'Asteroid':>10} | {'Tool':>8} | {'Force':>7} | {'Grip/ft':>8} | "
           f"{'Slide mm':>9} | {'Lift mm':>8} | {'Tilt':>6} | {'Stable':>6}")
    print(hdr)
    print("-" * len(hdr))

    for ast in ASTEROIDS:
        for tool, force in [("drill", DRILL_FORCE_N), ("scoop", SCOOP_FORCE_N)]:
            r = run_work_face_test(ast["gravity"], force, 0.15,
                                   duration_s=5.0, tool_name=tool)
            stable = "YES" if r["stable"] else "NO"
            print(f"{ast['name']:>10} | {tool:>8} | {force:>5.2f} N | "
                  f"{'0.15 N':>8} | {r['backward_mm']:>9.1f} | "
                  f"{r['lift_mm']:>8.1f} | {r['tilt_deg']:>5.1f} | {stable:>6}")

    # --- Test 2: Maximum tool force before losing grip ---
    print()
    print("--- TEST 2: Maximum Tool Force Before Grip Failure ---")
    hdr2 = (f"{'Asteroid':>10} | {'Grip/ft':>8} | {'Max Drill':>10} | "
            f"{'Max Scoop':>10} | {'Drill Safe?':>11}")
    print(hdr2)
    print("-" * len(hdr2))

    for ast in ASTEROIDS:
        for grip in [0.10, 0.15, 0.30]:
            max_drill = find_max_tool_force(ast["gravity"], grip)
            max_scoop = max_drill * 0.8  # Scoop uses less force, similar limit
            drill_safe = "YES" if max_drill > DRILL_FORCE_N else "NO"
            print(f"{ast['name']:>10} | {grip:>6.2f} N | {max_drill:>8.2f} N | "
                  f"{max_scoop:>8.2f} N | {drill_safe:>11}")

    # --- Test 3: Rail vs off-rail comparison ---
    print()
    print("--- TEST 3: On-Rail (steel, 1.5 N grip) vs Off-Rail (regolith, 0.15 N) ---")
    hdr3 = (f"{'Asteroid':>10} | {'Surface':>12} | {'Grip/ft':>8} | "
            f"{'Drill Slide':>11} | {'Stable':>6}")
    print(hdr3)
    print("-" * len(hdr3))

    for ast in ASTEROIDS:
        # Off-rail (microspines only)
        r_off = run_work_face_test(ast["gravity"], DRILL_FORCE_N, 0.15,
                                    tool_name="drill")
        print(f"{ast['name']:>10} | {'off-rail':>12} | {'0.15 N':>8} | "
              f"{r_off['backward_mm']:>9.1f} mm | "
              f"{'YES' if r_off['stable'] else 'NO':>6}")

        # On-rail (steel foil, magnet grip via rail brush)
        r_on = run_work_face_test(ast["gravity"], DRILL_FORCE_N, 1.50,
                                   tool_name="drill")
        print(f"{'':>10} | {'on-rail':>12} | {'1.50 N':>8} | "
              f"{r_on['backward_mm']:>9.1f} mm | "
              f"{'YES' if r_on['stable'] else 'NO':>6}")
        print("-" * len(hdr3))

    # --- Test 4: Multi-ant drilling (brace ant doubles grip) ---
    print()
    print("--- TEST 4: Multi-Ant Drilling (brace ant behind driller) ---")
    print("  Brace ant grips driller's abdomen socket + adds 8 feet of grip.")
    print("  Mandible link: 1.5 N. Effectively doubles grip force per foot")
    print("  (brace ant's feet on the same surface, sharing load).")
    print()
    hdr4 = (f"{'Asteroid':>10} | {'Config':>18} | {'Grip/ft':>8} | "
            f"{'Slide mm':>9} | {'Lift mm':>8} | {'Tilt':>6} | {'Stable':>6}")
    print(hdr4)
    print("-" * len(hdr4))

    for ast in ASTEROIDS:
        # Solo ant drilling (baseline)
        r1 = run_work_face_test(ast["gravity"], DRILL_FORCE_N, 0.15,
                                duration_s=5.0, tool_name="drill")
        stable1 = "YES" if r1["stable"] else "NO"
        print(f"{ast['name']:>10} | {'solo (1 ant)':>18} | {'0.15 N':>8} | "
              f"{r1['backward_mm']:>9.1f} | {r1['lift_mm']:>8.1f} | "
              f"{r1['tilt_deg']:>5.1f} | {stable1:>6}")

        # Two-ant team: double grip (16 feet total)
        r2 = run_work_face_test(ast["gravity"], DRILL_FORCE_N, 0.30,
                                duration_s=5.0, tool_name="drill")
        stable2 = "YES" if r2["stable"] else "NO"
        print(f"{'':>10} | {'2-ant team':>18} | {'0.30 N':>8} | "
              f"{r2['backward_mm']:>9.1f} | {r2['lift_mm']:>8.1f} | "
              f"{r2['tilt_deg']:>5.1f} | {stable2:>6}")

        # Three-ant team: triple grip (24 feet)
        r3 = run_work_face_test(ast["gravity"], DRILL_FORCE_N, 0.45,
                                duration_s=5.0, tool_name="drill")
        stable3 = "YES" if r3["stable"] else "NO"
        print(f"{'':>10} | {'3-ant team':>18} | {'0.45 N':>8} | "
              f"{r3['backward_mm']:>9.1f} | {r3['lift_mm']:>8.1f} | "
              f"{r3['tilt_deg']:>5.1f} | {stable3:>6}")
        print("-" * len(hdr4))

    # --- Summary ---
    print()
    print("=" * 85)
    print("  HOW SCOOPING WORKS IN MICROGRAVITY")
    print("=" * 85)
    print()
    print("  1. Ant walks to work face along power rail (magnetic highway)")
    print("  2. All 8 feet grip the surface (microspines + studs)")
    print("  3. Mandibles extend drill/scoop tool into the wall")
    print("  4. Drill: N20 motor grinds rock. Cuttings float into hopper")
    print("     (hopper has containment walls -- material can't drift away)")
    print("  5. Scoop: mandibles push blade into loose regolith, sweep into hopper")
    print("  6. In 5 kPa tunnel air: particles drift slowly, don't scatter wildly")
    print("  7. Hopper fills to 200g (~12% per scoop cycle)")
    print("  8. Ant walks back along rail to dump at thermal sorter")
    print()
    print("  KEY INSIGHT: No pile, no heap, no excavation pit.")
    print("  The ant sculpts the tunnel wall directly. Each drill/scoop pass")
    print("  removes a thin layer. The tunnel grows by the wall receding.")
    print("  Like a sculptor removing marble, not a miner digging a hole.")
    print()
    print("  MULTI-ANT DRILLING:")
    print("  At the work face, drilling is a team sport:")
    print("    Driller ant: faces wall, extends drill tool, pushes into rock")
    print("    Brace ant: parks behind driller, grips abdomen socket (1.5 N)")
    print("    Scoop ant: follows behind, catches cuttings floating from drill")
    print("  The brace ant's 8 feet double the total grip. This is how real")
    print("  ants work too -- leaf-cutters brace each other while cutting.")
    print()
    print("  TUNNEL ADVANCE CONVOY (4-5 ants):")
    print("    1. Driller + brace ant at the face (team of 2)")
    print("    2. Plasterer 2-3m behind (sealing walls with paste_nozzle)")
    print("    3. Rail layer 1-2m behind (pressing copper/steel tape)")
    print("    4. Scoop ant shuttling cuttings to thermal sorter")
    print("=" * 85)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n  Total time: {time.time() - t0:.1f}s")
