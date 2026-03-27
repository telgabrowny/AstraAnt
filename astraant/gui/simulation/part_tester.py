"""Part testing procedures for salvaged components.

When a dead ant is brought to the manufacturing bay, each component
is tested individually on the test jig. The same test station used
for newly built ants works for individual part testing.

The test jig is simple: a power supply, a few connectors, and the
taskmaster running the test firmware over radio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PartTestResult:
    """Result of testing one salvaged part."""
    part_type: str
    part_id: str
    test_name: str
    procedure: str
    result: str          # "PASS", "FAIL", "DEGRADED"
    value_if_pass_usd: float
    recycle_value_usd: float  # Value as raw material if it fails
    notes: str = ""


def test_salvaged_servo(servo_health: float, servo_index: int) -> PartTestResult:
    """Test a salvaged servo motor on the test jig.

    Physical procedure:
    1. Worker places servo in the test jig cradle (magnetic alignment pins)
    2. Pogo pin connector mates with servo's 3 wires (signal, VCC, GND)
    3. Test jig applies 5V power
    4. Taskmaster sends PWM sweep command: 0° -> 90° -> 180° -> 90° -> 0°
    5. Test jig's position sensor (separate VL53L0x on a lever arm)
       measures if the servo shaft actually moved to commanded positions
    6. If positions match within ±5°: PASS
    7. If shaft moves but is noisy/inconsistent: DEGRADED (usable for low-load)
    8. If shaft doesn't move or moves erratically: FAIL (gears stripped)
    """
    if servo_health > 0.5:
        result = "PASS"
        notes = f"Shaft tracks command within +/-3deg. Smooth movement."
    elif servo_health > 0.3:
        result = "DEGRADED"
        notes = f"Shaft tracks but with {(1-servo_health)*100:.0f}% position error. OK for low-load roles."
    else:
        result = "FAIL"
        notes = f"Shaft does not respond to command. Gears likely stripped."

    leg_names = ["front-left", "front-right", "mid-left",
                 "mid-right", "rear-left", "rear-right",
                 "mandible-left", "mandible-right"]
    name = leg_names[servo_index] if servo_index < len(leg_names) else f"servo-{servo_index}"

    return PartTestResult(
        part_type="servo",
        part_id=name,
        test_name="PWM sweep + position verify",
        procedure=(
            "1. Seat in test cradle (magnetic pins align connector)\n"
            "2. Apply 5V power via pogo pins\n"
            "3. Send PWM sweep: 0->90->180->90->0 degrees\n"
            "4. Measure shaft position via lever-arm sensor\n"
            "5. Compare commanded vs actual position"
        ),
        result=result,
        value_if_pass_usd=3.0 if servo_index < 6 else 2.0,
        recycle_value_usd=0.01,  # Metal content only
        notes=notes,
    )


def test_salvaged_mcu(mcu_health: float) -> PartTestResult:
    """Test a salvaged RP2040 MCU board.

    Physical procedure:
    1. Worker places board on test jig alignment posts
    2. Pogo pins contact the programming header and power pads
    3. Apply 3.3V power
    4. Wait 2 seconds for boot
    5. Check for serial heartbeat on UART0 (should print "AstraAnt Worker vX.X")
    6. If heartbeat received: PASS
    7. If boot but no heartbeat: attempt re-flash firmware, re-test
    8. If no boot (no current draw, or excess current draw): FAIL
    """
    if mcu_health > 0.5:
        return PartTestResult(
            part_type="mcu",
            part_id="RP2040",
            test_name="Power-on heartbeat check",
            procedure=(
                "1. Seat on alignment posts\n"
                "2. Pogo pins contact programming header\n"
                "3. Apply 3.3V\n"
                "4. Wait 2s for boot\n"
                "5. Check UART0 for heartbeat string"
            ),
            result="PASS",
            value_if_pass_usd=4.0,
            recycle_value_usd=0.005,
            notes="Heartbeat received. Firmware intact. Ready for reuse.",
        )
    else:
        return PartTestResult(
            part_type="mcu",
            part_id="RP2040",
            test_name="Power-on heartbeat check",
            procedure="(same as above)",
            result="FAIL",
            value_if_pass_usd=4.0,
            recycle_value_usd=0.005,
            notes="No heartbeat after power-on. Attempted re-flash: failed. "
                  "Chip likely damaged by power surge. To sintering furnace.",
        )


def test_salvaged_sensor(sensor_health: float) -> PartTestResult:
    """Test a salvaged VL53L0x distance sensor.

    Physical procedure:
    1. Mount sensor on test jig with fixed-distance target at 100mm
    2. Apply 3.3V power, initialize via I2C
    3. Read 10 distance measurements
    4. If average reading is 95-105mm (±5%): PASS
    5. If readings are noisy but average is close: DEGRADED
    6. If no I2C response or readings are wildly wrong: FAIL (laser diode dead)
    """
    if sensor_health > 0.5:
        result = "PASS"
        notes = "Reads 100mm target as 99.2mm (±0.8%). Laser output nominal."
    elif sensor_health > 0.2:
        result = "DEGRADED"
        notes = f"Reads 100mm target as {100 + (1-sensor_health)*20:.0f}mm. Laser degraded, reduced range."
    else:
        result = "FAIL"
        notes = "No I2C response. Laser diode likely dead."

    return PartTestResult(
        part_type="sensor",
        part_id="VL53L0x",
        test_name="Fixed-distance target reading",
        procedure=(
            "1. Mount on jig with 100mm target plate\n"
            "2. Power on, I2C init\n"
            "3. Read 10 measurements\n"
            "4. Compare average to known distance"
        ),
        result=result,
        value_if_pass_usd=4.0,
        recycle_value_usd=0.005,
        notes=notes,
    )


def test_salvaged_radio(radio_health: float) -> PartTestResult:
    """Test a salvaged nRF24L01 radio module.

    Physical procedure:
    1. Mount on test jig with SPI pogo pins
    2. Apply 3.3V power (with 10µF capacitor on VCC!)
    3. Taskmaster sends "PING" packet on test channel
    4. Test jig firmware (on the radio) should respond "PONG"
    5. Measure RSSI (signal strength) on the response
    6. If PONG received with RSSI > -70 dBm: PASS
    7. If PONG received but weak: DEGRADED
    8. If no PONG after 3 attempts: FAIL
    """
    if radio_health > 0.5:
        return PartTestResult(
            part_type="radio",
            part_id="nRF24L01",
            test_name="Ping-pong handshake",
            procedure=(
                "1. Mount with SPI pogo pins + 10uF cap\n"
                "2. Apply 3.3V\n"
                "3. Taskmaster sends PING\n"
                "4. Wait for PONG response\n"
                "5. Measure signal strength"
            ),
            result="PASS",
            value_if_pass_usd=2.0,
            recycle_value_usd=0.003,
            notes="PONG received in 2ms. RSSI: -45 dBm. Crystal and PA nominal.",
        )
    else:
        return PartTestResult(
            part_type="radio",
            part_id="nRF24L01",
            test_name="Ping-pong handshake",
            procedure="(same)",
            result="FAIL",
            value_if_pass_usd=2.0,
            recycle_value_usd=0.003,
            notes="No PONG after 3 attempts. RF section likely damaged.",
        )


def run_full_salvage_test(component_health) -> list[PartTestResult]:
    """Run the complete salvage test sequence on a dead ant's components.

    Returns ordered list of test results.
    """
    results = []

    # Test each leg servo
    for i in range(6):
        results.append(test_salvaged_servo(component_health.leg_servos[i], i))

    # Test mandible servos
    for i in range(2):
        results.append(test_salvaged_servo(component_health.mandible_servos[i], 6 + i))

    # Test MCU
    results.append(test_salvaged_mcu(component_health.mcu))

    # Test radio
    results.append(test_salvaged_radio(component_health.radio))

    # Test sensor
    results.append(test_salvaged_sensor(component_health.lidar_sensor))

    return results


def format_test_report(results: list[PartTestResult]) -> str:
    """Format salvage test results as readable report."""
    lines = []
    lines.append("SALVAGE TEST REPORT")
    lines.append("=" * 60)

    passed = sum(1 for r in results if r.result == "PASS")
    degraded = sum(1 for r in results if r.result == "DEGRADED")
    failed = sum(1 for r in results if r.result == "FAIL")
    total_value = sum(r.value_if_pass_usd for r in results if r.result in ("PASS", "DEGRADED"))

    lines.append(f"  PASS: {passed}  DEGRADED: {degraded}  FAIL: {failed}")
    lines.append(f"  Salvage value: ${total_value:.2f}")
    lines.append("")

    for r in results:
        status = {"PASS": "[OK]", "DEGRADED": "[~~]", "FAIL": "[XX]"}[r.result]
        lines.append(f"  {status} {r.part_type:8s} {r.part_id:16s} {r.notes[:50]}")

    lines.append("=" * 60)
    return "\n".join(lines)
