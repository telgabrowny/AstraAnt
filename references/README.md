# AstraAnt External References

Archival copies of external research we might want to cite or build on, in case the original sources go dark.

## Harvard RAnts / photormones (Mahadevan lab)

Ant-inspired swarm that builds and excavates via "photormone" light-field stigmergy.
The same swarm switches between construction and deconstruction by tuning just two parameters
(cooperation strength + deposition rate). Peer-reviewed in PRX Life, 2026.

**Why this is here:** candidate algorithmic foundation for AstraAnt swarm coordination.
Photormones (light fields) work in vacuum / microgravity where chemical pheromones don't,
and the build/excavate mode switch matches AstraAnt's Phase 1 → Phase 2 lifecycle.
See `~/.claude/.../memory/reference_harvard_rants_photormones.md` for the full writeup.

### What's archived here

| File | Source | Size |
|---|---|---|
| `giardina_2022_collective_phototactic_robotectonics.pdf` | [arXiv 2208.12373](https://arxiv.org/abs/2208.12373), CC BY-4.0 | 6.7 MB |
| `harvard_rants_dryad/Code_zenodo.zip` | [Zenodo 10747067](https://zenodo.org/records/10747067) | 136 KB |
| `harvard_rants_dryad/Code_extracted/` | unpacked copy of the above (readable in-place) | — |

The Arduino firmware covers five behaviors — **Construction**, **De-Construction**,
**No Gradient descent**, **no Thresholding**, **Pseudocode** — with `base.ino` plus per-robot
customized routines for `rant1`..`rant7`.

### Not archived (Dryad-only)

The **Dryad dataset** ([doi:10.5061/dryad.05qfttfb2](https://datadryad.org/dataset/doi:10.5061/dryad.05qfttfb2))
includes a few pieces not mirrored to Zenodo:

- **MATLAB** agent simulation (the one we'd most want to port to Python for AstraAnt)
- **Mathematica** notebooks for asymptotic analysis of self-trapping instability
- Figure data (`.txt` / `.csv`) + Python plotting notebook
- Original README

Dryad sits behind an Anubis JS proof-of-work challenge, so automated fetches are blocked.
Total is ~8.75 MB — download via browser and drop `Figs.zip` into `harvard_rants_dryad/`
whenever convenient.

### Related reading

- [Harvard SEAS press release](https://seas.harvard.edu/news/simple-robots-collectively-build-and-excavate-are-inspired-ants)
- [eLife 2022 companion paper on cooperative excavation](https://elifesciences.org/articles/79638)
- PRX Life paper DOI: [10.1103/cx3h-bwhc](https://journals.aps.org/prxlife/abstract/10.1103/cx3h-bwhc)
- Authors: Fabio Giardina, S. Ganga Prasath, L. Mahadevan (Harvard SEAS)
