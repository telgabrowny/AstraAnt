"""Attitude Determination and Control System (ADCS).

Determines spacecraft orientation from sun sensors and gyroscope.
Commands cold-gas RCS thrusters for attitude maneuvers.

Sensors:
  - 4x analog sun sensors (photodiodes behind pinhole masks)
  - 3-axis MEMS gyroscope (I2C)

Actuators:
  - 4x cold-gas N2 thrusters (solenoid valves, digital pins)

Modes:
  - Detumble: B-dot style using rate-only feedback
  - Sun-point: orient solar panels toward sun (safe mode)
  - Target-point: orient ion thruster toward target vector

Math is kept to simple trig -- no quaternion library needed.
All vectors are body-frame 3-tuples (x, y, z).
"""

import machine
import math
import time
import struct


def init_adcs(cfg):
    """Initialize ADCS hardware from config.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict of initialized hardware and state variables.
    """
    adcs_cfg = cfg.get("adcs", {})

    hw = {
        "sun_adcs": [],
        "rcs_pins": [],
        "gyro_i2c": None,
        "gyro_addr": adcs_cfg.get("gyro_i2c_addr", 0x28),
        "detumble_gain": adcs_cfg.get("detumble_gain", 0.001),
        "pointing_tol_deg": adcs_cfg.get("pointing_tolerance_deg", 2.0),
        "alpha": adcs_cfg.get("complementary_alpha", 0.98),
        # State
        "attitude_deg": (0.0, 0.0, 0.0),  # roll, pitch, yaw estimate
        "rates_dps": (0.0, 0.0, 0.0),     # angular rates deg/s
        "sun_vector": (0.0, 0.0, 1.0),    # unit sun vector in body frame
        "sun_valid": False,
        "last_update_ms": 0,
    }

    # Sun sensor ADCs (4 photodiodes, 90 deg apart)
    for pin in adcs_cfg.get("sun_sensor_pins", []):
        try:
            adc = machine.ADC(machine.Pin(pin), atten=machine.ADC.ATTN_11DB)
            hw["sun_adcs"].append(adc)
        except Exception:
            hw["sun_adcs"].append(None)

    # RCS thruster solenoid pins (active high)
    for pin in adcs_cfg.get("rcs_pins", []):
        try:
            p = machine.Pin(pin, machine.Pin.OUT, value=0)
            hw["rcs_pins"].append(p)
        except Exception:
            hw["rcs_pins"].append(None)

    return hw


def read_sun_sensors(hw):
    """Read 4 sun sensor channels, compute sun direction vector.

    Sun sensors are arranged in a cross pattern:
      Index 0: +X face
      Index 1: -X face
      Index 2: +Y face
      Index 3: -Y face

    The differential between opposing pairs gives the sun angle
    in that axis. Assumes sensors follow cos(theta) response.

    Args:
        hw: ADCS hardware dict.

    Returns:
        Tuple (sun_x, sun_y, sun_z) unit vector in body frame.
        Updates hw['sun_vector'] and hw['sun_valid'].
    """
    readings = []
    for adc in hw.get("sun_adcs", []):
        if adc is None:
            readings.append(0.0)
            continue
        try:
            raw = adc.read()
            v = raw / 4095.0  # Normalize to 0-1
            readings.append(v)
        except Exception:
            readings.append(0.0)

    # Need at least 4 sensors
    while len(readings) < 4:
        readings.append(0.0)

    total = sum(readings)
    if total < 0.01:
        # No sun detected (eclipse or sensor failure)
        hw["sun_valid"] = False
        return hw["sun_vector"]

    # Differential computation
    # X axis: sensor[0] (+X) vs sensor[1] (-X)
    sun_x = readings[0] - readings[1]
    # Y axis: sensor[2] (+Y) vs sensor[3] (-Y)
    sun_y = readings[2] - readings[3]
    # Z axis: inferred from remaining intensity
    # If both pairs read high, sun is roughly along Z
    avg_pair = (readings[0] + readings[1] + readings[2] + readings[3]) / 4.0
    sun_z = avg_pair  # Positive = sun on +Z side

    # Normalize
    mag = math.sqrt(sun_x * sun_x + sun_y * sun_y + sun_z * sun_z)
    if mag < 0.001:
        hw["sun_valid"] = False
        return hw["sun_vector"]

    sun_vec = (sun_x / mag, sun_y / mag, sun_z / mag)
    hw["sun_vector"] = sun_vec
    hw["sun_valid"] = True
    return sun_vec


def read_gyro(hw, i2c):
    """Read 3-axis gyroscope rates.

    Assumes a simple MEMS gyro (e.g. BMX055 or similar) on I2C.
    Registers: 0x02-0x07 = X/Y/Z rate data (16-bit signed, LSB first).
    Scale: 2000 dps full scale = 16.4 LSB/dps.

    Args:
        hw: ADCS hardware dict.
        i2c: machine.I2C object.

    Returns:
        Tuple (rate_x, rate_y, rate_z) in degrees/second.
    """
    addr = hw.get("gyro_addr", 0x28)
    try:
        data = i2c.readfrom_mem(addr, 0x02, 6)
        rx = struct.unpack_from("<h", data, 0)[0] / 16.4
        ry = struct.unpack_from("<h", data, 2)[0] / 16.4
        rz = struct.unpack_from("<h", data, 4)[0] / 16.4
        hw["rates_dps"] = (rx, ry, rz)
        return (rx, ry, rz)
    except Exception:
        return hw["rates_dps"]


def estimate_attitude(hw, i2c):
    """Update attitude estimate using complementary filter.

    Fuses gyro integration (fast, drifts) with sun sensor
    direction (slow, absolute). Alpha blends between them.

    Args:
        hw: ADCS hardware dict.
        i2c: machine.I2C object.

    Returns:
        Tuple (roll, pitch, yaw) in degrees.
    """
    now_ms = time.ticks_ms()
    dt_s = time.ticks_diff(now_ms, hw.get("last_update_ms", now_ms)) / 1000.0
    if dt_s <= 0 or dt_s > 1.0:
        dt_s = 0.02  # Default 50 Hz
    hw["last_update_ms"] = now_ms

    # Read sensors
    rates = read_gyro(hw, i2c)
    sun_vec = read_sun_sensors(hw)

    alpha = hw.get("alpha", 0.98)
    roll, pitch, yaw = hw.get("attitude_deg", (0.0, 0.0, 0.0))

    # Gyro integration (dead reckoning)
    roll_gyro = roll + rates[0] * dt_s
    pitch_gyro = pitch + rates[1] * dt_s
    yaw_gyro = yaw + rates[2] * dt_s

    if hw.get("sun_valid", False):
        # Sun sensor gives roll and pitch reference
        # Sun vector in body frame -> roll = atan2(sun_y, sun_z)
        #                            pitch = atan2(sun_x, sun_z)
        sx, sy, sz = sun_vec
        if abs(sz) > 0.01:
            sun_roll = math.degrees(math.atan2(sy, sz))
            sun_pitch = math.degrees(math.atan2(sx, sz))
        else:
            sun_roll = roll_gyro
            sun_pitch = pitch_gyro

        # Complementary filter blend
        roll = alpha * roll_gyro + (1.0 - alpha) * sun_roll
        pitch = alpha * pitch_gyro + (1.0 - alpha) * sun_pitch
        yaw = yaw_gyro  # No absolute yaw reference from sun alone
    else:
        roll = roll_gyro
        pitch = pitch_gyro
        yaw = yaw_gyro

    # Wrap to -180..+180
    roll = ((roll + 180) % 360) - 180
    pitch = ((pitch + 180) % 360) - 180
    yaw = ((yaw + 180) % 360) - 180

    hw["attitude_deg"] = (roll, pitch, yaw)
    return (roll, pitch, yaw)


def _fire_thruster(hw, thruster_id, duration_ms):
    """Fire a single RCS thruster for a duration.

    Args:
        hw: ADCS hardware dict.
        thruster_id: Index 0-3 into rcs_pins.
        duration_ms: Pulse duration in milliseconds (max 2000).
    """
    pins = hw.get("rcs_pins", [])
    if thruster_id < 0 or thruster_id >= len(pins):
        return
    pin = pins[thruster_id]
    if pin is None:
        return

    duration_ms = max(1, min(2000, duration_ms))
    try:
        pin.value(1)
        time.sleep_ms(duration_ms)
        pin.value(0)
    except Exception:
        # Ensure thruster is off even on error
        try:
            pin.value(0)
        except Exception:
            pass


def _all_thrusters_off(hw):
    """Safety: ensure all RCS thrusters are off."""
    for pin in hw.get("rcs_pins", []):
        if pin is not None:
            try:
                pin.value(0)
            except Exception:
                pass


def detumble(hw, i2c):
    """Detumble using rate-damping (B-dot style).

    Fires thrusters proportional to and opposing angular rates.
    Continues until rates are below 1 deg/s on all axes.

    Args:
        hw: ADCS hardware dict.
        i2c: machine.I2C object.

    Returns:
        True if detumble complete (rates < 1 dps), False if still tumbling.
    """
    rates = read_gyro(hw, i2c)
    gain = hw.get("detumble_gain", 0.001)

    # Rate magnitude
    rate_mag = math.sqrt(sum(r * r for r in rates))
    if rate_mag < 1.0:
        _all_thrusters_off(hw)
        return True

    # Proportional opposing pulses
    # Thruster 0/1 control X-axis rotation
    # Thruster 2/3 control Y-axis rotation
    # (simplified: no Z-axis control with 4 thrusters in this config)
    pulse_x = int(abs(rates[0]) * gain * 1000)
    pulse_y = int(abs(rates[1]) * gain * 1000)
    pulse_x = max(5, min(500, pulse_x))
    pulse_y = max(5, min(500, pulse_y))

    if rates[0] > 1.0:
        _fire_thruster(hw, 0, pulse_x)
    elif rates[0] < -1.0:
        _fire_thruster(hw, 1, pulse_x)

    if rates[1] > 1.0:
        _fire_thruster(hw, 2, pulse_y)
    elif rates[1] < -1.0:
        _fire_thruster(hw, 3, pulse_y)

    return False


def sun_point(hw, i2c):
    """Orient solar panels toward the sun (safe mode attitude).

    Solar panels are on the +Z face. Target: sun_vector = (0, 0, 1).
    Uses bang-bang thruster control with deadband.

    Args:
        hw: ADCS hardware dict.
        i2c: machine.I2C object.

    Returns:
        True if pointing is within tolerance, False otherwise.
    """
    estimate_attitude(hw, i2c)

    if not hw.get("sun_valid", False):
        # No sun -- can't point, just maintain current attitude
        return False

    sx, sy, sz = hw["sun_vector"]
    tol = hw.get("pointing_tol_deg", 2.0)

    # Error angles (small angle approximation)
    # To get sun on +Z, we need roll and pitch near 0
    roll_err = math.degrees(math.atan2(sy, max(0.01, sz)))
    pitch_err = math.degrees(math.atan2(sx, max(0.01, sz)))

    on_target = abs(roll_err) < tol and abs(pitch_err) < tol

    if on_target:
        _all_thrusters_off(hw)
        return True

    # Bang-bang with minimum pulse
    MIN_PULSE = 10  # ms
    if roll_err > tol:
        _fire_thruster(hw, 0, MIN_PULSE)
    elif roll_err < -tol:
        _fire_thruster(hw, 1, MIN_PULSE)

    if pitch_err > tol:
        _fire_thruster(hw, 2, MIN_PULSE)
    elif pitch_err < -tol:
        _fire_thruster(hw, 3, MIN_PULSE)

    return False


def point_at_target(hw, i2c, target_vec):
    """Orient spacecraft so -X axis points at target vector.

    The ion thruster fires along -X, so to thrust toward target,
    we need target_vec aligned with -X body axis.

    Args:
        hw: ADCS hardware dict.
        i2c: machine.I2C object.
        target_vec: (x, y, z) unit vector in body frame toward target.

    Returns:
        True if pointing error < tolerance.
    """
    estimate_attitude(hw, i2c)
    tol = hw.get("pointing_tol_deg", 2.0)

    # Target should be along -X. Error = angle between target_vec and (-1,0,0)
    tx, ty, tz = target_vec
    mag = math.sqrt(tx * tx + ty * ty + tz * tz)
    if mag < 0.001:
        return False

    tx, ty, tz = tx / mag, ty / mag, tz / mag

    # Pointing error: angle between target_vec and -X
    # cos(error) = dot(target, (-1,0,0)) = -tx
    dot = -tx
    dot = max(-1.0, min(1.0, dot))
    error_deg = math.degrees(math.acos(dot))

    if error_deg < tol:
        _all_thrusters_off(hw)
        return True

    # Use Y and Z components of target to determine correction
    # If ty > 0, need to rotate about Z (yaw)
    # If tz > 0, need to rotate about Y (pitch)
    MIN_PULSE = 10

    if abs(ty) > math.sin(math.radians(tol)):
        if ty > 0:
            _fire_thruster(hw, 2, MIN_PULSE)
        else:
            _fire_thruster(hw, 3, MIN_PULSE)

    if abs(tz) > math.sin(math.radians(tol)):
        if tz > 0:
            _fire_thruster(hw, 0, MIN_PULSE)
        else:
            _fire_thruster(hw, 1, MIN_PULSE)

    return False


def get_attitude(hw):
    """Get current attitude estimate.

    Returns:
        Tuple (roll, pitch, yaw) in degrees.
    """
    return hw.get("attitude_deg", (0.0, 0.0, 0.0))


def get_rates(hw):
    """Get current angular rates.

    Returns:
        Tuple (rx, ry, rz) in degrees per second.
    """
    return hw.get("rates_dps", (0.0, 0.0, 0.0))


def safe_shutdown(hw):
    """Emergency shutdown: all thrusters off."""
    _all_thrusters_off(hw)
