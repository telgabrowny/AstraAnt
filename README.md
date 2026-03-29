# AstraAnt -- Ant Swarm Asteroid Mining Simulator

A modular, physics-grounded simulator for designing and testing autonomous mechanical ant swarm missions to asteroids. Part serious feasibility study, part strategy game.

**If someone handed you unlimited funding and a rocket launch tomorrow, this project's outputs specify exactly what to buy, build, test, and launch.**

## What Is This?

AstraAnt simulates a colony of small robots (the "ants") that mine asteroids from the inside. The ants dig sealed, pressurized tunnels into the asteroid, extract metals and water through bioleaching, manufacture copies of themselves from extracted materials, and ship products to lunar or Mars orbit via solar-sail micro-pods.

The simulator tracks every kilogram of material from mine face to cargo pod, models realistic component failure and recycling, and produces actionable engineering outputs: bills of materials with real supplier links, wiring diagrams, 3D-printable chassis files, and MicroPython firmware you can flash onto real hardware.

## Quick Start

```bash
pip install -e ".[dev,gui]"

# See what's available
astraant --help

# Run a feasibility analysis
astraant analyze --track bioleachingioleaching --asteroid bennu --destination lunar_orbit

# Compare all three extraction tracks
astraant compare

# Plan a mission (pick an objective, get the best asteroid)
astraant plan cheapest_profit

# Full 5-year economics with reality check
astraant economics --track bioleaching --reality-check

# Run a 30-day headless simulation
astraant simulate --days 30 --track bioleaching

# Launch the 3D GUI
astraant gui --track bioleaching --workers 20

# Open the web dashboard
astraant dashboard
```

## Architecture

- **3 ant castes**: Worker (6 legs + 2 mandible arms, $37, RP2040), Taskmaster ($75, ESP32-S3), Surface Ant ($1242, vacuum-rated Maxon actuators)
- **7 modular tool heads**: drill, scoop, paste nozzle, thermal rake, sampling probe, cargo gripper, panel brush. Magnetic clip mount, all 3D-printable.
- **Underground tunnel operations**: sealed at 1-10 kPa, extends COTS component life 100x
- **3 extraction tracks**: mechanical, bioleaching, hybrid
- **Self-sustaining biology**: bacteria self-replicate, sugar grown on-site from algae photobioreactor
- **In-situ manufacturing**: build new ants from asteroid iron using a sintering furnace
- **Voxel asteroid interior**: Minecraft-style geology with mineral veins
- **Material ledger**: every kilogram tracked from mine face to cargo pod
- **Game economy**: starting budget, revenue with 2.5-year transit delay, resupply funded from profits

## CLI Commands (22)

| Command | Description |
|---------|-------------|
| `catalog summary\|parts\|asteroids\|species\|tools\|stale` | Browse the component database |
| `ant list\|info <caste>` | Inspect ant configurations |
| `analyze` | Feasibility analysis (mass, cost, break-even) |
| `compare` | Three-track head-to-head comparison |
| `economics` | Full 5-year site economics + reality check |
| `readiness` | What's proven vs needs testing vs open research |
| `sensitivity` | Which parameters matter most |
| `composition` | Mining variability by geological zone |
| `scaling` | Extrapolate from 10 to 100K ants |
| `simulate` | Headless simulation with results |
| `orbit` | Asteroid position + redirection analysis |
| `plan` | Mission planner (9 objectives, ranks asteroids) |
| `phase2` | Chamber facility planning (8 facility types) |
| `launch-plan` | Single-launch manifest (fits in one Starship) |
| `manufacturing` | What to build from excess materials |
| `endgame` | Rotating habitat progress tracker |
| `price-report` | Component price staleness detection |
| `build bom\|wiring\|scad\|models` | Physical build outputs |
| `gui` | 3D interactive simulation |
| `dashboard` | Streamlit web dashboard |
| `saves list` | Manage save game files |

## Physical Build Outputs

At any time, export everything needed to build a real worker ant:

```bash
# Parts list with DigiKey/Mouser links
astraant build bom worker --track mechanical

# Pin-to-pin wiring diagram
astraant build wiring worker

# 3D-printable models (chassis, tools, pod scaffold, mothership)
astraant build scad --all
astraant build models  # Compile to .obj via OpenSCAD
```

The firmware is real MicroPython that runs on RP2040:
- `firmware/worker/main.py` -- command-driven state machine
- `firmware/worker/gait.py` -- tripod walking gait
- `firmware/worker/drivers/` -- VL53L0x lidar + nRF24L01 radio

## Key Numbers

| Metric | Value |
|--------|-------|
| Worker ant cost (prototype) | $37 |
| Worker ant cost (10K volume) | $14 |
| Surface ant cost | $1,242 |
| Single Starship launch (everything) | 16,187 kg payload, 35% margin |
| Total mission cost | $81-163M (depending on Starship pricing) |
| 5-year revenue (Bennu, lunar orbit) | $709M |
| Time to profitability | ~Day 100 |
| Readiness score | 52/100 (budget to flight-ready: ~$85K, 20 weeks) |

## The Endgame

The colony excavates a pressurized chamber inside the asteroid, installs industrial equipment (CNC mill, 3D printers, welding station), and begins building a rotating habitat -- section by section, growing from a 5m sleeping ring (0.02g) toward a 224m radius Interstellar-class cylinder (1.0g, 53 football fields of floor area).

## Tech Stack

- Python 3.10+, MicroPython for firmware
- PyYAML, Click, Rich for CLI
- Ursina Engine for 3D GUI
- Streamlit for web dashboard
- SciPy for bioreactor ODE simulation
- OpenSCAD for parametric 3D models
- pytest (100 tests)

## Status

82 commits. 100 tests. 15,000+ lines. Active development.

## License

Not yet determined.
