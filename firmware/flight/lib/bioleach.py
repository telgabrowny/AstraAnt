"""Bioleaching operations controller.

Manages the chemical and biological processing of asteroid material
inside the sealed Kapton+Kevlar membrane bag.

Process sequence:
  1. HEAT: Solar concentrators warm the interior to ~30C
  2. INOCULATE: Release freeze-dried bacteria into solution
  3. LEACH: Bacteria dissolve metals from regolith over days/weeks
  4. ELECTROFORM: Run electrowinning to deposit metals as wire/plate
  5. DRAIN: Transfer spent solution to storage
  6. FEED: Replenish nutrients and restart cycle

The bioleaching cycle runs continuously once started. The main loop
calls tick_bioleach() periodically (every ~1 second).

Chemistry:
  A. ferrooxidans + A. thiooxidans generate H2SO4 from sulfides
  Fe3+ leaches Cu, Ni, Co from sulfide minerals
  Electrowinning deposits: Cu (+0.34V), Ni (-0.26V), Co (-0.28V), Fe (-0.44V)

Temperature control: PID loop driving a resistive heater.
pH monitoring: target pH ~2.0 for optimal bioleaching.
"""

import machine
import time
import math

# -- Bioleach sub-states --
BIO_IDLE = 0
BIO_HEAT = 1
BIO_INOCULATE = 2
BIO_LEACH = 3
BIO_ELECTROFORM = 4
BIO_DRAIN = 5
BIO_FEED = 6

BIO_STATE_NAMES = {
    0: "IDLE", 1: "HEAT", 2: "INOCULATE", 3: "LEACH",
    4: "ELECTROFORM", 5: "DRAIN", 6: "FEED",
}

# -- Electrowinning metal sequence (voltage thresholds) --
# Deposit in order from most noble to least noble
METALS = [
    {"name": "Cu", "voltage": 0.34, "atomic_mass": 63.55, "valence": 2},
    {"name": "Ni", "voltage": 0.26, "atomic_mass": 58.69, "valence": 2},
    {"name": "Co", "voltage": 0.28, "atomic_mass": 58.93, "valence": 2},
    {"name": "Fe", "voltage": 0.44, "atomic_mass": 55.85, "valence": 2},
]


def init_bioleach(cfg):
    """Initialize bioleaching hardware and state.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict with bioleach hardware and state.
    """
    bio_cfg = cfg.get("bioleach", {})
    thermal = cfg.get("thermal", {})

    state = {
        "sub_state": BIO_IDLE,
        "state_entry_ms": 0,

        # PID state
        "pid_integral": 0.0,
        "pid_last_error": 0.0,
        "pid_last_ms": 0,
        "pid_kp": thermal.get("pid_kp", 2.0),
        "pid_ki": thermal.get("pid_ki", 0.1),
        "pid_kd": thermal.get("pid_kd", 0.5),
        "target_temp_c": bio_cfg.get("temp_target_c", 30.0),

        # Heater
        "heater_pwm": None,
        "heater_duty": 0.0,
        "max_duty": thermal.get("heater_max_duty", 0.8),

        # pH monitoring
        "ph_adc": None,
        "current_ph": 7.0,
        "target_ph": bio_cfg.get("target_ph", 2.0),
        "ph_alarm_low": bio_cfg.get("ph_alarm_low", 1.0),
        "ph_alarm_high": bio_cfg.get("ph_alarm_high", 4.0),

        # Pump
        "pump_pwm": None,
        "pump_duty": bio_cfg.get("pump_duty_default", 0.5),

        # Electrowinning
        "ewin_current_a": bio_cfg.get("electrowin_current_a", 50.0),
        "ewin_voltage": 0.0,
        "ewin_metal_idx": 0,  # Index into METALS list
        "faraday_const": bio_cfg.get("faraday_const", 96485),

        # Production tracking
        "metal_deposited_g": {"Cu": 0.0, "Ni": 0.0, "Co": 0.0, "Fe": 0.0},
        "wire_produced_m": 0.0,
        "leach_cycles": 0,
        "total_leach_hours": 0.0,

        # Temperature reading (from health module)
        "current_temp_c": 25.0,
    }

    # Heater PWM
    heater_pin = bio_cfg.get("heater_pin", thermal.get("heater_pin"))
    if heater_pin is not None:
        try:
            pwm = machine.PWM(machine.Pin(heater_pin))
            pwm.freq(10)  # Low frequency for resistive heater
            pwm.duty_u16(0)
            state["heater_pwm"] = pwm
        except Exception:
            pass

    # pH sensor ADC
    ph_pin = bio_cfg.get("ph_sensor_pin")
    if ph_pin is not None:
        try:
            state["ph_adc"] = machine.ADC(machine.Pin(ph_pin),
                                           atten=machine.ADC.ATTN_11DB)
        except Exception:
            pass

    # Peristaltic pump PWM
    pump_pin = bio_cfg.get("pump_pin")
    if pump_pin is not None:
        try:
            pwm = machine.PWM(machine.Pin(pump_pin))
            pwm.freq(1000)
            pwm.duty_u16(0)
            state["pump_pwm"] = pwm
        except Exception:
            pass

    return state


def pid_temperature(bio, measured_temp_c):
    """PID temperature controller for bioreactor heater.

    Computes heater PWM duty cycle to maintain target temperature.

    Args:
        bio: Bioleach state dict.
        measured_temp_c: Current temperature reading from thermocouple.

    Returns:
        Heater duty cycle (0.0 to max_duty).
    """
    bio["current_temp_c"] = measured_temp_c
    target = bio.get("target_temp_c", 30.0)
    error = target - measured_temp_c

    now_ms = time.ticks_ms()
    dt_s = time.ticks_diff(now_ms, bio.get("pid_last_ms", now_ms)) / 1000.0
    if dt_s <= 0 or dt_s > 10.0:
        dt_s = 1.0
    bio["pid_last_ms"] = now_ms

    kp = bio.get("pid_kp", 2.0)
    ki = bio.get("pid_ki", 0.1)
    kd = bio.get("pid_kd", 0.5)

    # Proportional
    p_term = kp * error

    # Integral with anti-windup
    bio["pid_integral"] += error * dt_s
    bio["pid_integral"] = max(-50.0, min(50.0, bio["pid_integral"]))
    i_term = ki * bio["pid_integral"]

    # Derivative
    d_error = (error - bio.get("pid_last_error", 0.0)) / dt_s
    d_term = kd * d_error
    bio["pid_last_error"] = error

    # Output
    output = p_term + i_term + d_term
    max_duty = bio.get("max_duty", 0.8)
    duty = max(0.0, min(max_duty, output / 100.0))

    # Apply to heater PWM
    pwm = bio.get("heater_pwm")
    if pwm is not None:
        try:
            pwm.duty_u16(int(duty * 65535))
        except Exception:
            pass

    bio["heater_duty"] = duty
    return duty


def monitor_ph(bio):
    """Read pH sensor and log the value.

    pH sensor outputs 0-3.3V for pH 0-14 range.

    Args:
        bio: Bioleach state dict.

    Returns:
        Current pH reading (float).
    """
    adc = bio.get("ph_adc")
    if adc is None:
        return bio.get("current_ph", 7.0)

    try:
        raw = adc.read()
        voltage = (raw / 4095.0) * 3.3
        # Linear mapping: 0V = pH 0, 3.3V = pH 14
        ph = (voltage / 3.3) * 14.0
        bio["current_ph"] = round(ph, 2)
    except Exception:
        pass

    return bio["current_ph"]


def run_pump(bio, duty_cycle=None):
    """Control peristaltic pump.

    Args:
        bio: Bioleach state dict.
        duty_cycle: Pump duty cycle 0.0-1.0 (None = use default).
    """
    if duty_cycle is None:
        duty_cycle = bio.get("pump_duty", 0.5)

    duty_cycle = max(0.0, min(1.0, duty_cycle))
    pwm = bio.get("pump_pwm")
    if pwm is not None:
        try:
            pwm.duty_u16(int(duty_cycle * 65535))
        except Exception:
            pass
    bio["pump_duty"] = duty_cycle


def stop_pump(bio):
    """Stop the peristaltic pump.

    Args:
        bio: Bioleach state dict.
    """
    run_pump(bio, 0.0)


def run_electrowinning(bio, voltage=None):
    """Set electrowinning cell voltage for metal deposition.

    The electrowinning cell deposits different metals at different
    voltages. Run at each voltage sequentially to separate metals.

    Args:
        bio: Bioleach state dict.
        voltage: Cell voltage (V). None = use current metal's voltage.

    Returns:
        Current metal being deposited (name string).
    """
    if voltage is not None:
        bio["ewin_voltage"] = voltage
    else:
        idx = bio.get("ewin_metal_idx", 0)
        if idx < len(METALS):
            bio["ewin_voltage"] = METALS[idx]["voltage"]

    # The actual DAC/power supply control would go here.
    # On ESP32-S3, we would use a DAC pin or PWM + filter.
    # For now, we track the setpoint for telemetry.

    idx = bio.get("ewin_metal_idx", 0)
    if idx < len(METALS):
        return METALS[idx]["name"]
    return "Fe"  # Default to iron


def wire_production_rate(bio):
    """Calculate wire production rate from Faraday's law.

    m_dot = (I * M) / (n * F)

    where:
      I = electrowinning current (A)
      M = atomic mass of metal (g/mol)
      n = valence (electrons transferred per atom)
      F = Faraday constant (96485 C/mol)

    Returns:
        Tuple (rate_g_per_hr, metal_name).
    """
    idx = bio.get("ewin_metal_idx", 0)
    if idx >= len(METALS):
        idx = 3  # Default to Fe

    metal = METALS[idx]
    current = bio.get("ewin_current_a", 50.0)
    F = bio.get("faraday_const", 96485)

    # Faraday's law: mass rate in g/s
    rate_g_per_s = (current * metal["atomic_mass"]) / (metal["valence"] * F)
    rate_g_per_hr = rate_g_per_s * 3600.0

    return (round(rate_g_per_hr, 2), metal["name"])


def tick_bioleach(bio, temp_readings):
    """Advance the bioleaching state machine by one tick.

    Args:
        bio: Bioleach state dict.
        temp_readings: List of temperature readings from health module.

    Returns:
        Current sub-state code (int).
    """
    st = bio["sub_state"]
    now = time.ticks_ms()
    elapsed_ms = time.ticks_diff(now, bio.get("state_entry_ms", now))
    elapsed_hr = elapsed_ms / 3_600_000.0

    # Get bioreactor temperature (first channel)
    temp_c = temp_readings[0] if temp_readings else 25.0
    if temp_c == -999.0:
        temp_c = bio.get("current_temp_c", 25.0)

    # ---- IDLE ----
    if st == BIO_IDLE:
        pass  # Waiting for main loop to start bioleaching

    # ---- HEAT: bring to operating temperature ----
    elif st == BIO_HEAT:
        pid_temperature(bio, temp_c)
        target = bio.get("target_temp_c", 30.0)
        if abs(temp_c - target) < 2.0 and elapsed_ms > 60_000:
            # Stable at temperature for >1 minute
            bio["sub_state"] = BIO_INOCULATE
            bio["state_entry_ms"] = now

    # ---- INOCULATE: release bacteria into solution ----
    elif st == BIO_INOCULATE:
        pid_temperature(bio, temp_c)
        run_pump(bio, 0.3)  # Gentle circulation to distribute bacteria
        # Inoculation takes ~30 minutes for bacteria to activate
        if elapsed_ms > 1_800_000:  # 30 minutes
            bio["sub_state"] = BIO_LEACH
            bio["state_entry_ms"] = now

    # ---- LEACH: active bioleaching ----
    elif st == BIO_LEACH:
        pid_temperature(bio, temp_c)
        run_pump(bio)  # Full circulation
        monitor_ph(bio)

        # Track leaching time
        bio["total_leach_hours"] += elapsed_hr

        # Check pH (indicates bacterial activity)
        ph = bio.get("current_ph", 7.0)
        if ph < bio.get("ph_alarm_low", 1.0):
            # pH too low -- acid concentration too high, slow bacteria
            run_pump(bio, 0.8)  # Increase circulation to dilute

        # Transition to electroforming after minimum leach time (24 hours)
        # In practice, ground station commands this transition
        if elapsed_ms > 86_400_000:  # 24 hours
            bio["sub_state"] = BIO_ELECTROFORM
            bio["state_entry_ms"] = now

    # ---- ELECTROFORM: deposit metals as wire/plate ----
    elif st == BIO_ELECTROFORM:
        pid_temperature(bio, temp_c)
        run_pump(bio, 0.3)  # Slow circulation during deposition
        metal_name = run_electrowinning(bio)

        # Track production
        rate, name = wire_production_rate(bio)
        if name in bio["metal_deposited_g"]:
            bio["metal_deposited_g"][name] += rate * (elapsed_hr)

        # Run each metal for ~6 hours, then advance
        if elapsed_ms > 21_600_000:  # 6 hours
            idx = bio.get("ewin_metal_idx", 0)
            if idx < len(METALS) - 1:
                bio["ewin_metal_idx"] = idx + 1
                bio["state_entry_ms"] = now
            else:
                # All metals processed, drain and restart
                bio["ewin_metal_idx"] = 0
                bio["sub_state"] = BIO_DRAIN
                bio["state_entry_ms"] = now

    # ---- DRAIN: transfer spent solution ----
    elif st == BIO_DRAIN:
        pid_temperature(bio, temp_c)
        run_pump(bio, 0.8)  # High flow to drain
        # Drain for 30 minutes
        if elapsed_ms > 1_800_000:
            stop_pump(bio)
            bio["sub_state"] = BIO_FEED
            bio["state_entry_ms"] = now

    # ---- FEED: replenish nutrients ----
    elif st == BIO_FEED:
        pid_temperature(bio, temp_c)
        run_pump(bio, 0.5)  # Mix nutrients
        # Feed cycle: 15 minutes
        if elapsed_ms > 900_000:
            bio["leach_cycles"] += 1
            bio["sub_state"] = BIO_LEACH
            bio["state_entry_ms"] = now

    return bio["sub_state"]


def start_bioleach(bio):
    """Start the bioleaching process from IDLE.

    Args:
        bio: Bioleach state dict.
    """
    bio["sub_state"] = BIO_HEAT
    bio["state_entry_ms"] = time.ticks_ms()
    bio["pid_integral"] = 0.0
    bio["pid_last_error"] = 0.0


def get_bioleach_summary(bio):
    """Get bioleach state for telemetry.

    Returns:
        Dict with current sub-state and production stats.
    """
    rate, metal = wire_production_rate(bio)
    return {
        "sub_state": bio.get("sub_state", 0),
        "sub_state_name": BIO_STATE_NAMES.get(bio.get("sub_state", 0), "?"),
        "temp_c": bio.get("current_temp_c", 0.0),
        "heater_duty": round(bio.get("heater_duty", 0.0), 2),
        "ph": bio.get("current_ph", 0.0),
        "ewin_voltage": bio.get("ewin_voltage", 0.0),
        "current_metal": metal,
        "production_rate_g_hr": rate,
        "metal_deposited_g": bio.get("metal_deposited_g", {}),
        "leach_cycles": bio.get("leach_cycles", 0),
        "total_leach_hours": round(bio.get("total_leach_hours", 0.0), 1),
    }


def safe_shutdown(bio):
    """Emergency shutdown: heater off, pump off, electrowinning off."""
    pwm = bio.get("heater_pwm")
    if pwm is not None:
        try:
            pwm.duty_u16(0)
        except Exception:
            pass
    stop_pump(bio)
    bio["ewin_voltage"] = 0.0
    bio["heater_duty"] = 0.0
