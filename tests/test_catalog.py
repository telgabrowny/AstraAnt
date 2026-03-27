"""Tests for the catalog loader."""

from astraant.catalog import Catalog


def test_catalog_loads():
    """Catalog loads without errors and finds entries."""
    cat = Catalog()
    counts = cat.summary()
    assert counts["parts"] > 0, "No parts found in catalog"
    assert counts["asteroids"] > 0, "No asteroids found in catalog"
    assert counts["species"] > 0, "No species found in catalog"


def test_part_lookup():
    """Can look up a specific part by ID."""
    cat = Catalog()
    esp32 = cat.get_part("esp32_s3")
    assert esp32 is not None, "ESP32-S3 not found"
    assert esp32.get("category") == "compute"


def test_asteroid_lookup():
    """Can look up a specific asteroid by ID."""
    cat = Catalog()
    bennu = cat.get_asteroid("bennu")
    assert bennu is not None, "Bennu not found"
    assert bennu.get("physical", {}).get("spectral_class") in ("B", "C", "Cb")


def test_parts_by_category():
    """Can filter parts by category."""
    cat = Catalog()
    sensors = cat.parts_by_category("sensor")
    assert len(sensors) >= 3, f"Expected at least 3 sensors, got {len(sensors)}"


def test_asteroid_accessibility_filter():
    """Can filter asteroids by delta-v."""
    cat = Catalog()
    accessible = cat.asteroids_by_accessibility(5.0)
    # Bennu, Ryugu, Itokawa, 2008 EV5 should be under 5 km/s
    assert len(accessible) >= 2, f"Expected at least 2 accessible asteroids, got {len(accessible)}"


def test_part_has_price():
    """Individual parts should have at least one supplier with a price."""
    cat = Catalog()
    # Skip composite catalog entries (phase2 equipment aggregate)
    skip_categories = {"phase2_industrial"}
    for part in cat.parts:
        if part.get("category") in skip_categories:
            continue
        price = part.best_price()
        assert price is not None, f"Part {part.id} has no price"
        assert price > 0, f"Part {part.id} has zero/negative price"
