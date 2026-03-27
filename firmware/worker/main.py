"""AstraAnt Worker Ant Firmware -- MicroPython for RP2040 Pico

This is the real control code that runs on the physical ant.
State machine: IDLE -> MOVE -> DIG/SCOOP/SORT/PLASTER/TEND -> HAUL -> DUMP -> RETURN

The worker's current role is set by the taskmaster over nRF24L01 radio.
Tool head determines which actions are available.

Pin assignments match the wiring diagram output from:
  astraant build wiring worker --track a
"""

import machine
import time
from micropython import const

# -- Pin Definitions (from wiring diagram) --
# Legs (PWM)
LEG_PINS = [2, 3, 8, 9, 10, 11]  # GP2-GP11
# Mandibles (PWM)
MANDIBLE_LEFT_PIN = 12
MANDIBLE_RIGHT_PIN = 13
# nRF24L01 (SPI0)
NRF_MOSI = 19
NRF_MISO = 16
NRF_SCK = 18
NRF_CSN = 17
NRF_CE = 20
# VL53L0x (I2C0)
I2C_SDA = 4
I2C_SCL = 5
# Tool motor driver (DRV8833)
MOTOR_IN1 = 21
MOTOR_IN2 = 22
# Battery voltage monitor
VBAT_ADC = 26

# -- Constants --
SERVO_FREQ = const(50)
SERVO_MIN_US = const(500)
SERVO_MAX_US = const(2500)
HEARTBEAT_MS = const(5000)

# -- State Machine --
STATE_IDLE = const(0)
STATE_MOVING = const(1)
STATE_WORKING = const(2)  # Dig/scoop/sort/plaster/tend depending on tool
STATE_HAULING = const(3)
STATE_DUMPING = const(4)
STATE_RETURNING = const(5)
STATE_TOOL_SWAP = const(6)
STATE_ERROR = const(7)


class WorkerAnt:
    """Main worker ant controller."""

    def __init__(self):
        self.state = STATE_IDLE
        self.role = "miner"  # Set by taskmaster: miner, sorter, plasterer, tender
        self.tool = "drill_head"  # Current tool attached
        self.cargo_g = 0
        self.max_cargo_g = 200
        self.cycle_count = 0

        # Initialize hardware
        self._init_servos()
        self._init_sensors()
        self._init_radio()
        self._init_motor()

        self.last_heartbeat = time.ticks_ms()

    def _init_servos(self):
        """Initialize leg and mandible servos."""
        self.leg_servos = []
        for pin_num in LEG_PINS:
            pwm = machine.PWM(machine.Pin(pin_num))
            pwm.freq(SERVO_FREQ)
            self.leg_servos.append(pwm)

        self.mandible_l = machine.PWM(machine.Pin(MANDIBLE_LEFT_PIN))
        self.mandible_l.freq(SERVO_FREQ)
        self.mandible_r = machine.PWM(machine.Pin(MANDIBLE_RIGHT_PIN))
        self.mandible_r.freq(SERVO_FREQ)

    def _init_sensors(self):
        """Initialize I2C sensors."""
        self.i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA),
                               scl=machine.Pin(I2C_SCL), freq=400000)
        # VL53L0x will be at address 0x29
        self.proximity_addr = 0x29
        # ADC for battery voltage
        self.vbat_adc = machine.ADC(machine.Pin(VBAT_ADC))

    def _init_radio(self):
        """Initialize nRF24L01 radio."""
        self.spi = machine.SPI(0,
                               mosi=machine.Pin(NRF_MOSI),
                               miso=machine.Pin(NRF_MISO),
                               sck=machine.Pin(NRF_SCK))
        self.nrf_csn = machine.Pin(NRF_CSN, machine.Pin.OUT, value=1)
        self.nrf_ce = machine.Pin(NRF_CE, machine.Pin.OUT, value=0)
        # Full nRF24L01 driver would be imported here
        # from nrf24l01 import NRF24L01

    def _init_motor(self):
        """Initialize tool motor driver (DRV8833)."""
        self.motor_in1 = machine.PWM(machine.Pin(MOTOR_IN1))
        self.motor_in1.freq(1000)
        self.motor_in2 = machine.PWM(machine.Pin(MOTOR_IN2))
        self.motor_in2.freq(1000)
        self.motor_stop()

    # -- Servo Control --
    def set_servo_angle(self, servo, angle_deg):
        """Set a servo to a specific angle (0-180)."""
        angle_deg = max(0, min(180, angle_deg))
        pulse_us = SERVO_MIN_US + (angle_deg / 180) * (SERVO_MAX_US - SERVO_MIN_US)
        servo.duty_ns(int(pulse_us * 1000))

    def mandible_open(self):
        self.set_servo_angle(self.mandible_l, 30)
        self.set_servo_angle(self.mandible_r, 150)

    def mandible_close(self):
        self.set_servo_angle(self.mandible_l, 90)
        self.set_servo_angle(self.mandible_r, 90)

    def mandible_grip(self):
        """Full grip for tool holding."""
        self.set_servo_angle(self.mandible_l, 110)
        self.set_servo_angle(self.mandible_r, 70)

    # -- Motor Control --
    def motor_forward(self, speed_pct=100):
        duty = int(speed_pct / 100 * 65535)
        self.motor_in1.duty_u16(duty)
        self.motor_in2.duty_u16(0)

    def motor_stop(self):
        self.motor_in1.duty_u16(0)
        self.motor_in2.duty_u16(0)

    # -- Walking --
    def walk_forward(self, steps=1):
        """Execute tripod gait walking cycle."""
        for _ in range(steps):
            # Tripod gait: legs 0,2,4 move together, then 1,3,5
            for phase in range(2):
                for i, servo in enumerate(self.leg_servos):
                    if (i % 2) == phase:
                        self.set_servo_angle(servo, 120)  # Swing forward
                    else:
                        self.set_servo_angle(servo, 60)   # Push back
                time.sleep_ms(200)

    # -- Proximity --
    def read_proximity_mm(self):
        """Read VL53L0x distance in mm. Returns -1 if sensor not found."""
        try:
            # Simplified — full driver would use VL53L0x library
            if self.proximity_addr in self.i2c.scan():
                return 100  # Placeholder — real driver reads actual distance
            return -1
        except Exception:
            return -1

    # -- Battery --
    def read_battery_voltage(self):
        """Read battery voltage via ADC. Returns volts."""
        raw = self.vbat_adc.read_u16()
        # Assuming voltage divider: Vbat -> 100K -> ADC -> 100K -> GND
        # ADC reads half of Vbat, 3.3V reference, 16-bit
        voltage = (raw / 65535) * 3.3 * 2
        return voltage

    # -- State Machine --
    def tick(self):
        """Main control loop tick. Called repeatedly."""
        # Check for radio commands from taskmaster
        self._check_radio()

        # Send heartbeat
        if time.ticks_diff(time.ticks_ms(), self.last_heartbeat) > HEARTBEAT_MS:
            self._send_heartbeat()
            self.last_heartbeat = time.ticks_ms()

        # State machine dispatch
        if self.state == STATE_IDLE:
            pass  # Wait for taskmaster command

        elif self.state == STATE_MOVING:
            # Walk toward target (simplified — real nav uses proximity + dead reckoning)
            self.walk_forward(steps=3)
            proximity = self.read_proximity_mm()
            if proximity > 0 and proximity < 50:
                # Reached something — transition to working
                self.state = STATE_WORKING

        elif self.state == STATE_WORKING:
            if self.role == "miner":
                self._do_mining()
            elif self.role == "sorter":
                self._do_sorting()
            elif self.role == "plasterer":
                self._do_plastering()
            elif self.role == "tender":
                self._do_tending()

        elif self.state == STATE_HAULING:
            self.walk_forward(steps=3)
            # Walk toward dump point (simplified)
            self.state = STATE_DUMPING  # Placeholder transition

        elif self.state == STATE_DUMPING:
            self.mandible_open()
            time.sleep_ms(500)
            self.cargo_g = 0
            self.cycle_count += 1
            self.state = STATE_RETURNING

        elif self.state == STATE_RETURNING:
            self.walk_forward(steps=3)
            self.state = STATE_MOVING  # Back to work face

        elif self.state == STATE_TOOL_SWAP:
            # Release current tool, pick up new one
            self.mandible_open()
            time.sleep_ms(300)
            # Walk to dock position (simplified)
            self.walk_forward(steps=2)
            self.mandible_grip()
            time.sleep_ms(300)
            self.state = STATE_IDLE

        elif self.state == STATE_ERROR:
            self.motor_stop()
            # Flash LED or signal error state

    def _do_mining(self):
        """Mine with drill head — spin motor, advance into rock face."""
        self.mandible_grip()  # Hold tool firmly
        self.motor_forward(speed_pct=80)
        time.sleep_ms(2000)  # Drill for 2 seconds
        self.motor_stop()
        self.cargo_g += 20  # Collected ~20g
        if self.cargo_g >= self.max_cargo_g:
            self.state = STATE_HAULING

    def _do_sorting(self):
        """Sort with thermal rake — rake material from drum."""
        self.mandible_grip()
        # Rake motion (simplified — real version uses leg coordination)
        for servo in self.leg_servos[:2]:
            self.set_servo_angle(servo, 150)
        time.sleep_ms(500)
        for servo in self.leg_servos[:2]:
            self.set_servo_angle(servo, 30)
        time.sleep_ms(500)
        self.state = STATE_IDLE  # Wait for next drum load

    def _do_plastering(self):
        """Plaster with paste nozzle — squeeze mandibles to extrude."""
        # Mandible squeeze pushes paste through nozzle
        self.mandible_grip()  # Squeeze!
        self.walk_forward(steps=1)  # Move along wall while extruding
        time.sleep_ms(1000)
        self.mandible_close()  # Release squeeze

    def _do_tending(self):
        """Tend bioreactor with sampling probe — dip and read."""
        self.mandible_close()  # Hold probe at reading position
        time.sleep_ms(2000)  # Wait for sensor stabilization
        # Read pH and turbidity from probe (via ADC/I2C)
        # Real version reads actual sensor values
        self.state = STATE_MOVING  # Move to next sampling point

    def _check_radio(self):
        """Check for commands from taskmaster."""
        # Placeholder — real version uses nRF24L01 driver
        pass

    def _send_heartbeat(self):
        """Send status to taskmaster."""
        # Payload: state, role, cargo, battery, cycle_count
        pass


# -- Main Entry Point --
def main():
    print("AstraAnt Worker v0.1.0 -- RP2040")
    ant = WorkerAnt()
    print(f"Initialized. Battery: {ant.read_battery_voltage():.2f}V")
    print(f"I2C devices: {ant.i2c.scan()}")
    print("Entering main loop...")

    while True:
        try:
            ant.tick()
            time.sleep_ms(50)  # 20 Hz control loop
        except KeyboardInterrupt:
            ant.motor_stop()
            print("Stopped.")
            break
        except Exception as e:
            ant.motor_stop()
            ant.state = STATE_ERROR
            print(f"ERROR: {e}")
            time.sleep_ms(1000)


if __name__ == "__main__":
    main()
