# AstraAnt — Analysis Notes (July 2026)

Two assessments plus the economics correction that shipped alongside them.

---

## 1. Economics correction (shipped)

The single load-bearing bug in the feasibility case: revenue was booked on **total
extraction** (~45 t on Bennu/5 yr) while the 2 kg micro-pod fleet can only ship ~9 t —
an ~80% stranded stockpile the model ignored, inflating ROI to 22,714%.

Fixed in `mission_economics.py`: value is now split into **gross-mined / stranded /
in-transit / realized**, delivery is allocated greedily by value density, and net
profit + ROI are based on **realized** (delivered-and-arrived) revenue only. Realized
ROI on the base case drops to ~6,658%, and `--water-sweep` shows it falling to ~388%
at a mature-market $2,000/kg water price. Delivery throughput — not extraction — is the
binding constraint, and the reports now say so.

---

## 2. The "Seven Eves" bootstrap scenario

> *In orbit, ~$10k of seed, and you desperately need long-term self-sufficiency from
> extracted materials of all kinds. How do you go about it?*

**The key reframe: you're consuming, not exporting.** The delivery bottleneck that wrecks
the profit case (§1) *vanishes* here — you build with the material in place. This is
actually AstraAnt's strongest scenario. ISRU value is use-in-place, not $/kg at a market
that may not exist. Survival bootstrapping is a better pitch than billionaire profit.

**The $10k seed is brutal.** That's a handful of micro-ants ($14–33 each) plus minimal
tools — nowhere near a lander's drill/power/comms/seal kit (~80–120 kg, millions). So
read "$10k of materials" as the *local stockpile you've already extracted*, and the real
question is the replication ladder, not the shopping list.

**Priority ladder (what to bootstrap first):**
1. **Water + volatiles + power** — thermal desorption of hydrated clay (no chemistry),
   CO₂/N₂ capture for pressurant, solar. Water = life, propellant, radiation mass. This
   is Year-0 mechanical-track tech that works from day one.
2. **Shelter = free pressure vessel.** Dig and seal a tunnel; rock is simultaneously the
   pressure hull, the micrometeorite shield, and the radiation shelter. Structural mass
   (regolith, sintered block, slag-glass floor) is *free and unlimited* — the opposite of
   the launch-mass regime. Progressive pressurization: 0.1 kPa → 1–3 kPa → 5–10 kPa.
3. **The replication ladder — build bodies locally, import brains.** Magnetic separation
   → iron; sacrificial-anode purification → clean metal; sinter/cast/electroform →
   chassis, legs, tools, structural members. Per CLAUDE.md the EM press already
   *self-replicates its own body + coils; only the controller chip needs Earth resupply.*
   So the **local mass fraction can approach ~95%+** with the MCU/sensors as the umbilical.
4. **Energy is the multiplier.** Solar loses ~50% to day/night and scales 1/r². The single
   biggest quality-of-life upgrade is a small fission unit (Kilopower-class): 24/7 ops,
   free process heat, eclipse immunity. Without it the doubling time is long but nonzero.

**The metric that matters: local mass fraction.** Track every kilogram of a new ant by
origin. Structure and tools go local early; the few grams of silicon per ant (controller,
sensors) stay imported until on-site chip fab (Year 20–30, speculative-but-grounded). The
honest endstate: **near-self-sufficient in mass, still Earth-dependent for a pinch of
silicon per unit** — which is exactly the Seven Eves "we can make everything but the smart
part" bottleneck.

**Failure modes to design against:** the controller chip is the hard umbilical; bearings
and actuators wear (sealed tunnels buy ~100× MTBF but not infinity); bioreactor
contamination; and power as the pacing constraint. The realistic plan is a slow,
compounding local-mass-fraction climb, not an overnight self-replicating explosion.

**What I'd do with the seed, sequenced:** water + power online → dig+seal a one-section
tunnel → magnetic-separate and sinter enough iron to build tool heads and a second-gen
chassis batch → stand up the EM press so bodies replicate locally → ration imported chips
to only the controllers → let local mass fraction compound while begging Earth (or a
resupply rocket) for one thing: more brains, and eventually a fission unit.

---

## 3. Game-code reassessment (near-term + long-term)

**What actually exists (better than a skim suggests).** ~4,700 LOC of game layer under
`astraant/gui/`. The sim is **not a spreadsheet**: `gui/simulation/sim_engine.py` steps a
headless engine that iterates every `AntAgent` through per-caste state machines, mines
voxels from an `AsteroidGrid`, tracks a `MaterialLedger`, and runs a `GameEconomy`. The
engine has **zero Ursina dependency** — the cleanest structural decision in the codebase.
Also already built despite "future" labels: boulder mechanics (hardness/HP/clearing +
tests), a year-gated tech-upgrade tree, delivery scheduling, comms delay, save/load,
tutorial/loan-shark narration. 329 test functions, several exercising the game layer.

**The single biggest gap.** The entire competitive metagame from the "Game Vision" docs is
absent: zero files for `faction`, `safety_zone`, or `size_class`; no orbital survey; no
management zoom levels. `funding.py` still has the old 3-source model — the faction
refactor hasn't started. Multi-site is faked: `mothership_count` is a scalar throughput
multiplier, not real per-site engine instances. Even the **day/night power cycle** — which
the docs flag and for which every asteroid already carries `rotation_period_hours` — is
unimplemented (no `_power_available` in the engine). So: **what shipped is a solid
single-colony real-time tunnel-digging sim with a ground-control command layer; what's
documented is a multi-faction 4X.** That's the gap.

**Smallest viable next increment: the day/night power cycle.** Data already exists, it's a
localized change (a `_power_available` fraction in `tick` gating ant activity), and it
delivers exactly the "failure that teaches" the design wants. Far better next step than
starting factions.

**Long-term structural risks.**
- **Ursina is the wrong bet for their runtime.** `gui/app.py` hard-imports Ursina/Panda3D,
  which needs an OpenGL window — unrunnable in the remote/web environments they operate in.
  The headless-engine split means a future swap to a web renderer (three.js/WASM) is
  possible *without rewriting the sim*, but Ursina itself won't reach a browser demo. (The
  `web/colony_walkthrough.html` render in this repo is the proof-of-concept for that path.)
- **`SimEngine` is a ~1,200-line god object** owning ants, manufacturing, boulders,
  economy, endgame, and command handling. Factions/multi-site/safety-zones will strain it;
  decompose into subsystems before that growth.
- **Single-colony assumptions are baked in** (one dig position, fleet-as-multiplier). The
  Director/CEO "zoom" vision needs N real engine instances — a genuine refactor.

**Reality check on scope:** of ~44 CLI commands, only 3 (`simulate`, `gui`, `saves`) are
game; the rest are the feasibility/analysis toolkit. The project is ~90% analysis tool,
10% game — but the 10% is honestly built.
