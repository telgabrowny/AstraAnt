"""AstraAnt Taskmaster Firmware -- MicroPython for ESP32-S3

Commands a squad of ~20 worker ants via nRF24L01 radio.
Navigates tunnels using IMU + visual odometry + lidar.
Classifies regolith with spectral sensor.
Connects to mothership via CAN bus backbone.

Pin assignments match: astraant build wiring taskmaster
"""

import machine
import time
from micropython import const

# -- Pin Definitions --
# Legs (PWM)
LEG_PINS = [1, 2, 3, 4, 5, 6]
# Mandibles (PWM)
MANDIBLE_LEFT_PIN = 7
MANDIBLE_RIGHT_PIN = 14
# nRF24L01 (SPI2) -- to workers
NRF_MOSI = 11
NRF_MISO = 13
NRF_SCK = 12
NRF_CSN = 10
NRF_CE = 15
# BNO055 IMU + VL53L0x + AS7341 (I2C0) -- shared bus
I2C_SDA = 8
I2C_SCL = 9
# CAN bus transceiver (UART0) -- to mothership backbone
CAN_TX = 43
CAN_RX = 44

# -- Known I2C Addresses --
BNO055_ADDR = const(0x28)
VL53L0X_ADDR = const(0x29)
AS7341_ADDR = const(0x39)

SQUAD_SIZE = const(20)
HEARTBEAT_MS = const(10000)


class Taskmaster:
    """Taskmaster ant controller — squad leader."""

    def __init__(self):
        self.squad_status = {}  # worker_id -> {state, role, cargo, battery}
        self.tunnel_map = []    # Simplified tunnel segment list
        self.current_position = (0, 0, 0)
        self.heading_deg = 0

        self._init_hardware()

    def _init_hardware(self):
        # Servos (same as worker)
        self.leg_servos = []
        for pin_num in LEG_PINS:
            pwm = machine.PWM(machine.Pin(pin_num))
            pwm.freq(50)
            self.leg_servos.append(pwm)

        # I2C bus (IMU + lidar + spectral all share)
        self.i2c = machine.I2C(0, sda=machine.Pin(I2C_SDA),
                               scl=machine.Pin(I2C_SCL), freq=400000)

        # UART for CAN bus backbone
        self.uart = machine.UART(0, baudrate=115200,
                                 tx=machine.Pin(CAN_TX),
                                 rx=machine.Pin(CAN_RX))

        # SPI for nRF24L01
        self.spi = machine.SPI(1,
                               mosi=machine.Pin(NRF_MOSI),
                               miso=machine.Pin(NRF_MISO),
                               sck=machine.Pin(NRF_SCK))

    def scan_sensors(self):
        """Report which sensors are detected on I2C."""
        devices = self.i2c.scan()
        found = {}
        if BNO055_ADDR in devices:
            found["imu"] = "BNO055"
        if VL53L0X_ADDR in devices:
            found["lidar"] = "VL53L0X"
        if AS7341_ADDR in devices:
            found["spectral"] = "AS7341"
        return found

    def read_spectral(self):
        """Read AS7341 spectral data for mineral classification."""
        # Placeholder — real version reads 11 spectral channels
        # and classifies: sulfide, silicate, REE-bearing, PGM-bearing
        return {"classification": "unknown", "confidence": 0.0}

    def assign_role(self, worker_id, role, tool):
        """Send role assignment to a worker ant."""
        msg = f"ASSIGN:{worker_id}:{role}:{tool}"
        # Send via nRF24L01 radio
        # self.nrf.send(msg.encode())
        self.squad_status[worker_id] = {"role": role, "tool": tool}

    def broadcast_command(self, command):
        """Broadcast a command to all workers in squad."""
        msg = f"CMD:{command}"
        # self.nrf.send(msg.encode())

    def report_to_mothership(self, data):
        """Send status report via CAN bus backbone."""
        msg = f"TM_REPORT:{data}\n"
        self.uart.write(msg.encode())

    def tick(self):
        """Main control loop tick."""
        # 1. Check for messages from workers
        # 2. Check for commands from mothership
        if self.uart.any():
            line = self.uart.readline()
            if line:
                self._handle_mothership_command(line.decode().strip())

        # 3. Navigate / patrol
        # 4. Classify regolith at work face
        # 5. Assign roles based on colony needs

    def _handle_mothership_command(self, cmd):
        """Process a command from the mothership."""
        if cmd.startswith("RETARGET:"):
            area = cmd.split(":")[1]
            self.broadcast_command(f"MOVE_TO:{area}")
        elif cmd.startswith("EMERGENCY_STOP"):
            self.broadcast_command("STOP_ALL")


def main():
    print("AstraAnt Taskmaster v0.1.0 -- ESP32-S3")
    tm = Taskmaster()
    sensors = tm.scan_sensors()
    print(f"Sensors found: {sensors}")
    print(f"I2C devices: {tm.i2c.scan()}")
    print("Entering main loop...")

    while True:
        try:
            tm.tick()
            time.sleep_ms(50)
        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep_ms(1000)


if __name__ == "__main__":
    main()
