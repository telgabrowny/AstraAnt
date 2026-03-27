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
- **Three extraction tracks**: A (mechanical), B (bioleaching), C (hybrid mechanical+bio)
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
astraant analyze [--workers N --track a|b|c --asteroid ID --destination lunar_orbit|mars_orbit]
astraant compare
astraant readiness [--track a|b|c]
astraant sensitivity [--workers N --track a|b|c]
astraant simulate [--workers N --days 30 --track a|b|c]
astraant build bom <caste> [--track a|b|c]
astraant build wiring <caste> [--track a|b|c]
astraant build scad [tool_id] [--all]
astraant gui [--workers N --asteroid ID --track a|b|c]
astraant economics [--asteroid ID --years 5 --reality-check]
astraant composition [--asteroid ID --batches 200]
astraant scaling [--track a|b|c --baseline N]
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
8. Track B/C bioreactor visualization

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
- 300 kg water dominates Track B/C launch mass (bioreactor wet mass = 410 kg, not 110 kg dry)
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
