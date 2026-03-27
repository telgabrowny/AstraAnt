"""The Loan Shark -- your friendly financier and tutorial narrator.

"Listen kid, I'm lending you $163 million to send robots to a rock
in space. You better make this work, because the vig doesn't stop
just because your bugs are floating around in the dark."

The loan shark:
1. Funds the initial mission (the principal)
2. Charges interest (difficulty-dependent rate)
3. Narrates the tutorial ("What are these little orange things?")
4. Comments on your progress ("My money is sitting in transit?!")
5. Gets increasingly nervous as debt grows
6. Gets increasingly happy as payments come in
7. Has a final payoff scene when the debt is cleared

Difficulty levels set the interest rate. Everything else is the same.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LoanState:
    """The loan shark's financial state."""
    principal_usd: float = 163_000_000
    interest_rate_annual: float = 0.18  # 18% = Hard difficulty
    balance_usd: float = 163_000_000
    total_interest_paid_usd: float = 0
    total_principal_paid_usd: float = 0
    payments_made: int = 0
    paid_off: bool = False
    paid_off_year: float = 0
    peak_debt_usd: float = 163_000_000

    # Mood tracking (affects dialogue)
    mood: str = "neutral"  # confident, neutral, nervous, angry, pleased, ecstatic


DIFFICULTY_RATES = {
    "easy": 0.08,
    "normal": 0.12,
    "hard": 0.18,
    "nightmare": 0.25,
}

DIFFICULTY_DESCRIPTIONS = {
    "easy": "8% annual. The loan shark is your uncle. He believes in you.",
    "normal": "12% annual. Standard high-risk lending. They expect results.",
    "hard": "18% annual. They're not your friend. The vig compounds monthly.",
    "nightmare": "25% annual. You borrowed from the WRONG people. Don't miss a payment.",
}


# Tutorial tooltips narrated by the loan shark
TUTORIAL_TOOLTIPS = {
    "first_launch": {
        "trigger": "game_start",
        "shark_says": "Alright, I just wired you $163 million. That rocket better "
                      "have everything you need on it, because I'm not sending another "
                      "one until you start paying me back.",
        "explains": "Your entire operation launches on one Starship. Everything — "
                    "the mothership, the ants, the bioreactors, the Phase 2 equipment — "
                    "is packed inside. Choose your loadout wisely.",
    },
    "workers_explained": {
        "trigger": "first_ant_deployed",
        "shark_says": "What are these little orange things scurrying around? "
                      "THOSE are my $33 robots? They better be tough.",
        "explains": "Worker ants: 6 legs, 2 mandible arms, swap tool heads at magnetic docks. "
                    "$33 each at hobby prices. They mine, haul, seal walls, sort material, "
                    "and tend bioreactors — all with the same body, different tools.",
    },
    "mining_starts": {
        "trigger": "first_material_dumped",
        "shark_says": "OK, they're digging. When does the money start flowing?",
        "explains": "Material goes through a pipeline: mine -> thermal sort (extract water + CO2) "
                    "-> crush -> bioleach (bacteria extract metals) -> precipitate -> cargo pods. "
                    "Revenue arrives when pods reach the destination. By solar sail. In 2.5 years.",
    },
    "revenue_delay": {
        "trigger": "first_pod_launched",
        "shark_says": "2.5 YEARS?! My interest is compounding RIGHT NOW. "
                      "You're telling me I won't see a dime for 2.5 years?",
        "explains": "Cargo pods use solar sails — free propulsion but slow transit. "
                    "Your first revenue arrives 2.5 years after the first pod launches. "
                    "Meanwhile, the loan shark's interest keeps ticking.",
    },
    "interest_notice": {
        "trigger": "quarterly",
        "shark_says": "Just a friendly reminder: your balance is now ${balance}. "
                      "That's ${interest} in interest this quarter alone. "
                      "Tick tock.",
        "explains": "Interest compounds quarterly. At {rate}% annual, that's "
                    "{quarterly_rate:.1f}% per quarter. Your debt grows even while you sleep.",
    },
    "first_revenue": {
        "trigger": "first_revenue_received",
        "shark_says": "FINALLY. ${revenue} just hit the account. "
                      "That barely covers this quarter's interest, but it's a start.",
        "explains": "Revenue from delivered cargo pods. Water is 90% of the value "
                    "at lunar orbit prices. As more pods arrive, payments increase.",
    },
    "ant_died": {
        "trigger": "first_ant_failure",
        "shark_says": "One of your bugs just died. That's MY money walking around "
                      "out there. Tell me you're recycling the parts.",
        "explains": "Dead ants are recovered and tested part by part. Working servos, "
                    "MCUs, and sensors go to the spare parts bin. Chassis metal goes "
                    "back to the sintering furnace. ~$30 of $33 recovered per ant.",
    },
    "manufacturing_started": {
        "trigger": "first_ant_manufactured",
        "shark_says": "Wait — you're building NEW robots? FROM THE ROCK? "
                      "That's... actually smart. More miners, more money.",
        "explains": "The sintering furnace melts extracted iron into ant chassis parts. "
                    "Electronics still come from Earth ($9 per 100 ants), but the structural "
                    "parts are free. The factory builds copies of itself.",
    },
    "profitable": {
        "trigger": "revenue_exceeds_interest",
        "shark_says": "Your payments now exceed the interest. The balance is "
                      "actually going DOWN. I'm starting to like you, kid.",
        "explains": "When annual revenue exceeds annual interest, the debt starts shrinking. "
                    "This is the inflection point. From here, it's a countdown to payoff.",
    },
    "paid_off": {
        "trigger": "balance_zero",
        "shark_says": "We're even. $163 million plus ${total_interest} in interest. "
                      "Pleasure doing business. "
                      "...Say, you got room for investors on the next asteroid?",
        "explains": "DEBT PAID OFF! From here, all revenue is pure profit. "
                    "The loan shark becomes your first investor in the expansion.",
    },
    "anomaly_found": {
        "trigger": "anomaly_detected",
        "shark_says": "Your bugs found something weird in there? "
                      "If it's valuable, I want a cut. If it's dangerous, "
                      "I want my money back first.",
        "explains": "Anomalies are flagged by the spectral sensor when readings "
                    "don't match any known mineral signature. Could be scientifically "
                    "priceless or just an interesting rock.",
    },
}


class LoanShark:
    """Manages the loan, payments, and tutorial narration."""

    def __init__(self, difficulty: str = "hard"):
        rate = DIFFICULTY_RATES.get(difficulty, 0.18)
        self.loan = LoanState(interest_rate_annual=rate)
        self.difficulty = difficulty
        self.triggered_tutorials: set[str] = set()
        self._last_interest_time = 0
        self._interest_interval_hours = 365.25 * 24 / 4  # Quarterly

    def tick(self, sim_time_hours: float, revenue_this_tick: float = 0) -> list[dict[str, Any]]:
        """Process interest accrual and payments. Returns events."""
        events = []

        if self.loan.paid_off:
            return events

        # Quarterly interest
        if sim_time_hours - self._last_interest_time >= self._interest_interval_hours:
            self._last_interest_time = sim_time_hours
            quarterly_rate = self.loan.interest_rate_annual / 4
            interest = self.loan.balance_usd * quarterly_rate
            self.loan.balance_usd += interest
            self.loan.total_interest_paid_usd += interest
            self.loan.peak_debt_usd = max(self.loan.peak_debt_usd, self.loan.balance_usd)

            events.append({
                "type": "interest_charged",
                "amount": interest,
                "balance": self.loan.balance_usd,
                "message": f"INTEREST: ${interest:,.0f} charged. Balance: ${self.loan.balance_usd:,.0f}",
            })

            # Update mood
            if self.loan.balance_usd > self.loan.principal_usd * 1.5:
                self.loan.mood = "nervous"
            elif self.loan.balance_usd > self.loan.principal_usd:
                self.loan.mood = "neutral"

        # Apply revenue as payment
        if revenue_this_tick > 0:
            payment = min(revenue_this_tick, self.loan.balance_usd)
            self.loan.balance_usd -= payment
            self.loan.total_principal_paid_usd += payment
            self.loan.payments_made += 1
            self.loan.mood = "pleased" if self.loan.balance_usd < self.loan.principal_usd else "neutral"

            if self.loan.balance_usd <= 0:
                self.loan.balance_usd = 0
                self.loan.paid_off = True
                self.loan.paid_off_year = sim_time_hours / (365.25 * 24)
                self.loan.mood = "ecstatic"
                events.append({
                    "type": "loan_paid_off",
                    "message": f"DEBT CLEARED! Total interest paid: "
                               f"${self.loan.total_interest_paid_usd:,.0f}. "
                               f"You're free. Year {self.loan.paid_off_year:.1f}.",
                })

        return events

    def get_tutorial(self, trigger: str, **kwargs) -> dict[str, str] | None:
        """Get a tutorial tooltip if this trigger hasn't fired yet."""
        if trigger in self.triggered_tutorials:
            return None

        for tooltip_id, tooltip in TUTORIAL_TOOLTIPS.items():
            if tooltip["trigger"] == trigger:
                self.triggered_tutorials.add(trigger)
                shark_text = tooltip["shark_says"]
                explain_text = tooltip["explains"]

                # Format with dynamic values
                for key, val in kwargs.items():
                    shark_text = shark_text.replace(f"{{{key}}}", str(val))
                    explain_text = explain_text.replace(f"{{{key}}}", str(val))

                return {
                    "id": tooltip_id,
                    "shark_says": shark_text,
                    "explains": explain_text,
                }
        return None

    def get_shark_comment(self) -> str:
        """Get a contextual comment based on current mood."""
        comments = {
            "confident": "Everything's going according to plan. Keep it up.",
            "neutral": "Numbers look OK. Keep mining.",
            "nervous": "That balance is getting high. When's the next payment?",
            "angry": "I'm starting to regret this arrangement.",
            "pleased": "Now THAT'S what I like to see. More of that.",
            "ecstatic": "Best investment I ever made. What's the next asteroid?",
        }
        return comments.get(self.loan.mood, "...")

    def summary(self) -> dict[str, Any]:
        return {
            "difficulty": self.difficulty,
            "rate": f"{self.loan.interest_rate_annual*100:.0f}%",
            "balance": round(self.loan.balance_usd, 0),
            "principal": self.loan.principal_usd,
            "total_interest": round(self.loan.total_interest_paid_usd, 0),
            "payments": self.loan.payments_made,
            "paid_off": self.loan.paid_off,
            "mood": self.loan.mood,
            "peak_debt": round(self.loan.peak_debt_usd, 0),
        }
