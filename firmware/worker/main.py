"""AstraAnt Worker Ant Firmware -- MicroPython for RP2040 Pico

Real control code using CommandHandler + real drivers.
Receives commands from taskmaster via nRF24L01, executes them,
reports status. The SAME CommandHandler logic runs in the sim.

Pin assignments match: astraant build wiring worker --track a

To flash:
  1. Hold BOOTSEL on the Pico, connect USB
  2. Copy uf2 firmware (MicroPython) to the drive
  3. Copy this entire firmware/worker/ directory to the Pico
  4. Reset -- ant boots and enters IDLE state
"""

import machine
import time
from micropython import const

# Import our modules
from gait import GaitController
from command_handler import CommandHandler
from radio_protocol import pack_heartbeat

# Conditional imports (these may not be available on desktop Python)
try:
    from drivers.vl53l0x import VL53L0X
    from drivers.nrf24l01 import NRF24L01
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

# -- Pin Definitions (from wiring diagram) --
LEG_PINS = [2, 3, 8, 9, 10, 11]      # GP2-GP11 PWM for leg servos
MANDIBLE_PINS = [12, 13]              # GP12-GP13 PWM for mandible servos
NRF_MOSI, NRF_MISO, NRF_SCK = 19, 16, 18  # SPI0
NRF_CSN, NRF_CE = 17, 20             # SPI chip select + chip enable
I2C_SDA, I2C_SCL = 4, 5              # I2C0 for VL53L0x
MOTOR_IN1, MOTOR_IN2 = 21, 22        # DRV8833 motor driver for drill
RAIL_CONTACT_ADC = 26                 # ADC for supercapacitor voltage
HOPPER_STRAIN_ADC = 27               # ADC for hopper weight

# -- Configuration --
WORKER_ID = const(0)                  # Set uniquely per ant (0-255)
RADIO_CHANNEL = const(76)
TICK_MS = const(20)                   # 50 Hz control loop
HEARTBEAT_INTERVAL_MS = const(5000)


def init_hardware():
    """Initialize all hardware peripherals. Returns dict of hardware objects."""
    hw = {}

    # Leg servos (PWM at 50 Hz)
    hw["leg_servos"] = []
    for pin_num in LEG_PINS:
        pwm = machine.PWM(machine.Pin(pin_num))
        pwm.freq(50)
        hw["leg_servos"].append(pwm)

    # Mandible servos
    hw["mandible_servos"] = []
    for pin_num in MANDIBLE_PINS:
        pwm = machine.PWM(machine.Pin(pin_num))
        pwm.freq(50)
        hw["mandible_servos"].append(pwm)

    # All servos combined (for gait controller)
    hw["all_servos"] = hw["leg_servos"] + hw["mandible_servos"]

    # I2C bus (VL53L0x sensor)
    hw["i2c"] = machine.I2C(0, sda=machine.Pin(I2C_SDA),
                             scl=machine.Pin(I2C_SCL), freq=400000)

    # VL53L0x distance sensor
    if HAS_HARDWARE:
        hw["lidar"] = VL53L0X(hw["i2c"])
    else:
        hw["lidar"] = None

    # SPI bus (nRF24L01 radio)
    hw["spi"] = machine.SPI(0, mosi=machine.Pin(NRF_MOSI),
                            miso=machine.Pin(NRF_MISO),
                            sck=machine.Pin(NRF_SCK))
    hw["nrf_csn"] = machine.Pin(NRF_CSN, machine.Pin.OUT, value=1)
    hw["nrf_ce"] = machine.Pin(NRF_CE, machine.Pin.OUT, value=0)

    if HAS_HARDWARE:
        hw["radio"] = NRF24L01(hw["spi"], hw["nrf_csn"], hw["nrf_ce"],
                               channel=RADIO_CHANNEL)
        # Set addresses (taskmaster = TX target, our address = RX)
        hw["radio"].set_address(
            tx_addr=b"\xe1\xf0\xf0\xf0\xf0",   # Taskmaster address
            rx_addr=bytes([0xe1, 0xf0, 0xf0, 0xf0, WORKER_ID]),
        )
    else:
        hw["radio"] = None

    # Motor driver (DRV8833 for drill tool)
    hw["motor_in1"] = machine.PWM(machine.Pin(MOTOR_IN1))
    hw["motor_in1"].freq(1000)
    hw["motor_in2"] = machine.PWM(machine.Pin(MOTOR_IN2))
    hw["motor_in2"].freq(1000)

    # ADC for supercapacitor voltage and hopper weight
    hw["supercap_adc"] = machine.ADC(machine.Pin(RAIL_CONTACT_ADC))
    hw["hopper_adc"] = machine.ADC(machine.Pin(HOPPER_STRAIN_ADC))

    return hw


def make_callbacks(hw):
    """Create hardware callback functions for the CommandHandler."""

    def set_servo(idx, angle_deg):
        angle_deg = max(0, min(180, angle_deg))
        pulse_us = 500 + (angle_deg / 180) * 2000
        hw["all_servos"][idx].duty_ns(int(pulse_us * 1000))

    def read_supercap():
        raw = hw["supercap_adc"].read_u16()
        # Supercap voltage: 0-5.5V through voltage divider (halved)
        voltage = (raw / 65535) * 3.3 * 2
        max_voltage = 5.5
        return int(min(100, voltage / max_voltage * 100))

    def read_hopper():
        raw = hw["hopper_adc"].read_u16()
        # Strain gauge: 0 = empty, ~40000 = 200g full
        return int(min(100, raw / 40000 * 100))

    def read_proximity():
        if hw["lidar"]:
            return hw["lidar"].read_range_mm()
        return -1

    def send_radio(packet):
        if hw["radio"]:
            hw["radio"].send(packet)

    def drill_motor(speed_pct):
        duty = int(abs(speed_pct) / 100 * 65535)
        if speed_pct > 0:
            hw["motor_in1"].duty_u16(duty)
            hw["motor_in2"].duty_u16(0)
        elif speed_pct < 0:
            hw["motor_in1"].duty_u16(0)
            hw["motor_in2"].duty_u16(duty)
        else:
            hw["motor_in1"].duty_u16(0)
            hw["motor_in2"].duty_u16(0)

    # Gait controller
    gait = GaitController(hw["leg_servos"])

    def gait_step(dt_ms):
        gait.step(dt_ms)

    return {
        "set_servo": set_servo,
        "read_supercap": read_supercap,
        "read_hopper": read_hopper,
        "read_proximity": read_proximity,
        "send_radio": send_radio,
        "drill_motor": drill_motor,
        "gait_step": gait_step,
        "gait": gait,
    }


def main():
    """Main entry point."""
    print(f"AstraAnt Worker v0.2.0 -- RP2040 (ID: {WORKER_ID})")

    # Initialize hardware
    hw = init_hardware()
    callbacks = make_callbacks(hw)

    print(f"I2C devices: {hw['i2c'].scan()}")
    print(f"Supercap: {callbacks['read_supercap']()}%")
    print(f"Hopper: {callbacks['read_hopper']()}%")

    # Create command handler (the shared firmware/sim state machine)
    handler = CommandHandler(
        worker_id=WORKER_ID,
        set_servo_fn=callbacks["set_servo"],
        read_supercap_fn=callbacks["read_supercap"],
        read_hopper_fn=callbacks["read_hopper"],
        read_proximity_fn=callbacks["read_proximity"],
        send_radio_fn=callbacks["send_radio"],
        drill_motor_fn=callbacks["drill_motor"],
        gait_step_fn=callbacks["gait_step"],
    )

    # Center all servos
    callbacks["gait"].all_neutral()
    print("Servos centered. Entering main loop...")

    # Start listening for radio commands
    if hw["radio"]:
        hw["radio"].start_listening()

    # Main control loop
    last_heartbeat = time.ticks_ms()

    while True:
        try:
            loop_start = time.ticks_ms()

            # Check for radio commands from taskmaster
            if hw["radio"] and hw["radio"].available():
                packet = hw["radio"].receive()
                if packet:
                    hw["radio"].stop_listening()
                    handler.handle_command(packet)
                    hw["radio"].start_listening()

            # Tick the command handler state machine
            handler.tick(TICK_MS)

            # Send heartbeat every 5 seconds
            if time.ticks_diff(time.ticks_ms(), last_heartbeat) > HEARTBEAT_INTERVAL_MS:
                hw["radio"].stop_listening() if hw["radio"] else None
                pkt = pack_heartbeat(
                    WORKER_ID, handler.rail_position,
                    handler.supercap_pct, handler.hopper_pct,
                    handler.state, handler.servo_ok_mask,
                )
                callbacks["send_radio"](pkt)
                hw["radio"].start_listening() if hw["radio"] else None
                last_heartbeat = time.ticks_ms()

            # Sleep to maintain tick rate
            elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
            if elapsed < TICK_MS:
                time.sleep_ms(TICK_MS - elapsed)

        except KeyboardInterrupt:
            callbacks["drill_motor"](0)
            callbacks["gait"].all_neutral()
            print("Stopped.")
            break
        except Exception as e:
            callbacks["drill_motor"](0)
            print(f"ERROR: {e}")
            time.sleep_ms(1000)


if __name__ == "__main__":
    main()
