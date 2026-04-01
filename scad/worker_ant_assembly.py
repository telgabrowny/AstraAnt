"""
AstraAnt Worker Ant -- Parametric Assembly for Ansys Analysis
==============================================================

CadQuery parametric model of the 8-legged worker ant.
Engineering-grade: every part at its real position with real clearances.

VEHICLE SPECS:
  Thorax:    55 x 35 x 20 mm (PETG prototype)
  Abdomen:   45 x 30 x 18 mm (material hopper mount)
  Head:      18 mm dome + 2x mandible arms
  Legs:      8x (4 pairs), SG90 servo-driven
  Mandibles: 2x SG51R micro servos
  Brain:     RP2040 Pico (not ESP32 -- worker is simpler)
  Power:     Supercapacitor 10F/5.5V (no tether -- rail contact)
  Total:     ~120 g

Dimensions from:
  worker_chassis.scad        -- OpenSCAD reference (all in mm)
  worker_ant_8leg.xml        -- MuJoCo model (verified physics)

Usage:
  python scad/worker_ant_assembly.py

Outputs:
  scad/worker_ant_assembly.step    (color-coded assembly)
  scad/worker_ant_assembly.stl     (merged mesh)
  scad/worker_ant_chassis.step     (just the chassis -- 3D printable)
  scad/worker_ant_chassis.stl      (chassis STL for slicing)
"""

import os
import sys
import math
import warnings

import cadquery as cq
from cadquery import importers, Color

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_RAW = os.path.join(SCRIPT_DIR, "vendor_parts", "raw")
OUT_DIR = SCRIPT_DIR  # outputs go alongside the script

SG90_STEP = os.path.join(VENDOR_RAW, "sg90",
                         "SG90 - Micro Servo 9g - Tower Pro.STEP")
PICO_STEP = os.path.join(VENDOR_RAW, "pico", "Pico-R3.step")

# ---------------------------------------------------------------------------
# Material densities (kg/m^3)
# ---------------------------------------------------------------------------
RHO_PETG = 1270       # PETG filament
RHO_NDFEB = 7500      # N52 NdFeB magnet
RHO_PCB = 1850        # FR4 PCB

# ---------------------------------------------------------------------------
# SG90 Micro Servo -- real datasheet dimensions (mm)
# ---------------------------------------------------------------------------
SG90_L = 22.5       # length (along output shaft axis)
SG90_W = 12.2       # width
SG90_H = 22.7       # height (including mounting tabs)
SG90_TAB_H = 16.0   # height to bottom of mounting tabs
SG90_TAB_T = 2.5    # tab thickness
SG90_TAB_W = 32.5   # tab tip-to-tip width
SG90_SHAFT_D = 4.8  # output shaft diameter
SG90_SHAFT_H = 3.5  # shaft protrusion above body
SG90_CLEARANCE = 0.3  # press-fit clearance per side

# ---------------------------------------------------------------------------
# SG51R Micro Servo -- mandible servos (mm)
# ---------------------------------------------------------------------------
SG51_L = 16.0
SG51_W = 8.0
SG51_H = 12.0

# ---------------------------------------------------------------------------
# RP2040 Pico module dimensions (mm)
# ---------------------------------------------------------------------------
PICO_L = 51.0
PICO_W = 21.0
PICO_H = 3.5        # PCB + components height

# ---------------------------------------------------------------------------
# Thorax (main chassis body) -- from worker_chassis.scad
# ---------------------------------------------------------------------------
THORAX_L = 55.0     # length (X)
THORAX_W = 35.0     # width (Y)
THORAX_H = 20.0     # height (Z)
WALL = 2.0          # wall thickness

# ---------------------------------------------------------------------------
# Abdomen (rear body section)
# ---------------------------------------------------------------------------
ABDOMEN_L = 45.0    # length (X)
ABDOMEN_W = 30.0    # width (Y)
ABDOMEN_H = 18.0    # height (Z)

# ---------------------------------------------------------------------------
# Head dome
# ---------------------------------------------------------------------------
HEAD_D = 18.0       # head dome diameter

# ---------------------------------------------------------------------------
# Leg geometry -- from MuJoCo model
# ---------------------------------------------------------------------------
N_LEG_PAIRS = 4
# Pair x-positions from MuJoCo model (in mm, from thorax center)
# MuJoCo: +0.018, +0.006, -0.006, -0.018 (meters -> mm)
LEG_PAIR_X = [18.0, 6.0, -6.0, -18.0]
# Hip Y position (center of servo, from MuJoCo: 17.5mm from centerline)
HIP_Y = 17.5
# Hip Z offset below thorax center (from MuJoCo: -5mm)
HIP_Z = -5.0
# Leg segment dimensions (from MuJoCo capsule endpoints)
# MuJoCo: fromto="0 0 0  0 0.0725 -0.035" -> dy=72.5mm, dz=-35mm
LEG_UPPER_L = 20.0   # coxa length (horizontal)
LEG_LOWER_L = 25.0   # femur length (angled down)
LEG_DIA = 3.0        # leg rod diameter (MuJoCo: size="0.003" = 3mm radius -> 6mm dia, but that is the capsule half-width; rod is 3mm dia visual)
LEG_DY = 72.5        # lateral extension from hip to foot
LEG_DZ = -35.0       # vertical drop from hip to foot

# ---------------------------------------------------------------------------
# Foot pad
# ---------------------------------------------------------------------------
FOOT_PAD_D = 8.0
FOOT_PAD_H = 3.0
MAG_D = 6.0
MAG_H = 2.0
SPINE_COUNT = 8
SPINE_HOLE_D = 0.4
SPINE_RING_R = 2.8
SPINE_ANGLE = 30.0   # degrees inward from vertical

# ---------------------------------------------------------------------------
# Mandible geometry -- from worker_chassis.scad
# ---------------------------------------------------------------------------
MANDIBLE_LENGTH = 35.0
MANDIBLE_SPACING = 20.0   # distance between mandible tips
MANDIBLE_ARM_DIA = 4.0    # arm cross-section diameter
MANDIBLE_TIP_D = 6.0      # tip sphere diameter

# ---------------------------------------------------------------------------
# Magnetic tool mount
# ---------------------------------------------------------------------------
TOOL_MAGNET_D = 4.0
TOOL_MAGNET_DEPTH = 2.0

# ---------------------------------------------------------------------------
# Drill head (front-mounted payload)
# ---------------------------------------------------------------------------
DRILL_MOUNT_L = 14.0
DRILL_MOUNT_W = 10.0
DRILL_MOUNT_H = 10.0
DRILL_BIT_D = 4.0
DRILL_BIT_L = 18.0
DRILL_MOTOR_D = 8.0
DRILL_MOTOR_H = 14.0

# ---------------------------------------------------------------------------
# Material hopper (abdomen-mounted)
# ---------------------------------------------------------------------------
HOPPER_L = 30.0
HOPPER_W = 20.0
HOPPER_H = 14.0
HOPPER_WALL = 1.5

# ---------------------------------------------------------------------------
# Supercapacitor (10F / 5.5V coin cell type)
# ---------------------------------------------------------------------------
SUPERCAP_D = 21.5    # typical 10F 5.5V coin supercap
SUPERCAP_H = 7.5

# ---------------------------------------------------------------------------
# Grip socket (rear, for ant-to-ant chaining)
# ---------------------------------------------------------------------------
GRIP_GROOVE_W = 3.0
GRIP_GROOVE_DEPTH = 1.5
GRIP_GROOVE_SPACING = 10.0

# ---------------------------------------------------------------------------
# Color palette (subsystem coding)
# ---------------------------------------------------------------------------
COL_CHASSIS   = Color(0.92, 0.55, 0.12, 1.0)   # worker orange
COL_ABDOMEN   = Color(0.78, 0.42, 0.08, 1.0)   # abdomen darker orange
COL_HEAD      = Color(0.85, 0.45, 0.10, 1.0)   # head orange
COL_SERVO     = Color(0.20, 0.40, 0.80, 1.0)   # SG90 blue
COL_SERVO_SM  = Color(0.25, 0.50, 0.85, 1.0)   # SG51R lighter blue
COL_LEG       = Color(0.60, 0.30, 0.05, 1.0)   # leg brown
COL_FOOT      = Color(0.20, 0.20, 0.22, 1.0)   # foot pad dark
COL_MAGNET    = Color(0.75, 0.75, 0.78, 1.0)   # NdFeB silver
COL_PCB       = Color(0.10, 0.50, 0.15, 1.0)   # PCB green
COL_MANDIBLE  = Color(0.70, 0.35, 0.05, 1.0)   # mandible brown
COL_DRILL     = Color(0.50, 0.50, 0.55, 1.0)   # drill steel gray
COL_MOTOR     = Color(0.40, 0.40, 0.45, 1.0)   # motor dark gray
COL_HOPPER    = Color(0.65, 0.67, 0.72, 1.0)   # hopper light gray
COL_SUPERCAP  = Color(0.30, 0.30, 0.32, 1.0)   # supercap black

# ---------------------------------------------------------------------------
# Mass ledger -- every component tracked
# ---------------------------------------------------------------------------
class MassLedger:
    """Track every component mass, position, and subsystem."""
    def __init__(self):
        self.entries = []  # (name, subsystem, mass_g, x, y, z)

    def add(self, name, subsys, mass_g, x, y, z):
        self.entries.append((name, subsys, mass_g, x, y, z))

    def total_mass_g(self):
        return sum(e[2] for e in self.entries)

    def center_of_mass(self):
        m_tot = self.total_mass_g()
        if m_tot == 0:
            return (0.0, 0.0, 0.0)
        cx = sum(e[2] * e[3] for e in self.entries) / m_tot
        cy = sum(e[2] * e[4] for e in self.entries) / m_tot
        cz = sum(e[2] * e[5] for e in self.entries) / m_tot
        return (cx, cy, cz)

    def report(self):
        lines = []
        lines.append("=" * 80)
        lines.append("  WORKER ANT ASSEMBLY -- MASS PROPERTIES REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Group by subsystem
        subsystems = {}
        for name, subsys, mass, x, y, z in self.entries:
            if subsys not in subsystems:
                subsystems[subsys] = []
            subsystems[subsys].append((name, mass, x, y, z))

        for subsys in sorted(subsystems.keys()):
            items = subsystems[subsys]
            sub_mass = sum(m for _, m, _, _, _ in items)
            lines.append(f"--- {subsys} ({sub_mass:.1f} g) ---")
            for name, mass, x, y, z in items:
                lines.append(
                    f"  {name:<40} {mass:>6.1f} g  "
                    f"@ ({x:>7.1f}, {y:>7.1f}, {z:>7.1f}) mm"
                )
            lines.append("")

        m_tot = self.total_mass_g()
        cx, cy, cz = self.center_of_mass()

        lines.append("=" * 80)
        lines.append(f"  TOTAL MASS:         {m_tot:.1f} g")
        lines.append(f"  CENTER OF MASS:     ({cx:.1f}, {cy:.1f}, {cz:.1f}) mm")
        lines.append(f"  GEOMETRIC CENTER:   (0.0, 0.0, 0.0) mm (thorax center)")
        lines.append(f"  CoM OFFSET:         "
                     f"dX={cx:.1f}  dY={cy:.1f}  dZ={cz:.1f} mm")
        lines.append("")

        # Check symmetry (Y should be ~0 for left/right balance)
        if abs(cy) > 1.0:
            lines.append(f"  WARNING: CoM Y-offset {cy:.1f} mm -- left/right imbalance")
        else:
            lines.append(f"  OK: CoM Y-offset {cy:.1f} mm -- symmetric")

        # Check mass target
        if abs(m_tot - 120) > 10:
            lines.append(
                f"  WARNING: Total mass {m_tot:.1f} g deviates from 120 g target"
            )
        else:
            lines.append(f"  OK: Total mass {m_tot:.1f} g within 10 g of 120 g target")

        lines.append("=" * 80)
        return "\n".join(lines)


ledger = MassLedger()

# ---------------------------------------------------------------------------
# Vendor STEP import helpers
# ---------------------------------------------------------------------------
_sg90_cache = None
_pico_cache = None


def load_sg90():
    """Import the real SG90 STEP file, scale to mm if needed.
    Returns a Workplane/Shape. Cached after first load."""
    global _sg90_cache
    if _sg90_cache is not None:
        return _sg90_cache

    if not os.path.isfile(SG90_STEP):
        print(f"  WARN: SG90 STEP not found at {SG90_STEP}, using parametric box")
        _sg90_cache = _make_sg90_parametric()
        return _sg90_cache

    try:
        print(f"  Loading SG90 STEP: {SG90_STEP}")
        raw = importers.importStep(SG90_STEP)
        # Check bounding box to determine scale
        bb = raw.val().BoundingBox()
        dx = bb.xmax - bb.xmin
        dy = bb.ymax - bb.ymin
        dz = bb.zmax - bb.zmin
        dims = sorted([dx, dy, dz])
        print(f"    Raw BB: {dx:.2f} x {dy:.2f} x {dz:.2f}")

        # Expected SG90 smallest dim ~12.2mm (width), mid ~22.5mm, largest ~22.7mm
        expected_smallest = 12.2
        scale = 1.0
        if dims[0] < 1.0:
            # Probably in meters, scale to mm
            scale = 1000.0
            print(f"    Detected meters, scaling by {scale}x")
        elif dims[0] > 100:
            # Probably in mils or 1000x too large
            scale = expected_smallest / dims[0]
            print(f"    Detected oversized, scaling by {scale:.4f}x")
        elif abs(dims[0] - expected_smallest) / expected_smallest > 0.5:
            # Try inches -> mm
            if abs(dims[0] * 25.4 - expected_smallest) / expected_smallest < 0.3:
                scale = 25.4
                print(f"    Detected inches, scaling by {scale}x")

        if abs(scale - 1.0) > 0.001:
            raw = raw.val().scale(scale)
            raw = cq.Workplane("XY").add(raw)
            bb = raw.val().BoundingBox()
            dx = bb.xmax - bb.xmin
            dy = bb.ymax - bb.ymin
            dz = bb.zmax - bb.zmin
            print(f"    Scaled BB: {dx:.2f} x {dy:.2f} x {dz:.2f}")

        # Center the servo at origin
        cx = (bb.xmax + bb.xmin) / 2
        cy = (bb.ymax + bb.ymin) / 2
        cz = (bb.zmax + bb.zmin) / 2
        raw = raw.translate((-cx, -cy, -cz))

        _sg90_cache = raw
        return _sg90_cache
    except Exception as e:
        print(f"  WARN: SG90 STEP import failed: {e}")
        print(f"         Using parametric box fallback")
        _sg90_cache = _make_sg90_parametric()
        return _sg90_cache


def _make_sg90_parametric():
    """Parametric SG90 model matching datasheet dimensions."""
    body = cq.Workplane("XY").box(SG90_L, SG90_W, SG90_TAB_H)

    # Mounting tabs
    tab_z = SG90_TAB_H / 2 - SG90_TAB_T / 2
    tabs = (cq.Workplane("XY")
            .box(SG90_TAB_W, SG90_W, SG90_TAB_T)
            .translate((0, 0, tab_z)))
    body = body.union(tabs)

    # Top cap above tabs
    cap_h = SG90_H - SG90_TAB_H
    cap = (cq.Workplane("XY")
           .box(SG90_L, SG90_W, cap_h)
           .translate((0, 0, SG90_TAB_H / 2 + cap_h / 2)))
    body = body.union(cap)

    # Output shaft
    shaft = (cq.Workplane("XY")
             .circle(SG90_SHAFT_D / 2)
             .extrude(SG90_SHAFT_H)
             .translate((SG90_L / 2 - 5.5, 0, SG90_H / 2)))
    body = body.union(shaft)

    return body


def load_pico():
    """Import the real RP2040 Pico STEP file. Cached after first load."""
    global _pico_cache
    if _pico_cache is not None:
        return _pico_cache

    if not os.path.isfile(PICO_STEP):
        print(f"  WARN: Pico STEP not found at {PICO_STEP}, using parametric box")
        _pico_cache = _make_pico_parametric()
        return _pico_cache

    try:
        print(f"  Loading Pico STEP: {PICO_STEP}")
        raw = importers.importStep(PICO_STEP)
        bb = raw.val().BoundingBox()
        dx = bb.xmax - bb.xmin
        dy = bb.ymax - bb.ymin
        dz = bb.zmax - bb.zmin
        dims = sorted([dx, dy, dz])
        print(f"    Raw BB: {dx:.2f} x {dy:.2f} x {dz:.2f}")

        # Expected Pico: 51 x 21 x ~3.5mm
        expected_mid = 21.0
        scale = 1.0
        if dims[1] < 1.0:
            scale = 1000.0
            print(f"    Detected meters, scaling by {scale}x")
        elif dims[1] > 100:
            scale = expected_mid / dims[1]
            print(f"    Detected oversized, scaling by {scale:.4f}x")

        if abs(scale - 1.0) > 0.001:
            raw = raw.val().scale(scale)
            raw = cq.Workplane("XY").add(raw)
            bb = raw.val().BoundingBox()
            dx = bb.xmax - bb.xmin
            dy = bb.ymax - bb.ymin
            dz = bb.zmax - bb.zmin
            print(f"    Scaled BB: {dx:.2f} x {dy:.2f} x {dz:.2f}")

        # Center at origin
        cx = (bb.xmax + bb.xmin) / 2
        cy = (bb.ymax + bb.ymin) / 2
        cz = (bb.zmax + bb.zmin) / 2
        raw = raw.translate((-cx, -cy, -cz))

        _pico_cache = raw
        return _pico_cache
    except Exception as e:
        print(f"  WARN: Pico STEP import failed: {e}")
        print(f"         Using parametric box fallback")
        _pico_cache = _make_pico_parametric()
        return _pico_cache


def _make_pico_parametric():
    """Parametric RP2040 Pico matching real dimensions."""
    # PCB board
    pcb = (cq.Workplane("XY")
           .box(PICO_L, PICO_W, 1.0))

    # RP2040 chip (QFN-56, 7x7mm, centered)
    chip = (cq.Workplane("XY")
            .box(7.0, 7.0, 1.0)
            .translate((0, 0, 1.0)))
    pcb = pcb.union(chip)

    # USB connector (micro USB, at one end)
    usb = (cq.Workplane("XY")
           .box(7.5, 5.5, 2.5)
           .translate((PICO_L / 2 - 3.75, 0, 1.25)))
    pcb = pcb.union(usb)

    # Pin headers (two rows along the long edges)
    for side in (-1, 1):
        pins = (cq.Workplane("XY")
                .box(PICO_L - 6, 2.54, 2.5)
                .translate((0, side * (PICO_W / 2 - 1.27), -1.25)))
        pcb = pcb.union(pins)

    return pcb


# ---------------------------------------------------------------------------
# CHASSIS -- the 3D-printable frame (thorax + head dome + abdomen bridge)
# ---------------------------------------------------------------------------
def build_chassis():
    """Build the thorax frame with servo pockets, wire channels,
    electronics bay, head dome, and abdomen.
    Designed to be 3D-printable."""

    # === THORAX ===
    thorax = (cq.Workplane("XY")
              .box(THORAX_L, THORAX_W, THORAX_H)
              .edges("|Z")
              .fillet(4.0)
              .edges("|X")
              .fillet(2.0))

    # Hollow out interior (shell)
    inner = (cq.Workplane("XY")
             .box(THORAX_L - 2 * WALL,
                  THORAX_W - 2 * WALL,
                  THORAX_H - 2 * WALL))
    thorax = thorax.cut(inner)

    # ---- 8 Servo pockets (4 pairs along the body) ----
    c = SG90_CLEARANCE
    for i, x_pos in enumerate(LEG_PAIR_X):
        for side in (-1, 1):
            pocket_y = side * (THORAX_W / 2 - SG90_W / 2 + 0.5)
            pocket_z = HIP_Z

            # Main body pocket
            pocket = (cq.Workplane("XY")
                      .box(SG90_L + c * 2, SG90_W + c * 2, SG90_TAB_H + c * 2)
                      .translate((x_pos, pocket_y, pocket_z)))
            thorax = thorax.cut(pocket)

            # Tab slot
            tab_slot = (cq.Workplane("XY")
                        .box(SG90_TAB_W + c * 2,
                             SG90_W + c * 2,
                             SG90_TAB_T + c * 2)
                        .translate((x_pos, pocket_y,
                                    pocket_z + SG90_TAB_H / 2 - SG90_TAB_T / 2)))
            thorax = thorax.cut(tab_slot)

            # Wire exit hole at bottom of pocket
            wire_hole = (cq.Workplane("XY")
                         .circle(2.0)
                         .extrude(WALL + 2)
                         .translate((x_pos, pocket_y,
                                     pocket_z - SG90_TAB_H / 2 - 1)))
            thorax = thorax.cut(wire_hole)

    # ---- Wire routing channel (main trunk along X inside bottom wall) ----
    wire_channel = (cq.Workplane("XZ")
                    .rect(THORAX_L - 4, 2.5)
                    .extrude(2.0)
                    .translate((0, 0, -THORAX_H / 2 + WALL / 2)))
    thorax = thorax.cut(wire_channel)

    # ---- Electronics bay (top, for RP2040 Pico: 51x21mm) ----
    # Centered on thorax top
    ebay = (cq.Workplane("XY")
            .box(PICO_L + 2, PICO_W + 2, PICO_H + 2)
            .translate((0, 0, THORAX_H / 2 - PICO_H / 2 - 0.5)))
    thorax = thorax.cut(ebay)

    # M2 screw bosses for Pico (4 corners)
    for boss_x_off in (-20, 20):
        for boss_y_off in (-8, 8):
            boss = (cq.Workplane("XY")
                    .circle(2.0)
                    .extrude(PICO_H + 2)
                    .translate((boss_x_off, boss_y_off,
                                THORAX_H / 2 - PICO_H - 1.5)))
            thorax = thorax.union(boss)
            hole = (cq.Workplane("XY")
                    .circle(1.1)
                    .extrude(PICO_H + 4)
                    .translate((boss_x_off, boss_y_off,
                                THORAX_H / 2 - PICO_H - 2.5)))
            thorax = thorax.cut(hole)

    # === HEAD DOME (front of thorax) ===
    # From worker_chassis.scad: translate([thorax_length/2 + head_diameter/3, 0, 2])
    head_x = THORAX_L / 2 + HEAD_D / 3
    head = (cq.Workplane("XY")
            .sphere(HEAD_D / 2))
    head = head.translate((head_x, 0, 2))

    # Mandible servo pockets in head (2x SG51R)
    for side in (-1, 1):
        sg51_pocket = (cq.Workplane("XY")
                       .box(SG51_L + 0.3, SG51_W + 0.3, SG51_H + 0.3)
                       .translate((head_x + HEAD_D / 4,
                                   side * MANDIBLE_SPACING / 3, 0)))
        head = head.cut(sg51_pocket)

    # Sensor window (VL53L0x, front of head)
    sensor_window = (cq.Workplane("XY")
                     .box(3, 6, 6)
                     .translate((head_x + HEAD_D / 2 - 1, 0, 2)))
    head = head.cut(sensor_window)

    # Wire channel from head to thorax
    head_wire = (cq.Workplane("XY")
                 .circle(4)
                 .extrude(HEAD_D)
                 .translate((head_x - HEAD_D / 2, 0, -HEAD_D / 2 + 2)))
    head = head.cut(head_wire)

    thorax = thorax.union(head)

    # === ABDOMEN (rear body section) ===
    # From worker_chassis.scad: translate([-thorax_length/2 - abdomen_length/2 + 8, 0, -2])
    abd_x = -THORAX_L / 2 - ABDOMEN_L / 2 + 8
    abd_z = -2.0
    abdomen = (cq.Workplane("XY")
               .box(ABDOMEN_L, ABDOMEN_W, ABDOMEN_H)
               .edges("|Z")
               .fillet(5.0)
               .edges("|X")
               .fillet(2.0))

    # Hollow out abdomen
    abd_inner = (cq.Workplane("XY")
                 .box(ABDOMEN_L - 2 * WALL,
                      ABDOMEN_W - 2 * WALL,
                      ABDOMEN_H - 2 * WALL))
    abdomen = abdomen.cut(abd_inner)

    # Hopper mount holes (top, 2x M3)
    for hx in (-10, 10):
        hopper_hole = (cq.Workplane("XY")
                       .circle(1.6)
                       .extrude(5)
                       .translate((hx, 0, ABDOMEN_H / 2 - 2)))
        abdomen = abdomen.cut(hopper_hole)

    abdomen = abdomen.translate((abd_x, 0, abd_z))

    # ---- Grip socket on abdomen rear (for ant-to-ant chaining) ----
    abd_rear_x = abd_x - ABDOMEN_L / 2
    for g_off in (-GRIP_GROOVE_SPACING / 2, GRIP_GROOVE_SPACING / 2):
        groove = (cq.Workplane("YZ")
                  .rect(GRIP_GROOVE_W, ABDOMEN_H - 4)
                  .extrude(GRIP_GROOVE_DEPTH)
                  .translate((abd_rear_x, g_off, abd_z)))
        abdomen = abdomen.cut(groove)

    thorax = thorax.union(abdomen)

    # Log chassis mass
    ledger.add("Chassis (thorax frame)", "CHASSIS", 20.0, 0, 0, 0)
    ledger.add("Abdomen shell", "CHASSIS", 10.0, abd_x, 0, abd_z)
    ledger.add("Head dome", "CHASSIS", 5.0, head_x, 0, 2)

    return thorax


# ---------------------------------------------------------------------------
# LEGS (8x) -- upper + lower segments as cylinders
# ---------------------------------------------------------------------------
def build_legs():
    """Build 8 legs as upper (coxa) + lower (femur) cylinder segments.
    Returns list of (name, workplane) tuples."""
    parts = []

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            leg_name = f"leg_{pair_names[i]}{side_name}"

            hip_pos = (x_pos, side * HIP_Y, HIP_Z)
            foot_pos = (x_pos, side * (HIP_Y + LEG_DY), HIP_Z + LEG_DZ)

            # Knee position: end of upper leg (coxa extends laterally)
            knee_y = side * (HIP_Y + LEG_UPPER_L)
            knee_pos = (x_pos, knee_y, HIP_Z)

            # Upper leg (coxa): horizontal cylinder from hip outward
            upper = (cq.Workplane("XY")
                     .circle(LEG_DIA / 2)
                     .extrude(LEG_UPPER_L))
            if side == 1:
                upper = upper.translate((x_pos, HIP_Y, HIP_Z))
            else:
                upper = (upper.rotate((0, 0, 0), (0, 0, 1), 180)
                         .translate((x_pos, -HIP_Y, HIP_Z)))
            parts.append((f"upper_{leg_name}", upper))

            # Lower leg (femur): angled cylinder from knee to foot
            dy_lower = foot_pos[1] - knee_pos[1]
            dz_lower = foot_pos[2] - knee_pos[2]
            lower_len = math.sqrt(dy_lower ** 2 + dz_lower ** 2)
            angle_deg = math.degrees(math.atan2(-dz_lower, abs(dy_lower)))

            lower = (cq.Workplane("XY")
                     .circle(LEG_DIA / 2)
                     .extrude(lower_len))

            if side == 1:
                lower = (lower
                         .rotate((0, 0, 0), (1, 0, 0), -angle_deg)
                         .translate(knee_pos))
            else:
                lower = (lower
                         .rotate((0, 0, 0), (1, 0, 0), angle_deg)
                         .translate(knee_pos))
            parts.append((f"lower_{leg_name}", lower))

            # Knee joint sphere
            knee_sphere = (cq.Workplane("XY")
                           .sphere(LEG_DIA / 2 + 0.3)
                           .translate(knee_pos))
            parts.append((f"knee_{leg_name}", knee_sphere))

            # Mass: SG90 servo per leg is logged in build_servos().
            # Leg structure itself is negligible (included in chassis mass).

    return parts


# ---------------------------------------------------------------------------
# FOOT PADS (8x) -- disc with magnet recess and microspine holes
# ---------------------------------------------------------------------------
def build_foot_pads():
    """Build 8 foot pads with magnet recess and microspine holes."""
    parts = []

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            foot_name = f"foot_{pair_names[i]}{side_name}"

            foot_x = x_pos
            foot_y = side * (HIP_Y + LEG_DY)
            foot_z = HIP_Z + LEG_DZ

            # Main disc
            pad = (cq.Workplane("XY")
                   .circle(FOOT_PAD_D / 2)
                   .extrude(FOOT_PAD_H))

            # Magnet recess (bottom)
            mag_recess = (cq.Workplane("XY")
                          .circle(MAG_D / 2)
                          .extrude(MAG_H))
            pad = pad.cut(mag_recess)

            # Servo horn attachment bore (top center)
            horn_bore = (cq.Workplane("XY")
                         .circle(1.1)
                         .extrude(2.0)
                         .translate((0, 0, FOOT_PAD_H - 2.0)))
            pad = pad.cut(horn_bore)

            # Microspine holes (ring of 8, angled inward)
            for sp in range(SPINE_COUNT):
                angle_around = sp * (360.0 / SPINE_COUNT)
                rad = math.radians(angle_around)
                hx = SPINE_RING_R * math.cos(rad)
                hy = SPINE_RING_R * math.sin(rad)
                spine = (cq.Workplane("XY")
                         .circle(SPINE_HOLE_D / 2)
                         .extrude(FOOT_PAD_H + 1))
                spine = (spine
                         .rotate((0, 0, 0), (0, 1, 0), -SPINE_ANGLE * math.cos(rad))
                         .rotate((0, 0, 0), (1, 0, 0), -SPINE_ANGLE * math.sin(rad))
                         .translate((hx, hy, -0.5)))
                pad = pad.cut(spine)

            pad = pad.translate((foot_x, foot_y, foot_z - FOOT_PAD_H))
            parts.append((f"pad_{foot_name}", pad))

            # Magnet disc (visual)
            magnet = (cq.Workplane("XY")
                      .circle(MAG_D / 2)
                      .extrude(MAG_H)
                      .translate((foot_x, foot_y, foot_z - FOOT_PAD_H)))
            parts.append((f"magnet_{foot_name}", magnet))

    return parts


# ---------------------------------------------------------------------------
# SG90 SERVOS (8x legs) -- real STEP or parametric
# ---------------------------------------------------------------------------
def build_leg_servos():
    """Place 8 SG90 servos at the hip positions in the chassis pockets."""
    parts = []
    sg90_shape = load_sg90()

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            servo_name = f"servo_{pair_names[i]}{side_name}"

            pocket_y = side * (THORAX_W / 2 - SG90_W / 2 + 0.5)
            pocket_z = HIP_Z

            positioned = sg90_shape.translate((x_pos, pocket_y, pocket_z))
            parts.append((servo_name, positioned))

            ledger.add(f"SG90 {servo_name}", "SERVOS",
                       9.0, x_pos, pocket_y, pocket_z)

    return parts


# ---------------------------------------------------------------------------
# SG51R MANDIBLE SERVOS (2x) -- parametric boxes
# ---------------------------------------------------------------------------
def build_mandible_servos():
    """Place 2 SG51R micro servos in the head dome for mandibles."""
    parts = []

    head_x = THORAX_L / 2 + HEAD_D / 3

    for side in (-1, 1):
        side_name = "L" if side == 1 else "R"
        servo_name = f"mandible_servo_{side_name}"

        # Position inside head dome matching SCAD pockets
        sx = head_x + HEAD_D / 4
        sy = side * MANDIBLE_SPACING / 3
        sz = 0

        servo = (cq.Workplane("XY")
                 .box(SG51_L, SG51_W, SG51_H)
                 .translate((sx, sy, sz)))

        # Shaft stub on front face
        shaft = (cq.Workplane("XY")
                 .circle(2.0)
                 .extrude(3.0)
                 .translate((sx + SG51_L / 4, sy, sz + SG51_H / 2)))
        servo = servo.union(shaft)

        parts.append((servo_name, servo))

        ledger.add(f"SG51R {servo_name}", "MANDIBLE_SERVOS",
                   2.0, sx, sy, sz)

    return parts


# ---------------------------------------------------------------------------
# MANDIBLE ARMS (2x) -- from worker_chassis.scad
# ---------------------------------------------------------------------------
def build_mandibles():
    """Build 2 mandible arms extending forward from head with tool mount tips."""
    parts = []

    # From worker_chassis.scad: translate([thorax_length/2 + head_diameter/2 + 3, 0, 0])
    mand_base_x = THORAX_L / 2 + HEAD_D / 2 + 3

    for side in (-1, 1):
        side_name = "L" if side == 1 else "R"
        arm_name = f"mandible_arm_{side_name}"

        # Arm: tapered cylinder from base to tip
        # From SCAD: hull from sphere(d=5) to sphere(d=4) at (mandible_length, side*3, 0)
        base_pos = (mand_base_x, 0, 0)
        tip_pos = (mand_base_x + MANDIBLE_LENGTH, side * 3, 0)

        # Build as a cylinder connecting base to tip
        arm = (cq.Workplane("YZ")
               .circle(MANDIBLE_ARM_DIA / 2)
               .extrude(MANDIBLE_LENGTH)
               .translate((mand_base_x, side * 0.5, 0)))
        # Slight lateral offset toward the tip
        parts.append((arm_name, arm))

        # Tip sphere with magnet pocket for tool mount
        tip_x = mand_base_x + MANDIBLE_LENGTH
        tip_y = side * 3
        tip = (cq.Workplane("XY")
               .sphere(MANDIBLE_TIP_D / 2)
               .translate((tip_x, tip_y, 0)))

        # Magnet pocket in tip
        mag_pocket = (cq.Workplane("XY")
                      .circle(TOOL_MAGNET_D / 2 + 0.1)
                      .extrude(TOOL_MAGNET_DEPTH + 0.1)
                      .translate((tip_x, tip_y, 1)))
        tip = tip.cut(mag_pocket)

        parts.append((f"mandible_tip_{side_name}", tip))

    # Tool mount hardware mass
    ledger.add("Tool mount hardware (magnets + clip)", "TOOL_MOUNT",
               1.0, mand_base_x + MANDIBLE_LENGTH, 0, 0)

    return parts


# ---------------------------------------------------------------------------
# RP2040 PICO (brain) -- real STEP or parametric
# ---------------------------------------------------------------------------
def build_electronics():
    """RP2040 Pico in the electronics bay on top of thorax."""
    parts = []

    pico_shape = load_pico()

    # Position in electronics bay (centered on thorax top)
    ebay_z = THORAX_H / 2 - PICO_H / 2 - 0.5
    positioned = pico_shape.translate((0, 0, ebay_z))
    parts.append(("rp2040_pico", positioned))

    ledger.add("RP2040 Pico", "ELECTRONICS", 3.0, 0, 0, ebay_z)

    return parts


# ---------------------------------------------------------------------------
# SUPERCAPACITOR (10F / 5.5V -- coin type, in abdomen)
# ---------------------------------------------------------------------------
def build_supercap():
    """Supercapacitor coin cell in the abdomen cavity."""
    parts = []

    # Position: centered in abdomen
    abd_x = -THORAX_L / 2 - ABDOMEN_L / 2 + 8
    abd_z = -2.0

    cap = (cq.Workplane("XY")
           .circle(SUPERCAP_D / 2)
           .extrude(SUPERCAP_H)
           .translate((abd_x, 0, abd_z - SUPERCAP_H / 2 + 2)))
    parts.append(("supercap", cap))

    # Lead tabs (visual)
    for tab_y in (-3, 3):
        tab = (cq.Workplane("XY")
               .box(1.0, 3.0, SUPERCAP_H + 4)
               .translate((abd_x + SUPERCAP_D / 2 + 0.5, tab_y,
                           abd_z - SUPERCAP_H / 2 + 2)))
        parts.append((f"supercap_tab_{tab_y}", tab))

    ledger.add("Supercapacitor 10F/5.5V", "ELECTRONICS", 5.0,
               abd_x, 0, abd_z)

    return parts


# ---------------------------------------------------------------------------
# DRILL HEAD (front-mounted payload)
# ---------------------------------------------------------------------------
def build_drill_head():
    """Drill head assembly: housing, motor, drill bit.
    Clips between mandible tips via magnetic tool mount."""
    parts = []

    # Position: between mandible tips
    mand_base_x = THORAX_L / 2 + HEAD_D / 2 + 3
    drill_x = mand_base_x + MANDIBLE_LENGTH - DRILL_MOUNT_L / 2

    # Housing (small block between mandible tips)
    housing = (cq.Workplane("XY")
               .box(DRILL_MOUNT_L, DRILL_MOUNT_W, DRILL_MOUNT_H)
               .edges("|Z")
               .fillet(1.0)
               .translate((drill_x, 0, 0)))
    parts.append(("drill_housing", housing))

    # Drill motor (cylinder on top)
    motor = (cq.Workplane("XY")
             .circle(DRILL_MOTOR_D / 2)
             .extrude(DRILL_MOTOR_H)
             .translate((drill_x, 0, DRILL_MOUNT_H / 2)))
    parts.append(("drill_motor", motor))

    # Drill bit (extends forward from housing)
    bit = (cq.Workplane("YZ")
           .circle(DRILL_BIT_D / 2)
           .extrude(DRILL_BIT_L)
           .translate((drill_x + DRILL_MOUNT_L / 2, 0, 0)))
    parts.append(("drill_bit", bit))

    # Bit tip (pointed cone)
    bit_tip = (cq.Workplane("YZ")
               .circle(DRILL_BIT_D / 2)
               .workplane(offset=4)
               .circle(0.3)
               .loft()
               .translate((drill_x + DRILL_MOUNT_L / 2 + DRILL_BIT_L, 0, 0)))
    parts.append(("drill_bit_tip", bit_tip))

    # Magnet mounts (2x, matching mandible tips)
    for side in (-1, 1):
        mag = (cq.Workplane("XY")
               .circle(TOOL_MAGNET_D / 2)
               .extrude(TOOL_MAGNET_DEPTH)
               .translate((drill_x, side * (DRILL_MOUNT_W / 2), 0)))
        parts.append((f"drill_magnet_{side}", mag))

    # Drill head is a swappable tool -- not counted in base 120g budget.
    # But we place it for visual completeness.

    return parts


# ---------------------------------------------------------------------------
# MATERIAL HOPPER (abdomen-mounted)
# ---------------------------------------------------------------------------
def build_hopper():
    """Material collection hopper on top of abdomen."""
    parts = []

    abd_x = -THORAX_L / 2 - ABDOMEN_L / 2 + 8
    abd_z = -2.0
    hopper_z = abd_z + ABDOMEN_H / 2 + HOPPER_H / 2

    # Outer box
    outer = (cq.Workplane("XY")
             .box(HOPPER_L, HOPPER_W, HOPPER_H)
             .edges("|Z")
             .fillet(1.5))

    # Hollow out (open top)
    inner = (cq.Workplane("XY")
             .box(HOPPER_L - 2 * HOPPER_WALL,
                  HOPPER_W - 2 * HOPPER_WALL,
                  HOPPER_H - HOPPER_WALL)
             .translate((0, 0, HOPPER_WALL / 2)))
    outer = outer.cut(inner)

    outer = outer.translate((abd_x, 0, hopper_z))
    parts.append(("hopper", outer))

    # Hopper is a removable payload, not counted in base mass budget.
    # (like the drill head, it is a tool attachment)

    return parts


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    """Build the complete worker ant assembly with color-coded subsystems."""

    print("Building AstraAnt Worker Ant Assembly...")
    print(f"  Thorax:  {THORAX_L:.0f} x {THORAX_W:.0f} x {THORAX_H:.0f} mm")
    print(f"  Abdomen: {ABDOMEN_L:.0f} x {ABDOMEN_W:.0f} x {ABDOMEN_H:.0f} mm")
    print(f"  Head:    {HEAD_D:.0f} mm dome")
    print()

    assy = cq.Assembly(name="worker_ant")

    # --- Chassis (thorax + abdomen + head dome) ---
    print("  [1/8] Building chassis frame (thorax + abdomen + head)...")
    chassis = build_chassis()
    assy.add(chassis, name="chassis", color=COL_CHASSIS)

    # --- Leg servos (8x SG90) ---
    print("  [2/8] Placing SG90 leg servos (8x)...")
    servo_parts = build_leg_servos()
    for name, part in servo_parts:
        assy.add(part, name=name, color=COL_SERVO)

    # --- Mandible servos (2x SG51R) ---
    print("  [3/8] Placing SG51R mandible servos (2x)...")
    mservo_parts = build_mandible_servos()
    for name, part in mservo_parts:
        assy.add(part, name=name, color=COL_SERVO_SM)

    # --- Legs ---
    print("  [4/8] Building legs (8x upper + lower)...")
    leg_parts = build_legs()
    for name, part in leg_parts:
        col = COL_LEG if "knee" not in name else COL_CHASSIS
        assy.add(part, name=name, color=col)

    # --- Foot pads ---
    print("  [5/8] Building foot pads (8x + magnets)...")
    foot_parts = build_foot_pads()
    for name, part in foot_parts:
        col = COL_MAGNET if "magnet" in name else COL_FOOT
        assy.add(part, name=name, color=col)

    # --- Electronics (RP2040 Pico) ---
    print("  [6/8] Placing RP2040 Pico...")
    elec_parts = build_electronics()
    for name, part in elec_parts:
        assy.add(part, name=name, color=COL_PCB)

    # --- Supercapacitor ---
    print("  [7/8] Placing supercapacitor (10F/5.5V)...")
    cap_parts = build_supercap()
    for name, part in cap_parts:
        col = COL_SUPERCAP if "tab" not in name else COL_MAGNET
        assy.add(part, name=name, color=col)

    # --- Mandible arms + tool mount ---
    print("  [8/8] Building mandible arms + drill head + hopper...")
    mand_parts = build_mandibles()
    for name, part in mand_parts:
        col = COL_MANDIBLE
        assy.add(part, name=name, color=col)

    # --- Drill head (visual, swappable tool) ---
    drill_parts = build_drill_head()
    for name, part in drill_parts:
        col = (COL_MOTOR if "motor" in name
               else COL_MAGNET if "magnet" in name
               else COL_DRILL)
        assy.add(part, name=name, color=col)

    # --- Material hopper (visual, swappable payload) ---
    hopper_parts = build_hopper()
    for name, part in hopper_parts:
        assy.add(part, name=name, color=COL_HOPPER)

    return assy, chassis


def export_assembly(assy, chassis):
    """Export STEP assembly, merged STL, chassis-only STEP and STL."""

    os.makedirs(OUT_DIR, exist_ok=True)

    # --- Complete STEP assembly (preserves colors and structure) ---
    step_path = os.path.join(OUT_DIR, "worker_ant_assembly.step")
    print(f"\n  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assy.save(step_path, exportType="STEP")
    size_mb = os.path.getsize(step_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Merged STL ---
    stl_path = os.path.join(OUT_DIR, "worker_ant_assembly.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assy.save(stl_path, exportType="STL", tolerance=0.05, angularTolerance=0.1)
    size_mb = os.path.getsize(stl_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Chassis-only STEP (this is what you 3D print) ---
    chassis_step = os.path.join(OUT_DIR, "worker_ant_chassis.step")
    print(f"  Exporting chassis STEP: {chassis_step}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cq.exporters.export(chassis, chassis_step, exportType="STEP")
    size_kb = os.path.getsize(chassis_step) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    # --- Chassis-only STL ---
    chassis_stl = os.path.join(OUT_DIR, "worker_ant_chassis.stl")
    print(f"  Exporting chassis STL:  {chassis_stl}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cq.exporters.export(chassis, chassis_stl, exportType="STL",
                            tolerance=0.05, angularTolerance=0.1)
    size_kb = os.path.getsize(chassis_stl) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 70)
    print("  AstraAnt Worker Ant -- CadQuery Parametric Assembly")
    print("=" * 70)
    print()

    assy, chassis = build_assembly()
    export_assembly(assy, chassis)

    # --- Mass properties report ---
    print()
    print(ledger.report())

    # --- Output file listing ---
    print()
    print("  Output files:")
    for f in ["worker_ant_assembly.step", "worker_ant_assembly.stl",
              "worker_ant_chassis.step", "worker_ant_chassis.stl"]:
        fp = os.path.join(OUT_DIR, f)
        if os.path.isfile(fp):
            print(f"    {fp}")

    print()
    print("  Done. Import STEP into FreeCAD/Fusion360/Ansys for analysis.")
    print("  Chassis STEP/STL ready for 3D print slicing.")
    print("=" * 70)


if __name__ == "__main__":
    main()
