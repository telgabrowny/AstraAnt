"""Game economy — budget, revenue, and reinvestment.

The player starts with a fixed budget. Revenue arrives when cargo pods
reach the destination (2.5 year transit delay). Future launches must be
funded from accumulated revenue. Key decision: reinvest in expansion
or take profits.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


# Delivery methods: cost, payload capacity, transit time to NEA, risk of loss.
# There's more than one way to get hardware to an asteroid.
DELIVERY_METHODS = {
    "cubesat_3u": {
        "name": "3U CubeSat Rideshare",
        "payload_kg": 5,
        "cost_usd": 150_000,
        "transit_years": 2.0,       # Ion drive from LEO
        "failure_rate": 0.08,       # 8% loss rate
        "description": "Upgrade packs, replacement parts, sensor modules.",
    },
    "cubesat_6u": {
        "name": "6U CubeSat Rideshare",
        "payload_kg": 12,
        "cost_usd": 300_000,
        "transit_years": 2.0,
        "failure_rate": 0.07,
        "description": "30-50 micro worker ants + tool heads.",
    },
    "cubesat_12u": {
        "name": "12U CubeSat Rideshare",
        "payload_kg": 24,
        "cost_usd": 500_000,
        "transit_years": 1.5,       # Faster: larger bus supports a better propulsion module
        "failure_rate": 0.06,
        "description": "Bioreactor module, surface ant, or large ant batch.",
    },
    "espa_rideshare": {
        "name": "ESPA Secondary Payload",
        "payload_kg": 180,
        "cost_usd": 2_000_000,
        "transit_years": 1.0,       # Rides with a primary mission
        "failure_rate": 0.03,
        "description": "Seed ship: drill + power + comms + sealant + first ants.",
    },
    "dedicated_falcon_heavy": {
        "name": "Dedicated Falcon Heavy",
        "payload_kg": 16_000,       # To NEA, after escape burn
        "cost_usd": 150_000_000,
        "transit_years": 0.75,
        "failure_rate": 0.02,
        "description": "Full mothership + large swarm in one launch.",
    },
    "dedicated_starship": {
        "name": "Dedicated Starship",
        "payload_kg": 100_000,
        "cost_usd": 50_000_000,     # Projected future pricing
        "transit_years": 0.5,
        "failure_rate": 0.02,
        "description": "Everything at once. Multiple motherships + full colony.",
    },
    "solar_sail": {
        "name": "Solar Sail Cargo",
        "payload_kg": 15,
        "cost_usd": 200_000,        # LEO rideshare + sail hardware
        "transit_years": 3.5,       # Slow but free propulsion
        "failure_rate": 0.12,
        "description": "Ultra-budget. Free propulsion, long wait, higher risk.",
    },
}


@dataclass
class ScheduledDelivery:
    """A delivery in transit to the asteroid."""
    method: str                     # Key into DELIVERY_METHODS
    contents: str                   # Description of what's on board
    cost_usd: float
    launch_time_hours: float
    arrival_time_hours: float
    payload_kg: float
    lost: bool = False              # Delivery failed in transit


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

    # Delivery tracking (piecemeal or bulk)
    deliveries_in_transit: list[ScheduledDelivery] = field(default_factory=list)
    deliveries_arrived: int = 0
    deliveries_lost: int = 0

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

        # Process delivery arrivals -- failure rolled at arrival, not launch
        arrived_deliveries = []
        for d in self.deliveries_in_transit:
            if sim_time_hours >= d.arrival_time_hours:
                arrived_deliveries.append(d)
                spec = DELIVERY_METHODS.get(d.method, {})
                failure_rate = spec.get("failure_rate", 0.05)
                if random.random() < failure_rate:
                    d.lost = True
                    self.deliveries_lost += 1
                    events.append({
                        "type": "delivery_lost",
                        "method": d.method,
                        "contents": d.contents,
                        "message": f"DELIVERY LOST: {d.contents} "
                                   f"({spec.get('name', d.method)}) -- "
                                   f"contact lost during transit. ${d.cost_usd/1e6:.2f}M lost.",
                    })
                else:
                    self.deliveries_arrived += 1
                    events.append({
                        "type": "delivery_arrived",
                        "method": d.method,
                        "contents": d.contents,
                        "payload_kg": d.payload_kg,
                        "message": f"DELIVERY ARRIVED: {d.contents} "
                                   f"({d.payload_kg:.0f} kg via {spec.get('name', d.method)})",
                    })
        for d in arrived_deliveries:
            self.deliveries_in_transit.remove(d)

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
        """Can we afford to send a resupply mission (legacy: dedicated Starship)?"""
        resupply_cost = 20_000_000
        return self.cash_on_hand_usd >= resupply_cost

    def send_resupply(self) -> dict[str, Any] | None:
        """Send a resupply mission (legacy: dedicated Starship)."""
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

    def schedule_delivery(self, method: str, contents: str,
                          sim_time_hours: float) -> dict[str, Any] | None:
        """Schedule a delivery using any available method.

        Returns event dict on success, None if can't afford.
        """
        spec = DELIVERY_METHODS.get(method)
        if spec is None:
            return None

        cost = spec["cost_usd"]
        if not self.spend(cost, f"delivery: {method}"):
            return None

        transit_hours = spec["transit_years"] * 365.25 * 24
        arrival = sim_time_hours + transit_hours

        delivery = ScheduledDelivery(
            method=method,
            contents=contents,
            cost_usd=cost,
            launch_time_hours=sim_time_hours,
            arrival_time_hours=arrival,
            payload_kg=spec["payload_kg"],
            # lost is NOT determined at launch -- rolled at arrival in tick()
        )
        self.deliveries_in_transit.append(delivery)
        self.resupply_missions_sent += 1
        self.resupply_missions_cost_usd += cost

        transit_str = f"{spec['transit_years']:.1f} years"
        return {
            "type": "delivery_scheduled",
            "method": method,
            "cost_usd": cost,
            "payload_kg": spec["payload_kg"],
            "contents": contents,
            "arrival_hours": arrival,
            "message": f"DELIVERY SCHEDULED: {spec['name']} -- {contents}. "
                       f"Cost: ${cost/1e6:.2f}M. Transit: {transit_str}. "
                       f"Cash remaining: ${self.cash_on_hand_usd/1e6:.1f}M",
        }

    def can_afford_delivery(self, method: str) -> bool:
        """Check if a specific delivery method is affordable."""
        spec = DELIVERY_METHODS.get(method)
        if spec is None:
            return False
        return self.cash_on_hand_usd >= spec["cost_usd"]

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
            "deliveries_in_transit": len(self.deliveries_in_transit),
            "deliveries_arrived": self.deliveries_arrived,
            "deliveries_lost": self.deliveries_lost,
            "profitable": self.profitable,
            "net_position": round(
                self.cash_on_hand_usd + self.total_revenue_in_transit_usd - self.initial_budget_usd, 0
            ),
        }
