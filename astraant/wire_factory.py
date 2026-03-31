"""Wire Factory Pipeline Simulator.

Models the complete electroforming -> wire -> WAAM construction pipeline
inside the sous-vide bag.  The three stages are:

  1. Electroforming: Faraday's law deposits iron from acid solution onto
     a cathode wire.  Rate = current_amps * 0.02496 kg/day.
  2. Wire processing: Electroformed iron is drawn/cut to 5 m lengths and
     coiled onto ~0.15 kg bobbins ready for the WAAM print heads.
  3. WAAM printing: Bots (and the two mothership arms) consume wire at
     0.5 kg/hr each (1.1 kW per head) to build structures.

Bot fleet scaling:
  - Month 0: 2 mothership arms provide WAAM capability (not bots, but
    equivalent print heads).
  - Month 1+: Arms/bots print new bots.  Each bot = 5 kg iron, ~10 hrs.
  - Doubling time ~1 month until limited by power or wire production.

Build queue (priority order):
  1. Stirling engine -- 15 kg iron, unlocks power scaling
  2. More bots      -- 5 kg each, fleet expansion
  3. Concentrator mirrors -- 2 kg frame each, heating
  4. Shell sections  -- 500+ kg structural growth
  5. Replacement parts -- pump housings, electrode frames
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

# -- Physical constants (shared with bootstrap_sim.py) ----------------------
FARADAY_KG_PER_AMP_DAY = 0.02496   # Faraday's law: kg Fe per amp per day
WIRE_DIAMETER_MM = 1.5              # Output wire gauge
BOBBIN_MASS_KG = 0.15              # Wire per bobbin (5 m coil)
CELL_VOLTAGE = 2.0                  # V per electro-winning cell

# -- WAAM printing ----------------------------------------------------------
WAAM_KG_PER_HOUR = 0.5              # Deposition rate per print head
WAAM_KW_PER_HEAD = 1.1              # Power draw per active head

# -- Bot specs --------------------------------------------------------------
BOT_IRON_KG = 5.0                   # Iron to print one bot
BOT_PRINT_HOURS = 10.0              # Time to print one bot (one head)
INITIAL_ARMS = 2                    # Mothership arms (act as print heads)

# -- Build queue items ------------------------------------------------------
STIRLING_IRON_KG = 15.0             # Stirling engine mass
STIRLING_BUILD_HOURS = 48.0         # ~2 days to print
STIRLING_POWER_BONUS_KW = 5.0       # Power gained when Stirling is online

CONCENTRATOR_IRON_KG = 2.0          # Mirror frame mass
CONCENTRATOR_BUILD_HOURS = 4.0      # Time per mirror
CONCENTRATOR_POWER_PER_M2_KW = 0.05 # Marginal electrical gain per m2

SHELL_SECTION_KG = 500.0            # Mass of one shell section
SHELL_BUILD_HOURS = 100.0           # Time per section (one head)

REPLACEMENT_PART_KG = 3.0           # Average replacement part mass
REPLACEMENT_BUILD_HOURS = 6.0       # Time per part


@dataclass
class WireFactoryState:
    """Snapshot of the wire factory at a given hour."""
    hour: int = 0

    # Electroforming output
    wire_produced_kg: float = 0.0       # Cumulative wire produced
    wire_inventory_kg: float = 0.0      # Wire on hand (produced - consumed)
    wire_consumed_kg: float = 0.0       # Cumulative wire consumed by WAAM
    bobbin_count: int = 0               # Complete bobbins wound

    # WAAM fleet
    bot_count: int = 0                  # Printed bots (excludes 2 arms)
    active_heads: int = INITIAL_ARMS    # Arms + bots available to print
    bots_building: int = 0              # Bots currently under construction

    # Build progress
    stirling_built: bool = False
    stirling_progress_kg: float = 0.0
    concentrator_m2: float = 0.0
    shell_sections: int = 0
    replacement_parts: int = 0
    structures_built: list = field(default_factory=list)

    # Power
    power_kw: float = 1.1              # Available electrical power
    current_a: float = 544.0           # Electro-winning current

    # Build queue tracking (hours remaining on current job per head)
    _head_jobs: list = field(default_factory=list)

    @property
    def day(self) -> float:
        return self.hour / 24.0

    @property
    def month(self) -> float:
        return self.hour / (24.0 * 30.44)

    @property
    def wire_rate_kg_day(self) -> float:
        return self.current_a * FARADAY_KG_PER_AMP_DAY

    @property
    def waam_demand_kg_hr(self) -> float:
        """Wire consumed by all active heads printing at full rate."""
        return self.active_heads * WAAM_KG_PER_HOUR

    @property
    def power_used_kw(self) -> float:
        """Power consumed by electro-winning + active WAAM heads."""
        ewin_kw = self.current_a * CELL_VOLTAGE / 1000.0
        waam_kw = self.active_heads * WAAM_KW_PER_HEAD
        return ewin_kw + waam_kw


def _assign_jobs(state: WireFactoryState) -> None:
    """Assign idle heads to the next priority job.

    Priority order:
      1. Stirling engine (all available heads collaborate until done)
      2. More bots (if wire production can feed them)
      3. Concentrator mirrors
      4. Shell sections (if wire inventory allows)
      5. Replacement parts (occasional)

    Multiple heads can work on the Stirling simultaneously.  Each head
    deposits wire at WAAM_KG_PER_HOUR; the shared stirling_progress_kg
    counter tracks total progress.  When it reaches STIRLING_IRON_KG the
    engine is complete and remaining Stirling jobs are cancelled.
    """
    for i, job in enumerate(state._head_jobs):
        if job is not None:
            continue  # Head is busy

        # Priority 1: Stirling engine (multiple heads collaborate)
        if not state.stirling_built and state.wire_inventory_kg >= WAAM_KG_PER_HOUR:
            # Each head works until the shared progress counter hits the target.
            # kg_left is set high; the job completes when stirling_progress_kg
            # reaches STIRLING_IRON_KG (checked in _tick_heads).
            state._head_jobs[i] = {
                "type": "stirling",
                "hours_left": STIRLING_IRON_KG / WAAM_KG_PER_HOUR,
                "kg_left": STIRLING_IRON_KG,
                "kg_consumed": 0.0,
            }
            continue

        # Priority 2: More bots (capped by wire production sustainability)
        # Wire rate (kg/hr) must exceed total fleet WAAM demand
        wire_rate_kg_hr = state.wire_rate_kg_day / 24.0
        building_bots = sum(
            1 for j in state._head_jobs if j is not None and j["type"] == "bot")
        future_heads = state.active_heads + building_bots
        future_demand_kg_hr = (future_heads + 1) * WAAM_KG_PER_HOUR
        # Only build another bot if wire production can sustain it
        if (future_demand_kg_hr <= wire_rate_kg_hr
                and state.wire_inventory_kg >= WAAM_KG_PER_HOUR):
            state._head_jobs[i] = {
                "type": "bot",
                "hours_left": BOT_PRINT_HOURS,
                "kg_left": BOT_IRON_KG,
                "kg_consumed": 0.0,
            }
            continue

        # Priority 3: Concentrator mirrors (cap at 100 m2)
        building_conc = sum(
            1 for j in state._head_jobs
            if j is not None and j["type"] == "concentrator")
        total_conc_m2 = state.concentrator_m2 + building_conc * (CONCENTRATOR_IRON_KG / 2.0)
        if (total_conc_m2 < 100
                and state.wire_inventory_kg >= CONCENTRATOR_IRON_KG):
            state._head_jobs[i] = {
                "type": "concentrator",
                "hours_left": CONCENTRATOR_BUILD_HOURS,
                "kg_left": CONCENTRATOR_IRON_KG,
                "kg_consumed": 0.0,
            }
            continue

        # Priority 4: Shell sections (need substantial wire stock)
        if state.wire_inventory_kg >= SHELL_SECTION_KG * 0.1:
            state._head_jobs[i] = {
                "type": "shell",
                "hours_left": SHELL_BUILD_HOURS,
                "kg_left": SHELL_SECTION_KG,
                "kg_consumed": 0.0,
            }
            continue

        # Priority 5: Replacement parts (every ~720 hours, one head)
        if (state.hour > 0 and state.hour % 720 == 0
                and state.wire_inventory_kg >= REPLACEMENT_PART_KG):
            state._head_jobs[i] = {
                "type": "replacement",
                "hours_left": REPLACEMENT_BUILD_HOURS,
                "kg_left": REPLACEMENT_PART_KG,
                "kg_consumed": 0.0,
            }
            continue

        # Nothing to do -- head idles


def _tick_heads(state: WireFactoryState) -> None:
    """Advance all print heads by 1 hour.  Consume wire, complete jobs."""
    for i, job in enumerate(state._head_jobs):
        if job is None:
            continue

        # Skip Stirling jobs if engine is already done (collaborative build)
        if job["type"] == "stirling" and state.stirling_built:
            state._head_jobs[i] = None
            continue

        # How much wire this head consumes in 1 hour
        consume = min(WAAM_KG_PER_HOUR, job["kg_left"], state.wire_inventory_kg)
        if consume <= 1e-9:
            continue  # Starved -- no wire available

        state.wire_inventory_kg -= consume
        state.wire_consumed_kg += consume
        job["kg_left"] -= consume
        job["kg_consumed"] += consume
        job["hours_left"] -= 1.0

        # Stirling: track shared progress counter
        if job["type"] == "stirling":
            state.stirling_progress_kg += consume
            # Stirling complete when shared progress reaches target
            if state.stirling_progress_kg >= STIRLING_IRON_KG - 0.01:
                _complete_job(state, job)
                state._head_jobs[i] = None
                # Cancel all other Stirling jobs (engine is built)
                for j_idx, other in enumerate(state._head_jobs):
                    if other is not None and other["type"] == "stirling":
                        state._head_jobs[j_idx] = None
                continue

        # Non-Stirling job complete?
        if job["type"] != "stirling":
            if job["kg_left"] <= 0.01 or job["hours_left"] <= 0.01:
                _complete_job(state, job)
                state._head_jobs[i] = None


def _complete_job(state: WireFactoryState, job: dict) -> None:
    """Record a completed build job."""
    jtype = job["type"]
    actual_kg = job["kg_consumed"]

    if jtype == "stirling":
        state.stirling_built = True
        state.power_kw += STIRLING_POWER_BONUS_KW
        # More power = more electro-winning current
        extra_amps = STIRLING_POWER_BONUS_KW * 1000 / CELL_VOLTAGE
        state.current_a += extra_amps
        state.structures_built.append(
            {"hour": state.hour, "type": "Stirling engine",
             "kg": actual_kg})

    elif jtype == "bot":
        state.bot_count += 1
        state.active_heads += 1
        state._head_jobs.append(None)  # New head slot
        state.structures_built.append(
            {"hour": state.hour, "type": "WAAM bot",
             "kg": actual_kg})

    elif jtype == "concentrator":
        # Each frame holds ~1 m2 of reflective area
        area = CONCENTRATOR_IRON_KG / 2.0  # 2 kg per m2 frame
        state.concentrator_m2 += area
        # Small power gain from concentrator -> thermoelectric
        state.power_kw += area * CONCENTRATOR_POWER_PER_M2_KW
        state.structures_built.append(
            {"hour": state.hour, "type": "Concentrator mirror",
             "kg": actual_kg})

    elif jtype == "shell":
        state.shell_sections += 1
        state.structures_built.append(
            {"hour": state.hour, "type": "Shell section",
             "kg": actual_kg})

    elif jtype == "replacement":
        state.replacement_parts += 1
        state.structures_built.append(
            {"hour": state.hour, "type": "Replacement part",
             "kg": actual_kg})


def run_wire_factory(
    duration_days: int = 365,
    initial_current_a: float = 544.0,
    initial_power_kw: float = 1.1,
    snapshot_interval_hours: int = 24,
) -> List[WireFactoryState]:
    """Run the wire factory pipeline hour-by-hour.

    Args:
        duration_days: Simulation length in days.
        initial_current_a: Starting electro-winning current (amps).
        initial_power_kw: Starting electrical power (kW).
        snapshot_interval_hours: How often to record state snapshots.

    Returns:
        List of WireFactoryState snapshots (one per snapshot_interval).
    """
    total_hours = duration_days * 24

    state = WireFactoryState(
        hour=0,
        current_a=initial_current_a,
        power_kw=initial_power_kw,
        active_heads=INITIAL_ARMS,
        _head_jobs=[None] * INITIAL_ARMS,
    )

    snapshots: List[WireFactoryState] = []
    # Record initial state
    snapshots.append(_snapshot(state))

    # Partial bobbin accumulator
    bobbin_accum_kg = 0.0

    for h in range(1, total_hours + 1):
        state.hour = h

        # --- Stage 1: Electroforming (continuous) ---
        wire_this_hour = state.current_a * FARADAY_KG_PER_AMP_DAY / 24.0
        state.wire_produced_kg += wire_this_hour
        state.wire_inventory_kg += wire_this_hour

        # --- Stage 2: Wire processing (automatic) ---
        bobbin_accum_kg += wire_this_hour
        while bobbin_accum_kg >= BOBBIN_MASS_KG:
            bobbin_accum_kg -= BOBBIN_MASS_KG
            state.bobbin_count += 1

        # --- Stage 3: WAAM printing ---
        _assign_jobs(state)
        _tick_heads(state)

        # --- Snapshot ---
        if h % snapshot_interval_hours == 0:
            snapshots.append(_snapshot(state))

    return snapshots


def _snapshot(state: WireFactoryState) -> WireFactoryState:
    """Create an immutable copy of the current state for the snapshot list."""
    return WireFactoryState(
        hour=state.hour,
        wire_produced_kg=state.wire_produced_kg,
        wire_inventory_kg=state.wire_inventory_kg,
        wire_consumed_kg=state.wire_consumed_kg,
        bobbin_count=state.bobbin_count,
        bot_count=state.bot_count,
        active_heads=state.active_heads,
        bots_building=sum(
            1 for j in state._head_jobs if j is not None and j["type"] == "bot"),
        stirling_built=state.stirling_built,
        stirling_progress_kg=state.stirling_progress_kg,
        concentrator_m2=state.concentrator_m2,
        shell_sections=state.shell_sections,
        replacement_parts=state.replacement_parts,
        structures_built=list(state.structures_built),
        power_kw=state.power_kw,
        current_a=state.current_a,
    )


def format_report(snapshots: List[WireFactoryState]) -> str:
    """Format a human-readable report from simulation snapshots.

    Uses ASCII-only characters for Windows cp1252 compatibility.
    """
    if not snapshots:
        return "No data."

    lines: List[str] = []
    first = snapshots[0]
    last = snapshots[-1]

    lines.append("=" * 95)
    lines.append("  WIRE FACTORY PIPELINE -- Electroforming to WAAM Construction")
    lines.append("=" * 95)
    lines.append(f"  Duration: {last.hour / 24:.0f} days ({last.hour / (24*30.44):.1f} months)")
    lines.append(f"  Initial current: {first.current_a:.0f} A  |  Initial power: {first.power_kw:.1f} kW")
    lines.append(f"  Wire gauge: {WIRE_DIAMETER_MM} mm  |  Bobbin size: {BOBBIN_MASS_KG} kg")
    lines.append(f"  WAAM rate: {WAAM_KG_PER_HOUR} kg/hr per head at {WAAM_KW_PER_HEAD} kW")
    lines.append("")

    # Monthly summary table
    lines.append("--- MONTHLY SUMMARY ---")
    hdr = (f"{'Month':>5} | {'Wire kg':>9} | {'Inv kg':>8} | {'Bobbins':>7} | "
           f"{'Bots':>4} | {'Heads':>5} | {'Stirlng':>7} | {'Conc m2':>7} | "
           f"{'Shells':>6} | {'Power':>7} | {'Amps':>7}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    # Show monthly snapshots (every ~30 days = ~720 hours)
    hours_per_month = int(30.44 * 24)
    shown_months = set()
    for s in snapshots:
        month = int(s.hour / hours_per_month)
        if month in shown_months:
            continue
        shown_months.add(month)
        stirling_str = "YES" if s.stirling_built else "no"
        lines.append(
            f"{month:>5} | {s.wire_produced_kg:>9.1f} | {s.wire_inventory_kg:>8.1f} | "
            f"{s.bobbin_count:>7} | {s.bot_count:>4} | {s.active_heads:>5} | "
            f"{stirling_str:>7} | {s.concentrator_m2:>7.1f} | "
            f"{s.shell_sections:>6} | {s.power_kw:>5.1f}kW | {s.current_a:>6.0f}A"
        )

    # Build log
    lines.append("")
    lines.append("--- BUILD LOG (first 40 items) ---")
    for i, item in enumerate(last.structures_built[:40]):
        day = item["hour"] / 24.0
        lines.append(
            f"  Day {day:>6.1f}: {item['type']:<22s} ({item['kg']:.1f} kg)")
    if len(last.structures_built) > 40:
        lines.append(f"  ... and {len(last.structures_built) - 40} more items")

    # Final summary
    lines.append("")
    lines.append("=" * 95)
    lines.append("  FINAL STATE")
    lines.append("=" * 95)
    lines.append(f"  Wire produced:      {last.wire_produced_kg:>10.1f} kg "
                 f"({last.wire_produced_kg / 1000:.2f} tonnes)")
    lines.append(f"  Wire consumed:      {last.wire_consumed_kg:>10.1f} kg")
    lines.append(f"  Wire inventory:     {last.wire_inventory_kg:>10.1f} kg")
    lines.append(f"  Bobbins wound:      {last.bobbin_count:>10}")
    lines.append(f"  WAAM bots built:    {last.bot_count:>10}")
    lines.append(f"  Active print heads: {last.active_heads:>10} "
                 f"({INITIAL_ARMS} arms + {last.bot_count} bots)")
    lines.append(f"  Stirling engine:    {'BUILT' if last.stirling_built else 'NOT YET'}")
    lines.append(f"  Concentrator area:  {last.concentrator_m2:>10.1f} m2")
    lines.append(f"  Shell sections:     {last.shell_sections:>10} "
                 f"({last.shell_sections * SHELL_SECTION_KG / 1000:.1f} tonnes)")
    lines.append(f"  Replacement parts:  {last.replacement_parts:>10}")
    lines.append(f"  Final power:        {last.power_kw:>10.1f} kW")
    lines.append(f"  Final current:      {last.current_a:>10.0f} A")
    lines.append(f"  Final wire rate:    {last.current_a * FARADAY_KG_PER_AMP_DAY:>10.1f} kg/day")
    total_built_kg = sum(item["kg"] for item in last.structures_built)
    lines.append(f"  Total mass built:   {total_built_kg:>10.1f} kg "
                 f"({total_built_kg / 1000:.2f} tonnes)")
    lines.append("")

    # Sanity checks
    lines.append("  SANITY CHECKS:")
    if last.wire_inventory_kg < -0.01:
        lines.append("    [FAIL] Wire inventory went negative!")
    else:
        lines.append("    [OK]   Wire inventory >= 0")

    delta = abs(last.wire_produced_kg - last.wire_consumed_kg - last.wire_inventory_kg)
    if delta < 1.0:
        lines.append("    [OK]   Wire produced = consumed + inventory (conservation)")
    else:
        lines.append(
            f"    [WARN] Conservation delta: {delta:.1f} kg "
            f"(produced={last.wire_produced_kg:.1f}, "
            f"consumed={last.wire_consumed_kg:.1f}, "
            f"inv={last.wire_inventory_kg:.1f})")

    lines.append("=" * 95)

    return "\n".join(lines)
