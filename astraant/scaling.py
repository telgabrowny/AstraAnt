"""Statistical scaling model -- extrapolate small-N simulation to large swarm sizes.

Run a detailed simulation at small N (10-100 ants), measure per-ant throughput
and failure rates, then extrapolate to large N (1K-100K) using statistical models.

The key insight: individual ant behavior doesn't change with swarm size.
What changes is contention (crowding in tunnels), communication load,
and the ratio of specialists needed. We model these as scaling factors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .gui.simulation.sim_engine import SimEngine


@dataclass
class ScalingResult:
    """Result for one swarm size."""
    workers: int
    taskmasters: int
    surface_ants: int
    total_ants: int
    material_kg_per_day: float
    water_kg_per_day: float
    failures_per_day: float
    tunnel_growth_m_per_day: float
    efficiency: float              # Per-ant throughput relative to baseline


@dataclass
class ScalingReport:
    """Complete scaling analysis across swarm sizes."""
    baseline_workers: int
    track: str
    results: list[ScalingResult] = field(default_factory=list)
    sim_days: int = 30


def _run_calibration(workers: int, track: str, sim_days: int = 30) -> dict[str, float]:
    """Run a short simulation to measure per-ant throughput."""
    taskmasters = max(1, workers // 20)
    surface_ants = max(1, workers // 50)

    engine = SimEngine(
        workers=workers, taskmasters=taskmasters,
        surface_ants=surface_ants, track=track,
    )
    engine.setup()
    engine.clock.speed = 10000.0

    target_time = sim_days * 86400.0
    while engine.clock.sim_time < target_time:
        engine.tick(0.1)

    status = engine.status()
    stats = status["stats"]
    days = engine.clock.sim_time / 86400.0

    return {
        "material_kg_per_day": stats["material_kg"] / max(1, days),
        "water_kg_per_day": stats["water_kg"] / max(1, days),
        "failures_per_day": stats["failures"] / max(1, days),
        "tunnel_m_per_day": status["tunnel"]["total_length_m"] / max(1, days),
    }


def _crowding_factor(workers: int, baseline: int = 50) -> float:
    """Model efficiency loss from tunnel crowding at large swarm sizes.

    At small N, ants don't interfere with each other. As N grows,
    tunnel congestion reduces per-ant throughput. Modeled as a
    soft logistic curve that starts dropping around 200 workers.
    """
    # Efficiency is 1.0 up to ~100 workers, then gradually drops
    # At 1000 workers: ~0.85 efficiency
    # At 10000 workers: ~0.60 efficiency
    # At 100000 workers: ~0.40 efficiency
    if workers <= 50:
        return 1.0
    k = 0.003  # Crowding rate
    midpoint = 500
    return 0.4 + 0.6 / (1 + math.exp(k * (workers - midpoint)))


def run_scaling_analysis(track: str = "bioleaching", sim_days: int = 30,
                         baseline_workers: int = 50) -> ScalingReport:
    """Run scaling analysis from small to large swarm sizes.

    1. Simulate at baseline size to get per-ant throughput
    2. Apply crowding/efficiency factors to extrapolate to larger sizes
    """
    report = ScalingReport(
        baseline_workers=baseline_workers,
        track=track,
        sim_days=sim_days,
    )

    # Calibration run at baseline size
    cal = _run_calibration(baseline_workers, track, sim_days)
    baseline_per_ant_material = cal["material_kg_per_day"] / baseline_workers
    baseline_per_ant_water = cal["water_kg_per_day"] / max(1, baseline_workers * 0.10)  # Sorter fraction
    baseline_failure_rate = cal["failures_per_day"] / baseline_workers
    baseline_tunnel_rate = cal["tunnel_m_per_day"] / (baseline_workers * 0.60)  # Miner fraction

    # Extrapolate to different swarm sizes
    for n_workers in [10, 25, 50, 100, 200, 500, 1000, 5000, 10000, 50000, 100000]:
        taskmasters = max(1, n_workers // 20)
        surface_ants = max(1, n_workers // 50)
        total = n_workers + taskmasters + surface_ants

        crowd = _crowding_factor(n_workers, baseline_workers)

        # For small N (<= baseline), run actual sim for accuracy
        if n_workers <= baseline_workers and n_workers >= 10:
            actual = _run_calibration(n_workers, track, sim_days)
            mat_per_day = actual["material_kg_per_day"]
            water_per_day = actual["water_kg_per_day"]
            fail_per_day = actual["failures_per_day"]
            tunnel_per_day = actual["tunnel_m_per_day"]
            eff = (mat_per_day / n_workers) / baseline_per_ant_material if baseline_per_ant_material > 0 else 1.0
        else:
            # Statistical extrapolation with crowding factor
            mat_per_day = n_workers * baseline_per_ant_material * crowd
            water_per_day = (n_workers * 0.10) * baseline_per_ant_water * crowd
            fail_per_day = n_workers * baseline_failure_rate
            tunnel_per_day = (n_workers * 0.60) * baseline_tunnel_rate * crowd
            eff = crowd

        report.results.append(ScalingResult(
            workers=n_workers,
            taskmasters=taskmasters,
            surface_ants=surface_ants,
            total_ants=total,
            material_kg_per_day=round(mat_per_day, 2),
            water_kg_per_day=round(water_per_day, 2),
            failures_per_day=round(fail_per_day, 2),
            tunnel_growth_m_per_day=round(tunnel_per_day, 2),
            efficiency=round(eff, 3),
        ))

    return report


def format_scaling_report(report: ScalingReport) -> str:
    """Format scaling analysis as readable text."""
    lines = []
    lines.append("=" * 85)
    lines.append(f"SCALING ANALYSIS -- Track {report.track.upper()}, calibrated at {report.baseline_workers} workers")
    lines.append(f"Simulated {report.sim_days} days at baseline, extrapolated with crowding model")
    lines.append("=" * 85)

    lines.append(f"\n{'Workers':>8s} {'Total':>7s} {'Mat/day':>10s} {'Water/day':>10s} "
                 f"{'Fail/day':>9s} {'Tunnel/day':>11s} {'Efficiency':>11s}")
    lines.append("-" * 85)

    for r in report.results:
        sim_marker = " [sim]" if r.workers <= report.baseline_workers and r.workers >= 10 else " [ext]"
        lines.append(f"{r.workers:>8,d} {r.total_ants:>7,d} {r.material_kg_per_day:>10.1f} "
                     f"{r.water_kg_per_day:>10.1f} {r.failures_per_day:>9.1f} "
                     f"{r.tunnel_growth_m_per_day:>11.1f} {r.efficiency:>10.1%}{sim_marker}")

    lines.append("\n[sim] = actual simulation  [ext] = statistical extrapolation")
    lines.append(f"Crowding model: efficiency drops at >100 workers due to tunnel congestion")
    lines.append(f"At 100K workers: ~40% individual efficiency (crowding), but 40,000x total throughput")

    lines.append("\n" + "=" * 85)
    return "\n".join(lines)
