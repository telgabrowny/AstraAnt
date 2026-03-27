"""Catalog loader — reads YAML part/species/asteroid/reagent files into a searchable database."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


CATALOG_DIR = Path(__file__).parent.parent / "catalog"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file, returning its contents as a dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_directory(subdir: str) -> list[dict[str, Any]]:
    """Load all YAML files from a catalog subdirectory."""
    dirpath = CATALOG_DIR / subdir
    if not dirpath.exists():
        return []
    items = []
    for filepath in sorted(dirpath.glob("*.yaml")):
        try:
            data = _load_yaml(filepath)
            data["_source_file"] = str(filepath.name)
            items.append(data)
        except Exception as e:
            print(f"Warning: failed to load {filepath}: {e}")
    return items


class CatalogEntry:
    """Wrapper around a catalog YAML dict with attribute access."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"No field '{name}' in catalog entry '{self.id}'")

    def __repr__(self) -> str:
        return f"CatalogEntry({self._data.get('id', '?')})"

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def best_price(self) -> float | None:
        """Return the lowest current price across all suppliers."""
        suppliers = self._data.get("sourcing", {}).get("suppliers", [])
        prices = [s["price_usd"] for s in suppliers if "price_usd" in s]
        return min(prices) if prices else None

    def price_trend(self) -> list[dict[str, Any]]:
        """Return price history sorted by date."""
        history = self._data.get("sourcing", {}).get("price_history", [])
        return sorted(history, key=lambda h: h.get("date", ""))

    def days_since_price_check(self) -> int | None:
        """Days since the most recent supplier price was checked."""
        suppliers = self._data.get("sourcing", {}).get("suppliers", [])
        dates = []
        for s in suppliers:
            if "date_checked" in s:
                try:
                    d = datetime.strptime(s["date_checked"], "%Y-%m-%d").date()
                    dates.append(d)
                except ValueError:
                    pass
        if not dates:
            return None
        latest = max(dates)
        return (date.today() - latest).days


class Catalog:
    """The full component catalog — parts, species, asteroids, reagents."""

    def __init__(self, catalog_dir: Path | None = None) -> None:
        self._dir = catalog_dir or CATALOG_DIR
        self.parts: list[CatalogEntry] = []
        self.species: list[CatalogEntry] = []
        self.asteroids: list[CatalogEntry] = []
        self.reagents: list[CatalogEntry] = []
        self.sealing: list[CatalogEntry] = []
        self._load()

    def _load(self) -> None:
        old_dir = CATALOG_DIR
        # Temporarily override for loading
        for subdir, attr in [
            ("parts", "parts"),
            ("species", "species"),
            ("asteroids", "asteroids"),
            ("reagents", "reagents"),
            ("sealing", "sealing"),
        ]:
            dirpath = self._dir / subdir
            if not dirpath.exists():
                continue
            items = []
            for filepath in sorted(dirpath.glob("*.yaml")):
                try:
                    data = _load_yaml(filepath)
                    data["_source_file"] = str(filepath.name)
                    items.append(CatalogEntry(data))
                except Exception as e:
                    print(f"Warning: failed to load {filepath}: {e}")
            setattr(self, attr, items)

    def get_part(self, part_id: str) -> CatalogEntry | None:
        """Look up a part by its ID."""
        for p in self.parts:
            if p.get("id") == part_id:
                return p
        return None

    def get_species(self, species_id: str) -> CatalogEntry | None:
        for s in self.species:
            if s.get("id") == species_id:
                return s
        return None

    def get_asteroid(self, asteroid_id: str) -> CatalogEntry | None:
        for a in self.asteroids:
            if a.get("id") == asteroid_id:
                return a
        return None

    def get_reagent(self, reagent_id: str) -> CatalogEntry | None:
        for r in self.reagents:
            if r.get("id") == reagent_id:
                return r
        return None

    def parts_by_category(self, category: str) -> list[CatalogEntry]:
        """Filter parts by category (compute, actuator, sensor, etc.)."""
        return [p for p in self.parts if p.get("category") == category]

    def stale_parts(self, days: int = 90) -> list[CatalogEntry]:
        """Find parts whose prices haven't been checked in N days."""
        stale = []
        for p in self.parts:
            d = p.days_since_price_check()
            if d is not None and d > days:
                stale.append(p)
        return stale

    def asteroids_by_confidence(self, level: str) -> list[CatalogEntry]:
        """Filter asteroids by composition confidence level."""
        return [
            a for a in self.asteroids
            if a.get("composition", {}).get("confidence") == level
        ]

    def asteroids_by_accessibility(self, max_delta_v: float) -> list[CatalogEntry]:
        """Filter asteroids by maximum delta-v from LEO."""
        results = []
        for a in self.asteroids:
            dv = (a.get("mining_relevance", {})
                   .get("accessibility", {})
                   .get("delta_v_from_leo_km_per_s"))
            if dv is not None and dv <= max_delta_v:
                results.append(a)
        return results

    def summary(self) -> dict[str, int]:
        """Return counts of catalog entries by type."""
        return {
            "parts": len(self.parts),
            "species": len(self.species),
            "asteroids": len(self.asteroids),
            "reagents": len(self.reagents),
            "sealing": len(self.sealing),
        }
