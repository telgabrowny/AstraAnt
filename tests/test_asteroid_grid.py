"""Tests for asteroid grid voxel system -- hardness, boulders, material classes."""

from astraant.gui.simulation.asteroid_grid import (
    AsteroidGrid, Voxel, ASTEROID_HARDNESS, ZONE_HARDNESS_MODIFIER,
)


def test_voxel_material_class_thresholds():
    """Material class boundaries are correct."""
    assert Voxel(0, 0, 0, hardness=0.05).material_class == "dust"
    assert Voxel(0, 0, 0, hardness=0.20).material_class == "regolith"
    assert Voxel(0, 0, 0, hardness=0.40).material_class == "gravel"
    assert Voxel(0, 0, 0, hardness=0.60).material_class == "cobble"
    assert Voxel(0, 0, 0, hardness=0.80).material_class == "boulder"
    assert Voxel(0, 0, 0, hardness=0.95).material_class == "megalith"


def test_voxel_is_boulder():
    """is_boulder flag triggers at hardness >= 0.75."""
    assert not Voxel(0, 0, 0, hardness=0.74).is_boulder
    assert Voxel(0, 0, 0, hardness=0.75).is_boulder
    assert Voxel(0, 0, 0, hardness=0.95).is_boulder


def test_rubble_pile_mostly_soft():
    """Rubble pile asteroids should be mostly dust/regolith/gravel."""
    grid = AsteroidGrid(radius_m=30, asteroid_type="rubble_pile", seed=42)
    counts = {"soft": 0, "hard": 0}
    for x in range(-8, 9):
        for y in range(-8, 9):
            for z in range(-8, 9):
                v = grid.get_voxel(x, y, z)
                if v.zone_type == "void":
                    continue
                if v.hardness < 0.55:
                    counts["soft"] += 1
                else:
                    counts["hard"] += 1
    total = counts["soft"] + counts["hard"]
    soft_pct = counts["soft"] / total
    assert soft_pct > 0.70, f"Rubble pile should be >70% soft, got {soft_pct:.0%}"


def test_monolithic_harder_than_rubble():
    """Monolithic asteroids should have higher average hardness than rubble piles."""
    rubble = AsteroidGrid(radius_m=30, asteroid_type="rubble_pile", seed=42)
    mono = AsteroidGrid(radius_m=30, asteroid_type="monolithic", seed=42)

    def avg_hardness(grid):
        total, count = 0.0, 0
        for x in range(-5, 6):
            for y in range(-5, 6):
                for z in range(-5, 6):
                    v = grid.get_voxel(x, y, z)
                    if v.zone_type != "void":
                        total += v.hardness
                        count += 1
        return total / count if count else 0

    assert avg_hardness(mono) > avg_hardness(rubble)


def test_metallic_has_most_boulders():
    """Metallic asteroids should produce the most boulders."""
    boulder_counts = {}
    for atype in ["rubble_pile", "monolithic", "metallic"]:
        grid = AsteroidGrid(radius_m=20, asteroid_type=atype, seed=42)
        boulders = 0
        for x in range(-8, 9):
            for y in range(-8, 9):
                for z in range(-8, 9):
                    v = grid.get_voxel(x, y, z)
                    if v.zone_type != "void" and v.is_boulder:
                        boulders += 1
        boulder_counts[atype] = boulders
    assert boulder_counts["metallic"] > boulder_counts["rubble_pile"]


def test_center_harder_than_surface():
    """Voxels near the center should be slightly harder (compaction)."""
    grid = AsteroidGrid(radius_m=30, asteroid_type="rubble_pile", seed=99)

    def avg_hardness_at_dist(dist_range):
        import math
        total, count = 0.0, 0
        for x in range(-25, 26):
            for z in range(-25, 26):
                y = 0
                dist = math.sqrt(x*x + y*y + z*z)
                if dist_range[0] <= dist <= dist_range[1]:
                    v = grid.get_voxel(x, y, z)
                    if v.zone_type != "void":
                        total += v.hardness
                        count += 1
        return total / count if count else 0

    center_avg = avg_hardness_at_dist((0, 8))
    surface_avg = avg_hardness_at_dist((22, 29))
    assert center_avg > surface_avg, (
        f"Center ({center_avg:.3f}) should be harder than surface ({surface_avg:.3f})"
    )


def test_hardness_profiles_exist():
    """All documented asteroid types have hardness profiles."""
    for atype in ["rubble_pile", "monolithic", "metallic", "mixed"]:
        assert atype in ASTEROID_HARDNESS
        profile = ASTEROID_HARDNESS[atype]
        assert "base_mean" in profile
        assert "boulder_probability" in profile
        assert "megalith_probability" in profile


def test_zone_hardness_modifiers_sensible():
    """Zone hardness modifiers match physical intuition."""
    assert ZONE_HARDNESS_MODIFIER["metal_grain"] > 0, "Metal should be harder"
    assert ZONE_HARDNESS_MODIFIER["organic_rich"] < 0, "Organics should be softer"
    assert ZONE_HARDNESS_MODIFIER["hydrated_matrix"] < 0, "Clay should be softer"


def test_mine_voxel_marks_mined():
    """Mining a voxel marks it and returns composition."""
    grid = AsteroidGrid(radius_m=30, seed=42)
    v = grid.mine_voxel(0, -3, 0)
    assert v.mined
    assert v.zone_type != "void"
    assert 0.0 <= v.hardness <= 1.0
    assert grid.total_mined == 1


def test_mine_voxel_idempotent():
    """Mining the same voxel twice should not double-count."""
    grid = AsteroidGrid(radius_m=30, seed=42)
    v1 = grid.mine_voxel(0, -3, 0)
    v2 = grid.mine_voxel(0, -3, 0)
    assert v1 is v2
    assert grid.total_mined == 1


def test_void_voxels_outside_radius():
    """Voxels beyond the asteroid radius should be void."""
    grid = AsteroidGrid(radius_m=10, seed=42)
    v = grid.get_voxel(15, 0, 0)
    assert v.zone_type == "void"
    assert v.mined  # Void voxels are pre-marked as mined


def test_reveal_area_marks_voxels():
    """reveal_area should mark nearby voxels as revealed."""
    grid = AsteroidGrid(radius_m=30, seed=42)
    revealed = grid.reveal_area(0, -5, 0, radius=3)
    assert len(revealed) > 0
    assert all(v.revealed for v in revealed)
    assert grid.total_revealed == len(revealed)
    # Calling again should return empty (already revealed)
    revealed2 = grid.reveal_area(0, -5, 0, radius=3)
    assert len(revealed2) == 0


def test_unknown_asteroid_type_uses_mixed():
    """Unrecognized asteroid type should fall back to 'mixed' profile."""
    grid = AsteroidGrid(radius_m=10, asteroid_type="banana", seed=42)
    v = grid.get_voxel(0, 0, 0)
    assert 0.0 <= v.hardness <= 1.0  # Should not crash


def test_summary_includes_material_counts():
    """Grid summary should report material class distribution."""
    grid = AsteroidGrid(radius_m=20, seed=42)
    for x in range(-5, 6):
        for y in range(-5, 6):
            for z in range(-5, 6):
                grid.get_voxel(x, y, z)
    summary = grid.summary()
    assert "material_counts" in summary
    assert "asteroid_type" in summary
    assert sum(summary["material_counts"].values()) > 0


def test_default_asteroid_type_is_rubble_pile():
    """Default grid should be rubble_pile for backward compatibility."""
    grid = AsteroidGrid(radius_m=20, seed=42)
    assert grid.asteroid_type == "rubble_pile"
