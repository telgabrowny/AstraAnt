# Hobbyist Bioleaching & Electrowinning Guide

Tabletop-scale asteroid mining: feed bacteria some rocks, use electricity to get metal.
Total cost ~$100-150. Everything reusable except consumables (ore, chemicals).

---

## Experiment Progression

Don't jump to the complex stuff. Each experiment validates a piece of the pipeline.

| # | What | Goal | Time |
|---|------|------|------|
| 1 | Pyrite + A. ferrooxidans | Prove bacteria dissolve rock | 3-4 weeks |
| 2 | Add chalcopyrite | Extract copper, selective electrowinning | 3-4 weeks |
| 3 | Sulfides in silicate matrix | Bioleach through gangue rock | 4-6 weeks |
| 4 | Full regolith simulant | Simulate asteroid ore processing | 4-6 weeks |

---

## Shopping List

### Bacteria

| Organism | Role | Source | Cost |
|----------|------|--------|------|
| Acidithiobacillus ferrooxidans | Sulfide metal extraction | Carolina Biological Supply, Ward's Science | $15-30 |
| (alternative) | Same | Collect orange water from acid mine drainage, culture in 9K medium | Free |
| Aspergillus niger | REE extraction (Exp 5+) | Biological supply, or isolate from bread/fruit mold | $10-20 |

DO NOT attempt Chromobacterium violaceum (PGM/gold track) at home. It produces hydrogen cyanide gas.

### Ore (1 kg units)

| Mineral | Formula | Target | Source | Cost |
|---------|---------|--------|--------|------|
| Pyrite | FeS2 | Iron | eBay/Etsy mineral dealers, Amazon "iron pyrite rough bulk", rock shops | $5-15/kg |
| Chalcopyrite | CuFeS2 | Copper | Mineral dealers (eBay/Etsy) | $10-20/kg |
| Pentlandite | (Fe,Ni)9S8 | Nickel | Mining supply companies (harder to find) | $15-30/kg |
| Sphalerite | ZnS | Zinc | Mineral dealers | $10-20/kg |

For Experiment 1, you only need pyrite. Crush to <2mm grain size (mortar and pestle, rock hammer in a bag, or cheap rock tumbler without media).

### Growth Medium Chemicals (9K Medium)

Per liter of distilled water:

| Chemical | Amount | Common Name | Where to Buy | Cost |
|----------|--------|-------------|-------------|------|
| FeSO4 * 7H2O | 44.22 g | Iron sulfate / copperas | Garden supply, Amazon | $5-10/kg |
| (NH4)2SO4 | 3.0 g | Ammonium sulfate | Fertilizer aisle, Amazon | $8-12/kg |
| KH2PO4 | 0.5 g | Potassium phosphate | Amazon (lab reagent) | $8-12/kg |
| MgSO4 * 7H2O | 0.5 g | Epsom salt | Pharmacy, grocery | $3/kg |
| KCl | 0.1 g | Potassium chloride | Grocery as "salt substitute" (Nu-Salt, NoSalt) | $3 |
| H2SO4 | drops | Sulfuric acid | Pool supply as "pH Down" | $8-15 |

The ferrous sulfate (44g/L) is the bacteria's energy source -- they oxidize Fe2+ to Fe3+ and use the energy to live. Everything else is trace nutrients.

### Equipment

| Item | Cost | Where |
|------|------|-------|
| Glass jar or HDPE bucket (1-2L) | $5 | Any store. NOT metal -- the acid corrodes it |
| Aquarium air pump | $8-12 | Pet store |
| Airstone + tubing | $3-5 | Pet store |
| pH strips (range 0-5) | $8-10 | Amazon |
| Thermometer | $3-5 | Any store |
| Coffee filters or cheesecloth | $3-5 | Grocery |
| Adjustable DC power supply (1-5V, 0-1A) | $30-50 | Amazon, electronics store |
| Graphite rods (electrodes) | $5-10 | Amazon "graphite electrode" or thick mechanical pencil leads |
| Stainless steel plate or copper sheet | $5-10 | Hardware store, Amazon |
| Nitrile gloves | $5 | Hardware store |
| Safety glasses | $5 | Hardware store |
| Baking soda (for spill neutralization) | $2 | Grocery |
| Small digital scale (0.1g precision) | $10-15 | Amazon (for weighing cathode before/after) |

**Total: ~$100-150** for everything.

---

## Experiment 1: Iron from Pyrite (Proof of Concept)

This validates the fundamental chemistry: bacteria eat sulfide rock, electricity makes metal.

### Setup (Day 1)

1. Prepare 1L of 9K medium in a clean glass jar
   - Dissolve chemicals in distilled water in the order listed
   - Add sulfuric acid (pH Down) drop by drop until pH reads 2.0
   - The solution will be pale green (ferrous iron color)

2. Add 50-100g of crushed pyrite (<2mm grain size)

3. Inoculate with A. ferrooxidans culture
   - If from a supplier: follow their instructions, usually pour the whole vial in
   - If from mine drainage: add 50-100mL of the orange water

4. Insert airstone, connect to aquarium pump, turn on
   - The bacteria are aerobic -- they NEED oxygen
   - Gentle bubbling is fine, not vigorous

5. Cover the jar loosely (aluminum foil with holes, or cheesecloth)
   - Needs air exchange but keeps dust/flies out

6. Place somewhere warm (25-30C), away from direct sunlight
   - Room temperature works but is slower
   - An aquarium heater set to 30C in a water bath speeds things up

### Monitoring (Weeks 1-4)

Check every 2-3 days:

| What to Check | How | Expected |
|--------------|-----|----------|
| pH | pH strip | Should stay at 1.5-2.5 (bacteria maintain it) |
| Color | Visual | Pale green -> orange -> dark red-brown over weeks |
| Smell | Careful sniff | Slight sulfurous smell is normal |
| Pyrite surface | Visual | Pitting, surface dulling = bacteria attacking |
| Bubbles | Visual | Fine bubbles from airstone should be steady |

**Signs it's working:**
- Solution turns orange/red (ferric iron Fe3+ accumulating)
- pH stays low without you adding more acid
- Pyrite chunks show surface etching/pitting

**Signs something's wrong:**
- pH rising above 3.0 (bacteria may be dead -- add acid to lower)
- No color change after 2 weeks (inoculation may have failed -- re-inoculate)
- Mold growing on surface (contamination -- start over with sterile jar)

### Harvest & Electrowinning (Week 4-5)

7. Filter the solution through coffee filters into a clean glass container
   - The filtrate (orange/brown liquid) is your pregnant leach solution (PLS)
   - The residue on the filter is spent pyrite and bacterial biomass

8. Set up electrowinning cell:
   - Pour PLS into a clean glass beaker (250-500 mL)
   - Cathode: stainless steel plate or strip, partially submerged
   - Anode: graphite rod, partially submerged, opposite side
   - Connect to DC power supply: cathode to negative, anode to positive
   - Set voltage to 2-3V

9. Wait 1-24 hours
   - Iron deposits as a dark gray/black coating on the cathode
   - You may see small bubbles (hydrogen evolution at cathode -- normal)
   - The solution color may lighten as iron is removed

10. Remove cathode, rinse gently with distilled water, let dry

11. Weigh the cathode (compare to pre-experiment weight)
    - Mass increase = extracted iron
    - Even a fraction of a gram is a valid result

**Congratulations.** Bacteria ate rock. Electricity made metal. This is asteroid mining at tabletop scale.

### Record What You Learn

These observations feed back into the AstraAnt simulator (bioreactor.py):
- How many days until the solution turned orange? (culture lag phase)
- What was the final pH? (steady-state acidity)
- How much mass did the pyrite lose? (dissolution rate)
- How much iron deposited on the cathode? (Faraday efficiency)
- Did the bacteria ever crash? What happened? (failure modes)

---

## Experiment 2: Copper from Chalcopyrite

Same setup as Experiment 1, but add 25-50g of crushed chalcopyrite alongside the pyrite. The bacteria attack both minerals. The PLS now contains Fe2+ AND Cu2+ ions.

### Selective Electrowinning

Copper is more noble than iron (+0.34V vs -0.44V). At low voltage, ONLY copper plates out.

| Voltage | What Deposits | Visual |
|---------|--------------|--------|
| 0.3-0.5V | Copper only | Pink/salmon/orange coating on cathode |
| 0.8-1.2V | Copper + iron | Darker, mixed deposit |
| 2.0-3.0V | Everything | Dark gray/black (mostly iron, some copper) |

**Start at 0.5V.** Watch for the pink copper deposit. This demonstrates selective electrowinning -- voltage controls which metal you extract. This is the same principle the asteroid colony uses.

---

## Experiment 3: Bioleaching Through a Matrix

Replace pure sulfide ore with a mix:
- 70% olivine sand or fine gravel (the gangue -- inert rock matrix)
- 20% crushed pyrite
- 10% crushed chalcopyrite

The bacteria now have to find sulfide grains scattered through non-reactive silicate rock. This tests whether dilution kills the process or just slows it.

**What to compare with Experiment 1:**
- Time to first color change (longer = gangue slows access)
- Final iron/copper yield (lower = some sulfides inaccessible)
- Bacterial growth rate (may be slower in matrix)

---

## Experiment 4: Asteroid Regolith Simulant

C-type asteroid simulant recipe (approximate):

| Component | % | Source |
|-----------|---|--------|
| Olivine sand | 40% | Garden supply "green sand", geological supplier |
| Bentonite clay | 15% | Pottery supply |
| Crushed pyrite | 15% | Mineral dealer |
| Magnetite powder (Fe3O4) | 10% | Amazon "black iron oxide", or beach black sand |
| Serpentine | 10% | Geological supplier |
| Chalcopyrite | 5% | Mineral dealer |
| Garden lime (calcium carbonate) | 5% | Garden supply |

Crush everything to <2mm, mix thoroughly. This gives you a silicate-dominated matrix with sulfide minerals dispersed through it -- roughly analogous to a C-type asteroid.

**Key question this answers:** Does the full mineral complexity inhibit the bacteria? The carbonate (lime) will buffer the pH upward, fighting the acid the bacteria produce. The clay may coat sulfide surfaces, blocking bacterial access. These are real challenges the asteroid colony would face.

---

## Safety Notes

- **pH 1.5-2.5 is like lemon juice to dilute battery acid.** Wear gloves. Wear safety glasses. Keep baking soda nearby to neutralize spills.
- **The bacteria themselves are NOT pathogenic.** They eat rocks, not people. Acidithiobacillus is a rock-munching extremophile, not a disease organism.
- **Ferric iron solution stains EVERYTHING orange.** Permanently. Work on surfaces you don't care about.
- **The electrowinning step uses low voltage/current (2-3V, <1A).** No electrical hazard. A 9V battery with a resistor works in a pinch.
- **Ventilation:** Work in a well-ventilated area. The sulfide oxidation can produce faint sulfurous odor. Not dangerous but unpleasant.
- **DO NOT attempt the PGM/gold track (C. violaceum) at home.** It produces hydrogen cyanide gas, which is lethal. That experiment requires sealed gas-tight reactors and proper lab safety.
- **Disposal:** Neutralize spent solution with baking soda until pH > 6, then it's safe for drain disposal. The bacterial biomass is harmless.

---

## What This Proves

If you successfully extract copper from chalcopyrite via bioleaching and plate it via electrowinning, you have physically demonstrated:

1. Microbial mineral dissolution (bioleaching)
2. Selective metal recovery (electrowinning at controlled voltage)
3. The complete AstraAnt extraction pipeline (minus the sealed PGM step)

Every result directly validates or challenges the simulation parameters in bioreactor.py. Document everything -- times, masses, pH readings, photos. This is the "bridge to reality" that makes the game's outputs real.

---

## Part 2: Electrochemical Metal Printing (The Press Demo)

No bacteria needed. Proves patterned metal deposition in an afternoon.

### Prior Art

This has been done by hobbyists and academics. You're not inventing from scratch:
- CNC electroforming machines on Hackaday.io (cheap 3018 CNC + nickel anode)
- Ender 3 converted to electrochemical machine (Hackaday, 2021)
- Desktop multi-metal electrochemical 3D printer (Nature Scientific Reports, 2019)
- Microfluidic fountain pen systems achieving 6 um/s deposition (academic, 2020)

Compared to powder sintering (needs lasers, argon atmosphere, explosive metal powder),
electrochemical deposition needs a glass jar, copper sulfate, and a battery.

### Level 1: Hand-Held Wire Demo (5 min, ~$10)

Proves localized electrodeposition with zero equipment:

1. Glass jar half-full of copper sulfate solution (root killer + water)
2. Small steel object inside (bolt, washer, key) wired to NEGATIVE terminal
3. Copper wire in your hand, wired to POSITIVE terminal
4. Apply 2-3V from any DC source (bench supply, battery + resistor)
5. Touch the wire tip near the steel surface, move slowly across
6. Pink copper trail appears where the wire passed

You just "painted" copper onto steel with electricity.

### Level 2: Glass Dish Printer (afternoon, ~$25-35 add-on)

The proper demo. Small constrained working area, CNC-controlled.

Parts (assuming you already have a 3D printer + bioleaching power supply):

| Item | Cost | Source |
|------|------|--------|
| Blunt syringe needles (14ga) | $5 | Amazon (nozzle) |
| 0.5mm copper wire (spool) | $5 | Hardware/craft store (anode filament) |
| Small peristaltic pump or syringe | $10-15 | Amazon (electrolyte delivery) |
| Silicone tubing (2-3mm ID) | $5 | Amazon |
| Small glass dish / Pyrex pan | $5 | Any store (3x3 inch working area) |
| Small steel or copper plate | $5-10 | Hardware store (cathode/build plate) |

Setup:

    [3D printer gantry, modified to hold nozzle]
            |
        [syringe needle with copper wire through center]
            |
    ~~~~copper sulfate solution (1-2cm deep)~~~~
        [steel plate (cathode, wired to negative)]
    [glass dish sitting on printer bed]

Process:
1. Cut steel plate to fit glass dish, wire to negative terminal
2. Fill dish with copper sulfate solution (~1-2cm depth)
3. Thread copper wire through syringe needle (wire = anode, needle = guide)
4. Mount needle where the hot end was on your printer
5. Connect copper wire to positive terminal
6. Position wire tip ~0.5-1mm above the steel surface
7. Run G-code at VERY slow speed (F30-F60, i.e. 0.5-1mm/s)
8. Apply 0.3-1.0V (start low for smooth deposit)
9. Watch: copper traces appear on the steel plate matching the toolpath

For sharper lines: sheath the wire in heat-shrink tubing, expose only the last
1-2mm of tip. This concentrates current to a smaller spot.

Electrical contact to the wire: do NOT use an alligator clip (needs constant
repositioning as wire feeds). Use a brass tube (2mm ID, 10-20mm long) that
the wire threads through. Solder the positive lead to the outside of the tube.
The wire slides through with continuous contact. Same principle as a MIG welder
contact tip. Brass tube from hardware/hobby shop, ~$2.

    Wire from spool
        |
    [brass tube, soldered to positive lead]
        |
    [PTFE tube / heat-shrink (insulating guide)]
        |
    [exposed wire tip, last 2-3mm]
        |
    ~~electrolyte~~

Voltage guide:
- 0.1-0.3V: smooth, shiny deposit, slow (30-60 min for visible result)
- 0.5-1.0V: matte deposit, faster (5-15 min visible)
- 2.0-3.0V: rough/powdery but very fast (1-5 min visible)

### Level 3: Submerged Tank with Multi-Axis Head ($50-100)

The full concept: 5-DOF print head operating underwater.

Additional parts:

| Item | Cost | Source |
|------|------|--------|
| Small glass aquarium or large jar | $10-20 | Pet store |
| Hobby servos (waterproof SG90s) | $15-20 | Amazon (for multi-axis arm) |
| 3D printed arm linkages (PETG) | ~$5 filament | Print yourself |
| Arduino Nano | $5-10 | Amazon (arm controller) |

The head operates fully submerged. Advantages:
- No fluid management (everything is already wet)
- Head can approach from any angle (vertical walls, overhangs)
- The print head can deposit on existing objects (put a bolt in the tank,
  deposit reinforcement on stress points)

For 3D structures: each deposited layer becomes part of the cathode,
so subsequent layers deposit on top. Build upward layer by layer,
exactly like plastic 3D printing but with real metal.

### Level 4: Multi-Metal Patterned Deposition

Once Level 2 works with copper:
1. Deposit copper pattern (copper sulfate, 30 min)
2. Rinse build plate thoroughly
3. Swap electrolyte to nickel sulfate solution
4. Run a DIFFERENT toolpath
5. Deposit nickel in a different pattern (30 min)
6. Result: copper traces + nickel traces, different locations, same build plate

This demonstrates the multi-metal architectured material concept from the
asteroid colony design. Two metals, two patterns, one part.

### What This Proves

At Level 2, you've demonstrated:
- Localized electrodeposition with a moving electrode (the press concept)
- CNC-controlled metal patterning from electrolyte
- The "electrochemical pen" approach proven in published research
- Pattern quality vs. gap distance (try different tip heights)

Combined with the bioleaching experiments: bacteria eat rock -> dissolved metal
ions -> patterned deposition -> multi-metal part. The full asteroid-to-structure
pipeline on a kitchen table.

### Single-Bath Multi-Metal: No Fluid Changes Needed

You don't need separate electrolytes for each metal. The sacrificial anode wire
supplies all the metal ions on demand. The bath is just the highway.

**Starting bath:** Distilled water + sulfuric acid (pH 2). No metal salts.

When you feed copper wire and apply current, copper dissolves from the wire,
travels through the acid bath, and deposits on the build plate. Switch to
nickel wire = nickel deposits. The bath composition adjusts dynamically.

**Wire swap approach (simplest):**
- One nozzle, swap wires manually between layers (10 seconds)
- Copper wire for copper traces, nickel wire for nickel, iron wire for iron
- Same bath throughout

**Multi-wire nozzle (automated):**
- Multiple wires through adjacent nozzles, one active at a time
- Arduino + MOSFET selects which wire is energized
- G-code triggers wire switching
- Like a multi-filament 3D printer (Prusa MMU) but for metals

**Voltage per metal (approximate, at cathode vs. the wire anode):**
- Copper: 0.3-0.5V (deposits first, most noble)
- Nickel: 0.8-1.2V
- Iron: 1.0-1.5V
- Zinc: 1.3-1.8V

**Cross-contamination management:**
When switching from copper to nickel, residual Cu2+ in the bath will co-deposit
briefly (copper is more noble -- it always wants to plate). Solutions:
- Run a brief "scavenging" pass at copper voltage to deplete residual Cu2+
- Or accept the thin copper flash layer (negligible for structural parts)
- Or use a very small bath volume where residual ions are minimal
- In the scanning head setup, the wire tip is so close to the cathode (0.5mm)
  that local chemistry is dominated by the active wire anyway

**Updated minimal shopping list (multi-metal printer, no metal salts needed):**

| Item | Cost | Source |
|------|------|--------|
| Sulfuric acid (pool pH-Down) | $8-15 | Pool supply (the only bath chemistry) |
| Copper wire (0.5-1mm) | $5 | Hardware store |
| Nickel wire (0.5mm) | $8 | Amazon "pure nickel wire" |
| Iron/steel wire | $3 | Hardware store |
| Zinc wire (optional) | $8 | Amazon |
| Distilled water | $2 | Grocery |
| Glass dish + steel build plate | $10 | Any store + hardware store |
| DC power supply (adjustable) | already have | From bioleaching kit |
| **Total** | **~$35-45** | For multi-metal capability |

This is cheaper than the metal sulfate approach AND gives unlimited supply
(wire lasts much longer than dissolved salts in a small bath).

### Multiple Print Heads (Parallelization)

Multiple wire tips can operate simultaneously in the same bath without
interference, as long as they're spaced at least 3-5x the tip-to-surface gap
apart (~3-5mm at typical 1mm working height).

Configurations:
- Same metal, same object: N tips = Nx throughput. Share one power supply.
- Different metals, same object: each tip dominates local ion chemistry.
  Needs separate power supply channels (different voltages per metal).
- Different metals, different objects: cleanest. Each object is a separate
  cathode. Each head+cathode pair is an independent circuit.

Watch out: if two heads at DIFFERENT voltages share the SAME cathode (build
plate), the higher-voltage head drives background current everywhere. Fix:
use separate cathode plates for different metals, or same voltage for all
active heads.

The practical limit is mechanical (fitting heads on the gantry), not
electrical. For a 3x3 inch dish, 2-3 heads max before it gets crowded.

### Covered Anodes for Tank Setups

For stationary tank applications (I-beam pulling, ring spinning) where the
anode is separate from the print head:

- Multiple anode rods (Cu, Ni, Fe, Zn) mounted in the tank
- Each rod has a sliding insulating sleeve (heat-shrink tubing, rubber)
- Expose only the active anode, keep others covered
- Motorize the sleeves with servos for automatic switching
- Add a "scavenging step" between switches: briefly run cathode at the previous
  metal's voltage to deplete residual ions from the bath before switching

This approach works for any tank-based electroforming where the anode isn't
part of the scanning head assembly.

### References

- Hackaday: Low Cost Metal 3D Printing By Electrochemistry (2021)
- Hackaday.io: CNC Electroforming Machine project
- Nature Scientific Reports: Multi-metal 4D printing with desktop electrochemical
  3D printer (2019)
- Nature Communications: Selective Co/Ni electrodeposition for battery recycling
  via electrolyte and interface control (2021)
- University of Cincinnati: Electrochemical Additive Manufacturing (ECAM) lab
- Crystals journal: Low-Cost Electrochemical Metal 3D Printer Based on a
  Microfluidic System (2020)
