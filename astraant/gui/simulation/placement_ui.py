"""Placement UI logic -- traffic-light feedback for equipment layout.

In microgravity, EVERY surface is mountable: floor, walls, ceiling.
The tunnel is a cylinder -- equipment can be bolted at any angle
around the circumference. This actually HELPS with thermal separation:
put the furnace on the ceiling and heat rises into rock, not toward
the algae on the floor.

Color coding:
  GREEN:  All checks pass. Good placement.
  YELLOW: Placement works but has warnings (heat proximity, vibration).
  RED:    Invalid placement (power exceeded, won't fit, connection impossible).

Training tooltips explain WHY each color was chosen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math


@dataclass
class MountingSurface:
    """A surface where equipment can be bolted in the tunnel."""
    name: str
    angle_deg: float         # 0=floor, 90=right wall, 180=ceiling, 270=left wall
    usable_length_m: float   # Along the tunnel axis
    usable_width_m: float    # Around the circumference at this angle

    @property
    def is_ceiling(self) -> bool:
        return 135 < self.angle_deg < 225

    @property
    def is_wall(self) -> bool:
        return (45 < self.angle_deg < 135) or (225 < self.angle_deg < 315)

    @property
    def is_floor(self) -> bool:
        return self.angle_deg < 45 or self.angle_deg > 315


# Standard tunnel cross-section surfaces
TUNNEL_SURFACES = [
    MountingSurface("floor", 0, 999, 0.35),        # 350mm usable width
    MountingSurface("right_wall", 90, 999, 0.30),
    MountingSurface("ceiling", 180, 999, 0.35),
    MountingSurface("left_wall", 270, 999, 0.30),
    # Diagonal positions for creative mounting
    MountingSurface("floor_right", 45, 999, 0.25),
    MountingSurface("right_ceiling", 135, 999, 0.25),
    MountingSurface("ceiling_left", 225, 999, 0.25),
    MountingSurface("left_floor", 315, 999, 0.25),
]


@dataclass
class PlacementCheck:
    """Result of checking one placement position."""
    color: str               # "green", "yellow", "red"
    score: float             # 0-100 (higher = better)
    reasons: list[str]       # Why this color
    tips: list[str]          # Helpful suggestions
    surface: str
    angle_deg: float


def check_placement_position(
    equipment_id: str,
    equipment_spec: dict[str, Any],
    surface_angle_deg: float,
    tunnel_position_m: float,
    existing_placements: list[dict[str, Any]],
    available_power_w: float = 5800,
) -> PlacementCheck:
    """Check if placing equipment at this position is valid.

    Returns a traffic-light result with explanation.
    """
    reasons = []
    tips = []
    score = 100  # Start perfect, deduct for issues

    phys = equipment_spec.get("physical", {})
    power = equipment_spec.get("power", {})
    heat = equipment_spec.get("heat", {})
    constraints = equipment_spec.get("placement_constraints", {})
    mounting = equipment_spec.get("mounting", {})

    # Determine surface name
    surface = "floor"
    if 45 < surface_angle_deg < 135:
        surface = "right_wall"
    elif 135 <= surface_angle_deg <= 225:
        surface = "ceiling"
    elif 225 < surface_angle_deg < 315:
        surface = "left_wall"

    # === SIZE CHECK ===
    # Does the equipment fit on this surface?
    width_mm = phys.get("width_mm", phys.get("diameter_mm", 300))
    surface_width_mm = 350 if surface in ("floor", "ceiling") else 300
    if width_mm > surface_width_mm:
        reasons.append(f"Too wide ({width_mm}mm) for {surface} ({surface_width_mm}mm usable)")
        score -= 50
        tips.append(f"Try a wider surface (floor or ceiling = 350mm)")

    # === POWER CHECK ===
    total_existing_power = sum(p.get("power_w", 0) for p in existing_placements)
    new_power = power.get("draw_w", 0)
    if total_existing_power + new_power > available_power_w:
        reasons.append(f"Power bus exceeded: {total_existing_power + new_power}W > {available_power_w}W")
        score = 0  # Hard fail
        tips.append("Add more solar panels, switch to nuclear, or remove other equipment")

    # === HEAT PROXIMITY ===
    max_surface_temp = heat.get("max_surface_temp_c", 25)
    is_heat_source = max_surface_temp > 50
    is_heat_sensitive = heat.get("SENSITIVE_TO_HEAT", False)

    for existing in existing_placements:
        ex_heat = existing.get("heat", {})
        ex_temp = ex_heat.get("max_surface_temp_c", 25)
        ex_sensitive = ex_heat.get("SENSITIVE_TO_HEAT", False)
        ex_angle = existing.get("surface_angle_deg", 0)
        ex_pos = existing.get("tunnel_position_m", 0)

        # Distance calculation (simplified: angle difference + tunnel distance)
        angle_diff = abs(surface_angle_deg - ex_angle)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        # Circumferential distance (0.2m radius tunnel, angle in degrees)
        circ_dist = 0.2 * math.radians(angle_diff)
        linear_dist = abs(tunnel_position_m - ex_pos)
        total_dist = math.sqrt(circ_dist**2 + linear_dist**2)

        if is_heat_source and ex_sensitive and total_dist < 1.0:
            reasons.append(
                f"Hot surface ({max_surface_temp}C) within {total_dist:.1f}m of "
                f"heat-sensitive {existing.get('id', '?')}"
            )
            score -= 30
            tips.append(
                f"Move to OPPOSITE side of tunnel (ceiling vs floor). "
                f"Heat rises into rock instead of toward sensitive equipment."
            )

        if is_heat_sensitive and ex_temp > 50 and total_dist < 1.0:
            reasons.append(
                f"Heat-sensitive equipment within {total_dist:.1f}m of "
                f"{existing.get('id', '?')} ({ex_temp}C surface)"
            )
            score -= 30
            tips.append(
                f"Put this on the opposite wall/ceiling from the heat source."
            )

    # === CEILING BONUS for heat sources ===
    if is_heat_source and surface == "ceiling":
        score += 10
        reasons.append("BONUS: Heat source on ceiling -- heat rises into rock, not toward equipment")
        tips.append("Excellent placement for hot equipment in microgravity!")

    # === VIBRATION CHECK ===
    needs_isolation = mounting.get("vibration_isolation", False)
    away_from = constraints.get("must_be_away_from", [])

    for existing in existing_placements:
        if existing.get("id", "") in away_from:
            ex_pos = existing.get("tunnel_position_m", 0)
            dist = abs(tunnel_position_m - ex_pos)
            if dist < 1.0:
                reasons.append(
                    f"Vibration source near {existing.get('id', '?')} ({dist:.1f}m away)"
                )
                score -= 20
                tips.append(
                    f"Move at least 1m along the tunnel from {existing.get('id', '?')}. "
                    f"Vibration travels through the rock more in the axial direction."
                )

    # === FLUID CONNECTION CHECK ===
    fluid_conns = equipment_spec.get("fluid_connections", [])
    for conn in fluid_conns:
        target = conn.get("connects_to", "")
        if target and target not in ("tunnel_entrance", "waste_paste_tank",
                                      "crusher_output", "co2_kiln_output",
                                      "solar_concentrator", "thermal_sorter_output",
                                      "condenser"):
            # Check if target is placed nearby
            target_found = False
            for existing in existing_placements:
                if target in existing.get("id", ""):
                    target_found = True
                    ex_pos = existing.get("tunnel_position_m", 0)
                    pipe_length = abs(tunnel_position_m - ex_pos)
                    max_dist = constraints.get(f"max_distance_from_{target}_m",
                               constraints.get("max_distance_from_water_m", 5))
                    if pipe_length > max_dist:
                        reasons.append(
                            f"Pipe to {target} too long ({pipe_length:.1f}m > {max_dist}m max)"
                        )
                        score -= 15
                        tips.append(f"Move closer to {target} for shorter plumbing run")
                    break
            if not target_found:
                reasons.append(f"Need connection to {target} (not placed yet)")
                score -= 5
                tips.append(f"Place {target} first, then position this nearby")

    # === FINAL COLOR ===
    if score <= 0:
        color = "red"
    elif score < 70:
        color = "yellow"
    else:
        color = "green"

    if not reasons:
        reasons.append("All checks pass!")
        tips.append("Good placement. No issues detected.")

    return PlacementCheck(
        color=color,
        score=max(0, min(100, score)),
        reasons=reasons,
        tips=tips,
        surface=surface,
        angle_deg=surface_angle_deg,
    )


def get_placement_help(equipment_id: str, equipment_spec: dict) -> str:
    """Get placement guidance for a piece of equipment (training mode)."""
    constraints = equipment_spec.get("placement_constraints", {})
    heat = equipment_spec.get("heat", {})
    mounting = equipment_spec.get("mounting", {})
    name = equipment_spec.get("name", equipment_id)

    lines = [f"PLACEMENT GUIDE: {name}", "=" * 50]

    # Surface recommendation
    if heat.get("max_surface_temp_c", 25) > 60:
        lines.append("RECOMMENDED: Mount on CEILING")
        lines.append("  In microgravity, hot equipment on the ceiling means")
        lines.append("  radiated heat goes into the rock above, not toward")
        lines.append("  other equipment below. The rock is an infinite heat sink.")
    elif heat.get("SENSITIVE_TO_HEAT", False):
        lines.append("RECOMMENDED: Mount on FLOOR (away from ceiling heat sources)")
        lines.append("  Heat-sensitive equipment should be on the opposite surface")
        lines.append("  from any furnaces or thermal processors.")
    else:
        lines.append("FLEXIBLE: Can mount on any surface (floor, wall, ceiling)")
        lines.append("  In microgravity, all surfaces are equally valid.")
        lines.append("  Choose based on proximity to connected equipment.")

    # Proximity
    near = constraints.get("must_be_near", [])
    if near:
        lines.append(f"\nMUST BE NEAR: {', '.join(near)}")
        lines.append("  Short plumbing runs reduce leaks and pressure drops.")

    away = constraints.get("must_be_away_from", [])
    if away:
        lines.append(f"\nMUST BE AWAY FROM: {', '.join(away)}")

    # Vibration
    if mounting.get("vibration_isolation"):
        lines.append("\nVIBRATION WARNING: This equipment vibrates.")
        lines.append("  Requires isolation mounts. Keep 1m+ from bioreactors.")

    lines.append("")
    return "\n".join(lines)
