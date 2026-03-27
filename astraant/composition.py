"""Asteroid composition variability model.

Real asteroids aren't uniform. Composition varies by location, depth,
and grain size. This module models that variability so the simulator
produces realistic extraction results -- sometimes you hit a rich vein,
sometimes you get nothing but silicates.

Based on OSIRIS-REx and Hayabusa2 sample return data showing significant
spatial variation in composition across collection sites.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog


@dataclass
class RegolithSample:
    """A single batch of regolith with its specific composition."""
    mass_kg: float
    metals_ppm: dict[str, float]     # Actual metals in THIS batch
    water_pct: float                  # Water content of THIS batch
    zone: str                         # Which zone it came from
    depth_m: float                    # How deep it was mined


@dataclass
class CompositionZone:
    """A zone within the asteroid with distinct composition."""
    name: str
    fraction: float                   # What fraction of the asteroid this zone represents
    metals_multiplier: dict[str, float]  # Multiplier vs bulk average
    water_multiplier: float
    description: str


# Typical zone distribution for a C-type rubble pile asteroid
# Based on Bennu/Ryugu sample analysis showing spatial heterogeneity
C_TYPE_ZONES = [
    CompositionZone(
        name="hydrated_matrix",
        fraction=0.40,
        metals_multiplier={"iron": 0.8, "nickel": 0.9, "copper": 0.7, "cobalt": 0.8,
                           "platinum": 0.5, "palladium": 0.5, "iridium": 0.3,
                           "rare_earths_total": 1.2},
        water_multiplier=1.5,         # Extra water in hydrated clay zones
        description="Hydrated clay-rich matrix. High water, moderate metals, elevated REE."
    ),
    CompositionZone(
        name="sulfide_pocket",
        fraction=0.15,
        metals_multiplier={"iron": 2.5, "nickel": 3.0, "copper": 5.0, "cobalt": 4.0,
                           "platinum": 1.5, "palladium": 1.5, "iridium": 1.0,
                           "rare_earths_total": 0.3},
        water_multiplier=0.3,
        description="Sulfide mineral concentration. Rich in base metals, low water."
    ),
    CompositionZone(
        name="metal_grain",
        fraction=0.05,
        metals_multiplier={"iron": 8.0, "nickel": 6.0, "copper": 2.0, "cobalt": 3.0,
                           "platinum": 10.0, "palladium": 8.0, "iridium": 5.0,
                           "rare_earths_total": 0.1},
        water_multiplier=0.0,
        description="Iron-nickel metal grains. Jackpot for PGMs. Rare but very valuable."
    ),
    CompositionZone(
        name="organic_rich",
        fraction=0.10,
        metals_multiplier={"iron": 0.3, "nickel": 0.4, "copper": 0.5, "cobalt": 0.3,
                           "platinum": 0.2, "palladium": 0.2, "iridium": 0.1,
                           "rare_earths_total": 0.5},
        water_multiplier=1.2,
        description="Organic carbon-rich zones. Low metals but good for CO2/sugar production."
    ),
    CompositionZone(
        name="silicate_bulk",
        fraction=0.25,
        metals_multiplier={"iron": 0.6, "nickel": 0.5, "copper": 0.3, "cobalt": 0.4,
                           "platinum": 0.3, "palladium": 0.2, "iridium": 0.2,
                           "rare_earths_total": 1.5},
        water_multiplier=0.5,
        description="Bulk silicate material. Low value metals, elevated REE in silicate matrix."
    ),
    CompositionZone(
        name="void_rubble",
        fraction=0.05,
        metals_multiplier={"iron": 0.1, "nickel": 0.1, "copper": 0.1, "cobalt": 0.1,
                           "platinum": 0.05, "palladium": 0.05, "iridium": 0.05,
                           "rare_earths_total": 0.1},
        water_multiplier=0.1,
        description="Loosely packed rubble with high void fraction. Almost nothing useful."
    ),
]

# S-type asteroids have different zone distribution
S_TYPE_ZONES = [
    CompositionZone(
        name="olivine_pyroxene",
        fraction=0.50,
        metals_multiplier={"iron": 0.8, "nickel": 0.6, "copper": 0.3, "cobalt": 0.5,
                           "platinum": 0.3, "palladium": 0.2, "iridium": 0.1,
                           "rare_earths_total": 0.5},
        water_multiplier=0.0,
        description="Silicate minerals. The bulk of S-type asteroids. Low metal value."
    ),
    CompositionZone(
        name="metal_inclusion",
        fraction=0.10,
        metals_multiplier={"iron": 5.0, "nickel": 4.0, "copper": 1.5, "cobalt": 2.0,
                           "platinum": 6.0, "palladium": 5.0, "iridium": 3.0,
                           "rare_earths_total": 0.1},
        water_multiplier=0.0,
        description="Metal inclusions in silicate matrix. High value but dispersed."
    ),
    CompositionZone(
        name="regolith_fines",
        fraction=0.30,
        metals_multiplier={"iron": 1.2, "nickel": 1.0, "copper": 0.8, "cobalt": 0.8,
                           "platinum": 0.8, "palladium": 0.7, "iridium": 0.5,
                           "rare_earths_total": 0.8},
        water_multiplier=0.05,       # Trace solar wind implanted hydrogen
        description="Fine surface regolith. Average composition, easy to process."
    ),
    CompositionZone(
        name="feldspar",
        fraction=0.10,
        metals_multiplier={"iron": 0.2, "nickel": 0.1, "copper": 0.1, "cobalt": 0.1,
                           "platinum": 0.1, "palladium": 0.1, "iridium": 0.05,
                           "rare_earths_total": 2.0},
        water_multiplier=0.0,
        description="Feldspar minerals. Only value is elevated REE content."
    ),
]


def get_zones_for_asteroid(asteroid_id: str, catalog: Catalog | None = None) -> list[CompositionZone]:
    """Get the composition zone model for a specific asteroid."""
    if catalog is None:
        catalog = Catalog()
    asteroid = catalog.get_asteroid(asteroid_id)
    if asteroid is None:
        return C_TYPE_ZONES  # Default

    spec_class = asteroid.get("physical", {}).get("spectral_class", "C")
    if spec_class in ("S", "Sq", "L"):
        return S_TYPE_ZONES
    return C_TYPE_ZONES


def sample_regolith(bulk_metals_ppm: dict[str, float], bulk_water_pct: float,
                    mass_kg: float, zones: list[CompositionZone],
                    depth_m: float = 1.0,
                    variability: float = 1.0) -> RegolithSample:
    """Sample a batch of regolith with realistic composition variability.

    Args:
        bulk_metals_ppm: Average metal content from asteroid catalog
        bulk_water_pct: Average water percentage
        mass_kg: How much regolith in this batch
        zones: Composition zone model for this asteroid
        depth_m: Mining depth (affects weathering/composition)
        variability: 0.0 = uniform (no variation), 1.0 = full model, >1.0 = exaggerated
    """
    # Pick a zone based on weighted random selection
    roll = random.random()
    cumulative = 0.0
    selected_zone = zones[0]
    for zone in zones:
        cumulative += zone.fraction
        if roll < cumulative:
            selected_zone = zone
            break

    # Apply zone multipliers to bulk composition
    sample_metals = {}
    for metal, ppm in bulk_metals_ppm.items():
        multiplier = selected_zone.metals_multiplier.get(metal, 1.0)
        # Add random scatter within the zone (gaussian, +/- 30%)
        scatter = 1.0 + random.gauss(0, 0.15 * variability)
        scatter = max(0.1, scatter)  # Never go below 10% of expected
        sample_metals[metal] = ppm * multiplier * scatter

    # Water content
    water_scatter = 1.0 + random.gauss(0, 0.2 * variability)
    water_scatter = max(0.0, water_scatter)
    sample_water = bulk_water_pct * selected_zone.water_multiplier * water_scatter

    # Depth effect: deeper = less space weathering, slightly different composition
    if depth_m > 5:
        # Below ~5m, pristine material (not space-weathered)
        for metal in sample_metals:
            sample_metals[metal] *= 1.05  # Slightly richer than surface
        sample_water *= 1.10  # More water preserved at depth

    return RegolithSample(
        mass_kg=mass_kg,
        metals_ppm=sample_metals,
        water_pct=sample_water,
        zone=selected_zone.name,
        depth_m=depth_m,
    )


def simulate_mining_variability(asteroid_id: str, n_batches: int = 100,
                                 batch_kg: float = 10.0,
                                 catalog: Catalog | None = None) -> dict[str, Any]:
    """Simulate mining multiple batches to show composition variability.

    Returns statistics on what you'd actually encounter mining this asteroid.
    """
    if catalog is None:
        catalog = Catalog()

    asteroid = catalog.get_asteroid(asteroid_id)
    if asteroid is None:
        return {"error": f"Asteroid {asteroid_id} not found"}

    comp = asteroid.get("composition", {})
    bulk_metals = comp.get("metals_ppm", {})
    bulk_water = comp.get("bulk", {}).get("water_hydrated", 0)
    zones = get_zones_for_asteroid(asteroid_id, catalog)

    batches = []
    zone_counts: dict[str, int] = {}
    metal_totals: dict[str, list[float]] = {}

    for i in range(n_batches):
        depth = 1.0 + (i / n_batches) * 20  # Mining deeper over time
        sample = sample_regolith(bulk_metals, bulk_water, batch_kg, zones, depth)
        batches.append(sample)

        zone_counts[sample.zone] = zone_counts.get(sample.zone, 0) + 1
        for metal, ppm in sample.metals_ppm.items():
            if metal not in metal_totals:
                metal_totals[metal] = []
            metal_totals[metal].append(ppm)

    # Statistics
    stats = {}
    for metal, values in metal_totals.items():
        avg = sum(values) / len(values)
        min_v = min(values)
        max_v = max(values)
        std = (sum((v - avg)**2 for v in values) / len(values)) ** 0.5
        stats[metal] = {
            "avg_ppm": round(avg, 1),
            "min_ppm": round(min_v, 1),
            "max_ppm": round(max_v, 1),
            "std_ppm": round(std, 1),
            "cv_pct": round(100 * std / avg, 1) if avg > 0 else 0,
            "bulk_ppm": bulk_metals.get(metal, 0),
        }

    return {
        "asteroid": asteroid.get("name", asteroid_id),
        "n_batches": n_batches,
        "batch_kg": batch_kg,
        "zone_distribution": zone_counts,
        "metal_stats": stats,
    }


def format_variability_report(result: dict[str, Any]) -> str:
    """Format mining variability analysis."""
    lines = []
    lines.append("=" * 75)
    lines.append(f"COMPOSITION VARIABILITY -- {result['asteroid']}")
    lines.append(f"{result['n_batches']} batches of {result['batch_kg']} kg each")
    lines.append("=" * 75)

    lines.append(f"\n--- ZONE DISTRIBUTION ---")
    for zone, count in sorted(result["zone_distribution"].items(), key=lambda x: -x[1]):
        pct = count / result["n_batches"] * 100
        bar = "#" * int(pct / 2)
        lines.append(f"  {zone:20s} {count:>4d} ({pct:4.1f}%) {bar}")

    lines.append(f"\n--- METAL VARIABILITY ---")
    lines.append(f"  {'Metal':<20s} {'Bulk(ppm)':>10s} {'Avg':>10s} {'Min':>10s} "
                 f"{'Max':>10s} {'StdDev':>10s} {'CV%':>6s}")
    lines.append(f"  {'-'*70}")

    for metal, s in sorted(result["metal_stats"].items(),
                           key=lambda x: -x[1]["bulk_ppm"]):
        lines.append(f"  {metal:<20s} {s['bulk_ppm']:>10.0f} {s['avg_ppm']:>10.1f} "
                     f"{s['min_ppm']:>10.1f} {s['max_ppm']:>10.1f} "
                     f"{s['std_ppm']:>10.1f} {s['cv_pct']:>5.1f}%")

    lines.append(f"\nCV% = coefficient of variation (higher = more variable)")
    lines.append(f"Metal grains are rare (5% of volume) but when hit, PGMs spike 5-10x")
    lines.append("=" * 75)
    return "\n".join(lines)
