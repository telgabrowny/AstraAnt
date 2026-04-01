"""Solar power budget calculator for AstraAnt missions.

Computes power generation from solar panels at any heliocentric distance,
compares against consumption in each mission phase (transit, approach,
capture, bioleach, WAAM ops), and flags deficits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# Solar constant at 1 AU
SOLAR_FLUX_1AU_W_M2 = 1361.0  # W/m^2

# Default panel parameters
DEFAULT_PANEL_AREA_M2 = 4.0
DEFAULT_CELL_EFFICIENCY = 0.20       # 20%
DEFAULT_POINTING_LOSS = 0.05         # 5% average cosine factor
DEFAULT_DEGRADATION_PER_YEAR = 0.02  # 2% per year

# Supercap spec for printer bot charging
SUPERCAP_FARAD = 47.0   # F
SUPERCAP_VOLTS = 5.5     # V
BOT_CHARGE_POWER_W = 5.0  # W per bot


@dataclass
class SolarParams:
    """Solar panel configuration."""
    panel_area_m2: float = DEFAULT_PANEL_AREA_M2
    cell_efficiency: float = DEFAULT_CELL_EFFICIENCY
    pointing_loss: float = DEFAULT_POINTING_LOSS
    degradation_per_year: float = DEFAULT_DEGRADATION_PER_YEAR
    distance_au: float = 1.0
    years_deployed: float = 0.0


def solar_power(params: SolarParams) -> float:
    """Available solar power in watts.

    P = area * efficiency * flux/r^2 * (1-pointing) * (1-degradation*years)
    """
    flux = SOLAR_FLUX_1AU_W_M2 / (params.distance_au ** 2)
    degradation_factor = max(0.0, 1.0 - params.degradation_per_year * params.years_deployed)
    pointing_factor = 1.0 - params.pointing_loss
    return (params.panel_area_m2
            * params.cell_efficiency
            * flux
            * pointing_factor
            * degradation_factor)


# -- Mission phase definitions -----------------------------------------------

@dataclass
class PowerConsumer:
    """A single power-consuming subsystem."""
    name: str
    watts: float
    note: str = ""


@dataclass
class MissionPhase:
    """One phase of the mission with its power consumers."""
    name: str
    consumers: list[PowerConsumer] = field(default_factory=list)

    @property
    def total_watts(self) -> float:
        return sum(c.watts for c in self.consumers)


def get_mission_phases(waam_heads: int = 1, bots_charging: int = 1) -> list[MissionPhase]:
    """Return all mission phases with their power consumers.

    waam_heads: number of active WAAM print heads (100W each).
    bots_charging: number of printer bots charging simultaneously (5W each).
    """
    return [
        MissionPhase("TRANSIT", [
            PowerConsumer("Ion thruster", 65.0, "continuous"),
            PowerConsumer("ADCS", 2.0),
            PowerConsumer("Comms (beacon)", 3.0),
            PowerConsumer("Computer", 1.0),
            PowerConsumer("Heater", 5.0, "if needed"),
        ]),
        MissionPhase("APPROACH", [
            PowerConsumer("ADCS (active pointing)", 5.0),
            PowerConsumer("Star tracker", 2.0),
            PowerConsumer("Comms", 5.0),
            PowerConsumer("Computer", 1.0),
        ]),
        MissionPhase("CAPTURE", [
            PowerConsumer("Arm servos (2x3 joints)", 15.0),
            PowerConsumer("Pump (membrane)", 5.0),
            PowerConsumer("ADCS", 2.0),
            PowerConsumer("Comms", 3.0),
            PowerConsumer("Computer", 1.0),
        ]),
        MissionPhase("BIOLEACH", [
            PowerConsumer("Heater", 50.0, "thermal control"),
            PowerConsumer("Pump", 10.0),
            PowerConsumer("Comms", 3.0),
            PowerConsumer("Computer", 1.0),
            # electrowinning gets all remaining power -- not listed as fixed consumer
        ]),
        MissionPhase("WAAM_OPS", [
            PowerConsumer("Wire feed + arc", 100.0 * waam_heads, f"{waam_heads} head(s)"),
            PowerConsumer("Pump", 10.0),
            PowerConsumer("Bot charging", BOT_CHARGE_POWER_W * bots_charging,
                          f"{bots_charging} bot(s)"),
            PowerConsumer("Comms", 3.0),
        ]),
    ]


# -- Phase analysis ----------------------------------------------------------

@dataclass
class PhaseAnalysis:
    """Power analysis result for a single mission phase."""
    phase_name: str
    available_w: float
    consumed_w: float
    margin_w: float
    margin_pct: float
    deficit: bool
    consumers: list[PowerConsumer] = field(default_factory=list)
    electrowinning_w: float = 0.0  # leftover for electrowinning (bioleach/WAAM)


@dataclass
class PowerBudgetReport:
    """Complete power budget for all mission phases."""
    solar_params: SolarParams
    available_power_w: float
    phases: list[PhaseAnalysis] = field(default_factory=list)
    supercap_energy_j: float = 0.0
    supercap_charge_time_s: float = 0.0
    notes: list[str] = field(default_factory=list)


def analyze_power_budget(
    solar: SolarParams | None = None,
    waam_heads: int = 1,
    bots_charging: int = 1,
) -> PowerBudgetReport:
    """Run full power budget analysis across all mission phases."""
    if solar is None:
        solar = SolarParams()

    available = solar_power(solar)
    phases = get_mission_phases(waam_heads=waam_heads, bots_charging=bots_charging)

    report = PowerBudgetReport(
        solar_params=solar,
        available_power_w=available,
    )

    for phase in phases:
        consumed = phase.total_watts
        margin_w = available - consumed
        margin_pct = (margin_w / available * 100.0) if available > 0 else -100.0
        deficit = margin_w < 0

        pa = PhaseAnalysis(
            phase_name=phase.name,
            available_w=available,
            consumed_w=consumed,
            margin_w=margin_w,
            margin_pct=margin_pct,
            deficit=deficit,
            consumers=list(phase.consumers),
        )

        # Electrowinning gets whatever is left (bioleach and WAAM phases)
        if phase.name in ("BIOLEACH", "WAAM_OPS") and margin_w > 0:
            pa.electrowinning_w = margin_w

        if deficit:
            report.notes.append(
                f"DEFICIT: {phase.name} needs {consumed:.0f}W but only "
                f"{available:.0f}W available ({margin_w:+.0f}W)."
            )

        report.phases.append(pa)

    # Supercap charge time for printer bot
    report.supercap_energy_j = 0.5 * SUPERCAP_FARAD * (SUPERCAP_VOLTS ** 2)
    if BOT_CHARGE_POWER_W > 0:
        report.supercap_charge_time_s = report.supercap_energy_j / BOT_CHARGE_POWER_W
    else:
        report.supercap_charge_time_s = float("inf")

    return report


def format_power_budget(report: PowerBudgetReport) -> str:
    """Format power budget as human-readable text."""
    s = report.solar_params
    lines = []
    lines.append("=" * 65)
    lines.append("SOLAR POWER BUDGET")
    lines.append("=" * 65)

    lines.append("")
    lines.append("--- SOLAR GENERATION ---")
    lines.append(f"  Panel area:         {s.panel_area_m2:.1f} m^2")
    lines.append(f"  Cell efficiency:    {s.cell_efficiency * 100:.0f}%")
    flux = SOLAR_FLUX_1AU_W_M2 / (s.distance_au ** 2)
    lines.append(f"  Solar flux at {s.distance_au:.2f} AU: {flux:.1f} W/m^2")
    lines.append(f"  Pointing loss:      {s.pointing_loss * 100:.0f}%")
    if s.years_deployed > 0:
        deg = s.degradation_per_year * s.years_deployed * 100
        lines.append(f"  Degradation:        {deg:.1f}% ({s.years_deployed:.1f} yr)")
    lines.append(f"  Available power:    {report.available_power_w:.1f} W")

    lines.append("")
    lines.append("--- PHASE ANALYSIS ---")

    for pa in report.phases:
        status = "OK" if not pa.deficit else "*** DEFICIT ***"
        lines.append(f"")
        lines.append(f"  Phase: {pa.phase_name}  [{status}]")
        for c in pa.consumers:
            note = f"  ({c.note})" if c.note else ""
            lines.append(f"    {c.name:<30s} {c.watts:6.0f} W{note}")
        lines.append(f"    {'':30s} ------")
        lines.append(f"    {'Total consumed':<30s} {pa.consumed_w:6.0f} W")
        lines.append(f"    {'Available':<30s} {pa.available_w:6.0f} W")
        lines.append(f"    {'Margin':<30s} {pa.margin_w:+6.0f} W ({pa.margin_pct:+.0f}%)")
        if pa.electrowinning_w > 0:
            lines.append(f"    -> Electrowinning headroom:  {pa.electrowinning_w:.0f} W")

    lines.append("")
    lines.append("--- PRINTER BOT SUPERCAP ---")
    lines.append(f"  Supercap:           {SUPERCAP_FARAD:.0f} F / {SUPERCAP_VOLTS:.1f} V")
    lines.append(f"  Stored energy:      {report.supercap_energy_j:.0f} J")
    lines.append(f"  Charge power:       {BOT_CHARGE_POWER_W:.0f} W")
    lines.append(f"  Charge time:        {report.supercap_charge_time_s:.0f} s "
                 f"({report.supercap_charge_time_s / 60:.1f} min)")

    if report.notes:
        lines.append("")
        lines.append("--- WARNINGS ---")
        for note in report.notes:
            lines.append(f"  * {note}")

    lines.append("")
    lines.append("=" * 65)
    return "\n".join(lines)
