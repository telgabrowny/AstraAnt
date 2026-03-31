# Vendor Parts -- 3D Model Sources for AstraAnt

Off-the-shelf part models for the Printer Bot and Seed Mothership assemblies.
These are NOT included in the repo (too large, varied licenses). This file
documents where to download them and how to prepare them for OpenSCAD.

**Last updated: 2026-03-30**

---

## OpenSCAD Import Constraints

OpenSCAD can only import **STL** and **AMF** mesh files (via `import()`).
It CANNOT import STEP, IGES, or native CAD formats directly.

Any STEP/IGES models must be converted to STL before use. See the
[Conversion Guide](#step-to-stl-conversion) at the bottom of this file.

Usage in OpenSCAD:
```openscad
// Import a vendor part positioned at origin
import("vendor_parts/sg90_servo.stl", convexity=4);
```

---

## Part Index

| # | Part | Dims (mm) | Used In | Qty |
|---|------|-----------|---------|-----|
| 1 | SG90 Micro Servo | 22.5 x 12.2 x 22.7 | Printer Bot legs | 8 |
| 2 | ESP32-S3 DevKitC-1 | 25.5 x 18 x ~3 | Printer Bot brain | 1 |
| 3 | RP2040 Pico | 51 x 21 x ~3.5 | Worker ant brain | 1 |
| 4 | N20 DC Micro Gearmotor | 12 dia x 25 long | Printer Bot wire feed | 1 |
| 5 | 683 Miniature Bearing | 3x7x3 | Wire feed rollers | 2 |
| 6 | 6x2mm NdFeB Disc Magnet | 6 dia x 2 | Foot pads (mag grip) | 8 |
| 7 | Peristaltic Pump Head | ~40-60mm body | Seed Mothership fluid | 1 |
| 8 | BIT-3 Ion Thruster | 80 dia x 60 deep | Seed Mothership prop | 1 |

---

## 1. SG90 Micro Servo (TowerPro)

- **Dimensions**: 22.5 x 12.2 x 22.7 mm (body), 32.5 mm tab-to-tab
- **Mass**: 9 g
- **Project ref**: `catalog/parts/sg90_servo.yaml`, `scad/printer_bot.scad`

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **GrabCAD (1)** | https://grabcad.com/library/tower-pro-sg90-servo-motor-1 | STEP, STL, SLDPRT | GrabCAD Community (free, non-commercial attribution) | High quality, includes wire channel and mounting tabs. Multiple versions available -- search "SG90" on GrabCAD and pick the one with highest downloads. Over 50 SG90 models on the platform. |
| **GrabCAD (2)** | https://grabcad.com/library/towerpro-sg90-9g-micro-servo-1 | STEP, IGS | GrabCAD Community | Another popular upload with accurate tab geometry. |
| **Thingiverse** | Search "SG90" on thingiverse.com | STL only | CC-BY or CC-BY-SA typically | Many SG90 mount/bracket designs that include an SG90 reference model. STL only -- no STEP. Accuracy varies. |
| **SnapEDA** | https://www.snapeda.com/parts/SG90/TowerPro/view-part/ | STEP (3D), also Eagle/KiCad footprints | Free with SnapEDA account | Good dimensional accuracy. Also gives you the PCB footprint if you need it for a carrier board. |
| **3DContentCentral** | Search "SG90" at 3dcontentcentral.com | STEP, STL, multiple native formats | Free (Dassault account required) | Supplier-contributed models, generally accurate. |

**Recommended**: GrabCAD -- largest selection, STEP available for high-fidelity work,
and many uploads include the output shaft spline detail which matters for horn fit.

**Accuracy note**: The SG90 is so widely modeled that you can cross-check any download
against the datasheet dims (22.2 x 11.8 x 31.0 per our catalog, or 22.5 x 12.2 x 22.7
per the printer_bot.scad -- slight variation exists between genuine TowerPro and clones).
Verify the tab-to-tab width (should be ~32-33mm) and shaft position offset from center.

**Needs conversion**: Yes -- download STEP, convert to STL for OpenSCAD.

---

## 2. ESP32-S3 DevKitC-1 (Espressif)

- **Dimensions**: 25.5 x 18 mm (board), ~69 x 25.5 mm with pin headers
- **Project ref**: `catalog/parts/esp32_s3.yaml`, `scad/printer_bot.scad`

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **Espressif GitHub** | https://github.com/espressif/esp-dev-kits (navigate to esp32-s3-devkitc-1/hardware/) | KiCad PCB, Altium, DXF board outline | Apache 2.0 | Official board files from Espressif. These are EDA files (KiCad/Altium), not 3D STEP files. KiCad 7+ can export a 3D STEP model from the board file if you have the 3D component library installed. This is the most dimensionally accurate source. |
| **GrabCAD** | Search "ESP32-S3 DevKitC" on grabcad.com | STEP, STL | GrabCAD Community | Community uploads -- check carefully that it is the DevKitC-1 variant (not the DevKitM or DevKitN). Several ESP32 dev board models available. |
| **SnapEDA** | https://www.snapeda.com search for "ESP32-S3-DevKitC-1" | STEP (3D), Eagle/KiCad footprints | Free with SnapEDA account | Good source for board-level 3D models with component height profiles. |
| **3DContentCentral** | Search "ESP32-S3" at 3dcontentcentral.com | STEP, native CAD | Free (Dassault account) | May have Espressif-contributed models. |

**Recommended**: Start with the **Espressif GitHub** official KiCad board files.
If you have KiCad 7+ installed, open the .kicad_pcb file and export as STEP via
File > Export > STEP. This gives the most accurate board outline and component
placement. If you don't want to set up KiCad, grab a STEP from GrabCAD.

**Note on module vs. dev board**: The project uses the DevKitC-1 dev board (with USB,
pin headers, regulator), not the bare ESP32-S3-WROOM-1 module. The module is 18 x 25.5mm;
the full dev board is approximately 69 x 25.5mm. For the printer bot, the relevant
dimensions are the module footprint (25.5 x 18mm as defined in printer_bot.scad) since
only the module sits in the electronics bay.

**Needs conversion**: Yes if STEP; KiCad export requires KiCad installed.

---

## 3. Raspberry Pi Pico (RP2040)

- **Dimensions**: 51 x 21 x ~3.5 mm (with headers: ~8.5mm tall)
- **Project ref**: `catalog/parts/rp2040.yaml`

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **Raspberry Pi Official** | https://datasheets.raspberrypi.com/pico/Pico-R3-step.zip | STEP | Open (Raspberry Pi documentation license) | Official STEP model from Raspberry Pi. This is the gold standard. Includes all component outlines, pin headers, USB connector. Directly from the hardware design files. |
| **Raspberry Pi KiCad** | https://datasheets.raspberrypi.com/pico/RPi-Pico-Pico_H-KiCad.zip | KiCad PCB + 3D | Open | Official KiCad project files. Can export STEP from KiCad. |
| **GrabCAD** | https://grabcad.com/library/raspberry-pi-pico-4 | STEP, STL, various | GrabCAD Community | Many Pico models uploaded. The official STEP is better. |
| **Thingiverse** | Search "Raspberry Pi Pico" on thingiverse.com | STL | CC-BY variants | Mostly cases and mounts that include a Pico reference model. STL-only. |

**Recommended**: Use the **official Raspberry Pi STEP file** from their datasheets
page. It is the definitive dimensional reference for the Pico board. No community
model will be more accurate.

**Needs conversion**: Yes -- official file is STEP. Convert to STL for OpenSCAD.

---

## 4. N20 DC Micro Gearmotor

- **Dimensions**: 12 mm diameter x 10 mm gearbox x 15-25 mm motor body (varies by ratio)
- **Shaft**: 3 mm D-shaft
- **Project ref**: `catalog/parts/n20_dc_motor.yaml`, `scad/printer_bot.scad` (wire feed motor)

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **GrabCAD** | Search "N20 gearmotor" or "N20 micro motor" on grabcad.com | STEP, STL, SLDPRT | GrabCAD Community | Many N20 models available. Look for one that matches the Pololu "micro metal gearmotor" form factor (12mm dia, 10mm gearbox, D-shaft). Pololu's variant is the most standardized. 20+ models to choose from. |
| **Pololu** | https://www.pololu.com/product/3072 (example, 100:1 HPCB) | DXF (2D outline only) | Pololu terms | Pololu provides 2D DXF dimensional drawings on each product page under "Resources." No 3D model, but the dimensions are authoritative. |
| **3DContentCentral** | Search "N20 motor" at 3dcontentcentral.com | STEP, native | Free (Dassault account) | Fewer options than GrabCAD but sometimes higher quality. |
| **TraceParts** | Search "N20 gearmotor" at traceparts.com | STEP, IGES, STL | Free account required | Industrial parts catalog, sometimes has micro motor models. |

**Recommended**: GrabCAD for the 3D model, cross-checked against the **Pololu 2D DXF**
for dimensional accuracy. The N20 form factor has slight variations between
manufacturers, so verify: 12mm body OD, gearbox length, shaft protrusion, and
mounting hole positions against whatever source you pick.

**Needs conversion**: Yes if STEP.

---

## 5. 683 Miniature Ball Bearing (3x7x3 mm)

- **Dimensions**: 3 mm bore x 7 mm OD x 3 mm width
- **Type**: Deep groove ball bearing, open (or shielded: 683ZZ)
- **Used for**: Wire feed roller shafts in the WAAM print head

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **GrabCAD** | Search "683 bearing" or "3x7x3 bearing" on grabcad.com | STEP, STL | GrabCAD Community | Several miniature bearing models available. Some are generic parametric models usable for any bearing size. |
| **SKF** | https://www.skf.com/group/products/rolling-bearings/ball-bearings/deep-groove-ball-bearings (search W 618/3) | STEP (some models) | Free for engineering use | SKF's online catalog provides STEP downloads for many bearing sizes. The 683 is listed as "W 618/3" in SKF nomenclature. Check the product page for a CAD download button. |
| **NSK** | https://www.nsk.com search for "683" | STEP | Free for engineering use | NSK's online catalog sometimes provides 3D models. Less reliable availability for micro sizes. |
| **TraceParts** | https://www.traceparts.com search "683 bearing" | STEP, IGES, STL, many formats | Free account required | TraceParts hosts manufacturer catalogs (SKF, NMB, etc.) and is one of the best sources for standardized mechanical components. Very likely to have this exact bearing. |
| **McMaster-Carr** | https://www.mcmaster.com search "3mm bore miniature bearing" | STEP | McMaster account (US/Canada) | McMaster provides STEP downloads for nearly every product. The 683 bearing (McMaster PN varies) will have an accurate STEP model. Requires a McMaster account. |

**Recommended**: **TraceParts** or **McMaster-Carr** for an accurate manufacturer model.
Bearing geometry is standardized (ISO 15), so any 683/W618-3 model will have correct
dimensions. If you just need a placeholder, the bearing is simple enough to model
parametrically in OpenSCAD:

```openscad
// 683 bearing placeholder (3x7x3)
module bearing_683() {
    difference() {
        cylinder(d=7, h=3, center=true, $fn=48);   // outer race
        cylinder(d=3, h=3.1, center=true, $fn=48);  // bore
    }
}
```

**Needs conversion**: Yes if STEP. Parametric OpenSCAD module may be sufficient
given the simple geometry.

---

## 6. 6x2mm NdFeB Disc Magnet (N52)

- **Dimensions**: 6 mm diameter x 2 mm thick
- **Material**: NdFeB (neodymium), nickel plated, N52 grade
- **Project ref**: `scad/printer_bot.scad` (foot pad grip magnets)

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **GrabCAD** | Search "neodymium disc magnet 6mm" on grabcad.com | STEP, STL | GrabCAD Community | A few magnet models exist. Most are simple cylinders. |
| **K&J Magnetics** | https://www.kjmagnetics.com/proddetail.asp?prod=D62-N52 | None (2D drawings only) | N/A | K&J is the reference supplier for NdFeB magnets. They provide dimensional drawings but NOT 3D CAD files. Use their dimensions to validate any model you find or create. |
| **McMaster-Carr** | Search "neodymium disc magnet 6mm" at mcmaster.com | STEP | McMaster account | McMaster carries disc magnets and provides STEP files. May not have exact 6x2 N52 but will have a dimensionally identical disc magnet model. |

**Recommended**: Model this yourself in OpenSCAD. A disc magnet is a cylinder, possibly
with a small edge chamfer (typically 0.1-0.2mm on NdFeB magnets from nickel plating).
No vendor model will add meaningful accuracy over a parametric cylinder.

```openscad
// 6x2mm NdFeB disc magnet with plating chamfer
module magnet_6x2() {
    chamfer = 0.15;
    hull() {
        cylinder(d=6, h=2 - 2*chamfer, center=true, $fn=48);
        cylinder(d=6 - 2*chamfer, h=2, center=true, $fn=48);
    }
}
```

**Needs conversion**: No -- parametric OpenSCAD is the right approach for this part.

---

## 7. Peristaltic Pump Head (Watson-Marlow Style)

- **Type**: Roller peristaltic pump, 3-roller or 4-roller
- **Typical body size**: 40-60 mm diameter (varies widely by flow rate)
- **Project ref**: `configs/mothership/bioreactor.yaml`, `astraant/seed_bom.py`

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **GrabCAD (1)** | Search "peristaltic pump" on grabcad.com | STEP, STL, various | GrabCAD Community | 40+ peristaltic pump models on GrabCAD. Quality ranges from simple 3-roller heads to complete Watson-Marlow assemblies. Look for models with visible rollers and tubing channel -- these are more useful for visualization. |
| **GrabCAD (2)** | Search "Watson Marlow pump" on grabcad.com | STEP, SLDPRT | GrabCAD Community | Specific Watson-Marlow pump assemblies uploaded by community members. |
| **Thingiverse** | Search "peristaltic pump" on thingiverse.com | STL | CC-BY variants | Many 3D-printable peristaltic pump designs (functional, not just models). These are useful because they show the actual roller mechanism at a printable scale. |
| **Watson-Marlow** | https://www.watson-marlow.com (product pages) | Sometimes STEP/DXF on request | Varies | Watson-Marlow provides dimensional drawings and sometimes CAD downloads for specific pump heads. Contact their engineering support or check individual product pages. |
| **TraceParts** | Search "peristaltic pump" at traceparts.com | STEP, IGES, STL | Free account | May have industrial peristaltic pump models from various manufacturers. |

**Recommended**: GrabCAD for a representative model. For the AstraAnt seed mothership,
the exact pump model matters less than getting the envelope dimensions right. The pump
in the seed mothership is a miniature unit (fluid handling for electro-winning cell),
not a large industrial Watson-Marlow. A 3D-printable design from Thingiverse might
actually be closer to the target size and complexity.

**Note**: For the seed mothership, the pump is internal to the main body and not
visible externally, so a simplified representation may be adequate. For the
display model (1:10 scale), internal components are not rendered anyway.

**Needs conversion**: Depends on source. GrabCAD STEP models need conversion.
Thingiverse STL files can be used directly.

---

## 8. BIT-3 Ion Thruster (Busek) or Similar CubeSat Ion Engine

- **Dimensions**: ~80 mm diameter x 60 mm deep (BIT-3 class)
- **Type**: Iodine-fed ion thruster, 1.4 mN thrust, Isp 2200 s
- **Project ref**: `astraant/seed_bom.py`, `configs/mothership/propulsion.yaml`,
  `scad/seed_mothership.scad`

### Best Sources

| Source | URL | Format | License | Notes |
|--------|-----|--------|---------|-------|
| **NASA 3D Resources** | https://nasa3d.arc.nasa.gov/models | STL (mostly) | Public domain (NASA media) | NASA's official 3D model library has spacecraft components, but focuses on famous missions (ISS, SLS, etc.). Ion thrusters are less commonly modeled. Search for "ion thruster" or "electric propulsion." The NEXT-C or NSTAR engines may be available but are much larger than BIT-3. |
| **GrabCAD** | Search "ion thruster" or "Hall thruster" on grabcad.com | STEP, STL | GrabCAD Community | Several ion thruster and Hall-effect thruster models available. Most are educational/conceptual rather than dimensionally accurate to a specific product. Look for "CubeSat thruster" or "electric propulsion." |
| **Busek Publications** | https://www.busek.com/bit3 | PDF drawings only | Proprietary | Busek publishes dimensional outline drawings in their datasheets and conference papers (AIAA, etc.). These give you the envelope dimensions but no 3D CAD file. The BIT-3 is a commercial product with restricted technical data -- Busek does not publish STEP files. |
| **NASA Technical Reports (NTRS)** | https://ntrs.nasa.gov search "BIT-3" or "iodine thruster" | PDF papers with dimensions | Public domain | Conference papers and technical reports include dimensional drawings, mass, and performance data. Not 3D models, but excellent reference for creating one. |
| **NIFTi / SmallSat catalog** | Various CubeSat component databases | Varies | Varies | Some CubeSat component databases include 3D envelope models for propulsion systems. Search "CubeSat electric propulsion" on platforms like satsearch.co or unisec-global.org. |

**Recommended**: No high-quality, freely available STEP model of the BIT-3 exists
publicly (it is an ITAR-adjacent commercial product). The best approach is:

1. Download the BIT-3 datasheet from Busek's website for envelope dimensions.
2. Use a GrabCAD "ion thruster" model as a visual reference.
3. For OpenSCAD, model it parametrically using the datasheet dimensions.
   The BIT-3 is essentially a cylinder with a grid assembly on one end:

```openscad
// BIT-3 class ion thruster (simplified envelope)
module bit3_thruster() {
    // Main body cylinder
    color([0.5, 0.5, 0.55])
    cylinder(d=80, h=60, $fn=64);

    // Grid assembly (front face)
    color([0.6, 0.6, 0.65])
    translate([0, 0, 60])
        cylinder(d=75, h=5, $fn=64);

    // Propellant feed connector (rear)
    color([0.4, 0.4, 0.45])
    translate([0, 0, -10])
        cylinder(d=15, h=10, $fn=32);
}
```

**Needs conversion**: N/A -- parametric model recommended due to lack of vendor CAD.

---

## STEP to STL Conversion

OpenSCAD only imports STL (and AMF). Most vendor 3D models are distributed as STEP.
Here are the conversion options:

### Option 1: FreeCAD (Recommended -- Free, Scriptable)

FreeCAD can convert STEP to STL from the GUI or command line.

**GUI method:**
1. Open FreeCAD
2. File > Open > select the .step file
3. Select the imported shape in the model tree
4. File > Export > choose "STL Mesh (*.stl)"
5. Set mesh tolerance (0.01mm is good for small parts)

**Command-line batch conversion** (Python script using FreeCAD):
```python
# convert_step_to_stl.py -- run with: freecad -c convert_step_to_stl.py
import sys
import FreeCAD
import Part
import Mesh

input_file = sys.argv[1]   # e.g., "sg90_servo.step"
output_file = sys.argv[2]  # e.g., "sg90_servo.stl"

shape = Part.Shape()
shape.read(input_file)
mesh = Mesh.Mesh()
mesh.addFacets(shape.tessellate(0.01))  # 0.01mm tolerance
mesh.write(output_file)
print(f"Converted {input_file} -> {output_file}")
```

Run from command line:
```bash
freecadcmd convert_step_to_stl.py input.step output.stl
```

### Option 2: OpenSCAD via CSG (Workaround)

OpenSCAD itself cannot read STEP, but you can:
1. Convert STEP to STL using FreeCAD (above)
2. Import the STL in OpenSCAD: `import("part.stl");`

### Option 3: Online Converters

- **CAD Exchanger** (https://cadexchanger.com/) -- accurate, free tier limited
- **3D-Tool** (https://www.3d-tool.com/) -- free viewer with export
- **Autodesk Fusion 360** (free for personal use) -- File > Open STEP, File > Export STL

### Option 4: Blender with Add-on

Blender (free) with the **CAD Sketcher** or **Import-Export: STL/STEP** add-on
can read STEP files. Blender's STEP support requires the `ifcopenshell` or
`OCP` Python package.

### Recommended Conversion Settings

For parts at the scale of AstraAnt components (5-80mm):

| Setting | Value | Why |
|---------|-------|-----|
| Mesh tolerance | 0.01 mm | Fine enough for 3D printing accuracy |
| Angular tolerance | 5 degrees | Smooth curves without excessive triangles |
| File size target | < 5 MB per part | Keeps OpenSCAD responsive |
| Binary STL | Yes | 5x smaller than ASCII STL |

---

## File Naming Convention

When downloading and converting vendor models, use this naming scheme:

```
scad/vendor_parts/
    sg90_servo.stl
    esp32_s3_devkitc1.stl
    rp2040_pico.stl
    n20_gearmotor.stl
    bearing_683_3x7x3.stl
    magnet_ndfeb_6x2.stl        (or use parametric OpenSCAD)
    peristaltic_pump_mini.stl
    bit3_ion_thruster.stl       (or use parametric OpenSCAD)
```

Each STL should be:
- Oriented with the primary mounting face on the XY plane
- Centered on the origin (or centered on the mounting hole pattern)
- In millimeters (verify -- some models use inches or meters)
- Manifold (watertight) with no degenerate triangles

---

## Integration with Existing SCAD Files

The current `printer_bot.scad` and `seed_mothership.scad` use parametric
OpenSCAD modules (e.g., `sg90_visual()`, `esp32_board()`) as placeholders.

To swap in vendor STL models:

```openscad
// Before (parametric placeholder):
module sg90_visual() {
    color([0.2, 0.4, 0.8])
        cube([sg90_l, sg90_w, sg90_tab_h], center=true);
    // ... simplified geometry
}

// After (vendor model):
module sg90_visual() {
    color([0.2, 0.4, 0.8])
    translate([0, 0, -sg90_tab_h/2])    // adjust origin to match
    rotate([0, 0, 0])                    // adjust orientation
        import("vendor_parts/sg90_servo.stl", convexity=4);
}
```

The `servo_pocket()` module should NOT use the vendor model -- pockets
should remain parametric with explicit clearances so they render correctly
in difference() operations.

---

## License Summary

| Part | Likely License | Commercial Use OK? |
|------|---------------|-------------------|
| SG90 (GrabCAD) | GrabCAD Community License | Yes with attribution |
| ESP32-S3 (Espressif GitHub) | Apache 2.0 | Yes |
| RP2040 Pico (Raspberry Pi) | Open documentation license | Yes |
| N20 Motor (GrabCAD) | GrabCAD Community License | Yes with attribution |
| 683 Bearing (TraceParts) | Engineering use, varies by source | Typically yes |
| NdFeB Magnet | Self-modeled / trivial geometry | N/A |
| Peristaltic Pump (GrabCAD) | GrabCAD Community License | Yes with attribution |
| BIT-3 Thruster | Self-modeled (no vendor CAD public) | N/A |

**GrabCAD Community License**: Models are free to download and use. Attribution
to the original author is expected. Commercial use is generally permitted but
check individual model pages for any restrictions noted by the uploader.

---

## Priority Download Order

For getting the printer bot prototype print-ready:

1. **SG90 Servo** -- most critical, 8 per bot, pocket fit matters
2. **N20 Motor** -- wire feed mechanism, shaft alignment matters
3. **683 Bearing** -- simple geometry, parametric is fine initially
4. **ESP32-S3** -- for visual completeness, not structural
5. **Magnets** -- use parametric, no vendor model needed
6. **RP2040 Pico** -- for worker ant, not the printer bot directly
7. **Peristaltic Pump** -- seed mothership internals, low priority
8. **BIT-3 Thruster** -- seed mothership, display model only

---

## Verification Checklist

After downloading and converting each model, verify:

- [ ] Dimensions match the catalog YAML specs and SCAD parameter values
- [ ] Units are in millimeters (not inches or meters)
- [ ] Model is watertight (no holes or non-manifold edges)
- [ ] Origin and orientation are consistent with the SCAD assembly
- [ ] File size is reasonable (< 5 MB per part)
- [ ] Model imports cleanly in OpenSCAD (`import()` with no errors)
- [ ] Visual preview matches the physical part (if you have one on hand)
