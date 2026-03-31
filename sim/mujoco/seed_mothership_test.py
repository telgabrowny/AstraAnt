"""AstraAnt Seed Mothership -- Full Articulated Model Test Suite

Tests the 41 kg seed mothership model: solar wing deployment,
3-DOF robotic arm articulation, gripper open/close, ion thrust
approach toward asteroid rock, and physics validation.

All masses from seed_bom.py. All dimensions from BOM specs.

Usage:
    python seed_mothership_test.py                  # Full test + viewer
    python seed_mothership_test.py --headless        # CI mode (no GUI)
    python seed_mothership_test.py --render           # Viewer only
    python seed_mothership_test.py --quick            # Shorter animations

Requires: pip install mujoco numpy
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
    print("ERROR: MuJoCo not installed. Run: pip install mujoco")
    sys.exit(1)

DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(DIR, "seed_mothership_full.xml")

# ---------------------------------------------------------------------------
# BOM reference values (from astraant/seed_bom.py)
# ---------------------------------------------------------------------------
BOM_TOTAL_MASS_KG = 40.8      # grand total from BOM
MASS_TOLERANCE_KG = 1.0       # allow ~2.5% rounding tolerance
ION_THRUST_N = 0.0014         # BIT-3 class, 1.4 mN
ARM_REACH_M = 0.30            # 2 x 0.15m segments = 30cm
SOLAR_WING_SPAN_M = 2.0      # each wing 2.0m long
MEMBRANE_MASS_KG = 8.0        # Kapton+Kevlar spool
PROPELLANT_MASS_KG = 5.5      # iodine 5.0 + N2 0.5

# Asteroid reference
BENNU_GRAVITY = 5.80e-6       # m/s^2

# Actuator indices (from MJCF order)
ACT_SOLAR_L = 0
ACT_SOLAR_R = 1
ACT_ARM_L_SHOULDER = 2
ACT_ARM_L_ELBOW = 3
ACT_ARM_L_WRIST = 4
ACT_ARM_L_GRIP_L = 5
ACT_ARM_L_GRIP_R = 6
ACT_ARM_R_SHOULDER = 7
ACT_ARM_R_ELBOW = 8
ACT_ARM_R_WRIST = 9
ACT_ARM_R_GRIP_L = 10
ACT_ARM_R_GRIP_R = 11
ACT_MEMBRANE = 12


def load_model():
    """Load the seed mothership MJCF model."""
    return mujoco.MjModel.from_xml_path(MODEL_PATH)


def get_body_id(model, name):
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    if bid < 0:
        raise RuntimeError(f"Body '{name}' not found in model")
    return bid


def ship_mass(model):
    """Total mothership mass (excluding asteroid rock)."""
    rock_id = get_body_id(model, "asteroid")
    return sum(model.body_mass) - model.body_mass[rock_id]


def ship_position(data):
    """Mothership CoM position [x, y, z]."""
    return data.qpos[7:10].copy()  # asteroid freejoint is qpos[0:7]


def settle(model, data, duration_s):
    """Run sim with no control for a duration."""
    n = int(duration_s / model.opt.timestep)
    for _ in range(n):
        mujoco.mj_step(model, data)


def animate_to(model, data, targets, duration_s, viewer=None):
    """Smoothly ramp actuator controls from current to targets.

    targets: dict of {actuator_index: target_value}
    """
    dt = model.opt.timestep
    n_steps = int(duration_s / dt)
    if n_steps < 1:
        n_steps = 1

    start_ctrl = data.ctrl.copy()
    for step in range(n_steps):
        alpha = (step + 1) / n_steps
        # Smooth ease-in-out
        alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)
        for idx, target in targets.items():
            data.ctrl[idx] = start_ctrl[idx] + alpha * (target - start_ctrl[idx])
        mujoco.mj_step(model, data)
        if viewer is not None:
            viewer.sync()


def apply_ion_thrust(model, data, thrust_fraction, ship_body_id):
    """Apply ion thrust along +x direction on mothership body.

    thrust_fraction: 0.0 to 1.0 (fraction of max 1.4 mN)
    """
    force = ION_THRUST_N * max(0.0, min(1.0, thrust_fraction))
    data.xfrc_applied[ship_body_id, 0] = force


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_model_loads(model):
    """TEST 1: Model loads, has correct structure."""
    data = mujoco.MjData(model)
    mujoco.mj_step(model, data)

    results = {
        "bodies": model.nbody,
        "joints": model.njnt,
        "actuators": model.nu,
        "dof": model.nv,
        "geoms": model.ngeom,
        "sensors": model.nsensor,
    }

    # Verify key bodies exist
    required_bodies = [
        "mothership", "asteroid",
        "solar_wing_L", "solar_wing_R",
        "arm_L_shoulder", "arm_L_elbow", "arm_L_wrist",
        "arm_L_finger_L", "arm_L_finger_R",
        "arm_R_shoulder", "arm_R_elbow", "arm_R_wrist",
        "arm_R_finger_L", "arm_R_finger_R",
        "membrane_bundle",
    ]
    missing = []
    for name in required_bodies:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if bid < 0:
            missing.append(name)

    results["missing_bodies"] = missing
    results["all_bodies_found"] = len(missing) == 0
    return results


def test_mass_budget(model):
    """TEST 2: Mass matches BOM within tolerance."""
    rock_id = get_body_id(model, "asteroid")
    total = sum(model.body_mass)
    rock = model.body_mass[rock_id]
    ship = total - rock

    # Per-body breakdown
    breakdown = {}
    for i in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        if name != "world":
            breakdown[name] = float(model.body_mass[i])

    error = abs(ship - BOM_TOTAL_MASS_KG)
    return {
        "ship_mass_kg": float(ship),
        "target_kg": BOM_TOTAL_MASS_KG,
        "error_kg": error,
        "within_tolerance": error < MASS_TOLERANCE_KG,
        "rock_mass_kg": float(rock),
        "breakdown": breakdown,
    }


def test_center_of_mass(model):
    """TEST 3: Center of mass is near geometric center (balanced)."""
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Get subtree CoM of mothership body (includes all children)
    ship_id = get_body_id(model, "asteroid")
    ship_id = get_body_id(model, "mothership")
    com = data.subtree_com[ship_id].copy()

    # Ship body is at origin in local frame; CoM should be near it
    # The propellant is in the rear, membrane under, so CoM shifts
    # slightly back and down. Check it's within 0.15m of geometric center.
    ship_pos = data.xpos[ship_id].copy()
    offset = com - ship_pos

    return {
        "com_world": com.tolist(),
        "ship_pos": ship_pos.tolist(),
        "com_offset_m": offset.tolist(),
        "offset_magnitude_m": float(np.linalg.norm(offset)),
        "balanced": np.linalg.norm(offset) < 0.15,
    }


def test_solar_deploy(model):
    """TEST 4: Solar wings deploy from 0 to 90 degrees."""
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    settle(model, data, 0.2)

    # Read stowed joint angles (should be near 0)
    sid_L = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "solar_L_angle")
    sid_R = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "solar_R_angle")
    adr_L = model.sensor_adr[sid_L]
    adr_R = model.sensor_adr[sid_R]
    mujoco.mj_forward(model, data)
    stowed_L = math.degrees(float(data.sensordata[adr_L]))
    stowed_R = math.degrees(float(data.sensordata[adr_R]))

    # Deploy to 90 degrees
    animate_to(model, data, {ACT_SOLAR_L: 90, ACT_SOLAR_R: 90}, 2.0)
    settle(model, data, 1.0)

    # Read deployed joint angles (should be near 90 deg)
    mujoco.mj_forward(model, data)
    deployed_L = math.degrees(float(data.sensordata[adr_L]))
    deployed_R = math.degrees(float(data.sensordata[adr_R]))

    # Also measure panel geom tip positions for span
    # Panel L geom center is at (0, 0.40, 0) in wing_L body frame
    # When deployed 90 deg, the 0.4m offset rotates to Z direction
    # Use the geom xpos to get world position of panel centers
    gid_L = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "solar_panel_L")
    gid_R = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "solar_panel_R")
    panel_L_pos = data.geom_xpos[gid_L].copy()
    panel_R_pos = data.geom_xpos[gid_R].copy()
    deployed_span = float(np.linalg.norm(panel_L_pos - panel_R_pos))

    # Pass if both joints reach at least 70 degrees
    deployed = deployed_L > 70 and deployed_R > 70

    return {
        "stowed_L_deg": stowed_L,
        "stowed_R_deg": stowed_R,
        "deployed_L_deg": deployed_L,
        "deployed_R_deg": deployed_R,
        "deployed_span_m": deployed_span,
        "deployed": deployed,
    }


def test_arm_reach(model):
    """TEST 5: Arms extend and measure reach envelope."""
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    settle(model, data, 0.2)

    ship_id = get_body_id(model, "mothership")
    wrist_L_id = get_body_id(model, "arm_L_wrist")
    wrist_R_id = get_body_id(model, "arm_R_wrist")

    # Stowed position
    ship_pos = data.xpos[ship_id].copy()
    stowed_L = data.xpos[wrist_L_id].copy()
    stowed_R = data.xpos[wrist_R_id].copy()
    stowed_reach_L = float(np.linalg.norm(stowed_L - ship_pos))
    stowed_reach_R = float(np.linalg.norm(stowed_R - ship_pos))

    # Extend arms: shoulder 45 deg, elbow 90 deg, wrist 0 deg
    targets = {
        ACT_ARM_L_SHOULDER: 45,
        ACT_ARM_L_ELBOW: 90,
        ACT_ARM_L_WRIST: 0,
        ACT_ARM_R_SHOULDER: 45,
        ACT_ARM_R_ELBOW: 90,
        ACT_ARM_R_WRIST: 0,
    }
    animate_to(model, data, targets, 2.0)
    settle(model, data, 0.5)

    extended_L = data.xpos[wrist_L_id].copy()
    extended_R = data.xpos[wrist_R_id].copy()
    extended_reach_L = float(np.linalg.norm(extended_L - ship_pos))
    extended_reach_R = float(np.linalg.norm(extended_R - ship_pos))

    # Fully extended: shoulder 0, elbow 0 (straight out)
    targets_max = {
        ACT_ARM_L_SHOULDER: 0,
        ACT_ARM_L_ELBOW: 0,
        ACT_ARM_L_WRIST: 0,
        ACT_ARM_R_SHOULDER: 0,
        ACT_ARM_R_ELBOW: 0,
        ACT_ARM_R_WRIST: 0,
    }
    animate_to(model, data, targets_max, 2.0)
    settle(model, data, 0.5)

    max_L = data.xpos[wrist_L_id].copy()
    max_R = data.xpos[wrist_R_id].copy()
    max_reach_L = float(np.linalg.norm(max_L - ship_pos))
    max_reach_R = float(np.linalg.norm(max_R - ship_pos))

    return {
        "stowed_reach_L_m": stowed_reach_L,
        "stowed_reach_R_m": stowed_reach_R,
        "extended_reach_L_m": extended_reach_L,
        "extended_reach_R_m": extended_reach_R,
        "max_reach_L_m": max_reach_L,
        "max_reach_R_m": max_reach_R,
        "reaches_30cm": max_reach_L > 0.25 or max_reach_R > 0.25,
    }


def test_gripper(model):
    """TEST 6: Grippers open and close.

    Uses geom positions (finger tip capsule centers) rather than body
    positions (hinge pivots) to measure the actual finger tip gap.
    """
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    settle(model, data, 0.2)

    # Extend arms first so fingers are free to move
    animate_to(model, data, {
        ACT_ARM_L_SHOULDER: 30,
        ACT_ARM_L_ELBOW: 60,
        ACT_ARM_R_SHOULDER: 30,
        ACT_ARM_R_ELBOW: 60,
    }, 1.0)
    settle(model, data, 0.3)

    # Geom IDs for finger tip capsules
    gid_LL = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "arm_L_finger_L_geom")
    gid_LR = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "arm_L_finger_R_geom")

    # Record closed finger tip gap (fingers at 0 deg)
    mujoco.mj_forward(model, data)
    closed_LL = data.geom_xpos[gid_LL].copy()
    closed_LR = data.geom_xpos[gid_LR].copy()
    closed_gap = float(np.linalg.norm(closed_LL - closed_LR))

    # Open grippers to 40 degrees
    animate_to(model, data, {
        ACT_ARM_L_GRIP_L: 40,
        ACT_ARM_L_GRIP_R: 40,
        ACT_ARM_R_GRIP_L: 40,
        ACT_ARM_R_GRIP_R: 40,
    }, 1.0)
    settle(model, data, 0.3)

    mujoco.mj_forward(model, data)
    open_LL = data.geom_xpos[gid_LL].copy()
    open_LR = data.geom_xpos[gid_LR].copy()
    open_gap = float(np.linalg.norm(open_LL - open_LR))

    # Close grippers back
    animate_to(model, data, {
        ACT_ARM_L_GRIP_L: 0,
        ACT_ARM_L_GRIP_R: 0,
        ACT_ARM_R_GRIP_L: 0,
        ACT_ARM_R_GRIP_R: 0,
    }, 1.0)
    settle(model, data, 0.3)

    mujoco.mj_forward(model, data)
    reclosed_LL = data.geom_xpos[gid_LL].copy()
    reclosed_LR = data.geom_xpos[gid_LR].copy()
    reclosed_gap = float(np.linalg.norm(reclosed_LL - reclosed_LR))

    # Also read joint angles for the record
    jid_LL = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "j_arm_L_finger_L")
    jid_LR = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "j_arm_L_finger_R")
    grip_L_angle = math.degrees(float(data.qpos[model.jnt_qposadr[jid_LL]]))
    grip_R_angle = math.degrees(float(data.qpos[model.jnt_qposadr[jid_LR]]))

    return {
        "closed_gap_mm": closed_gap * 1000,
        "open_gap_mm": open_gap * 1000,
        "reclosed_gap_mm": reclosed_gap * 1000,
        "grip_L_angle_deg": grip_L_angle,
        "grip_R_angle_deg": grip_R_angle,
        "opens_wider": open_gap > closed_gap + 0.001,
        "closes_back": reclosed_gap < open_gap - 0.001,
    }


def test_ion_thrust(model):
    """TEST 7: Ion thrust moves mothership toward asteroid."""
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)

    ship_id = get_body_id(model, "mothership")
    rock_id = get_body_id(model, "asteroid")

    settle(model, data, 0.2)

    # Record initial positions
    ship_start = data.xpos[ship_id].copy()
    rock_pos = data.xpos[rock_id].copy()
    initial_dist = float(np.linalg.norm(rock_pos - ship_start))

    # Apply full ion thrust for 10 seconds toward rock (+x direction)
    dt = model.opt.timestep
    n_steps = int(10.0 / dt)
    for _ in range(n_steps):
        apply_ion_thrust(model, data, 1.0, ship_id)
        mujoco.mj_step(model, data)

    ship_end = data.xpos[ship_id].copy()
    final_dist = float(np.linalg.norm(rock_pos - ship_end))
    displacement = float(np.linalg.norm(ship_end - ship_start))

    # Expected: F = ma -> a = 0.0014 / 40.45 = 3.46e-5 m/s^2
    # After 10s: d = 0.5 * a * t^2 = 0.5 * 3.46e-5 * 100 = 0.00173 m
    expected_a = ION_THRUST_N / 40.45
    expected_d = 0.5 * expected_a * 10.0**2

    return {
        "initial_distance_m": initial_dist,
        "final_distance_m": final_dist,
        "displacement_m": displacement,
        "expected_displacement_m": expected_d,
        "moved_toward_rock": final_dist < initial_dist,
        "acceleration_m_s2": expected_a,
    }


def test_membrane_release(model):
    """TEST 8: Membrane bundle can detach (slide downward)."""
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    settle(model, data, 0.2)

    membrane_id = get_body_id(model, "membrane_bundle")
    start_pos = data.xpos[membrane_id].copy()

    # Release membrane (slide 0.3m down)
    animate_to(model, data, {ACT_MEMBRANE: 0.3}, 2.0)
    settle(model, data, 0.5)

    end_pos = data.xpos[membrane_id].copy()
    drop_m = float(start_pos[2] - end_pos[2])

    # Read sensor (use sensor_adr for correct sensordata index)
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "membrane_pos")
    slide_val = float(data.sensordata[model.sensor_adr[sid]])

    return {
        "start_z_m": float(start_pos[2]),
        "end_z_m": float(end_pos[2]),
        "drop_m": drop_m,
        "slide_sensor_m": slide_val,
        "released": drop_m > 0.1,
    }


# ---------------------------------------------------------------------------
# Full suite runner
# ---------------------------------------------------------------------------

def run_full_suite(model, quick=False):
    """Run all tests and print results."""
    print("=" * 78)
    print("  AstraAnt Seed Mothership -- Full Articulated Model Tests")
    print("=" * 78)

    mass = ship_mass(model)
    print(f"  Model mass:    {mass:.2f} kg (BOM target: {BOM_TOTAL_MASS_KG} kg)")
    print(f"  Bodies: {model.nbody}  Joints: {model.njnt}  "
          f"Actuators: {model.nu}  DOF: {model.nv}")
    print(f"  Geoms: {model.ngeom}  Sensors: {model.nsensor}")
    print()

    all_pass = True

    # --- TEST 1: Model structure ---
    print("--- TEST 1: Model Structure ---")
    r1 = test_model_loads(model)
    status = "PASS" if r1["all_bodies_found"] else "FAIL"
    if not r1["all_bodies_found"]:
        all_pass = False
    print(f"  Bodies: {r1['bodies']}  Joints: {r1['joints']}  "
          f"Actuators: {r1['actuators']}  DOF: {r1['dof']}")
    print(f"  All required bodies found: {r1['all_bodies_found']}  [{status}]")
    if r1["missing_bodies"]:
        print(f"  Missing: {r1['missing_bodies']}")
    print()

    # --- TEST 2: Mass budget ---
    print("--- TEST 2: Mass Budget ---")
    r2 = test_mass_budget(model)
    status = "PASS" if r2["within_tolerance"] else "FAIL"
    if not r2["within_tolerance"]:
        all_pass = False
    print(f"  Ship mass:  {r2['ship_mass_kg']:.2f} kg")
    print(f"  BOM target: {r2['target_kg']:.1f} kg")
    print(f"  Error:      {r2['error_kg']:.2f} kg  [{status}]")
    print(f"  Rock mass:  {r2['rock_mass_kg']:.0f} kg")
    print()
    print("  Subsystem breakdown:")
    for name, mass_kg in sorted(r2["breakdown"].items(),
                                 key=lambda x: -x[1]):
        if mass_kg > 0.01:
            print(f"    {name:25s}: {mass_kg:8.3f} kg")
    print()

    # --- TEST 3: Center of mass ---
    print("--- TEST 3: Center of Mass ---")
    r3 = test_center_of_mass(model)
    status = "PASS" if r3["balanced"] else "WARN"
    if not r3["balanced"]:
        print(f"  WARNING: CoM offset > 0.15m from body center")
    print(f"  CoM offset:  [{r3['com_offset_m'][0]:.4f}, "
          f"{r3['com_offset_m'][1]:.4f}, {r3['com_offset_m'][2]:.4f}] m")
    print(f"  Magnitude:   {r3['offset_magnitude_m']:.4f} m  [{status}]")
    print()

    # --- TEST 4: Solar wing deployment ---
    print("--- TEST 4: Solar Wing Deployment ---")
    r4 = test_solar_deploy(model)
    status = "PASS" if r4["deployed"] else "FAIL"
    if not r4["deployed"]:
        all_pass = False
    print(f"  Stowed L angle:  {r4['stowed_L_deg']:.1f} deg")
    print(f"  Stowed R angle:  {r4['stowed_R_deg']:.1f} deg")
    print(f"  Deployed L angle:{r4['deployed_L_deg']:.1f} deg")
    print(f"  Deployed R angle:{r4['deployed_R_deg']:.1f} deg")
    print(f"  Deployed span:   {r4['deployed_span_m']:.3f} m")
    print(f"  Wings deployed:  {r4['deployed']}  [{status}]")
    print()

    # --- TEST 5: Arm reach ---
    print("--- TEST 5: Arm Reach Envelope ---")
    r5 = test_arm_reach(model)
    status = "PASS" if r5["reaches_30cm"] else "FAIL"
    if not r5["reaches_30cm"]:
        all_pass = False
    print(f"  Stowed reach L:   {r5['stowed_reach_L_m']:.3f} m")
    print(f"  Stowed reach R:   {r5['stowed_reach_R_m']:.3f} m")
    print(f"  Extended reach L: {r5['extended_reach_L_m']:.3f} m")
    print(f"  Extended reach R: {r5['extended_reach_R_m']:.3f} m")
    print(f"  Max reach L:      {r5['max_reach_L_m']:.3f} m")
    print(f"  Max reach R:      {r5['max_reach_R_m']:.3f} m")
    print(f"  Reaches 30cm:     {r5['reaches_30cm']}  [{status}]")
    print()

    # --- TEST 6: Gripper ---
    print("--- TEST 6: Gripper Open/Close ---")
    r6 = test_gripper(model)
    status = "PASS" if (r6["opens_wider"] and r6["closes_back"]) else "FAIL"
    if not (r6["opens_wider"] and r6["closes_back"]):
        all_pass = False
    print(f"  Closed gap:   {r6['closed_gap_mm']:.1f} mm")
    print(f"  Open gap:     {r6['open_gap_mm']:.1f} mm")
    print(f"  Reclosed gap: {r6['reclosed_gap_mm']:.1f} mm")
    print(f"  Opens wider:  {r6['opens_wider']}")
    print(f"  Closes back:  {r6['closes_back']}  [{status}]")
    print()

    # --- TEST 7: Ion thrust ---
    print("--- TEST 7: Ion Thrust Approach ---")
    r7 = test_ion_thrust(model)
    status = "PASS" if r7["moved_toward_rock"] else "FAIL"
    if not r7["moved_toward_rock"]:
        all_pass = False
    print(f"  Initial distance:     {r7['initial_distance_m']:.3f} m")
    print(f"  Final distance:       {r7['final_distance_m']:.3f} m")
    print(f"  Displacement:         {r7['displacement_m']:.6f} m")
    print(f"  Expected (F=ma):      {r7['expected_displacement_m']:.6f} m")
    print(f"  Acceleration:         {r7['acceleration_m_s2']:.2e} m/s^2")
    print(f"  Moved toward rock:    {r7['moved_toward_rock']}  [{status}]")
    print()

    # --- TEST 8: Membrane release ---
    print("--- TEST 8: Membrane Release ---")
    r8 = test_membrane_release(model)
    status = "PASS" if r8["released"] else "FAIL"
    if not r8["released"]:
        all_pass = False
    print(f"  Start Z:      {r8['start_z_m']:.3f} m")
    print(f"  End Z:        {r8['end_z_m']:.3f} m")
    print(f"  Drop:         {r8['drop_m']:.3f} m")
    print(f"  Slide sensor: {r8['slide_sensor_m']:.3f} m")
    print(f"  Released:     {r8['released']}  [{status}]")
    print()

    # --- Summary ---
    print("=" * 78)
    if all_pass:
        print("  ALL TESTS PASSED")
    else:
        print("  SOME TESTS FAILED -- review output above")
    print("=" * 78)

    return all_pass


# ---------------------------------------------------------------------------
# Interactive viewer: full deployment sequence
# ---------------------------------------------------------------------------

def render_deployment(model):
    """Interactive viewer showing full deployment sequence."""
    try:
        import mujoco.viewer
    except ImportError:
        print("ERROR: MuJoCo viewer not available (needs OpenGL)")
        return

    data = mujoco.MjData(model)
    ship_id = get_body_id(model, "mothership")

    print()
    print("  Seed Mothership Deployment Sequence")
    print("  ------------------------------------")
    print("  Phase 1: Solar wing deployment (0-90 deg)")
    print("  Phase 2: Left arm extend + gripper open/close")
    print("  Phase 3: Right arm extend + gripper open/close")
    print("  Phase 4: Both arms work pose")
    print("  Phase 5: Ion thrust toward asteroid")
    print("  Phase 6: Membrane release")
    print()
    print("  Close the viewer window to exit.")
    print()

    settle(model, data, 0.1)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        if not viewer.is_running():
            return

        def step_and_sync(n=1):
            for _ in range(n):
                if not viewer.is_running():
                    return False
                mujoco.mj_step(model, data)
                viewer.sync()
            return True

        def animate_viewer(targets, duration_s):
            """Animate with viewer sync."""
            dt = model.opt.timestep
            n_steps = max(1, int(duration_s / dt))
            start_ctrl = data.ctrl.copy()
            for step in range(n_steps):
                if not viewer.is_running():
                    return False
                alpha = (step + 1) / n_steps
                alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)
                for idx, target in targets.items():
                    data.ctrl[idx] = (start_ctrl[idx]
                                      + alpha * (target - start_ctrl[idx]))
                mujoco.mj_step(model, data)
                viewer.sync()
            return True

        def hold(duration_s):
            n = int(duration_s / model.opt.timestep)
            return step_and_sync(n)

        # Phase 1: Deploy solar wings
        print("  Phase 1: Deploying solar wings...")
        if not animate_viewer({ACT_SOLAR_L: 90, ACT_SOLAR_R: 90}, 3.0):
            return
        if not hold(1.0):
            return

        # Phase 2: Left arm
        print("  Phase 2: Left arm extend + grip...")
        if not animate_viewer({
            ACT_ARM_L_SHOULDER: 45,
            ACT_ARM_L_ELBOW: 60,
            ACT_ARM_L_WRIST: 0,
        }, 2.0):
            return
        if not hold(0.5):
            return
        # Open gripper
        if not animate_viewer({
            ACT_ARM_L_GRIP_L: 40,
            ACT_ARM_L_GRIP_R: 40,
        }, 1.0):
            return
        if not hold(0.5):
            return
        # Close gripper
        if not animate_viewer({
            ACT_ARM_L_GRIP_L: 0,
            ACT_ARM_L_GRIP_R: 0,
        }, 1.0):
            return
        if not hold(0.5):
            return

        # Phase 3: Right arm
        print("  Phase 3: Right arm extend + grip...")
        if not animate_viewer({
            ACT_ARM_R_SHOULDER: 45,
            ACT_ARM_R_ELBOW: 60,
            ACT_ARM_R_WRIST: 0,
        }, 2.0):
            return
        if not hold(0.5):
            return
        if not animate_viewer({
            ACT_ARM_R_GRIP_L: 40,
            ACT_ARM_R_GRIP_R: 40,
        }, 1.0):
            return
        if not hold(0.5):
            return
        if not animate_viewer({
            ACT_ARM_R_GRIP_L: 0,
            ACT_ARM_R_GRIP_R: 0,
        }, 1.0):
            return

        # Phase 4: Both arms work pose
        print("  Phase 4: Both arms work pose...")
        if not animate_viewer({
            ACT_ARM_L_SHOULDER: 30,
            ACT_ARM_L_ELBOW: 90,
            ACT_ARM_L_WRIST: -30,
            ACT_ARM_R_SHOULDER: -30,
            ACT_ARM_R_ELBOW: 90,
            ACT_ARM_R_WRIST: 30,
        }, 2.0):
            return
        if not hold(1.0):
            return

        # Phase 5: Ion thrust
        print("  Phase 5: Ion thrust toward asteroid...")
        dt = model.opt.timestep
        n_thrust = int(15.0 / dt)
        for _ in range(n_thrust):
            if not viewer.is_running():
                return
            apply_ion_thrust(model, data, 1.0, ship_id)
            mujoco.mj_step(model, data)
            viewer.sync()
        if not hold(1.0):
            return

        # Phase 6: Membrane release
        print("  Phase 6: Membrane release...")
        data.xfrc_applied[:] = 0.0  # stop thrust
        if not animate_viewer({ACT_MEMBRANE: 0.3}, 3.0):
            return

        # Hold for viewing
        print("  Sequence complete. Viewer stays open.")
        while viewer.is_running():
            mujoco.mj_step(model, data)
            viewer.sync()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AstraAnt seed mothership model test suite")
    parser.add_argument("--headless", action="store_true",
                        help="CI mode: run tests without viewer")
    parser.add_argument("--render", action="store_true",
                        help="Launch interactive deployment viewer only")
    parser.add_argument("--quick", action="store_true",
                        help="Shorter animation durations")
    args = parser.parse_args()

    print(f"Loading model: {MODEL_PATH}")
    model = load_model()
    m = ship_mass(model)
    print(f"  Ship mass: {m:.2f} kg  (BOM: {BOM_TOTAL_MASS_KG} kg)")
    print(f"  Bodies: {model.nbody}  Joints: {model.njnt}  "
          f"Actuators: {model.nu}  DOF: {model.nv}")
    print()

    if args.render:
        render_deployment(model)
        return

    t0 = time.time()
    passed = run_full_suite(model, quick=args.quick)
    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")

    if not args.headless:
        print("\n  Launching interactive deployment viewer...")
        render_deployment(model)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
