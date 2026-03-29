# AstraAnt — Project Instructions for Claude

## Project Identity
AstraAnt is an ant swarm asteroid mining simulator and feasibility tracker. It must be **"billionaire-ready" at all times** — if someone offered unlimited funding and a rocket launch tomorrow, the project's outputs should specify exactly what to buy, build, test, and launch.

## Repository
- GitHub: https://github.com/telgabrowny/AstraAnt
- Local: C:\Users\Taurik\Dropbox\robotStuff\AstraAnt

## Quality Bar
- Every catalog entry must map to a real purchasable part with real specs
- Every physics number must be defensible against published literature
- Every config must be actionable — you could hand it to an engineer and they'd know what to build
- The testing/simulation pipeline must identify unknowns that need physical testing before flight
- Always maintain a readiness gap list: proven vs. needs testing vs. open research question
- Use ASCII-only characters in all Python output (Windows cp1252 compatibility)

## Architecture Decisions (Locked In)
- **Underground tunnel operations** as primary operating model
- **Sealed tunnels** at 1-10 kPa (extends COTS component MTBF ~100x)
- **3-caste system with modular tools**: Worker (6 legs + 2 mandibles, ~$33, RP2040, swaps tool heads), Taskmaster (~$75, ESP32-S3, permanent sensors), Surface Ant (~$1242, vacuum-rated Maxon, aluminum chassis)
- **7 modular tool heads**: drill, scoop, paste nozzle, thermal rake, sampling probe, cargo gripper, panel brush. Magnetic clip mount, all 3D-printable via OpenSCAD.
- **Self-sustaining biology**: Bacteria self-replicate, sugar grown on-site from algae photobioreactor, water recovered from asteroid ice, waste becomes tunnel sealant
- **Three extraction tracks**: mechanical, bioleaching, hybrid (formerly A/B/C)
- **Centrifuge bioreactors** for microgravity fluid handling (30% mass overhead)
- **Modular mothership**: drill, power, comms, sealing, cargo, bioreactor modules
- **Multi-destination economics**: lunar orbit (first stage), Mars orbit (long-term)
- **MicroPython** control code from the start
- **Supervised autonomy**: autonomous day-to-day, ground sends high-level commands with realistic comm delay
- **Ursina Engine** for 3D interactive GUI (pip-installable, pure Python, Panda3D underneath)

## Tech Stack
- Python 3.10+, MicroPython for ant firmware
- PyYAML for catalog/configs
- Click for CLI
- Ursina for 3D GUI (planned)
- SciPy for bioreactor ODE simulation (Monod kinetics)
- pytest for testing

## Project Structure
```
AstraAnt/
  astraant/           # Python package
    __init__.py
    catalog.py        # YAML catalog loader
    cli.py            # Click CLI
    configs.py        # Ant/mothership config loader
    feasibility.py    # Mass budget, cost, break-even calculator
    bioreactor.py     # Monod kinetics ODE bioreactor simulation
    sensitivity.py    # Parameter sweep analysis
    scad_generator.py # OpenSCAD parametric tool models
    wiring.py         # Pin-to-pin wiring diagrams
    readiness.py      # Readiness assessment framework
    gui/              # Ursina 3D visualization
  catalog/            # Component database (YAML files)
    parts/            # 15+ real electronic components
    species/          # 7 bioleaching organisms
    asteroids/        # 7 target asteroids
    reagents/         # 5 chemicals
    sealing/          # Tunnel sealing materials
    tools/            # 7 tool head YAML files
  configs/            # Mission configurations
    ants/             # worker.yaml, taskmaster.yaml, surface_ant.yaml
    mothership/       # drill, power, comms, sealing, cargo, bioreactor + more
  tests/              # pytest test suites
  scad/               # Generated OpenSCAD .scad files
  firmware/
    worker/           # MicroPython for RP2040
    taskmaster/       # MicroPython for ESP32-S3
  output/             # Generated reports, BOMs (gitignored)
```

## CLI Commands
```
astraant catalog summary|parts|asteroids|species|tools|stale
astraant ant list|info <caste>
astraant analyze [--workers N --track mechanical|bioleaching|hybrid --asteroid ID --destination lunar_orbit|mars_orbit]
astraant compare
astraant readiness [--track mechanical|bioleaching|hybrid]
astraant sensitivity [--workers N --track mechanical|bioleaching|hybrid]
astraant simulate [--workers N --days 30 --track mechanical|bioleaching|hybrid]
astraant build bom <caste> [--track mechanical|bioleaching|hybrid]
astraant build wiring <caste> [--track mechanical|bioleaching|hybrid]
astraant build scad [tool_id] [--all]
astraant gui [--workers N --asteroid ID --track mechanical|bioleaching|hybrid]
astraant economics [--asteroid ID --years 5 --reality-check]
astraant composition [--asteroid ID --batches 200]
astraant scaling [--track mechanical|bioleaching|hybrid --baseline N]
astraant price-report [--stale-days 90]
```

## Development Practices
- Run `pytest tests/` after changes — all tests must pass
- Periodic code reviews to catch issues early
- Conventional commits (feat/fix/docs/test/refactor)
- ASCII-only in CLI output (no unicode box-drawing or arrows — Windows terminal breaks)
- Keep catalog extensible — adding a new part/asteroid = dropping a YAML file
- Test coverage for all calculator logic

## GUI Plan (Ursina Engine)
Build phases:
1. Window + procedural asteroid + orbit camera
2. Procedural 6-legged spider ant models (3 castes, color-coded)
3. Mothership on surface with solar panels, tunnel entrance
4. Simulation engine (ant state machines, tunnel growth)
5. UI overlay (status dashboard, time controls)
6. Ground control with comm delay (player as Earth operator)
7. Polish (LOD, tunnel interior, hauled material visuals)
8. Bioleaching/hybrid bioreactor visualization

Ant models: procedural from primitives (ellipsoid body, cylinder legs, tripod gait animation)
- Worker: orange, small, visible hopper + drill tool
- Taskmaster: blue, larger, sensor cluster on head, wired tether
- Courier: silver/green, largest, solar panel on back, small sail

## Readiness Assessment Framework
At any time, the system should classify every aspect as:
- **PROVEN**: Can order/build today. Real parts, tested designs.
- **NEEDS_PHYSICAL_TEST**: Must build and test before flight commitment.
- **NEEDS_SIM_VALIDATION**: Our simulator answers this question.
- **OPEN_RESEARCH**: Needs more investigation, no clear answer yet.

Key items needing physical testing:
- SG90 servo MTBF in 5 kPa sealed environment
- Regolith sintering effectiveness with analog materials
- Bioreactor centrifuge bacterial growth in simulated microgravity
- Ant locomotion in microgravity (parabolic flight or drop tower)
- Tunnel sealing pressure retention
- ESP32-S3 SEU rate under 2m regolith shielding

## Adding New Data
- **New asteroid**: Drop a YAML file in `catalog/asteroids/` following `catalog/SCHEMA.md`
- **New part**: Drop a YAML file in `catalog/parts/`
- **New species**: Drop a YAML file in `catalog/species/`
- **Price update**: Edit the supplier price + date_checked in the part's YAML, add to price_history

## Key Numbers to Remember
- Worker ant: $33 (prototype), ~$14 (production)
- Taskmaster ant: $75 (prototype), ~$41 (production)
- Surface Ant: $1,242 (prototype), ~$807 (production)
- 300 kg water dominates bioleaching/hybrid launch mass (bioreactor wet mass = 410 kg, not 110 kg dry)
- 2m regolith = ~70-80% GCR reduction (radiation shielding)
- 5 kPa tunnel pressure stops lubricant outgassing, extends COTS MTBF ~100x
- Solar power scales with 1/r^2 — Psyche at 2.9 AU gets only 12% of 1 AU power
- CP1 polyimide sail: ~7 g/m^2 film, NOT 50g for 25 m^2 (real mass ~175g film + booms)
- NEA surface gravity is negligible for fluid dynamics (Bennu: 6 μm/s^2)

## Current Stats
- 100 tests passing
- 17+ catalog parts, 7 asteroids, 7 species, 5 reagents, 9 tool heads
- 12 mothership modules (including compute, propulsion, nuclear, manufacturing, hull layout, landing sequence)
- 22 CLI commands
- Bioreactor ODE simulation with Monod kinetics
- Voxel grid asteroid interior (Minecraft-style geology with mineral veins)
- Composition variability model (6 spatial zones per asteroid type)
- Statistical scaling model (10 to 100K ants)
- Full mission economics with reality check + game economy (cash flow, transit delay)
- Mission planner with 9 objectives (cheapest profit to Interstellar habitat)
- Endgame habitat tracker (progressive cone-to-cylinder, 1g target)
- In-situ manufacturing simulation (build ants from asteroid materials)
- Material ledger (every kg tracked from mine face to cargo pod)
- Per-component failure model with individual part testing + salvage
- Anomaly detection system (scientific + fanciful findings)
- Ion propulsion for asteroid redirection + nuclear reactor options
- Real orbital mechanics (Kepler's equation, asteroid positions at dates)
- 10 OpenSCAD printable models (chassis + tools + pod scaffold + mothership + servo adapter)
- Real MicroPython firmware: gait controller, radio protocol, command handler, sensor drivers
- Taskmaster squad manager with command dispatch and failure recovery
- GUI: 3D asteroid, procedural ants, tunnel cutaway, ground control, camera modes
- Streamlit web dashboard
- Price tracking and staleness detection
- Solar sail trajectory estimation + micro-pod return vehicles
- Phase 2 facilities (8 types + humanoid construction crew)
- Single-launch mission planner (everything fits in one Starship)

## Game Vision & Strategy (Locked In)

### Identity
AstraAnt is an **educational hard sci-fi management sim disguised as an indie game**. It is NOT marketed as educational -- the education is the side effect of engagement, like how Kerbal taught orbital mechanics without calling itself a textbook. The pitch: **"Everything in this game is real. The parts are real. The physics are real. The ants are real robots you could build. We just haven't launched them yet."**

### Genre Neighbors
Factorio, Oxygen Not Included, Kerbal Space Program, Dwarf Fortress, Shapez, Mindustry. Complex systems where understanding the real mechanics IS the gameplay.

### The Killer Differentiator: "Bridge to Reality"
No other game does this. The outputs are REAL:
- BOM = real parts with real Digikey/Mouser links
- SCAD files = real 3D-printable models
- Firmware = real MicroPython you could flash on an RP2040
- Wiring diagrams = real pin-to-pin connections
- Physics = defensible against published literature

This must be preserved and emphasized. An "Export to Reality" feature should be a first-class GUI element.

### Visual Aesthetic: Blueprint/Schematic
- The art direction is **technical drawings and engineering schematics** -- something you wouldn't be embarrassed to show your boss at work
- Clean, precise, professional. Not cartoonish, not gritty-realistic
- Think: engineering diagrams that happen to be interactive
- Procedural models are fine but should feel intentionally schematic, not placeholder
- Color-coding remains: orange workers, blue taskmasters, green/silver surface ants

### Game Loop (what makes it fun)
1. **Planning phase**: Pick asteroid, design swarm, choose track, set budget (CLI analysis tools become the planning UI)
2. **Execution phase**: Watch colony mine, grow, fail, recover. Ground control with comm delay -- you send orders and watch them execute (or not)
3. **Decision tension**: Which track? Which asteroid? Expand or consolidate? Fix failures or scrap and rebuild?
4. **Progressive complexity**: Start with 10 workers + drill on Bennu. Unlock bioleaching. Unlock manufacturing. Unlock Phase 2. Each layer reveals more real engineering.
5. **Failure states that teach**: Ant dies from current limit error. Tunnel depressurizes from skipped sealing. Bioreactor crashes from sugar starvation. Each failure teaches real engineering.
6. **Endgame**: From sleeping ring to Interstellar habitat. The long game.

### Monetization Strategy
- **$5-10 base price** on Steam. Not free -- a price signals quality and filters for engagement.
- **Cosmetic-only skins/DLC**: Ant hats, paint jobs, mothership decals, tunnel lighting. Cute but never gameplay-affecting.
- **Educational licensing**: Classroom/STEM program versions are a potentially larger market than indie gaming.
- **Launch path**: Free demo on itch.io first for feedback, Steam when polished.

### Performance Philosophy (The Dwarf Fortress Principle)
- Optimize per-ant computation cost. Use profiling (`profile_sim.py`), fix memory leaks, cache aggressively.
- But do NOT fake the simulation to hit a framerate. If 10K ants doing real physics is slow, that's honest and respected.
- "Slow because it's doing real work" is a feature. "Slow because it's badly written" is a bug.
- Players who run Dwarf Fortress understand this tradeoff and respect it.

### ITAR / Export Control
- Current scope (COTS hobby parts, published physics, educational engineering) is clearly exempt under fundamental research and public domain exclusions.
- Same legal territory as Kerbal Space Program.
- If the project ever specifies actual flight-qualified rad-hardened components or real mission-critical trajectories, get legal review at that point. Not now.

### AI Development Transparency
- Solo developer, AI-assisted development. All physics and engineering validated against published literature.
- The developer is the domain expert and architect; AI is the development workforce.
- Steam requires AI content disclosure -- be straightforward about it.
- Quality of the output matters, not the toolchain. Nobody questions an architect for using power tools.

### Community Strategy
- **Maker/STEM crossover** is the core audience. People who get excited about "I can actually print and build these."
- Community builds (people posting physical ant robots with flashed firmware) are the best possible marketing.
- Discord/subreddit for the community. Let builders shape the roadmap.

### Space Law & Safety Zones
Real legal basis (Outer Space Treaty 1967, U.S. SPACE Act 2015, Artemis Accords 2020+):
- **You own what you extract, never the celestial body.** Like fishing in international waters.
- **Safety zones** are operational buffers around active sites (Artemis Accords). Not sovereignty, but "don't land on my drill site."
- Competing operations on the same asteroid are legally permitted. First-mover advantage is practical (good site), not legal (no ownership).

In-game: safety zone is a visible colored perimeter around your operations. Other factions must respect it, but can establish their own elsewhere on the same body.

### Faction System (National Space Law Frameworks)
Factions are based on real national/institutional differences in space law, funding models, and engineering culture. Each must feel meaningfully different to PLAY, not just cosmetically different.

**Competition trigger:** Early game is solo (training wheels -- learn systems, establish colony). After a milestone threshold, competing factions arrive on your asteroid. Safety zones start mattering. This is the "training wheels off" transition.

#### Faction Roster

**United States (SPACE Act)**
- Private commercial model. Investor-funded (volatile but flexible).
- Medium safety zones (Artemis Accords compliant).
- FAA/FCC licensing = regulatory delay before launch.
- Tech bonus: best launch infrastructure, widest part catalog.
- Weakness: investors get impatient, regulatory paperwork.

**China (State Enterprise)**
- Government IS the company. State-directed, 50-year plans.
- Large safety zones (broad interpretation of "operational area").
- No shareholder pressure. Massive stable funding.
- Tech bonus: nuclear propulsion R&D, patient long-term investment.
- Weakness: political directives override engineering ("mine HERE"), less adaptive.

**Russia (Roscosmos)**
- State corporation, historically strong, underfunded.
- Aggressive safety zone claims (Soviet-era posture).
- Tech bonus: best nuclear thermal propulsion (TOPAZ heritage), high risk tolerance.
- Weakness: budget constraints = cheaper hardware = more failures.

**Luxembourg/EU (SpaceResources.lu)**
- Most business-friendly regulatory framework. Lowest barriers.
- Smallest safety zones (cooperative philosophy).
- No independent launch capability -- buys rides.
- Tech bonus: favorable taxes, EU market, collaboration bonuses with other factions.
- Weakness: slow consensus decisions, dependent on others for launch.

**Gulf States / UAE**
- Sovereign wealth fund. Nearly unlimited patient capital.
- Medium safety zones.
- Tech bonus: deep pockets, can purchase best hardware/talent immediately.
- Weakness: less institutional experience, dependent on imported expertise early.

**Japan (JAXA)**
- Already returned real asteroid samples (Hayabusa/Hayabusa2).
- Smallest safety zones (respectful, cooperative).
- Tech bonus: precision engineering (lower failure rates), proven asteroid ops.
- Weakness: smallest budget, conservative expansion pace.

**India (ISRO)**
- Budget space power. Reached Mars for less than the movie Gravity cost.
- No mining-specific legislation (gameplay: regulatory ambiguity = flexibility + risk).
- Tech bonus: extreme cost efficiency (ants manufactured cheaper).
- Weakness: smaller launch capacity, less deep-space heritage.

#### Faction Gameplay Axes
| Axis | What Varies |
|------|-------------|
| Funding model | Private investors vs. state budget vs. sovereign wealth |
| Safety zone radius | Aggressive (Russia/China) vs. cooperative (Japan/Luxembourg) |
| Regulatory delay | Heavy (US/EU) vs. minimal (Luxembourg/UAE) |
| Tech bonus | Nuclear (Russia), cost (India), reliability (Japan), launch (US), capital (UAE) |
| Risk tolerance | Conservative (Japan) vs. aggressive (Russia/China) |
| Starting capital | Low (India/Russia) vs. high (UAE/US) vs. massive-but-slow (China) |

#### Design Principles for Factions
- No faction is "best." Each has real tradeoffs from real institutional differences.
- Faction choice affects gameplay mechanics, not just flavor text.
- All factions play the same core game (ants, tunnels, extraction) but the constraints and bonuses shape strategy.
- Factions should teach players about real differences in how nations approach space.

### Faction System vs. Current Funding/Loan Shark System

**Current state:** `funding.py` has 3 funding sources (Loan Shark / NASA / Bootstrapper) that set budget, interest rate, and rocket capacity. `loan_shark.py` is a narrator character who funds you, charges interest, and delivers tutorial tooltips with personality. The loan shark's writing is good -- keep the tone and tutorial narration approach.

**Future direction:** The faction system REPLACES the funding sources as the primary "game start" choice. Instead of picking a funding source, you pick a faction. Each faction implies:
- A funding model (replaces loan shark interest rates / NASA milestones / bootstrapper poverty)
- A narrator personality (each faction gets its own voice -- Chinese bureaucrat, Russian mission commander, Indian chief engineer, etc. Same tutorial content, different delivery)
- Tech bonuses, safety zone size, regulatory constraints
- Competing AI factions that arrive later

**Migration path (phased):**
1. **Phase 1 (now):** Keep loan shark + funding system as-is. It works.
2. **Phase 2:** Refactor funding sources into faction definitions. The loan shark becomes the US/private-investor faction narrator. NASA partnership becomes its own faction variant. Each faction gets a narrator with the same tutorial tooltip structure but different personality.
3. **Phase 3:** Add AI competitor factions. Safety zones. Competition trigger after early-game milestone.
4. **Phase 4:** Full faction diplomacy -- trade agreements, safety zone disputes, joint ventures.

**What to preserve from loan_shark.py:**
- The tutorial tooltip architecture (trigger-based, fires once, explains mechanics)
- The narrator personality approach (character voice makes dry info engaging)
- The mood system (narrator reacts to your performance)
- The financial pressure mechanic (debt/interest as pacing)

**What changes:**
- Instead of one narrator, each faction has its own voice
- Instead of just debt pressure, each faction has unique constraints (political directives, milestone requirements, budget caps, regulatory delays)
- The "paid off" moment becomes faction-specific (US: investor becomes partner. China: promoted to next Five Year Plan. India: ISRO publishes your results as national achievement.)

#### Hidden Faction: Free Mars
- Not selectable at game start. Appears as an AI faction mid-to-late game.
- Covert operation funded by siphoning from legitimate Mars colony budgets.
- Motivation: stockpile resources for declaring Martian independence. Not profit.
- Gameplay: they HOARD, not sell. Deliberately inconspicuous safety zones. No market activity.
- Reveal moment: when stockpile threshold is met, they declare independence. Suddenly a real faction with the largest material reserve but no trade relationships.
- Grounded in real academic work on Mars colony governance and communication-delay-driven independence.

### Technology Progression System (The Real Tech Tree)

Tech upgrades are a **teaching mechanism**. Each unlock reveals a real technology the player may never have heard of. The "aha" moment when bioleaching arrives and suddenly you're extracting 5x the copper from the same regolith you've been processing for 3 years -- that teaches what bioleaching IS by showing what it DOES.

#### What You Can Do With Just Crushed Gravel (Year 0, No Chemistry)
The early game is the mechanical track. Real extraction from regolith without biology:
- **Thermal sorting**: Heat regolith. Water ice sublimes at ~200K, CO2 at ~195K. Collect both. Water = hugely valuable. CO2 = feedstock for sugar production later.
- **Magnetic separation**: Iron-nickel grains stick to a magnet. C-type asteroid meteoritic metal is already alloyed. No chemistry needed.
- **Density sorting**: Centrifuge or vibration table. Heavy metal grains separate from light silicates. Works in any gravity.
- **Spectral identification**: AS7341 11-channel spectral sensor (already in catalog) identifies minerals by reflected wavelength. "What did we just dig up?"
- **Bulk sintering**: Heat regolith until it fuses into solid blocks. Structural material for tunnel walls, habitat sections. No purity needed.

This is a legitimate real-world approach. Less efficient than bioleaching, but it works and produces water + bulk metals + construction material from day one.

#### Tech Tree (grounded in real timelines)

| Era | Unlock | Real Basis | Gameplay Impact |
|-----|--------|-----------|-----------------|
| **Year 0** | Mechanical extraction, thermal sort, water recovery, magnetic separation | Today's COTS hardware | Baseline operations. Water + bulk metals. |
| **Year 2-3** | Bioleaching (resupply rocket with bacteria + bioreactor) | Proven Earth tech, ISS experiments | 5x extraction purity. Rare earths accessible. Revenue jump. Requires $X resupply rocket cost. |
| **Year 5-8** | Modular fission (Kilopower-class, 10kW) | NASA KRUSTY tested 2018, flight unit in dev | Unlimited power. Enables 24/7 ops in shadow, deeper asteroid ops. |
| **Year 8-12** | Engineered extremophiles (synthetic biology) | Current synbio trajectory | Higher bioleaching yields. New target metals. Faster cycles. |
| **Year 10-15** | Metal 3D printing (laser sintering from extracted metals) | Exists today, miniaturization trajectory | Print ant chassis locally. Print tools, structural parts. Reduces Earth dependency. |
| **Year 15-25** | Fusion micro-reactor (50-100kW) | Speculative but plausible (Commonwealth Fusion, Helion timelines) | Order-of-magnitude power increase. Enables energy-intensive refining. |
| **Year 20-30** | On-site chip fabrication (simple ASICs from asteroid silicon) | Extremely speculative but not impossible with asteroid-purity silicon | Print basic control circuits locally. Reduce resupply to raw wafers. |
| **Year 30-50** | Full self-replication (builds everything including electronics) | The endgame | Colony no longer needs Earth. Independence is physically possible. |

#### Tech Tree Design Principles
- **Each unlock should be a resupply rocket.** Real cost, real delay, real decision: is this upgrade worth the investment now? The rocket itself is a gameplay event (months of anticipation, loading manifest, watching it arrive).
- **No unlock is mandatory.** A pure mechanical colony works forever -- just less efficiently. Bioleaching is better but costs a resupply. Nuclear is amazing but expensive. Players who never unlock bioleaching still have a viable game.
- **Unlocks teach by demonstration.** Don't explain bioleaching in a textbook popup. Let the player see their extraction rates triple. THEN the tutorial tooltip explains what just happened.
- **Hardware aging is real.** COTS parts from Year 0 fail faster than Year 15 parts. The RP2040 that was state-of-art at launch is ancient by Year 20. Resupply rockets can include upgraded MCUs, better servos, rad-hardened components. Same ant body, better guts.
- **The speculative stuff is flagged.** Year 0-10 is real hardware. Year 10-20 is "plausible near-future." Year 20+ is "speculative but grounded." The game should be transparent about which tier each tech falls in.
- **Manufacturing fidelity scales with tech era.** Early: sintered regolith blocks (crude). Mid: metal 3D printing (functional parts). Late: precision fabrication (electronics). Each tier of manufacturing capability lets you build more of the colony locally.

### Management Scaling Model (The Zoom Principle)

The player's role changes as the empire grows. The simulation always runs at full ant-level fidelity (Dwarf Fortress principle). What changes is the player's *interface* to that simulation -- like Google Maps, same data, different zoom level.

**Year 0-5: The Engineer (1 mothership, ~100 ants)**
- Hands-on. Watch ants dig. Respond to failures. Learn every system.
- This is the solo continent. The Civ early game. The core experience.

**Year 5-15: The Site Manager (2-3 motherships)**
- Tab between sites. Each runs autonomously.
- Intervene when AI flags issues: "Site 2: bioreactor pH excursion, auto-recovery failed."
- Can dive into real-time ant view on any site, but don't have to.

**Year 15-30: The Director (5-10 motherships)**
- Strategic map: asteroid positions, mothership locations, cargo trajectories, revenue flows.
- Set policies, not orders: "Site 3: prioritize water." "Site 7: build toward habitat."
- Each site is a dashboard card. Dive in only when you want to or when flagged critical.

**Year 30-50+: The CEO (dozens of motherships)**
- Corporation dashboard. Capital allocation, tech investment, expansion, faction diplomacy.
- Never see individual ants unless you choose to.
- Decisions: which asteroids next, resupply allocation across sites, habitat endgame, faction deals.

**Design principles:**
- The player's role changes, not the simulation. All sites always run full ant-level sim.
- Player can zoom into any site at any time. The detail is always there.
- Communication delay enforces the right management style: you send goals, not commands. At scale, you're just sending goals to more sites.
- No management level is "better." Year 0 hands-on play is as valid as Year 50 CEO play. Players who never expand past one site have a complete game.

### Asteroid Scarcity Gradient

Space is vast. Competition is a consequence of choosing premium targets, not forced.

| Tier | Count | Character | Competition |
|------|-------|-----------|-------------|
| **Premium** | ~7-10 | The catalog asteroids (Bennu, Ryugu, etc). Confirmed composition, low delta-v, proven water. | Contested. Multiple factions want these. |
| **Characterized** | ~200-500 | Procedurally generated from real NEA distributions. Orbital parameters and spectral class known, composition estimated but uncertain. | Light competition. Some factions try these. |
| **Frontier** | Thousands | Poorly characterized, high delta-v, expensive to reach. Might be gold, might be dry gravel. | Nobody else bothers. All yours. |

"Just pick another asteroid" is a valid strategy. Like real estate: Manhattan (Bennu, contested) vs. Montana (frontier, solo). Both work. Different risk/reward.

### Conflict Model (Economic, Not Military)
No sabotage. No combat. Interesting conflicts are economic and logistical:
- **Resource race**: same asteroid, two operations. Platinum vein runs through the middle. Who reaches it first?
- **Market pressure**: two factions flooding lunar orbit with water craters the price.
- **Safety zone disputes**: your tunnel network approaching their boundary. Negotiate or reroute.
- **Cooperation**: their bioreactor is better, your launch capacity is bigger. Joint venture?
- **Strategic retreat**: competition makes this rock unprofitable. Redeploy mothership. Real cost, real time, valid choice.

### Landing Site Selection & Orbital Survey

**Real-world basis:** Every real asteroid mission (OSIRIS-REx, Hayabusa2) spends months in orbit surveying before picking a landing/sampling site. Site selection is a major engineering decision based on terrain, composition, accessibility, and safety.

**Existing foundations:**
- `landing_sequence.yaml`: describes 24-hour survey orbit, terrain mapping, "find flattest area near equator." Narrative only, no code.
- `asteroid_grid.py`: 3D voxel grid with mineral veins, zones, richness multipliers. Interior geology exists but is invisible from orbit.
- `composition.py`: 6 spatial zones per asteroid type. Depth variation modeled.
- `multi_site_bennu.yaml`: 16 equatorial sites, static config.

**What needs building (future):**

1. **Surface terrain model**: 2D height map with roughness, slope, boulder density. Generated procedurally per asteroid. Determines landing difficulty and initial tunnel orientation.

2. **Orbital survey phase**: Pre-landing gameplay. Mothership orbits, sensors gradually reveal surface data over hours/days:
   - Visual camera: terrain roughness, boulder fields, obvious features
   - IR/thermal: subsurface ice deposits (warm spots = buried volatiles)
   - Spectral: surface mineral hints (but NOT full interior knowledge -- that requires digging)
   - Gravity gradiometry: density variations suggest interior structure but imprecisely

3. **Information asymmetry is the game**: You get partial data from orbit. You make your best guess. You find out what's really underground when you start digging. A "perfect" landing site from orbit might have barren interior. A mediocre-looking site might sit on top of a platinum vein. This is real -- OSIRIS-REx's sample site selection involved exactly this uncertainty.

4. **Site scoring heuristic**: Evaluate candidates on terrain flatness, estimated subsurface composition, proximity to other sites (multi-mothership ops), solar exposure, comm line-of-sight.

5. **Landing site UI**: During approach phase, player sees a 3D asteroid surface with survey data overlaid. Heat maps for composition estimates, slope coloring, boulder markers. Click to place landing marker. Confirm to commit. Irreversible once anchored (real constraint -- you screw-anchor into the surface).

6. **Real satellite data integration**: For the 7 catalog asteroids, actual shape models and surface maps exist from real missions (Bennu: OSIRIS-REx global survey, Ryugu: Hayabusa2 mapping). These could be used directly or as references for procedural generation fidelity.

**Landing site selection feeds the competition model**: on a contested asteroid, the best landing sites get taken first. Arriving second means choosing between a suboptimal site or a different asteroid entirely.

### Boulder & Obstacle Mechanics

**Real-world basis:** C-type asteroids like Bennu are rubble piles -- loose gravel held together by micro-cohesion and negligible gravity. Bennu's surface has boulders up to 30m. Interior is a mix of loose regolith, cobbles, and consolidated boulders. OSIRIS-REx found Bennu's surface far more boulder-strewn than expected.

**Current state:** `asteroid_grid.py` has a `void_rubble` zone type but all voxels mine identically. No hardness, no obstacles, no decision points when digging.

**Material size classes (relative to ~10cm worker ant body):**

| Class | Size | Handling | Tool Needed |
|-------|------|----------|-------------|
| **Regolith** (sand/gravel) | <5cm | Scoop and carry. One worker, one load. Most of what you dig through. | scoop_head |
| **Cobbles** | 5-30cm | One ant can push/roll in microgravity (no weight, but inertia is real). Can't scoop. | cargo_gripper |
| **Boulders** | 30cm-2m | Too much inertia for one ant. Requires team effort or breakdown. Decision point. | See options below |
| **Megaliths** | >2m | Go around. Period. Becomes a permanent feature of your tunnel geometry. | N/A |

**Boulder resolution options (the player/AI decision):**

| Choice | Time | Material Recovery | When To Pick |
|--------|------|------------------|-------------|
| **Drill + fracture** | Slow | Full -- all material recovered | Boulder is in a valuable vein (sulfide pocket, metal grain) |
| **Thermal spalling** | Slower | Full -- peel layers off with thermal stress | Harder consolidated rock, when drill bits are worn |
| **Cooperative push** | Fast | None -- boulder pushed to dump zone intact | Boulder is worthless silicate, need to clear the path |
| **Go around** | Fastest | None | Boulder is huge, not valuable, path flexibility exists |
| **Incorporate into wall** | Medium | None -- becomes structure | Near junction or chamber, provides free reinforcement |

**Drill + fracture (real technique):** Multiple ants with drill heads bore holes in a grid pattern. Thermal cycling (heat one side, cold the other) propagates cracks along the drill holes. Boulder fractures into manageable cobble-sized pieces. Workers scoop the fragments. Time-consuming but recovers all material. Exactly how real quarrying works.

**Thermal spalling (real technique, ancient):** Thermal rake heats one face while the rest stays cold. Thermal stress fractures the surface layer. Material flakes off. Repeat. Like peeling an onion. Indigenous peoples used fire-setting for millennia. Proposed for actual asteroid mining by multiple research groups.

**Cooperative push (microgravity-specific):** Zero weight but full inertia. 6-8 workers pushing in coordination (taskmaster directs) can accelerate a boulder slowly. DANGER: once moving, it doesn't stop easily. Risk of crushing ants, damaging tunnel walls, or runaway mass. Taskmaster must choreograph approach, push, and braking. Real microgravity construction hazard.

**Design principles:**
- Boulders are generated as part of the voxel grid (new zone type or attribute: hardness/consolidation level).
- Regolith-dominated zones (most of C-type interior) rarely have boulders. Players learn the baseline is easy scooping.
- Boulder encounters are events -- the first one triggers a tutorial tooltip explaining options.
- Player can set standing policies ("always drill boulders in valuable zones, always go around in silicate") or handle case-by-case.
- At Director/CEO zoom level, boulders are auto-resolved by policy. Only flagged if the AI can't decide (e.g., boulder in a mixed-value zone on a critical tunnel path).
- Cooperative push is the most dramatic option -- risk of runaway mass, potential ant casualties. High risk/high reward gameplay moment.
- Boulder frequency varies by asteroid type: rubble piles (Bennu) = more loose material, fewer boulders. Monolithic (Eros) = more consolidated rock, more boulders, harder digging overall.

### Ant Size Classes & Quality Tiers (Future)

**Current state:** One size class (micro/hobby). 3 castes (worker $36, taskmaster $80, surface ant $1467). All COTS hobby hardware. This is the bootstrapper/ISRO tier.

**Future direction:** Multiple size/quality tiers that map to factions, budget, and tech era. Size isn't just cosmetic -- it determines what the ant can physically do.

#### Size Classes

| Class | Body Size | Unit Cost | Hardware Tier | Key Capability |
|-------|-----------|-----------|---------------|----------------|
| **Micro** | ~10cm (palm) | $36 | RP2040, SG90 servos, 3D-printed PLA | Current design. Cheap, fragile, replaceable, self-replicable earliest. |
| **Standard** | ~30cm (cat) | $200-500 | ARM Cortex-M7, metal gears, aluminum chassis, real bearings | Reliable workhorse. 5x lifespan of micro. Handles cobbles directly. |
| **Heavy** | ~60cm (dog) | $2K-5K | Jetson-class compute, brushless motors, machined aluminum, self-contained power | Moves boulders solo. Carries 10x payload. Each loss hurts. |
| **Industrial** | ~1.5m (person) | $50K-200K | Maxon actuators, full autonomy, manipulator arms, internal tool bay | Mars Rover class. Bores 2m tunnels in one pass. Carries bioreactor modules. |
| **Mega** | ~3m+ (vehicle) | $500K+ | Dedicated excavator platform. Mini tunnel boring machine. | Not really an "ant." Endgame habitat excavation at scale. |

#### Size vs. Swarm Philosophy (Neither Is Best)

**Micro swarm (1000+ units, $36K total):**
- Massive redundancy. Lose 50, production barely dips.
- Gets into cracks, voids, everywhere. Perfect for exploration.
- Self-replicable from asteroid iron earliest (simplest parts).
- Can't handle boulders individually. Need cooperative tactics or go around.
- Fragile. High turnover. But parts are cheap and mostly local-built.

**Heavy squad (20-50 units, $100-250K total):**
- Each unit moves 10x more material per trip.
- Handles boulders solo. Wider tunnels. Faster excavation rate per ant.
- Each loss is a real setback ($5K replacement + delivery delay).
- Harder to manufacture locally (precision parts need better fabrication).
- Better sensors per unit -- finds veins faster.

**Industrial team (5-10 units, $500K-2M total):**
- Does things small ants literally can't: move 100kg boulders, bore chamber-scale tunnels, install heavy equipment.
- Each unit is a major asset. Loss is catastrophic financially.
- Cannot self-replicate until very late game (Year 20+ fabrication tech).
- Requires bigger mothership, heavier launch mass.

**Mixed doctrine (the real answer for most factions):**
- Micro swarm for exploration, hauling, routine work.
- A few heavy units for boulder clearing, tunnel boring, heavy lifting.
- One or two industrial units for chamber excavation and equipment installation.
- The MIX is the interesting strategic decision. Budget allocation across tiers.

#### Faction-Size Mapping

| Faction | Default Doctrine | Why |
|---------|-----------------|-----|
| India (ISRO) | Micro swarm, huge numbers | Cost efficiency is their superpower. 2000 cheap ants beat 50 expensive ones. |
| US Commercial | Mixed -- micro workers + standard taskmasters | Balanced. Investors want results but not gold-plated hardware. |
| Japan (JAXA) | Standard across the board | Precision engineering. Every unit is reliable. Few failures. |
| China | Heavy units, smaller numbers | State-funded, no budget pressure. Each ant is a quality asset. |
| UAE | Heavy + Industrial | Money is not the constraint. Buy the best. Launch the heaviest. |
| Russia | Standard workers + heavy specialists | Nuclear-powered heavies for deep boring. Workers are expendable. |
| Luxembourg/EU | Micro swarm (bought, not built) | No launch capability, so minimize mass. Buy the cheapest ride. |
| Free Mars | Whatever they can divert | Covert ops. Grab what's available from "legitimate" colony supplies. |

#### Size Class Design Principles
- The current 3-caste system (worker/taskmaster/surface) exists at EVERY size class. A micro worker and a heavy worker do the same jobs, just at different scale/capability.
- Size classes unlock progressively: micro available at Year 0, standard at Year 3-5 (first resupply), heavy at Year 8-12, industrial at Year 15+, mega at Year 25+.
- Faction starting doctrine is a default, not a lock. India CAN buy heavy units later. UAE CAN switch to micro swarms if they want. The default just reflects institutional culture.
- Each size class should have its own catalog YAML files with real (or plausible) parts at that tier.
- The "bridge to reality" feature (export BOM, print STL, flash firmware) works for micro and standard tiers. Heavy and above are aspirational/educational -- real parts exist but the complete robot is a larger engineering project.
- Visual distinction in the GUI: micro ants are fast and numerous. Heavy ants are slow and imposing. Industrial units are dramatic. The size difference should be immediately visible and viscerally satisfying.

### Delivery Models (More Than One Way to Launch)

Real space missions have multiple launch options. The game should represent this. There is no single "right" way to get hardware to an asteroid -- the tradeoff is cost vs. mass vs. transit time vs. risk.

#### The Bootstrap Problem
Worker ants are useless without infrastructure. Before any mining can happen, the asteroid needs:
- A drill (bore the initial tunnel entrance)
- Anchoring system (screw anchors + gasket seal to the surface)
- Power (deployable solar panels)
- Comms relay (Earth link)
- Sealant (pressurize the first tunnel section)
- At least a few ants to begin work

This is the **minimum viable lander** (~80-120 kg). It must arrive as one package. After that, everything else can be delivered piecemeal.

#### Delivery Options

| Method | Payload | Cost | Transit Time | Risk | Who Uses This |
|--------|---------|------|-------------|------|---------------|
| **Dedicated Starship** | 100,000+ kg | $50-100M | 6-18 months | Low | UAE, China. Land everything at once. |
| **Dedicated Falcon Heavy** | 63,800 kg LEO | $150M | 6-18 months | Low | US commercial, large missions. |
| **ESPA rideshare** | ~180 kg secondary | $1-3M | Goes where the primary goes | Medium (no control over trajectory) | Bootstrapper seed ship. |
| **CubeSat rideshare** | 6U=12kg, 12U=24kg | $150-500K | 1-3 years (ion drive to NEA) | Higher (small margins, long transit) | Ant resupply batches, upgrade packs. |
| **Solar sail delivery** | 5-20 kg | $100-300K (ride to LEO, sail is free propulsion) | 2-5 years | Highest (unproven for cargo) | Extreme budget. The long game. |

#### Piecemeal CubeSat Delivery Model (The Bootstrapper Strategy)

The ultra-budget approach: send pieces one at a time via rideshare slots. Each arrival is a game event.

**Example manifest (total ~$5M over 3 years):**

| Delivery | Size | Contents | Cost | Arrives |
|----------|------|----------|------|---------|
| Seed ship | ESPA ~120 kg | Drill, power, comms, sealant, 10 micro ants | $2M | Month 0 |
| Ant batch 1 | 6U CubeSat | 30 workers + tool heads | $300K | Month 4 |
| Ant batch 2 | 6U CubeSat | 20 workers + 2 taskmasters | $300K | Month 8 |
| Surface ant | 12U CubeSat | 1 surface ant (vacuum-rated) + spare parts | $500K | Month 12 |
| Bioreactor | 12U CubeSat | Bacteria + nutrients + centrifuge drum | $500K | Month 14 |
| Upgrade pack 1 | 3U CubeSat | Metal gear servos, brushless motors (for all ants) | $150K | Month 18 |
| Ant batch 3 | 6U CubeSat | 50 workers + 5 taskmasters | $400K | Month 22 |
| Nuclear power | ESPA ~80 kg | Kilopower 1kW fission unit | $2M | Year 3 |

**Early game with piecemeal delivery feels completely different:**
- Month 0: 10 ants. Every one matters. One failure is 10% of your workforce.
- Month 4: Reinforcements! 30 fresh workers. Real relief.
- Month 14: Bioreactor arrives. Extraction rates triple. Revenue jumps.
- Year 3: Nuclear power. No more night-side shutdowns.

**Contrast: UAE lands a 2-ton mothership with 200 heavy ants on day one.** Same asteroid, completely different experience. Both viable.

#### Delivery Model Design Principles
- **The manifest IS the strategy.** What you put on each delivery, and when, is the core budget player's planning game.
- **Transit times are real.** 1-3 years for CubeSat deliveries. Once launched, you can't change the contents. Commit early, wait long.
- **Rideshare means you go where they go.** ESPA slots are secondary payloads -- you might not get an ideal trajectory. CubeSats need their own propulsion (ion drive or solar sail) for the final leg.
- **Every delivery is a game event.** Anticipation, arrival animation, unpacking. Like Christmas morning on an asteroid.
- **Loss is possible.** CubeSat failure rate is ~5-10%. A delivery that doesn't arrive is a real setback. Insurance is available but costs extra.
- **The seed ship is irreplaceable.** If your one ESPA rideshare fails, the game is over (or you wait 6-12 months for another rideshare window). This is the highest-stakes moment for budget players.
- **Dedicated launches can send EVERYTHING at once** but cost 50-100x more. That's the whole tradeoff.
- **Faction default delivery models:**
  - Bootstrapper/India: Seed ship ESPA + CubeSat resupply chain
  - US Commercial: Falcon Heavy dedicated + occasional rideshare resupply
  - UAE/China: Starship dedicated. Everything at once. Money is not the constraint.
  - Japan: Dedicated medium launcher (H3) + precision CubeSat resupply (Hayabusa heritage)
  - Russia: Proton/Angara dedicated + bulk resupply on schedule
  - Luxembourg/EU: No launch capability. Buys rideshare slots from others. Cheapest per-kg but least control over timing.
