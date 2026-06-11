"""Tests for catalog validation (astraant/validation.py)."""

from pathlib import Path

import yaml

from astraant.catalog import Catalog
from astraant.validation import ERROR, WARNING, has_errors, validate_catalog


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


def _good_part(part_id="part_ok"):
    return {
        "id": part_id,
        "name": "Good Part",
        "category": "sensor",
        "specs": {"mass_g": 9.0},
        "sourcing": {
            "suppliers": [
                {"name": "DigiKey", "price_usd": 3.5,
                 "date_checked": "2026-03-26"},
            ],
        },
    }


def _catalog(tmp_path, parts=(), asteroids=()):
    for i, p in enumerate(parts):
        _write_yaml(tmp_path / "parts" / f"part_{i}.yaml", p)
    for i, a in enumerate(asteroids):
        _write_yaml(tmp_path / "asteroids" / f"ast_{i}.yaml", a)
    return Catalog(catalog_dir=tmp_path)


def test_good_part_produces_no_issues(tmp_path):
    issues = validate_catalog(_catalog(tmp_path, parts=[_good_part()]))
    assert issues == []


def test_missing_id_is_error(tmp_path):
    bad = _good_part()
    del bad["id"]
    issues = validate_catalog(_catalog(tmp_path, parts=[bad]))
    assert has_errors(issues)
    assert any("missing 'id'" in i.message for i in issues)


def test_duplicate_ids_are_error(tmp_path):
    issues = validate_catalog(_catalog(
        tmp_path, parts=[_good_part("dup"), _good_part("dup")]))
    assert any(i.severity == ERROR and "duplicate id" in i.message
               for i in issues)


def test_non_numeric_mass_is_error(tmp_path):
    bad = _good_part()
    bad["specs"]["mass_g"] = "nine grams"
    issues = validate_catalog(_catalog(tmp_path, parts=[bad]))
    assert any(i.severity == ERROR and "mass_g" in i.message for i in issues)


def test_missing_suppliers_is_warning_not_error(tmp_path):
    bad = _good_part()
    bad["sourcing"] = {"suppliers": []}
    issues = validate_catalog(_catalog(tmp_path, parts=[bad]))
    assert not has_errors(issues)
    assert any(i.severity == WARNING and "no suppliers" in i.message
               for i in issues)


def test_bad_price_is_error(tmp_path):
    bad = _good_part()
    bad["sourcing"]["suppliers"][0]["price_usd"] = "cheap"
    issues = validate_catalog(_catalog(tmp_path, parts=[bad]))
    assert any(i.severity == ERROR and "price_usd" in i.message
               for i in issues)


def test_bad_date_checked_is_warning(tmp_path):
    bad = _good_part()
    bad["sourcing"]["suppliers"][0]["date_checked"] = "March 2026"
    issues = validate_catalog(_catalog(tmp_path, parts=[bad]))
    assert not has_errors(issues)
    assert any("date_checked" in i.message for i in issues)


def test_asteroid_missing_rotation_is_warning(tmp_path):
    ast = {"id": "ast_x", "name": "X", "composition": {"bulk": {}},
           "physical": {"diameter_m": 100}}
    issues = validate_catalog(_catalog(tmp_path, asteroids=[ast]))
    assert not has_errors(issues)
    assert any("rotation_period_hours" in i.message for i in issues)


def test_asteroid_negative_rotation_is_error(tmp_path):
    ast = {"id": "ast_x", "name": "X", "composition": {"bulk": {}},
           "physical": {"rotation_period_hours": -2.0}}
    issues = validate_catalog(_catalog(tmp_path, asteroids=[ast]))
    assert has_errors(issues)


def test_shipped_catalog_has_no_errors():
    """The real catalog must always validate clean (warnings allowed)."""
    issues = validate_catalog(Catalog())
    errors = [i for i in issues if i.severity == ERROR]
    assert errors == [], "\n".join(str(i) for i in errors)
