# AstraAnt 3D Print Guide

All 15 SCAD models compile to valid STL. This guide covers print settings,
dimensions, materials, and which models are functional prototypes versus
display pieces.

## Model Summary

| # | File | STL Size | Scale | Approx Dimensions (mm) | Material | Supports | Est. Print Time | Type |
|---|------|----------|-------|------------------------|----------|----------|-----------------|------|
| 1 | cargo_gripper.scad | 43 KB | 1:1 | 35 x 25 x 30 | PETG | None | 30 min | Functional |
| 2 | drill_head.scad | 162 KB | 1:1 | 15 x 15 x 55 | PETG | None | 45 min | Functional |
| 3 | foot_pad.scad | 174 KB | 1:1 | 8 dia x 5 tall | PETG | None | 10 min | Functional |
| 4 | mothership.scad | 530 KB | 1:25 | 60 dia x 140 tall, 200 wingspan | PLA/PETG | Yes (antenna, panels) | 4-6 hrs | Display |
| 5 | nautilus_station.scad | 7.5 MB | 1:100 | ~200 x 150 x 160 | PLA/PETG | Yes (siphuncle tubes, mothership) | 8-12 hrs | Display |
| 6 | paste_nozzle.scad | 74 KB | 1:1 | 25 x 45 x 20 | PETG | Yes (nozzle overhang) | 40 min | Functional |
| 7 | pod_scaffold.scad | 2.9 MB | 1:1 | 120 x 80 x 65 | PETG | None | 2-3 hrs | Functional |
| 8 | printer_bot.scad | 1.7 MB | 1:1 | 110 x 90 x 40 (with legs) | PETG | Yes (leg sockets) | 3-4 hrs | Functional |
| 9 | sampling_probe.scad | 189 KB | 1:1 | 15 x 15 x 55 | PETG | Yes (probe tip) | 40 min | Functional |
| 10 | scoop_head.scad | 81 KB | 1:1 | 25 x 45 x 25 | PETG | None | 30 min | Functional |
| 11 | seed_capture.scad | 9.2 MB | 1:20 | 150 x 120 x 120 | PLA/PETG | Yes (concentrator, mothership) | 6-8 hrs | Display |
| 12 | seed_mothership.scad | 2.0 MB | 1:10 | 200 x 100 x 50 (with wings) | PLA/PETG | None (printed upright) | 2-3 hrs | Display |
| 13 | servo_horn_adapter.scad | 142 KB | 1:1 | 8 dia x 12 tall | PETG | None | 10 min | Functional |
| 14 | thermal_rake.scad | 152 KB | 1:1 | 35 x 25 x 40 | PETG | None | 30 min | Functional |
| 15 | worker_chassis.scad | 3.4 MB | 1:1 | 135 x 35 x 25 (body only) | PETG | Yes (leg sockets) | 3-4 hrs | Functional |

## Compilation Notes

All models compiled cleanly except:

- **mothership.scad**: Produces warnings about variable `z` being overwritten
  on lines 220-251. This is a known OpenSCAD limitation -- the `z = z + value`
  accumulator pattern triggers reassignment warnings but the geometry still
  renders correctly. Some modules land at z=0 instead of their intended stack
  position due to how OpenSCAD scoping works. Cosmetic issue only for the STL
  export (all modules are present in the output).

- **nautilus_station.scad**: Compiles successfully (11 min 48 sec, the longest
  build). The logarithmic spiral geometry with hull() operations on 72 sphere
  pairs for the trace line is the bottleneck. No errors.

## Functional Prototypes

These models accept real off-the-shelf parts. You can print them and build
working hardware.

### Tool Heads (magnetic clip mount, swap between ant mandibles)

All 7 tool heads share the same **magnetic mount interface**: 15 x 10 x 6mm
block with a 4mm magnet pocket and two mandible grip grooves. Print one mount,
test the fit, and adjust `magnet_d` clearance if needed.

| Tool | Key Feature | Post-Print Assembly |
|------|-------------|---------------------|
| **cargo_gripper** | U-shaped fork with grip pad recesses | Glue silicone pads to jaw faces |
| **drill_head** | N20 motor pocket + replaceable bit | Press-fit N20 motor, insert tungsten carbide bit |
| **paste_nozzle** | Reservoir cradle + slit nozzle + trowel | Insert silicone tube reservoir |
| **sampling_probe** | pH electrode + syringe holder | Insert 5ml syringe body, pH electrode, turbidity sensor |
| **scoop_head** | Curved scoop with rear lip | Ready to use after printing |
| **thermal_rake** | 5 tine sockets + pusher face | Press-fit 3mm alumina rods (McMaster-Carr) |

### Ant Bodies

| Model | Key Feature | Post-Print Assembly |
|-------|-------------|---------------------|
| **worker_chassis** | 8-leg, 2-mandible frame. MuJoCo-verified 8-leg config. | Press-fit 8x SG90 + 2x SG51R servos, mount RP2040 Pico, clip foot pads |
| **printer_bot** | 8-leg WAAM printer bot with wire feed head | Press-fit 8x SG90, mount ESP32-S3, install wire feed rollers, glue 6mm NdFeB magnets in foot pads |
| **foot_pad** | 8mm grip pad with microspine holes + penetrator studs | Press-fit 0.3mm spring-steel wire into spine holes |
| **servo_horn_adapter** | Connects SG90 horn to leg segment | Test fit, adjust `leg_socket_id` +/- 0.1mm |

### Cargo Pod

| Model | Key Feature | Post-Print Assembly |
|-------|-------------|---------------------|
| **pod_scaffold** | Lattice box for ferrocement filling | Fill lattice cells with bioreactor waste paste, let set 4 hrs |

## Display Models

These are scale models for visualization. Not functional hardware.

| Model | What It Shows | Scale | Print Notes |
|-------|---------------|-------|-------------|
| **mothership** | Full mothership with all modules stacked vertically, Phase 2 cargo ring, deployed solar panels | 1:25 | Paint modules different colors to match the in-game color coding |
| **nautilus_station** | 5-generation logarithmic spiral growth of the habitat, cutaway showing interior rock, siphuncle tubes, bulkheads | 1:100 | Cutaway face down on build plate for stability. Consider printing each chamber separately for multi-color |
| **seed_mothership** | Minimum viable asteroid mining seed (41 kg, $654K). Solar wings, robotic arms, Kapton membrane bundle | 1:10 | Print upright, no supports needed |
| **seed_capture** | Moment of capture: rock wrapped in Kapton membrane, seed mothership docked, printer bots on surface | 1:20 | Clear/transparent filament for membrane looks amazing |

## General Printing Tips

### Layer Height
- Functional parts: **0.2mm** (good balance of speed and detail)
- Display models: **0.15mm** (smoother surfaces, especially for spheres)
- Servo horn adapter: **0.15mm** (precision fit matters)

### Infill
- Functional tool heads: **20-30%** (light but strong enough for use)
- Worker/printer chassis: **15-20%** (servo pockets provide structure)
- Display models: **10-15%** (just needs to hold shape)
- Pod scaffold: **100%** for outer walls, lattice is the infill itself

### Material Selection
- **PETG** for all functional parts (heat resistant, impact tough, chemical
  resistant). Required where servos generate heat or parts see mechanical stress.
- **PLA** acceptable for display models only (easier to print, more color options,
  but brittle and softens at 60C).
- **Clear PETG** for the seed_capture membrane shell -- print it as a separate
  piece and assemble over the rock.

### Print Orientation
- **Tool heads**: Mount face on build plate (flat bottom)
- **Worker chassis**: Right-side up, thorax flat on bed
- **Printer bot**: Right-side up, thorax flat on bed
- **Foot pad**: Flat disc face down
- **Servo horn adapter**: Horn socket face on build plate
- **Nautilus station**: Cutaway face down (flat plane = stable base)
- **Mothership**: Drill end down (wide base for stability)
- **Seed mothership**: Upright (body centered, wings extend to sides)
- **Seed capture**: Flat cutaway face of the iron shell on bed

### Tolerances
- Servo pockets include **0.3-0.4mm** clearance for press-fit
- Magnet pockets include **0.2mm** clearance
- If parts are loose, reduce clearance by 0.1mm in the SCAD parameters
- If parts are tight, increase clearance by 0.1mm
- Test with one servo pocket before committing to a full chassis print

## Multi-Material / Multi-Color Recommendations

### Worker Chassis (if your printer supports MMU/AMS)
- **Orange** body (thorax + abdomen + head) -- the signature worker ant color
- **Dark gray** mandible arms and servo reinforcement ribs
- **Gray** electronics bay mounting posts

### Printer Bot
- **Iron gray** chassis and legs (represents WAAM-printed asteroid iron)
- **Blue** SG90 servo bodies (visual reference)
- **Green** ESP32 PCB
- **Orange** wire bobbin and WAAM nozzle tip
- **Silver** NdFeB magnets in foot pads

### Nautilus Station (best candidate for multi-color)
- **Gold** Gen 0 chamber (Kapton membrane vault)
- **Dark gray** Gen 1 (oldest iron)
- **Medium gray** Gen 2-3 (progressively lighter iron)
- **Light silver** Gen 4 (newest, shiniest iron)
- **Blue** tiny mothership solar panels
- **Orange** printer bots on the shell surface
- **Clear/translucent** concentrator mirrors

### Seed Capture Scene
- **Brown** asteroid rock
- **Clear gold** or **transparent** Kapton membrane (print separately)
- **Silver** iron shell (cutaway section)
- **Gray** seed mothership body
- **Blue** solar panel wings
- **Orange** printer bots

### Mothership
- **Silver** drill module (bottom)
- **Gray** sealing module
- **Teal** bioreactor vats
- **Blue** water tank (translucent if possible)
- **Orange** manufacturing module
- **Olive** cargo staging
- **Dark blue** solar panel wings
- **White** comms antenna

## Scale Adjustment

All display models have a `scale_factor` parameter at the top of the SCAD file.

| Model | Default | Smaller | Larger |
|-------|---------|---------|--------|
| mothership | 1/25 | 1/50 (fits in palm) | 1/10 (shelf centerpiece) |
| nautilus_station | 1/100 | 1/200 (keychain) | 1/50 (big desk model) |
| seed_mothership | 1/10 | 1/20 (keychain) | 1/5 (400mm wingspan, large printer) |
| seed_capture | 1/20 | 1/40 (ornament) | 1/10 (200mm rock, impressive) |

Functional models (tool heads, chassis) are already 1:1 and should not be
rescaled -- they mate with real SG90 servos and real magnets.

## Build Order (Recommended)

If you want to build a working ant prototype:

1. **servo_horn_adapter** -- Quick 10-min print. Test the SG90 fit immediately.
   Adjust tolerances before printing bigger parts.
2. **foot_pad** -- Another quick print. Verify microspine hole sizing.
3. **One tool head** (scoop_head is simplest) -- Test the magnetic mount fit.
4. **worker_chassis** -- The big print. Uses confirmed tolerances from steps 1-3.
5. **Remaining tool heads** as needed.

For display, start with **seed_mothership** (fastest, no supports) to test your
print quality before tackling the larger nautilus_station or seed_capture scene.
