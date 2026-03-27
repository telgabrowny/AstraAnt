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
- **Ant caste hierarchy**: Worker (cheap, ~$36, RP2040), Taskmaster (smart, ~$70, ESP32-S3), Courier (surface ops, ~$1400, vacuum-rated)
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
- SciPy for bioreactor ODE simulation (planned)
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
    readiness.py      # Readiness assessment framework (planned)
    gui/              # Ursina 3D visualization (planned)
  catalog/            # Component database (YAML files)
    parts/            # 15 real electronic components
    species/          # 5 bioleaching organisms
    asteroids/        # 7 target asteroids
    reagents/         # 5 chemicals
    sealing/          # Tunnel sealing materials
  configs/            # Mission configurations
    ants/             # worker.yaml, taskmaster.yaml, courier.yaml
    mothership/       # drill, power, comms, sealing, cargo, bioreactor
  tests/              # pytest test suites
  firmware/           # MicroPython for real hardware (planned)
  output/             # Generated reports, BOMs (gitignored)
```

## CLI Commands
```
astraant catalog summary|parts|asteroids|species|stale
astraant ant list|info <caste>
astraant analyze [--workers N --track a|b|c --asteroid ID --destination lunar_orbit|mars_orbit]
astraant compare [same options]
astraant build bom <caste> [--track a|b|c]
astraant gui [planned]
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
- 300 kg water dominates Track B/C launch mass (bioreactor wet mass = 410 kg, not 110 kg dry)
- 2m regolith = ~70-80% GCR reduction (radiation shielding)
- 5 kPa tunnel pressure stops lubricant outgassing, extends COTS MTBF ~100x
- Solar power scales with 1/r^2 — Psyche at 2.9 AU gets only 12% of 1 AU power
- CP1 polyimide sail: ~7 g/m^2 film, NOT 50g for 25 m^2 (real mass ~175g film + booms)
- NEA surface gravity is negligible for fluid dynamics (Bennu: 6 μm/s^2)
