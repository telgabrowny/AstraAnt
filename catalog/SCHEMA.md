# AstraAnt Catalog Schema

All catalog entries are YAML files. Drop a new file into the appropriate directory to add a part.

## Parts (`catalog/parts/`)

```yaml
id: "unique_part_id"               # Snake_case identifier used in configs
name: "Human Readable Name"
category: "compute|actuator|solar|sensor|communication|sail|battery|motor|pump|filter|vessel|structure"
description: "Brief description"

specs:
  mass_g: 9.0                      # Mass in grams
  power_draw_mw: 600               # Power consumption in milliwatts
  # ... category-specific specs

environmental:
  temp_min_c: -40                   # Operating temperature range
  temp_max_c: 85
  vacuum_compatible: false          # Can operate in hard vacuum
  sealed_tunnel_compatible: true    # Can operate in 1-10 kPa environment
  radiation_tolerance: "none|low|moderate|high"
  mtbf_hours_vacuum: 500           # Mean time between failures in vacuum
  mtbf_hours_sealed: 8000          # MTBF in sealed tunnel (1-10 kPa)
  mtbf_hours_earth: 50000          # MTBF at Earth conditions

sourcing:
  suppliers:
    - name: "DigiKey"
      url: "https://www.digikey.com/..."
      part_number: "XXX-YYY"
      price_usd: 3.50
      date_checked: "2026-03-26"
    - name: "Mouser"
      url: "https://www.mouser.com/..."
      part_number: "AAA-BBB"
      price_usd: 3.25
      date_checked: "2026-03-26"
  price_history:
    - date: "2026-03-26"
      price_usd: 3.50
      source: "DigiKey"

notes: "Any relevant notes about this part"
datasheet_url: "URL to datasheet"
added_date: "2026-03-26"
last_updated: "2026-03-26"
```

## Species (`catalog/species/`)

```yaml
id: "species_id"
name: "Scientific Name"
common_name: "Common name"
type: "bacteria|fungal"
description: "What this organism does"

growth:
  optimal_temp_c: 30
  temp_range_c: [20, 40]
  optimal_ph: 2.0
  ph_range: [1.5, 3.0]
  doubling_time_hours: 12
  growth_model: "monod"            # Kinetics model to use
  monod_params:
    mu_max_per_hour: 0.058         # Maximum specific growth rate
    ks_g_per_liter: 0.5            # Half-saturation constant

extraction:
  target_metals: ["copper", "nickel", "cobalt"]
  mechanism: "Description of extraction mechanism"
  extraction_rate_mg_per_liter_per_day: 50
  extraction_efficiency: 0.85       # Fraction of target metal dissolved
  residence_time_days: 15

requirements:
  aeration: true
  nutrients: ["ferrous_sulfate"]
  nutrient_consumption_g_per_liter_per_day: 0.5

environmental:
  radiation_tolerance: "low|moderate|high"
  radiation_ld50_gray: 200
  vacuum_survival: false
  spore_forming: false

references:
  - "Author et al. (Year). Title. Journal."

notes: "Relevant notes"
added_date: "2026-03-26"
```

## Asteroids (`catalog/asteroids/`)

```yaml
id: "asteroid_id"
name: "Official Name"
designation: "IAU Designation"
discovery:
  date: "YYYY-MM-DD"
  discoverer: "Name"

physical:
  diameter_m: 500
  mass_kg: 7.329e10
  density_kg_per_m3: 1190
  surface_gravity_m_per_s2: 0.000006
  rotation_period_hours: 4.3
  spectral_class: "B"              # Tholen or SMASS classification
  albedo: 0.044

orbit:
  semi_major_axis_au: 1.126
  eccentricity: 0.204
  inclination_deg: 6.035
  perihelion_au: 0.897
  aphelion_au: 1.356
  orbital_period_years: 1.196
  epoch: "2025-01-01"

composition:
  source: "sample_return|spectral_inference|radar"
  confidence: "high|medium|low"
  bulk:                             # Weight percentages
    silicates: 50.0
    iron_nickel: 5.0
    carbon: 2.0
    water_ice: 10.0
    # ... other components
  metals_ppm:                       # Parts per million for valuable metals
    platinum: 0
    palladium: 0
    iridium: 0
    copper: 0
    nickel: 50000                   # 5%
    cobalt: 0
    rare_earths_total: 0

mining_relevance:
  accessibility:
    delta_v_from_leo_km_per_s: 5.0
    estimated_transit_days_solar_sail: 730
    launch_windows_per_year: 1
  value_assessment: "Brief assessment of mining potential"
  water_availability: true|false
  regolith_type: "rubble_pile|monolithic|mixed"

references:
  - "Source of composition data"

notes: "Relevant notes"
added_date: "2026-03-26"
last_updated: "2026-03-26"
```

## Reagents (`catalog/reagents/`)

```yaml
id: "reagent_id"
name: "Chemical Name"
formula: "Chemical formula"
category: "acid|base|nutrient|precipitant|backup_leach"

specs:
  density_g_per_ml: 1.84
  concentration: "Concentration if solution"
  consumption_rate: "Usage description"

sourcing:
  suppliers:
    - name: "Sigma-Aldrich"
      price_usd_per_kg: 50
      date_checked: "2026-03-26"
  price_history:
    - date: "2026-03-26"
      price_usd_per_kg: 50
      source: "Sigma-Aldrich"

safety:
  hazard_class: "Corrosive|Toxic|etc"
  handling_notes: "Notes"

added_date: "2026-03-26"
```
