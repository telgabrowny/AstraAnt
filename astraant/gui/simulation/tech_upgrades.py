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


# ---- System-level upgrades ----
# These are whole-capability unlocks, not individual component swaps.
# Delivered as complete modules via resupply rockets. Each one changes
# what the colony can DO, not just how well it does it.

@dataclass
class SystemUpgrade:
    """A system-level capability upgrade delivered via resupply."""
    id: str
    name: str
    available_after_year: float
    delivery_method: str              # Key into DELIVERY_METHODS
    delivery_mass_kg: float           # Total mass of the module
    cost_usd: float                   # Hardware cost (delivery cost is separate)
    requires: list[str] = field(default_factory=list)  # IDs of prerequisite upgrades
    effects: dict[str, Any] = field(default_factory=dict)
    description: str = ""


SYSTEM_UPGRADES = [
    # Year 0: available from the start (if you have the budget)
    SystemUpgrade(
        id="battery_bank",
        name="Mothership Battery Bank",
        available_after_year=0,
        delivery_method="cubesat_12u",
        delivery_mass_kg=20,
        cost_usd=15_000,
        effects={
            "night_power_fraction": 0.6,  # 60% capacity during dark periods
            "note": "LiFePO4 battery bank. Bridges asteroid dark periods at 60% capacity. "
                    "Essential for slow rotators (Itokawa 12hr rotation).",
        },
        description="Lithium iron phosphate battery bank for the mothership power rail. "
                    "Stores solar energy during daylight, powers tunnel operations during dark periods. "
                    "20 kg, fits in a 12U CubeSat. Enables 24/7 mining at reduced night capacity.",
    ),

    # Year 2-3: bioleaching (the big early upgrade)
    SystemUpgrade(
        id="bioreactor_module",
        name="Centrifuge Bioleaching Bay",
        available_after_year=2,
        delivery_method="cubesat_12u",
        delivery_mass_kg=22,
        cost_usd=50_000,
        effects={
            "extraction_multiplier": 5.0,
            "new_metals": ["copper", "cobalt", "rare_earths"],
            "requires_water_kg": 300,
            "startup_days": 90,
            "note": "Bacteria dissolve metals from regolith at 5x the purity of mechanical "
                    "sorting. 90-day startup while cultures establish. Needs water (from ice "
                    "extraction or delivered). Self-sustaining once running.",
        },
        description="The single biggest revenue upgrade. Bioleaching bacteria extract copper, "
                    "cobalt, and rare earths that mechanical sorting cannot reach. 5x extraction "
                    "purity. Self-sustaining biology -- bacteria replicate, sugar grown on-site. "
                    "90-day startup period while cultures establish in centrifuge vats.",
    ),
    SystemUpgrade(
        id="sugar_production",
        name="In-Situ Sugar Production",
        available_after_year=2,
        delivery_method="cubesat_6u",
        delivery_mass_kg=8,
        cost_usd=20_000,
        requires=["bioreactor_module"],
        effects={
            "eliminates_sugar_resupply": True,
            "note": "Algae photobioreactor produces sucrose from CO2 + water + light. "
                    "Closes the consumables loop for bioleaching.",
        },
        description="Algae photobioreactor. Converts CO2 (from thermal extraction) + water + "
                    "light into sucrose to feed bioleaching bacteria. Eliminates Earth sugar "
                    "dependency. Small, light, fits in a 6U CubeSat.",
    ),

    # Year 5-8: nuclear power
    SystemUpgrade(
        id="fission_reactor_1kw",
        name="Kilopower Fission Reactor (1 kWe)",
        available_after_year=5,
        delivery_method="espa_rideshare",
        delivery_mass_kg=75,
        cost_usd=15_000_000,        # Hardware only; delivery cost is separate
        effects={
            "power_kw": 1.0,
            "eliminates_day_night": True,
            "enables_deep_ops": True,
            "note": "Based on NASA KRUSTY (tested 2018). Uranium-235 Stirling engine. "
                    "24/7 power regardless of solar distance or asteroid rotation. "
                    "1 kWe is modest but eliminates all dark-period constraints.",
        },
        description="NASA Kilopower-class fission reactor. 1 kW electric, 75 kg, fits on an "
                    "ESPA rideshare. Eliminates day/night power cycling entirely. Enables "
                    "operations on far-from-sun asteroids (Psyche at 2.9 AU). The single biggest "
                    "quality-of-life upgrade. 10+ year fuel life.",
    ),
    SystemUpgrade(
        id="fission_reactor_10kw",
        name="Kilopower Fission Reactor (10 kWe)",
        available_after_year=8,
        delivery_method="dedicated_falcon_heavy",
        delivery_mass_kg=1500,
        cost_usd=25_000_000,
        requires=["fission_reactor_1kw"],
        effects={
            "power_kw": 10.0,
            "enables_manufacturing": True,
            "note": "10x the 1kW unit. Enough power for metal 3D printing, chip fabrication, "
                    "and large-scale bioreactor operations.",
        },
        description="Scaled-up Kilopower reactor. 10 kWe enables energy-intensive operations: "
                    "metal sintering, 3D printing from extracted metals, large bioreactor arrays. "
                    "Requires dedicated launch (1500 kg). The foundation for in-situ manufacturing.",
    ),

    # Year 10-15: manufacturing
    SystemUpgrade(
        id="metal_3d_printer",
        name="Laser Sintering Metal Printer",
        available_after_year=10,
        delivery_method="espa_rideshare",
        delivery_mass_kg=120,
        cost_usd=2_000_000,
        requires=["fission_reactor_10kw"],
        effects={
            "can_print": ["chassis", "tools", "structural_parts", "gears"],
            "reduces_earth_dependency_pct": 40,
            "note": "Print ant chassis, replacement tools, structural brackets from extracted "
                    "asteroid iron/nickel. 40% reduction in Earth resupply needs.",
        },
        description="Selective laser sintering printer. Uses extracted asteroid metals (iron, "
                    "nickel alloy) as feedstock. Prints ant chassis, tool heads, structural "
                    "parts, gears. Resolution ~0.1mm. Requires 10kW reactor for the laser. "
                    "The first step toward self-sufficiency.",
    ),

    # Year 15-25: speculative but grounded
    SystemUpgrade(
        id="fusion_micro_reactor",
        name="Fusion Micro-Reactor (50 kWe)",
        available_after_year=20,
        delivery_method="dedicated_starship",
        delivery_mass_kg=5000,
        cost_usd=100_000_000,
        requires=["fission_reactor_10kw"],
        effects={
            "power_kw": 50.0,
            "enables_heavy_manufacturing": True,
            "note": "Speculative but plausible (Commonwealth Fusion, Helion timelines). "
                    "Order-of-magnitude power increase enables full manufacturing capability.",
        },
        description="Compact fusion reactor. 50 kWe, enough for industrial-scale manufacturing, "
                    "large habitat climate control, and powering hundreds of heavy ants. "
                    "Speculative near-future technology based on current fusion startup timelines.",
    ),
]


class UpgradeManager:
    """Tracks available and purchased upgrades (component + system level)."""

    def __init__(self):
        # Component upgrades (individual parts: servos, sensors, MCUs)
        self.available: list[CatalogUpgrade] = []
        self.purchased: dict[str, int] = {}  # upgrade_id -> quantity bought
        self.installed: dict[str, int] = {}  # upgrade_id -> quantity installed

        # System upgrades (whole capabilities: bioreactor, nuclear, manufacturing)
        self.systems_available: list[SystemUpgrade] = []
        self.systems_unlocked: dict[str, bool] = {}  # system_id -> True if delivered+installed

    def check_availability(self, current_year: float) -> list[CatalogUpgrade | SystemUpgrade]:
        """Check which new upgrades have become available."""
        newly_available: list[CatalogUpgrade | SystemUpgrade] = []

        for upgrade in UPGRADES:
            if upgrade.available_after_year <= current_year:
                if upgrade not in self.available:
                    self.available.append(upgrade)
                    newly_available.append(upgrade)

        for sys_up in SYSTEM_UPGRADES:
            if sys_up.available_after_year <= current_year:
                if sys_up not in self.systems_available:
                    # Check prerequisites
                    prereqs_met = all(
                        self.systems_unlocked.get(req, False) for req in sys_up.requires
                    )
                    if prereqs_met:
                        self.systems_available.append(sys_up)
                        newly_available.append(sys_up)

        return newly_available

    def purchase(self, upgrade_id: str, quantity: int, cash: float) -> dict[str, Any]:
        """Purchase a component upgrade for the next resupply. Returns cost or error."""
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

    def purchase_system(self, system_id: str, cash: float) -> dict[str, Any]:
        """Purchase a system upgrade (hardware cost only; delivery cost is separate)."""
        sys_up = next((s for s in self.systems_available if s.id == system_id), None)
        if sys_up is None:
            return {"error": f"System {system_id} not available yet"}
        if self.systems_unlocked.get(system_id):
            return {"error": f"System {system_id} already installed"}
        if sys_up.cost_usd > cash:
            return {"error": f"Need ${sys_up.cost_usd:,.0f} but only ${cash:,.0f} available"}
        return {
            "system": sys_up,
            "cost": sys_up.cost_usd,
            "delivery_method": sys_up.delivery_method,
            "delivery_mass_kg": sys_up.delivery_mass_kg,
            "message": f"Purchased {sys_up.name} for ${sys_up.cost_usd:,.0f}. "
                       f"Ships via {sys_up.delivery_method} ({sys_up.delivery_mass_kg:.0f} kg).",
        }

    def unlock_system(self, system_id: str) -> dict[str, Any] | None:
        """Mark a system upgrade as delivered and installed (called on delivery arrival)."""
        sys_up = next((s for s in self.systems_available if s.id == system_id), None)
        if sys_up is None:
            return None
        self.systems_unlocked[system_id] = True
        return {
            "system": sys_up,
            "message": f"SYSTEM ONLINE: {sys_up.name} -- {sys_up.description[:100]}",
        }

    def has_system(self, system_id: str) -> bool:
        """Check if a system upgrade has been unlocked."""
        return self.systems_unlocked.get(system_id, False)

    def summary(self) -> dict[str, Any]:
        return {
            "components_available": len(self.available),
            "components_purchased": dict(self.purchased),
            "components_installed": dict(self.installed),
            "component_upgrades": [{"id": u.id, "name": u.name, "year": u.available_after_year,
                                    "cost": u.cost_per_unit_usd}
                                   for u in self.available],
            "systems_available": [{"id": s.id, "name": s.name, "year": s.available_after_year,
                                   "cost": s.cost_usd, "delivery": s.delivery_method}
                                  for s in self.systems_available],
            "systems_unlocked": list(self.systems_unlocked.keys()),
        }
