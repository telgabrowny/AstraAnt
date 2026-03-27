"""Tunnel network state — branching topology with directed digging.

The tunnel network is a graph: nodes are junctions, edges are tunnel segments.
Each segment has a direction, composition zone, and can be extended or branched.
Multiple mothership sites can grow toward a common meeting point.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class Vec3:
    """Simple 3D position for tunnel node locations."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: Vec3) -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 +
                         (self.z - other.z)**2)

    def direction_to(self, other: Vec3) -> Vec3:
        d = self.distance_to(other)
        if d < 0.01:
            return Vec3(0, -1, 0)  # Default: dig down
        return Vec3((other.x - self.x) / d, (other.y - self.y) / d,
                     (other.z - self.z) / d)


@dataclass
class TunnelNode:
    """A junction point in the tunnel network."""
    id: int
    position: Vec3
    is_entrance: bool = False
    is_chamber: bool = False
    chamber_radius_m: float = 0.0


@dataclass
class TunnelSegment:
    """A tunnel segment between two nodes."""
    id: int
    from_node_id: int
    to_node_id: int
    length_m: float = 0.0
    diameter_m: float = 0.4          # Operational width
    sealed: bool = False
    seal_quality: float = 0.0
    pressurized: bool = False
    pressure_kpa: float = 0.0
    material_extracted_kg: float = 0.0
    depth_from_surface_m: float = 0.0
    # Composition zone
    zone_type: str = ""
    zone_richness: float = 1.0
    # Infrastructure
    rail_installed: bool = False     # Power rails bonded to wall
    # Dig direction (unit vector)
    direction: Vec3 = field(default_factory=lambda: Vec3(0, -1, 0))

    @property
    def volume_m3(self) -> float:
        return math.pi * (self.diameter_m / 2) ** 2 * self.length_m

    @property
    def wall_area_m2(self) -> float:
        return math.pi * self.diameter_m * self.length_m


@dataclass
class CommonChamber:
    """A large chamber that multiple tunnel networks excavate toward."""
    center: Vec3
    target_radius_m: float = 8.0     # Target size
    current_radius_m: float = 0.0
    material_removed_kg: float = 0.0
    sealed: bool = False
    pressurized: bool = False
    connected_sites: list[int] = field(default_factory=list)
    purpose: str = ""

    @property
    def target_volume_m3(self) -> float:
        return (4/3) * math.pi * self.target_radius_m ** 3

    @property
    def current_volume_m3(self) -> float:
        return (4/3) * math.pi * self.current_radius_m ** 3

    @property
    def completion_pct(self) -> float:
        if self.target_volume_m3 <= 0:
            return 0
        return min(100, self.current_volume_m3 / self.target_volume_m3 * 100)


class TunnelNetwork:
    """The complete tunnel system inside the asteroid.

    Supports branching topology: nodes connected by segments.
    Can grow toward a common chamber shared with other sites.
    """

    def __init__(self, site_id: int = 0, entrance_pos: Vec3 | None = None) -> None:
        self.site_id = site_id
        self.nodes: list[TunnelNode] = []
        self.segments: list[TunnelSegment] = []
        self._next_node_id = 0
        self._next_seg_id = 0
        self.target_pressure_kpa = 5.0
        self.total_material_extracted_kg = 0.0
        self.total_water_recovered_kg = 0.0

        # Dig direction preference (set by player/taskmaster)
        self.dig_target: Vec3 | None = None  # None = explore freely

        # Common chamber reference (shared across sites)
        self.common_chamber: CommonChamber | None = None

        # Create entrance node
        pos = entrance_pos or Vec3(0, 10, 0)  # Surface of asteroid
        entrance = self._add_node(pos, is_entrance=True)

        # Create initial shaft segment (drilled by mothership)
        shaft_end = self._add_node(Vec3(pos.x, pos.y - 3, pos.z))
        self._add_segment(entrance.id, shaft_end.id, length_m=3.0,
                          depth=1.5, sealed=True, seal_quality=0.9,
                          pressurized=True)

    def _add_node(self, position: Vec3, is_entrance: bool = False,
                  is_chamber: bool = False) -> TunnelNode:
        node = TunnelNode(id=self._next_node_id, position=position,
                          is_entrance=is_entrance, is_chamber=is_chamber)
        self.nodes.append(node)
        self._next_node_id += 1
        return node

    def _add_segment(self, from_id: int, to_id: int, length_m: float = 1.0,
                     depth: float = 0.0, sealed: bool = False,
                     seal_quality: float = 0.0, pressurized: bool = False) -> TunnelSegment:
        from_node = next((n for n in self.nodes if n.id == from_id), None)
        to_node = next((n for n in self.nodes if n.id == to_id), None)

        direction = Vec3(0, -1, 0)
        if from_node and to_node:
            direction = from_node.position.direction_to(to_node.position)

        seg = TunnelSegment(
            id=self._next_seg_id,
            from_node_id=from_id, to_node_id=to_id,
            length_m=length_m, diameter_m=0.4,
            sealed=sealed, seal_quality=seal_quality,
            pressurized=pressurized,
            pressure_kpa=self.target_pressure_kpa if pressurized else 0.0,
            depth_from_surface_m=depth,
            direction=direction,
        )
        self.segments.append(seg)
        self._next_seg_id += 1
        return seg

    def extend_tunnel(self, segment_id: int, amount_m: float, regolith_kg: float) -> None:
        """Worker ants dig, extending a segment."""
        for seg in self.segments:
            if seg.id == segment_id:
                seg.length_m += amount_m
                seg.material_extracted_kg += regolith_kg
                self.total_material_extracted_kg += regolith_kg

                # Update the endpoint node position based on dig direction
                end_node = next((n for n in self.nodes if n.id == seg.to_node_id), None)
                if end_node:
                    end_node.position.x += seg.direction.x * amount_m
                    end_node.position.y += seg.direction.y * amount_m
                    end_node.position.z += seg.direction.z * amount_m
                return

    def branch_tunnel(self, from_segment_id: int, direction: Vec3 | None = None) -> TunnelSegment:
        """Create a branch from an existing tunnel segment.

        Returns the new branch segment.
        """
        parent_seg = next((s for s in self.segments if s.id == from_segment_id), None)
        if parent_seg is None:
            parent_seg = self.segments[-1]  # Default to latest segment

        # Branch point is at the end of the parent segment
        branch_node = next((n for n in self.nodes if n.id == parent_seg.to_node_id), None)
        if branch_node is None:
            return self.segments[-1]

        # Choose direction
        if direction is None:
            if self.dig_target:
                # Dig toward the target
                direction = branch_node.position.direction_to(self.dig_target)
            elif self.common_chamber:
                # Dig toward the common chamber
                direction = branch_node.position.direction_to(self.common_chamber.center)
            else:
                # Random exploration direction
                angle = random.uniform(0, math.pi * 2)
                direction = Vec3(math.cos(angle) * 0.5, -0.8, math.sin(angle) * 0.5)

        # Create new endpoint
        new_pos = Vec3(
            branch_node.position.x + direction.x * 0.5,
            branch_node.position.y + direction.y * 0.5,
            branch_node.position.z + direction.z * 0.5,
        )
        new_node = self._add_node(new_pos)
        new_seg = self._add_segment(branch_node.id, new_node.id, length_m=0.5,
                                    depth=abs(new_pos.y))
        new_seg.direction = direction

        return new_seg

    def seal_segment(self, segment_id: int, quality: float) -> None:
        for seg in self.segments:
            if seg.id == segment_id:
                seg.sealed = True
                seg.seal_quality = min(1.0, seg.seal_quality + quality)
                return

    def pressurize_segment(self, segment_id: int) -> None:
        for seg in self.segments:
            if seg.id == segment_id and seg.sealed and seg.seal_quality >= 0.5:
                seg.pressurized = True
                seg.pressure_kpa = self.target_pressure_kpa * seg.seal_quality
                return

    def record_water_recovery(self, water_kg: float) -> None:
        self.total_water_recovered_kg += water_kg

    def set_dig_target(self, target: Vec3) -> None:
        """Player sets a dig direction target."""
        self.dig_target = target

    def contribute_to_chamber(self, regolith_kg: float, density_kg_m3: float = 1190) -> None:
        """Contribute excavated material toward the common chamber."""
        if self.common_chamber is None:
            return
        self.common_chamber.material_removed_kg += regolith_kg
        # Calculate new radius from removed volume
        volume = self.common_chamber.material_removed_kg / density_kg_m3
        self.common_chamber.current_radius_m = (3 * volume / (4 * math.pi)) ** (1/3)

    @property
    def total_length_m(self) -> float:
        return sum(s.length_m for s in self.segments)

    @property
    def total_volume_m3(self) -> float:
        return sum(s.volume_m3 for s in self.segments)

    @property
    def sealed_length_m(self) -> float:
        return sum(s.length_m for s in self.segments if s.sealed)

    @property
    def pressurized_length_m(self) -> float:
        return sum(s.length_m for s in self.segments if s.pressurized)

    @property
    def active_work_face_id(self) -> int:
        if self.segments:
            return self.segments[-1].id
        return 0

    @property
    def branch_count(self) -> int:
        """Count branch points (nodes with >2 connected segments)."""
        connections = {}
        for seg in self.segments:
            connections[seg.from_node_id] = connections.get(seg.from_node_id, 0) + 1
            connections[seg.to_node_id] = connections.get(seg.to_node_id, 0) + 1
        return sum(1 for c in connections.values() if c > 2)

    @property
    def deepest_point_m(self) -> float:
        if not self.nodes:
            return 0
        entrance = next((n for n in self.nodes if n.is_entrance), self.nodes[0])
        return max(entrance.position.distance_to(n.position) for n in self.nodes)

    def summary(self) -> dict:
        return {
            "site_id": self.site_id,
            "segments": len(self.segments),
            "nodes": len(self.nodes),
            "branches": self.branch_count,
            "total_length_m": round(self.total_length_m, 1),
            "total_volume_m3": round(self.total_volume_m3, 2),
            "sealed_length_m": round(self.sealed_length_m, 1),
            "pressurized_length_m": round(self.pressurized_length_m, 1),
            "deepest_point_m": round(self.deepest_point_m, 1),
            "material_extracted_kg": round(self.total_material_extracted_kg, 1),
            "water_recovered_kg": round(self.total_water_recovered_kg, 1),
            "common_chamber": {
                "completion_pct": round(self.common_chamber.completion_pct, 1),
                "current_radius_m": round(self.common_chamber.current_radius_m, 1),
                "target_radius_m": self.common_chamber.target_radius_m,
                "connected_sites": len(self.common_chamber.connected_sites),
            } if self.common_chamber else None,
        }
