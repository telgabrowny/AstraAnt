"""Tech upgrades -- better components available via resupply rockets.

You don't "research" anything. You BUY better parts. New components
become available as real manufacturers release improved versions
(modeled as time-based catalog updates). You include them in your
next resupply drop, funded from mining revenue.

This is a CATALOG UPGRADE PATH, not a tech tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CatalogUpgrade:
    """A component upgrade available for purchase."""
    id: str
    name: str
    category: str
    available_after_year: float     # Game year when this becomes available
    cost_per_unit_usd: float
    mass_per_unit_kg: float
    replaces: str                    # ID of the component it replaces
    improvement: dict[str, Any]     # What gets better
    description: str
    units_needed: int = 1           # How many per ant or per mothership


UPGRADES = [
    # Year 1-2: immediate improvements (ship with first resupply)
    CatalogUpgrade(
        id="sg90_metal_gear",
        name="SG90 Metal Gear Servo",
        category="actuator",
        available_after_year=1,
        cost_per_unit_usd=5,
        mass_per_unit_kg=0.011,
        replaces="sg90_servo",
        improvement={"mtbf_hours_sealed": 20000, "note": "Metal gears instead of plastic. 2.5x MTBF."},
        description="Drop-in replacement for SG90 with metal gear train. Same size, same pinout. "
                    "Plastic gears were the #1 failure mode. Metal gears last 2.5x longer.",
        units_needed=8,
    ),
    CatalogUpgrade(
        id="supercap_100f",
        name="100F Supercapacitor (worker upgrade)",
        category="energy_storage",
        available_after_year=1,
        cost_per_unit_usd=6,
        mass_per_unit_kg=0.015,
        replaces="supercapacitor_backup",
        improvement={"energy_wh": 0.4, "off_rail_minutes": 4, "note": "2x off-rail time."},
        description="Double the off-rail operating time. Workers can drill longer per trip. "
                    "Particularly useful for deep branch tunnels far from the main rail.",
        units_needed=1,
    ),

    # Year 2-3: meaningful upgrades
    CatalogUpgrade(
        id="n20_brushless",
        name="N20 Brushless DC Motor",
        category="motor",
        available_after_year=2,
        cost_per_unit_usd=12,
        mass_per_unit_kg=0.012,
        replaces="n20_dc_motor",
        improvement={"mtbf_hours": 50000, "efficiency_pct": 90, "note": "No brushes to wear. 10x lifetime."},
        description="Brushless version of the N20 drill motor. No brush wear, no sparking, "
                    "90% efficiency vs 60% for brushed. Drill bits last longer too (less vibration).",
        units_needed=1,
    ),
    CatalogUpgrade(
        id="vl53l1x_lidar",
        name="VL53L1X Long-Range ToF Sensor",
        category="sensor",
        available_after_year=2,
        cost_per_unit_usd=5,
        mass_per_unit_kg=0.001,
        replaces="vl53l0x_lidar",
        improvement={"range_mm": 4000, "note": "2x range (4m vs 2m). Better for tunnel mapping."},
        description="Next-gen ToF sensor from ST. 4m range in dark tunnels. Same I2C address.",
        units_needed=1,
    ),
    CatalogUpgrade(
        id="esp32_s3_rad_tolerant",
        name="ESP32-S3 with Rad-Tolerant Packaging",
        category="compute",
        available_after_year=3,
        cost_per_unit_usd=25,
        mass_per_unit_kg=0.012,
        replaces="esp32_s3",
        improvement={"seu_rate_reduction": 10, "note": "10x fewer single-event upsets. For taskmasters."},
        description="Same ESP32-S3 die in radiation-hardened packaging. Mostly useful for "
                    "taskmasters at shallow depth where residual radiation is higher.",
        units_needed=1,
    ),

    # Year 3-5: game-changing upgrades
    CatalogUpgrade(
        id="rp2350",
        name="RP2350 Microcontroller",
        category="compute",
        available_after_year=3,
        cost_per_unit_usd=1.5,
        mass_per_unit_kg=0.005,
        replaces="rp2040",
        improvement={"clock_mhz": 200, "ram_kb": 520, "security": "ARM TrustZone",
                     "note": "Faster, more RAM, security features. Drop-in board replacement."},
        description="Next-gen Raspberry Pi microcontroller. 2x faster, 2x RAM. "
                    "Enables more complex worker autonomy (local obstacle avoidance).",
        units_needed=1,
    ),
    CatalogUpgrade(
        id="tungsten_carbide_drill",
        name="Tungsten Carbide Drill Insert",
        category="tool",
        available_after_year=2,
        cost_per_unit_usd=15,
        mass_per_unit_kg=0.005,
        replaces="drill_head",
        improvement={"bit_lifetime_hours": 500, "excavation_rate_bonus_pct": 30,
                     "note": "10x bit lifetime. 30% faster drilling. Worth the cost."},
        description="Sintered tungsten carbide insert for the drill head. Massively longer "
                    "bit life and faster cutting in hard regolith. The upgrade every miner wants.",
        units_needed=1,
    ),
    CatalogUpgrade(
        id="piezo_actuator",
        name="Piezoelectric Leg Actuator",
        category="actuator",
        available_after_year=5,
        cost_per_unit_usd=20,
        mass_per_unit_kg=0.006,
        replaces="sg90_servo",
        improvement={"mtbf_hours_sealed": 100000, "power_mw": 200, "mass_g": 6,
                     "note": "No gears at all. Solid state. Essentially infinite mechanical life."},
        description="Solid-state piezoelectric actuators. No gears, no bearings, no brushes. "
                    "100K+ hour MTBF. 1/3 the power draw. The endgame actuator technology.",
        units_needed=8,
    ),

    # Year 5+: transformative
    CatalogUpgrade(
        id="onboard_ml_chip",
        name="Neural Inference Accelerator",
        category="compute",
        available_after_year=5,
        cost_per_unit_usd=15,
        mass_per_unit_kg=0.003,
        replaces="none",  # Addition, not replacement
        improvement={"local_decision_making": True,
                     "note": "Workers make some decisions locally instead of waiting for taskmaster. "
                             "Obstacle avoidance, anomaly pre-screening, path optimization."},
        description="Coral-class ML accelerator. Allows workers to run simple neural nets "
                    "locally. Reduces radio traffic by 60% (workers handle routine decisions).",
        units_needed=1,
    ),
]


class UpgradeManager:
    """Tracks available and purchased upgrades."""

    def __init__(self):
        self.available: list[CatalogUpgrade] = []
        self.purchased: dict[str, int] = {}  # upgrade_id -> quantity bought
        self.installed: dict[str, int] = {}  # upgrade_id -> quantity installed

    def check_availability(self, current_year: float) -> list[CatalogUpgrade]:
        """Check which new upgrades have become available."""
        newly_available = []
        for upgrade in UPGRADES:
            if upgrade.available_after_year <= current_year:
                if upgrade not in self.available:
                    self.available.append(upgrade)
                    newly_available.append(upgrade)
        return newly_available

    def purchase(self, upgrade_id: str, quantity: int, cash: float) -> dict[str, Any]:
        """Purchase an upgrade for the next resupply. Returns cost or error."""
        upgrade = next((u for u in self.available if u.id == upgrade_id), None)
        if upgrade is None:
            return {"error": f"Upgrade {upgrade_id} not available yet"}

        cost = upgrade.cost_per_unit_usd * quantity
        if cost > cash:
            return {"error": f"Need ${cost:,.0f} but only ${cash:,.0f} available"}

        self.purchased[upgrade_id] = self.purchased.get(upgrade_id, 0) + quantity
        return {
            "upgrade": upgrade,
            "quantity": quantity,
            "cost": cost,
            "message": f"Purchased {quantity}x {upgrade.name} for ${cost:,.0f}. "
                       f"Ships with next resupply rocket.",
        }

    def summary(self) -> dict[str, Any]:
        return {
            "available": len(self.available),
            "purchased": dict(self.purchased),
            "installed": dict(self.installed),
            "upgrades": [{"id": u.id, "name": u.name, "year": u.available_after_year,
                          "cost": u.cost_per_unit_usd}
                         for u in self.available],
        }
