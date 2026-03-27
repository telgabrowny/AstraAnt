"""VL53L0X Time-of-Flight distance sensor driver for MicroPython.

Minimal driver for the ST VL53L0X laser ranging sensor.
I2C interface, default address 0x29.

Based on the ST API and pololu/vl53l0x-arduino reference implementation.
Simplified for the RP2040 -- only continuous ranging mode.
"""

import time
from micropython import const

# Default I2C address
_VL53L0X_ADDR = const(0x29)

# Register addresses
_REG_SYSRANGE_START = const(0x00)
_REG_RESULT_RANGE_STATUS = const(0x14)
_REG_RESULT_RANGE_VAL = const(0x1E)  # 16-bit range result (mm)
_REG_SYSTEM_INTERRUPT_CLEAR = const(0x0B)
_REG_I2C_SLAVE_ADDR = const(0x8A)


class VL53L0X:
    """Minimal VL53L0X driver for distance measurement."""

    def __init__(self, i2c, address=_VL53L0X_ADDR):
        self.i2c = i2c
        self.addr = address
        self._initialized = False

        # Verify the sensor is present
        devices = i2c.scan()
        if address not in devices:
            print(f"VL53L0X not found at 0x{address:02X}. Found: {[hex(d) for d in devices]}")
            return

        self._init_sensor()

    def _init_sensor(self):
        """Initialize the sensor for continuous ranging."""
        try:
            # Set default tuning parameters
            self._write_reg(0x88, 0x00)
            self._write_reg(0x80, 0x01)
            self._write_reg(0xFF, 0x01)
            self._write_reg(0x00, 0x00)
            self._write_reg(0x00, 0x01)
            self._write_reg(0xFF, 0x00)
            self._write_reg(0x80, 0x00)

            # Start continuous ranging
            self._write_reg(_REG_SYSRANGE_START, 0x02)
            self._initialized = True
        except Exception as e:
            print(f"VL53L0X init failed: {e}")

    def read_range_mm(self) -> int:
        """Read distance in millimeters. Returns -1 if no reading available."""
        if not self._initialized:
            return -1

        try:
            # Check if measurement is ready
            status = self._read_reg(_REG_RESULT_RANGE_STATUS)
            if not (status & 0x01):
                return -1  # Not ready yet

            # Read 16-bit range value
            data = self.i2c.readfrom_mem(self.addr, _REG_RESULT_RANGE_VAL, 2)
            distance_mm = (data[0] << 8) | data[1]

            # Clear interrupt
            self._write_reg(_REG_SYSTEM_INTERRUPT_CLEAR, 0x01)

            # Restart measurement
            self._write_reg(_REG_SYSRANGE_START, 0x02)

            # Sanity check (max range is ~2000mm)
            if distance_mm > 2000 or distance_mm == 0:
                return -1

            return distance_mm

        except Exception:
            return -1

    def _write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def _read_reg(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def change_address(self, new_address):
        """Change the I2C address (useful for multiple sensors)."""
        self._write_reg(_REG_I2C_SLAVE_ADDR, new_address & 0x7F)
        self.addr = new_address
