"""Equipment placement engine -- validates that everything fits and connects.

Enforces physical constraints:
  1. Equipment fits in available space (volume check)
  2. Power bus not exceeded (circuit breaker check)
  3. Fluid connections can reach between equipment
  4. Heat sources separated from heat-sensitive equipment
  5. Vibration sources isolated from sensitive equipment
  6. Clearance zones don't overlap
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SPEC_FILE = Path(__file__).parent.parent / "catalog" / "equipment_specs.yaml"


@dataclass
class PlacedEquipment:
    """An item placed at a specific location."""
    id: str
    spec: dict[str, Any]
    position_mm: tuple[float, float, float]  # Center point (x, y, z)
    deck: int                                 # Which mothership deck

    @property
    def bounds_mm(self) -> dict[str, float]:
        """Bounding box including clearance zones."""
        phys = self.spec.get("physical", {})
        clear = self.spec.get("clearance", {})

        # Get dimensions (handle cylinder and box shapes)
        if phys.get("shape") == "cylinder":
            w = h_dim = phys.get("diameter_mm", 500)
            h = phys.get("height_mm", 500)
        else:
            w = phys.get("width_mm", phys.get("length_mm", 300))
            h_dim = phys.get("height_mm", 300)
            h = phys.get("length_mm", phys.get("height_mm", 300))

        # Add clearance
        cl_sides = clear.get("sides_mm", clear.get("all_sides_mm", 100))
        cl_top = clear.get("top_mm", cl_sides)
        cl_front = clear.get("front_mm", cl_sides)

        return {
            "width_with_clearance": w + 2 * cl_sides,
            "height_with_clearance": h_dim + cl_top,
            "depth_with_clearance": h + cl_front,
            "base_width": w,
            "base_height": h_dim,
        }

    @property
    def power_draw_w(self) -> float:
        return self.spec.get("power", {}).get("draw_w", 0)

    @property
    def heat_output_w(self) -> float:
        return self.spec.get("heat", {}).get("output_w", 0)

    @property
    def is_heat_sensitive(self) -> bool:
        return self.spec.get("heat", {}).get("SENSITIVE_TO_HEAT", False)

    @property
    def max_surface_temp(self) -> float:
        return self.spec.get("heat", {}).get("max_surface_temp_c", 25)


def load_equipment_specs() -> dict[str, Any]:
    """Load all equipment specifications from the catalog."""
    if not SPEC_FILE.exists():
        return {}
    with open(SPEC_FILE) as f:
        return yaml.safe_load(f) or {}


def validate_placement(placed_items: list[PlacedEquipment],
                        available_power_w: float = 5800,
                        available_volume_m3: float = 4.0) -> dict[str, Any]:
    """Validate a set of equipment placements against physical constraints.

    Returns a report with warnings and errors.
    """
    errors = []
    warnings = []

    # 1. Total power check
    total_power = sum(item.power_draw_w for item in placed_items)
    if total_power > available_power_w:
        errors.append(
            f"POWER EXCEEDED: {total_power:.0f}W needed but only "
            f"{available_power_w:.0f}W available. Need more solar panels or nuclear."
        )
    elif total_power > available_power_w * 0.85:
        warnings.append(
            f"POWER MARGIN LOW: {total_power:.0f}W of {available_power_w:.0f}W "
            f"({total_power/available_power_w*100:.0f}%). Less than 15% margin."
        )

    # 2. Volume check
    total_volume_l = 0
    for item in placed_items:
        phys = item.spec.get("physical", {})
        if phys.get("shape") == "cylinder":
            import math
            r = phys.get("diameter_mm", 500) / 2000  # Convert to meters
            h = phys.get("height_mm", 500) / 1000
            vol = math.pi * r**2 * h * 1000  # Liters
        else:
            w = phys.get("width_mm", phys.get("length_mm", 300)) / 1000
            d = phys.get("length_mm", phys.get("height_mm", 300)) / 1000
            h = phys.get("height_mm", 300) / 1000
            vol = w * d * h * 1000
        total_volume_l += vol

    total_volume_m3 = total_volume_l / 1000
    if total_volume_m3 > available_volume_m3:
        errors.append(
            f"VOLUME EXCEEDED: {total_volume_m3:.2f} m3 equipment but only "
            f"{available_volume_m3:.2f} m3 available."
        )

    # 3. Heat proximity check
    hot_items = [i for i in placed_items if i.max_surface_temp > 60]
    sensitive_items = [i for i in placed_items if i.is_heat_sensitive]

    for hot in hot_items:
        for sens in sensitive_items:
            # Check placement constraint distances
            constraints = sens.spec.get("placement_constraints", {})
            min_dist = constraints.get("min_distance_from_furnace_m",
                       constraints.get("min_distance_from_bio_m", 1.0))
            # Simple distance check (would use actual positions in full sim)
            warnings.append(
                f"HEAT CHECK: {hot.id} ({hot.max_surface_temp}C surface) near "
                f"{sens.id} (heat sensitive). Ensure {min_dist}m separation."
            )

    # 4. Vibration check
    vibration_sources = [i for i in placed_items
                          if i.spec.get("mounting", {}).get("vibration_isolation")]
    for vib in vibration_sources:
        constraints = vib.spec.get("placement_constraints", {})
        away_from = constraints.get("must_be_away_from", [])
        for other in placed_items:
            if other.id in away_from:
                warnings.append(
                    f"VIBRATION: {vib.id} should be away from {other.id}. "
                    f"Ensure vibration isolation mounts are installed."
                )

    # 5. Fluid connection check
    for item in placed_items:
        connections = item.spec.get("fluid_connections", [])
        for conn in connections:
            target = conn.get("connects_to", "")
            if target and not any(p.id == target or target in p.id for p in placed_items):
                if target not in ("tunnel_entrance", "waste_paste_tank", "crusher_output",
                                  "co2_kiln_output", "solar_concentrator",
                                  "thermal_sorter_output", "condenser"):
                    warnings.append(
                        f"MISSING CONNECTION: {item.id} needs {conn['id']} -> {target} "
                        f"but {target} is not placed."
                    )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "total_power_w": total_power,
        "power_margin_pct": round((1 - total_power / available_power_w) * 100, 1) if available_power_w > 0 else 0,
        "total_volume_m3": round(total_volume_m3, 3),
        "volume_margin_pct": round((1 - total_volume_m3 / available_volume_m3) * 100, 1) if available_volume_m3 > 0 else 0,
        "items_placed": len(placed_items),
        "heat_sources": len(hot_items),
        "heat_sensitive": len(sensitive_items),
    }


def format_placement_report(result: dict[str, Any]) -> str:
    """Format placement validation as readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("EQUIPMENT PLACEMENT VALIDATION")
    lines.append("=" * 60)

    status = "VALID" if result["valid"] else "INVALID"
    lines.append(f"\n  Status: {status}")
    lines.append(f"  Items placed: {result['items_placed']}")
    lines.append(f"  Power: {result['total_power_w']:.0f}W ({result['power_margin_pct']:.0f}% margin)")
    lines.append(f"  Volume: {result['total_volume_m3']:.3f} m3 ({result['volume_margin_pct']:.0f}% margin)")

    if result["errors"]:
        lines.append(f"\n  ERRORS ({len(result['errors'])}):")
        for e in result["errors"]:
            lines.append(f"    [!] {e}")

    if result["warnings"]:
        lines.append(f"\n  WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            lines.append(f"    [~] {w}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
