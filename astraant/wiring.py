"""Wiring diagram generator -- produces pin-to-pin connection maps for building real ants.

Reads ant configs and part datasheets to generate a complete wiring guide
that you could hand to someone with the BOM and they'd know exactly
what connects to what.
"""

from __future__ import annotations

from typing import Any

from .configs import load_all_ant_configs


# Pin mappings for common MCUs
MCU_PINS = {
    "rp2040": {
        "name": "Raspberry Pi Pico (RP2040)",
        "voltage": "3.3V logic, 5V VBUS input",
        "gpio_count": 26,
        "i2c": [{"sda": "GP4", "scl": "GP5", "bus": "I2C0"},
                {"sda": "GP6", "scl": "GP7", "bus": "I2C1"}],
        "spi": [{"mosi": "GP19", "miso": "GP16", "sck": "GP18", "cs": "GP17", "bus": "SPI0"}],
        "uart": [{"tx": "GP0", "rx": "GP1", "bus": "UART0"}],
        "pwm": ["GP2", "GP3", "GP8", "GP9", "GP10", "GP11",
                 "GP12", "GP13", "GP14", "GP15"],
        "adc": ["GP26", "GP27", "GP28"],
        "power_out": "3V3(OUT)",
        "power_in": "VSYS (1.8-5.5V) or VBUS (5V USB)",
        "ground": "GND (pins 3,8,13,18,23,28,33,38)",
    },
    "esp32_s3": {
        "name": "ESP32-S3-WROOM-1",
        "voltage": "3.3V logic, 5V VIN",
        "gpio_count": 45,
        "i2c": [{"sda": "GPIO8", "scl": "GPIO9", "bus": "I2C0"}],
        "spi": [{"mosi": "GPIO11", "miso": "GPIO13", "sck": "GPIO12",
                 "cs": "GPIO10", "bus": "SPI2"}],
        "uart": [{"tx": "GPIO43", "rx": "GPIO44", "bus": "UART0"}],
        "pwm": ["GPIO1", "GPIO2", "GPIO3", "GPIO4", "GPIO5", "GPIO6",
                 "GPIO7", "GPIO14", "GPIO15", "GPIO16", "GPIO17", "GPIO18"],
        "adc": ["GPIO1", "GPIO2", "GPIO3", "GPIO4", "GPIO5", "GPIO6", "GPIO7"],
        "power_out": "3V3",
        "power_in": "5V (VIN pin)",
        "ground": "GND",
    },
}

# Wiring templates for common components
COMPONENT_WIRING = {
    "sg90_servo": {
        "pins": {"signal": "PWM", "vcc": "5V", "gnd": "GND"},
        "wire_colors": {"signal": "orange/white", "vcc": "red", "gnd": "brown/black"},
        "notes": "Signal wire needs 3.3V->5V level shifter if MCU is 3.3V logic. "
                 "Or drive directly -- most SG90s respond to 3.3V PWM.",
        "pwm_freq_hz": 50,
        "pwm_duty_range": "1ms-2ms pulse (5-10% duty at 50Hz)",
    },
    "vl53l0x_lidar": {
        "pins": {"sda": "I2C_SDA", "scl": "I2C_SCL", "vcc": "3.3V", "gnd": "GND",
                 "xshut": "GPIO (optional)", "gpio1": "GPIO (optional interrupt)"},
        "protocol": "I2C",
        "i2c_address": "0x29 (default)",
        "notes": "Use XSHUT to power-cycle for address reassignment if using multiple.",
    },
    "bno055_imu": {
        "pins": {"sda": "I2C_SDA", "scl": "I2C_SCL", "vcc": "3.3V", "gnd": "GND",
                 "rst": "GPIO (optional reset)", "int": "GPIO (optional interrupt)"},
        "protocol": "I2C",
        "i2c_address": "0x28 (default) or 0x29 (ADR pin high)",
        "notes": "Power-on self-calibration takes ~20 seconds. Save calibration data to flash.",
    },
    "nrf24l01_rf": {
        "pins": {"mosi": "SPI_MOSI", "miso": "SPI_MISO", "sck": "SPI_SCK",
                 "csn": "SPI_CS", "ce": "GPIO", "vcc": "3.3V", "gnd": "GND",
                 "irq": "GPIO (optional)"},
        "protocol": "SPI",
        "notes": "MUST be powered from 3.3V (NOT 5V!). Add 10uF capacitor across VCC-GND.",
    },
    "sx1276_lora": {
        "pins": {"mosi": "SPI_MOSI", "miso": "SPI_MISO", "sck": "SPI_SCK",
                 "nss": "SPI_CS", "reset": "GPIO", "dio0": "GPIO (interrupt)",
                 "vcc": "3.3V", "gnd": "GND"},
        "protocol": "SPI",
        "notes": "Requires antenna! Do NOT transmit without antenna connected -- damages the module.",
    },
    "as7341_spectral": {
        "pins": {"sda": "I2C_SDA", "scl": "I2C_SCL", "vcc": "3.3V", "gnd": "GND",
                 "int": "GPIO (optional)", "led": "GPIO (optional LED drive)"},
        "protocol": "I2C",
        "i2c_address": "0x39",
        "notes": "Built-in LED driver for active illumination. Good for dark tunnel environments.",
    },
    "ds18b20_temp": {
        "pins": {"data": "GPIO", "vcc": "3.3V", "gnd": "GND"},
        "protocol": "OneWire",
        "notes": "Needs 4.7K pullup resistor between data and VCC. "
                 "Multiple sensors can share one data pin (each has unique address).",
    },
    "ov7670_camera": {
        "pins": {"sda": "I2C_SDA (SCCB)", "scl": "I2C_SCL (SIOC)",
                 "vsync": "GPIO", "href": "GPIO", "pclk": "GPIO",
                 "d0-d7": "8x GPIO (parallel data)", "xclk": "PWM (clock out)",
                 "vcc": "3.3V", "gnd": "GND"},
        "protocol": "SCCB (I2C-like) + parallel data",
        "notes": "Requires 8 GPIO pins for parallel data + clock. Very GPIO-hungry. "
                 "Consider ESP32-S3 camera interface instead of bit-banging on RP2040.",
    },
    "n20_dc_motor": {
        "pins": {"motor_a": "H-bridge OUT_A", "motor_b": "H-bridge OUT_B"},
        "driver_required": "DRV8833 or L298N H-bridge motor driver",
        "driver_pins": {"in1": "GPIO (PWM)", "in2": "GPIO (PWM)",
                        "vcc": "Battery voltage", "gnd": "GND"},
        "notes": "Do NOT connect directly to MCU GPIO -- needs a motor driver. "
                 "DRV8833 is recommended (small, cheap, handles 1.5A).",
    },
}


def generate_wiring_diagram(caste: str, track: str = "a") -> str:
    """Generate a complete wiring diagram for an ant caste."""
    configs = load_all_ant_configs()
    if caste not in configs:
        return f"Unknown caste '{caste}'. Available: {', '.join(configs.keys())}"

    cfg = configs[caste]
    mcu_id = cfg.get("compute", {}).get("part_id", "rp2040")
    mcu = MCU_PINS.get(mcu_id, MCU_PINS["rp2040"])

    lines = []
    lines.append(f"{'=' * 70}")
    lines.append(f"WIRING DIAGRAM -- {caste.upper()} ANT (Track {track.upper()})")
    lines.append(f"MCU: {mcu['name']}")
    lines.append(f"Logic: {mcu['voltage']}")
    lines.append(f"{'=' * 70}")

    # Track pin assignments
    pwm_idx = 0
    i2c_bus = 0
    gpio_idx = 20  # Start generic GPIO assignments from GP20

    connections = []

    # --- Locomotion (6 leg servos) ---
    loco = cfg.get("locomotion", {})
    n_legs = loco.get("legs", loco.get("actuators", 6))
    servo_id = loco.get("part_id", "sg90_servo")
    servo_info = COMPONENT_WIRING.get(servo_id, {})

    lines.append(f"\n--- LOCOMOTION ({n_legs}x Leg Servos) ---")
    leg_names = ["Front-Left", "Front-Right", "Mid-Left",
                 "Mid-Right", "Rear-Left", "Rear-Right"]
    for i in range(n_legs):
        leg_name = leg_names[i] if i < len(leg_names) else f"Leg-{i+1}"
        pwm_pin = mcu["pwm"][pwm_idx] if pwm_idx < len(mcu["pwm"]) else f"GP{gpio_idx}"
        lines.append(f"  Leg {i+1} ({leg_name}):")
        lines.append(f"    Signal (orange) -> {pwm_pin}")
        lines.append(f"    VCC (red)       -> 5V power rail")
        lines.append(f"    GND (brown)     -> Common GND")
        pwm_idx += 1

    if servo_info.get("notes"):
        lines.append(f"  Note: {servo_info['notes']}")

    # --- Mandible Arms (2 servos) ---
    mandibles = cfg.get("mandibles", {})
    n_mandibles = mandibles.get("count", 0)
    if n_mandibles > 0:
        mandible_part = mandibles.get("part_id", "sg51r_micro_servo")
        lines.append(f"\n--- MANDIBLE ARMS ({n_mandibles}x Micro Servos) ---")
        for i in range(n_mandibles):
            side = "Left" if i == 0 else "Right"
            pwm_pin = mcu["pwm"][pwm_idx] if pwm_idx < len(mcu["pwm"]) else f"GP{gpio_idx}"
            lines.append(f"  Mandible {side} ({mandible_part}):")
            lines.append(f"    Signal -> {pwm_pin}")
            lines.append(f"    VCC    -> 5V power rail")
            lines.append(f"    GND    -> Common GND")
            pwm_idx += 1
        grip = mandibles.get("grip_force_n", "?")
        lines.append(f"  Grip force: {grip}N  |  Tool mount: magnetic clip")

    if servo_info.get("notes"):
        lines.append(f"  Note: {servo_info['notes']}")

    # --- Communication ---
    lines.append(f"\n--- COMMUNICATION ---")
    comms = cfg.get("communication", {})
    if isinstance(comms, list):
        comm_list = comms
    elif isinstance(comms, dict):
        comm_list = [comms]
    else:
        comm_list = []

    for comm in comm_list:
        comm_id = comm.get("part_id", comm.get("type", "?"))
        comm_info = COMPONENT_WIRING.get(comm_id, {})
        protocol = comm_info.get("protocol", "?")

        lines.append(f"  {comm_id} ({comm.get('purpose', protocol)}):")
        if protocol == "SPI":
            spi = mcu["spi"][0]
            lines.append(f"    MOSI   -> {spi['mosi']}")
            lines.append(f"    MISO   -> {spi['miso']}")
            lines.append(f"    SCK    -> {spi['sck']}")
            lines.append(f"    CS/NSS -> {spi['cs']}")
            if "ce" in comm_info.get("pins", {}):
                lines.append(f"    CE     -> GP{gpio_idx}")
                gpio_idx += 1
            lines.append(f"    VCC    -> 3.3V")
            lines.append(f"    GND    -> Common GND")
        elif protocol == "I2C":
            i2c = mcu["i2c"][i2c_bus % len(mcu["i2c"])]
            lines.append(f"    SDA    -> {i2c['sda']}")
            lines.append(f"    SCL    -> {i2c['scl']}")
            lines.append(f"    VCC    -> 3.3V")
            lines.append(f"    GND    -> Common GND")
        elif "wired_can_bus" in comm_id:
            lines.append(f"    CAN_H  -> CAN bus backbone (twisted pair)")
            lines.append(f"    CAN_L  -> CAN bus backbone (twisted pair)")
            lines.append(f"    VCC    -> 5V")
            lines.append(f"    GND    -> Common GND")
            lines.append(f"    TX     -> {mcu['uart'][0]['tx']} (via CAN transceiver)")
            lines.append(f"    RX     -> {mcu['uart'][0]['rx']} (via CAN transceiver)")

        if comm_info.get("notes"):
            lines.append(f"    Note: {comm_info['notes']}")

    # --- Sensors ---
    lines.append(f"\n--- SENSORS ---")
    for sensor in cfg.get("sensors", []):
        sensor_id = sensor.get("part_id", sensor.get("type", "?"))
        sensor_info = COMPONENT_WIRING.get(sensor_id, {})
        protocol = sensor_info.get("protocol", "?")

        lines.append(f"  {sensor_id} ({sensor.get('purpose', '')[:40]}):")
        if "I2C" in protocol or "SCCB" in protocol:
            i2c = mcu["i2c"][i2c_bus % len(mcu["i2c"])]
            lines.append(f"    SDA    -> {i2c['sda']} (shared I2C bus)")
            lines.append(f"    SCL    -> {i2c['scl']} (shared I2C bus)")
            addr = sensor_info.get("i2c_address", "see datasheet")
            lines.append(f"    I2C addr: {addr}")
        elif protocol == "OneWire":
            lines.append(f"    DATA   -> GP{gpio_idx} (with 4.7K pullup to 3.3V)")
            gpio_idx += 1
        elif protocol == "SPI":
            lines.append(f"    (uses SPI bus -- see communication section)")

        lines.append(f"    VCC    -> 3.3V")
        lines.append(f"    GND    -> Common GND")

        if sensor_info.get("notes"):
            lines.append(f"    Note: {sensor_info['notes']}")

    # --- Tool ---
    lines.append(f"\n--- TOOL ---")
    tool = cfg.get("tool", {})
    if isinstance(tool, dict):
        # Track-specific tool
        track_tool = tool.get(f"track_{track}", tool)
        if track_tool and track_tool.get("type") not in (None, "none"):
            tool_id = track_tool.get("part_id", "?")
            tool_info = COMPONENT_WIRING.get(tool_id, {})

            lines.append(f"  {track_tool.get('type', '?')} ({tool_id}):")
            if "motor" in tool_id.lower() or "n20" in tool_id.lower():
                lines.append(f"    ** Needs motor driver (DRV8833 recommended) **")
                lines.append(f"    DRV8833 IN1  -> GP{gpio_idx} (PWM for speed)")
                gpio_idx += 1
                lines.append(f"    DRV8833 IN2  -> GP{gpio_idx} (direction)")
                gpio_idx += 1
                lines.append(f"    DRV8833 OUT1 -> Motor wire A")
                lines.append(f"    DRV8833 OUT2 -> Motor wire B")
                lines.append(f"    DRV8833 VCC  -> Battery voltage")
                lines.append(f"    DRV8833 GND  -> Common GND")
            elif "servo" in tool_id.lower() or "sg90" in tool_id.lower():
                pwm_pin = mcu["pwm"][pwm_idx] if pwm_idx < len(mcu["pwm"]) else f"GP{gpio_idx}"
                lines.append(f"    Signal -> {pwm_pin}")
                lines.append(f"    VCC    -> 5V rail")
                lines.append(f"    GND    -> Common GND")
                pwm_idx += 1
            if tool_info.get("notes"):
                lines.append(f"    Note: {tool_info['notes']}")
        else:
            lines.append(f"  No tool (this caste doesn't mine)")

    # --- Power ---
    lines.append(f"\n--- POWER ---")
    power = cfg.get("power", {})
    source = power.get("source", "?")
    lines.append(f"  Source: {source}")
    if source == "tunnel_power_rail":
        lines.append(f"  Power rail contact -> 12V rail (+ and - strips on tunnel wall)")
        lines.append(f"  Spring-loaded copper brush maintains contact while moving")
        lines.append(f"  12V rail -> buck converter -> 5V servo rail + 3.3V logic rail")
        lines.append(f"  Supercapacitor charges continuously while on rail")
        lines.append(f"  Off-rail: supercap provides ~2 min of full-power operation")
    elif source == "tethered":
        lines.append(f"  Tether -> 48V bus (via DC-DC buck converter to 5V)")
        lines.append(f"  Buck converter 5V out -> MCU VIN / servo rail")
        lines.append(f"  Buck converter 3.3V out -> sensor/radio rail")
    elif source == "solar":
        lines.append(f"  Solar panel -> charge controller -> battery")
        lines.append(f"  Battery -> 5V boost converter -> MCU/servo rail")

    backup = power.get("backup_power", power.get("backup_battery", cfg.get("battery", {})))
    if backup:
        btype = backup.get("type", "battery")
        if btype == "supercapacitor":
            energy = backup.get("energy_wh", 0)
            lines.append(f"  Backup: {backup.get('capacitance_f', '?')}F supercapacitor ({energy} Wh)")
            lines.append(f"  Charge time: {backup.get('charge_time_seconds', '?')}s from rail")
            lines.append(f"  Covers: rail junctions, work face ops, tool dock visits")
        else:
            lines.append(f"  Backup: {backup.get('capacity_mah', '?')} mAh battery")
            lines.append(f"  Battery -> charger module -> system power")

    # --- Summary ---
    lines.append(f"\n--- PIN USAGE SUMMARY ---")
    lines.append(f"  PWM pins used:    {pwm_idx}")
    lines.append(f"  I2C buses used:   {min(i2c_bus + 1, len(mcu['i2c']))}")
    lines.append(f"  SPI buses used:   {'1' if any('SPI' in COMPONENT_WIRING.get(c.get('part_id', ''), {}).get('protocol', '') for c in comm_list) else '0'}")
    lines.append(f"  GPIO pins used:   {gpio_idx - 20} (starting from GP20)")
    lines.append(f"  Total pins:       {pwm_idx + 2 + (gpio_idx - 20)}")  # +2 for I2C
    remaining = mcu["gpio_count"] - (pwm_idx + 2 + (gpio_idx - 20))
    lines.append(f"  Remaining GPIO:   {remaining}")

    lines.append(f"\n--- ADDITIONAL COMPONENTS NEEDED ---")
    lines.append(f"  1x DC-DC buck converter (48V->5V if tethered, or LiPo->5V)")
    lines.append(f"  1x 3.3V voltage regulator (if MCU board doesn't include one)")
    lines.append(f"  6x servo extension cables (if needed for leg routing)")
    if any("n20" in str(cfg.get("tool", {})).lower() for _ in [1]):
        lines.append(f"  1x DRV8833 motor driver module")
    lines.append(f"  1x 10uF capacitor across radio module VCC-GND")
    lines.append(f"  1x 4.7K resistor (if using DS18B20 temperature sensor)")
    lines.append(f"  Hookup wire, headers, proto board or custom PCB")

    lines.append(f"\n{'=' * 70}")
    return "\n".join(lines)
