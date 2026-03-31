"""Tests for the nautilus mechanics spiral position tracking."""

from astraant.nautilus_mechanics import run_multi_cycle, NautilusState


def test_nautilus_spiral_positions_grow():
    """chamber_positions list grows when septa trigger (new chambers added)."""
    state, summaries, events = run_multi_cycle(
        cycles=10, initial_diameter_m=10, current_amps=2000, growth_factor=1.2)
    # Must have more than the initial position (at least 1 new chamber)
    assert len(state.chamber_positions) > 1, (
        f"Only {len(state.chamber_positions)} chamber(s) -- "
        f"expected growth over 10 cycles")


def test_nautilus_spiral_not_concentric():
    """Chamber positions must have different (x,y), not all at (0,0)."""
    state, summaries, events = run_multi_cycle(
        cycles=10, initial_diameter_m=10, current_amps=2000, growth_factor=1.2)
    assert len(state.chamber_positions) >= 2, "Need at least 2 chambers for this test"
    # First chamber is at origin; subsequent ones must NOT be at origin
    non_origin = [
        (x, y) for x, y, r, gen in state.chamber_positions[1:]
        if abs(x) > 0.1 or abs(y) > 0.1
    ]
    assert len(non_origin) > 0, (
        "All chambers are at (0,0) -- spiral placement is broken. "
        f"Positions: {state.chamber_positions}")


def test_nautilus_spiral_radius_increases():
    """Each generation must have a larger radius than the previous one."""
    state, summaries, events = run_multi_cycle(
        cycles=10, initial_diameter_m=10, current_amps=2000, growth_factor=1.2)
    assert len(state.chamber_positions) >= 2, "Need at least 2 chambers for this test"
    radii = [r for x, y, r, gen in state.chamber_positions]
    for i in range(1, len(radii)):
        assert radii[i] > radii[i - 1], (
            f"Chamber {i} radius {radii[i]:.2f}m is not larger than "
            f"chamber {i-1} radius {radii[i-1]:.2f}m")
