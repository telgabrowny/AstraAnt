"""Anomaly detection system -- flags findings that don't match expected models.

Real anomalies (scientific mode):
  - Spectral readings that don't match ANY known mineral signature
  - Void cavities behind the rock face (lidar distance jumps)
  - Density anomalies (hopper weight vs expected for regolith type)
  - Thermal hotspots or coldspots
  - Unexpected crystalline structures in the ore
  - Radioactive mineral concentrations (dosimeter spikes)
  - Organic molecule complexity exceeding expected for the asteroid type

Fanciful anomalies (game mode -- toggle at mission start):
  - Ancient impact debris from another solar system
  - Perfectly geometric mineral formations
  - Inexplicable void with smooth walls
  - Material with impossible isotope ratios
  - "That's not a rock..."

Detection: each sensor reading compared to expected range.
If ANY reading is >3 sigma from expected, flag as ANOMALY.
Taskmaster escalates to mothership. Pi4 adds to Earth telemetry
with PRIORITY flag. Human decides what to do.
"""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnomalyEvent:
    """A detected anomaly."""
    id: int
    sim_time: float
    location: tuple[int, int, int]    # Voxel grid coordinates
    anomaly_type: str
    severity: str                      # "curiosity", "significant", "extraordinary"
    sensor_data: dict[str, Any]
    description: str
    scientific_explanation: str
    fanciful_explanation: str          # Only shown if fanciful mode is on
    action_required: str
    resolved: bool = False


# Sensor expected ranges (for baseline comparison)
EXPECTED_RANGES = {
    "spectral_channels": {
        # AS7341 11-channel spectral sensor expected readings per zone
        "silicate": [0.2, 0.4, 0.6, 0.8, 0.9, 0.7, 0.5, 0.3, 0.2, 0.1, 0.05],
        "sulfide": [0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.8, 0.6, 0.4, 0.2, 0.1],
        "metal": [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.8, 0.9, 0.95, 0.9, 0.85],
        "organic": [0.4, 0.5, 0.6, 0.4, 0.3, 0.2, 0.15, 0.1, 0.08, 0.05, 0.03],
    },
    "density_kg_m3": {"min": 800, "max": 3500, "typical": 1190},
    "temperature_c": {"min": -20, "max": 60, "typical": 20},
    "proximity_mm": {"min": 0, "max": 2000},
}

# Scientific anomaly templates
SCIENTIFIC_ANOMALIES = [
    {
        "type": "spectral_unknown",
        "severity": "significant",
        "probability_per_1000_voxels": 2,
        "description": "Spectral reading doesn't match any known mineral signature in the database. "
                       "11-channel profile has peaks at unusual wavelengths.",
        "scientific_explanation": "Possible exotic mineral phase formed under unique pressure/temperature "
                                  "conditions during the asteroid's parent body differentiation. "
                                  "Could be a new mineral species not yet cataloged on Earth.",
        "fanciful_explanation": "The spectral signature is... organized. Almost like a barcode. "
                                "Probably just a coincidence in the crystal structure.",
        "action_required": "Collect sample. Seal in dedicated container. Flag for Earth analysis.",
        "sensor": "spectral",
    },
    {
        "type": "void_cavity",
        "severity": "significant",
        "probability_per_1000_voxels": 5,
        "description": "VL53L0x reads sudden distance increase -- open cavity behind the rock face. "
                       "Estimated void size: 0.5-3m diameter.",
        "scientific_explanation": "Primordial gas pocket trapped during asteroid formation, or cavity "
                                  "formed by ice sublimation billions of years ago. Common in rubble "
                                  "pile asteroids. May contain pristine primordial material.",
        "fanciful_explanation": "The cavity walls are unusually smooth. Almost polished. "
                                "And there's something reflecting the lidar at the far end...",
        "action_required": "Stop drilling. Map cavity with lidar sweeps. Report to Earth before entering.",
        "sensor": "proximity",
    },
    {
        "type": "density_anomaly",
        "severity": "curiosity",
        "probability_per_1000_voxels": 10,
        "description": "Hopper mass reading doesn't match expected density for the zone type. "
                       "Material is significantly heavier or lighter than regolith baseline.",
        "scientific_explanation": "Concentrated metal inclusion (if heavy) or high-porosity material (if light). "
                                  "Metal inclusions could be fragments from ancient collisions with "
                                  "iron-nickel asteroids.",
        "fanciful_explanation": "The heavy chunk has an unusually regular shape. "
                                "Almost... manufactured. Probably just a nicely weathered rock.",
        "action_required": "Set aside in anomaly sample bin. Continue mining. Low priority.",
        "sensor": "hopper_weight",
    },
    {
        "type": "thermal_hotspot",
        "severity": "significant",
        "probability_per_1000_voxels": 1,
        "description": "DS18B20 reads 15C+ above ambient. Localized heat source in the rock.",
        "scientific_explanation": "Radioactive mineral concentration (thorium, uranium, or potassium-40). "
                                  "Natural heating from decay. Safe at this level but worth documenting. "
                                  "Could indicate a rare earth element deposit.",
        "fanciful_explanation": "The heat is coming from behind a thin wall of rock. "
                                "The temperature profile suggests something actively generating heat. "
                                "Radioactive decay doesn't usually look this... focused.",
        "action_required": "Mark location. Continue with caution. Check dosimeter readings.",
        "sensor": "temperature",
    },
    {
        "type": "crystalline_structure",
        "severity": "curiosity",
        "probability_per_1000_voxels": 3,
        "description": "Drill encounters sudden resistance change -- hard crystalline layer. "
                       "Spectral confirms non-standard mineral structure.",
        "scientific_explanation": "Mineral vein crystallized from hydrothermal fluids in the parent body "
                                  "before it was disrupted. Possibly gem-quality olivine (peridot) or "
                                  "pyroxene crystals. Scientifically interesting, low commercial value.",
        "fanciful_explanation": "The crystal structure is hexagonal. Perfectly hexagonal. "
                                "Each face is exactly 12.7mm. Natural crystals aren't this precise.",
        "action_required": "Extract sample carefully. Photo with camera module. Flag for mineralogy.",
        "sensor": "drill_resistance",
    },
    {
        "type": "organic_complexity",
        "severity": "extraordinary",
        "probability_per_1000_voxels": 0.5,
        "description": "Spectral analysis shows organic molecular bands far more complex than expected. "
                       "C-type asteroids have organics, but not THIS complex.",
        "scientific_explanation": "Complex prebiotic chemistry -- amino acid chains longer than expected. "
                                  "Could advance our understanding of how life's building blocks formed "
                                  "in the early solar system. Nobel Prize material for the analysis lab.",
        "fanciful_explanation": "The molecular structure has repeating patterns. "
                                "Like a polymer. A very specific polymer. "
                                "Almost like it was... encoded.",
        "action_required": "PRIORITY SAMPLE. Seal in nitrogen atmosphere immediately. "
                           "Do NOT process through bioreactor. This goes to Earth.",
        "sensor": "spectral",
    },
    {
        "type": "isotope_anomaly",
        "severity": "extraordinary",
        "probability_per_1000_voxels": 0.1,
        "description": "Material from this voxel has spectral characteristics inconsistent with "
                       "solar system formation models. Possible presolar grain concentration.",
        "scientific_explanation": "Presolar grains -- tiny crystals formed in other stars before our "
                                  "solar system existed. Silicon carbide or diamond nanocrystals from "
                                  "supernovae. Extremely rare and scientifically priceless.",
        "fanciful_explanation": "The isotope ratios don't match ANY star in our cataloged neighborhood. "
                                "This material came from somewhere very, very far away. "
                                "And very, very long ago. Before our Sun existed.",
        "action_required": "HIGHEST PRIORITY. Isolate. Do not contaminate. "
                           "Earth team must analyze before ANY further mining in this area.",
        "sensor": "spectral",
    },
]

# Fanciful-only anomalies (only appear if fanciful mode is enabled)
FANCIFUL_ANOMALIES = [
    {
        "type": "geometric_void",
        "severity": "extraordinary",
        "probability_per_1000_voxels": 0.05,
        "description": "Void cavity with perfectly flat walls meeting at exact 90-degree angles. "
                       "Interior dimensions: 2.1m x 2.1m x 2.1m.",
        "scientific_explanation": "Extraordinary coincidence in fracture geometry. "
                                  "Cubic cleavage planes in a large crystal that later dissolved.",
        "fanciful_explanation": "It's a room. A perfectly cubic room inside an asteroid. "
                                "The walls are smooth. There are grooves in the floor. "
                                "Something was here.",
        "action_required": "FULL STOP. Do not enter. Image with every available sensor. "
                           "Immediate priority Earth communication.",
    },
    {
        "type": "signal",
        "severity": "extraordinary",
        "probability_per_1000_voxels": 0.01,
        "description": "Taskmaster's nRF24L01 picks up periodic electromagnetic emission "
                       "from a specific location in the rock. Not random noise -- structured.",
        "scientific_explanation": "Piezoelectric crystal under tidal stress from asteroid rotation. "
                                  "Emits weak EM pulses at the rotation frequency. Natural phenomenon.",
        "fanciful_explanation": "The signal repeats every 4.297 seconds. "
                                "That's Bennu's rotation period to 4 significant figures. "
                                "It's been transmitting since before we arrived.",
        "action_required": "Record signal. Analyze frequency, modulation, periodicity. "
                           "Do not transmit near the source. Earth team decides next steps.",
    },
]


class AnomalyDetector:
    """Detects and catalogs anomalies during mining operations."""

    def __init__(self, fanciful_mode: bool = False, seed: int = 42):
        self.fanciful_mode = fanciful_mode
        self._rng = random.Random(seed)
        self.anomalies: list[AnomalyEvent] = []
        self._next_id = 0
        self._voxels_checked = 0

    def check_voxel(self, x: int, y: int, z: int,
                     zone_type: str, sim_time: float) -> AnomalyEvent | None:
        """Check a mined voxel for anomalies.

        Called each time a voxel is excavated. Returns an AnomalyEvent
        if something unusual is found, or None for normal material.
        """
        self._voxels_checked += 1

        # Check each anomaly template against probability
        templates = SCIENTIFIC_ANOMALIES[:]
        if self.fanciful_mode:
            templates.extend(FANCIFUL_ANOMALIES)

        for template in templates:
            prob = template["probability_per_1000_voxels"] / 1000
            if self._rng.random() < prob:
                event = AnomalyEvent(
                    id=self._next_id,
                    sim_time=sim_time,
                    location=(x, y, z),
                    anomaly_type=template["type"],
                    severity=template["severity"],
                    sensor_data={
                        "sensor": template.get("sensor", "unknown"),
                        "zone_at_location": zone_type,
                        "depth_m": abs(y),
                    },
                    description=template["description"],
                    scientific_explanation=template["scientific_explanation"],
                    fanciful_explanation=template.get("fanciful_explanation", ""),
                    action_required=template["action_required"],
                )
                self._next_id += 1
                self.anomalies.append(event)
                return event

        return None

    def summary(self) -> dict[str, Any]:
        by_severity = {}
        for a in self.anomalies:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        return {
            "total_anomalies": len(self.anomalies),
            "voxels_checked": self._voxels_checked,
            "by_severity": by_severity,
            "fanciful_mode": self.fanciful_mode,
            "unresolved": sum(1 for a in self.anomalies if not a.resolved),
        }
