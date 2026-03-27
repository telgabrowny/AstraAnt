"""nRF24L01+ radio driver for MicroPython.

Minimal driver for Nordic Semiconductor nRF24L01+ 2.4 GHz transceiver.
SPI interface. 32-byte fixed payload.

Based on micropython-nrf24l01 by Peter Hinch and the Nordic datasheet.
Simplified for AstraAnt worker-to-taskmaster communication.
"""

import time
from micropython import const

# nRF24L01 register addresses
_CONFIG = const(0x00)
_EN_AA = const(0x01)
_EN_RXADDR = const(0x02)
_SETUP_AW = const(0x03)
_SETUP_RETR = const(0x04)
_RF_CH = const(0x05)
_RF_SETUP = const(0x06)
_STATUS = const(0x07)
_RX_ADDR_P0 = const(0x0A)
_TX_ADDR = const(0x10)
_RX_PW_P0 = const(0x11)

# Commands
_R_RX_PAYLOAD = const(0x61)
_W_TX_PAYLOAD = const(0xA0)
_FLUSH_TX = const(0xE1)
_FLUSH_RX = const(0xE2)
_NOP = const(0xFF)

PAYLOAD_SIZE = const(32)  # Fixed 32-byte packets for AstraAnt protocol


class NRF24L01:
    """Simplified nRF24L01+ driver for 32-byte packet communication."""

    def __init__(self, spi, csn_pin, ce_pin, channel=76, payload_size=PAYLOAD_SIZE):
        self.spi = spi
        self.csn = csn_pin
        self.ce = ce_pin
        self.payload_size = payload_size

        # Initialize pins
        self.csn.value(1)
        self.ce.value(0)
        time.sleep_ms(5)

        # Configure the radio
        self._write_reg(_CONFIG, 0x0C)       # CRC enabled, 2-byte CRC
        self._write_reg(_EN_AA, 0x01)        # Auto-ack on pipe 0
        self._write_reg(_EN_RXADDR, 0x01)    # Enable pipe 0
        self._write_reg(_SETUP_AW, 0x03)     # 5-byte address
        self._write_reg(_SETUP_RETR, 0x3F)   # 15 retransmits, 1000us delay
        self._write_reg(_RF_CH, channel)     # Channel (0-125)
        self._write_reg(_RF_SETUP, 0x06)     # 1Mbps, 0dBm power
        self._write_reg(_RX_PW_P0, payload_size)

        self._flush_tx()
        self._flush_rx()

    def set_address(self, tx_addr: bytes, rx_addr: bytes):
        """Set transmit and receive addresses (5 bytes each)."""
        self._write_reg_multi(_TX_ADDR, tx_addr)
        self._write_reg_multi(_RX_ADDR_P0, rx_addr)

    def send(self, data: bytes) -> bool:
        """Send a packet (blocking). Returns True if ACK received."""
        if len(data) > self.payload_size:
            data = data[:self.payload_size]
        elif len(data) < self.payload_size:
            data = data + bytes(self.payload_size - len(data))

        self.ce.value(0)

        # Power up as TX
        config = self._read_reg(_CONFIG)
        self._write_reg(_CONFIG, (config | 0x02) & ~0x01)  # PWR_UP=1, PRIM_RX=0
        time.sleep_us(150)

        # Write payload
        self._flush_tx()
        self.csn.value(0)
        self.spi.write(bytes([_W_TX_PAYLOAD]))
        self.spi.write(data)
        self.csn.value(1)

        # Pulse CE to transmit
        self.ce.value(1)
        time.sleep_us(15)
        self.ce.value(0)

        # Wait for TX complete or timeout
        for _ in range(100):
            status = self._read_reg(_STATUS)
            if status & 0x20:  # TX_DS (data sent)
                self._write_reg(_STATUS, 0x20)  # Clear flag
                return True
            if status & 0x10:  # MAX_RT (max retransmits)
                self._write_reg(_STATUS, 0x10)
                self._flush_tx()
                return False
            time.sleep_us(100)

        return False

    def start_listening(self):
        """Enter receive mode."""
        config = self._read_reg(_CONFIG)
        self._write_reg(_CONFIG, config | 0x03)  # PWR_UP=1, PRIM_RX=1
        self._flush_rx()
        self.ce.value(1)
        time.sleep_us(130)

    def stop_listening(self):
        """Exit receive mode."""
        self.ce.value(0)

    def available(self) -> bool:
        """Check if a packet is available to read."""
        status = self._read_reg(_STATUS)
        return bool(status & 0x40)  # RX_DR flag

    def receive(self) -> bytes | None:
        """Read a received packet. Returns None if no packet available."""
        if not self.available():
            return None

        self.csn.value(0)
        self.spi.write(bytes([_R_RX_PAYLOAD]))
        data = self.spi.read(self.payload_size)
        self.csn.value(1)

        # Clear RX flag
        self._write_reg(_STATUS, 0x40)

        return bytes(data)

    def _write_reg(self, reg, value):
        self.csn.value(0)
        self.spi.write(bytes([0x20 | reg, value]))
        self.csn.value(1)

    def _write_reg_multi(self, reg, data):
        self.csn.value(0)
        self.spi.write(bytes([0x20 | reg]))
        self.spi.write(data)
        self.csn.value(1)

    def _read_reg(self, reg):
        self.csn.value(0)
        self.spi.write(bytes([reg]))
        result = self.spi.read(1)
        self.csn.value(1)
        return result[0]

    def _flush_tx(self):
        self.csn.value(0)
        self.spi.write(bytes([_FLUSH_TX]))
        self.csn.value(1)

    def _flush_rx(self):
        self.csn.value(0)
        self.spi.write(bytes([_FLUSH_RX]))
        self.csn.value(1)
