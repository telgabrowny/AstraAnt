"""Integration tests for boulder encounter and clearing in the sim engine."""

from astraant.gui.simulation.sim_engine import SimEngine


def test_boulder_encounter_blocks_dig():
    """When a boulder is active, dig position should not advance."""
    engine = SimEngine(workers=10, taskmasters=1, surface_ants=1, track="mechanical")
    engine.setup()
    engine.clock.speed = 10000

    # Force a boulder at the work face
    engine._boulder_active = True
    engine._boulder_hardness = 0.85
    engine._boulder_hp = 100.0  # Very high HP so it won't clear quickly
    engine._boulder_zone = "silicate_bulk"
    engine._boulders_encountered = 1

    dig_before = list(engine._dig_position)

    # Run several ticks
    for _ in range(200):
        engine.tick(0.1)

    # Dig position should not have advanced
    assert engine._dig_position == dig_before, (
        f"Dig should not advance while boulder active: {dig_before} -> {engine._dig_position}"
    )


def test_boulder_eventually_clears():
    """A boulder with finite HP should eventually be cleared by mining."""
    engine = SimEngine(workers=20, taskmasters=1, surface_ants=1, track="mechanical")
    engine.setup()
    engine.clock.speed = 50000

    # Force a boulder with low HP
    engine._boulder_active = True
    engine._boulder_hardness = 0.80
    engine._boulder_hp = 0.5  # Low HP -- should clear quickly
    engine._boulder_zone = "metal_grain"
    engine._boulders_encountered = 1

    # Run until it clears or timeout
    cleared = False
    for _ in range(500):
        events = engine.tick(0.1)
        for e in events:
            if e.get("type") == "boulder_cleared":
                cleared = True
                break
        if cleared:
            break

    assert cleared, "Boulder should have been cleared"
    assert not engine._boulder_active
    assert engine._boulders_cleared >= 1
    assert engine.stats.boulders_cleared >= 1


def test_boulder_stats_in_status():
    """Status dict should include boulder stats."""
    engine = SimEngine(workers=5, taskmasters=1, surface_ants=1, track="mechanical")
    engine.setup()
    engine._boulders_encountered = 3
    engine._boulders_cleared = 2
    engine.stats.boulders_encountered = 3
    engine.stats.boulders_cleared = 2
    engine._boulder_active = True

    status = engine.status()
    stats = status["stats"]
    assert stats["boulders_encountered"] == 3
    assert stats["boulders_cleared"] == 2
    assert stats["boulder_active"] is True


def test_simulation_produces_boulders():
    """A real simulation should naturally encounter boulders over time."""
    from astraant.gui.simulation.asteroid_grid import AsteroidGrid

    engine = SimEngine(workers=50, taskmasters=3, surface_ants=1, track="mechanical")
    engine.setup()
    # Use a metallic asteroid (15% boulder rate) for reliable test
    engine.grid = AsteroidGrid(radius_m=50, asteroid_type="metallic", seed=42)
    engine.clock.speed = 100000

    target_sim_time = 30 * 86400.0  # 30 days
    while engine.clock.sim_time < target_sim_time:
        engine.tick(0.1)

    assert engine.stats.boulders_encountered > 0, (
        f"30 days on metallic asteroid should encounter boulders. "
        f"Dumps: {engine.stats.total_dump_cycles}, "
        f"dig depth: {abs(engine._dig_position[1])}"
    )
