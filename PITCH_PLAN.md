# AstraAnt Sous Vide: NASA/SpaceX Pitch Package Plan

## Status: ACTIVE (started 2026-03-31)
## Target: Full seed mission to NEA, 2030 launch window
## Deliverables: Pitch deck (PDF) + Live demo (interactive) + GitHub repo

---

## MASTER TASK LIST

Each task has: [STATUS] ID, dependencies, estimated effort, and acceptance criteria.
Status: [ ] TODO, [~] IN PROGRESS, [x] DONE, [B] BLOCKED

---

### PHASE 1: FOUNDATION (Sessions 1-3)

#### 1.1 Asteroid Selection + Trajectory
- [ ] 1.1.1 Survey all 7 catalog asteroids for 2030 launch windows
  - Use JPL Horizons API (via astroquery or manual) to get ephemeris
  - Calculate delta-V from Earth escape to each NEA for 2029-2031 windows
  - Select the target with lowest delta-V + confirmed C-type + water content
  - Candidates: Bennu (well-characterized), Ryugu (sample returned), 2008 EV5 (low dV)
  - Acceptance: target selected with specific launch date, arrival date, delta-V budget
  - Depends on: nothing
  - Effort: 1 session

- [ ] 1.1.2 Full trajectory design
  - Earth departure: rideshare to GTO, then ion spiral
  - Transfer orbit: low-thrust trajectory optimization (use pykep or poliastro)
  - Asteroid approach: terminal guidance, relative nav
  - Calculate propellant budget against BIT-3 specs (5 kg iodine, Isp 2200s)
  - Acceptance: trajectory with dates, delta-V splits, propellant margin
  - Depends on: 1.1.1
  - Effort: 1 session

- [ ] 1.1.3 Launch vehicle selection + rideshare booking path
  - SpaceX Transporter (SSO) vs Falcon 9 GTO rideshare vs RocketLab
  - Actual pricing quotes (published rates)
  - ESPA vs CubeSat deployer vs custom separation system
  - Acceptance: specific launch vehicle, cost, adapter, manifest constraints
  - Depends on: 1.1.1
  - Effort: 0.5 session

#### 1.2 Vendor Parts Acquisition
- [B] 1.2.1 Download STEP files from GrabCAD (USER ACTION NEEDED)
  - Parts needed (from scad/vendor_parts/README.md):
    1. SG90 servo (search: "SG90 servo" on GrabCAD, pick highest-rated STEP)
    2. ESP32-S3 DevKitC (search: "ESP32 DevKit", or get from Espressif GitHub)
    3. RP2040 Pico (official STEP from raspberrypi.com)
    4. N20 gearmotor (search: "N20 motor" on GrabCAD)
    5. Peristaltic pump head (search: "peristaltic pump" on GrabCAD)
    6. BIT-3 or similar ion thruster (search: "cubesat thruster" or "ion engine")
    7. Solar panel hinge mechanism (search: "cubesat solar panel deployment")
    8. UHF patch antenna (search: "UHF patch antenna" on GrabCAD)
  - Download as STEP, convert to STL via FreeCAD: `freecadcmd -c "import Part; s=Part.Shape(); s.read('file.step'); s.exportStl('file.stl')"`
  - Place in scad/vendor_parts/ as: sg90.stl, esp32_s3.stl, rp2040.stl, etc.
  - Acceptance: all 8 STL files in vendor_parts/, each imports in OpenSCAD
  - Depends on: GrabCAD account (user has or creates one)
  - Effort: 30 min user action

- [ ] 1.2.2 Verify and clean vendor meshes
  - Check each STL: correct scale (mm vs m), manifold, reasonable poly count
  - Fix any issues with Blender mesh cleanup
  - Create a test OpenSCAD file that imports all 8 and renders a lineup
  - Acceptance: all meshes load cleanly in both OpenSCAD and Blender
  - Depends on: 1.2.1
  - Effort: 0.5 session

#### 1.3 Blender Render Pipeline Setup
- [ ] 1.3.1 Install Blender + set up project
  - Install Blender 4.x (free, blender.org)
  - Create AstraAnt Blender project: scad/renders/astraant.blend
  - Set up: HDRI space environment, camera rigs, material library
  - Blueprint aesthetic: clean, precise, technical, "show your boss" quality
  - Acceptance: empty scene renders a starfield at 4K resolution
  - Depends on: nothing
  - Effort: 0.5 session

- [ ] 1.3.2 Import and material-assign all models
  - Import each vendor STL + custom SCAD STL into Blender
  - Assign PBR materials: aluminum (body), blue glass (solar panels), copper (nozzles),
    gold (Kapton), green (PCB), iron (WAAM parts), rubber (seals)
  - Set up proper scale (everything in meters)
  - Acceptance: each component is recognizable and correctly colored
  - Depends on: 1.2.2, 1.3.1
  - Effort: 1-2 sessions

- [ ] 1.3.3 Create render scenes
  - Scene 1: Seed mothership (hero shot, 3/4 angle, technical lighting)
  - Scene 2: Capture sequence (mothership wrapping rock, membrane deploying)
  - Scene 3: Printer bot close-up (recognizable SG90s, ESP32, WAAM head)
  - Scene 4: Nautilus station cutaway (spiral chambers, siphuncle, bots on surface)
  - Scene 5: Tug fleet sortie (tug approaching rock, station in background)
  - Scene 6: 50-year station (massive spiral, habitat ring, concentrator array)
  - Each: 4K resolution, transparent PNG + JPEG, with and without labels
  - Acceptance: each render is "show the board of directors" quality
  - Depends on: 1.3.2
  - Effort: 2-3 sessions

---

### PHASE 2: GNC + FIRMWARE (Sessions 4-7)

#### 2.1 GNC Firmware
- [ ] 2.1.1 Attitude Determination and Control System (ADCS)
  - Sun sensor model: 4x thermocouple + shadow mask, ~5 deg accuracy
  - Star tracker model: nano star tracker, ~0.01 deg accuracy
  - Magnetometer: for LEO phase only (Earth field)
  - Attitude estimator: complementary filter (sun + star tracker fusion)
  - Reaction control: 4x cold gas thrusters (N2), bang-bang control
  - MicroPython implementation for ESP32-S3
  - MuJoCo sim verification: does the ADCS stabilize the spacecraft?
  - Acceptance: spacecraft achieves <1 deg pointing accuracy in sim
  - Depends on: nothing
  - Effort: 2 sessions

- [ ] 2.1.2 Navigation + Trajectory Following
  - Orbital mechanics: Kepler propagation + ion thrust
  - Trajectory following: compare actual position (from ground tracking) to planned
  - Mid-course corrections: adjust thrust vector/duration
  - Terminal approach: relative navigation using on-board camera + target brightness
  - MicroPython implementation
  - Acceptance: sim shows spacecraft following planned trajectory within tolerance
  - Depends on: 2.1.1, 1.1.2
  - Effort: 2 sessions

- [ ] 2.1.3 Autonomous Capture Sequencer
  - State machine: approach -> station-keep -> arm deploy -> grip -> membrane deploy -> seal
  - Each state has entry/exit conditions, timeout, abort criteria
  - Runs on ESP32, commands arm servos + membrane release + pump
  - MuJoCo verification using capture_test.py scene
  - Acceptance: full capture sequence runs autonomously in sim without ground commands
  - Depends on: 2.1.2
  - Effort: 1 session

- [ ] 2.1.4 Bioleaching Operations Controller
  - State machine: heat -> inoculate -> monitor -> electroform -> drain -> feed
  - PID temperature control (thermocouple -> heater)
  - Electrodeposition current control (voltage stepping for Cu/Ni/Co/Fe)
  - Pump cycling (circulation schedule)
  - Wire factory sequencing (cut, coil, airlock)
  - MicroPython implementation
  - Acceptance: full bioleaching cycle runs autonomously in sim
  - Depends on: nothing
  - Effort: 1 session

#### 2.2 Firmware Package (flash-ready)
- [ ] 2.2.1 Consolidate all MicroPython firmware
  - Main flight computer (ESP32-S3): ADCS + nav + capture + bioleach + comms
  - Worker gait controller (RP2040): existing firmware/worker/
  - Printer bot controller (RP2040): gait + WAAM head + wire feed
  - Each as a complete, flashable package with config files
  - Include boot.py, main.py, lib/ structure for each
  - Acceptance: `mpremote connect /dev/ttyUSB0 cp -r firmware/flight/ :` deploys cleanly
  - Depends on: 2.1.1 through 2.1.4
  - Effort: 1 session

---

### PHASE 3: RADIO + GROUND STATION (Sessions 8-11)

#### 3.1 Radio Link Model
- [ ] 3.1.1 Link budget calculation
  - UHF uplink: 437 MHz, 2W TX power, patch antenna gain
  - X-band downlink (optional): 8.4 GHz, higher bandwidth
  - Path loss at NEA distance (0.01-2 AU): free-space path loss formula
  - Noise: cosmic background + receiver noise figure
  - Data rate achievable: Shannon capacity
  - Use GNU Radio or MATLAB link budget tools (or Python implementation)
  - Acceptance: link budget closes at target asteroid distance with margin
  - Depends on: 1.1.1 (asteroid distance)
  - Effort: 1 session

- [ ] 3.1.2 GNU Radio simulation of the radio link
  - Install GNU Radio (free, gnuradio.org)
  - Model: modulator -> channel (path loss + noise + delay) -> demodulator
  - Modulation: GMSK or BPSK (common CubeSat choice)
  - Forward error correction: convolutional code or LDPC
  - Simulate: transmit telemetry packet, add noise + delay, decode
  - Verify: bit error rate at expected SNR
  - Acceptance: radio sim decodes telemetry at NEA distance SNR
  - Depends on: 3.1.1
  - Effort: 1 session

- [ ] 3.1.3 Comm delay model
  - Light-time delay: distance_AU * 499 seconds
  - Round-trip: 2x one-way
  - Slider: 1x real-time, 10x, 100x, instant
  - Integrate with ground station UI
  - Acceptance: commands sent from console arrive after correct delay
  - Depends on: nothing
  - Effort: 0.5 session

#### 3.2 Ground Station Console
- [ ] 3.2.1 Architecture design
  - Backend: Python (FastAPI or Flask) serving real-time data via WebSocket
  - Frontend: React or Vue dashboard (professional, dark theme, blueprint aesthetic)
  - Data source: lifecycle_sim.py or live telemetry (switchable)
  - Comm delay: applied to all command/telemetry paths
  - Acceptance: architecture diagram, tech stack selected
  - Depends on: nothing
  - Effort: 0.5 session

- [ ] 3.2.2 Telemetry display panel
  - Real-time gauges: temperature, pressure, battery voltage, current
  - Attitude display: 3D spacecraft orientation (Three.js or similar)
  - Orbit display: spacecraft position relative to Earth + target asteroid
  - Status indicators: green/yellow/red for each subsystem
  - Timeline: mission phase, elapsed time, ETA to next event
  - Acceptance: all telemetry fields update in real-time from sim backend
  - Depends on: 3.2.1
  - Effort: 2 sessions

- [ ] 3.2.3 Command panel
  - Command categories: ADCS, propulsion, capture, bioleach, WAAM, maintenance
  - Each command: button + confirmation dialog + delay indicator
  - Command queue: shows pending commands in transit (light-delay)
  - Command history: log of all sent/acknowledged commands
  - Emergency: ABORT button (priority queue, bypasses normal sequencing)
  - Acceptance: can send commands that affect sim state after correct delay
  - Depends on: 3.2.2, 3.1.3
  - Effort: 1 session

- [ ] 3.2.4 Science/production dashboard
  - Bioleaching progress: iron concentration, pH, temperature trend
  - Extraction totals: Fe, Cu, Ni, Co, PGM (real-time accumulation)
  - Wire factory: wire inventory, bobbin count, bot fleet size
  - Shell growth: wall thickness, safety factor, chamber progression
  - Revenue: if customers enabled, show sales and cash flow
  - Acceptance: all production metrics update from sousvide_sim backend
  - Depends on: 3.2.2
  - Effort: 1 session

- [ ] 3.2.5 3D viewport (Three.js)
  - Render the spacecraft, asteroid, membrane, bots in real-time 3D
  - Camera modes: orbit, follow spacecraft, follow bot, station overview
  - Show: solar wings deployed, arms moving, bots walking, shell growing
  - Import Blender models via glTF export
  - Acceptance: interactive 3D view of current mission state
  - Depends on: 1.3.2 (Blender models for glTF export)
  - Effort: 2-3 sessions

---

### PHASE 4: SIMULATION INTEGRATION (Sessions 12-14)

#### 4.1 Unified Simulation Backend
- [ ] 4.1.1 Integrate all Python sims into single state machine
  - Mission phases: launch -> transit -> approach -> capture -> bioleach ->
    electroform -> WAAM -> growth -> tug_ops -> expansion
  - Each phase runs the appropriate sim module
  - State persists between phases (save/load)
  - Time acceleration: 1x, 10x, 100x, 1000x, jump-to-event
  - Acceptance: can run from launch to Year 50 with phase transitions
  - Depends on: all Phase 2 firmware
  - Effort: 2 sessions

- [ ] 4.1.2 MuJoCo physics spot-checks at phase transitions
  - At each major transition, run the relevant MuJoCo test
  - If MuJoCo test fails, flag the transition as "needs physical verification"
  - Log all MuJoCo results alongside Python sim results
  - Acceptance: lifecycle_sim.py enhanced with MuJoCo gates
  - Depends on: 4.1.1
  - Effort: 1 session

- [ ] 4.1.3 Hardware-in-the-loop interface
  - Define serial protocol between ground station and flight computer
  - If real ESP32 is connected via USB: route commands/telemetry through serial
  - If no hardware: route through sim backend (software-in-the-loop)
  - Same ground station UI works for both modes
  - Acceptance: ground station can talk to either sim or real hardware
  - Depends on: 3.2.3, 2.2.1
  - Effort: 1 session

---

### PHASE 5: PITCH DECK (Sessions 15-16)

#### 5.1 Pitch Document
- [ ] 5.1.1 Narrative structure
  - Page 1: The hook ("41 kg. $654K. Self-replicating asteroid mining.")
  - Page 2-3: The problem (cost of launching material to space)
  - Page 4-5: The solution (biological mining + WAAM self-replication)
  - Page 6-8: How it works (capture -> bioleach -> electroform -> WAAM -> grow)
  - Page 9-10: The economics (50-year revenue model, break-even at Year 2)
  - Page 11: The target (specific asteroid, 2030 launch, trajectory)
  - Page 12-13: The technology (each subsystem, TRL assessment)
  - Page 14: The verification (MuJoCo tests, lifecycle sim results)
  - Page 15: The roadmap (Phase 0-5, costs, timeline)
  - Page 16: The ask (what we need from NASA/SpaceX)
  - Each page: hero render + key numbers + concise text
  - Acceptance: 16-page PDF, board-of-directors quality
  - Depends on: 1.3.3 (renders)
  - Effort: 1 session

- [ ] 5.1.2 Technical appendix
  - Full BOM with supplier links and quotes
  - Trajectory design details
  - Link budget
  - Structural analysis (hoop stress, safety factors)
  - Readiness gap assessment (11 items needing physical test)
  - Test results summary (211 Python tests + MuJoCo physics)
  - Acceptance: appendix answers any technical question a reviewer might ask
  - Depends on: all previous phases
  - Effort: 1 session

#### 5.2 Live Demo Package
- [ ] 5.2.1 Demo script (10-minute walkthrough)
  - Open ground station -> show telemetry (sim running)
  - Send a command -> watch it arrive after light delay
  - Show bioleaching progress in real-time (accelerated)
  - Switch to 3D view -> show bots walking on shell
  - Show MuJoCo test -> watch printer bot walk
  - Show Blender render -> hero shot of the station
  - Show the BOM -> "this is what $654K buys you"
  - Acceptance: runs smoothly on a laptop in 10 minutes
  - Depends on: all previous phases
  - Effort: 1 session

---

## GrabCAD PARTS NEEDED (User Action)

Search these on grabcad.com and download the STEP files:

1. **"SG90 servo tower pro"** -- pick the one with mounting ears and gear horn visible
2. **"ESP32 S3 devkit"** -- or search "ESP32 development board"
3. **"Raspberry Pi Pico"** -- official STEP available at raspberrypi.com/documentation/microcontrollers/pico-series.html
4. **"N20 micro gearmotor"** -- the small DC motor with gearbox
5. **"peristaltic pump head"** -- Watson-Marlow style roller pump
6. **"cubesat ion thruster"** or **"BIT-3 thruster"** -- any small electric propulsion
7. **"cubesat deployable solar panel"** -- the hinge mechanism
8. **"UHF patch antenna cubesat"** -- small patch antenna

Save each as .step file in: `C:\Users\Taurik\Dropbox\robotStuff\AstraAnt\scad\vendor_parts\`

I will handle the STEP-to-STL conversion and Blender import.

---

## DEPENDENCY GRAPH

```
Phase 1 (Foundation)
  1.1 Asteroid + trajectory ──────────────┐
  1.2 Vendor parts (USER ACTION) ─────┐   │
  1.3 Blender pipeline ───────────────┼───┤
                                      │   │
Phase 2 (GNC + Firmware)              │   │
  2.1 ADCS + Nav + Capture ───────────┼───┤
  2.2 Firmware consolidation ─────────┤   │
                                      │   │
Phase 3 (Radio + Ground Station)      │   │
  3.1 Radio link model ──────────────┤   │
  3.2 Ground station UI ─────────────┤   │
                                      │   │
Phase 4 (Integration)                 │   │
  4.1 Unified sim backend ───────────┘   │
                                          │
Phase 5 (Pitch)                           │
  5.1 Deck + appendix ───────────────────┘
  5.2 Live demo
```

---

## TOOLS TO INSTALL

- [x] MuJoCo (already installed, 3.6.0)
- [x] Ursina (already installed, 8.3.0)
- [x] OpenSCAD (already installed)
- [ ] Blender 4.x (blender.org, free)
- [ ] GNU Radio (gnuradio.org, free) -- for radio link simulation
- [ ] FreeCAD (freecad.org, free) -- for STEP-to-STL conversion
- [ ] Node.js (nodejs.org) -- for ground station frontend (React/Vue)
- [ ] pykep or poliastro (pip install) -- for trajectory optimization

---

## SESSION LOG

| Session | Date | Tasks Completed | Notes |
|---------|------|-----------------|-------|
| 0 | 2026-03-30 | All sous vide sims, WAAM, relay, lifecycle | Foundation work |
| 1 | 2026-03-31 | MuJoCo models, lifecycle verification | 11/11 phases pass |
| 2 | TBD | | |

---

## ACCEPTANCE CRITERIA (overall)

The package is complete when:
1. A non-technical board member can watch the 10-minute demo and understand the concept
2. A NASA engineer can read the technical appendix and find no hand-waving
3. The ground station console can control a simulated mission from launch to Year 50
4. Every render shows recognizable, real parts (not block geometry)
5. The firmware can be flashed to real hardware without modification
6. The trajectory hits a real asteroid at a real launch date
7. The radio link budget closes with positive margin
8. The pitch deck answers "why should we fund this?" convincingly

---

*This plan is a living document. Update after each session.*
