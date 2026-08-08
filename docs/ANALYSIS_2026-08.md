# Analysis Notes — August 2026

Session topic: minimum-budget mission framing ("free launch" thought exercise),
close-approach target survey 2026-2046, and a competitive landscape check.

## 1. The free-launch budget exercise

Premise: launch cost is zero (hypothetical rideshare prize). What remains?

Key conclusion: **launch was never the dominant cost at this scale.** A
rideshare slot is $1-3M; the scraped budget for everything else:

| Prize class | Mission | Out-of-pocket |
|---|---|---|
| 6U-12U CubeSat | Prospector scout (rendezvous + survey, no landing) | ~$700K-1.5M |
| ESPA (~120-180 kg) | Minimum viable lander (drill, anchor, solar, comms, ~10 ants) | ~$2.5-6M |

Line items (ESPA case): bus + lander hardware $800K-2M; final-leg ion
propulsion $150-300K; deep-space comms + ground time $300-600K (the sneaky
one — DSN is scarce, university dish partnerships are the beg/borrow move);
rad-tolerance + testing $100-300K; licensing/integration $100-200K;
3-5 years of solo ops $150-400K.

Claim-tier discipline: this budget buys the toehold and the dataset, NOT
break-even. One seed ship's deliverable water to cislunar over 5 years only
matters if a propellant-depot buyer exists on arrival. The honest pitch is
that proven anchoring + digging + water recovery on a real NEA is worth more
in the follow-on round than the water itself.

Target correction: "asteroid belt" does not close on this budget (solar at
2.9 AU = 12% of 1 AU, +3-5 km/s, multi-year transit). NEAs are the game.

## 2. Close-approach survey 2026-2046 (data-driven, 2026-08-07)

Method: JPL CNEOS close-approach API (dist < 0.05 AU, H < 22, i.e. >~140 m)
cross-referenced with NHATS accessible-target list. 400 objects returned.

**The physics point: miss distance is not the cost — relative velocity is.**
1999 AN10 passes at 1.0 LD in Aug 2027 but at 26 km/s: unreachable. What a
close approach DOES buy:

1. It marks the cheap transfer epoch (orbits nearly intersect); miss it and
   the synodic wait is often 7-15 years.
2. Near-real-time supervised autonomy during landing/anchoring (light-seconds
   vs tens of minutes) — a major de-risk for a shoestring mission.
3. Cargo return: yeet pods during the NEXT approach; the asteroid delivers
   your product to cislunar for near-zero delta-v. Materially improves the
   ~80%-stranded micro-pod economics.

Shortlist (best rendezvous-capable approaches in window):

| Object | Approach | Miss | v_rel | Size | NHATS dv |
|---|---|---|---|---|---|
| Apophis | 2029-04-13 | 0.10 LD | 7.4 | 340 m | 6.0 |
| 2006 SU49 | 2029-01-28 | 3.2 LD | 4.9 | ~470 m | 9.3 |
| Ryugu (catalog) | 2033-12-21 | 18.5 LD | 4.1 | 896 m | 8.2 |
| 2000 QK130 | 2036-03-15 | 4.4 LD | 7.6 | ~192 m | 8.3 |
| 2008 EV5 (catalog) | 2039-12-28 | 18.9 LD | 4.2 | 400 m | 6.3 |
| 2011 DV | 2040-04-24 | 5.5 LD | 5.5 | ~247 m | 6.6 |

Feasibility-grade picks: Ryugu 2033 and 2008 EV5 2039 (C-type, catalog,
ground-truth composition). Apophis 2029 is the PR/timeline play but S-type
(weak water) and needs a ~2027-28 launch. The three non-catalog candidates
were added to `catalog/asteroids/` with honestly-flagged unknown composition.
Bennu's big approach (2054/2060) falls outside the window.

## 3. Competitive landscape (checked 2026-08)

The dominant real-world architecture has converged on exactly our
feasibility tier's shape: <$10M small spacecraft, rideshare launch,
prospect-first.

- **AstroForge**: M-type PGM play, ~$55M raised. Odin (Feb 2025) lost ~20h
  after launch; Vestri (200 kg, electric propulsion, first private asteroid
  landing attempt) stated Q4 2026. Sells PGMs to the terrestrial market —
  opposite of our water-first-to-cislunar thesis.
- **Karman+**: $20M seed, "COTS+" <$10M missions. High Frontier demo (LEO
  rideshare, self-propelled to NEA, ~1 kg regolith excavation) slipped to
  Feb 2027. Water-for-refueling thesis = closest to ours; no named customer.
- **TransAstra**: capture-bag whole-asteroid retrieval to lunar orbit +
  optical mining. 1-m bag demo'd on ISS Oct 2025; asteroid mission 2028-29
  only "if funded." Nearer-term revenue is debris capture.
- **ExLabs**: pivoted toward deep-space rideshare/science prime. ApophisExL
  launches 2028 for the Apr 2029 flyby — validates our Apophis-window logic;
  they sell the ride, not the rock.
- **Interlune** (lunar He-3): the only player with a SIGNED government buyer
  (US DOE, 3 L He-3 by Apr 2029). Proves the pattern we assume: anchor
  customer first, then extraction. Nobody has that for asteroid water yet.
- **Origin Space** (China): quiet since 2021; state Tianwen-2 (launched May
  2025, to Kamo'oalewa) is the active Chinese thread.
- Historical: Planetary Resources sold for parts (2018), DSI absorbed by
  Bradford (2019). The 2010s bubble postmortem still applies: no customer,
  no mission, no company.

Implications for AstraAnt:
- Odin's <1 day loss supports our high spacecraft-loss assumptions
  (CubeSat failure rate 5-10% was, if anything, optimistic for deep space).
- Nobody is doing swarm/colony architecture — everyone flies one precious
  spacecraft. Our redundancy thesis remains undefended territory.
- The missing piece industry-wide is the buyer, not the tech. Interlune's
  DOE deal is the template: our economics should model an anchor-customer
  contract as the revenue trigger, not spot-market water sales.
