# AstraAnt User Guide

Complete guide to installing, configuring, and using the AstraAnt asteroid mining simulator.

---

## Table of Contents

1. [Installation](#installation)
2. [Core Concepts](#core-concepts)
3. [Command Reference](#command-reference)
4. [3D GUI Guide](#3d-gui-guide)
5. [Web Dashboard](#web-dashboard)
6. [Extending the Catalog](#extending-the-catalog)
7. [Troubleshooting](#troubleshooting)

---

## Installation

### Requirements

- Python 3.10 or newer
- pip (comes with Python)
- Git (for cloning)

### Basic Install

```bash
git clone https://github.com/telgabrowny/AstraAnt.git
cd AstraAnt
pip install -e .
```

### Optional Extras

```bash
# Everything (recommended)
pip install -e ".[dev,gui,dashboard,sim,viz]"

# Individual extras:
pip install -e ".[dev]"         # pytest for running tests
pip install -e ".[gui]"         # Ursina 3D engine
pip install -e ".[dashboard]"   # Streamlit web dashboard
pip install -e ".[sim]"         # SciPy, NumPy, Mesa for simulation
pip install -e ".[viz]"         # Plotly, Dash for charts
```

### Verify It Works

```bash
astraant --version
astraant catalog summary
python -m pytest tests/ -q     # Should show 100 passed
```

If `astraant` isn't found after install, use `python -m astraant` instead.

---

## Core Concepts

### The Mission

AstraAnt models a swarm of small robots ("ants") that mine asteroids from the inside. They dig sealed, pressurized tunnels, extract metals and water, and ship products to lunar or Mars orbit via micro-pods. The simulator tracks every kilogram from mine face to cargo pod.

### Ant Castes

There are three types of ants, each with different hardware and roles:

| Caste | Cost | MCU | Role |
|-------|------|-----|------|
| **Worker** | ~$36 | RP2040 | 6 legs + 2 mandible arms. Does all digging, hauling, sorting, wall-plastering. Swaps modular tool heads. |
| **Taskmaster** | ~$80 | ESP32-S3 | Squad manager. Permanent sensors, coordinates groups of workers, relays commands from mothership. |
| **Surface Ant** | ~$1,467 | Maxon actuators | Vacuum-rated aluminum chassis. Operates outside the tunnels for external maintenance, cargo loading, solar panel cleaning. |

Workers make up ~90% of the swarm. Taskmasters are about 1 per 20 workers. Surface ants are few (2-5 typically).

### Extraction Tracks

Every analysis command accepts `--track` to choose how materials are extracted:

| Track | What It Does | Pros | Cons |
|-------|-------------|------|------|
| **mechanical** | Dig, crush, sort by density/magnetics. No biology. | Simplest. Lightest launch mass. No water needed. | Lower extraction purity. Gets ~50% less metal per kg processed. |
| **bioleaching** | Bacteria dissolve metals from crushed regolith in acid vats. | Higher purity. Better extraction rates. Self-sustaining biology. | +300 kg water launch mass. Bioreactor modules required. 3-month startup period. |
| **hybrid** | Mechanical mining speed + bioleaching purity. Best of both. | Highest throughput AND purity. | Most complex. Heaviest launch mass. All bioreactor costs plus mechanical systems. |

**Which to pick?** Bioleaching is the default for economics/scaling commands because it produces the best revenue. Mechanical is the default for build/hardware commands because it's the simplest to physically construct. The `compare` command shows all three side-by-side.

### Destinations

Where you ship extracted materials determines their value:

| Destination | Water $/kg | Metal $/kg | Why |
|-------------|-----------|-----------|-----|
| `lunar_orbit` | $50,000 | $20-70K | Avoiding launch cost from Earth. Water is rocket fuel. |
| `mars_orbit` | $500,000 | $200-300K | Much harder to reach. Everything is more valuable. |
| `earth_return` | $0.001 | $0.50-50K | Only platinum-group metals are worth the trip home. |

### Readiness Levels

The readiness system classifies every aspect of the mission:

| Level | Meaning |
|-------|---------|
| **PROVEN** | Can order/build today. Real parts, tested designs, known physics. |
| **NEEDS_PHYSICAL_TEST** | Design exists but hasn't been built and tested. Example: SG90 servo MTBF in 5 kPa. |
| **NEEDS_SIM_VALIDATION** | The simulator can answer this question with the right parameters. |
| **OPEN_RESEARCH** | No clear answer yet. Needs investigation or experimentation. |

### Break-Even Cycles

A "cycle" is 30 days of mining operations. Break-even is how many cycles until cumulative revenue exceeds total mission cost (hardware + launch + consumables). A break-even of 1 cycle means you're profitable within the first month of production.

### Key Numbers

- Bioreactor wet mass includes **300 kg of water** -- this dominates launch mass for bioleaching/hybrid tracks
- Water at lunar orbit is worth **$50,000/kg** (avoided launch cost)
- 5 kPa sealed tunnels extend COTS component life **~100x**
- Solar power scales with 1/r^2 -- Psyche at 2.9 AU gets only 12% of near-Earth power

---

## Command Reference

### Global Options

```
astraant --version    Show version
astraant --help       List all commands
astraant CMD --help   Show options for a specific command
```

---

### Catalog Commands

Browse the component database (parts, asteroids, species, tools).

#### `catalog summary`

Show how many entries are in each catalog category.

```bash
astraant catalog summary
```

#### `catalog parts`

List all electronic/mechanical parts with prices and staleness.

```bash
astraant catalog parts                  # All parts
astraant catalog parts -c electronics   # Filter by category
```

#### `catalog asteroids`

List target asteroids with spectral class, delta-v, and water availability.

```bash
astraant catalog asteroids              # All 7 asteroids
astraant catalog asteroids --max-dv 6   # Only those reachable with <6 km/s
```

#### `catalog species`

List bioleaching organisms and their target metals.

```bash
astraant catalog species
```

#### `catalog tools`

List modular tool heads with mass, cost, and electrical specs.

```bash
astraant catalog tools
```

#### `catalog stale`

Find parts whose prices haven't been checked recently.

```bash
astraant catalog stale              # Default: 90 days
astraant catalog stale --days 30    # Stricter threshold
```

---

### Ant Commands

Inspect the three ant caste configurations.

#### `ant list`

Summary table of all castes: mass, cost, idle/active power.

```bash
astraant ant list
```

#### `ant info`

Detailed breakdown for one caste.

```bash
astraant ant info worker
astraant ant info taskmaster
astraant ant info surface_ant
```

Shows mass budget, computed mass, estimated cost, power draw (idle/active/peak), and components (MCU, actuators, sensors).

---

### Analysis Commands

#### `analyze`

Run a complete feasibility analysis: mass budget, cost estimate, power budget, revenue projection, and break-even.

```bash
# Defaults: 100 workers, bennu, lunar orbit, mechanical track
astraant analyze

# Customize everything
astraant analyze -w 200 -t 10 -s 5 \
    --track bioleaching \
    --asteroid psyche \
    --destination mars_orbit \
    --vehicle starship
```

| Option | Default | Description |
|--------|---------|-------------|
| `-w, --workers` | 100 | Number of worker ants |
| `-t, --taskmasters` | 5 | Number of taskmaster ants |
| `-s, --surface-ants` | 3 | Number of surface ants |
| `--track` | mechanical | `mechanical`, `bioleaching`, or `hybrid` |
| `--asteroid` | bennu | Target asteroid ID |
| `--destination` | lunar_orbit | `lunar_orbit`, `mars_orbit`, or `earth_return` |
| `--vehicle` | starship_conservative | Launch vehicle ID |

**Output includes:** mass budget per caste, mothership modules, launch cost (prototype and production pricing), power budget per ant, revenue per cycle, and break-even cycle count.

#### `compare`

Run all three extraction tracks side-by-side with the same swarm and asteroid.

```bash
astraant compare
astraant compare -w 200 --asteroid eros --destination mars_orbit
```

Produces a table comparing total mass, launch cost, revenue per cycle, and break-even across mechanical/bioleaching/hybrid.

#### `economics`

Full mission economics over multiple years. Shows regolith processing, water recovery, metal extraction, revenue by material, cargo delivery timeline, and ROI.

```bash
astraant economics --track bioleaching --years 10 --reality-check
```

| Option | Default | Description |
|--------|---------|-------------|
| `--track` | bioleaching | Extraction track |
| `--years` | 5.0 | Mission lifetime in years |
| `--reality-check` | off | Add hidden costs analysis (insurance, ground ops, spares) |

The `--reality-check` flag is important -- it adds costs that optimistic projections skip.

#### `sensitivity`

Which parameters matter most? Sweeps worker count, launch cost, destination, and track to show which changes have the biggest impact on break-even.

```bash
astraant sensitivity
astraant sensitivity -w 200 --track hybrid --asteroid ryugu
```

#### `composition`

Simulate mining variability -- what happens when you hit different geological zones. Models 6 spatial zones per asteroid type and shows how batch-to-batch composition varies.

```bash
astraant composition --asteroid bennu --batches 200
```

#### `scaling`

Extrapolate performance from small swarms to large ones. Runs a short simulation at baseline size, then applies crowding and efficiency factors.

```bash
astraant scaling --track bioleaching --baseline 25 --days 10
```

#### `readiness`

Classify every mission component as PROVEN, NEEDS_PHYSICAL_TEST, NEEDS_SIM_VALIDATION, or OPEN_RESEARCH. Shows what you can build today vs. what needs testing first.

```bash
astraant readiness --track mechanical
```

The output includes estimated cost and time for each test needed.

---

### Mission Planning Commands

#### `plan`

Pick an objective, get the best asteroid and mission configuration.

```bash
astraant plan                    # List all 9 objectives
astraant plan cheapest_profit    # Get specific recommendation
astraant plan interstellar       # Go big
```

**Available objectives:**

| Objective | Description |
|-----------|-------------|
| `cheapest_profit` | Minimize cost while still profitable in 5 years |
| `max_water` | Extract the most water (dominates lunar orbit revenue) |
| `max_platinum` | Target PGM-rich asteroids for highest per-kg value |
| `rare_earths` | Focus on rare earth elements for electronics manufacturing |
| `fuel_depot` | Establish propellant production (water electrolysis) |
| `habitat_small` | Build a 0.15g walk-around ring station inside asteroid |
| `habitat_medium` | 100m radius station with trees and a small community |
| `interstellar` | 224m radius rotating cylinder, full 1g Earth gravity |
| `self_replicating` | Maximize local manufacturing, build ants from asteroid materials |

#### `orbit`

Asteroid orbital mechanics: current position, distance from Earth, and redirection analysis (how many motherships + years of thrust to move it).

```bash
astraant orbit --asteroid bennu --date 2030-01-01
astraant orbit --asteroid psyche --motherships 32 --power nuclear_40kw --years 10
```

#### `launch-plan`

Plan a single-launch manifest that fits everything in one Starship. Shows exactly what goes on the rocket.

```bash
astraant launch-plan -w 100 --local-ants 500
astraant launch-plan --no-phase2 --extra-solar-kw 30
```

#### `endgame`

Track habitat construction progress -- from a 5m sleeping ring to a 224m Interstellar-class cylinder.

```bash
astraant endgame
astraant endgame --target-radius 100 --excavated 50000
```

#### `phase2`

Plan Phase 2 facilities (CNC mill, 3D printers, welding station, etc.) inside the excavated chamber.

```bash
astraant phase2 --all-facilities
astraant phase2 -f cnc_mill -f printer_farm --chamber-m3 5000
```

#### `manufacturing`

What can you build from excess extracted materials? Plans in-situ manufacturing of ant components from asteroid iron, nickel, copper.

```bash
astraant manufacturing --asteroid bennu --track bioleaching --years 5
```

#### `price-report`

Full price health check: which parts have stale pricing, price trends, and current worker ant cost breakdown.

```bash
astraant price-report
astraant price-report --stale-days 30
```

---

### Build Commands

Export everything needed to build a physical ant.

#### `build bom`

Generate a Bill of Materials for a specific caste with real part IDs, quantities, and costs.

```bash
astraant build bom worker
astraant build bom worker --track bioleaching -o worker_bom.txt
astraant build bom taskmaster
astraant build bom surface_ant
```

#### `build wiring`

Generate a pin-to-pin wiring diagram.

```bash
astraant build wiring worker
astraant build wiring taskmaster --track hybrid -o wiring.txt
```

#### `build scad`

Generate OpenSCAD 3D-printable models for tool heads.

```bash
astraant build scad --all              # Generate all tools
astraant build scad drill_head         # Single tool
astraant build scad --all -o models/   # Custom output directory
```

#### `build models`

Compile OpenSCAD files to visual models (.scad -> .stl -> .obj). Requires OpenSCAD installed on your system.

```bash
astraant build models           # Build all
astraant build models --model drill_head
```

---

### Simulation Commands

#### `simulate`

Run a headless (no GUI) simulation and print results. Good for batch testing or CI.

```bash
astraant simulate --days 30 --track bioleaching
astraant simulate -w 200 -t 10 -s 5 --days 60 --speed 50000
```

| Option | Default | Description |
|--------|---------|-------------|
| `-w, --workers` | 50 | Number of workers |
| `-t, --taskmasters` | 3 | Number of taskmasters |
| `-s, --surface-ants` | 2 | Number of surface ants |
| `--track` | mechanical | Extraction track |
| `--days` | 30 | Simulated mission days |
| `--speed` | 10000 | Simulation speed multiplier |

**Output includes:** tunnel length/volume, material extracted, water recovered, sealed wall area, dump/drum/vat cycles, anomalies detected, ant failures, and bioreactor stats (for bioleaching/hybrid tracks).

#### `gui`

Launch the 3D interactive simulation window (requires `pip install -e ".[gui]"`).

```bash
astraant gui
astraant gui --track bioleaching -w 30 --asteroid ryugu
```

See [3D GUI Guide](#3d-gui-guide) below for controls and features.

#### `saves list`

List all saved game files with metadata.

```bash
astraant saves list
```

#### `dashboard`

Launch the Streamlit web dashboard at http://localhost:8501.

```bash
astraant dashboard
```

See [Web Dashboard](#web-dashboard) below for details.

---

## 3D GUI Guide

The GUI is a real-time 3D simulation powered by Ursina Engine.

### Launching

```bash
pip install -e ".[gui]"
astraant gui --track bioleaching -w 20
```

### What You See

- **Procedural asteroid** with correct shape (rubble pile, monolithic, or mixed)
- **Color-coded ants**: orange (worker), blue (taskmaster), green (surface ant)
- **Tunnel network** growing into the asteroid as ants dig
- **Status dashboard** overlay showing real-time metrics
- **Mothership** on the asteroid surface

### Hotkeys

| Key | Action |
|-----|--------|
| **Space** | Toggle asteroid cutaway (see inside the tunnels) |
| **C** | Toggle cutaway mode details |
| **Tab** | Cycle camera modes: orbit, taskmaster (first-person), mothership, follow ant |
| **M** | Display mission metrics |
| **S** | Save game |
| **Pause/Play** | Time controls |

### Ant States

During simulation, ants cycle through these states:

idle, moving, digging, loading, hauling, dumping, returning, sorting, plastering, tending, patrolling, surface_ops, failed

Workers are dynamically assigned roles (mining, sorting, plastering, tending bioreactor) based on current needs.

### Auto-Save

The game auto-saves every 5 minutes of real time. Manual save with **S**.

---

## Web Dashboard

A Streamlit-based interface that runs all analysis commands interactively.

### Launching

```bash
pip install -e ".[dashboard]"
astraant dashboard
```

Opens at http://localhost:8501 in your browser.

### Sidebar Controls

- Target asteroid (7 options)
- Destination (lunar orbit, Mars orbit, Earth return)
- Extraction track (mechanical, bioleaching, hybrid)
- Worker count (10-500 slider)
- Mission lifetime (1-20 years)
- Power source (solar, nuclear 10kW, nuclear 40kW)
- Fanciful Findings mode (enables rare anomaly discoveries)

### Tabs

The dashboard has tabs for every major analysis: mission planning, feasibility, economics, catalog browsing, composition, manufacturing, readiness, price health, orbital mechanics, Phase 2 facilities, launch manifest, and endgame habitat.

All parameters update live as you change the sidebar.

---

## Extending the Catalog

AstraAnt's data is stored in YAML files. Adding new entries is just dropping a new file in the right directory.

### Adding a New Part

Create a file in `catalog/parts/`:

```yaml
# catalog/parts/my_sensor.yaml
id: my_sensor
name: "My Custom Sensor"
category: electronics
specs:
  mass_g: 3.5
  voltage_range: "3.0-5.5V"
sourcing:
  - supplier: digikey
    part_number: "ABC-123"
    url: "https://www.digikey.com/..."
    price_usd: 4.50
    date_checked: "2026-03-15"
    in_stock: true
price_history:
  - date: "2026-03-15"
    price_usd: 4.50
    source: digikey
```

### Adding a New Asteroid

Create a file in `catalog/asteroids/`:

```yaml
# catalog/asteroids/my_asteroid.yaml
id: my_asteroid
name: "My Asteroid"
physical:
  spectral_class: S
  diameter_m: 500
  mass_kg: 1.0e11
composition:
  confidence: moderate
  minerals:
    iron_ppm: 180000
    nickel_ppm: 12000
mining_relevance:
  water_availability: true
  accessibility:
    delta_v_from_leo_km_per_s: 5.2
```

See `catalog/SCHEMA.md` for the complete field reference.

### Adding a New Species

Drop a YAML file in `catalog/species/` with growth kinetics, extraction rates, and environmental tolerance.

### Updating Prices

Edit the part's YAML file:
1. Update the `price_usd` and `date_checked` in sourcing
2. Add an entry to `price_history`
3. Run `astraant price-report` to verify

---

## Troubleshooting

### "astraant: command not found"

Use `python -m astraant` instead, or verify the install with `pip show astraant`.

### GUI won't launch

```
Error: GUI dependencies not installed. Run: pip install astraant[gui]
```

Install the GUI extra: `pip install -e ".[gui]"`. Ursina requires Panda3D, which needs a working OpenGL driver.

### OpenSCAD models won't compile

`build models` requires OpenSCAD installed and on your PATH. Download from https://openscad.org/. The `build scad` command (generates .scad files) works without it.

### Dashboard won't start

Make sure Streamlit is installed: `pip install -e ".[dashboard]"`. If port 8501 is in use, Streamlit will try the next available port.

### Tests failing after changes

```bash
python -m pytest tests/ -x -q    # Stop on first failure, quiet output
```

The `-x` flag stops at the first failure so you can focus on one issue at a time.

### Encoding errors on Windows

AstraAnt uses ASCII-only output to avoid Windows terminal encoding issues. If you see encoding errors, check that you haven't introduced non-ASCII characters in YAML files or Python strings.
