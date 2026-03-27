"""Game economy — budget, revenue, and reinvestment.

The player starts with a fixed budget. Revenue arrives when cargo pods
reach the destination (2.5 year transit delay). Future launches must be
funded from accumulated revenue. Key decision: reinvest in expansion
or take profits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameEconomy:
    """Tracks the financial state of the mission."""

    # Starting conditions
    initial_budget_usd: float = 163_000_000     # One Starship launch + hardware
    budget_remaining_usd: float = 163_000_000

    # Revenue tracking
    pods_in_transit: list[dict] = field(default_factory=list)  # {launch_time, arrival_time, value_usd}
    pods_delivered: int = 0
    total_revenue_received_usd: float = 0.0
    total_revenue_in_transit_usd: float = 0.0

    # Expenses
    total_spent_usd: float = 0.0
    resupply_missions_sent: int = 0
    resupply_missions_cost_usd: float = 0.0

    # Financial state
    cash_on_hand_usd: float = 0.0               # Available for spending
    debt_usd: float = 0.0                        # If spending exceeds revenue
    profitable: bool = False
    time_to_profit_sim_hours: float = 0.0

    def spend(self, amount_usd: float, description: str = "") -> bool:
        """Attempt to spend money. Returns False if insufficient funds."""
        if amount_usd <= self.cash_on_hand_usd:
            self.cash_on_hand_usd -= amount_usd
            self.total_spent_usd += amount_usd
            return True
        return False

    def launch_pod(self, value_usd: float, launch_time: float,
                   transit_years: float = 2.5) -> None:
        """Record a cargo pod launch."""
        arrival_time = launch_time + transit_years * 365.25 * 24  # hours
        self.pods_in_transit.append({
            "launch_time": launch_time,
            "arrival_time": arrival_time,
            "value_usd": value_usd,
        })
        self.total_revenue_in_transit_usd += value_usd

    def tick(self, sim_time_hours: float) -> list[dict[str, Any]]:
        """Process revenue arrivals. Returns events for pods that arrived."""
        events = []
        arrived = []

        for pod in self.pods_in_transit:
            if sim_time_hours >= pod["arrival_time"]:
                arrived.append(pod)
                self.cash_on_hand_usd += pod["value_usd"]
                self.total_revenue_received_usd += pod["value_usd"]
                self.total_revenue_in_transit_usd -= pod["value_usd"]
                self.pods_delivered += 1
                events.append({
                    "type": "revenue",
                    "value_usd": pod["value_usd"],
                    "message": f"CARGO DELIVERED: ${pod['value_usd']:,.0f} received "
                               f"({self.pods_delivered} pods total)",
                })

        for pod in arrived:
            self.pods_in_transit.remove(pod)

        # Check profitability
        if not self.profitable and self.total_revenue_received_usd > self.initial_budget_usd:
            self.profitable = True
            self.time_to_profit_sim_hours = sim_time_hours
            events.append({
                "type": "profitable",
                "message": f"MISSION PROFITABLE! Revenue ${self.total_revenue_received_usd:,.0f} "
                           f"exceeds investment ${self.initial_budget_usd:,.0f}",
            })

        return events

    def can_afford_resupply(self) -> bool:
        """Can we afford to send a resupply mission?"""
        resupply_cost = 20_000_000  # One Starship resupply launch
        return self.cash_on_hand_usd >= resupply_cost

    def send_resupply(self) -> dict[str, Any] | None:
        """Send a resupply mission (more motherships + electronics)."""
        cost = 20_000_000
        if not self.spend(cost, "resupply mission"):
            return None
        self.resupply_missions_sent += 1
        self.resupply_missions_cost_usd += cost
        return {
            "type": "resupply",
            "cost_usd": cost,
            "contents": "4 motherships + electronics for 500 ants",
            "message": f"RESUPPLY #{self.resupply_missions_sent}: ${cost/1e6:.0f}M sent. "
                       f"Cash remaining: ${self.cash_on_hand_usd/1e6:.0f}M",
        }

    def summary(self) -> dict[str, Any]:
        return {
            "initial_budget": self.initial_budget_usd,
            "cash_on_hand": round(self.cash_on_hand_usd, 0),
            "total_spent": round(self.total_spent_usd, 0),
            "total_revenue_received": round(self.total_revenue_received_usd, 0),
            "revenue_in_transit": round(self.total_revenue_in_transit_usd, 0),
            "pods_in_transit": len(self.pods_in_transit),
            "pods_delivered": self.pods_delivered,
            "resupply_missions": self.resupply_missions_sent,
            "profitable": self.profitable,
            "net_position": round(
                self.cash_on_hand_usd + self.total_revenue_in_transit_usd - self.initial_budget_usd, 0
            ),
        }
