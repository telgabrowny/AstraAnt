# AstraAnt — Ant Swarm Asteroid Mining Simulator

## Project Overview

Build a modular, layered simulator for designing and testing autonomous "mechanical ant" swarm missions to asteroids. The simulator must use real off-the-shelf hardware specs, run real control code (MicroPython targeting actual microcontrollers), and model realistic orbital mechanics, underground tunnel operations, and mission economics.

The goal: given a catalog of real purchasable components, design ant robots and mission architectures, then simulate whether they can profitably mine an asteroid and deliver materials to cislunar or Mars orbit — scaling from a single ant proof-of-concept to a full swarm colony operation.

### Primary Operating Model: Underground Tunnel Operations

The mission architecture centers on **underground operations**. The mothership lands on the asteroid, drills/excavates an initial cavity, deploys surface solar arrays, and routes power underground. All ant operations occur within sealed tunnel networks inside the asteroid.

**Why underground?** This solves five problems simultaneously:
1. **Radiation shielding** — 2m of regolith provides ~70-80% GCR reduction, complete SPE protection. COTS electronics survive without rad-hardening.
2. **Thermal stability** — Subsurface temperature is nearly constant vs. extreme surface cycling (-150C to +200C).
3. **Anchoring** — Work inside a cavity eliminates the microgravity locomotion problem on the surface.
4. **Dust control** — Excavated material stays contained rather than escaping into space.
5. **Cavity stability** — In microgravity, there is essentially no cave-in risk. Tunnels are self-stable.

### Sealed Tunnel Environment

Tunnels are lightly sealed and pressurized to **1-10 kPa** (~1-10% of Earth atmospheric pressure) using fill gas (nitrogen, CO2, or argon). This is not breathable but is enough to:
- **Prevent lubricant outgassing** — COTS servo grease stays in place, extending actuator life ~100x
- **Enable convective heat transfer** — Thermal management simplified
- **Allow dust management** — Fans and filters work in a pressurized environment
- **Extend COTS electronics life** — Near-normal operating conditions

Sealing methods are configurable in the component catalog:
- **Regolith sintering** — Microwave or solar concentrator fuses tunnel walls into ceramic shell (no Earth consumables)
- **Polymer spray** — Epoxy/silicone coating brought from Earth (known mass, reliable)
- **Regolith + ice paste** — For C-type asteroids with water ice content (mixed binder)
- **Bioreactor waste slurry** — Depleted rock fines + water + CaO traces applied by plasterer ants (Track B/C only, zero consumable cost, 75% seal effectiveness; best as bulk filler under polymer spray topcoat)

The mothership serves as the tunnel entrance end cap with an inflatable gasket seal.

### Three Extraction Tracks (Head-to-Head Comparison)

The simulator supports three parallel extraction tracks that can be compared against the same asteroid target:

- **Track A — Mechanical Extraction:** Ants mine directly using rotary scrapers, crushers, and mechanical tools within tunnels.
- **Track B — Bioleaching Extraction:** Ants act as regolith haulers feeding mothership-based centrifuge bioreactor vats where bacterial cultures extract metals from raw rock.
- **Track C — Hybrid Extraction:** Mechanical pre-processing (crushing, grinding) feeds bioleaching vats for final metal extraction. Combines Track A throughput with Track B purity.

All tracks share the same orbital mechanics, tunnel physics, swarm logistics, and economics layers. They diverge at the extraction and processing stages. The simulator must run all three tracks against the same asteroid target and produce comparative cost, yield, timeline, and scalability analyses.

---

## Core Design Principles

- **Real hardware only.** Every component in the simulation (microcontrollers, motors, solar cells, sensors, communication modules, bioreactor vessels, bacterial cultures, chemical reagents) must map to a real purchasable part or material with real specs (mass, power draw, thermal tolerances, failure rates, MTBF, cost). Start with a seed catalog and make it extensible.
- **Real control code.** The ant behavior code is written in MicroPython targeting the specified microcontroller. The simulator executes this code against simulated physics.
- **Three-track comparison.** Mechanical, bioleaching, and hybrid extraction must be runnable against the same scenarios with the same economics framework, producing directly comparable outputs.
- **Layered architecture.** Each layer (orbital mechanics, tunnel physics, robot simulation, swarm coordination, mission economics) should be independently testable and replaceable.
- **Incremental complexity.** Start with the simplest possible working simulation and scale up. Do not try to build everything at once.
- **Quantitative rigor.** Every output should include units, uncertainty ranges, and documented assumptions. This is a feasibility study, not a toy.

---

## Ant Caste System

Inspired by real ant colonies, the swarm uses three specialized castes with different hardware configurations and roles:

### Worker Ant — Cheap, Disposable Tunnel Laborer
The majority of the swarm (~80-90%). Minimal sensors, simple MCU, follows taskmaster commands.

```yaml
ant_config:
  caste: "worker"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 200
  compute:
    part: "RP2040"          # Simple, cheap, low-power
    clock_mhz: 133
    ram_kb: 264
    power_draw_mw: 100
  locomotion:
    actuators: 6
    options:                 # Catalog has both — sim finds cost-optimal
      - part: "micro_servo_sg90"         # COTS: cheap, degrades in vacuum
        per_unit_mass_g: 9
        per_unit_power_mw: 600
        mtbf_hours_sealed_tunnel: 8000   # Much better than vacuum
        mtbf_hours_vacuum: 500
        cost_usd: 3
      - part: "vacuum_rated_actuator"    # Space-rated: expensive, durable
        per_unit_mass_g: 35
        per_unit_power_mw: 800
        mtbf_hours_vacuum: 50000
        cost_usd: 150
  communication:
    part: "nrf24l01_rf"     # Short-range RF to nearest taskmaster/relay
    range_m: 50
    power_mw: 40
    bandwidth_kbps: 250
  sensors:
    - part: "vl53l0x_lidar"   # Proximity/collision avoidance
      power_mw: 20
  tool:
    track_a:
      type: "rotary_scraper"
      part: "micro_dc_motor_n20"
      power_mw: 500
    track_b:
      type: "scoop_gripper"
      part: "micro_servo_sg90"
      power_mw: 100
    track_c:
      type: "rotary_scraper"          # Same as Track A
      part: "micro_dc_motor_n20"
      power_mw: 500
  storage_hopper:
    track_a_capacity_g: 200
    track_b_capacity_g: 350          # Larger: no heavy mining tool
    track_c_capacity_g: 200
  power:
    source: "tethered"               # Power via cable from tunnel bus
    backup_battery_mah: 500          # For short untethered moves
  estimated_cost_usd: 50-100        # COTS version
```

### Taskmaster Ant — Squad Leader with Full Sensor Suite
Commands a squad of ~20 worker ants. Rich sensors, capable MCU, handles navigation and task allocation.

```yaml
ant_config:
  caste: "taskmaster"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 400
  compute:
    part: "ESP32-S3"
    clock_mhz: 240
    ram_kb: 512
    power_draw_mw: 250
  locomotion:
    actuators: 6
    part: "micro_servo_sg90"         # Or vacuum-rated — catalog option
    per_unit_mass_g: 9
    per_unit_power_mw: 600
  communication:
    local:
      part: "nrf24l01_rf"           # Short-range to workers
      range_m: 50
      power_mw: 40
    backbone:
      part: "wired_can_bus"          # Wired connection to tunnel backbone
      bandwidth_kbps: 1000
  sensors:
    - part: "bno055_imu"             # 9-axis IMU for tunnel navigation
      power_mw: 12
    - part: "vl53l0x_lidar"          # Proximity/mapping
      power_mw: 20
    - part: "ov7670_camera"          # Low-res visual odometry
      power_mw: 60
    - part: "as7341_spectral"        # 11-channel spectral for composition
      power_mw: 15
    - part: "ds18b20_temp_probe"     # Temperature monitoring
      power_mw: 1
  tool:
    type: "none"                     # Taskmasters don't mine — they command
  power:
    source: "tethered"
    backup_battery_mah: 1000
  squad_size: 20                     # Workers per taskmaster
  estimated_cost_usd: 200-400
```

### Courier Ant — Surface/Space Operations Specialist
Handles cargo staging at tunnel entrance, return vehicle loading, and surface operations. Only caste that operates outside the tunnel.

```yaml
ant_config:
  caste: "courier"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 500
  compute:
    part: "ESP32-S3"
    clock_mhz: 240
    ram_kb: 512
    power_draw_mw: 250
  locomotion:
    actuators: 6
    part: "vacuum_rated_actuator"    # Must survive surface vacuum
    per_unit_mass_g: 35
    per_unit_power_mw: 800
  communication:
    part: "sx1276_lora"              # Long-range for surface/orbit ops
    range_km: 10
    power_mw: 120
  solar:
    part: "alta_devices_gaas_cell"
    area_cm2: 50
    efficiency: 0.29
    power_output_mw_at_1au: 1450    # NOTE: scales with 1/r^2 from Sun
  sail:
    type: "personal_stationkeeping"
    area_m2: 3                       # Small sail for local maneuvering
    mass_g: 30                       # ~7 g/m2 film + minimal structure
    material: "cp1_polyimide"
    reflectivity: 0.9
  sensors:
    - part: "bno055_imu"
      power_mw: 12
    - part: "sun_sensor_coarse"      # Attitude determination
      power_mw: 5
    - part: "vl53l0x_lidar"
      power_mw: 20
    - part: "radiation_dosimeter"    # Track exposure for lifetime estimation
      power_mw: 2
  thermal:
    heater_power_mw: 500             # Survive shadow side
    mli_blanket_mass_g: 20           # Multi-layer insulation
  power:
    source: "solar"
    battery_mah: 2000
  estimated_cost_usd: 400-800
```

### Sorter Ant — Thermal Drum Operator
Operates the thermal sorting drum, separating water ice and volatiles from raw regolith before it enters the jaw crusher. Worker-class body with a heat-resistant ceramic scoop for handling hot material.

```yaml
ant_config:
  caste: "sorter"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 111
  compute:
    part: "RP2040"
    clock_mhz: 133
    ram_kb: 264
    power_draw_mw: 100
  locomotion:
    actuators: 6
    part: "micro_servo_sg90"
    per_unit_mass_g: 9
    per_unit_power_mw: 600
    mtbf_hours_sealed_tunnel: 8000
    cost_usd: 3
  communication:
    part: "nrf24l01_rf"
    range_m: 50
    power_mw: 40
    bandwidth_kbps: 250
  sensors:
    - part: "vl53l0x_lidar"
      power_mw: 20
    - part: "ds18b20_temp_probe"
      power_mw: 1
  tool:
    type: "ceramic_scoop"
    heat_rating_c: 200
    part: "custom_ceramic_end_effector"
    power_mw: 100
  power:
    source: "tethered"
    backup_battery_mah: 500
  estimated_cost_usd: 38
```

### Plasterer Ant — Tunnel Wall Sealant Applicator
Applies bioreactor waste slurry to tunnel walls as a sealant paste. Worker-class body fitted with a nozzle-and-trowel paste applicator for even coating.

```yaml
ant_config:
  caste: "plasterer"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 108
  compute:
    part: "RP2040"
    clock_mhz: 133
    ram_kb: 264
    power_draw_mw: 100
  locomotion:
    actuators: 6
    part: "micro_servo_sg90"
    per_unit_mass_g: 9
    per_unit_power_mw: 600
    mtbf_hours_sealed_tunnel: 8000
    cost_usd: 3
  communication:
    part: "nrf24l01_rf"
    range_m: 50
    power_mw: 40
    bandwidth_kbps: 250
  sensors:
    - part: "vl53l0x_lidar"
      power_mw: 20
  tool:
    type: "nozzle_and_trowel"
    paste_flow_rate_ml_per_min: 50
    coverage_m2_per_hour: 2
    part: "custom_paste_applicator"
    power_mw: 150
  slurry_hopper:
    capacity_ml: 500
  power:
    source: "tethered"
    backup_battery_mah: 500
  estimated_cost_usd: 41
```

### Tender Ant — Bioreactor Monitor
Monitors bioreactor vats, performing spot-checks on pH and turbidity, and adjusting valves as needed. Worker-class body with a portable pH sensor and fine manipulator for valve operations.

```yaml
ant_config:
  caste: "tender"
  chassis:
    type: "spider_6leg"
    mass_budget_grams: 108
  compute:
    part: "ESP32-S3"           # Needs more processing for sensor analysis
    clock_mhz: 240
    ram_kb: 512
    power_draw_mw: 250
  locomotion:
    actuators: 6
    part: "micro_servo_sg90"
    per_unit_mass_g: 9
    per_unit_power_mw: 600
    mtbf_hours_sealed_tunnel: 8000
    cost_usd: 3
  communication:
    part: "nrf24l01_rf"
    range_m: 50
    power_mw: 40
    bandwidth_kbps: 250
  sensors:
    - part: "vl53l0x_lidar"
      power_mw: 20
    - part: "atlas_scientific_ph_probe_portable"
      power_mw: 50
      accuracy: 0.02
    - part: "turbidity_sensor_tsd10"
      power_mw: 30
    - part: "ds18b20_temp_probe"
      power_mw: 1
  tool:
    type: "fine_manipulator"
    grip_force_n: 5
    precision_mm: 0.5
    part: "micro_servo_gripper"
    power_mw: 200
  power:
    source: "tethered"
    backup_battery_mah: 500
  estimated_cost_usd: 65
```

---

## Architecture Layers

### Layer 1: Orbital Mechanics
- Solar sail propulsion modeling (radiation pressure, sail area, reflectivity, mass ratio)
- Transfer orbit calculation between Earth, target asteroids, Mars, and Lagrange points
- Transit time estimation for solar-sail-propelled units of given mass
- Delta-v budgets for course corrections
- **Destination options:** Earth-Moon L2/Lunar orbit, Mars orbit, Earth return
- **Initial approach:** Use pre-computed transit times from published literature for known NEA targets. Build a custom Keplerian propagator in a later phase.
- **Later phase:** Solar sail trajectory optimization (continuous low-thrust — this is an active research area in astrodynamics, non-trivial to implement)
- **Data sources:** JPL Small Body Database for real asteroid orbital elements, sizes, and estimated compositions

### Layer 2: Tunnel Physics & Environment
- **Replaces** the original surface physics layer as primary operating environment
- Microgravity regolith mechanics inside tunnel cavities
- Tunnel pressure model: sealing effectiveness, leak rate, fill gas requirements, compressor power
- Thermal model: subsurface temperature stability vs. depth, heat generation from operations
- Regolith structural model: tunnel dimensions, stability analysis (trivial in microgravity)
- **Radiation shielding model:** Shielding effectiveness as function of depth
  - 10 cm regolith (~15 g/cm2): blocks most SPE, ~10% GCR reduction
  - 50 cm (~75 g/cm2): blocks all SPE, ~30-40% GCR reduction
  - 1 m (~150 g/cm2): ~50% GCR reduction
  - 2 m (~300 g/cm2): ~70-80% GCR reduction
  - 5 m (~750 g/cm2): ~95%+ GCR reduction
- Surface physics model retained for courier ant operations (anchoring, locomotion, thermal cycling)
- **Suggested tools:** Custom Python models initially; MuJoCo or PyBullet for detailed tunnel physics later

### Layer 3: Robot Hardware Simulation
- Component-level robot model built from catalog parts
- Each ant caste is defined as a configuration file listing specific components
- **Power budget simulation:** Tethered power for workers/taskmasters, solar + battery for couriers
- **Thermal simulation:** Component temperatures based on tunnel pressure environment and duty cycle
- **Degradation modeling:** Component wear based on MTBF, operating conditions, radiation exposure
- **Communication simulation:** Wired backbone bandwidth, RF channel capacity, message routing
- Power output scales with heliocentric distance: P(r) = P(1AU) / r^2

### Layer 3B: Mothership — Modular Infrastructure Platform

The mothership is the mission's infrastructure backbone. It is defined as a collection of interchangeable modules:

#### Drill Module
```yaml
mothership_module_drill:
  type: "initial_excavation"
  drill_head:
    part: "rotary_percussion_drill"
    power_w: 500
    mass_kg: 15
    penetration_rate_m_per_hour: 0.5  # In consolidated regolith
    bit_lifetime_hours: 200
  debris_management:
    type: "auger_conveyor"
    power_w: 100
    mass_kg: 5
  total_mass_kg: 25
  total_power_w: 600
  rad_hardened: true                   # Operates on surface initially
```

#### Power Module
```yaml
mothership_module_power:
  type: "surface_solar_array"
  solar_panels:
    part: "alta_devices_gaas_array"
    area_m2: 20
    efficiency: 0.29
    power_output_w_at_1au: 5800       # Scales with 1/r^2
    mass_kg: 15                        # Including deployment mechanism
  power_distribution:
    tunnel_bus_voltage_v: 48
    cable_mass_per_meter_g: 50
    max_tunnel_depth_m: 100
    distribution_efficiency: 0.92
  battery_bank:
    part: "lithium_iron_phosphate"
    capacity_wh: 10000
    mass_kg: 30
    purpose: "eclipse_survival_and_peak_loads"
  total_mass_kg: 50
  total_power_w: 5800                  # At 1 AU; varies by asteroid distance
```

#### Communication Module
```yaml
mothership_module_comms:
  type: "hybrid_network_hub"
  earth_link:
    part: "high_gain_antenna_x_band"
    power_w: 50
    mass_kg: 5
    data_rate_kbps: 10                 # Deep space, varies with distance
    latency_minutes: 4-24              # Depends on Earth-asteroid distance
  tunnel_backbone:
    type: "wired_can_bus"
    bandwidth_kbps: 1000
    cable_mass_per_meter_g: 30
    relay_nodes:
      spacing_m: 20
      power_per_node_w: 1
      mass_per_node_g: 50
  local_rf:
    part: "nrf24l01_access_point"
    range_m: 50
    channels: 8                        # Simultaneous connections
    power_w: 2
  total_mass_kg: 8
  total_power_w: 55
```

#### Sealing Module
```yaml
mothership_module_sealing:
  type: "tunnel_pressurization"
  seal_options:
    - method: "polymer_spray"
      consumable_kg_per_m2: 0.1
      seal_effectiveness: 0.98         # Pressure retention
      application_power_w: 50
    - method: "regolith_sintering"
      consumable_kg_per_m2: 0          # Uses local material
      power_w: 2000                    # Microwave sintering head
      sintering_head_mass_kg: 10
      seal_effectiveness: 0.85
    - method: "ice_regolith_paste"
      requires: "c_type_asteroid"      # Needs water ice
      consumable_kg_per_m2: 0
      seal_effectiveness: 0.70
    - method: "bioreactor_waste_slurry"
      requires: "active_bioreactor"    # Track B/C only
      consumable_kg_per_m2: 0          # Zero cost — uses waste stream
      seal_effectiveness: 0.75         # CaO traces act as natural cement
      application: "plasterer_ant"     # Applied by plasterer caste
      notes: "Depleted rock fines + water + CaO traces form paste. Portland cement chemistry. Best used as bulk filler with polymer spray topcoat for 0.98 combined effectiveness."
  gasket:
    type: "inflatable_entrance_seal"
    mass_kg: 5
  compressor:
    part: "mini_diaphragm_compressor"
    power_w: 20
    mass_kg: 3
    fill_gas: "nitrogen"
    target_pressure_kpa: 5             # Configurable 1-10 kPa
    leak_makeup_rate_liters_per_day: 2
  fill_gas_supply:
    initial_mass_kg: 5                 # Enough for ~500 m3 at 5 kPa
  total_mass_kg: 15-25                 # Depends on sealing method
  total_power_w: 20-2050               # Depends on sealing method
```

#### Cargo Staging Module
```yaml
mothership_module_cargo:
  type: "return_vehicle_staging"
  storage_bins:
    capacity_kg: 500
    mass_kg: 10
  packaging:
    type: "regolith_bag_compactor"
    power_w: 50
    mass_kg: 5
  return_vehicles:
    count: 5                           # Per mission cycle
    config: "see return vehicle section"
  total_mass_kg: 20                    # Excluding return vehicles
```

#### Thermal Sorting Module
```yaml
mothership_module_thermal_sort:
  type: "pre_crusher_volatile_separation"
  heated_drum:
    operating_temp_c: 120
    drum_diameter_m: 0.4
    drum_length_m: 0.6
    rotation_rpm: 5
    heating_power_w: 300
    mass_kg: 15
  ice_recovery:
    rate: 0.90                          # 90% water ice recovery
    collection: "cold_trap_condenser"
    condenser_power_w: 50
    condenser_mass_kg: 5
  co2_capture:
    method: "cold_trap"
    destination: "algae_photobioreactor" # Feeds sugar production module
  throughput_kg_per_hour: 10
  operator: "sorter_ant"                # Sorter caste loads/unloads drum
  benefits:
    - "Prevents crusher clogging from wet material"
    - "Recovers water ice for bioreactor medium and electrolysis"
    - "Captures CO2 for algae photobioreactor"
    - "Dry sorted material improves crusher efficiency"
  total_mass_kg: 22
  total_power_w: 380
```

#### Exterior Maintenance System
```yaml
mothership_exterior_maintenance:
  type: "hull_maintenance_infrastructure"
  grip_rails:
    type: "extruded_aluminum_t_slot"
    coverage: "full_hull_grid"
    spacing_m: 0.5
    mass_kg: 8
  magnetic_cleats:
    type: "switchable_magnetic_anchor"
    count: 24
    per_unit_mass_g: 50
    per_unit_power_mw: 100              # Only when switching
  tool_docking_points:
    count: 12
    locations: "distributed_at_maintenance_stations"
    per_point_mass_g: 200
    tools_available: ["brush", "torque_driver", "seal_applicator", "inspection_camera"]
  maintenance_tasks:
    - task: "solar_panel_dust_removal"
      frequency: "weekly"
      duration_minutes: 30
    - task: "antenna_alignment_check"
      frequency: "weekly"
      duration_minutes: 20
    - task: "hull_seal_inspection"
      frequency: "weekly"
      duration_minutes: 40
    - task: "thermal_radiator_cleaning"
      frequency: "biweekly"
      duration_minutes: 30
  operator: "courier_ant"               # Only caste rated for exterior work
  dedicated_units: 1                    # 1 courier ant assigned to maintenance
  weekly_maintenance_hours: 3
  total_infrastructure_mass_kg: 12
```

### Layer 3C: Bioreactor Module (Track B and Track C)

The mothership carries a modular bioleaching plant using **centrifuge bioreactors** to handle microgravity fluid dynamics. All bioreactor vessels are rotating drum designs that simulate partial gravity for settling, aeration, and mixing.

#### Centrifuge Bioreactor Design
```yaml
centrifuge_bioreactor_system:
  rotation_rate_rpm: 20-40             # Provides 0.01-0.1g equivalent
  bearing_type: "magnetic_bearing"     # No lubricant outgassing concerns
  bearing_power_w: 5                   # Per vessel
  spin_up_power_w: 20                  # Per vessel, brief
  structural_mass_overhead: 1.3        # 30% mass increase over static vessel
  # Centrifuge solves: settling, gas/liquid separation, mixing via Coriolis
```

#### Crusher Module
```yaml
crusher:
  type: "jaw_crusher_mini"
  input_size_mm: 50
  output_size_mm: 2
  throughput_kg_per_hour: 5
  power_w: 200
  mass_kg: 30
  # Track A: final product is crushed ore
  # Track B: feeds bioreactor vats
  # Track C: mechanical crushing feeds bioreactor (higher throughput than Track B alone)
```

#### Vat 1 — Sulfide Metal Bioreactor
```yaml
vat_sulfide:
  volume_liters: 200
  vessel_material: "stainless_316L"
  vessel_mass_kg: 32.5                 # 25 kg static × 1.3 centrifuge overhead
  centrifuge_rpm: 30
  bacteria:
    - species: "acidithiobacillus_ferrooxidans"
      optimal_temp_c: 30
      optimal_ph: 2.0
      doubling_time_hours: 12
      radiation_tolerance: "low"       # Needs shielding
    - species: "acidithiobacillus_thiooxidans"
      optimal_temp_c: 30
      optimal_ph: 2.5
      doubling_time_hours: 10
      radiation_tolerance: "low"
  target_metals: ["iron", "copper", "nickel", "cobalt", "zinc"]
  residence_time_days: 15
  extraction_efficiency: 0.85
  aeration:
    type: "membrane_gas_exchanger"     # No bubbles needed in centrifuge
    power_w: 10
  heating_power_w: 50
  monitoring:
    - part: "atlas_scientific_ph_kit"
      power_mw: 50
    - part: "atlas_scientific_orp_kit"
      power_mw: 50
    - part: "ds18b20_temp_probe"
      power_mw: 5
```

#### Vat 2 — Rare Earth Bioreactor
```yaml
vat_ree:
  volume_liters: 100
  vessel_material: "HDPE"
  vessel_mass_kg: 13                   # 10 kg × 1.3
  centrifuge_rpm: 25
  organisms:
    - species: "aspergillus_niger"
      type: "fungal"
      optimal_temp_c: 28
      optimal_ph: 4.0
      doubling_time_hours: 8
      nutrient_requirement: "sucrose_10g_per_liter"
      radiation_tolerance: "moderate"  # Fungal spores more resilient
  target_metals: ["lanthanum", "cerium", "neodymium", "yttrium", "aluminum"]
  residence_time_days: 14
  extraction_efficiency: 0.60
  nutrient_consumption_kg_per_cycle: 1.0
  heating_power_w: 30
```

#### Vat 3 — Platinum Group Metals (Hybrid)
```yaml
vat_pgm:
  volume_liters: 50
  vessel_material: "stainless_316L"
  vessel_mass_kg: 10.4                 # 8 kg × 1.3
  centrifuge_rpm: 20
  bacteria:
    - species: "chromobacterium_violaceum"
      optimal_temp_c: 28
      optimal_ph: 7.5
      doubling_time_hours: 4
      cyanide_production_mg_per_liter_per_day: 5
      radiation_tolerance: "low"
  target_metals: ["platinum", "palladium", "iridium", "rhodium"]
  residence_time_days: 30
  extraction_efficiency: 0.40          # PGM bioleaching is immature
  sealed: true
  heating_power_w: 20
  chemical_backup:
    reagent: "sodium_cyanide"
    concentration_g_per_liter: 2
    consumption_per_cycle_kg: 0.5
```

#### Precipitation & Separation
```yaml
precipitation:
  stages:
    - metal: "copper"
      precipitation_ph: 5.3
      reagent: "calcium_oxide"
    - metal: "nickel"
      precipitation_ph: 7.5
      reagent: "sodium_hydroxide"
    - metal: "cobalt"
      precipitation_ph: 8.1
      reagent: "sodium_hydroxide"
  pump:
    part: "peristaltic_pump_mini"
    flow_rate_ml_per_min: 100
    power_w: 5
    mass_g: 500
  filter:
    type: "ceramic_filter_element"
    pore_size_um: 0.5
    mass_g: 200
    replacement_interval_days: 90
```

#### Water Recovery & Radiation Shielding
```yaml
water_recovery:
  recirculation_rate: 0.95
  loss_per_cycle_liters: 5
  ph_adjustment_reagent: "sulfuric_acid"

radiation_shielding:
  bio_bay_location: "minimum_2m_below_surface"
  additional_shielding: "water_jacket"  # Water supply doubles as radiation shield
  water_jacket_thickness_cm: 10         # ~10 g/cm2 additional shielding
```

#### Bioreactor Mass & Power Summary
```yaml
bioprocessing_totals:
  total_dry_mass_kg: 110               # Includes centrifuge overhead (30% over original 85 kg)
  total_wet_mass_kg: 410               # dry + 300 kg water (300 liters)
  total_power_budget_w: 400            # Including centrifuge bearings
  water_required_initial_liters: 300   # = 300 kg launch mass
  consumables_per_year_kg: 25          # Nutrients, reagents, filters
  centrifuge_power_overhead_w: 15      # 3 vessels × 5W bearing power
```

**CRITICAL NOTE FOR LAUNCH ECONOMICS:** The wet mass of the bioprocessing module is **410 kg**, not 110 kg. The 300 kg of water dominates the launch cost for Track B/C. This must be reflected in all economic calculations.

#### Processing Pipeline — Complete Material Flow

The full extraction pipeline from raw regolith to return cargo, showing which ant caste operates each stage:

```
Raw regolith
  -> [Sorter ant] Thermal drum (120C: ice sublimes, CO2 captured)
  -> [Taskmaster] Spectral sort by mineral type
  -> Jaw crusher (dry, sorted, <2mm)
  -> [Worker ants] deliver to correct bioreactor vat
  -> Bioleaching (bacteria extract metals into solution)
  -> Selective precipitation (metals separated by pH)
  -> Metal concentrates -> cargo pods -> return vehicle

Waste slurry -> [Plasterer ant] tunnel wall sealant (zero consumable cost)
Captured water -> bioreactor medium + electrolysis for H2
Captured CO2 -> algae photobioreactor -> sugar -> feeds Aspergillus
```

**Key integration points:**
- Thermal sorting (sorter ants) prevents crusher clogging and recovers volatiles *before* crushing
- Spectral sorting (taskmasters) ensures each bioreactor vat receives the correct mineral feedstock
- Waste slurry recycling (plasterer ants) closes the waste loop at zero consumable cost
- CO2 and water recovery feed back into the bioreactor and sugar production systems
- Tender ants provide continuous bioreactor monitoring between automated sensor readings

#### Sugar Production Module — On-Site Nutrient Synthesis

Eliminates Earth resupply of sucrose for the Aspergillus niger REE bioreactor vat by producing sugar on-site from captured CO2.

```yaml
sugar_production_module:
  photobioreactor:
    organism: "chlorella_vulgaris"
    volume_liters: 200
    vessel_material: "polycarbonate"
    vessel_mass_kg: 12
    illumination:
      type: "fiber_optic_solar"        # Fiber optic bundle routes surface sunlight
      fiber_bundle_mass_kg: 3
      collector_area_m2: 0.5
      transmission_efficiency: 0.60
    co2_source: "asteroid_carbonate_pyrolysis"
    growth_rate_g_per_liter_per_day: 0.5-0.8
    sugar_output_g_per_day: 100-160    # 1 kg every 7-10 days
    harvesting: "centrifugal_continuous"
    harvesting_power_w: 20

  co2_supply:
    source: "carbonate_pyrolysis_kiln"
    kiln_temp_c: 700
    kiln_power_w: 300
    kiln_mass_kg: 8
    feedstock: "asteroid_carbonates"    # CaCO3 -> CaO + CO2
    co2_yield_kg_per_kg_rock: 0.44     # Stoichiometric
    byproduct: "calcium_oxide"         # CaO -> used by plasterer ants as cement

  chemosynthetic_backup:
    organism: "cupriavidus_necator"
    type: "hydrogen_autotroph"
    inputs: ["H2", "CO2"]              # No light needed
    sugar_output_g_per_day: 40-60      # Lower yield but light-independent
    power_w: 80                        # Electrolysis for H2 production
    use_case: "eclipse_periods_or_deep_asteroid"

  totals:
    total_mass_kg: 62
    total_power_w: 470
    sugar_output_kg_per_year: 36-58
    eliminates_earth_resupply: true    # No more sucrose launches
    consumables_saved_kg_per_year: 25  # Previously imported from Earth
```

**Integration with bioreactor system:** Sugar output feeds directly into the Aspergillus niger REE vat (Vat 2), which requires 10g/L sucrose per cycle. At 100-160g/day production, the photobioreactor can sustain continuous REE bioleaching without Earth resupply. The CaO byproduct from carbonate pyrolysis feeds the plasterer ant waste slurry sealant system.

### Layer 4: Ant Control Code
- Written in **MicroPython** targeting the specified microcontroller (RP2040 for workers, ESP32-S3 for taskmasters/couriers)
- Runs natively within the Python simulation framework
- Core behaviors implemented as state machines:

#### Worker Ant Behaviors (all tracks)
- **Idle**: Wait for taskmaster command
- **Move**: Follow directed path along tunnel
- **Dig**: Excavate regolith from tunnel face (Track A: rotary scraper, Track B: scoop, Track C: rotary scraper)
- **Load**: Fill hopper with excavated/collected material
- **Haul**: Transport loaded hopper to designated dump point
- **Dump**: Deposit material (Track A: collection bin, Track B/C: bioreactor intake sorted by spectral class)
- **Return**: Move back to work face for next cycle
- **Emergency Stop**: Immediate halt on taskmaster command or fault detection

#### Taskmaster Ant Behaviors
- **Survey**: Map tunnel geometry using IMU + lidar + visual odometry
- **Classify**: Use spectral sensor to identify regolith composition at work face
- **Assign**: Allocate workers to dig/haul/idle based on extraction priorities
- **Route**: Plan efficient paths for workers within tunnel network
- **Monitor**: Track worker status, detect faults, report to mothership
- **Coordinate**: Communicate with adjacent taskmasters for cross-squad logistics

#### Courier Ant Behaviors (surface operations)
- **Navigate Surface**: Move across asteroid surface using IMU + sun sensor
- **Anchor**: Secure to surface before working
- **Stage Cargo**: Move processed material from tunnel entrance to return vehicle
- **Sail Attach**: Connect return vehicle sail for departure
- **Guide Return**: Attach to return cargo as guidance unit for transit (end-of-life role)

#### Track B/C Additional Behaviors
- **Spectral Sort** (taskmaster): Pre-classify regolith composition, assign workers to deliver to correct vat intake
- **Tend Bioreactor** (dedicated worker role): Monitor sensors, trigger alerts on pH/temp/ORP excursions, mechanically agitate slurry

#### Swarm Coordination
- Workers follow taskmaster commands — no peer-to-peer worker coordination
- Taskmasters coordinate locally with adjacent taskmasters via wired backbone
- Mothership provides high-level directives (mining priorities, vat status) via supervised autonomy
- **No centralized control** — each taskmaster makes local decisions within mothership-set parameters

### Layer 5: Swarm Simulation
- Scale from 1 ant to <1000 ants with individual agent simulation
- Agent-based simulation where each ant runs its own MicroPython control code instance
- Squad-level organization: 1 taskmaster + ~20 workers per squad
- Emergent behavior tracking: mining/hauling rate, tunnel expansion rate, resource allocation
- Attrition modeling: component degradation, failures, swarm performance curves
- **Track B/C specific:** Model the feedback loop between swarm hauling rate and bioreactor throughput — if ants deliver faster than vats can process, regolith queues build up; if too slowly, bacteria may starve
- **Track comparison mode:** Run all three tracks with identical swarm sizes against the same asteroid
- **Statistical scaling (later phase):** Validate small-N model, then extrapolate to 10K-100K using statistical/aggregate models
- **Suggested tools:** Mesa (Python agent-based modeling) for prototyping, custom engine for scale

### Layer 6: Mission Economics
- **Multi-destination revenue model:**

  | Material | Earth Return ($/kg) | Lunar Orbit ($/kg) | Mars Orbit ($/kg) |
  |----------|-------------------|-------------------|-------------------|
  | Water | ~0.001 | 50K-500K | 1M+ |
  | Iron/Nickel | ~0.50 | 10K-50K | 500K+ |
  | Platinum | ~30,000 | 30K + delivery | 30K + delivery |
  | Rare Earths | 10-1,000 | 10K-50K | 500K+ |

  Lunar/Mars values based on launch cost avoidance. All materials are valuable at Mars orbit.

- **Cost modeling:**
  - Component cost per ant by caste (from catalog prices)
  - Mothership module costs (configurable loadout)
  - Launch cost per kg (configurable: Falcon 9 ~$2,700/kg, Starship ~$200-500/kg projected)
  - Consumables per mission cycle (Track B/C: nutrients, reagents, fill gas)
  - Attrition replacement costs

- **Mission timeline:**
  - Launch → transit (months to years via solar sail) → arrival → excavation (mothership drills) → tunnel sealing → operations → return cargo cycles
  - Track A: Mine → crush → stage → return
  - Track B: Scoop → sort → bioreact (5-30 day residence) → precipitate → stage → return
  - Track C: Mine → crush → bioreact → precipitate → stage → return
  - Track B/C have latency before first return but continuous pipeline once running

- **Key economic outputs:**
  - **Mass budget** (first-class output — total mission mass by category)
  - Break-even analysis per track
  - Cost per kg of extracted metal (Track A vs B vs C)
  - Time to first revenue
  - NPV / IRR over N mission cycles
  - Bootstrap curve: cycle N revenue funds cycle N+1 with scaling factor
  - Sensitivity analysis: which parameters matter most?

- **Head-to-head comparison outputs:**
  - Scaling curves: cost-per-kg vs. swarm size (10 to 10,000 ants)
  - Robustness: performance degradation under 10%, 30%, 50% attrition
  - Track B/C consumables dependency: at what scale does Earth resupply become dominant cost?
  - Hybrid advantage: does Track C outperform both A and B?

### Layer 7: Return Vehicle

Each return cargo pod needs guidance, navigation, and a capture strategy. The return vehicle is not just "a bucket with a sail."

```yaml
return_vehicle:
  structure:
    cargo_capacity_kg: 100
    structure_mass_kg: 5
    material: "aluminum_honeycomb"
  sail:
    area_m2: 25                        # Large shared sail — realistic at this scale
    mass_kg: 0.5                       # ~175g film + 325g booms/deployment
    material: "cp1_polyimide"
    reflectivity: 0.9
  guidance:
    part: "ESP32-S3"                   # Or rad-tolerant option
    star_tracker:
      part: "st-16_star_tracker"       # Miniature star tracker
      mass_g: 100
      power_mw: 500
    sun_sensor:
      part: "coarse_sun_sensor"
      mass_g: 10
      power_mw: 5
    reaction_wheels:                   # Attitude control
      count: 3
      per_unit_mass_g: 50
      per_unit_power_mw: 200
  capture_strategy:
    primary: "lunar_orbit_insertion"   # Target Earth-Moon L2
    method: "solar_sail_deceleration"  # Sail provides braking thrust
    backup: "tug_rendezvous"           # Orbital tug matches and captures
    # Mars orbit option: target Mars-Sun L1 or Mars orbit insertion
  total_mass_kg: 6.5                   # Empty (excluding cargo)
  total_cost_usd: 500-2000
  guidance_ant: "courier_ant_eol"      # End-of-life courier ant serves as guidance unit
```

### Layer 8: Visualization & Dashboard
- 3D orbital view: fleet transit, asteroid position, return cargo trajectories
- Tunnel network view: ant activity within the asteroid, tunnel expansion over time
- Real-time mission economics dashboard (costs, revenue, attrition, material extracted)
- Component stress dashboard (thermal, power budget, degradation per ant)
- **Track comparison panels:** A vs B vs C side-by-side metrics
- **Bioreactor status:** Bacterial population health, vat pH/temp/ORP, extraction rates, consumables remaining
- **Suggested tools:** Plotly/Dash for prototyping, Three.js for production 3D dashboard

---

## Autonomy & Earth Communication

The mission operates under **supervised autonomy**:
- Day-to-day operations are fully autonomous (swarm + mothership AI)
- Ground control sends high-level commands: retarget mining area, adjust extraction priorities, approve return vehicle launches
- Communication via deep space network with realistic latency:
  - Near-Earth asteroid: 2-30 minutes one-way (varies with orbital position)
  - Mars-crossing asteroid: 4-24 minutes one-way
  - Bandwidth: ~1-10 kbps (sufficient for telemetry and commands, not real-time video)
- Mothership makes all time-critical decisions autonomously (emergency stops, fault recovery, vat pH adjustment)
- Ants never communicate directly with Earth — only via mothership relay

---

## Implementation Plan — Build Incrementally

### Phase 1: Foundation & First Numbers
1. Set up Python project with clear module structure matching layers above
2. Create the component catalog system (YAML/JSON database of real parts with specs, MTBF, costs)
3. Seed the catalog:
   - Ant castes: worker, taskmaster, courier configs with all component options
   - Mothership modules: drill, power, comms, sealing, cargo, bioreactor
   - Bacterial/fungal species profiles with published kinetics data
   - Reagents and consumables with mass, cost, consumption rates
   - Sealing materials with effectiveness and mass per area
4. Pre-compute NEA transit times from published literature for 5 target asteroids
5. Build a single ant power/thermal budget calculator
6. Build tunnel environment model (pressure, sealing mass, fill gas, radiation shielding vs. depth)
7. Build basic economics framework (mass budget → launch cost → opex → revenue at destination → break-even)
8. **Deliverable:** For a given asteroid + destination + swarm config, output: total mission mass by category, launch cost, estimated extraction rate, time to first revenue, break-even swarm size

### Phase 2: Single Ant on a Rock
9. Build simplified tunnel physics model (microgravity regolith in cavity)
10. Build the robot hardware simulator (reads ant config, simulates power budget, thermal state, degradation)
11. Write worker ant MicroPython state machine (dig, load, haul, dump)
12. Write taskmaster ant behavior (navigate tunnel, assign tasks, monitor workers)
13. **Track A:** One squad mines and crushes ore
14. **Track B:** One squad scoops and hauls; build single-vat bioreactor ODE simulation (Monod kinetics, SciPy solve_ivp)
15. **Track C:** One squad mines; mechanical crushing feeds bioreactor
16. **Deliverable:** 1 taskmaster + N workers for each track. Extraction rate comparison. First three-way data point.

### Phase 3: Swarm & Full Economics
17. Scale to multiple squads with agent-based simulation
18. Model tunnel network expansion over time
19. Full 3-vat bioreactor pipeline with precipitation and water recovery
20. Attrition modeling: component degradation, failures, squad reshuffling
21. **Track B/C:** Bioreactor failure modes (culture crash, contamination, nutrient depletion) and recovery
22. Full bootstrap economics loop: cycle N revenue funds cycle N+1
23. **Deliverable:** Multi-cycle mission comparison, A vs B vs C, break-even curves, sensitivity analysis, mass budget report

### Phase 4: Orbital Mechanics & Return Operations
24. Build Keplerian orbit propagator (2-body problem)
25. Build solar sail thrust model
26. Implement return vehicle trajectory planning (to lunar orbit or Mars orbit)
27. Courier ant surface/space operations
28. **Deliverable:** End-to-end simulation: launch → transit → arrive → mine → return cargo → revenue

### Phase 5: Scaling & Advanced Features
29. Statistical scaling model: validate against detailed sim at small N, extrapolate to 10K-100K
30. Multi-cycle simulation: bootstrap from seed investment to self-sustaining operation
31. Asteroid nudging: fraction of effort dedicated to orbital modification
32. **Track C optimization:** Find optimal mechanical/biological processing ratio
33. Local nutrient production modeling (growing sugar feedstock for REE vat)
34. **Deliverable:** Multi-decade simulation showing path from seed investment to self-sustaining mining operation

### Phase 6: Visualization
35. Build 3D orbital visualization
36. Build tunnel network activity visualization
37. Build economics dashboard with track comparison panels
38. Bioreactor status dashboard
39. **Deliverable:** Interactive web dashboard with full simulation state and comparison mode

---

## Technical Stack

- **Language:** Python for simulation framework, MicroPython for ant control code
- **Physics:** Custom models initially; MuJoCo or PyBullet for detailed tunnel physics later
- **Orbits:** Pre-computed literature values initially; custom propagator later
- **Agent modeling:** Mesa for prototyping, custom engine for performance at scale
- **Bioreactor modeling:** SciPy (integrate.solve_ivp) for ODE-based bacterial growth and extraction kinetics; Monod kinetics for growth rate modeling
- **Data formats:** YAML for configs, SQLite for simulation logs, JSON for component catalog
- **Visualization:** Plotly/Dash for prototyping, Three.js for production dashboard
- **Testing:** pytest with property-based testing for physics validation; bioreactor model validation against published experimental data

---

## Component Catalog Seed Data Needed

### Shared Components (All Castes)
- 3 microcontroller options (ESP32-S3, RP2040, STM32L4) with power, cost, rad tolerance data
- 3 solar cell types (GaAs space-grade, silicon commodity, thin-film flexible) with efficiency curves vs. temperature
- Actuator options: COTS (SG90 — cheap, limited MTBF) and vacuum-rated (expensive, durable) with mass, power, cost, MTBF in both vacuum and sealed-tunnel environments
- 2 communication modules (LoRa for surface, nRF24L01 for tunnel RF)
- Sensor catalog: lidar (VL53L0x), IMU (BNO055), camera (OV7670), spectral (AS7341), temperature (DS18B20), sun sensor, radiation dosimeter
- 2 solar sail material options with real areal density and reflectivity
- Real asteroid data for 5 target candidates with **known compositions** from sample-return missions (Bennu, Ryugu, Itokawa) and well-characterized spectral data (Eros, Psyche)

### Mothership Hardware
- Drill/excavation options with penetration rates for different regolith types
- Solar array sizing for different heliocentric distances
- Battery bank options
- Sealing materials (polymer spray, sintering equipment)
- Communication equipment (high-gain antenna, wired backbone cable)

### Track A — Mechanical Mining
- 2 mining tool motor options with wear rates
- Cutting/scraping head materials and lifetime
- Crusher options with throughput, power, mass

### Track B/C — Bioleaching
- **Bacterial/fungal species profiles** (research real published data):
  - *Acidithiobacillus ferrooxidans*: growth rate, optimal pH/temp, iron/sulfur oxidation rates, metal dissolution kinetics for copper, nickel, cobalt from sulfide ores
  - *Acidithiobacillus thiooxidans*: sulfur oxidation rate, synergy when co-cultured with ferrooxidans
  - *Aspergillus niger*: citric acid production rate, REE dissolution kinetics, sugar consumption
  - *Gluconobacter oxydans*: alternative to Aspergillus for REE
  - *Chromobacterium violaceum*: cyanide production rate, PGM dissolution kinetics, biosafety

- **Bioreactor hardware** (real purchasable lab/industrial equipment):
  - Centrifuge bioreactor vessel options with mass (including 30% centrifuge overhead)
  - Mini jaw crusher with throughput, power, mass
  - Peristaltic pumps, ceramic filters, monitoring sensor kits

- **Reagents and consumables** (mass, cost, consumption rates):
  - Sulfuric acid, calcium oxide, sodium hydroxide, sucrose/glucose, sodium cyanide, filter replacements, backup lyophilized culture stocks

---

## Key Simulation Questions to Answer

### Per-Track Questions
1. What is the minimum viable ant swarm (workers + taskmasters + couriers) for each track?
2. What is the minimum swarm size for a profitable single-cycle mission to lunar orbit?
3. How many bootstrap cycles from a $X seed investment to self-sustaining?
4. What is the optimal ratio of workers : taskmasters : couriers?
5. Which asteroids with known compositions offer the best economics?
6. At what launch cost ($/kg) does the business model work for a non-billionaire?
7. How does parking materials at Mars orbit vs. lunar orbit change the economics?
8. What is the optimal tunnel pressure for COTS component lifetime vs. sealing cost?

### Head-to-Head Comparison Questions
9. Which track achieves lower cost-per-kg at small scale (<100 ants)?
10. Which track achieves lower cost-per-kg at large scale (>10,000 ants)?
11. Which track reaches first revenue faster?
12. Which track is more resilient to high attrition rates (30%+ ant loss)?
13. Which track produces higher purity output?
14. At what scale does Track B's bioreactor capacity become the bottleneck?
15. Does Track C (hybrid) outperform both pure tracks? At what scale?
16. Track B/C consumables: when does local nutrient production become necessary?
17. Which track has the most favorable bootstrap curve to self-sustaining operations?

---

## Documented Assumptions & Simplifications

Every simplification should be noted so it can be upgraded later. Initial assumptions include:

- **Orbital mechanics:** Pre-computed transit times, not propagated trajectories (Phase 1-3)
- **Tunnel stability:** Assumed stable in microgravity (valid for rubble pile asteroids; may not hold for monolithic rock)
- **Sealing effectiveness:** Assumed constant over time (real seals degrade)
- **Bioreactor kinetics:** Based on terrestrial published data (microgravity centrifuge may differ)
- **Regolith properties:** Based on Bennu/Ryugu sample-return data (may not apply to all targets)
- **Communication:** Perfect message delivery within tunnel (no packet loss modeled initially)
- **Economics:** Commodity prices held constant (real markets fluctuate)
- **Radiation:** Uses empirical shielding curves, not Monte Carlo particle transport

---

## Notes for Development

- Build each phase as a working deliverable before moving to the next
- Write tests at every phase — physics models especially need validation against known solutions
- **Bioreactor kinetics must be validated against published literature values** — Acidithiobacillus ferrooxidans copper extraction from chalcopyrite is well-studied; use published dissolution curves to calibrate
- Keep the component catalog system extensible — users will want to add new parts
- The bacterial/fungal species catalog must also be extensible
- The ant control code must be real MicroPython that could run on the target MCU
- Optimize for clarity and modularity over performance initially
- Use type hints throughout
- Document assumptions prominently
- Track comparison outputs should be generated automatically when all tracks complete
- **Mass budget is a first-class output** — total mission mass by category is the #1 metric for feasibility
- Bioreactor simulation is computationally heavier than mechanical mining — profile early, optimize if needed
