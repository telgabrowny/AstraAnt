# From Your Desk to Space: The Real Roadmap

Everything -- the nautilus station, the WAAM bots, the processing cascade, the tugs -- rests on **three unproven mechanisms**. If these three work in space, everything else is engineering. Your CubeSat must prove all three.

1. **Bioleaching in microgravity** on real asteroid-composition rock (never tested in space)
2. **Iron electroforming** from acid solution onto surfaces in microgravity (never tested)
3. **WAAM wire-arc deposition** in vacuum with a moving print head (welding in vacuum is proven; wire feed to a bot is not)

---

## Phase 0: Earth Prototyping (6-12 months, $2-5K)

Your kitchen table and a 3D printer.

- 3D print the printer bot chassis (`scad/printer_bot.scad` already exists)
- Install real SG90 servos ($0.30 each), test 8-leg gait on your desk
- Buy *A. ferrooxidans* culture (ATCC 23270, ~$300 from a culture collection)
- Buy meteorite chips (NWA L-chondrite, ~$50/100g on eBay) -- identical mineralogy to asteroid regolith
- Set up a bioleaching jar: dilute sulfuric acid + bacteria + ground meteorite chips
  - Watch iron dissolve over 30-90 days
  - Measure pH, color change, iron concentration with a $30 test kit
  - **This is a high school science fair level experiment**
- Build a small electroforming rig: 9V battery + copper wire cathode in the bioleaching solution
  - Does iron plate onto the wire? If yes, you just proved the core mechanism.
- Get a cheap MIG welder ($150). Test wire-arc deposition on an iron plate.
  - Can you deposit a bead while moving the torch slowly? That is literally WAAM.
- Film everything. This is your proof of concept portfolio.

**Total cost: $500-2000.** Mostly stuff you can find at a hardware store.

---

## Phase 1: Vacuum + Controlled Testing (3-6 months, $2-5K)

- Build or rent a bell jar vacuum chamber (~$500 used on eBay)
  - Or partner with a local university physics department (free, plus academic credibility)
- Test WAAM in vacuum: wire + arc in the bell jar
  - Should work BETTER than air (no oxidation, cleaner weld bead)
- Test SG90 servo in vacuum (lubricate with Braycote 601 vacuum grease, $30)
  - Stock SG90 lubricant outgasses in vacuum. Braycote fixes this.
- Test bacteria survival: sealed vial, exterior exposed to vacuum + thermal cycling
  - Bacteria are inside the pressurized bag, never touch vacuum
  - But thermal cycling (-40C to +60C exterior) affects interior temperature
- Test electroforming in a sealed container (simulates the membrane bag)
- Test Kapton membrane material: fold/unfold cycles, check for cracking
  - Kapton film from Amazon: $20/roll. Practice folding and deployment.

---

## Phase 2: Microgravity Testing (optional but highly valuable, $5-15K)

Even 30 seconds of microgravity data is worth more than any simulation.

- **Option A**: Zero-G Corp parabolic flight (~$8K/seat, 30 sec microgravity x 15 parabolas)
  - Bring: sealed bioleaching vial, small electroforming cell
  - Question answered: does acid solution slosh? Does iron plate evenly?
- **Option B**: NASA Flight Opportunities program (free if accepted, competitive)
  - Suborbital rocket flight. More microgravity time. Takes 6-12 months to apply.
- **Option C**: University drop tower (free, 2-5 seconds of microgravity)
  - Less time but zero cost. Good for fluid behavior observations.

---

## Phase 3: CubeSat Build (12-18 months, $30-80K)

### Option A: Proof-of-Concept (RECOMMENDED FIRST)

A 6U CubeSat (12 kg, ~$150K total including launch). No asteroid rendezvous needed.

**Payload:**
- Sealed bioleaching cell: ground meteorite + acid + bacteria + heater + thermocouple
- Electroforming cell: acid solution + cathode wire + power supply
- WAAM test coupon: small wire feed mechanism + arc tip + iron plate target
- Temperature control: bimetallic thermostat + nickel heater (the relay life support)
- Three ESP32-S3 (TMR redundancy) + UHF radio
- Deployable solar panels (2 m2)
- No ion engine, no membrane, no arms. Just the three experiments.

**Mission profile:**
- Launch to LEO on SpaceX Transporter rideshare ($60-120K)
- Deploy, establish radio contact via SatNOGS ground network
- Heat bioleaching cell to 30C, start bacteria, monitor for 90 days
- Run electroforming cell, measure iron deposition rate
- Fire WAAM arc, deposit one test bead, photograph result
- Downlink all data via UHF

**If all three mechanisms work: you have proof for the full mission.**

Cost breakdown:
- CubeSat structure + avionics: $10-20K (using COTS CubeSat kits)
- Custom payload (3 experiment cells): $10-30K
- Solar panels + power system: $5-15K
- Radio + ground station: $2-5K (SatNOGS network is free)
- Integration + testing: $5-10K
- Launch: $60-120K
- **TOTAL: $99-225K**

### Option B: Full Seed Mothership (after Option A proves the concept)

The 41 kg, $654K package we've been designing. Ion engine to a NEA. Membrane. Arms. WAAM heads. Bacteria. The real thing.

Only do this after Option A proves the three mechanisms work.

---

## Phase 4: Launch (6-12 months lead time)

**Rideshare providers (current pricing, will likely decrease):**
- SpaceX Transporter (LEO/SSO): ~$5K/kg, launches every 3-4 months
- RocketLab Electron (LEO): ~$7K/kg
- For NEA mission (Option B): GTO rideshare + ion engine, ~$10K/kg

**Ground station:**
- SatNOGS network: free, global coverage, community-operated
- Your own station: RTL-SDR dongle ($30) + Yagi antenna ($80) + laptop
- Mission control: the AstraAnt CLI already does the orbital calculations

---

## Phase 5: Operations + Growth

**If proof-of-concept (Option A):**
- Publish results in a peer-reviewed journal (astrobiology + materials science)
- File provisional patents on the bioleaching-in-space process
- Use results to fund Option B (NASA SBIR Phase II, investors, ESA)
- Your CubeSat data is worth more than the hardware

**If full seed (Option B):**
- Year 0-1: Approach NEA, capture rock, deploy membrane
- Year 1-3: Bioleach, electroform, build first WAAM bots
- Year 3-5: Wire factory, bot fleet, shell growth
- Year 5-8: Local solar cells from waste silicon
- Year 8-15: Processing cascade, multiple chambers, near-independence
- Year 15+: Self-sustaining. $50K/5yr maintenance CubeSats.

---

## What Ensures Success

1. **Test on Earth first.** The #1 CubeSat failure mode is untested hardware. If it works in your kitchen, it will probably work in LEO. If it doesn't work in your kitchen, it will NOT work in LEO.

2. **Two of everything critical.** 2x ESP32, 2x radio, 2x experiment cells. One failure must not kill the mission.

3. **Simple operations first.** Step 1: radio link. Step 2: read sensors. Step 3: heat the cell. Step 4: start bacteria. Step 5: electroforming. Step 6: WAAM. Each step validates the next.

4. **Graceful degradation.** If WAAM fails, bioleaching + electroforming still proved. If electroforming fails, bioleaching still proved. If bioleaching fails, you learned WHY (fluid dynamics data). Every failure mode produces publishable science.

5. **Telemetry over action.** Send data home before every irreversible step. Do not start bioleaching until you have 48 hours of thermal data confirming temperature control works.

6. **Start with meteorite, not asteroid.** For the proof-of-concept CubeSat: bring ground meteorite from Earth. Identical mineralogy. No need to rendezvous with an asteroid until the full mission. Just prove the chemistry works in microgravity.

---

## The Pitch

For grants, crowdfunding, or investors:

> We are testing whether bacteria can mine asteroids.
>
> The biology is proven on Earth -- bioleaching is a $20 billion industry used in copper and gold mining worldwide. The question is: does it work in microgravity?
>
> For $150K, we fly a sealed bioleaching experiment to LEO on a CubeSat. 90 days. Three mechanisms tested: bioleaching, electroforming, and wire-arc manufacturing.
>
> If it works, the path to self-replicating asteroid mining opens up -- starting from a 41 kg seed package that grows itself into a permanent space station.
>
> Every gram of material produced in space is a gram that doesn't need to be launched from Earth at $2,700/kg. The economics are inevitable. The only question is whether the biology cooperates in space.
>
> Our CubeSat answers that question.

This pitch works for:
- **NASA SBIR Phase I** ($275K, exactly this scope)
- **NSF grants** (astrobiology + materials science crossover)
- **Kickstarter/crowdfunding** ($150K is achievable for space projects)
- **ESA, JAXA, CSA** equivalent programs
- **Angel investors** (show the 50-year revenue model from the sousvide sim)

---

## Cost Summary

| Phase | What | Cost | Timeline |
|-------|------|------|----------|
| 0 | Earth prototyping | $2-5K | 6-12 months |
| 1 | Vacuum testing | $2-5K | 3-6 months |
| 2 | Microgravity testing | $5-15K (optional) | 1-2 days |
| 3A | Proof-of-concept CubeSat | $30-80K | 12-18 months |
| 4A | Launch (LEO rideshare) | $60-120K | 6-12 months |
| **TOTAL (proof of concept)** | **Prove the 3 mechanisms** | **$99-225K** | **2-3 years** |
| 3B | Full seed mothership | $246K hardware | 12-18 months |
| 4B | Launch (GTO rideshare + ion) | $400K | 6-12 months |
| **TOTAL (full mission)** | **Self-replicating mining** | **$654K** | **3-4 years** |

Phase 0 starts tomorrow for the cost of a bacteria culture and some meteorite chips.
