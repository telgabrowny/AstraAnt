"""Mission planner — pick a goal, get the best asteroid and loadout.

"I want to build an Interstellar habitat" -> recommends Bennu, 428 motherships, nuclear
"I want maximum water" -> ranks asteroids by water content × accessibility
"I want platinum" -> ranks by PGM content, recommends Track B + bioleaching
"Cheapest path to profit" -> smallest viable mission
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog
from .mission_economics import calculate_site_economics


@dataclass
class MissionObjective:
    """A player-defined mission goal."""
    id: str
    name: str
    description: str
    scoring_fn: str        # Name of the scoring function to use
    recommended_track: str
    recommended_power: str
    min_workers: int
    suggested_motherships: int


OBJECTIVES = [
    MissionObjective(
        id="cheapest_profit",
        name="Cheapest Path to Profit",
        description="Minimize cost while still being profitable in 5 years.",
        scoring_fn="score_cheapest_profit",
        recommended_track="b",
        recommended_power="solar",
        min_workers=50,
        suggested_motherships=1,
    ),
    MissionObjective(
        id="max_water",
        name="Maximum Water Extraction",
        description="Extract the most water. Water dominates revenue at lunar orbit.",
        scoring_fn="score_max_water",
        recommended_track="b",
        recommended_power="solar",
        min_workers=100,
        suggested_motherships=1,
    ),
    MissionObjective(
        id="max_platinum",
        name="Platinum Group Metal Focus",
        description="Target PGM-rich asteroids. Highest per-kg value.",
        scoring_fn="score_max_pgm",
        recommended_track="b",
        recommended_power="solar",
        min_workers=100,
        suggested_motherships=1,
    ),
    MissionObjective(
        id="rare_earths",
        name="Rare Earth Elements",
        description="Focus on REE extraction for electronics manufacturing.",
        scoring_fn="score_rare_earths",
        recommended_track="b",
        recommended_power="solar",
        min_workers=100,
        suggested_motherships=1,
    ),
    MissionObjective(
        id="fuel_depot",
        name="Fuel Depot (Water -> Propellant)",
        description="Establish a propellant production station. Water-rich asteroid + electrolyzer.",
        scoring_fn="score_fuel_depot",
        recommended_track="b",
        recommended_power="nuclear_10kw",
        min_workers=100,
        suggested_motherships=1,
    ),
    MissionObjective(
        id="habitat_small",
        name="Small Habitat (0.15g Ring)",
        description="Build a walk-around ring station inside the asteroid. Crew quarters.",
        scoring_fn="score_habitat_small",
        recommended_track="b",
        recommended_power="nuclear_10kw",
        min_workers=100,
        suggested_motherships=4,
    ),
    MissionObjective(
        id="habitat_medium",
        name="Medium Habitat (0.45g, Trees)",
        description="Build a 100m radius station. Trees can grow. Small community.",
        scoring_fn="score_habitat_medium",
        recommended_track="b",
        recommended_power="nuclear_40kw",
        min_workers=200,
        suggested_motherships=16,
    ),
    MissionObjective(
        id="interstellar",
        name="Interstellar-Class Habitat (1g)",
        description="The endgame. 224m radius rotating cylinder. Full Earth gravity. A town in an asteroid.",
        scoring_fn="score_interstellar",
        recommended_track="b",
        recommended_power="nuclear_40kw",
        min_workers=500,
        suggested_motherships=100,
    ),
    MissionObjective(
        id="self_replicating",
        name="Self-Replicating Colony",
        description="Maximize local manufacturing capability. Build everything from asteroid materials.",
        scoring_fn="score_self_replication",
        recommended_track="c",
        recommended_power="nuclear_10kw",
        min_workers=100,
        suggested_motherships=4,
    ),
]


def score_asteroid(asteroid_id: str, objective: MissionObjective,
                   catalog: Catalog) -> dict[str, Any]:
    """Score an asteroid for a given objective."""
    ast = catalog.get_asteroid(asteroid_id)
    if ast is None:
        return {"id": asteroid_id, "score": 0, "reason": "not found"}

    comp = ast.get("composition", {})
    metals = comp.get("metals_ppm", {})
    bulk = comp.get("bulk", {})
    mining = ast.get("mining_relevance", {})
    access = mining.get("accessibility", {})
    phys = ast.get("physical", {})

    water_pct = bulk.get("water_hydrated", 0)
    dv = access.get("delta_v_from_leo_km_per_s", 99)
    diameter = phys.get("diameter_m", 0)
    confidence = comp.get("confidence", "low")

    # Accessibility factor (lower delta-v = better)
    access_factor = max(0, 1.0 - (dv - 4.0) / 6.0)  # 1.0 at 4 km/s, 0 at 10 km/s

    # Confidence factor
    conf_factor = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(confidence, 0.3)

    obj_id = objective.id
    score = 0
    reason = ""

    if obj_id == "cheapest_profit":
        # Best: high water, low delta-v, high confidence
        score = water_pct * access_factor * conf_factor * 10
        reason = f"water {water_pct}%, dv {dv}, conf {confidence}"

    elif obj_id == "max_water":
        score = water_pct * access_factor * 100
        reason = f"water {water_pct}%, access {access_factor:.2f}"

    elif obj_id == "max_pgm":
        pgm = metals.get("platinum", 0) + metals.get("palladium", 0) + metals.get("iridium", 0)
        # PGM values are small (ppm) but extremely valuable per kg
        score = pgm * access_factor * conf_factor * 100  # Scale up
        reason = f"PGM {pgm:.0f} ppm (Pt+Pd+Ir), access {access_factor:.2f}"

    elif obj_id == "rare_earths":
        ree = metals.get("rare_earths_total", 0)
        score = ree * access_factor * conf_factor * 10  # Scale up
        reason = f"REE {ree} ppm, access {access_factor:.2f}"

    elif obj_id == "fuel_depot":
        score = water_pct * access_factor * conf_factor * 50
        reason = f"water {water_pct}% (propellant feedstock)"

    elif obj_id in ("habitat_small", "habitat_medium", "interstellar"):
        # Need big asteroid + water + metals for construction
        size_factor = min(1.0, diameter / 500)  # Bigger = better
        score = size_factor * water_pct * access_factor * conf_factor * 20
        reason = f"diameter {diameter}m, water {water_pct}%, access {access_factor:.2f}"

    elif obj_id == "self_replicating":
        # Need iron + nickel + copper for manufacturing
        iron = metals.get("iron", 0)
        nickel = metals.get("nickel", 0)
        copper = metals.get("copper", 0)
        metal_score = (iron / 200000 + nickel / 13000 + copper / 120) / 3
        score = metal_score * water_pct * access_factor * conf_factor * 100
        reason = f"metals + water + access combined"

    return {
        "id": asteroid_id,
        "name": ast.get("name", asteroid_id),
        "score": round(score, 2),
        "reason": reason,
        "delta_v": dv,
        "water_pct": water_pct,
        "confidence": confidence,
        "diameter_m": diameter,
    }


def plan_mission(objective_id: str, catalog: Catalog | None = None) -> dict[str, Any]:
    """Plan a mission for the given objective.

    Returns the recommended asteroid, loadout, and estimated results.
    """
    if catalog is None:
        catalog = Catalog()

    # Find the objective
    obj = next((o for o in OBJECTIVES if o.id == objective_id), None)
    if obj is None:
        return {"error": f"Unknown objective: {objective_id}"}

    # Score all asteroids
    rankings = []
    for ast in catalog.asteroids:
        score = score_asteroid(ast.id, obj, catalog)
        rankings.append(score)

    rankings.sort(key=lambda x: -x["score"])

    # Best asteroid
    best = rankings[0] if rankings else None

    # Calculate economics for the best asteroid
    econ = None
    if best:
        econ = calculate_site_economics(
            best["id"], "lunar_orbit", obj.recommended_track,
            workers=obj.min_workers, mission_years=5,
        )

    return {
        "objective": obj,
        "rankings": rankings,
        "best_asteroid": best,
        "economics": econ,
    }


def format_mission_plan(result: dict[str, Any]) -> str:
    """Format mission plan as readable report."""
    lines = []
    obj = result["objective"]
    best = result["best_asteroid"]
    econ = result["economics"]

    lines.append("=" * 70)
    lines.append(f"MISSION PLANNER: {obj.name}")
    lines.append(f"{obj.description}")
    lines.append("=" * 70)

    lines.append(f"\n--- RECOMMENDED LOADOUT ---")
    lines.append(f"  Track: {obj.recommended_track.upper()}")
    lines.append(f"  Power: {obj.recommended_power}")
    lines.append(f"  Workers: {obj.min_workers}+")
    lines.append(f"  Motherships: {obj.suggested_motherships}")

    lines.append(f"\n--- ASTEROID RANKINGS ---")
    lines.append(f"  {'Rank':<5s} {'Asteroid':<25s} {'Score':<8s} {'dv':<8s} {'Water':<7s} {'Conf':<8s} {'Reason'}")
    lines.append(f"  {'-'*75}")
    for i, r in enumerate(result["rankings"][:7]):
        marker = " <<< BEST" if i == 0 else ""
        lines.append(f"  {i+1:<5d} {r['name']:<25s} {r['score']:<8.1f} {r['delta_v']:<8.1f} "
                     f"{r['water_pct']:<7.0f} {r['confidence']:<8s} {r['reason'][:30]}{marker}")

    if best and econ:
        lines.append(f"\n--- PROJECTED RESULTS ({best['name']}, 5yr) ---")
        lines.append(f"  Revenue: ${econ.total_revenue_usd:,.0f}")
        lines.append(f"  Cost: ${econ.total_mission_cost_usd:,.0f}")
        lines.append(f"  Net: ${econ.net_profit_usd:,.0f}")
        lines.append(f"  ROI: {econ.roi_pct:,.0f}%")

    # Show all available objectives
    lines.append(f"\n--- ALL OBJECTIVES ---")
    for o in OBJECTIVES:
        marker = " [SELECTED]" if o.id == obj.id else ""
        lines.append(f"  {o.id:<25s} {o.name}{marker}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
