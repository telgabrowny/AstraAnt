"""Endgame goal tracker -- progressive habitat construction inside the asteroid.

The habitat grows from a small centrifuge ring into a full 1g Interstellar-style
rotating cylinder through incremental ring sections. Each section is independently
excavated, sealed, and activated. People can live in completed sections while
deeper ones are still being dug.

The cone-to-cylinder approach: start narrow at the surface, widen each section
as you dig deeper, until reaching the target diameter. Then extend the cylinder
to the desired length. Like a tree adding growth rings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HabitatSection:
    """One ring section of the growing habitat."""
    section_id: int
    depth_m: float
    radius_m: float
    length_m: float = 10.0
    gravity_g: float = 0.0        # At 2 RPM
    volume_m3: float = 0.0
    excavation_mass_kg: float = 0.0
    status: str = "planned"       # planned, excavating, sealed, spinning, inhabited
    completion_pct: float = 0.0


@dataclass
class HabitatGoal:
    """The endgame habitat goal -- tracks progress toward Interstellar."""
    target_radius_m: float = 224      # 1g at 2 RPM
    target_length_m: float = 200
    rpm: float = 2.0
    section_length_m: float = 10
    growth_rate_m: float = 5          # Radius grows 5m per section

    sections: list[HabitatSection] = field(default_factory=list)
    current_section: int = 0          # Which section is actively being excavated
    total_excavated_m3: float = 0.0
    total_sections_complete: int = 0

    # Supply mission tracking
    supply_missions_sent: int = 0
    electronics_shipped_kg: float = 0.0

    def __post_init__(self):
        if not self.sections:
            self._generate_sections()

    def _generate_sections(self):
        """Pre-generate all section targets."""
        r = 5  # Start at centrifuge size
        depth = 0

        while True:
            actual_r = min(r, self.target_radius_m)
            omega = 2 * math.pi * self.rpm / 60
            g = omega ** 2 * actual_r / 9.81

            vol = math.pi * actual_r ** 2 * self.section_length_m * 1.2
            mass = vol * 1190  # Bennu density

            self.sections.append(HabitatSection(
                section_id=len(self.sections),
                depth_m=depth,
                radius_m=actual_r,
                length_m=self.section_length_m,
                gravity_g=round(g, 3),
                volume_m3=vol,
                excavation_mass_kg=mass,
            ))

            depth += self.section_length_m
            if r < self.target_radius_m:
                r += self.growth_rate_m
            else:
                # Full diameter reached -- extend to target length
                remaining = self.target_length_m - (depth - self._cone_depth())
                if remaining <= 0:
                    break

            if len(self.sections) > 100:
                break

    def _cone_depth(self) -> float:
        """Depth at which the cone reaches target radius."""
        sections_to_full = math.ceil((self.target_radius_m - 5) / self.growth_rate_m)
        return sections_to_full * self.section_length_m

    def excavate(self, volume_m3: float) -> list[str]:
        """Add excavated volume. Returns milestone events."""
        events = []
        self.total_excavated_m3 += volume_m3

        if self.current_section >= len(self.sections):
            return events

        section = self.sections[self.current_section]
        section.status = "excavating"
        section.completion_pct = min(100, section.completion_pct +
                                     (volume_m3 / section.volume_m3 * 100))

        if section.completion_pct >= 100:
            section.status = "sealed"
            self.total_sections_complete += 1
            self.current_section += 1

            events.append(
                f"HABITAT SECTION {section.section_id + 1} COMPLETE: "
                f"radius {section.radius_m:.0f}m, {section.gravity_g:.2f}g"
            )

            # Milestone checks
            if section.radius_m >= 15 and (section.section_id == 0 or
                    self.sections[section.section_id - 1].radius_m < 15):
                events.append("MILESTONE: Walk-around ring (0.15g) -- crew quarters operational")
            if section.radius_m >= 50 and self.sections[max(0, section.section_id - 1)].radius_m < 50:
                events.append("MILESTONE: Gardens section (0.22g) -- plants can grow with support")
            if section.radius_m >= 100 and self.sections[max(0, section.section_id - 1)].radius_m < 100:
                events.append("MILESTONE: Small town (0.45g) -- trees, rain, community spaces")
            if section.radius_m >= 200 and self.sections[max(0, section.section_id - 1)].radius_m < 200:
                events.append("MILESTONE: Near-Earth gravity (0.89g) -- almost like home")
            if section.gravity_g >= 0.99 and self.sections[max(0, section.section_id - 1)].gravity_g < 0.99:
                events.append("MILESTONE: FULL 1G ACHIEVED -- Interstellar-class habitat!")

        return events

    @property
    def overall_progress_pct(self) -> float:
        if not self.sections:
            return 0
        total_vol = sum(s.volume_m3 for s in self.sections)
        return min(100, self.total_excavated_m3 / total_vol * 100)

    @property
    def current_gravity(self) -> float:
        """Gravity in the most recently completed section."""
        if self.total_sections_complete == 0:
            return 0
        return self.sections[self.total_sections_complete - 1].gravity_g

    @property
    def current_radius(self) -> float:
        if self.total_sections_complete == 0:
            return 0
        return self.sections[self.total_sections_complete - 1].radius_m

    @property
    def habitable_floor_area_m2(self) -> float:
        """Total floor area of completed spinning sections."""
        area = 0
        for s in self.sections[:self.total_sections_complete]:
            area += 2 * math.pi * s.radius_m * s.length_m
        return area

    def summary(self) -> dict[str, Any]:
        return {
            "total_sections": len(self.sections),
            "sections_complete": self.total_sections_complete,
            "overall_progress_pct": round(self.overall_progress_pct, 2),
            "current_gravity_g": round(self.current_gravity, 3),
            "current_radius_m": round(self.current_radius, 0),
            "habitable_area_m2": round(self.habitable_floor_area_m2, 0),
            "target": f"{self.target_radius_m}m radius, {self.target_length_m}m long, 1g",
            "excavated_m3": round(self.total_excavated_m3, 0),
            "supply_missions": self.supply_missions_sent,
        }


def format_endgame_report(goal: HabitatGoal) -> str:
    """Format the endgame progress report."""
    lines = []
    lines.append("=" * 70)
    lines.append("ENDGAME: ROTATING HABITAT CONSTRUCTION PROGRESS")
    lines.append(f"Target: {goal.target_radius_m}m radius cylinder, "
                 f"{goal.target_length_m}m long, 1g at {goal.rpm} RPM")
    lines.append("=" * 70)

    s = goal.summary()
    lines.append(f"\n  Overall progress:    {s['overall_progress_pct']:.2f}%")
    lines.append(f"  Sections complete:   {s['sections_complete']} / {s['total_sections']}")
    lines.append(f"  Current gravity:     {s['current_gravity_g']:.3f}g")
    lines.append(f"  Current radius:      {s['current_radius_m']:.0f}m")
    lines.append(f"  Habitable area:      {s['habitable_area_m2']:,.0f} m2")
    lines.append(f"  Volume excavated:    {s['excavated_m3']:,.0f} m3")
    lines.append(f"  Supply missions:     {s['supply_missions']}")

    lines.append(f"\n--- SECTION STATUS ---")
    lines.append(f"{'Sec':<5s} {'Depth':<7s} {'Radius':<8s} {'Gravity':<8s} {'Status':<12s} {'Progress'}")
    lines.append("-" * 55)

    for sec in goal.sections[:max(goal.current_section + 3, 10)]:
        pct = f"{sec.completion_pct:.0f}%" if sec.completion_pct > 0 else ""
        lines.append(f"{sec.section_id + 1:<5d} {sec.depth_m:<7.0f} {sec.radius_m:<8.0f} "
                     f"{sec.gravity_g:<8.3f} {sec.status:<12s} {pct}")
    if goal.current_section + 3 < len(goal.sections):
        lines.append(f"  ... {len(goal.sections) - goal.current_section - 3} more sections planned ...")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
