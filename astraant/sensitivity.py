"""Sensitivity analysis -- which parameters matter most for mission economics.

Runs the feasibility calculator across a range of values for each parameter,
holding others constant, to identify which factors have the biggest impact
on break-even and total cost. Essential for the billionaire pitch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .feasibility import (
    MissionConfig, SwarmConfig, analyze_mission, LAUNCH_VEHICLES,
)
from .catalog import Catalog


@dataclass
class SensitivityResult:
    """Result of varying one parameter."""
    parameter: str
    values: list[float]
    break_even_cycles: list[int]
    total_cost: list[float]
    revenue_per_cycle: list[float]
    baseline_idx: int  # Which index is the baseline value


def run_sensitivity(baseline: MissionConfig | None = None,
                    catalog: Catalog | None = None) -> list[SensitivityResult]:
    """Run sensitivity analysis on key parameters.

    Returns a list of SensitivityResult, one per parameter varied.
    """
    if baseline is None:
        baseline = MissionConfig(
            swarm=SwarmConfig(workers=100, taskmasters=5, surface_ants=3, track="b"),
            asteroid_id="bennu",
            destination="lunar_orbit",
            launch_vehicle="starship_conservative",
        )
    if catalog is None:
        catalog = Catalog()

    results = []

    # 1. Worker count
    worker_counts = [10, 25, 50, 100, 200, 500]
    r = _sweep_workers(baseline, catalog, worker_counts)
    results.append(r)

    # 2. Launch cost ($/kg)
    launch_costs = [100, 200, 500, 1000, 2700, 5000]
    r = _sweep_launch_cost(baseline, catalog, launch_costs)
    results.append(r)

    # 3. Destination
    destinations = ["earth_return", "lunar_orbit", "mars_orbit"]
    r = _sweep_destination(baseline, catalog, destinations)
    results.append(r)

    # 4. Track
    tracks = ["a", "b", "c"]
    r = _sweep_track(baseline, catalog, tracks)
    results.append(r)

    return results


def _sweep_workers(base, catalog, counts):
    be, costs, revs = [], [], []
    base_idx = 0
    for i, n in enumerate(counts):
        m = MissionConfig(
            swarm=SwarmConfig(workers=n, taskmasters=max(1, n // 20),
                              surface_ants=base.swarm.surface_ants,
                              track=base.swarm.track),
            asteroid_id=base.asteroid_id,
            destination=base.destination,
            launch_vehicle=base.launch_vehicle,
        )
        r = analyze_mission(m, catalog)
        be.append(r.break_even_cycles)
        costs.append(r.cost_estimate.total_first_cycle_usd)
        revs.append(r.revenue_per_cycle_usd)
        if n == base.swarm.workers:
            base_idx = i
    return SensitivityResult("worker_count", counts, be, costs, revs, base_idx)


def _sweep_launch_cost(base, catalog, costs_per_kg):
    be, costs, revs = [], [], []
    base_idx = 0
    for i, cpk in enumerate(costs_per_kg):
        m = MissionConfig(
            swarm=SwarmConfig(workers=base.swarm.workers,
                              taskmasters=base.swarm.taskmasters,
                              surface_ants=base.swarm.surface_ants,
                              track=base.swarm.track),
            asteroid_id=base.asteroid_id,
            destination=base.destination,
            launch_vehicle="custom",
        )
        # Temporarily inject custom launch cost
        LAUNCH_VEHICLES["custom"] = {"cost_per_kg_usd": cpk, "payload_leo_kg": 100000}
        r = analyze_mission(m, catalog)
        be.append(r.break_even_cycles)
        costs.append(r.cost_estimate.total_first_cycle_usd)
        revs.append(r.revenue_per_cycle_usd)
        if cpk == 500:
            base_idx = i
    # Clean up
    LAUNCH_VEHICLES.pop("custom", None)
    return SensitivityResult("launch_cost_per_kg", costs_per_kg, be, costs, revs, base_idx)


def _sweep_destination(base, catalog, destinations):
    be, costs, revs = [], [], []
    base_idx = 0
    for i, dest in enumerate(destinations):
        m = MissionConfig(
            swarm=SwarmConfig(workers=base.swarm.workers,
                              taskmasters=base.swarm.taskmasters,
                              surface_ants=base.swarm.surface_ants,
                              track=base.swarm.track),
            asteroid_id=base.asteroid_id,
            destination=dest,
            launch_vehicle=base.launch_vehicle,
        )
        r = analyze_mission(m, catalog)
        be.append(r.break_even_cycles)
        costs.append(r.cost_estimate.total_first_cycle_usd)
        revs.append(r.revenue_per_cycle_usd)
        if dest == base.destination:
            base_idx = i
    return SensitivityResult("destination", list(range(len(destinations))), be, costs, revs, base_idx)


def _sweep_track(base, catalog, tracks):
    be, costs, revs = [], [], []
    base_idx = 0
    for i, track in enumerate(tracks):
        m = MissionConfig(
            swarm=SwarmConfig(workers=base.swarm.workers,
                              taskmasters=base.swarm.taskmasters,
                              surface_ants=base.swarm.surface_ants,
                              track=track),
            asteroid_id=base.asteroid_id,
            destination=base.destination,
            launch_vehicle=base.launch_vehicle,
        )
        r = analyze_mission(m, catalog)
        be.append(r.break_even_cycles)
        costs.append(r.cost_estimate.total_first_cycle_usd)
        revs.append(r.revenue_per_cycle_usd)
        if track == base.swarm.track:
            base_idx = i
    return SensitivityResult("extraction_track", list(range(len(tracks))), be, costs, revs, base_idx)


def format_sensitivity(results: list[SensitivityResult]) -> str:
    """Format sensitivity results as a readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("SENSITIVITY ANALYSIS")
    lines.append("Which parameters matter most for mission economics?")
    lines.append("=" * 70)

    labels = {
        "worker_count": ("Worker Count", [str(v) for v in [10, 25, 50, 100, 200, 500]]),
        "launch_cost_per_kg": ("Launch $/kg", ["$100", "$200", "$500", "$1K", "$2.7K", "$5K"]),
        "destination": ("Destination", ["Earth", "Lunar", "Mars"]),
        "extraction_track": ("Track", ["A(mech)", "B(bio)", "C(hybrid)"]),
    }

    for r in results:
        name, val_labels = labels.get(r.parameter, (r.parameter, [str(v) for v in r.values]))

        lines.append(f"\n--- {name} ---")
        lines.append(f"  {'Value':<12s} {'Total Cost':<15s} {'Revenue/Cyc':<15s} {'Break-Even'}")
        lines.append(f"  {'-'*55}")

        for i in range(len(r.values)):
            label = val_labels[i] if i < len(val_labels) else str(r.values[i])
            marker = " <-- baseline" if i == r.baseline_idx else ""

            def fmt_usd(v):
                if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
                if v >= 1_000: return f"${v/1_000:.0f}K"
                return f"${v:.0f}"

            be_str = f"{r.break_even_cycles[i]} cyc" if r.break_even_cycles[i] > 0 else "NEVER"

            lines.append(f"  {label:<12s} {fmt_usd(r.total_cost[i]):<15s} "
                         f"{fmt_usd(r.revenue_per_cycle[i]):<15s} {be_str}{marker}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
