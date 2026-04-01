"""Asteroid capture sequence state machine.

Manages the multi-step process of approaching, gripping, and
wrapping a small (~10m) C-type asteroid in a Kapton+Kevlar membrane.

Sequence:
  APPROACH -> SLOW -> STATION_KEEP -> ARM_DEPLOY -> GRIP ->
  MEMBRANE -> SEAL -> DONE

Each state has:
  - Entry conditions (must be true to enter)
  - Actions (what happens while in this state)
  - Exit conditions (when to transition to next state)
  - Timeout (abort if exceeded)
  - Abort behavior (what to do on failure)

Hardware:
  - 2x 3-DOF robotic arms (shoulder, elbow, wrist + gripper)
  - Spring-loaded membrane spool (single release pin)
  - Pressure sensor (confirms membrane seal)
  - Servo current monitoring (confirms grip contact)

The capture sequence requires a ground command to arm (safety
interlock). Once armed, it proceeds autonomously but can be
aborted at any point.
"""

import machine
import time

# -- Capture sub-states --
CAP_IDLE = 0
CAP_APPROACH = 1
CAP_SLOW = 2
CAP_STATION_KEEP = 3
CAP_ARM_DEPLOY = 4
CAP_GRIP = 5
CAP_MEMBRANE = 6
CAP_SEAL = 7
CAP_DONE = 8
CAP_ABORT = 9

CAP_STATE_NAMES = {
    0: "IDLE",
    1: "APPROACH",
    2: "SLOW",
    3: "STATION_KEEP",
    4: "ARM_DEPLOY",
    5: "GRIP",
    6: "MEMBRANE",
    7: "SEAL",
    8: "DONE",
    9: "ABORT",
}

# -- Timeouts (milliseconds) --
APPROACH_TIMEOUT_MS = 3600_000    # 1 hour
SLOW_TIMEOUT_MS = 1800_000        # 30 minutes
STATION_KEEP_TIMEOUT_MS = 600_000  # 10 minutes
ARM_DEPLOY_TIMEOUT_MS = 120_000   # 2 minutes
GRIP_TIMEOUT_MS = 300_000         # 5 minutes
MEMBRANE_TIMEOUT_MS = 600_000     # 10 minutes
SEAL_TIMEOUT_MS = 300_000         # 5 minutes


def init_capture(cfg):
    """Initialize capture hardware and state.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict with capture hardware and state machine.
    """
    cap_cfg = cfg.get("capture", {})

    state = {
        "sub_state": CAP_IDLE,
        "state_entry_ms": 0,
        "armed": False,
        "grip_confirmed": False,
        "membrane_deployed": False,
        "seal_confirmed": False,
        "abort_reason": "",
        "arm_servos": [],
        "gripper_servos": [],
        "membrane_pin": None,
        "stow_angles": cap_cfg.get("arm_stow_angles", [0, 90, 0, 0, 90, 0, 0, 0]),
        "extend_angles": cap_cfg.get("arm_extend_angles", [45, 45, 0, 45, 45, 0, 0, 0]),
        "grip_close": cap_cfg.get("grip_close_angle", 10),
        "grip_open": cap_cfg.get("grip_open_angle", 80),
        "grip_threshold_ma": cap_cfg.get("grip_current_threshold_ma", 200),
        "approach_speed": cap_cfg.get("approach_speed_mps", 0.001),
        "station_keep_range": cap_cfg.get("station_keep_range_m", 5.0),
    }

    # Initialize arm servos (8 channels: 3 per arm + 2 spare)
    for pin in cap_cfg.get("arm_servo_pins", []):
        try:
            pwm = machine.PWM(machine.Pin(pin))
            pwm.freq(50)
            state["arm_servos"].append(pwm)
        except Exception:
            state["arm_servos"].append(None)

    # Initialize gripper servos
    for pin in cap_cfg.get("gripper_pins", []):
        try:
            pwm = machine.PWM(machine.Pin(pin))
            pwm.freq(50)
            state["gripper_servos"].append(pwm)
        except Exception:
            state["gripper_servos"].append(None)

    # Membrane release pin (pyrotechnic or solenoid)
    mem_pin = cap_cfg.get("membrane_release_pin", None)
    if mem_pin is not None:
        try:
            state["membrane_pin"] = machine.Pin(mem_pin, machine.Pin.OUT, value=0)
        except Exception:
            pass

    return state


def _set_servo_angle(servo, angle_deg):
    """Set a servo to a specific angle (0-180 degrees).

    Args:
        servo: machine.PWM object (or None).
        angle_deg: Target angle in degrees.
    """
    if servo is None:
        return
    angle_deg = max(0, min(180, angle_deg))
    # Standard servo: 500-2500 us pulse at 50 Hz
    pulse_us = 500 + (angle_deg / 180.0) * 2000
    try:
        servo.duty_ns(int(pulse_us * 1000))
    except Exception:
        pass


def _read_servo_current_ma(servo):
    """Estimate servo current from PWM feedback (simplified).

    In production this would read an INA219 on the servo power line.
    Here we return a simulated value -- real hardware reads the
    current sense resistor.

    Args:
        servo: machine.PWM object.

    Returns:
        Estimated current in milliamps (placeholder).
    """
    # Placeholder: real implementation reads INA219 or ADC shunt
    # A stalled servo draws ~500-800 mA, free-running ~100 mA
    return 100


def arm_deploy(cap):
    """Extend robotic arms from stowed to operational position.

    Moves each arm servo to the extend_angles configuration.

    Args:
        cap: Capture state dict.

    Returns:
        True when all servos have reached target positions.
    """
    targets = cap.get("extend_angles", [])
    servos = cap.get("arm_servos", [])

    for i, servo in enumerate(servos):
        angle = targets[i] if i < len(targets) else 90
        _set_servo_angle(servo, angle)

    # Allow time for servos to reach position
    time.sleep_ms(1000)
    return True


def arm_stow(cap):
    """Retract robotic arms to stowed position.

    Args:
        cap: Capture state dict.

    Returns:
        True when stowed.
    """
    targets = cap.get("stow_angles", [])
    servos = cap.get("arm_servos", [])

    for i, servo in enumerate(servos):
        angle = targets[i] if i < len(targets) else 0
        _set_servo_angle(servo, angle)

    time.sleep_ms(1000)
    return True


def grip_rock(cap):
    """Close grippers and verify contact via current spike.

    Args:
        cap: Capture state dict.

    Returns:
        True if grip is confirmed (current exceeds threshold).
    """
    close_angle = cap.get("grip_close", 10)
    threshold = cap.get("grip_threshold_ma", 200)

    for servo in cap.get("gripper_servos", []):
        _set_servo_angle(servo, close_angle)

    time.sleep_ms(500)

    # Check current on each gripper
    grip_ok = True
    for servo in cap.get("gripper_servos", []):
        current = _read_servo_current_ma(servo)
        if current < threshold:
            grip_ok = False

    cap["grip_confirmed"] = grip_ok
    return grip_ok


def release_grip(cap):
    """Open grippers.

    Args:
        cap: Capture state dict.
    """
    open_angle = cap.get("grip_open", 80)
    for servo in cap.get("gripper_servos", []):
        _set_servo_angle(servo, open_angle)
    cap["grip_confirmed"] = False


def deploy_membrane(cap):
    """Release the Kapton+Kevlar membrane spool.

    Fires the release mechanism (solenoid or pyro pin). The membrane
    is spring-loaded and deploys by unspooling over the asteroid.

    This is a one-shot action -- the membrane cannot be retracted.

    Args:
        cap: Capture state dict.

    Returns:
        True if release pin was fired.
    """
    pin = cap.get("membrane_pin")
    if pin is None:
        cap["abort_reason"] = "membrane pin not initialized"
        return False

    try:
        # Fire release for 500ms (solenoid) or 50ms (pyro)
        pin.value(1)
        time.sleep_ms(500)
        pin.value(0)
        cap["membrane_deployed"] = True
        return True
    except Exception as e:
        cap["abort_reason"] = "membrane release failed: %s" % str(e)
        return False


def check_seal(cap):
    """Verify membrane seal by checking for pressure retention.

    In the full system, a pressure sensor inside the membrane bag
    detects slight positive pressure from outgassing.

    Args:
        cap: Capture state dict.

    Returns:
        True if seal is confirmed.
    """
    # Placeholder: real implementation reads pressure sensor
    # The membrane should show >0.1 kPa within 10 minutes of sealing
    # if the drawstring closure worked properly.
    if cap.get("membrane_deployed", False):
        cap["seal_confirmed"] = True
        return True
    return False


def tick_capture(cap, range_to_target_m, nav_state):
    """Advance the capture state machine by one tick.

    Called from the main loop. Checks conditions and transitions
    between sub-states.

    Args:
        cap: Capture state dict.
        range_to_target_m: Distance to asteroid surface in meters.
        nav_state: Navigator state dict (for velocity etc).

    Returns:
        Current sub-state code (int).
    """
    st = cap["sub_state"]
    now = time.ticks_ms()
    elapsed = time.ticks_diff(now, cap.get("state_entry_ms", now))

    # ---- IDLE: waiting for arm command ----
    if st == CAP_IDLE:
        if cap.get("armed", False):
            cap["sub_state"] = CAP_APPROACH
            cap["state_entry_ms"] = now
        return cap["sub_state"]

    # ---- APPROACH: closing distance to asteroid ----
    elif st == CAP_APPROACH:
        if elapsed > APPROACH_TIMEOUT_MS:
            _abort(cap, "approach timeout")
            return cap["sub_state"]

        if range_to_target_m >= 0 and range_to_target_m < 50.0:
            # Within 50m, slow down
            cap["sub_state"] = CAP_SLOW
            cap["state_entry_ms"] = now

    # ---- SLOW: final approach, reduce velocity ----
    elif st == CAP_SLOW:
        if elapsed > SLOW_TIMEOUT_MS:
            _abort(cap, "slow approach timeout")
            return cap["sub_state"]

        if range_to_target_m >= 0 and range_to_target_m < 10.0:
            cap["sub_state"] = CAP_STATION_KEEP
            cap["state_entry_ms"] = now

    # ---- STATION_KEEP: hold position near asteroid ----
    elif st == CAP_STATION_KEEP:
        if elapsed > STATION_KEEP_TIMEOUT_MS:
            _abort(cap, "station keeping timeout")
            return cap["sub_state"]

        sk_range = cap.get("station_keep_range", 5.0)
        if range_to_target_m >= 0 and range_to_target_m < sk_range:
            # Stable at target range, deploy arms
            cap["sub_state"] = CAP_ARM_DEPLOY
            cap["state_entry_ms"] = now

    # ---- ARM_DEPLOY: extend robotic arms ----
    elif st == CAP_ARM_DEPLOY:
        if elapsed > ARM_DEPLOY_TIMEOUT_MS:
            _abort(cap, "arm deploy timeout")
            return cap["sub_state"]

        if arm_deploy(cap):
            cap["sub_state"] = CAP_GRIP
            cap["state_entry_ms"] = now

    # ---- GRIP: close grippers on rock ----
    elif st == CAP_GRIP:
        if elapsed > GRIP_TIMEOUT_MS:
            _abort(cap, "grip timeout")
            return cap["sub_state"]

        if grip_rock(cap):
            cap["sub_state"] = CAP_MEMBRANE
            cap["state_entry_ms"] = now
        else:
            # Retry grip after a brief pause
            release_grip(cap)
            time.sleep_ms(2000)

    # ---- MEMBRANE: deploy wrapping membrane ----
    elif st == CAP_MEMBRANE:
        if elapsed > MEMBRANE_TIMEOUT_MS:
            _abort(cap, "membrane deploy timeout")
            return cap["sub_state"]

        if deploy_membrane(cap):
            cap["sub_state"] = CAP_SEAL
            cap["state_entry_ms"] = now
        else:
            _abort(cap, cap.get("abort_reason", "membrane failed"))

    # ---- SEAL: verify membrane seal ----
    elif st == CAP_SEAL:
        if elapsed > SEAL_TIMEOUT_MS:
            # Seal timeout is not fatal -- membrane may still work
            # Proceed to DONE with a warning
            cap["sub_state"] = CAP_DONE
            cap["state_entry_ms"] = now
            return cap["sub_state"]

        if check_seal(cap):
            cap["sub_state"] = CAP_DONE
            cap["state_entry_ms"] = now

    # ---- DONE: capture complete ----
    elif st == CAP_DONE:
        pass  # Stay here until main loop transitions to BIOLEACH

    # ---- ABORT: something failed ----
    elif st == CAP_ABORT:
        # Stay in abort until ground commands reset
        pass

    return cap["sub_state"]


def _abort(cap, reason):
    """Transition to abort state.

    Args:
        cap: Capture state dict.
        reason: Human-readable abort reason string.
    """
    cap["sub_state"] = CAP_ABORT
    cap["abort_reason"] = reason
    cap["state_entry_ms"] = time.ticks_ms()

    # Safety: release grippers, stow arms
    release_grip(cap)
    try:
        arm_stow(cap)
    except Exception:
        pass


def reset_capture(cap):
    """Reset capture state machine to IDLE.

    Called by ground command after abort resolution.

    Args:
        cap: Capture state dict.
    """
    cap["sub_state"] = CAP_IDLE
    cap["armed"] = False
    cap["grip_confirmed"] = False
    cap["membrane_deployed"] = False
    cap["seal_confirmed"] = False
    cap["abort_reason"] = ""
    cap["state_entry_ms"] = time.ticks_ms()


def get_capture_summary(cap):
    """Get capture state for telemetry.

    Returns:
        Dict with current sub-state and status flags.
    """
    return {
        "sub_state": cap.get("sub_state", 0),
        "sub_state_name": CAP_STATE_NAMES.get(cap.get("sub_state", 0), "?"),
        "armed": cap.get("armed", False),
        "grip_confirmed": cap.get("grip_confirmed", False),
        "membrane_deployed": cap.get("membrane_deployed", False),
        "seal_confirmed": cap.get("seal_confirmed", False),
        "abort_reason": cap.get("abort_reason", ""),
    }


def safe_shutdown(cap):
    """Emergency shutdown: release grippers, stow arms, safe all pins."""
    release_grip(cap)
    try:
        arm_stow(cap)
    except Exception:
        pass
    pin = cap.get("membrane_pin")
    if pin is not None:
        try:
            pin.value(0)
        except Exception:
            pass
