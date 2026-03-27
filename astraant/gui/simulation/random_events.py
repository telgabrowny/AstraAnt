"""Random events -- things that go wrong (and occasionally right).

These create tension and test the player's preparation. All events
are realistic scenarios that real space missions face. No magic,
no aliens (unless fanciful mode is on), just physics and engineering.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class RandomEvent:
    """A random event that affects the colony."""
    id: str
    name: str
    severity: str              # "minor", "moderate", "severe", "critical"
    description: str
    effects: dict[str, Any]    # What changes in the simulation
    player_choices: list[dict] # Options the player can choose
    auto_resolve: bool         # Does the colony handle it without player input?
    auto_resolve_time_hours: float  # How long the colony takes to fix it alone


# Events that can happen during mining operations
MINING_EVENTS = [
    RandomEvent(
        id="solar_particle_event",
        name="Solar Particle Event",
        severity="moderate",
        description=(
            "Coronal mass ejection detected. Intense radiation pulse incoming. "
            "Surface ants must shelter immediately. Underground ants unaffected "
            "(2m+ of regolith shielding). Estimated duration: 4-12 hours."
        ),
        effects={
            "surface_ants_disabled_hours": 8,
            "solar_panel_degradation_pct": 2,
            "comm_disruption_hours": 2,
        },
        player_choices=[
            {"label": "Recall surface ants immediately",
             "effect": "surface_ants_safe", "cost": 0,
             "note": "Surface ants take shelter in the tunnel entrance. No damage."},
            {"label": "Risk it -- keep surface ants working",
             "effect": "surface_ant_damage", "cost": 0,
             "note": "30% chance each surface ant takes radiation damage (reduced MTBF)."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=8,
    ),
    RandomEvent(
        id="micrometeorite_impact",
        name="Micrometeorite Impact on Solar Panel",
        severity="minor",
        description=(
            "Small particle impact detected on solar panel wing 2. "
            "Localized cell damage. Power output reduced by 3%. "
            "Surface ant can patch with spare cell if dispatched."
        ),
        effects={"solar_output_reduction_pct": 3},
        player_choices=[
            {"label": "Dispatch surface ant to patch",
             "effect": "panel_repaired", "cost": 0,
             "note": "Surface ant swaps damaged cell. 30 min task. Full power restored."},
            {"label": "Ignore -- 3% loss is acceptable",
             "effect": "accept_loss", "cost": 0,
             "note": "Cumulative damage adds up over years. Fix later?"},
        ],
        auto_resolve=False,
        auto_resolve_time_hours=0,
    ),
    RandomEvent(
        id="bioreactor_ph_excursion",
        name="Bioreactor pH Excursion",
        severity="moderate",
        description=(
            "Vat 1 (sulfide metals) pH drifting outside optimal range. "
            "Currently pH 3.2 (target: 2.0). If uncorrected, culture will "
            "crash within 2 hours. Tender ant detected the drift on patrol."
        ),
        effects={"bioreactor_efficiency_pct": 50, "culture_crash_hours": 2},
        player_choices=[
            {"label": "Add acid (auto -- tender ant handles it)",
             "effect": "ph_corrected", "cost": 0,
             "note": "Tender ant adjusts the acid dosing valve. pH returns to 2.0 in 30 min."},
            {"label": "Flush and restart the vat",
             "effect": "vat_restart", "cost": 0,
             "note": "Loses 5 days of culture growth. But guarantees clean restart."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=0.5,
    ),
    RandomEvent(
        id="tunnel_pressure_leak",
        name="Tunnel Pressure Leak Detected",
        severity="moderate",
        description=(
            "Pressure sensors show 0.3 kPa/hour decay in sector 7. "
            "Seal quality degrading -- possibly from thermal cycling or "
            "micro-crack in the wall paste. Plasterer worker needed."
        ),
        effects={"pressure_leak_kpa_per_hour": 0.3, "sector": 7},
        player_choices=[
            {"label": "Dispatch plasterer to patch",
             "effect": "leak_sealed", "cost": 0,
             "note": "Worker applies fresh paste over the crack. 1 hour fix."},
            {"label": "Apply polymer spray (better seal)",
             "effect": "leak_sealed_premium", "cost": 100,
             "note": "Uses polymer sealant from consumables. 98% seal vs 75% paste."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=1,
    ),
    RandomEvent(
        id="crusher_jam",
        name="Jaw Crusher Jammed",
        severity="minor",
        description=(
            "Large rock fragment wedged in the crusher jaws. "
            "Processing pipeline halted. Material backing up in dried buffer. "
            "Need a worker to clear the obstruction."
        ),
        effects={"crusher_halted": True, "buffer_filling": True},
        player_choices=[
            {"label": "Send worker to clear the jam",
             "effect": "crusher_cleared", "cost": 0,
             "note": "Worker uses cargo_gripper to extract the fragment. 15 min."},
            {"label": "Reverse crusher motor to dislodge",
             "effect": "crusher_reversed", "cost": 0,
             "note": "Risks further jamming. 50% chance it works, 50% makes it worse."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=0.25,
    ),
    RandomEvent(
        id="rich_vein_discovered",
        name="Rich Mineral Vein Discovered!",
        severity="minor",  # Minor because it's GOOD news
        description=(
            "Taskmaster spectral scan detected a concentrated sulfide pocket "
            "directly ahead of the current dig face. Estimated 3x normal "
            "copper and nickel content. Redirecting miners to this vein "
            "could significantly boost extraction for the next 2-3 weeks."
        ),
        effects={"extraction_bonus_pct": 200, "bonus_duration_days": 20},
        player_choices=[
            {"label": "Focus all miners on the vein",
             "effect": "vein_focus", "cost": 0,
             "note": "3x metal extraction for 20 days. Other tunnel expansion paused."},
            {"label": "Split effort -- mine vein + continue expansion",
             "effect": "vein_split", "cost": 0,
             "note": "1.5x metal extraction. Tunnel expansion continues at half speed."},
            {"label": "Ignore -- keep the current plan",
             "effect": "vein_ignore", "cost": 0,
             "note": "The vein will still be there later. But it might be smaller than estimated."},
        ],
        auto_resolve=False,
        auto_resolve_time_hours=0,
    ),
    RandomEvent(
        id="fan_failure",
        name="Tunnel Fan Failure -- Thermal Buildup",
        severity="moderate",
        description=(
            "Fan #3 in sector 5 has stopped spinning. No natural convection "
            "in microgravity -- temperature rising 2C/minute in that section. "
            "Sintering furnace surface temp climbing. Algae bioreactor at risk "
            "if ambient exceeds 40C. Worker needed to swap the fan unit."
        ),
        effects={"sector_temp_rise_c_per_min": 2, "sector": 5},
        player_choices=[
            {"label": "Dispatch worker with replacement fan",
             "effect": "fan_replaced", "cost": 0,
             "note": "Worker swaps the fan unit from spares. 15 min fix. "
                     "Adjacent fans increase speed to compensate until fixed."},
            {"label": "Shut down heat sources in that sector",
             "effect": "heat_sources_off", "cost": 0,
             "note": "Stops the temperature rise but halts sintering/sorting in sector 5."},
            {"label": "Ignore (hope adjacent fans compensate)",
             "effect": "hope_for_best", "cost": 0,
             "note": "RISKY: if ambient hits 50C, auto-shutdown triggers. "
                     "If it hits 40C, algae culture starts dying."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=0.5,
    ),
    RandomEvent(
        id="servo_batch_defect",
        name="Servo Batch Defect -- Accelerated Wear",
        severity="severe",
        description=(
            "Multiple workers reporting servo stalls in the same timeframe. "
            "Analysis suggests a manufacturing defect in a batch of SG90 servos "
            "shipped from Earth. Affected servos have 50% normal MTBF. "
            "Estimated 30 ants have the defective servos."
        ),
        effects={"affected_ants": 30, "mtbf_reduction_pct": 50},
        player_choices=[
            {"label": "Proactively replace all suspect servos",
             "effect": "replace_all", "cost": 0,
             "note": "30 ants offline for 1 day each. Uses 240 spare servos."},
            {"label": "Replace as they fail",
             "effect": "replace_on_fail", "cost": 0,
             "note": "Less disruption now but failures over the next 3 months."},
            {"label": "Order replacement batch in next resupply",
             "effect": "resupply_order", "cost": 500,
             "note": "Better servos arrive in the next resupply. Fix when they arrive."},
        ],
        auto_resolve=False,
        auto_resolve_time_hours=0,
    ),
    RandomEvent(
        id="comm_blackout",
        name="Earth Communication Blackout",
        severity="moderate",
        description=(
            "Solar conjunction -- the Sun is between Earth and the asteroid. "
            "No communication possible for 14 days. Colony must operate "
            "fully autonomously on last directives. Pi4 handles everything."
        ),
        effects={"comm_blackout_days": 14},
        player_choices=[
            {"label": "Accept -- colony is autonomous by design",
             "effect": "blackout_ok", "cost": 0,
             "note": "The Pi4 runs the colony. You just can't send new commands for 2 weeks."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=14 * 24,
    ),
    RandomEvent(
        id="water_ice_bonanza",
        name="Massive Ice Pocket Found!",
        severity="minor",
        description=(
            "Thermal sorter output spiked -- this section of regolith has "
            "3x the expected water content. Estimated 50 kg of extra water "
            "recoverable from this pocket. Major boost to water tank reserves."
        ),
        effects={"water_bonus_kg": 50},
        player_choices=[
            {"label": "Process all of it for bioreactor water",
             "effect": "water_to_bioreactor", "cost": 0,
             "note": "Tops off the bioreactor. Excess stored for electrolysis."},
            {"label": "Electrolyze the excess for H2 fuel",
             "effect": "water_to_h2", "cost": 0,
             "note": "Extra H2 for CO2 thrusters on cargo pods. More delta-v per pod."},
        ],
        auto_resolve=True,
        auto_resolve_time_hours=24,
    ),
]


class EventSystem:
    """Manages random event generation and resolution."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self.active_events: list[RandomEvent] = []
        self.resolved_events: list[RandomEvent] = []
        self.event_history: list[dict[str, Any]] = []
        self._check_interval_hours = 24     # Check for events once per sim-day
        self._last_check_hours = 0

    def tick(self, sim_time_hours: float) -> list[RandomEvent]:
        """Check for new random events. Returns newly triggered events."""
        if sim_time_hours - self._last_check_hours < self._check_interval_hours:
            return []
        self._last_check_hours = sim_time_hours

        new_events = []

        # Each event has a daily probability
        daily_probabilities = {
            "solar_particle_event": 0.005,       # ~2x per year
            "micrometeorite_impact": 0.003,       # ~1x per year
            "bioreactor_ph_excursion": 0.01,      # ~4x per year
            "tunnel_pressure_leak": 0.008,        # ~3x per year
            "crusher_jam": 0.02,                  # ~7x per year
            "rich_vein_discovered": 0.005,        # ~2x per year
            "servo_batch_defect": 0.001,          # ~1 every 3 years
            "comm_blackout": 0.002,               # ~1x per year (solar conjunction)
            "water_ice_bonanza": 0.003,           # ~1x per year
        }

        for event in MINING_EVENTS:
            prob = daily_probabilities.get(event.id, 0.005)
            if self._rng.random() < prob:
                # Don't fire the same event if one is already active
                if any(e.id == event.id for e in self.active_events):
                    continue
                self.active_events.append(event)
                new_events.append(event)
                self.event_history.append({
                    "event_id": event.id,
                    "time_hours": sim_time_hours,
                    "resolved": False,
                })

        return new_events

    def resolve_event(self, event_id: str, choice_idx: int = 0) -> dict[str, Any]:
        """Player resolves an active event by choosing an option."""
        for event in self.active_events:
            if event.id == event_id:
                choice = event.player_choices[choice_idx] if choice_idx < len(event.player_choices) else event.player_choices[0]
                self.active_events.remove(event)
                self.resolved_events.append(event)
                # Mark in history
                for h in self.event_history:
                    if h["event_id"] == event_id and not h["resolved"]:
                        h["resolved"] = True
                        h["choice"] = choice["label"]
                        break
                return {
                    "event": event,
                    "choice": choice,
                    "effect": choice["effect"],
                }
        return {"error": f"Event {event_id} not found"}

    def summary(self) -> dict[str, Any]:
        return {
            "active_events": len(self.active_events),
            "total_events": len(self.event_history),
            "resolved": len(self.resolved_events),
            "active": [{"id": e.id, "name": e.name, "severity": e.severity}
                       for e in self.active_events],
        }
