"""Catalog validation -- catch missing or malformed YAML before analysis runs.

Checks the fields the calculators and CLI actually rely on (per
catalog/SCHEMA.md). Errors are things that would crash or silently poison a
calculation (missing id, duplicate ids, non-numeric mass or price); warnings
are incomplete-but-survivable data (no suppliers, missing rotation period).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .catalog import Catalog, CatalogEntry

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    severity: str      # ERROR or WARNING
    kind: str          # parts / species / asteroids / reagents / sealing
    source_file: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper():7s}] {self.kind}/{self.source_file}: {self.message}"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_common(kind: str, entries: list[CatalogEntry],
                  issues: list[Issue]) -> None:
    seen_ids: dict[str, str] = {}
    for e in entries:
        src = e.get("_source_file", "?")
        eid = e.get("id")
        if not eid:
            issues.append(Issue(ERROR, kind, src, "missing 'id'"))
            continue
        if eid in seen_ids:
            issues.append(Issue(ERROR, kind, src,
                                f"duplicate id '{eid}' (also in {seen_ids[eid]})"))
        else:
            seen_ids[eid] = src
        if not e.get("name"):
            issues.append(Issue(WARNING, kind, src, f"'{eid}' missing 'name'"))


def _check_parts(parts: list[CatalogEntry], issues: list[Issue]) -> None:
    for p in parts:
        src = p.get("_source_file", "?")
        pid = p.get("id", "?")
        if not p.get("category"):
            issues.append(Issue(WARNING, "parts", src,
                                f"'{pid}' missing 'category'"))

        specs = p.get("specs", {}) or {}
        mass = specs.get("mass_g")
        if mass is None:
            issues.append(Issue(WARNING, "parts", src,
                                f"'{pid}' missing specs.mass_g"))
        elif not _is_number(mass) or mass < 0:
            issues.append(Issue(ERROR, "parts", src,
                                f"'{pid}' specs.mass_g is not a non-negative "
                                f"number: {mass!r}"))

        suppliers = (p.get("sourcing", {}) or {}).get("suppliers", []) or []
        if not suppliers:
            issues.append(Issue(WARNING, "parts", src,
                                f"'{pid}' has no suppliers"))
        for s in suppliers:
            sname = s.get("name", "?")
            price = s.get("price_usd")
            if price is None:
                issues.append(Issue(WARNING, "parts", src,
                                    f"'{pid}' supplier {sname} missing price_usd"))
            elif not _is_number(price) or price < 0:
                issues.append(Issue(ERROR, "parts", src,
                                    f"'{pid}' supplier {sname} price_usd is not "
                                    f"a non-negative number: {price!r}"))
            checked = s.get("date_checked")
            if checked is not None:
                try:
                    datetime.strptime(str(checked), "%Y-%m-%d")
                except ValueError:
                    issues.append(Issue(WARNING, "parts", src,
                                        f"'{pid}' supplier {sname} date_checked "
                                        f"not YYYY-MM-DD: {checked!r}"))


def _check_asteroids(asteroids: list[CatalogEntry],
                     issues: list[Issue]) -> None:
    for a in asteroids:
        src = a.get("_source_file", "?")
        aid = a.get("id", "?")
        if not a.get("composition"):
            issues.append(Issue(WARNING, "asteroids", src,
                                f"'{aid}' missing 'composition'"))
        rotation = (a.get("physical", {}) or {}).get("rotation_period_hours")
        if rotation is None:
            issues.append(Issue(WARNING, "asteroids", src,
                                f"'{aid}' missing physical.rotation_period_hours "
                                f"(day/night power cycle needs it)"))
        elif not _is_number(rotation) or rotation <= 0:
            issues.append(Issue(ERROR, "asteroids", src,
                                f"'{aid}' rotation_period_hours must be a "
                                f"positive number: {rotation!r}"))


def _check_species(species: list[CatalogEntry], issues: list[Issue]) -> None:
    for s in species:
        src = s.get("_source_file", "?")
        sid = s.get("id", "?")
        if not s.get("growth"):
            issues.append(Issue(WARNING, "species", src,
                                f"'{sid}' missing 'growth' block"))
        if not s.get("extraction"):
            issues.append(Issue(WARNING, "species", src,
                                f"'{sid}' missing 'extraction' block"))


def validate_catalog(catalog: Catalog | None = None) -> list[Issue]:
    """Validate every catalog entry. Returns all issues found (may be empty)."""
    cat = catalog or Catalog()
    issues: list[Issue] = []

    for kind, entries in [("parts", cat.parts), ("species", cat.species),
                          ("asteroids", cat.asteroids),
                          ("reagents", cat.reagents),
                          ("sealing", cat.sealing)]:
        _check_common(kind, entries, issues)

    _check_parts(cat.parts, issues)
    _check_asteroids(cat.asteroids, issues)
    _check_species(cat.species, issues)
    return issues


def has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == ERROR for i in issues)
