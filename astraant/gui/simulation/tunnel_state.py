"""Tunnel network state — tracks excavation progress, sealing, and pressurization."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TunnelSegment:
    """A single segment of the tunnel network."""
    id: int
    length_m: float = 0.0
    diameter_m: float = 0.2         # Drill bore diameter
    sealed: bool = False
    seal_quality: float = 0.0       # 0.0 to 1.0 (fraction of target pressure retained)
    pressurized: bool = False
    pressure_kpa: float = 0.0
    material_extracted_kg: float = 0.0
    depth_from_surface_m: float = 0.0

    @property
    def volume_m3(self) -> float:
        import math
        return math.pi * (self.diameter_m / 2) ** 2 * self.length_m

    @property
    def wall_area_m2(self) -> float:
        import math
        return math.pi * self.diameter_m * self.length_m


class TunnelNetwork:
    """The complete tunnel system inside the asteroid."""

    def __init__(self) -> None:
        self.segments: list[TunnelSegment] = []
        self._next_id = 0
        self.target_pressure_kpa = 5.0
        self.total_material_extracted_kg = 0.0
        self.total_water_recovered_kg = 0.0

        # Create initial shaft (drilled by mothership)
        self.add_segment(length_m=3.0, depth=1.5, sealed=True,
                         seal_quality=0.9, pressurized=True)

    def add_segment(self, length_m: float = 1.0, depth: float = 0.0,
                    sealed: bool = False, seal_quality: float = 0.0,
                    pressurized: bool = False) -> TunnelSegment:
        seg = TunnelSegment(
            id=self._next_id,
            length_m=length_m,
            diameter_m=0.2,
            sealed=sealed,
            seal_quality=seal_quality,
            pressurized=pressurized,
            pressure_kpa=self.target_pressure_kpa if pressurized else 0.0,
            depth_from_surface_m=depth,
        )
        self.segments.append(seg)
        self._next_id += 1
        return seg

    def extend_tunnel(self, segment_id: int, amount_m: float, regolith_kg: float) -> None:
        """Worker ants dig, extending a segment."""
        for seg in self.segments:
            if seg.id == segment_id:
                seg.length_m += amount_m
                seg.material_extracted_kg += regolith_kg
                self.total_material_extracted_kg += regolith_kg
                return

    def seal_segment(self, segment_id: int, quality: float) -> None:
        """Plasterer ant seals a tunnel segment."""
        for seg in self.segments:
            if seg.id == segment_id:
                seg.sealed = True
                seg.seal_quality = min(1.0, seg.seal_quality + quality)
                return

    def pressurize_segment(self, segment_id: int) -> None:
        """Pressurize a sealed segment."""
        for seg in self.segments:
            if seg.id == segment_id and seg.sealed and seg.seal_quality >= 0.5:
                seg.pressurized = True
                seg.pressure_kpa = self.target_pressure_kpa * seg.seal_quality
                return

    def record_water_recovery(self, water_kg: float) -> None:
        self.total_water_recovered_kg += water_kg

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
        """The segment currently being excavated (last/deepest)."""
        if self.segments:
            return self.segments[-1].id
        return 0

    def summary(self) -> dict:
        return {
            "segments": len(self.segments),
            "total_length_m": round(self.total_length_m, 1),
            "total_volume_m3": round(self.total_volume_m3, 2),
            "sealed_length_m": round(self.sealed_length_m, 1),
            "pressurized_length_m": round(self.pressurized_length_m, 1),
            "material_extracted_kg": round(self.total_material_extracted_kg, 1),
            "water_recovered_kg": round(self.total_water_recovered_kg, 1),
        }
