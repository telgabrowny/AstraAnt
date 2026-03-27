"""Performance profiler for the simulation engine.

Measures: tick time, memory usage, entity counts, and identifies
bottlenecks. Run with: python tests/profile_sim.py
"""

import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from astraant.gui.simulation.sim_engine import SimEngine


def profile_tick_performance():
    """Measure how long each tick takes at different swarm sizes."""
    print("TICK PERFORMANCE PROFILE")
    print("=" * 60)

    for n_workers in [10, 50, 100, 200]:
        engine = SimEngine(workers=n_workers, taskmasters=max(1, n_workers // 20),
                           surface_ants=2, track="b")
        engine.setup()
        engine.clock.speed = 10000

        # Warm up
        for _ in range(100):
            engine.tick(0.016)

        # Measure 1000 ticks
        start = time.perf_counter()
        for _ in range(1000):
            engine.tick(0.016)
        elapsed = time.perf_counter() - start

        avg_ms = elapsed / 1000 * 1000
        fps_equiv = 1000 / avg_ms if avg_ms > 0 else 999

        print(f"  {n_workers:>4d} workers: {avg_ms:.3f} ms/tick "
              f"({fps_equiv:.0f} fps equivalent)")


def profile_memory_growth():
    """Check if memory grows over time (unbounded lists, etc)."""
    print("\nMEMORY GROWTH PROFILE")
    print("=" * 60)

    engine = SimEngine(workers=50, taskmasters=3, surface_ants=2, track="b")
    engine.setup()
    engine.clock.speed = 100000

    import tracemalloc
    tracemalloc.start()

    snapshot1 = tracemalloc.take_snapshot()

    # Run for 5000 ticks (simulates ~minutes of gameplay at 60fps)
    for _ in range(5000):
        engine.tick(0.016)

    snapshot2 = tracemalloc.take_snapshot()

    # Run for another 5000 ticks
    for _ in range(5000):
        engine.tick(0.016)

    snapshot3 = tracemalloc.take_snapshot()

    # Compare
    stats1 = snapshot2.compare_to(snapshot1, "lineno")
    stats2 = snapshot3.compare_to(snapshot2, "lineno")

    print("  After 5000 ticks (top memory growers):")
    for stat in stats1[:5]:
        print(f"    {stat}")

    print("\n  After 10000 ticks (top memory growers):")
    for stat in stats2[:5]:
        print(f"    {stat}")

    current, peak = tracemalloc.get_traced_memory()
    print(f"\n  Current memory: {current / 1024:.0f} KB")
    print(f"  Peak memory: {peak / 1024:.0f} KB")
    tracemalloc.stop()


def profile_status_call():
    """Measure how expensive status() is."""
    print("\nSTATUS() CALL PROFILE")
    print("=" * 60)

    engine = SimEngine(workers=100, taskmasters=5, surface_ants=3, track="b")
    engine.setup()
    engine.clock.speed = 10000

    # Warm up
    for _ in range(500):
        engine.tick(0.016)

    # Measure status() calls
    start = time.perf_counter()
    for _ in range(1000):
        engine.status()
    elapsed = time.perf_counter() - start

    avg_us = elapsed / 1000 * 1_000_000
    print(f"  status() avg: {avg_us:.0f} us/call")
    print(f"  At 60 fps: {avg_us * 60 / 1000:.1f} ms/frame just for status()")
    print(f"  With caching (every 30 frames): {avg_us * 2 / 1000:.3f} ms/frame")


def profile_entity_counts():
    """Check how many sim objects exist over time."""
    print("\nSIM OBJECT COUNT PROFILE")
    print("=" * 60)

    engine = SimEngine(workers=50, taskmasters=3, surface_ants=2, track="b")
    engine.setup()
    engine.clock.speed = 100000

    # Enable manufacturing to spawn new ants
    engine.manufacturing.enabled = True
    engine.manufacturing.ants_queued = 10

    for phase in ["initial", "after 2000 ticks", "after 5000 ticks"]:
        if phase != "initial":
            n = 2000 if "2000" in phase else 3000
            for _ in range(n):
                engine.tick(0.016)

        print(f"  {phase}:")
        print(f"    Agents: {len(engine.agents)}")
        print(f"    Tunnel segments: {len(engine.tunnel.segments)}")
        print(f"    Tunnel nodes: {len(engine.tunnel.nodes)}")
        print(f"    Voxels generated: {len(engine.grid._voxels)}")
        print(f"    Event log: {len(engine.event_log)}")
        print(f"    Active events: {len(engine.event_system.active_events)}")
        print(f"    Anomalies: {len(engine.anomaly_detector.anomalies)}")
        print(f"    Economy pods in transit: {len(engine.economy.pods_in_transit)}")


if __name__ == "__main__":
    profile_tick_performance()
    profile_memory_growth()
    profile_status_call()
    profile_entity_counts()

    print("\n" + "=" * 60)
    print("DONE. Key metrics to watch:")
    print("  - Tick time should be <1ms for 60fps target")
    print("  - Memory should not grow linearly with tick count")
    print("  - status() should be <100us after caching")
    print("  - Event log should stay capped at ~500-1000 entries")
