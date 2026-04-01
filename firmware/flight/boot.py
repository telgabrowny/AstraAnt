# AstraAnt Seed Mothership -- boot.py
# Runs once on power-up before main.py
# Initializes watchdog, loads config, prints boot banner
#
# Target: ESP32-S3 (triple modular redundancy -- 3 units, this is one)
# Flash: mpremote connect /dev/ttyUSB0 cp -r firmware/flight/ :

import machine
import gc
import json
import sys
import time

# ---------------------------------------------------------------------------
# Hardware init -- must happen before anything else
# ---------------------------------------------------------------------------

# Set CPU to max (ESP32-S3: 240 MHz)
machine.freq(240_000_000)

# I2C bus 0: gyro, sun sensors (digital), temperature sensors
# Pins set in config.json but we need I2C up before config loads
# for watchdog board communication
try:
    i2c0 = machine.I2C(0, sda=machine.Pin(8), scl=machine.Pin(9), freq=400_000)
except Exception:
    i2c0 = None

# SPI bus: star tracker, spectral sensor
try:
    spi1 = machine.SPI(1,
                        baudrate=1_000_000,
                        polarity=0,
                        phase=0,
                        mosi=machine.Pin(35),
                        miso=machine.Pin(37),
                        sck=machine.Pin(36))
except Exception:
    spi1 = None

# ---------------------------------------------------------------------------
# Watchdog timer -- reboot if main loop hangs for 60 seconds
# ---------------------------------------------------------------------------
try:
    wdt = machine.WDT(timeout=60_000)
except Exception:
    # Some MicroPython ports don't support WDT at boot
    wdt = None

# ---------------------------------------------------------------------------
# Load mission config
# ---------------------------------------------------------------------------
CONFIG = None
CONFIG_PATH = "config.json"

try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = json.load(f)
except Exception as e:
    print("BOOT ERROR: Failed to load config.json:", e)
    CONFIG = {"firmware_version": "0.1.0-fallback", "mission": "UNKNOWN"}

# ---------------------------------------------------------------------------
# Reboot counter (persisted in NVS via file)
# ---------------------------------------------------------------------------
REBOOT_COUNT_FILE = "reboot_count.dat"

def read_reboot_count():
    """Read reboot counter from persistent storage."""
    try:
        with open(REBOOT_COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def write_reboot_count(n):
    """Write reboot counter to persistent storage."""
    try:
        with open(REBOOT_COUNT_FILE, "w") as f:
            f.write(str(n))
    except Exception:
        pass

reboot_count = read_reboot_count()
write_reboot_count(reboot_count + 1)

# Check if we should boot into safe mode due to repeated crashes
limits = CONFIG.get("limits", {})
safe_after = limits.get("safe_mode_after_reboots", 5)
max_reboots = limits.get("max_reboot_count", 10)
FORCE_SAFE_MODE = reboot_count >= safe_after

if reboot_count >= max_reboots:
    # Too many reboots -- halt and beacon only
    FORCE_SAFE_MODE = True

# ---------------------------------------------------------------------------
# Boot banner
# ---------------------------------------------------------------------------
gc.collect()
free_ram = gc.mem_free()
fw_ver = CONFIG.get("firmware_version", "?")
mission = CONFIG.get("mission", "?")
target = CONFIG.get("target_asteroid", "?")

print("")
print("=" * 60)
print("  AstraAnt Seed Mothership Flight Computer")
print("  Firmware: v%s" % fw_ver)
print("  Mission:  %s -> %s" % (mission, target))
print("  Reboots:  %d (safe_mode=%s)" % (reboot_count, FORCE_SAFE_MODE))
print("  Free RAM: %d bytes" % free_ram)
print("  CPU freq: %d MHz" % (machine.freq() // 1_000_000))
if i2c0:
    try:
        devs = i2c0.scan()
        print("  I2C devs: %s" % [hex(d) for d in devs])
    except Exception:
        print("  I2C devs: scan failed")
else:
    print("  I2C bus:  not available")
print("=" * 60)
print("")

# Expose globals for main.py
# main.py imports: from boot import CONFIG, wdt, i2c0, spi1, FORCE_SAFE_MODE, reboot_count
