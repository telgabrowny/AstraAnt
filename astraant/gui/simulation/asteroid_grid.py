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


class AsteroidGrid:
    """3D voxel grid representing the asteroid interior.

    Each voxel is 1m x 1m x 1m. Grid is centered on the asteroid center.
    Only the region near the mothership is initially generated (lazy loading).
    """

    def __init__(self, radius_m: float = 50, voxel_size_m: float = 1.0,
                 seed: int = 42) -> None:
        self.radius_m = radius_m
        self.voxel_size_m = voxel_size_m
        self.seed = seed
        self._rng = random.Random(seed)

        # Sparse storage: only generated/accessed voxels are stored
        self._voxels: dict[tuple[int, int, int], Voxel] = {}

        # Zone distribution (from composition model)
        self._zone_weights = [
            ("hydrated_matrix", 0.40),
            ("sulfide_pocket", 0.15),
            ("metal_grain", 0.05),
            ("organic_rich", 0.10),
            ("silicate_bulk", 0.25),
            ("void_rubble", 0.05),
        ]

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

        v = Voxel(x, y, z, zone_type=zone, richness=richness)
        self._voxels[key] = v
        return v

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

        return {
            "voxels_generated": len(self._voxels),
            "voxels_mined": self.total_mined,
            "voxels_revealed": self.total_revealed,
            "veins": len(self._veins),
            "zone_counts": zone_counts,
            "mined_zones": mined_zones,
        }
