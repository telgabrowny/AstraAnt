"""Housekeeping monitor -- temperature, power, battery, system health.

Reads all analog/digital sensors that report spacecraft health.
Compares against config thresholds and flags anomalies.
Generates compact health packets for telemetry downlink.

Hardware:
  - Solar panel voltage/current via ADC pins
  - Battery voltage via ADC pin (4S Li-ion, 28V nominal)
  - Thermocouples via ADC pins (bioreactor, bus, exterior)
  - ESP32-S3 internal temperature sensor
  - Free RAM and uptime from MicroPython runtime

All readings stored as simple dicts -- no dataclasses (MicroPython).
"""

import machine
import time
import gc
import struct


def init_health(cfg):
    """Initialize health monitoring hardware from config dict.

    Args:
        cfg: Full mission config dict (from config.json).

    Returns:
        Dict of initialized ADC objects and cached config values.
    """
    power = cfg.get("power", {})
    thermal = cfg.get("thermal", {})
    limits = cfg.get("limits", {})

    hw = {
        "solar_v_adc": None,
        "solar_i_adc": None,
        "battery_v_adc": None,
        "thermo_adcs": [],
        "config": cfg,
    }

    # Solar panel voltage ADC
    try:
        pin = power.get("solar_voltage_pin", 9)
        hw["solar_v_adc"] = machine.ADC(machine.Pin(pin), atten=machine.ADC.ATTN_11DB)
    except Exception:
        pass

    # Solar panel current ADC
    try:
        pin = power.get("solar_current_pin", 10)
        hw["solar_i_adc"] = machine.ADC(machine.Pin(pin), atten=machine.ADC.ATTN_11DB)
    except Exception:
        pass

    # Battery voltage ADC
    try:
        pin = power.get("battery_voltage_pin", 11)
        hw["battery_v_adc"] = machine.ADC(machine.Pin(pin), atten=machine.ADC.ATTN_11DB)
    except Exception:
        pass

    # Thermocouple ADCs
    for pin in thermal.get("thermocouple_pins", []):
        try:
            adc = machine.ADC(machine.Pin(pin), atten=machine.ADC.ATTN_11DB)
            hw["thermo_adcs"].append(adc)
        except Exception:
            hw["thermo_adcs"].append(None)

    return hw


def _adc_to_voltage(adc, scale=3.3, bits=12):
    """Read ADC and convert to voltage.

    Args:
        adc: machine.ADC object (or None).
        scale: Full-scale voltage (3.3V with 11dB attenuation on ESP32).
        bits: ADC resolution.

    Returns:
        Voltage as float, or -1.0 if ADC is None.
    """
    if adc is None:
        return -1.0
    try:
        raw = adc.read()
        return (raw / ((1 << bits) - 1)) * scale
    except Exception:
        return -1.0


def read_solar_voltage(hw):
    """Read solar panel bus voltage (V).

    The solar panels produce up to ~28V through a voltage divider
    (10:1) so the ADC sees 0-3.3V representing 0-33V.
    """
    v_adc = _adc_to_voltage(hw.get("solar_v_adc"))
    if v_adc < 0:
        return -1.0
    return v_adc * 10.0  # 10:1 divider


def read_solar_current(hw):
    """Read solar panel current (A).

    INA219-style current sensor outputs 0-3.3V for 0-10A range.
    """
    v_adc = _adc_to_voltage(hw.get("solar_i_adc"))
    if v_adc < 0:
        return -1.0
    return v_adc * (10.0 / 3.3)  # 0-10A range


def read_battery_voltage(hw):
    """Read battery pack voltage (V).

    4S Li-ion pack: 12.0V (empty) to 16.8V (full).
    Voltage divider (6:1) maps to 0-3.3V ADC range.
    """
    v_adc = _adc_to_voltage(hw.get("battery_v_adc"))
    if v_adc < 0:
        return -1.0
    return v_adc * 6.0  # 6:1 divider


def read_battery_soc(hw):
    """Estimate battery state of charge (0-100%).

    Linear approximation between cell_min_v and cell_max_v.
    """
    pack_v = read_battery_voltage(hw)
    if pack_v < 0:
        return -1

    cfg = hw.get("config", {}).get("power", {})
    cells = cfg.get("battery_cells", 4)
    cell_v = pack_v / max(1, cells)
    cell_min = cfg.get("cell_min_v", 3.0)
    cell_max = cfg.get("cell_max_v", 4.2)

    if cell_v <= cell_min:
        return 0
    if cell_v >= cell_max:
        return 100
    return int(((cell_v - cell_min) / (cell_max - cell_min)) * 100)


def read_temperatures(hw):
    """Read all thermocouple channels.

    Returns:
        List of temperature readings in Celsius. -999 for failed channels.
        Index 0 = bioreactor, index 1 = bus/electronics.
    """
    temps = []
    for adc in hw.get("thermo_adcs", []):
        v = _adc_to_voltage(adc)
        if v < 0:
            temps.append(-999.0)
        else:
            # Type-K thermocouple with AD8495 amplifier:
            # V_out = (T_c * 0.005) + 1.25
            # T_c = (V_out - 1.25) / 0.005
            t_c = (v - 1.25) / 0.005
            temps.append(round(t_c, 1))
    return temps


def read_cpu_temp():
    """Read ESP32-S3 internal temperature sensor.

    Returns:
        CPU temperature in Celsius, or -999 if unavailable.
    """
    try:
        # ESP32 internal temp sensor (MicroPython 1.20+)
        raw = machine.ADC(machine.ADC.HALL)
        # Fallback: use esp32 module if available
        return -999.0
    except Exception:
        pass

    try:
        import esp32
        return esp32.raw_temperature()  # Fahrenheit on some ports
    except Exception:
        return -999.0


def read_system(hw):
    """Read system-level health: CPU temp, free RAM, uptime.

    Returns:
        Dict with cpu_temp_c, free_ram_bytes, uptime_ms.
    """
    gc.collect()
    return {
        "cpu_temp_c": read_cpu_temp(),
        "free_ram_bytes": gc.mem_free(),
        "uptime_ms": time.ticks_ms(),
    }


def read_power(hw):
    """Read all power-related measurements.

    Returns:
        Dict with solar_v, solar_i, solar_w, battery_v, battery_soc.
    """
    sol_v = read_solar_voltage(hw)
    sol_i = read_solar_current(hw)
    sol_w = sol_v * sol_i if (sol_v >= 0 and sol_i >= 0) else -1.0
    bat_v = read_battery_voltage(hw)
    bat_soc = read_battery_soc(hw)

    return {
        "solar_v": round(sol_v, 2),
        "solar_i": round(sol_i, 2),
        "solar_w": round(sol_w, 1),
        "battery_v": round(bat_v, 2),
        "battery_soc": bat_soc,
    }


def check_limits(hw):
    """Compare all readings against config thresholds.

    Returns:
        Tuple of (ok: bool, alerts: list of strings).
        ok is False if any critical limit is exceeded.
    """
    cfg = hw.get("config", {})
    limits = cfg.get("limits", {})
    thermal = cfg.get("thermal", {})
    power_cfg = cfg.get("power", {})

    alerts = []

    # Temperature checks
    temps = read_temperatures(hw)
    t_max = thermal.get("max_temp_c", 45.0)
    t_min = thermal.get("min_temp_c", 5.0)
    for i, t in enumerate(temps):
        if t == -999.0:
            continue
        if t > t_max:
            alerts.append("TEMP_HIGH:ch%d=%.1fC>%.1f" % (i, t, t_max))
        if t < t_min:
            alerts.append("TEMP_LOW:ch%d=%.1fC<%.1f" % (i, t, t_min))

    # CPU temperature
    sys_info = read_system(hw)
    cpu_max = limits.get("cpu_temp_max_c", 85)
    cpu_t = sys_info.get("cpu_temp_c", -999)
    if cpu_t != -999 and cpu_t > cpu_max:
        alerts.append("CPU_HOT:%.1fC>%d" % (cpu_t, cpu_max))

    # Battery checks
    pwr = read_power(hw)
    safe_soc = power_cfg.get("safe_mode_soc_pct", 15)
    if pwr["battery_soc"] >= 0 and pwr["battery_soc"] < safe_soc:
        alerts.append("BAT_LOW:%d%%<%d%%" % (pwr["battery_soc"], safe_soc))

    # Solar overcurrent
    sol_max = limits.get("solar_overcurrent_a", 10.0)
    if pwr["solar_i"] >= 0 and pwr["solar_i"] > sol_max:
        alerts.append("SOL_OVERCURRENT:%.1fA>%.1f" % (pwr["solar_i"], sol_max))

    # RAM check (warn below 32 KB)
    if sys_info["free_ram_bytes"] < 32768:
        alerts.append("LOW_RAM:%d" % sys_info["free_ram_bytes"])

    ok = len(alerts) == 0
    return (ok, alerts)


def generate_health_packet(hw):
    """Generate a compact health summary for telemetry.

    Returns:
        Dict suitable for encoding into a telemetry frame.
        All values are simple types (int, float, str, list).
    """
    pwr = read_power(hw)
    temps = read_temperatures(hw)
    sys_info = read_system(hw)
    ok, alerts = check_limits(hw)

    return {
        "solar_v": pwr["solar_v"],
        "solar_i": pwr["solar_i"],
        "solar_w": pwr["solar_w"],
        "battery_v": pwr["battery_v"],
        "battery_soc": pwr["battery_soc"],
        "temps_c": temps,
        "cpu_temp_c": sys_info["cpu_temp_c"],
        "free_ram": sys_info["free_ram_bytes"],
        "uptime_ms": sys_info["uptime_ms"],
        "ok": ok,
        "alerts": alerts,
    }


def pack_health_binary(packet):
    """Pack health dict into a fixed-size binary blob (32 bytes).

    Format:
        [solar_v:f16][solar_i:f16][bat_v:f16][bat_soc:u8]
        [temp0:i8][temp1:i8][cpu_t:i8][free_ram_kb:u16]
        [uptime_s:u32][alert_flags:u8][pad:13]

    f16 = half-float is not standard in struct, so we use
    scaled integers: voltage * 100 as uint16, current * 100 as uint16.

    Args:
        packet: Dict from generate_health_packet().

    Returns:
        32-byte bytes object.
    """
    buf = bytearray(32)
    # Solar voltage * 100 -> uint16 (0-655.35V range)
    sv = max(0, min(65535, int(packet.get("solar_v", 0) * 100)))
    # Solar current * 100 -> uint16
    si = max(0, min(65535, int(packet.get("solar_i", 0) * 100)))
    # Battery voltage * 100 -> uint16
    bv = max(0, min(65535, int(packet.get("battery_v", 0) * 100)))
    # Battery SOC -> uint8
    bs = max(0, min(255, packet.get("battery_soc", 0)))

    struct.pack_into("<HHHb", buf, 0, sv, si, bv, bs)

    # Temperatures as signed int8 (-128 to 127 C)
    temps = packet.get("temps_c", [])
    for i in range(2):
        t = int(temps[i]) if i < len(temps) and temps[i] != -999 else -128
        t = max(-128, min(127, t))
        struct.pack_into("<b", buf, 7 + i, t)

    # CPU temp
    cpu_t = int(packet.get("cpu_temp_c", -999))
    cpu_t = max(-128, min(127, cpu_t)) if cpu_t != -999 else -128
    struct.pack_into("<b", buf, 9, cpu_t)

    # Free RAM in KB -> uint16
    ram_kb = packet.get("free_ram", 0) // 1024
    struct.pack_into("<H", buf, 10, min(65535, ram_kb))

    # Uptime in seconds -> uint32
    uptime_s = packet.get("uptime_ms", 0) // 1000
    struct.pack_into("<I", buf, 12, uptime_s)

    # Alert flags (bit field)
    flags = 0
    alerts = packet.get("alerts", [])
    for a in alerts:
        if "TEMP_HIGH" in a:
            flags |= 0x01
        if "TEMP_LOW" in a:
            flags |= 0x02
        if "CPU_HOT" in a:
            flags |= 0x04
        if "BAT_LOW" in a:
            flags |= 0x08
        if "SOL_OVERCURRENT" in a:
            flags |= 0x10
        if "LOW_RAM" in a:
            flags |= 0x20
    buf[16] = flags

    return bytes(buf)
