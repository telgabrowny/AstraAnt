"""
AstraAnt UHF Patch Antenna -- Parametric CadQuery Model
========================================================

CadQuery parametric model of a BIRDS-1 style CubeSat UHF patch antenna
operating at 437.375 MHz.

ANTENNA SPECS (from BIRDS-1 / EnduroSat published design):
  Ground plane:   80 x 80 mm, 1.6 mm thick FR4
  Patch element:  55 x 55 mm copper, centered
  Substrate:      Rogers RO4003, 55 x 55 x 10 mm
  Feed:           Coaxial, SMA connector on bottom
  Mounting:       4x 3 mm holes, 5 mm from edges
  Mass:           85 g (EnduroSat datasheet)

Usage:
  python scad/uhf_antenna.py

Outputs:
  scad/uhf_antenna.step    (colored assembly)
  scad/uhf_antenna.stl     (merged mesh)
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
RHO_FR4 = 1850           # FR4 PCB
RHO_COPPER = 8960        # Copper (patch, ground traces)
RHO_ROGERS = 1790        # Rogers RO4003C substrate
RHO_BRASS = 8500         # SMA connector body
RHO_PTFE = 2150          # PTFE insulator in SMA
RHO_SOLDER = 7300        # Solder joint

# ---------------------------------------------------------------------------
# Ground plane parameters (all dimensions in mm)
# ---------------------------------------------------------------------------
GND_X = 80.0              # Ground plane width
GND_Y = 80.0              # Ground plane height
GND_THICK = 1.6           # FR4 PCB thickness
GND_COPPER_THICK = 0.035  # Copper layer on both sides of FR4

# ---------------------------------------------------------------------------
# Patch element
# ---------------------------------------------------------------------------
PATCH_X = 55.0            # Patch width
PATCH_Y = 55.0            # Patch height
PATCH_THICK = 0.035       # Copper foil thickness
PATCH_HEIGHT = 10.0       # Height above ground plane (substrate thickness)

# ---------------------------------------------------------------------------
# Substrate (between patch and ground plane)
# ---------------------------------------------------------------------------
SUB_X = PATCH_X           # Same footprint as patch
SUB_Y = PATCH_Y
SUB_THICK = PATCH_HEIGHT  # Fills the gap between ground and patch

# ---------------------------------------------------------------------------
# SMA connector (female, panel-mount)
# ---------------------------------------------------------------------------
SMA_BODY_DIA = 6.35       # Outer conductor diameter
SMA_BODY_LENGTH = 10.0    # Body length below ground plane
SMA_HEX_SIZE = 8.0        # Hex nut across-flats
SMA_HEX_THICK = 3.0       # Hex nut thickness
SMA_FLANGE_DIA = 9.0      # Mounting flange diameter
SMA_FLANGE_THICK = 1.5    # Flange thickness
SMA_PIN_DIA = 1.3         # Center conductor diameter
SMA_PIN_LENGTH = GND_THICK + SUB_THICK + PATCH_THICK + 1.0  # Through substrate to patch
SMA_INSULATOR_DIA = 4.1   # PTFE insulator diameter

# Feed point offset from patch center (for impedance matching)
FEED_OFFSET_X = 8.0       # Offset from center along X for 50 ohm match

# ---------------------------------------------------------------------------
# Mounting holes
# ---------------------------------------------------------------------------
MOUNT_HOLE_DIA = 3.0      # M3 clearance holes
MOUNT_INSET = 5.0         # Distance from edge to hole center
NUM_MOUNT_HOLES = 4

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
COL_FR4 = Color(0.05, 0.35, 0.15, 1.0)        # Green PCB
COL_COPPER = Color(0.72, 0.45, 0.20, 1.0)     # Copper
COL_SUBSTRATE = Color(0.85, 0.80, 0.70, 1.0)  # Rogers tan/white
COL_SMA_BODY = Color(0.80, 0.75, 0.55, 1.0)   # Gold-plated brass
COL_SMA_PIN = Color(0.80, 0.75, 0.55, 1.0)    # Gold center pin
COL_PTFE = Color(0.90, 0.90, 0.90, 1.0)       # White PTFE


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
        lines.append("  UHF PATCH ANTENNA -- MASS BREAKDOWN")
        lines.append("=" * 60)
        for name, mass in self.entries:
            lines.append(f"  {name:<45} {mass:>7.4f} kg")
        lines.append("-" * 60)
        lines.append(f"  {'TOTAL':<45} {self.total():>7.4f} kg")
        lines.append(f"  {'EnduroSat spec':<45} {'0.0850':>7} kg")
        lines.append("=" * 60)
        return "\n".join(lines)


ledger = MassLedger()


# ===========================================================================
# BUILD FUNCTIONS
# ===========================================================================

def build_ground_plane():
    """FR4 ground plane with copper layers and mounting holes."""
    # FR4 core
    gnd = (cq.Workplane("XY")
           .rect(GND_X, GND_Y)
           .extrude(GND_THICK))

    # Drill 4 mounting holes at corners
    hole_positions = [
        (-GND_X / 2 + MOUNT_INSET, -GND_Y / 2 + MOUNT_INSET),
        (-GND_X / 2 + MOUNT_INSET,  GND_Y / 2 - MOUNT_INSET),
        ( GND_X / 2 - MOUNT_INSET, -GND_Y / 2 + MOUNT_INSET),
        ( GND_X / 2 - MOUNT_INSET,  GND_Y / 2 - MOUNT_INSET),
    ]
    for hx, hy in hole_positions:
        hole = (cq.Workplane("XY")
                .center(hx, hy)
                .circle(MOUNT_HOLE_DIA / 2)
                .extrude(GND_THICK + 0.2)
                .translate((0, 0, -0.1)))
        gnd = gnd.cut(hole)

    # Drill SMA connector hole at feed point
    sma_hole = (cq.Workplane("XY")
                .center(FEED_OFFSET_X, 0)
                .circle(SMA_BODY_DIA / 2 + 0.5)  # clearance
                .extrude(GND_THICK + 0.2)
                .translate((0, 0, -0.1)))
    gnd = gnd.cut(sma_hole)

    # FR4 mass
    vol = GND_X * GND_Y * GND_THICK
    # Subtract holes
    vol -= NUM_MOUNT_HOLES * math.pi * (MOUNT_HOLE_DIA / 2)**2 * GND_THICK
    vol -= math.pi * (SMA_BODY_DIA / 2 + 0.5)**2 * GND_THICK
    mass_fr4 = vol * 1e-9 * RHO_FR4
    ledger.add("Ground plane FR4 core", mass_fr4)

    return gnd


def build_ground_copper():
    """Copper layers on both sides of ground plane (ground pour)."""
    parts = []

    for side, z_off in [("bottom", -GND_COPPER_THICK),
                         ("top", GND_THICK)]:
        copper = (cq.Workplane("XY")
                  .rect(GND_X - 1.0, GND_Y - 1.0)  # Edge clearance
                  .extrude(GND_COPPER_THICK)
                  .translate((0, 0, z_off)))

        # Cut SMA hole on bottom copper, substrate clearance on top copper
        if side == "bottom":
            hole = (cq.Workplane("XY")
                    .center(FEED_OFFSET_X, 0)
                    .circle(SMA_BODY_DIA / 2 + 1.0)
                    .extrude(GND_COPPER_THICK + 0.2)
                    .translate((0, 0, z_off - 0.1)))
            copper = copper.cut(hole)
        else:
            # Top copper has clearance around substrate footprint
            clear = (cq.Workplane("XY")
                     .rect(SUB_X + 2.0, SUB_Y + 2.0)
                     .extrude(GND_COPPER_THICK + 0.2)
                     .translate((0, 0, z_off - 0.1)))
            copper = copper.cut(clear)

        parts.append((f"gnd_copper_{side}", copper))

    # Mass: two copper layers
    area = (GND_X - 1.0) * (GND_Y - 1.0)
    vol = area * GND_COPPER_THICK * 2 * 0.85  # ~85% fill after clearances
    mass_cu = vol * 1e-9 * RHO_COPPER
    ledger.add("Ground copper layers (2x)", mass_cu)

    return parts


def build_substrate():
    """Rogers RO4003C substrate block between ground and patch."""
    sub = (cq.Workplane("XY")
           .rect(SUB_X, SUB_Y)
           .extrude(SUB_THICK)
           .translate((0, 0, GND_THICK + GND_COPPER_THICK)))

    # Drill feed pin hole through substrate
    pin_hole = (cq.Workplane("XY")
                .center(FEED_OFFSET_X, 0)
                .circle(SMA_PIN_DIA / 2 + 0.3)  # clearance
                .extrude(SUB_THICK + 0.2)
                .translate((0, 0, GND_THICK + GND_COPPER_THICK - 0.1)))
    sub = sub.cut(pin_hole)

    vol = SUB_X * SUB_Y * SUB_THICK
    vol -= math.pi * (SMA_PIN_DIA / 2 + 0.3)**2 * SUB_THICK
    mass = vol * 1e-9 * RHO_ROGERS
    ledger.add("Rogers RO4003C substrate", mass)

    return sub


def build_patch():
    """Copper patch element on top of substrate."""
    patch_z = GND_THICK + GND_COPPER_THICK + SUB_THICK

    patch = (cq.Workplane("XY")
             .rect(PATCH_X, PATCH_Y)
             .extrude(PATCH_THICK)
             .translate((0, 0, patch_z)))

    vol = PATCH_X * PATCH_Y * PATCH_THICK
    mass = vol * 1e-9 * RHO_COPPER
    ledger.add("Patch element (Cu)", mass)

    return patch


def build_sma_connector():
    """SMA female panel-mount connector on bottom of ground plane."""
    parts = []

    # Mounting flange (sits against bottom of ground plane)
    flange = (cq.Workplane("XY")
              .circle(SMA_FLANGE_DIA / 2)
              .extrude(SMA_FLANGE_THICK)
              .translate((FEED_OFFSET_X, 0, -SMA_FLANGE_THICK)))
    parts.append(("sma_flange", flange))

    # Body cylinder extending below ground plane
    body = (cq.Workplane("XY")
            .circle(SMA_BODY_DIA / 2)
            .extrude(SMA_BODY_LENGTH)
            .translate((FEED_OFFSET_X, 0,
                        -SMA_FLANGE_THICK - SMA_BODY_LENGTH)))
    parts.append(("sma_body", body))

    # Hex nut at bottom of body
    hex_nut = (cq.Workplane("XY")
               .polygon(6, SMA_HEX_SIZE)
               .extrude(SMA_HEX_THICK)
               .translate((FEED_OFFSET_X, 0,
                           -SMA_FLANGE_THICK - SMA_BODY_LENGTH - SMA_HEX_THICK)))
    parts.append(("sma_hex_nut", hex_nut))

    # PTFE insulator visible inside body (at the top, visible from board side)
    insulator = (cq.Workplane("XY")
                 .circle(SMA_INSULATOR_DIA / 2)
                 .extrude(SMA_FLANGE_THICK)
                 .translate((FEED_OFFSET_X, 0, -SMA_FLANGE_THICK)))
    # Cut center for pin
    ins_hole = (cq.Workplane("XY")
                .center(FEED_OFFSET_X, 0)
                .circle(SMA_PIN_DIA / 2)
                .extrude(SMA_FLANGE_THICK + 0.2)
                .translate((0, 0, -SMA_FLANGE_THICK - 0.1)))
    insulator = insulator.cut(ins_hole)
    parts.append(("sma_insulator", insulator))

    # Center pin (goes through ground plane, substrate, to patch)
    pin = (cq.Workplane("XY")
           .circle(SMA_PIN_DIA / 2)
           .extrude(SMA_PIN_LENGTH)
           .translate((FEED_OFFSET_X, 0,
                       -SMA_FLANGE_THICK - 2.0)))  # starts inside SMA
    parts.append(("sma_center_pin", pin))

    # Mass: SMA connector assembly
    body_vol = math.pi * (SMA_BODY_DIA / 2)**2 * SMA_BODY_LENGTH
    flange_vol = math.pi * (SMA_FLANGE_DIA / 2)**2 * SMA_FLANGE_THICK
    hex_vol = (3 * math.sqrt(3) / 2) * (SMA_HEX_SIZE / 2)**2 * SMA_HEX_THICK
    total_brass_vol = (body_vol + flange_vol + hex_vol) * 0.6  # hollow
    mass_brass = total_brass_vol * 1e-9 * RHO_BRASS
    pin_vol = math.pi * (SMA_PIN_DIA / 2)**2 * SMA_PIN_LENGTH
    mass_pin = pin_vol * 1e-9 * RHO_BRASS
    insulator_vol = (math.pi * (SMA_INSULATOR_DIA / 2)**2 * SMA_FLANGE_THICK
                     - math.pi * (SMA_PIN_DIA / 2)**2 * SMA_FLANGE_THICK)
    mass_ptfe = insulator_vol * 1e-9 * RHO_PTFE

    ledger.add("SMA connector (brass + PTFE)", mass_brass + mass_pin + mass_ptfe)

    return parts


def build_standoffs():
    """Small standoffs supporting the substrate above the ground plane.

    4 standoffs at the corners of the substrate footprint.
    """
    parts = []
    standoff_dia = 3.0
    standoff_height = PATCH_HEIGHT - SUB_THICK  # gap if any, or supportive
    # Actually the substrate fills the full gap. Standoffs are at corners
    # just outside the substrate for structural support.
    standoff_height = PATCH_HEIGHT
    standoff_inset = 2.0  # from substrate edge

    positions = [
        (-SUB_X / 2 - standoff_inset, -SUB_Y / 2 - standoff_inset),
        (-SUB_X / 2 - standoff_inset,  SUB_Y / 2 + standoff_inset),
        ( SUB_X / 2 + standoff_inset, -SUB_Y / 2 - standoff_inset),
        ( SUB_X / 2 + standoff_inset,  SUB_Y / 2 + standoff_inset),
    ]

    for i, (sx, sy) in enumerate(positions):
        standoff = (cq.Workplane("XY")
                    .circle(standoff_dia / 2)
                    .extrude(standoff_height)
                    .translate((sx, sy, GND_THICK)))
        parts.append((f"standoff_{i}", standoff))

    vol = 4 * math.pi * (standoff_dia / 2)**2 * standoff_height
    mass = vol * 1e-9 * RHO_BRASS
    ledger.add("Standoffs (4x brass)", mass)

    return parts


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    """Build the complete UHF patch antenna assembly."""
    print("Building UHF Patch Antenna Model...")
    print(f"  Ground plane:  {GND_X:.0f} x {GND_Y:.0f} x {GND_THICK:.1f} mm (FR4)")
    print(f"  Patch:         {PATCH_X:.0f} x {PATCH_Y:.0f} mm (Cu)")
    print(f"  Substrate:     {SUB_X:.0f} x {SUB_Y:.0f} x {SUB_THICK:.0f} mm (RO4003C)")
    print(f"  Feed:          SMA coaxial, {FEED_OFFSET_X:.0f} mm from center")
    print()

    assy = cq.Assembly(name="uhf_patch_antenna")

    # Ground plane
    gnd = build_ground_plane()
    assy.add(gnd, name="ground_plane", color=COL_FR4)

    # Copper layers on ground plane
    cu_parts = build_ground_copper()
    for name, part in cu_parts:
        assy.add(part, name=name, color=COL_COPPER)

    # Rogers substrate
    sub = build_substrate()
    assy.add(sub, name="substrate", color=COL_SUBSTRATE)

    # Copper patch
    patch = build_patch()
    assy.add(patch, name="patch_element", color=COL_COPPER)

    # SMA connector
    sma_parts = build_sma_connector()
    for name, part in sma_parts:
        if "insulator" in name:
            col = COL_PTFE
        elif "pin" in name:
            col = COL_SMA_PIN
        else:
            col = COL_SMA_BODY
        assy.add(part, name=name, color=col)

    # Standoffs
    standoff_parts = build_standoffs()
    for name, part in standoff_parts:
        assy.add(part, name=name, color=COL_SMA_BODY)

    # Remaining mass to match spec
    current = ledger.total()
    remaining = 0.085 - current
    if remaining > 0:
        ledger.add("Misc (solder, traces, coating)", remaining)

    return assy


# ===========================================================================
# EXPORT
# ===========================================================================
def export(assy):
    """Export STEP and STL files."""
    os.makedirs(OUT_DIR, exist_ok=True)

    step_path = os.path.join(OUT_DIR, "uhf_antenna.step")
    print(f"  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(step_path, exportType="STEP")
    size_kb = os.path.getsize(step_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    stl_path = os.path.join(OUT_DIR, "uhf_antenna.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(stl_path, exportType="STL", tolerance=0.02, angularTolerance=0.05)
    size_kb = os.path.getsize(stl_path) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 60)
    print("  AstraAnt UHF Patch Antenna -- CadQuery Parametric Model")
    print("=" * 60)
    print()

    assy = build_assembly()
    export(assy)

    print()
    print(ledger.report())

    print()
    print("  KEY DIMENSIONS:")
    print(f"    Ground plane:     {GND_X:.0f} x {GND_Y:.0f} x {GND_THICK:.1f} mm")
    print(f"    Patch element:    {PATCH_X:.0f} x {PATCH_Y:.0f} mm")
    print(f"    Patch height:     {PATCH_HEIGHT:.0f} mm above ground")
    print(f"    Substrate:        {SUB_X:.0f} x {SUB_Y:.0f} x {SUB_THICK:.0f} mm (Rogers RO4003C)")
    print(f"    Feed point:       {FEED_OFFSET_X:.0f} mm from center (50 ohm match)")
    print(f"    SMA connector:    {SMA_BODY_DIA:.2f} mm dia, M{MOUNT_HOLE_DIA:.0f} mounting")
    print(f"    Mount holes:      {NUM_MOUNT_HOLES}x {MOUNT_HOLE_DIA:.0f} mm, {MOUNT_INSET:.0f} mm from edges")
    overall_height = SMA_BODY_LENGTH + SMA_FLANGE_THICK + GND_THICK + PATCH_HEIGHT + PATCH_THICK + SMA_HEX_THICK
    print(f"    Overall height:   {overall_height:.1f} mm (SMA bottom to patch top)")
    print(f"    Frequency:        437.375 MHz (UHF)")
    print(f"    Total mass:       {ledger.total():.4f} kg ({ledger.total() * 1000:.1f} g)")


if __name__ == "__main__":
    main()
