"""Funding sources -- pick one at game start, shapes the entire experience.

LOAN SHARK: $163M, 18% interest, full rocket. Race the debt clock.
NASA: $80M, 2% interest, 60% of rocket. Science milestones required.
BOOTSTRAPPER: $25M, 0% interest, rideshare slot. Every gram counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FundingSource:
    id: str
    name: str
    tagline: str
    budget_usd: float
    interest_rate: float
    rocket_kg: float
    difficulty: str
    intro: str


FUNDING_SOURCES = {
    "loan_shark": FundingSource(
        id="loan_shark",
        name="The Investor",
        tagline="$163M. 18% interest. Full rocket. Don't be late.",
        budget_usd=163_000_000,
        interest_rate=0.18,
        rocket_kg=25000,
        difficulty="Pressured",
        intro="A private investor wires you the full amount. No questions about "
              "your plan. Just one condition: 18% annual interest, compounding "
              "quarterly. Every day you're not paying it back, the number grows.",
    ),
    "nasa": FundingSource(
        id="nasa",
        name="NASA Partnership",
        tagline="$80M. 2% interest. Shared rocket. Science milestones.",
        budget_usd=80_000_000,
        interest_rate=0.02,
        rocket_kg=15000,
        difficulty="Balanced",
        intro="NASA funds the mission as a public-private partnership. Low interest, "
              "but you share the rocket with their instruments, and they expect "
              "science data on schedule. Miss a milestone, your funding gets reviewed.",
    ),
    "bootstrapper": FundingSource(
        id="bootstrapper",
        name="Self-Funded",
        tagline="$25M. No interest. Rideshare. Make it count.",
        budget_usd=25_000_000,
        interest_rate=0.0,
        rocket_kg=3750,
        difficulty="Hard",
        intro="You sold your house. You ran a Kickstarter. You begged every angel "
              "investor in Silicon Valley. $25 million and a rideshare slot on someone "
              "else's Starship. No debt, no boss, no safety net. This is yours.",
    ),
}


def get_funding(source_id: str) -> FundingSource | None:
    return FUNDING_SOURCES.get(source_id)


def what_fits(rocket_kg: float) -> dict[str, Any]:
    """Given a rocket capacity, what essential and optional items fit."""
    # Minimum viable colony
    essentials = [
        ("Mothership core", 108),
        ("Water (300L)", 300),
        ("Small ant swarm (30W+2T+1S)", 5),
        ("Consumables (1yr)", 15),
        ("Copper rail (25kg)", 25),
    ]
    essential_kg = sum(m for _, m in essentials)

    # Everything else is optional
    options = [
        ("Bioreactor (bioleaching)", 110),
        ("Thermal sorter", 13),
        ("Sugar production", 62),
        ("Manufacturing bay", 34),
        ("50 more workers + tools", 7),
        ("Cargo pods (200)", 112),
        ("Phase 2 equipment", 3780),
        ("Extra solar (+15kW)", 36),
        ("Nuclear 10kW", 500),
        ("Ant electronics (500 local)", 90),
    ]

    remaining = rocket_kg - essential_kg
    can_add = [(name, kg) for name, kg in options if kg <= remaining]

    return {
        "capacity_kg": rocket_kg,
        "essentials_kg": essential_kg,
        "remaining_kg": max(0, remaining),
        "essentials": essentials,
        "options": options,
        "fits": can_add,
        "too_big": [(name, kg) for name, kg in options if kg > remaining],
    }
