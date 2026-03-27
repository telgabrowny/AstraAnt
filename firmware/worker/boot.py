# AstraAnt Worker Ant -- boot.py
# This runs once on power-up before main.py
# Sets up any hardware that needs early initialization

import machine
import gc

# Set CPU frequency (RP2040 can run 48-133 MHz)
machine.freq(133_000_000)  # Full speed for servo timing accuracy

# Free memory
gc.collect()
print(f"AstraAnt Worker boot. Free RAM: {gc.mem_free()} bytes")
