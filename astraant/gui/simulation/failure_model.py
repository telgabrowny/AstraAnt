"""Detailed failure model for ant components.

Models realistic failure modes, detection by taskmaster, recovery
procedures, and salvage yields per component.

Most common failure: ONE servo strips its gears (plastic under load).
The other 7 servos, MCU, sensors, radio, and battery are all fine.
That's $3 of damage on a $33 ant, with ~$30 of parts salvageable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentHealth:
    """Health tracking for each component in an ant."""
    # Each component has remaining life as fraction (1.0 = new, 0.0 = failed)
    leg_servos: list[float] = field(default_factory=lambda: [1.0] * 6)
    mandible_servos: list[float] = field(default_factory=lambda: [1.0, 1.0])
    mcu: float = 1.0
    radio: float = 1.0
    lidar_sensor: float = 1.0
    battery: float = 1.0
    wiring: float = 1.0
    chassis: float = 1.0

    def tick(self, dt_hours: float) -> str | None:
        """Degrade components over time. Returns failure description or None."""
        # Servo wear: each servo degrades at different rates based on load
        for i in range(6):
            wear = dt_hours / 8000  # MTBF 8000 hrs
            self.leg_servos[i] -= wear * random.uniform(0.8, 1.5)
            if self.leg_servos[i] <= 0:
                self.leg_servos[i] = 0
                leg_name = ["front-left", "front-right", "mid-left",
                            "mid-right", "rear-left", "rear-right"][i]
                return f"leg servo ({leg_name}) gear stripped -- ant immobilized"

        for i in range(2):
            wear = dt_hours / 10000  # Mandibles under less load
            self.mandible_servos[i] -= wear * random.uniform(0.8, 1.2)
            if self.mandible_servos[i] <= 0:
                self.mandible_servos[i] = 0
                return f"mandible servo ({'left' if i == 0 else 'right'}) failed -- can't hold tools"

        # Battery degradation (gradual) — NOT a hard kill since ants are tethered.
        # Battery failure just means the ant can't do short untethered moves.
        self.battery -= dt_hours / (500 * 5)
        if self.battery <= 0 and self.battery > -0.01:
            self.battery = 0
            # Return None — battery death is a downgrade, not a kill
            # The ant can still work on tether power

        # Sensor degradation
        self.lidar_sensor -= dt_hours / 10000
        if self.lidar_sensor <= 0:
            self.lidar_sensor = 0
            return "VL53L0x laser diode degraded -- no proximity sensing"

        # MCU failure (rare, usually from power surge)
        if random.random() < dt_hours / 50000:
            self.mcu = 0
            return "MCU fault (power surge or bit flip) -- ant unresponsive"

        # Wiring fatigue (at leg joints)
        self.wiring -= dt_hours / 20000
        if self.wiring <= 0:
            self.wiring = 0
            return "wire fatigue at leg joint -- intermittent power loss"

        return None  # No failure this tick

    def get_salvageable_parts(self) -> dict[str, Any]:
        """After failure, determine what can be salvaged."""
        salvage = {
            "working_leg_servos": sum(1 for s in self.leg_servos if s > 0.3),
            "working_mandible_servos": sum(1 for s in self.mandible_servos if s > 0.3),
            "mcu_ok": self.mcu > 0.5,
            "radio_ok": self.radio > 0.5,
            "sensor_ok": self.lidar_sensor > 0.3,
            "battery_usable": self.battery > 0.2,  # Degraded but still holds some charge
            "chassis_metal_g": 46,        # ~40% of 115g ant = metal
            "chassis_plastic_g": 35,      # ~30% = PETG
            "copper_wire_g": 5,           # Small amount of wire
        }

        # Total value estimate
        salvage["total_parts_value_usd"] = (
            salvage["working_leg_servos"] * 3 +
            salvage["working_mandible_servos"] * 2 +
            (4 if salvage["mcu_ok"] else 0) +
            (2 if salvage["radio_ok"] else 0) +
            (4 if salvage["sensor_ok"] else 0) +
            (3 if salvage["battery_usable"] else 0)
        )
        salvage["recyclable_metal_g"] = (
            salvage["chassis_metal_g"] +
            (9 * (6 - salvage["working_leg_servos"])) +  # Dead servo metal
            (5 * (2 - salvage["working_mandible_servos"])) +
            salvage["copper_wire_g"]
        )

        return salvage


@dataclass
class FailureDetection:
    """How the taskmaster detects worker failures."""

    detection_methods = {
        "heartbeat_timeout": {
            "description": "Worker stops sending 5-second heartbeat via nRF24L01",
            "detection_time_seconds": 15,  # 3 missed heartbeats
            "catches": ["MCU fault", "power loss", "radio failure", "total destruction"],
        },
        "servo_stall_current": {
            "description": "Worker reports high current draw but no position change on a servo",
            "detection_time_seconds": 2,
            "catches": ["stripped gears", "jammed leg", "seized bearing"],
        },
        "position_stuck": {
            "description": "Worker position hasn't changed for 30+ seconds while in moving state",
            "detection_time_seconds": 30,
            "catches": ["immobilized", "stuck on obstacle", "tether tangled"],
        },
        "erratic_behavior": {
            "description": "Worker moving in circles, reporting impossible sensor values",
            "detection_time_seconds": 10,
            "catches": ["MCU bit flip", "sensor malfunction", "corrupted firmware"],
        },
        "power_anomaly": {
            "description": "Tether voltage drops or battery level crashes suddenly",
            "detection_time_seconds": 1,
            "catches": ["battery failure", "tether disconnect", "short circuit"],
        },
    }

    @staticmethod
    def detect_failure(failure_description: str) -> dict[str, Any]:
        """Given a failure, determine how it's detected and what happens next."""
        # Map failure types to detection methods
        if "servo" in failure_description or "gear" in failure_description:
            method = "servo_stall_current"
            response = "STALL DETECTED"
        elif "MCU" in failure_description or "unresponsive" in failure_description:
            method = "heartbeat_timeout"
            response = "HEARTBEAT LOST"
        elif "battery" in failure_description:
            method = "power_anomaly"
            response = "POWER FAULT"
        elif "wire" in failure_description:
            method = "position_stuck"
            response = "MOVEMENT STOPPED"
        elif "sensor" in failure_description or "laser" in failure_description:
            method = "erratic_behavior"
            response = "SENSOR ANOMALY"
        else:
            method = "heartbeat_timeout"
            response = "UNRESPONSIVE"

        detection = FailureDetection.detection_methods.get(method, {})

        return {
            "detection_method": method,
            "response_label": response,
            "detection_time_s": detection.get("detection_time_seconds", 15),
            "description": detection.get("description", ""),
            "recovery_procedure": _get_recovery_procedure(failure_description),
        }


def _get_recovery_procedure(failure: str) -> list[str]:
    """Step-by-step recovery after a worker ant is detected as failed."""
    steps = [
        "1. Taskmaster marks worker as FAILED in squad roster",
        "2. Taskmaster radios nearest available worker with cargo_gripper",
    ]

    if "servo" in failure or "gear" in failure:
        steps.extend([
            "3. Recovery worker approaches and grips the immobilized ant",
            "4. Drags the carcass back to the manufacturing bay",
            "5. At the bay: test each servo individually (power + observe movement)",
            "6. Working servos removed and placed in spare parts bin",
            "7. Failed servo + chassis go to the sintering furnace",
            "8. Metal melted and added to iron stockpile",
            "9. Taskmaster reassigns remaining squad to cover the gap",
        ])
    elif "MCU" in failure:
        steps.extend([
            "3. Recovery worker approaches -- ant may be physically intact but brain-dead",
            "4. Drags to manufacturing bay",
            "5. ALL servos likely fine (mechanical, unaffected by MCU fault)",
            "6. Sensors and radio may be fine (test individually)",
            "7. MCU board discarded (can't trust a corrupted chip)",
            "8. Salvage: ~7 servos, sensor, radio, battery -- $27 of $33 recovered",
        ])
    elif "battery" in failure:
        steps.extend([
            "3. Worker is still functional on tether power but can't go untethered",
            "4. Could continue operating if work area is within tether range",
            "5. Otherwise: drag to bay, swap battery from spares (if available)",
            "6. If no spare battery: salvage everything else, recycle the ant",
            "7. Battery lithium goes to chemical recycling (future capability)",
        ])
    else:
        steps.extend([
            "3. Recovery worker retrieves the carcass",
            "4. Full disassembly at manufacturing bay",
            "5. Test each component, sort into working/broken",
            "6. Working parts to spares, broken parts to furnace",
        ])

    return steps
