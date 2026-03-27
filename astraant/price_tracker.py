"""Price tracking and staleness detection for the component catalog.

This module supports the "run periodically" use case: check which parts
have stale pricing, flag new parts that appeared since last check, and
track price trends over time.

Run `astraant catalog stale` to see what needs updating.
Run `astraant price-report` for a full price health check.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .catalog import Catalog


def price_health_report(catalog: Catalog | None = None,
                        stale_threshold_days: int = 90) -> str:
    """Generate a price health report for the entire catalog.

    Shows:
    - Parts with stale prices (not checked in N days)
    - Parts with no supplier info
    - Price trends (if history available)
    - Summary statistics
    """
    if catalog is None:
        catalog = Catalog()

    today = date.today()
    lines = []
    lines.append("=" * 70)
    lines.append(f"PRICE HEALTH REPORT -- {today.isoformat()}")
    lines.append(f"Stale threshold: {stale_threshold_days} days")
    lines.append("=" * 70)

    stale = []
    current = []
    no_price = []
    total_cost_worker = 0.0

    for part in catalog.parts:
        price = part.best_price()
        days = part.days_since_price_check()

        if price is None:
            no_price.append(part)
        elif days is not None and days > stale_threshold_days:
            stale.append((part, days, price))
        else:
            current.append((part, days, price))

    # Current prices
    lines.append(f"\n--- CURRENT ({len(current)} parts) ---")
    for part, days, price in sorted(current, key=lambda x: x[0].id):
        age = f"{days}d ago" if days else "today"
        lines.append(f"  {part.id:<30s} ${price:>8.2f}  checked {age}")

    # Stale prices
    if stale:
        lines.append(f"\n--- STALE ({len(stale)} parts -- NEED UPDATE) ---")
        for part, days, price in sorted(stale, key=lambda x: -x[1]):
            lines.append(f"  {part.id:<30s} ${price:>8.2f}  STALE: {days} days old")
            # Show suppliers to check
            suppliers = part.get("sourcing", {}).get("suppliers", [])
            for s in suppliers:
                url = s.get("url", "no URL")
                lines.append(f"    -> Check: {s.get('name', '?')} {url[:60]}")
    else:
        lines.append(f"\n--- No stale prices (all checked within {stale_threshold_days} days) ---")

    # No price info
    if no_price:
        lines.append(f"\n--- NO PRICE ({len(no_price)} parts) ---")
        for part in no_price:
            lines.append(f"  {part.id:<30s} -- no supplier pricing data")

    # Price trends
    lines.append(f"\n--- PRICE TRENDS ---")
    for part in catalog.parts:
        history = part.price_trend()
        if len(history) >= 2:
            first = history[0].get("price_usd", 0)
            last = history[-1].get("price_usd", 0)
            if first > 0:
                change_pct = ((last - first) / first) * 100
                direction = "UP" if change_pct > 5 else "DOWN" if change_pct < -5 else "stable"
                if direction != "stable":
                    lines.append(f"  {part.id:<30s} ${first:.2f} -> ${last:.2f} ({direction} {abs(change_pct):.0f}%)")

    # Summary
    lines.append(f"\n--- SUMMARY ---")
    lines.append(f"  Total parts:    {len(catalog.parts)}")
    lines.append(f"  Current prices: {len(current)}")
    lines.append(f"  Stale prices:   {len(stale)}")
    lines.append(f"  No price data:  {len(no_price)}")
    lines.append(f"  Stale rate:     {len(stale) / max(1, len(catalog.parts)) * 100:.0f}%")

    # Worker ant cost at current prices
    worker_parts = ["rp2040", "sg90_servo", "nrf24l01_rf", "vl53l0x_lidar"]
    worker_cost = 0.0
    for pid in worker_parts:
        p = catalog.get_part(pid)
        if p:
            price = p.best_price()
            if price:
                if pid == "sg90_servo":
                    worker_cost += price * 8  # 6 legs + 2 mandibles
                else:
                    worker_cost += price
    lines.append(f"\n  Worker ant cost (current prices): ${worker_cost:.2f}")
    lines.append(f"  (SG90 x8 + RP2040 + nRF24 + VL53L0x)")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
