# AstraAnt — Colony Walkthrough (web)

`colony_walkthrough.html` is a **self-contained** first-person render of a completed
subsurface tunnel colony — a "walk the finished dig" survey built to the blueprint /
schematic aesthetic. Open it in any browser; click to enter, then WASD + mouse to walk.
No server, no network (Three.js is inlined), works offline.

## What you walk through
- **Surface canopy / airlock** — deployable origami dome, mud-sealed entry
- **Tunnel backbone** — iron U-channel ribs, rail line, slag-glass floor, low-pressure seal
- **Clean lab (0.05 g)** — the original workshop dome + EM press with glowing deposition coils
- **Bio-chamber** — 200–500 L bioleach reactors glowing green
- **Carnival centrifuge** — locally-built track-and-wheel, the 0.1–0.2 g heavy-industry floor
- **Mine face** — the advancing dig with ore stockpiles

Worker ants (orange) ride the backbone rail; a taskmaster (blue) works the clean lab.
The HUD reads zone / pressure / spin-gravity / depth / seal, updating as you cross
between chambers.

## Build
The published file is assembled from `src/`:

```sh
cd web
{ cat src/head.html; printf '\n<script>\n'; cat src/three.min.js; \
  printf '\n</script>\n<script>\n'; cat src/scene.js; printf '\n</script>\n'; } \
  > colony_walkthrough.html
```

- `src/head.html` — page shell: styles, HUD overlay, start card (no `<html>/<head>/<body>`)
- `src/scene.js` — the colony geometry, ants, pointer-lock FPS controls, HUD wiring
- `src/three.min.js` — Three.js r128 (vendored so the build reproduces offline)

Respects `prefers-reduced-motion` (disables ant/centrifuge motion and head-bob).
This is a standalone render, not the Ursina game GUI — the game engine lives in
`astraant/gui/`.
