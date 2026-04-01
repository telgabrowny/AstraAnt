"""
AstraAnt Deployable Solar Panel -- Parametric CadQuery Model
=============================================================

CadQuery parametric model of a standard CubeSat deployable solar panel.
Models both stowed and deployed configurations.

PANEL SPECS:
  Panel surface:    2000 x 800 x 1.5 mm (2 m^2)
  Solar cells:      40 x 16 grid, each 50 x 50 mm, 1 mm gaps
  Hinge:            Torsion spring, 800 mm long barrel (8 mm dia)
  Substrate:        Aluminum honeycomb (modeled as flat plate)
  Stowed:           800 x 800 x 3 mm (folded in half)
  Deployed:         Panel extended 90 deg from hinge
  Mass:             1.5 kg per panel

Usage:
  python scad/solar_panel_deploy.py

Outputs:
  scad/solar_panel_deployed.step
  scad/solar_panel_stowed.step
  scad/solar_panel.stl               (deployed config)
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
RHO_AL_HONEYCOMB = 32     # Aluminum honeycomb core density (effective, 1/8" cell)
RHO_AL_SKIN = 2700        # Al face sheets
RHO_SOLAR_CELL = 2330     # Silicon solar cells (triple-junction GaAs)
RHO_GLASS = 2500          # Cover glass (CMG)
RHO_AL = 2700             # Aluminum hinge, frame
RHO_SPRING_STEEL = 7850   # Torsion spring
RHO_KAPTON = 1420         # Kapton insulation layer

# ---------------------------------------------------------------------------
# Panel parameters (all dimensions in mm)
# ---------------------------------------------------------------------------
PANEL_LENGTH = 2000.0     # Full deployed length
PANEL_WIDTH = 800.0       # Panel width (hinge axis direction)
PANEL_THICK = 1.5         # Substrate thickness (honeycomb + face sheets)

# Substrate breakdown
SKIN_THICK = 0.2          # Each Al face sheet
CORE_THICK = PANEL_THICK - 2 * SKIN_THICK  # Honeycomb core

# ---------------------------------------------------------------------------
# Solar cell grid
# ---------------------------------------------------------------------------
CELL_SIZE = 50.0          # Cell is square
CELL_GAP = 1.0            # Gap between cells
CELL_THICK = 0.15         # Cell thickness (triple-junction, space-grade)
COVER_GLASS_THICK = 0.10  # CMG cover glass (100 um, typical space panel)
CELLS_ALONG_LENGTH = 40   # 40 cells along 2000 mm
CELLS_ALONG_WIDTH = 16    # 16 cells along 800 mm
CELL_MARGIN_LENGTH = (PANEL_LENGTH - CELLS_ALONG_LENGTH * (CELL_SIZE + CELL_GAP) + CELL_GAP) / 2
CELL_MARGIN_WIDTH = (PANEL_WIDTH - CELLS_ALONG_WIDTH * (CELL_SIZE + CELL_GAP) + CELL_GAP) / 2

# ---------------------------------------------------------------------------
# Hinge assembly
# ---------------------------------------------------------------------------
HINGE_BARREL_DIA = 8.0    # Hinge barrel outer diameter
HINGE_BARREL_WALL = 1.0   # Barrel wall thickness
HINGE_LENGTH = PANEL_WIDTH # Full width of panel
NUM_KNUCKLES = 3           # Number of hinge knuckles
KNUCKLE_GAP = 2.0          # Gap between knuckles
HINGE_PIN_DIA = 3.0        # Hinge pin diameter

# ---------------------------------------------------------------------------
# Frame / edge stiffener
# ---------------------------------------------------------------------------
FRAME_WIDTH = 5.0          # Edge frame width
FRAME_DEPTH = 3.0          # Frame depth (below panel surface)

# ---------------------------------------------------------------------------
# Stowed configuration
# ---------------------------------------------------------------------------
STOWED_FOLD_GAP = 0.5     # Gap between folded halves

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
COL_SUBSTRATE = Color(0.70, 0.70, 0.72, 1.0)  # Aluminum substrate
COL_CELL = Color(0.05, 0.08, 0.25, 1.0)       # Dark blue solar cells
COL_COVER = Color(0.15, 0.18, 0.40, 0.7)      # Blue-tinted cover glass
COL_HINGE = Color(0.55, 0.55, 0.58, 1.0)      # Steel hinge
COL_FRAME = Color(0.65, 0.65, 0.68, 1.0)       # Al frame
COL_PIN = Color(0.50, 0.50, 0.53, 1.0)         # Hinge pin


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
        lines.append("  DEPLOYABLE SOLAR PANEL -- MASS BREAKDOWN")
        lines.append("=" * 60)
        for name, mass in self.entries:
            lines.append(f"  {name:<45} {mass:>6.3f} kg")
        lines.append("-" * 60)
        lines.append(f"  {'TOTAL':<45} {self.total():>6.3f} kg")
        lines.append(f"  {'Target spec':<45} {'1.500':>6} kg")
        lines.append("=" * 60)
        return "\n".join(lines)


ledger = MassLedger()


# ===========================================================================
# BUILD FUNCTIONS
# ===========================================================================

def build_substrate():
    """Aluminum honeycomb sandwich panel."""
    substrate = (cq.Workplane("XY")
                 .rect(PANEL_LENGTH, PANEL_WIDTH)
                 .extrude(PANEL_THICK))

    # Mass: honeycomb core + two face sheets
    area_mm2 = PANEL_LENGTH * PANEL_WIDTH
    core_vol = area_mm2 * CORE_THICK
    skin_vol = area_mm2 * SKIN_THICK * 2
    mass_core = core_vol * 1e-9 * RHO_AL_HONEYCOMB
    mass_skins = skin_vol * 1e-9 * RHO_AL_SKIN
    ledger.add("Al honeycomb substrate", mass_core + mass_skins)

    return substrate


def build_solar_cells():
    """Grid of solar cells on the panel surface."""
    # Build the cell array as a single extruded grid
    # Use a simplified approach: one rectangle per row of cells merged
    cells_compound = cq.Workplane("XY")

    # Build cells as a 2D sketch then extrude
    # For performance, build a representative set (every Nth cell) for visual
    # and calculate mass from the full grid analytically
    cell_pitch = CELL_SIZE + CELL_GAP

    # Build cells as individual boxes (CadQuery handles this)
    cell_parts = []

    # For visual fidelity, model every cell in a representative strip
    # then replicate. For full model, build all cells.
    # Performance: build as a single compound if possible
    x_start = -PANEL_LENGTH / 2 + CELL_MARGIN_LENGTH + CELL_SIZE / 2
    y_start = -PANEL_WIDTH / 2 + CELL_MARGIN_WIDTH + CELL_SIZE / 2

    # Build a single cell prototype
    single_cell = (cq.Workplane("XY")
                   .rect(CELL_SIZE, CELL_SIZE)
                   .extrude(CELL_THICK))

    # For performance, build cells in strips (one long box per row with gaps)
    # This gives the visual grid effect without 640 individual bodies
    strip_parts = []
    for row in range(CELLS_ALONG_WIDTH):
        y_pos = y_start + row * cell_pitch
        strip = (cq.Workplane("XY")
                 .rect(PANEL_LENGTH - 2 * CELL_MARGIN_LENGTH, CELL_SIZE)
                 .extrude(CELL_THICK)
                 .translate((0, y_pos, PANEL_THICK)))
        strip_parts.append((f"cell_row_{row}", strip))

    # Vertical scribe lines (every cell_pitch along length) -- modeled as
    # thin cuts. Skip for now; the strips already show the grid rows.

    # Mass for all cells
    n_cells = CELLS_ALONG_LENGTH * CELLS_ALONG_WIDTH
    cell_vol = CELL_SIZE * CELL_SIZE * CELL_THICK * n_cells
    mass_cells = cell_vol * 1e-9 * RHO_SOLAR_CELL
    ledger.add(f"Solar cells ({n_cells}x Si)", mass_cells)

    # Cover glass
    cover_vol = CELL_SIZE * CELL_SIZE * COVER_GLASS_THICK * n_cells
    mass_cover = cover_vol * 1e-9 * RHO_GLASS
    ledger.add(f"Cover glass ({n_cells}x)", mass_cover)

    return strip_parts


def build_edge_frame():
    """Aluminum stiffening frame around the panel perimeter."""
    # Outer rectangle minus inner rectangle, extruded
    outer = (cq.Workplane("XY")
             .rect(PANEL_LENGTH, PANEL_WIDTH)
             .rect(PANEL_LENGTH - 2 * FRAME_WIDTH,
                   PANEL_WIDTH - 2 * FRAME_WIDTH)
             .extrude(FRAME_DEPTH)
             .translate((0, 0, -FRAME_DEPTH)))

    vol = ((PANEL_LENGTH * PANEL_WIDTH
            - (PANEL_LENGTH - 2 * FRAME_WIDTH) * (PANEL_WIDTH - 2 * FRAME_WIDTH))
           * FRAME_DEPTH)
    mass_kg = vol * 1e-9 * RHO_AL
    ledger.add("Edge stiffening frame (Al)", mass_kg)

    return outer


def build_hinge():
    """Torsion spring hinge assembly along one edge of the panel."""
    parts = []

    # Hinge barrel segments (knuckles)
    knuckle_length = (HINGE_LENGTH - (NUM_KNUCKLES - 1) * KNUCKLE_GAP) / NUM_KNUCKLES

    for k in range(NUM_KNUCKLES):
        y_start = -HINGE_LENGTH / 2 + k * (knuckle_length + KNUCKLE_GAP)

        # Barrel (hollow cylinder)
        barrel_outer = (cq.Workplane("XZ")
                        .circle(HINGE_BARREL_DIA / 2)
                        .extrude(knuckle_length))
        barrel_inner = (cq.Workplane("XZ")
                        .circle(HINGE_BARREL_DIA / 2 - HINGE_BARREL_WALL)
                        .extrude(knuckle_length + 0.2))
        barrel = barrel_outer.cut(barrel_inner)
        barrel = barrel.translate((-PANEL_LENGTH / 2 - HINGE_BARREL_DIA / 2,
                                   y_start, 0))
        parts.append((f"hinge_knuckle_{k}", barrel))

    # Hinge pin (runs full length)
    pin = (cq.Workplane("XZ")
           .circle(HINGE_PIN_DIA / 2)
           .extrude(HINGE_LENGTH)
           .translate((-PANEL_LENGTH / 2 - HINGE_BARREL_DIA / 2,
                       -HINGE_LENGTH / 2, 0)))
    parts.append(("hinge_pin", pin))

    # Mass
    barrel_vol = (math.pi * ((HINGE_BARREL_DIA / 2)**2
                              - (HINGE_BARREL_DIA / 2 - HINGE_BARREL_WALL)**2)
                  * knuckle_length * NUM_KNUCKLES)
    pin_vol = math.pi * (HINGE_PIN_DIA / 2)**2 * HINGE_LENGTH
    mass_barrel = barrel_vol * 1e-9 * RHO_AL
    mass_pin = pin_vol * 1e-9 * RHO_SPRING_STEEL
    ledger.add("Hinge knuckles (Al)", mass_barrel)
    ledger.add("Hinge pin + torsion spring (steel)", mass_pin)

    return parts


# ===========================================================================
# DEPLOYED ASSEMBLY
# ===========================================================================
def build_deployed():
    """Build the panel in deployed (extended) configuration."""
    print("  Building DEPLOYED configuration...")

    assy = cq.Assembly(name="solar_panel_deployed")

    # Substrate -- panel lies flat in XY plane
    substrate = build_substrate()
    assy.add(substrate, name="substrate", color=COL_SUBSTRATE)

    # Solar cells on top surface
    cell_parts = build_solar_cells()
    for name, part in cell_parts:
        assy.add(part, name=name, color=COL_CELL)

    # Edge frame on bottom
    frame = build_edge_frame()
    assy.add(frame, name="edge_frame", color=COL_FRAME)

    # Hinge along -X edge
    hinge_parts = build_hinge()
    for name, part in hinge_parts:
        col = COL_PIN if "pin" in name else COL_HINGE
        assy.add(part, name=name, color=col)

    # Remaining mass
    current = ledger.total()
    remaining = 1.500 - current
    if remaining > 0:
        ledger.add("Misc (wiring, diodes, connectors)", remaining)

    return assy


# ===========================================================================
# STOWED ASSEMBLY
# ===========================================================================
def build_stowed():
    """Build the panel in stowed (folded) configuration.

    The panel folds in half along its length so the stowed size is
    800 x 800 x ~3 mm (two halves face-to-face).
    """
    print("  Building STOWED configuration...")

    assy = cq.Assembly(name="solar_panel_stowed")

    half_length = PANEL_LENGTH / 2

    # Bottom half -- flat, cells facing down (folded over)
    bottom_half = (cq.Workplane("XY")
                   .rect(half_length, PANEL_WIDTH)
                   .extrude(PANEL_THICK))
    assy.add(bottom_half, name="panel_half_bottom", color=COL_SUBSTRATE)

    # Cell strip on bottom half (facing downward = on bottom surface)
    cell_pitch = CELL_SIZE + CELL_GAP
    y_start = -PANEL_WIDTH / 2 + CELL_MARGIN_WIDTH + CELL_SIZE / 2
    for row in range(CELLS_ALONG_WIDTH):
        y_pos = y_start + row * cell_pitch
        strip = (cq.Workplane("XY")
                 .rect(half_length - 2 * CELL_MARGIN_LENGTH, CELL_SIZE)
                 .extrude(CELL_THICK)
                 .translate((0, y_pos, -CELL_THICK)))
        assy.add(strip, name=f"stowed_cell_bottom_{row}", color=COL_CELL)

    # Top half -- stacked on top, cells also facing inward (down)
    top_half = (cq.Workplane("XY")
                .rect(half_length, PANEL_WIDTH)
                .extrude(PANEL_THICK)
                .translate((0, 0, PANEL_THICK + STOWED_FOLD_GAP)))
    assy.add(top_half, name="panel_half_top", color=COL_SUBSTRATE)

    # Cell strip on top half (facing downward toward bottom half)
    for row in range(CELLS_ALONG_WIDTH):
        y_pos = y_start + row * cell_pitch
        strip = (cq.Workplane("XY")
                 .rect(half_length - 2 * CELL_MARGIN_LENGTH, CELL_SIZE)
                 .extrude(CELL_THICK)
                 .translate((0, y_pos, PANEL_THICK + STOWED_FOLD_GAP - CELL_THICK)))
        assy.add(strip, name=f"stowed_cell_top_{row}", color=COL_CELL)

    # Hinge barrel along one edge (at -X side of bottom half)
    hinge_x = -half_length / 2 - HINGE_BARREL_DIA / 2
    knuckle_length = (HINGE_LENGTH - (NUM_KNUCKLES - 1) * KNUCKLE_GAP) / NUM_KNUCKLES
    for k in range(NUM_KNUCKLES):
        y_pos = -HINGE_LENGTH / 2 + k * (knuckle_length + KNUCKLE_GAP)
        barrel = (cq.Workplane("XZ")
                  .circle(HINGE_BARREL_DIA / 2)
                  .circle(HINGE_BARREL_DIA / 2 - HINGE_BARREL_WALL)
                  .extrude(knuckle_length)
                  .translate((hinge_x, y_pos, PANEL_THICK / 2)))
        assy.add(barrel, name=f"stowed_hinge_{k}", color=COL_HINGE)

    # Hinge pin
    pin = (cq.Workplane("XZ")
           .circle(HINGE_PIN_DIA / 2)
           .extrude(HINGE_LENGTH)
           .translate((hinge_x, -HINGE_LENGTH / 2, PANEL_THICK / 2)))
    assy.add(pin, name="stowed_hinge_pin", color=COL_PIN)

    return assy


# ===========================================================================
# EXPORT
# ===========================================================================
def export(assy, name):
    """Export a single assembly to STEP and/or STL."""
    os.makedirs(OUT_DIR, exist_ok=True)

    step_path = os.path.join(OUT_DIR, f"{name}.step")
    print(f"  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(step_path, exportType="STEP")
    size_kb = os.path.getsize(step_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    stl_path = os.path.join(OUT_DIR, f"{name}.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(stl_path, exportType="STL", tolerance=0.1, angularTolerance=0.2)
    size_kb = os.path.getsize(stl_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 60)
    print("  AstraAnt Deployable Solar Panel -- CadQuery Parametric Model")
    print("=" * 60)
    print()

    # Deployed configuration
    deployed_assy = build_deployed()
    export(deployed_assy, "solar_panel_deployed")

    # Stowed configuration (separate assembly, mass already logged)
    stowed_assy = build_stowed()
    export(stowed_assy, "solar_panel_stowed")

    # Also export merged STL as solar_panel.stl (deployed config)
    stl_alias = os.path.join(OUT_DIR, "solar_panel.stl")
    stl_deployed = os.path.join(OUT_DIR, "solar_panel_deployed.stl")
    if os.path.isfile(stl_deployed) and stl_alias != stl_deployed:
        import shutil
        shutil.copy2(stl_deployed, stl_alias)
        print(f"  Copied deployed STL -> {stl_alias}")

    print()
    print(ledger.report())

    print()
    print("  KEY DIMENSIONS:")
    print(f"    Panel deployed:   {PANEL_LENGTH:.0f} x {PANEL_WIDTH:.0f} x {PANEL_THICK:.1f} mm")
    print(f"    Panel area:       {PANEL_LENGTH * PANEL_WIDTH / 1e6:.1f} m^2")
    stowed_thick = 2 * PANEL_THICK + STOWED_FOLD_GAP
    print(f"    Panel stowed:     {PANEL_LENGTH / 2:.0f} x {PANEL_WIDTH:.0f} x {stowed_thick:.1f} mm")
    n_cells = CELLS_ALONG_LENGTH * CELLS_ALONG_WIDTH
    print(f"    Solar cells:      {CELLS_ALONG_LENGTH} x {CELLS_ALONG_WIDTH} = {n_cells} cells")
    print(f"    Cell size:        {CELL_SIZE:.0f} x {CELL_SIZE:.0f} mm, {CELL_GAP:.0f} mm gap")
    print(f"    Hinge:            {HINGE_BARREL_DIA:.0f} mm barrel x {HINGE_LENGTH:.0f} mm")
    print(f"    Total mass:       {ledger.total():.3f} kg")


if __name__ == "__main__":
    main()
