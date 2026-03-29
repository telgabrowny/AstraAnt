"""Voxel grid model of the asteroid interior.

Think of it like Minecraft but with geology: each voxel has a composition
type (hydrated clay, sulfide pocket, metal grain, etc.) that determines
what you get when you mine it. The tunnel network carves through this grid.

The grid is generated once at mission start based on the asteroid's
composition profile, then remains fixed. Mining reveals what's in each cell.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Voxel:
    """A single voxel in the asteroid grid."""
    x: int
    y: int
    z: int
    zone_type: str = "silicate_bulk"  # Composition zone
    mined: bool = False               # Has this voxel been excavated?
    revealed: bool = False            # Has a taskmaster scanned this?
    richness: float = 1.0             # Multiplier for metal content
    hardness: float = 0.1             # 0.0 = loose dust, 0.3 = gravel, 0.6 = cobble, 0.9+ = boulder

    @property
    def material_class(self) -> str:
        """Human-readable material class based on hardness."""
        if self.hardness < 0.15:
            return "dust"
        if self.hardness < 0.35:
            return "regolith"
        if self.hardness < 0.55:
            return "gravel"
        if self.hardness < 0.75:
            return "cobble"
        if self.hardness < 0.90:
            return "boulder"
        return "megalith"

    @property
    def is_boulder(self) -> bool:
        """True if this voxel requires special handling (can't just scoop)."""
        return self.hardness >= 0.75


# Hardness profiles by asteroid type.
# mean/std for a normal distribution, clamped to [0, 1].
# Rubble piles (Bennu, Ryugu) = mostly loose material, occasional boulders.
# Monolithic (Eros) = more consolidated, harder digging overall.
ASTEROID_HARDNESS = {
    "rubble_pile": {  # Bennu, Ryugu, Didymos
        "base_mean": 0.20, "base_std": 0.15,
        "boulder_probability": 0.03,   # 3% of voxels are boulders
        "megalith_probability": 0.005,  # 0.5% are megaliths
    },
    "monolithic": {  # Eros, Itokawa (debatable)
        "base_mean": 0.45, "base_std": 0.20,
        "boulder_probability": 0.10,
        "megalith_probability": 0.02,
    },
    "metallic": {  # Psyche
        "base_mean": 0.55, "base_std": 0.15,
        "boulder_probability": 0.15,
        "megalith_probability": 0.03,
    },
    "mixed": {  # Default / unknown
        "base_mean": 0.30, "base_std": 0.18,
        "boulder_probability": 0.05,
        "megalith_probability": 0.01,
    },
}

# Per-zone hardness adjustments.  Veins of certain types tend to be
# harder or softer than the surrounding bulk.
ZONE_HARDNESS_MODIFIER = {
    "hydrated_matrix": -0.10,   # Clay-like, softer
    "sulfide_pocket": 0.05,     # Slightly harder crystalline
    "metal_grain": 0.15,        # Consolidated metal, harder
    "organic_rich": -0.15,      # Soft, tar-like organics
    "silicate_bulk": 0.0,       # Baseline
    "void_rubble": -0.05,       # Loose fill in voids
}


class AsteroidGrid:
    """3D voxel grid representing the asteroid interior.

    Each voxel is 1m x 1m x 1m. Grid is centered on the asteroid center.
    Only the region near the mothership is initially generated (lazy loading).
    """

    def __init__(self, radius_m: float = 50, voxel_size_m: float = 1.0,
                 seed: int = 42, asteroid_type: str = "rubble_pile") -> None:
        self.radius_m = radius_m
        self.voxel_size_m = voxel_size_m
        self.seed = seed
        self.asteroid_type = asteroid_type
        self._rng = random.Random(seed)
        self._hardness_profile = ASTEROID_HARDNESS.get(
            asteroid_type, ASTEROID_HARDNESS["mixed"])

        # Sparse storage: only generated/accessed voxels are stored
        self._voxels: dict[tuple[int, int, int], Voxel] = {}

        # Pre-generate some "veins" — clusters of valuable material
        self._veins: list[dict[str, Any]] = []
        self._generate_veins()

        # Stats
        self.total_mined = 0
        self.total_revealed = 0

    def _generate_veins(self) -> None:
        """Pre-generate mineral vein positions and sizes.

        Veins are ellipsoidal clusters of a specific zone type.
        This creates the spatial structure that taskmasters can discover
        and players can direct mining toward.
        """
        n_veins = int(self.radius_m * 0.5)  # ~25 veins in a 50m radius asteroid

        for _ in range(n_veins):
            # Random position inside the asteroid
            r = self._rng.uniform(3, self.radius_m * 0.8)
            theta = self._rng.uniform(0, math.pi * 2)
            phi = self._rng.uniform(0.3, math.pi - 0.3)
            cx = int(r * math.sin(phi) * math.cos(theta))
            cy = int(r * math.cos(phi))
            cz = int(r * math.sin(phi) * math.sin(theta))

            # Random vein type (weighted toward valuable types for gameplay)
            roll = self._rng.random()
            if roll < 0.30:
                zone = "sulfide_pocket"
                size = self._rng.uniform(2, 8)
            elif roll < 0.40:
                zone = "metal_grain"
                size = self._rng.uniform(1, 4)  # Small but very valuable
            elif roll < 0.55:
                zone = "hydrated_matrix"
                size = self._rng.uniform(3, 12)
            elif roll < 0.70:
                zone = "organic_rich"
                size = self._rng.uniform(2, 6)
            else:
                zone = "void_rubble"
                size = self._rng.uniform(1, 5)

            self._veins.append({
                "center": (cx, cy, cz),
                "radius": size,
                "zone": zone,
                "richness": self._rng.uniform(0.8, 3.0),
            })

    def get_voxel(self, x: int, y: int, z: int) -> Voxel:
        """Get or generate a voxel at the given coordinates."""
        key = (x, y, z)
        if key in self._voxels:
            return self._voxels[key]

        # Check if inside the asteroid
        dist = math.sqrt(x*x + y*y + z*z)
        if dist > self.radius_m:
            # Outside the asteroid — void
            v = Voxel(x, y, z, zone_type="void", mined=True)
            self._voxels[key] = v
            return v

        # Determine zone type based on vein proximity
        zone = "silicate_bulk"  # Default
        richness = 1.0

        for vein in self._veins:
            cx, cy, cz = vein["center"]
            vein_dist = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if vein_dist <= vein["radius"]:
                zone = vein["zone"]
                richness = vein["richness"]
                break  # First matching vein wins

        hardness = self._generate_hardness(zone, dist)
        v = Voxel(x, y, z, zone_type=zone, richness=richness, hardness=hardness)
        self._voxels[key] = v
        return v

    def _generate_hardness(self, zone_type: str, dist_from_center: float) -> float:
        """Generate hardness for a voxel based on asteroid type, zone, and depth.

        Material closer to the center is slightly more consolidated
        (billions of years of settling, even in microgravity).
        """
        hp = self._hardness_profile

        # Base hardness from asteroid type (normal distribution)
        base = self._rng.gauss(hp["base_mean"], hp["base_std"])

        # Zone modifier (metal veins are harder, organics are softer)
        base += ZONE_HARDNESS_MODIFIER.get(zone_type, 0.0)

        # Depth modifier: harder toward center (dist_from_center=0 = deepest)
        depth_fraction = 1.0 - min(1.0, dist_from_center / max(1, self.radius_m))
        base += depth_fraction * 0.10

        # Boulder/megalith roll (independent of base hardness)
        roll = self._rng.random()
        if roll < hp["megalith_probability"]:
            base = self._rng.uniform(0.90, 1.00)  # Megalith
        elif roll < hp["megalith_probability"] + hp["boulder_probability"]:
            base = self._rng.uniform(0.75, 0.92)  # Boulder

        return max(0.0, min(1.0, base))

    def mine_voxel(self, x: int, y: int, z: int) -> Voxel:
        """Mine a voxel — marks it as excavated and returns its contents."""
        v = self.get_voxel(x, y, z)
        if not v.mined:
            v.mined = True
            self.total_mined += 1
        return v

    def reveal_area(self, cx: int, cy: int, cz: int, radius: int = 3) -> list[Voxel]:
        """Taskmaster scans an area, revealing voxel compositions.

        Returns list of newly revealed voxels.
        """
        revealed = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if dx*dx + dy*dy + dz*dz <= radius * radius:
                        v = self.get_voxel(cx + dx, cy + dy, cz + dz)
                        if not v.revealed:
                            v.revealed = True
                            self.total_revealed += 1
                            revealed.append(v)
        return revealed

    def get_nearby_veins(self, x: int, y: int, z: int, scan_radius: float = 10) -> list[dict]:
        """What valuable veins are near this position? (Taskmaster sensor data)"""
        nearby = []
        for vein in self._veins:
            cx, cy, cz = vein["center"]
            dist = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if dist <= scan_radius + vein["radius"]:
                nearby.append({
                    "zone": vein["zone"],
                    "distance_m": round(dist - vein["radius"], 1),
                    "size_m": round(vein["radius"], 1),
                    "direction": (
                        round((cx - x) / max(1, dist), 2),
                        round((cy - y) / max(1, dist), 2),
                        round((cz - z) / max(1, dist), 2),
                    ),
                    "richness": vein["richness"],
                })
        return sorted(nearby, key=lambda v: v["distance_m"])

    def get_slice(self, y_level: int, x_range: tuple[int, int] = (-25, 25),
                  z_range: tuple[int, int] = (-25, 25)) -> list[list[str]]:
        """Get a 2D horizontal slice of the asteroid at a given Y level.

        Returns a grid of zone type characters for ASCII visualization.
        """
        zone_chars = {
            "hydrated_matrix": "~",
            "sulfide_pocket": "$",
            "metal_grain": "*",
            "organic_rich": "o",
            "silicate_bulk": ".",
            "void_rubble": " ",
            "void": " ",
        }
        grid = []
        for z in range(z_range[0], z_range[1] + 1):
            row = []
            for x in range(x_range[0], x_range[1] + 1):
                v = self.get_voxel(x, y_level, z)
                if v.mined:
                    row.append("#")  # Excavated
                elif v.revealed:
                    row.append(zone_chars.get(v.zone_type, "?"))
                else:
                    row.append("?")  # Unknown
            grid.append(row)
        return grid

    def summary(self) -> dict[str, Any]:
        """Grid statistics."""
        zone_counts: dict[str, int] = {}
        mined_zones: dict[str, int] = {}
        for v in self._voxels.values():
            zone_counts[v.zone_type] = zone_counts.get(v.zone_type, 0) + 1
            if v.mined:
                mined_zones[v.zone_type] = mined_zones.get(v.zone_type, 0) + 1

        # Hardness distribution
        material_counts: dict[str, int] = {}
        for v in self._voxels.values():
            mc = v.material_class
            material_counts[mc] = material_counts.get(mc, 0) + 1

        return {
            "voxels_generated": len(self._voxels),
            "voxels_mined": self.total_mined,
            "voxels_revealed": self.total_revealed,
            "veins": len(self._veins),
            "asteroid_type": self.asteroid_type,
            "zone_counts": zone_counts,
            "mined_zones": mined_zones,
            "material_counts": material_counts,
        }
