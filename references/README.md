# AstraAnt External References

Archival copies of external research we might want to cite or build on, in case the
original sources go dark.

## Harvard RAnts / photormones (Mahadevan lab)

Ant-inspired swarm that builds and excavates via "photormone" light-field stigmergy.
The same swarm switches between construction and deconstruction by tuning just two
parameters (cooperation strength + deposition rate). Peer-reviewed in PRX Life, 2026.

**Why this is here:** candidate algorithmic foundation for AstraAnt swarm coordination.
Photormones (light fields) work in vacuum / microgravity where chemical pheromones don't,
and the build/excavate mode switch matches AstraAnt's Phase 1 → Phase 2 lifecycle.
See `~/.claude/.../memory/reference_harvard_rants_photormones.md` for the full writeup.

### What's archived

| File / folder | Source | Size |
|---|---|---|
| `giardina_2022_collective_phototactic_robotectonics.pdf` | [arXiv 2208.12373](https://arxiv.org/abs/2208.12373), CC BY-4.0 | 6.7 MB |
| `harvard_rants_dryad/arxiv_source.tar.gz` | arXiv source tarball: LaTeX + 14 figure PNGs (incl. `Exploded_Rant.png`) + `references.bib` | 7.1 MB |
| `harvard_rants_dryad/Code_zenodo.zip` + `Code_extracted/` | [Zenodo 10747067](https://zenodo.org/records/10747067), MIT | 136 KB |
| `harvard_rants_dryad/doi_10_5061_dryad_05qfttfb2__v20240330.zip` | [Dryad dataset](https://datadryad.org/dataset/doi:10.5061/dryad.05qfttfb2), full sealed bundle | 8.4 MB |
| `harvard_rants_dryad/Dryad_extracted/` | readable copy of the Dryad contents (Figs/ + README) | — |

The Arduino firmware covers five behaviors — **Construction**, **De-Construction**,
**No Gradient descent**, **no Thresholding**, **Pseudocode** — each with `base.ino`
plus per-robot customized routines for `rant1`..`rant7`.

The Figs folder has all plotting data + a Python notebook (`Figs.ipynb`) used to
generate every figure in the paper, plus frame PNGs from the construction and
deconstruction experiments.

### Known gap: Self-Trapping folder

Dryad's own README describes a third folder called `Self-Trapping/` containing:
- **MATLAB** agent simulation (finite-difference agent following its photormone trail)
- **Mathematica** notebooks for asymptotic analysis of self-trapping instability

**This folder is NOT in the Dryad upload** despite being documented — the sealed
Dryad bundle above only contains `Figs.zip` + `README.md`. The Arduino code is
mirrored separately on Zenodo (already archived here); the MATLAB sim and Mathematica
analysis appear to be unpublished outside of the paper's supplementary description.

If we ever want to port the agent sim to Python for AstraAnt, options are:
- Email the authors (Fabio Giardina, S. Ganga Prasath) and ask for the `Self-Trapping/`
  files directly
- Re-implement from the paper's mathematical description (the finite-difference scheme
  for photormone-following is described in the main text and SI)

### Related reading

- [Harvard SEAS press release](https://seas.harvard.edu/news/simple-robots-collectively-build-and-excavate-are-inspired-ants)
- [eLife 2022 companion paper on cooperative excavation](https://elifesciences.org/articles/79638)
- PRX Life paper DOI: [10.1103/cx3h-bwhc](https://journals.aps.org/prxlife/abstract/10.1103/cx3h-bwhc)
- Authors: Fabio Giardina, S. Ganga Prasath, L. Mahadevan (Harvard SEAS)
