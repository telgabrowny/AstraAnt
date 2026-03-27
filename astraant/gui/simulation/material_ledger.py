"""Material ledger — tracks every kilogram through the entire system.

Nothing is created from thin air. If ants mine 1 tonne, only 1 tonne
flows through the pipeline. Dead ants are recycled as feedstock.

Material flow:
  Mine face -> raw regolith buffer -> thermal sorter -> crusher -> bioreactor
  -> precipitation -> metal stockpile -> manufacturing / cargo pods
  Waste slurry -> tunnel walls (plasterer ants) or pod shells
  Water -> bioreactor medium + electrolysis + fill gas
  Dead ants -> salvage (parts) + recycle (metal/plastic to furnace)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MaterialLedger:
    """Tracks all material flows in the simulation. Every kg accounted for."""

    # === RAW MATERIAL BUFFERS (kg) ===
    raw_regolith_buffer_kg: float = 0.0        # Mined, waiting for thermal sort
    dried_regolith_buffer_kg: float = 0.0       # After thermal sort, waiting for crusher
    crushed_buffer_kg: float = 0.0              # Crushed, waiting for bioreactor
    bioreactor_slurry_kg: float = 0.0           # In the bioreactor vats

    # === EXTRACTED PRODUCTS (kg) ===
    water_tank_kg: float = 0.0                  # Recovered water
    iron_stockpile_kg: float = 0.0
    nickel_stockpile_kg: float = 0.0
    copper_stockpile_kg: float = 0.0
    cobalt_stockpile_kg: float = 0.0
    platinum_stockpile_mg: float = 0.0          # Milligrams (very small amounts)
    palladium_stockpile_mg: float = 0.0
    rare_earths_stockpile_g: float = 0.0        # Grams

    # === WASTE / CONSTRUCTION MATERIALS (kg) ===
    waste_paste_stockpile_kg: float = 0.0       # Bioreactor waste for wall sealing / pod shells
    co2_captured_kg: float = 0.0                # For algae photobioreactor
    organic_extract_kg: float = 0.0             # For supplementary carbon

    # === MANUFACTURED ITEMS ===
    sintered_parts_count: int = 0               # Metal parts ready for assembly
    pods_built: int = 0
    ants_built: int = 0

    # === CONSUMED (kg) - material that's been used up ===
    paste_applied_to_walls_kg: float = 0.0
    paste_used_for_pods_kg: float = 0.0
    iron_used_for_parts_kg: float = 0.0
    water_consumed_kg: float = 0.0              # Electrolysis, leaks, etc.
    metal_shipped_kg: float = 0.0               # Loaded into cargo pods and launched

    # === RECYCLED FROM DEAD ANTS ===
    dead_ants_recovered: int = 0
    salvaged_servos: int = 0                    # Working servos pulled from dead ants
    salvaged_mcus: int = 0                      # Working MCUs
    recycled_metal_kg: float = 0.0              # Chassis melted down
    recycled_plastic_kg: float = 0.0            # PETG/PHB from chassis

    # === THROUGHPUT LIMITS (kg/day) ===
    thermal_sorter_rate_kg_per_day: float = 960  # 40 kg/hr × 24
    crusher_rate_kg_per_day: float = 120         # 5 kg/hr × 24
    bioreactor_intake_kg_per_day: float = 120    # Matches crusher
    sintering_parts_per_day: float = 12          # Furnace bottleneck

    # === CUMULATIVE TOTALS ===
    total_mined_kg: float = 0.0
    total_processed_kg: float = 0.0
    total_extracted_metal_kg: float = 0.0
    total_water_recovered_kg: float = 0.0

    def mine_regolith(self, kg: float) -> float:
        """Worker dumps regolith at the raw buffer. Returns amount accepted."""
        self.raw_regolith_buffer_kg += kg
        self.total_mined_kg += kg
        return kg

    def process_thermal_sort(self, dt_days: float, water_fraction: float = 0.08,
                              co2_fraction: float = 0.005) -> dict[str, float]:
        """Thermal sorter processes raw regolith -> dried + water + CO2."""
        available = self.raw_regolith_buffer_kg
        can_process = min(available, self.thermal_sorter_rate_kg_per_day * dt_days)
        if can_process <= 0:
            return {}

        self.raw_regolith_buffer_kg -= can_process
        water = can_process * water_fraction * 0.90  # 90% recovery
        co2 = can_process * co2_fraction
        dried = can_process - water - co2

        self.water_tank_kg += water
        self.total_water_recovered_kg += water
        self.co2_captured_kg += co2
        self.dried_regolith_buffer_kg += dried

        return {"processed_kg": can_process, "water_kg": water, "co2_kg": co2, "dried_kg": dried}

    def process_crusher(self, dt_days: float) -> float:
        """Crusher grinds dried regolith -> crushed (ready for bioreactor)."""
        available = self.dried_regolith_buffer_kg
        can_crush = min(available, self.crusher_rate_kg_per_day * dt_days)
        if can_crush <= 0:
            return 0

        self.dried_regolith_buffer_kg -= can_crush
        self.crushed_buffer_kg += can_crush
        return can_crush

    def feed_bioreactor(self, dt_days: float) -> float:
        """Move crushed material into bioreactor vats."""
        available = self.crushed_buffer_kg
        can_feed = min(available, self.bioreactor_intake_kg_per_day * dt_days)
        if can_feed <= 0:
            return 0

        self.crushed_buffer_kg -= can_feed
        self.bioreactor_slurry_kg += can_feed
        self.total_processed_kg += can_feed
        return can_feed

    def extract_metals(self, extraction_results: dict[str, float]) -> None:
        """Record metal extraction from bioreactor processing.

        extraction_results: metal_name -> kg extracted
        """
        for metal, kg in extraction_results.items():
            if metal == "iron":
                self.iron_stockpile_kg += kg
            elif metal == "nickel":
                self.nickel_stockpile_kg += kg
            elif metal == "copper":
                self.copper_stockpile_kg += kg
            elif metal == "cobalt":
                self.cobalt_stockpile_kg += kg
            elif metal == "platinum":
                self.platinum_stockpile_mg += kg * 1000  # Convert to mg
            elif metal == "palladium":
                self.palladium_stockpile_mg += kg * 1000
            elif metal == "rare_earths":
                self.rare_earths_stockpile_g += kg * 1000

            self.total_extracted_metal_kg += kg

        # Remaining slurry becomes waste paste
        waste = self.bioreactor_slurry_kg * 0.1  # ~10% becomes paste per cycle
        self.bioreactor_slurry_kg -= waste
        self.waste_paste_stockpile_kg += waste

    def use_paste_for_walls(self, kg: float) -> float:
        """Plasterer ant uses waste paste for tunnel sealing."""
        used = min(kg, self.waste_paste_stockpile_kg)
        self.waste_paste_stockpile_kg -= used
        self.paste_applied_to_walls_kg += used
        return used

    def use_paste_for_pod(self) -> bool:
        """Build a ferrocement pod shell from waste paste."""
        needed = 0.1  # 100g paste per pod
        if self.waste_paste_stockpile_kg < needed:
            return False
        self.waste_paste_stockpile_kg -= needed
        self.paste_used_for_pods_kg += needed
        self.pods_built += 1
        return True

    def use_iron_for_part(self) -> bool:
        """Sinter one metal part from iron stockpile."""
        needed = 0.025  # 25g iron per part
        if self.iron_stockpile_kg < needed:
            return False
        self.iron_stockpile_kg -= needed
        self.iron_used_for_parts_kg += needed
        self.sintered_parts_count += 1
        return True

    def ship_metal(self, kg: float) -> float:
        """Load metal into cargo pod for shipment."""
        # Ship from the most valuable stockpile first
        shipped = 0
        for attr in ['copper_stockpile_kg', 'nickel_stockpile_kg', 'cobalt_stockpile_kg',
                      'iron_stockpile_kg']:
            available = getattr(self, attr)
            take = min(kg - shipped, available)
            if take > 0:
                setattr(self, attr, available - take)
                shipped += take
            if shipped >= kg:
                break
        self.metal_shipped_kg += shipped
        return shipped

    def recycle_dead_ant(self, ant_mass_g: float,
                         component_health: Any = None) -> dict:
        """Process a dead ant: TEST each part individually, salvage what works.

        If component_health is provided (from failure_model.ComponentHealth),
        uses actual per-component degradation to determine salvage.
        Otherwise uses statistical estimates.

        Returns what was recovered.
        """
        self.dead_ants_recovered += 1
        recovered = {"servos": 0, "mcus": 0, "sensors": 0, "batteries": 0,
                      "radios": 0, "metal_kg": 0, "plastic_kg": 0,
                      "test_results": []}

        if component_health is not None:
            # Per-component testing (realistic)
            salvage = component_health.get_salvageable_parts()
            recovered["servos"] = salvage["working_leg_servos"] + salvage["working_mandible_servos"]
            recovered["mcus"] = 1 if salvage["mcu_ok"] else 0
            recovered["sensors"] = 1 if salvage["sensor_ok"] else 0
            recovered["batteries"] = 1 if salvage["battery_usable"] else 0
            recovered["radios"] = 1 if salvage["radio_ok"] else 0
            recovered["metal_kg"] = salvage["recyclable_metal_g"] / 1000
            recovered["plastic_kg"] = salvage["chassis_plastic_g"] / 1000

            # Generate test report
            recovered["test_results"] = [
                f"Leg servos: {salvage['working_leg_servos']}/6 passed movement test",
                f"Mandible servos: {salvage['working_mandible_servos']}/2 passed",
                f"MCU: {'PASS (heartbeat OK)' if salvage['mcu_ok'] else 'FAIL (no response)'}",
                f"Radio: {'PASS (handshake OK)' if salvage['radio_ok'] else 'FAIL'}",
                f"Sensor: {'PASS (reading valid)' if salvage['sensor_ok'] else 'FAIL (no reading)'}",
                f"Battery: {'PASS (holds charge)' if salvage['battery_usable'] else 'FAIL (depleted)'}",
            ]
        else:
            # Statistical fallback (old behavior)
            import random
            for _ in range(8):
                if random.random() < 0.7:  # 70% of servos typically fine
                    recovered["servos"] += 1
            recovered["mcus"] = 1 if random.random() < 0.9 else 0
            recovered["sensors"] = 1 if random.random() < 0.8 else 0
            recovered["radios"] = 1 if random.random() < 0.95 else 0
            recovered["batteries"] = 1 if random.random() < 0.3 else 0  # Often the thing that failed
            recovered["metal_kg"] = ant_mass_g * 0.4 / 1000
            recovered["plastic_kg"] = ant_mass_g * 0.3 / 1000

        self.salvaged_servos += recovered["servos"]
        self.salvaged_mcus += recovered["mcus"]
        self.recycled_metal_kg += recovered["metal_kg"]
        self.iron_stockpile_kg += recovered["metal_kg"]
        self.recycled_plastic_kg += recovered["plastic_kg"]

        return recovered

    @property
    def total_in_system_kg(self) -> float:
        """Total material currently in all buffers + stockpiles."""
        return (self.raw_regolith_buffer_kg + self.dried_regolith_buffer_kg +
                self.crushed_buffer_kg + self.bioreactor_slurry_kg +
                self.water_tank_kg + self.iron_stockpile_kg +
                self.nickel_stockpile_kg + self.copper_stockpile_kg +
                self.cobalt_stockpile_kg + self.waste_paste_stockpile_kg)

    @property
    def buffer_status(self) -> dict[str, float]:
        """Percent full for each buffer stage."""
        return {
            "raw": self.raw_regolith_buffer_kg,
            "dried": self.dried_regolith_buffer_kg,
            "crushed": self.crushed_buffer_kg,
            "bioreactor": self.bioreactor_slurry_kg,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "total_mined_kg": round(self.total_mined_kg, 1),
            "total_processed_kg": round(self.total_processed_kg, 1),
            "total_water_kg": round(self.total_water_recovered_kg, 1),
            "total_metal_kg": round(self.total_extracted_metal_kg, 3),
            "buffers": {
                "raw_regolith": round(self.raw_regolith_buffer_kg, 1),
                "dried": round(self.dried_regolith_buffer_kg, 1),
                "crushed": round(self.crushed_buffer_kg, 1),
                "bioreactor": round(self.bioreactor_slurry_kg, 1),
            },
            "stockpiles": {
                "water": round(self.water_tank_kg, 1),
                "iron": round(self.iron_stockpile_kg, 3),
                "nickel": round(self.nickel_stockpile_kg, 3),
                "copper": round(self.copper_stockpile_kg, 3),
                "waste_paste": round(self.waste_paste_stockpile_kg, 1),
            },
            "recycled": {
                "dead_ants": self.dead_ants_recovered,
                "salvaged_servos": self.salvaged_servos,
                "salvaged_mcus": self.salvaged_mcus,
                "recycled_metal_kg": round(self.recycled_metal_kg, 3),
            },
            "shipped": {
                "metal_kg": round(self.metal_shipped_kg, 3),
                "pods": self.pods_built,
                "ants_built": self.ants_built,
            },
        }
