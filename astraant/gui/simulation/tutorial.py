"""Tutorial system -- contextual help triggered by game events.

Tooltips appear when you first encounter a game mechanic. Each one
fires once, explains what's happening, and disappears. Not tied to
any funding source -- works the same regardless of how you paid.

The tone is straightforward engineering explanation, not narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Tooltip:
    id: str
    trigger: str           # Event name that fires this
    title: str
    body: str


TOOLTIPS = [
    Tooltip("workers", "first_ant_deployed",
            "Worker Ants",
            "6 legs, 2 mandible arms, swappable tools. They mine, haul, seal, sort, "
            "and tend bioreactors — all with the same body, different tool heads. "
            "$37 each. The backbone of the colony."),

    Tooltip("mining", "first_material_dumped",
            "Mining Pipeline",
            "Regolith goes through: mine -> thermal sort (extract water + CO2) -> "
            "crush -> bioleach (bacteria dissolve metals) -> precipitate -> cargo pods. "
            "Every kilogram is tracked."),

    Tooltip("revenue_delay", "first_pod_launched",
            "Revenue Delay",
            "Cargo pods use solar sails. Free propulsion, but slow — 2.5 years to "
            "reach lunar orbit. You won't see revenue until those pods arrive. "
            "Plan your cash flow accordingly."),

    Tooltip("power_rail", "first_rail_installed",
            "Power Rail System",
            "Copper strips along tunnel walls provide continuous power. Ants have "
            "a spring-loaded brush that slides along the rail. No cables, no tangling. "
            "Supercapacitor covers 2 minutes off-rail at the work face."),

    Tooltip("failure", "first_ant_failure",
            "Ant Failure & Recycling",
            "Dead ants are recovered and tested part by part. Working servos, MCU, and "
            "sensors go to the spare parts bin. Chassis metal goes to the sintering "
            "furnace. ~$30 of $37 recovered per ant."),

    Tooltip("manufacturing", "first_ant_manufactured",
            "In-Situ Manufacturing",
            "The sintering furnace melts extracted iron into ant chassis parts. "
            "Electronics still ship from Earth (9 kg per 100 ants), but structures "
            "are built locally. The factory copies itself."),

    Tooltip("zones", "first_zone_discovered",
            "Mineral Veins",
            "The asteroid interior has geological zones — sulfide pockets rich in "
            "copper, metal grain inclusions with platinum, organic-rich areas for CO2. "
            "The taskmaster's spectral sensor finds them. Dig toward the valuable ones."),

    Tooltip("bioreactor", "bioreactor_first_cycle",
            "Bioleaching",
            "Bacteria dissolve metals from crushed rock. A. ferrooxidans handles "
            "iron/copper/nickel. Aspergillus niger extracts rare earths using citric acid. "
            "The bacteria self-replicate — they're not a consumable."),

    Tooltip("economy", "first_revenue_received",
            "Revenue",
            "Material delivered to lunar orbit is worth a LOT — water at $50K/kg, "
            "nickel at $5K/kg. Even small shipments generate significant revenue. "
            "The bottleneck is delivery throughput, not material value."),

    Tooltip("events", "first_random_event",
            "Random Events",
            "Things go wrong. Crusher jams, solar flares, bioreactor pH excursions. "
            "The colony can auto-resolve most issues, but your choices affect cost "
            "and downtime. Good events happen too — rich veins, ice bonanzas."),

    Tooltip("upgrades", "first_upgrade_available",
            "Component Upgrades",
            "Better parts become available over time (metal gear servos, brushless motors, "
            "tungsten carbide drill bits). Purchase them for the next resupply rocket. "
            "Funded from mining revenue."),

    Tooltip("endgame", "first_habitat_section",
            "The Endgame",
            "The colony excavates a chamber inside the asteroid. Install equipment, "
            "build a rotating ring for artificial gravity. Section by section, grow "
            "from a sleeping pod to an Interstellar-class 1g habitat."),

    Tooltip("microgravity", "game_start",
            "Microgravity",
            "There is no up or down. Heat doesn't rise. Dust doesn't settle. "
            "Ants walk on floors, walls, and ceilings equally. Fans provide the "
            "ONLY air circulation. Everything is different here."),

    Tooltip("comm_delay", "first_command_sent",
            "Communication Delay",
            "You're on Earth. The asteroid is minutes away at light speed. "
            "Every command takes 5-30 minutes to arrive. The colony operates "
            "autonomously between your orders. You set goals, not micromanage."),

    Tooltip("save", "game_start_2",
            "Saving",
            "F5 = quicksave. F9 = quickload. Auto-save every 5 minutes. "
            "Save files are in output/saves/ as readable JSON."),
]


class TutorialSystem:
    """Fires tooltips once per trigger event."""

    def __init__(self):
        self.seen: set[str] = set()
        self.queue: list[Tooltip] = []   # Tooltips waiting to display

    def check(self, trigger: str) -> Tooltip | None:
        """Check if a trigger should show a tooltip. Returns it or None."""
        for tip in TOOLTIPS:
            if tip.trigger == trigger and tip.id not in self.seen:
                self.seen.add(tip.id)
                self.queue.append(tip)
                return tip
        return None

    def pop_next(self) -> Tooltip | None:
        """Get the next queued tooltip for display."""
        if self.queue:
            return self.queue.pop(0)
        return None

    @property
    def pending(self) -> int:
        return len(self.queue)
