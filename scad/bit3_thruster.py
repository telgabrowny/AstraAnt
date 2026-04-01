"""
AstraAnt BIT-3 Ion Thruster -- Parametric CadQuery Model
=========================================================

CadQuery parametric model of the Busek BIT-3 iodine-fueled RF ion thruster.
Based on published Busek specifications and data sheets.

THRUSTER SPECS:
  Grid diameter:    25 mm
  Body:             30 mm dia x 40 mm long
  Mounting flange:  40 mm dia, 4x M3 on 32mm BCD
  Neutralizer:      8 mm dia x 15 mm, offset from body
  PPU:              80 x 60 x 30 mm separate box
  Total mass:       1.5 kg (thruster 0.8 kg + PPU 0.7 kg)

Usage:
  python scad/bit3_thruster.py

Outputs:
  scad/bit3_thruster.step   (colored assembly)
  scad/bit3_thruster.stl    (merged mesh)
"""

import os
import sys
import math
import warnings

import cadquery as cq
from cadquery import Color

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = SCRIPT_DIR

# ---------------------------------------------------------------------------
# Material densities (kg/m^3)
# ---------------------------------------------------------------------------
RHO_STEEL = 7900        # Stainless steel (thruster body)
RHO_MOLY = 10280        # Molybdenum (grids)
RHO_COPPER = 8960       # Copper (RF antenna coil)
RHO_AL = 2700           # Aluminum 6061-T6 (mounting flange)
RHO_PCB = 1850          # FR4 PCB (PPU internals)
RHO_AL_ENCLOSURE = 2700 # Aluminum enclosure (PPU housing)

# ---------------------------------------------------------------------------
# Thruster body parameters (all dimensions in mm)
# ---------------------------------------------------------------------------
BODY_DIA = 30.0          # Discharge chamber outer diameter
BODY_LENGTH = 40.0       # Discharge chamber length
BODY_WALL = 1.5          # Wall thickness

GRID_DIA = 25.0          # Ion optics grid diameter
GRID_THICKNESS = 1.0     # Each grid disc thickness
GRID_GAP = 1.5           # Gap between screen and accel grids
GRID_HOLE_DIA = 1.2      # Individual aperture diameter
GRID_HOLE_RINGS = 4      # Number of concentric rings of holes

# ---------------------------------------------------------------------------
# RF antenna coil
# ---------------------------------------------------------------------------
RF_COIL_WIRE_DIA = 1.0   # Copper wire diameter
RF_COIL_TURNS = 8        # Number of visible turns
RF_COIL_PITCH = 3.5      # Axial pitch per turn (mm)
RF_COIL_INNER_DIA = BODY_DIA + 1.0  # Wraps around discharge chamber

# ---------------------------------------------------------------------------
# Mounting flange
# ---------------------------------------------------------------------------
FLANGE_DIA = 40.0        # Outer diameter
FLANGE_THICKNESS = 3.0   # Thickness
BOLT_CIRCLE_DIA = 32.0   # Bolt circle diameter (M3 holes)
BOLT_HOLE_DIA = 3.2      # M3 clearance hole
NUM_BOLTS = 4            # Number of mounting holes

# ---------------------------------------------------------------------------
# Neutralizer
# ---------------------------------------------------------------------------
NEUT_DIA = 8.0           # Neutralizer tube diameter
NEUT_LENGTH = 15.0       # Neutralizer length
NEUT_OFFSET_Y = 22.0     # Lateral offset from thruster centerline
NEUT_OFFSET_X = -5.0     # Axial offset (slightly behind grid face)

# ---------------------------------------------------------------------------
# PPU (Power Processing Unit)
# ---------------------------------------------------------------------------
PPU_X = 80.0             # Length
PPU_Y = 60.0             # Width
PPU_Z = 30.0             # Height
PPU_WALL = 1.5           # Enclosure wall thickness
PPU_OFFSET_Y = 60.0      # Distance from thruster centerline
CABLE_DIA = 5.0          # Harness cable diameter
CABLE_LENGTH = 80.0      # Cable run length

# Connector on PPU
CONNECTOR_X = 15.0
CONNECTOR_Y = 10.0
CONNECTOR_Z = 8.0

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
COL_BODY = Color(0.55, 0.55, 0.58, 1.0)       # Stainless steel gray
COL_GRID = Color(0.35, 0.35, 0.38, 1.0)       # Molybdenum darker gray
COL_COIL = Color(0.72, 0.45, 0.20, 1.0)       # Copper
COL_FLANGE = Color(0.70, 0.70, 0.72, 1.0)     # Aluminum
COL_NEUT = Color(0.50, 0.50, 0.53, 1.0)       # Stainless gray
COL_PPU = Color(0.15, 0.15, 0.18, 1.0)        # Black box
COL_CONNECTOR = Color(0.80, 0.75, 0.60, 1.0)  # Gold connector
COL_CABLE = Color(0.20, 0.20, 0.22, 1.0)      # Dark cable


# ---------------------------------------------------------------------------
# Mass ledger
# ---------------------------------------------------------------------------
class MassLedger:
    """Track component masses."""
    def __init__(self):
        self.entries = []

    def add(self, name, mass_kg):
        self.entries.append((name, mass_kg))

    def total(self):
        return sum(m for _, m in self.entries)

    def report(self):
        lines = []
        lines.append("=" * 60)
        lines.append("  BIT-3 ION THRUSTER -- MASS BREAKDOWN")
        lines.append("=" * 60)
        for name, mass in self.entries:
            lines.append(f"  {name:<45} {mass:>6.3f} kg")
        lines.append("-" * 60)
        lines.append(f"  {'TOTAL':<45} {self.total():>6.3f} kg")
        lines.append(f"  {'Published spec':<45} {'1.500':>6} kg")
        lines.append("=" * 60)
        return "\n".join(lines)


ledger = MassLedger()


# ===========================================================================
# BUILD FUNCTIONS
# ===========================================================================

def build_discharge_chamber():
    """Cylindrical discharge chamber -- the main thruster body."""
    # Hollow cylinder (stainless steel)
    outer = (cq.Workplane("YZ")
             .circle(BODY_DIA / 2)
             .extrude(BODY_LENGTH))
    inner = (cq.Workplane("YZ")
             .circle(BODY_DIA / 2 - BODY_WALL)
             .extrude(BODY_LENGTH - BODY_WALL))
    # Shift inner forward so back wall is solid
    inner = inner.translate((BODY_WALL, 0, 0))
    chamber = outer.cut(inner)

    # Volume: pi * L * (R_o^2 - R_i^2) + back wall
    r_o = BODY_DIA / 2
    r_i = r_o - BODY_WALL
    vol_walls = math.pi * (r_o**2 - r_i**2) * (BODY_LENGTH - BODY_WALL)
    vol_back = math.pi * r_o**2 * BODY_WALL
    vol_mm3 = vol_walls + vol_back
    mass_kg = vol_mm3 * 1e-9 * RHO_STEEL
    ledger.add("Discharge chamber (SS)", mass_kg)

    return chamber


def build_grids():
    """Screen grid and accelerator grid with aperture pattern."""
    parts = []

    for i, x_off in enumerate([BODY_LENGTH, BODY_LENGTH + GRID_THICKNESS + GRID_GAP]):
        label = "screen" if i == 0 else "accel"

        # Base disc
        grid = (cq.Workplane("YZ")
                .circle(GRID_DIA / 2)
                .extrude(GRID_THICKNESS)
                .translate((x_off, 0, 0)))

        # Drill aperture pattern (concentric rings)
        holes = cq.Workplane("YZ").transformed(offset=(x_off, 0, 0))
        # Center hole
        holes = holes.circle(GRID_HOLE_DIA / 2)

        for ring in range(1, GRID_HOLE_RINGS + 1):
            r = ring * (GRID_DIA / 2) / (GRID_HOLE_RINGS + 1)
            n_holes = max(6, ring * 6)  # 6, 12, 18, 24 holes per ring
            for j in range(n_holes):
                angle = 2 * math.pi * j / n_holes
                cy = r * math.cos(angle)
                cz = r * math.sin(angle)
                holes = holes.center(cy, cz).circle(GRID_HOLE_DIA / 2).center(-cy, -cz)

        hole_solid = holes.extrude(GRID_THICKNESS + 0.2)
        hole_solid = hole_solid.translate((x_off - 0.1, 0, 0))
        grid = grid.cut(hole_solid)

        parts.append((f"grid_{label}", grid))

    # Mass: two thin molybdenum discs (approximate -- holes reduce mass ~30%)
    vol_each = math.pi * (GRID_DIA / 2)**2 * GRID_THICKNESS * 0.70
    mass_kg = 2 * vol_each * 1e-9 * RHO_MOLY
    ledger.add("Ion optics grids (Mo, 2x)", mass_kg)

    return parts


def build_rf_coil():
    """RF antenna coil wrapped around the discharge chamber."""
    parts = []

    coil_r = RF_COIL_INNER_DIA / 2 + RF_COIL_WIRE_DIA / 2
    wire_r = RF_COIL_WIRE_DIA / 2

    # Build coil as a series of torus segments (one per turn)
    # Each turn is a torus at a different X position
    total_coil_length = RF_COIL_TURNS * RF_COIL_PITCH
    start_x = (BODY_LENGTH - total_coil_length) / 2  # centered on chamber

    for t in range(RF_COIL_TURNS):
        x_pos = start_x + t * RF_COIL_PITCH

        # Create a single turn as a revolved circle
        turn = (cq.Workplane("XZ")
                .center(coil_r, 0)
                .circle(wire_r)
                .revolve(360, (0, 0, 0), (0, 0, 1)))
        # Rotate so the coil axis aligns with X (thrust axis)
        turn = turn.rotateAboutCenter((0, 1, 0), 90)
        turn = turn.translate((x_pos, 0, 0))
        parts.append((f"rf_coil_turn_{t}", turn))

    # Mass: total wire length
    circumference = 2 * math.pi * coil_r
    wire_length = circumference * RF_COIL_TURNS
    wire_vol = math.pi * wire_r**2 * wire_length
    mass_kg = wire_vol * 1e-9 * RHO_COPPER
    ledger.add("RF antenna coil (Cu)", mass_kg)

    return parts


def build_mounting_flange():
    """Mounting flange at the rear of the thruster."""
    flange = (cq.Workplane("YZ")
              .circle(FLANGE_DIA / 2)
              .circle(BODY_DIA / 2 + 0.5)  # clearance for chamber
              .extrude(FLANGE_THICKNESS))
    # Translate to rear of chamber (X=0 is the back)
    flange = flange.translate((-FLANGE_THICKNESS, 0, 0))

    # Drill bolt holes on bolt circle
    bolt_r = BOLT_CIRCLE_DIA / 2
    for i in range(NUM_BOLTS):
        angle = 2 * math.pi * i / NUM_BOLTS + math.pi / 4  # 45 deg offset
        by = bolt_r * math.cos(angle)
        bz = bolt_r * math.sin(angle)
        hole = (cq.Workplane("YZ")
                .center(by, bz)
                .circle(BOLT_HOLE_DIA / 2)
                .extrude(FLANGE_THICKNESS + 0.2)
                .translate((-FLANGE_THICKNESS - 0.1, 0, 0)))
        flange = flange.cut(hole)

    vol = math.pi * ((FLANGE_DIA / 2)**2 - (BODY_DIA / 2 + 0.5)**2) * FLANGE_THICKNESS
    # Subtract bolt holes
    vol -= NUM_BOLTS * math.pi * (BOLT_HOLE_DIA / 2)**2 * FLANGE_THICKNESS
    mass_kg = vol * 1e-9 * RHO_AL
    ledger.add("Mounting flange (Al)", mass_kg)

    return flange


def build_neutralizer():
    """Hollow cathode neutralizer -- small cylinder offset from main body."""
    neut = (cq.Workplane("YZ")
            .circle(NEUT_DIA / 2)
            .extrude(NEUT_LENGTH)
            .translate((BODY_LENGTH + NEUT_OFFSET_X, NEUT_OFFSET_Y, 0)))

    # Small mounting bracket connecting to thruster body
    bracket = (cq.Workplane("XY")
               .rect(3, NEUT_OFFSET_Y - BODY_DIA / 2)
               .extrude(3)
               .translate((BODY_LENGTH - 5,
                           BODY_DIA / 2 + (NEUT_OFFSET_Y - BODY_DIA / 2) / 2,
                           0)))

    vol = math.pi * (NEUT_DIA / 2)**2 * NEUT_LENGTH
    mass_kg = vol * 1e-9 * RHO_STEEL * 0.5  # hollow
    ledger.add("Neutralizer (hollow cathode)", mass_kg)

    return [(f"neutralizer_tube", neut), (f"neutralizer_bracket", bracket)]


def build_ppu():
    """Power Processing Unit -- separate electronics box."""
    # Outer enclosure
    outer = cq.Workplane("XY").box(PPU_X, PPU_Y, PPU_Z)
    inner = cq.Workplane("XY").box(PPU_X - 2 * PPU_WALL,
                                    PPU_Y - 2 * PPU_WALL,
                                    PPU_Z - 2 * PPU_WALL)
    ppu_box = outer.cut(inner)

    # Position PPU offset from thruster
    ppu_box = ppu_box.translate((BODY_LENGTH / 2, -PPU_OFFSET_Y, 0))

    # Connector on the face toward thruster
    connector = (cq.Workplane("XY")
                 .box(CONNECTOR_X, CONNECTOR_Y, CONNECTOR_Z)
                 .translate((BODY_LENGTH / 2,
                             -PPU_OFFSET_Y + PPU_Y / 2 + CONNECTOR_Y / 2,
                             0)))

    # Cable run (simplified as a cylinder between PPU and thruster)
    cable = (cq.Workplane("XZ")
             .circle(CABLE_DIA / 2)
             .extrude(CABLE_LENGTH)
             .translate((BODY_LENGTH / 2,
                         -PPU_OFFSET_Y + PPU_Y / 2 + CONNECTOR_Y,
                         0)))

    # Mass from Busek spec: 0.7 kg total PPU
    ledger.add("PPU enclosure + electronics", 0.700)

    return [("ppu_box", ppu_box),
            ("ppu_connector", connector),
            ("ppu_cable", cable)]


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    """Build the complete BIT-3 assembly."""
    print("Building BIT-3 Ion Thruster Model...")
    print(f"  Body:    {BODY_DIA:.0f} mm dia x {BODY_LENGTH:.0f} mm long")
    print(f"  Grid:    {GRID_DIA:.0f} mm dia ({GRID_HOLE_RINGS} rings of apertures)")
    print(f"  Flange:  {FLANGE_DIA:.0f} mm dia, {NUM_BOLTS}x M3 on {BOLT_CIRCLE_DIA:.0f} mm BCD")
    print(f"  PPU:     {PPU_X:.0f} x {PPU_Y:.0f} x {PPU_Z:.0f} mm")
    print()

    assy = cq.Assembly(name="bit3_thruster")

    # Discharge chamber
    chamber = build_discharge_chamber()
    assy.add(chamber, name="discharge_chamber", color=COL_BODY)

    # Ion optics grids
    grid_parts = build_grids()
    for name, part in grid_parts:
        assy.add(part, name=name, color=COL_GRID)

    # RF antenna coil
    coil_parts = build_rf_coil()
    for name, part in coil_parts:
        assy.add(part, name=name, color=COL_COIL)

    # Mounting flange
    flange = build_mounting_flange()
    assy.add(flange, name="mounting_flange", color=COL_FLANGE)

    # Neutralizer
    neut_parts = build_neutralizer()
    for name, part in neut_parts:
        col = COL_NEUT if "tube" in name else COL_FLANGE
        assy.add(part, name=name, color=col)

    # PPU
    ppu_parts = build_ppu()
    for name, part in ppu_parts:
        if "connector" in name:
            col = COL_CONNECTOR
        elif "cable" in name:
            col = COL_CABLE
        else:
            col = COL_PPU
        assy.add(part, name=name, color=col)

    # Account for remaining mass (wiring, gas feed, misc)
    current_mass = ledger.total()
    remaining = 1.500 - current_mass
    if remaining > 0:
        ledger.add("Misc (wiring, gas feed, fasteners)", remaining)

    return assy


def export(assy):
    """Export STEP and STL files."""
    os.makedirs(OUT_DIR, exist_ok=True)

    step_path = os.path.join(OUT_DIR, "bit3_thruster.step")
    print(f"  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(step_path, exportType="STEP")
    size_kb = os.path.getsize(step_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    stl_path = os.path.join(OUT_DIR, "bit3_thruster.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(stl_path, exportType="STL", tolerance=0.05, angularTolerance=0.1)
    size_kb = os.path.getsize(stl_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 60)
    print("  AstraAnt BIT-3 Ion Thruster -- CadQuery Parametric Model")
    print("=" * 60)
    print()

    assy = build_assembly()
    export(assy)

    print()
    print(ledger.report())

    print()
    print("  KEY DIMENSIONS:")
    print(f"    Grid diameter:       {GRID_DIA:.0f} mm")
    print(f"    Body diameter:       {BODY_DIA:.0f} mm")
    print(f"    Body length:         {BODY_LENGTH:.0f} mm")
    print(f"    Flange diameter:     {FLANGE_DIA:.0f} mm")
    print(f"    Bolt circle:         {BOLT_CIRCLE_DIA:.0f} mm ({NUM_BOLTS}x M{BOLT_HOLE_DIA - 0.2:.0f})")
    total_length = FLANGE_THICKNESS + BODY_LENGTH + GRID_THICKNESS * 2 + GRID_GAP
    print(f"    Overall length:      {total_length:.1f} mm (flange to grid face)")
    print(f"    Neutralizer offset:  {NEUT_OFFSET_Y:.0f} mm from centerline")
    print(f"    PPU size:            {PPU_X:.0f} x {PPU_Y:.0f} x {PPU_Z:.0f} mm")
    print(f"    Total mass:          {ledger.total():.3f} kg")


if __name__ == "__main__":
    main()
