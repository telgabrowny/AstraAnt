"""
AstraAnt WAAM Printer Bot -- Parametric Assembly for Ansys Analysis
===================================================================

CadQuery parametric model of the 8-legged WAAM printer ant.
Engineering-grade: every part at its real position with real clearances.

VEHICLE SPECS:
  Thorax:    45 x 30 x 16 mm (PETG prototype / WAAM iron in space)
  Legs:      8x (4 pairs), SG90 servo-driven
  Payload:   WAAM print head (front), wire bobbin (rear), ESP32 (top)
  Total:     ~411 g

Dimensions from:
  printer_bot.scad       -- OpenSCAD reference (all in mm)
  printer_bot.xml        -- MuJoCo model (verified physics)
  foot_pad.scad          -- Foot pad detail

Usage:
  python scad/printer_bot_assembly.py

Outputs:
  scad/printer_bot_assembly.step    (color-coded assembly)
  scad/printer_bot_assembly.stl     (merged mesh)
  scad/printer_bot_chassis.step     (just the chassis -- 3D printable)
  scad/printer_bot_chassis.stl      (chassis STL for slicing)
  scad/printer_bot_servos.stl       (per-subsystem)
  scad/printer_bot_legs.stl
  scad/printer_bot_printhead.stl
  scad/printer_bot_electronics.stl
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
ESP32_STEP = os.path.join(VENDOR_RAW, "esp32",
                          "ESP32-S3-WROOM-1_devkit_2xUSBC_c.step")
PICO_STEP = os.path.join(VENDOR_RAW, "pico", "Pico-R3.step")

# ---------------------------------------------------------------------------
# Material densities (kg/m^3)
# ---------------------------------------------------------------------------
RHO_IRON = 7874       # Pure iron (WAAM-printed)
RHO_PETG = 1270       # PETG filament
RHO_COPPER = 8960     # Copper wiring / tether
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
# ESP32-S3 MODULE (not DevKit -- too large for the bot)
# ---------------------------------------------------------------------------
ESP32_MOD_L = 25.5
ESP32_MOD_W = 18.0
ESP32_MOD_H = 3.0

# ---------------------------------------------------------------------------
# Thorax (chassis body)
# ---------------------------------------------------------------------------
THORAX_L = 45.0     # length (X)
THORAX_W = 30.0     # width (Y)
THORAX_H = 16.0     # height (Z)
HEAD_D = 14.0       # head dome diameter
WALL = 2.0          # wall thickness

# ---------------------------------------------------------------------------
# Leg geometry
# ---------------------------------------------------------------------------
N_LEG_PAIRS = 4
# Pair x-positions from MuJoCo model (in mm, from thorax center)
LEG_PAIR_X = [16.0, 6.0, -6.0, -16.0]
# Hip Y position (center of servo, from MuJoCo: 15mm from centerline)
HIP_Y = 15.0
# Hip Z offset below thorax center (from MuJoCo: -4mm)
HIP_Z = -4.0
# Leg segment dimensions
LEG_UPPER_L = 18.0   # coxa length
LEG_LOWER_L = 22.0   # femur length
LEG_DIA = 3.0        # leg rod diameter
# From MuJoCo: leg goes from hip to (0, +/-36, -30) relative to hip
LEG_DY = 36.0        # lateral extension from hip to foot
LEG_DZ = -30.0       # vertical drop from hip to foot

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
# WAAM Print head
# ---------------------------------------------------------------------------
HEAD_MOUNT_L = 20.0
HEAD_MOUNT_W = 14.0
HEAD_MOUNT_H = 12.0
ROLLER_D = 8.0
ROLLER_W = 5.0
ROLLER_BORE = 3.0
ARC_TIP_D = 3.0
ARC_TIP_L = 15.0
FEED_MOTOR_D = 10.0
FEED_MOTOR_H = 12.0
WIRE_GUIDE_D = 3.0
WIRE_GUIDE_L = 8.0

# ---------------------------------------------------------------------------
# Wire bobbin
# ---------------------------------------------------------------------------
BOBBIN_OUTER_D = 30.0
BOBBIN_INNER_D = 10.0
BOBBIN_WIDTH = 15.0
BOBBIN_WIRE_D = 26.0  # wire wound diameter

# ---------------------------------------------------------------------------
# Power tether
# ---------------------------------------------------------------------------
TETHER_D = 3.0
TETHER_STUB_L = 100.0  # 100mm visual stub

# ---------------------------------------------------------------------------
# Grip socket (rear, from worker_chassis.scad)
# ---------------------------------------------------------------------------
GRIP_GROOVE_W = 3.0
GRIP_GROOVE_DEPTH = 1.5
GRIP_GROOVE_SPACING = 10.0

# ---------------------------------------------------------------------------
# Color palette (subsystem coding)
# ---------------------------------------------------------------------------
COL_CHASSIS   = Color(0.50, 0.50, 0.55, 1.0)   # iron gray
COL_SERVO     = Color(0.20, 0.40, 0.80, 1.0)   # SG90 blue
COL_LEG       = Color(0.55, 0.55, 0.60, 1.0)   # leg iron
COL_FOOT      = Color(0.20, 0.20, 0.22, 1.0)   # foot pad dark
COL_MAGNET    = Color(0.75, 0.75, 0.78, 1.0)   # NdFeB silver
COL_PCB       = Color(0.10, 0.50, 0.15, 1.0)   # PCB green
COL_HOUSING   = Color(0.70, 0.70, 0.72, 1.0)   # print head housing
COL_COPPER    = Color(0.80, 0.50, 0.30, 1.0)   # arc nozzle / tether
COL_MOTOR     = Color(0.40, 0.40, 0.45, 1.0)   # feed motor
COL_BOBBIN    = Color(0.65, 0.67, 0.72, 1.0)   # wire spool
COL_WIRE      = Color(0.72, 0.72, 0.75, 1.0)   # wound wire
COL_HORN      = Color(0.90, 0.90, 0.90, 1.0)   # servo horn white

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
        lines.append("  PRINTER BOT ASSEMBLY -- MASS PROPERTIES REPORT")
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
        if abs(m_tot - 411) > 20:
            lines.append(
                f"  WARNING: Total mass {m_tot:.1f} g deviates from 411 g target"
            )
        else:
            lines.append(f"  OK: Total mass {m_tot:.1f} g within 20 g of 411 g target")

        lines.append("=" * 80)
        return "\n".join(lines)


ledger = MassLedger()

# ---------------------------------------------------------------------------
# Vendor STEP import helper
# ---------------------------------------------------------------------------
_sg90_cache = None


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
        # Check if it looks like mm already (smallest ~12)
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
    # Main body (centered at origin)
    body = cq.Workplane("XY").box(SG90_L, SG90_W, SG90_TAB_H)

    # Mounting tabs (wider flanges near top of body)
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

    # Output shaft cylinder
    shaft = (cq.Workplane("XY")
             .circle(SG90_SHAFT_D / 2)
             .extrude(SG90_SHAFT_H)
             .translate((SG90_L / 2 - 5.5, 0, SG90_H / 2)))
    body = body.union(shaft)

    return body


# ---------------------------------------------------------------------------
# CHASSIS -- the 3D-printable frame
# ---------------------------------------------------------------------------
def build_chassis():
    """Build the thorax frame with servo pockets, wire channels,
    electronics bay, print head mount, bobbin mount, and grip socket.
    Designed to be 3D-printable (no overhangs > 45 deg from build plate)."""

    # Start with a rounded box for the main thorax
    # Build as a box with chamfered edges (CadQuery fillet on box edges)
    thorax = (cq.Workplane("XY")
              .box(THORAX_L, THORAX_W, THORAX_H)
              .edges("|Z")
              .fillet(2.0)
              .edges("|X")
              .fillet(1.5))

    # ---- Hollow out the interior (leave WALL thickness shell) ----
    # Inner cavity
    inner = (cq.Workplane("XY")
             .box(THORAX_L - 2 * WALL,
                  THORAX_W - 2 * WALL,
                  THORAX_H - 2 * WALL))
    thorax = thorax.cut(inner)

    # ---- 8 Servo pockets (4 pairs along the body) ----
    # Each pocket is cut from the side walls, oriented so the servo
    # shaft points outward (toward the leg tip).
    # Pocket: SG90 body + clearance, with tab slots
    c = SG90_CLEARANCE
    for i, x_pos in enumerate(LEG_PAIR_X):
        for side in (-1, 1):
            # Pocket for the main servo body
            # Servo sits with its long axis along X (shaft axis),
            # mounted at the side wall of the thorax
            pocket_y = side * (THORAX_W / 2 - SG90_W / 2 + 0.5)
            pocket_z = HIP_Z  # hip Z offset

            # Main body pocket
            pocket = (cq.Workplane("XY")
                      .box(SG90_L + c * 2, SG90_W + c * 2, SG90_TAB_H + c * 2)
                      .translate((x_pos, pocket_y, pocket_z)))
            thorax = thorax.cut(pocket)

            # Tab slot (wider, thinner slice at the tab height)
            tab_slot = (cq.Workplane("XY")
                        .box(SG90_TAB_W + c * 2,
                             SG90_W + c * 2,
                             SG90_TAB_T + c * 2)
                        .translate((x_pos, pocket_y,
                                    pocket_z + SG90_TAB_H / 2 - SG90_TAB_T / 2)))
            thorax = thorax.cut(tab_slot)

            # Wire exit hole at bottom of pocket (for servo cable routing)
            wire_hole = (cq.Workplane("XY")
                         .circle(2.0)
                         .extrude(WALL + 2)
                         .translate((x_pos, pocket_y,
                                     pocket_z - SG90_TAB_H / 2 - 1)))
            thorax = thorax.cut(wire_hole)

    # ---- Wire routing channels (2mm wide grooves between servo pockets) ----
    # Main channel runs along X axis inside the bottom wall
    wire_channel = (cq.Workplane("XZ")
                    .rect(THORAX_L - 4, 2.5)
                    .extrude(2.0)
                    .translate((0, 0, -THORAX_H / 2 + WALL / 2)))
    thorax = thorax.cut(wire_channel)

    # ---- Electronics bay (top, recessed for ESP32 module) ----
    # Centered slightly forward to balance CoM with rear bobbin
    ebay_x = 5.0  # offset from center toward front
    ebay = (cq.Workplane("XY")
            .box(ESP32_MOD_L + 2, ESP32_MOD_W + 2, ESP32_MOD_H + 2)
            .translate((ebay_x, 0, THORAX_H / 2 - ESP32_MOD_H / 2 - 0.5)))
    thorax = thorax.cut(ebay)

    # M2 screw bosses for electronics (2x, inside the bay)
    for boss_x_off in (-8, 8):
        boss = (cq.Workplane("XY")
                .circle(2.0)
                .extrude(ESP32_MOD_H + 2)
                .translate((ebay_x + boss_x_off, 0,
                            THORAX_H / 2 - ESP32_MOD_H - 1.5)))
        thorax = thorax.union(boss)
        # Drill M2 hole (2.2mm)
        hole = (cq.Workplane("XY")
                .circle(1.1)
                .extrude(ESP32_MOD_H + 4)
                .translate((ebay_x + boss_x_off, 0,
                            THORAX_H / 2 - ESP32_MOD_H - 2.5)))
        thorax = thorax.cut(hole)

    # ---- Print head mount bosses (front, 2x M2) ----
    for boss_y in (-5, 5):
        boss = (cq.Workplane("YZ")
                .circle(2.0)
                .extrude(3)
                .translate((THORAX_L / 2, boss_y, 0)))
        thorax = thorax.union(boss)
        hole = (cq.Workplane("YZ")
                .circle(1.1)
                .extrude(5)
                .translate((THORAX_L / 2 - 1, boss_y, 0)))
        thorax = thorax.cut(hole)

    # ---- Head dome (front of thorax) ----
    head = (cq.Workplane("XY")
            .sphere(HEAD_D / 2))
    # Position at front, slightly above center (matches SCAD)
    head = head.translate((THORAX_L / 2 + HEAD_D / 2 - 3, 0, 2))
    thorax = thorax.union(head)

    # ---- Bobbin mount clip (rear) ----
    # Slot at the rear for the bobbin axle to clip in
    bobbin_slot = (cq.Workplane("XY")
                   .box(6, BOBBIN_WIDTH + 2, 12)
                   .translate((-THORAX_L / 2 - 2, 0, 2)))
    thorax = thorax.cut(bobbin_slot)

    # ---- Grip socket (rear, for ant-to-ant chaining) ----
    # Two parallel grooves on the rear face, matching worker_chassis.scad
    for g_off in (-GRIP_GROOVE_SPACING / 2, GRIP_GROOVE_SPACING / 2):
        groove = (cq.Workplane("YZ")
                  .rect(GRIP_GROOVE_W, THORAX_H - 4)
                  .extrude(GRIP_GROOVE_DEPTH)
                  .translate((-THORAX_L / 2, g_off, 0)))
        thorax = thorax.cut(groove)

    # ---- Power tether strain relief (rear, 5mm hole with flared entry) ----
    tether_hole = (cq.Workplane("YZ")
                   .circle(TETHER_D / 2 + 0.5)
                   .extrude(WALL + 2)
                   .translate((-THORAX_L / 2 - 1, 0, HIP_Z)))
    thorax = thorax.cut(tether_hole)
    # Flared entry (45-deg chamfer, printable)
    flare = (cq.Workplane("YZ")
             .circle(TETHER_D / 2 + 1.5)
             .workplane(offset=2)
             .circle(TETHER_D / 2 + 0.5)
             .loft()
             .translate((-THORAX_L / 2 - 1, 0, HIP_Z)))
    thorax = thorax.cut(flare)

    # Log chassis mass
    ledger.add("Chassis (thorax + head dome)", "CHASSIS", 80.0, 0, 0, 0)

    return thorax


# ---------------------------------------------------------------------------
# LEGS (8x) -- upper + lower segments as cylinders
# ---------------------------------------------------------------------------
def build_legs():
    """Build 8 legs as upper (coxa) + lower (femur) cylinder segments.
    Returns list of (name, workplane) tuples and foot pad info."""
    parts = []

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            leg_idx = i * 2 + (0 if side == 1 else 1)
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            leg_name = f"leg_{pair_names[i]}{side_name}"

            hip_pos = (x_pos, side * HIP_Y, HIP_Z)

            # Foot position relative to hip (from MuJoCo model)
            foot_pos = (x_pos, side * (HIP_Y + LEG_DY), HIP_Z + LEG_DZ)

            # Knee position: end of upper leg (coxa extends laterally)
            # Upper leg goes from hip straight outward along Y
            knee_y = side * (HIP_Y + LEG_UPPER_L)
            knee_pos = (x_pos, knee_y, HIP_Z)

            # Upper leg (coxa): horizontal cylinder from hip outward
            upper = (cq.Workplane("XY")
                     .circle(LEG_DIA / 2)
                     .extrude(LEG_UPPER_L))
            # Orient along Y axis
            if side == 1:
                upper = upper.translate((x_pos, HIP_Y, HIP_Z))
            else:
                upper = (upper.rotate((0, 0, 0), (0, 0, 1), 180)
                         .translate((x_pos, -HIP_Y, HIP_Z)))

            parts.append((f"upper_{leg_name}", upper))

            # Lower leg (femur): angled cylinder from knee to foot
            # Vector from knee to foot
            dy_lower = foot_pos[1] - knee_pos[1]
            dz_lower = foot_pos[2] - knee_pos[2]
            lower_len = math.sqrt(dy_lower ** 2 + dz_lower ** 2)
            angle_deg = math.degrees(math.atan2(-dz_lower, abs(dy_lower)))

            lower = (cq.Workplane("XY")
                     .circle(LEG_DIA / 2)
                     .extrude(lower_len))

            # Rotate to angle downward, then position at knee
            if side == 1:
                lower = (lower
                         .rotate((0, 0, 0), (1, 0, 0), -angle_deg)
                         .translate(knee_pos))
            else:
                lower = (lower
                         .rotate((0, 0, 0), (1, 0, 0), angle_deg)
                         .translate(knee_pos))

            parts.append((f"lower_{leg_name}", lower))

            # Knee joint sphere (visual joint marker)
            knee_sphere = (cq.Workplane("XY")
                           .sphere(LEG_DIA / 2 + 0.3)
                           .translate(knee_pos))
            parts.append((f"knee_{leg_name}", knee_sphere))

            # Log mass
            ledger.add(f"Leg {leg_name} (upper+lower)", "LEGS",
                       5.0, x_pos, side * (HIP_Y + LEG_DY / 2), HIP_Z + LEG_DZ / 2)

    return parts


# ---------------------------------------------------------------------------
# FOOT PADS (8x) -- disc with magnet recess and microspine holes
# ---------------------------------------------------------------------------
def build_foot_pads():
    """Build 8 foot pads with magnet recess and microspine holes."""
    parts = []

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            leg_idx = i * 2 + (0 if side == 1 else 1)
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            foot_name = f"foot_{pair_names[i]}{side_name}"

            # Foot position (from MuJoCo)
            foot_x = x_pos
            foot_y = side * (HIP_Y + LEG_DY)
            foot_z = HIP_Z + LEG_DZ

            # Main disc
            pad = (cq.Workplane("XY")
                   .circle(FOOT_PAD_D / 2)
                   .extrude(FOOT_PAD_H))

            # Magnet recess (bottom, 6mm dia x 2mm deep)
            mag_recess = (cq.Workplane("XY")
                          .circle(MAG_D / 2)
                          .extrude(MAG_H))
            pad = pad.cut(mag_recess)

            # Servo horn attachment bore (top center, 2.2mm dia x 2mm deep)
            horn_bore = (cq.Workplane("XY")
                         .circle(1.1)
                         .extrude(2.0)
                         .translate((0, 0, FOOT_PAD_H - 2.0)))
            pad = pad.cut(horn_bore)

            # Microspine holes (ring of 8, angled inward at 30 deg)
            for sp in range(SPINE_COUNT):
                angle_around = sp * (360.0 / SPINE_COUNT)
                rad = math.radians(angle_around)
                hx = SPINE_RING_R * math.cos(rad)
                hy = SPINE_RING_R * math.sin(rad)
                # Angled hole: 0.4mm dia, angled 30 deg inward
                spine = (cq.Workplane("XY")
                         .circle(SPINE_HOLE_D / 2)
                         .extrude(FOOT_PAD_H + 1))
                # Approximate angle by tilting toward center
                spine = (spine
                         .rotate((0, 0, 0), (0, 1, 0), -SPINE_ANGLE * math.cos(rad))
                         .rotate((0, 0, 0), (1, 0, 0), -SPINE_ANGLE * math.sin(rad))
                         .translate((hx, hy, -0.5)))
                pad = pad.cut(spine)

            # Position the foot pad
            pad = pad.translate((foot_x, foot_y, foot_z - FOOT_PAD_H))
            parts.append((f"pad_{foot_name}", pad))

            # Magnet disc (visual, sits in the recess)
            magnet = (cq.Workplane("XY")
                      .circle(MAG_D / 2)
                      .extrude(MAG_H)
                      .translate((foot_x, foot_y, foot_z - FOOT_PAD_H)))
            parts.append((f"magnet_{foot_name}", magnet))

            ledger.add(f"Foot pad {foot_name} + magnet", "FEET",
                       2.0, foot_x, foot_y, foot_z)

    return parts


# ---------------------------------------------------------------------------
# SG90 SERVOS (8x) -- real STEP or parametric
# ---------------------------------------------------------------------------
def build_servos():
    """Place 8 SG90 servos at the hip positions in the chassis pockets."""
    parts = []
    sg90_shape = load_sg90()

    for i, x_pos in enumerate(LEG_PAIR_X):
        for side_idx, side in enumerate((-1, 1)):
            leg_idx = i * 2 + (0 if side == 1 else 1)
            side_name = "L" if side == 1 else "R"
            pair_names = ["F", "M1", "M2", "R"]
            servo_name = f"servo_{pair_names[i]}{side_name}"

            # Servo center position in the chassis pocket
            pocket_y = side * (THORAX_W / 2 - SG90_W / 2 + 0.5)
            pocket_z = HIP_Z

            # Copy and position the servo
            positioned = sg90_shape.translate((x_pos, pocket_y, pocket_z))
            parts.append((servo_name, positioned))

            ledger.add(f"SG90 {servo_name}", "SERVOS",
                       9.0, x_pos, pocket_y, pocket_z)

    return parts


# ---------------------------------------------------------------------------
# ESP32 MODULE (brain)
# ---------------------------------------------------------------------------
def build_electronics():
    """ESP32-S3 module (25.5x18x3mm) in the electronics bay."""
    parts = []

    ebay_x = 5.0  # Same offset as chassis bay
    ebay_z = THORAX_H / 2 - ESP32_MOD_H / 2 - 0.5

    # PCB board
    pcb = (cq.Workplane("XY")
           .box(ESP32_MOD_L, ESP32_MOD_W, 1.6)
           .translate((ebay_x, 0, ebay_z)))
    parts.append(("esp32_pcb", pcb))

    # RF shield module on top
    shield = (cq.Workplane("XY")
              .box(18, 13, 2.5)
              .translate((ebay_x + 3, 0, ebay_z + 1.5)))
    parts.append(("esp32_shield", shield))

    # Antenna trace
    antenna = (cq.Workplane("XY")
               .box(5, ESP32_MOD_W - 2, 0.2)
               .translate((ebay_x + ESP32_MOD_L / 2 - 3, 0, ebay_z + 0.9)))
    parts.append(("esp32_antenna", antenna))

    ledger.add("ESP32-S3 module", "ELECTRONICS", 3.0,
               ebay_x, 0, ebay_z)

    return parts


# ---------------------------------------------------------------------------
# WAAM PRINT HEAD (front-mounted)
# ---------------------------------------------------------------------------
def build_print_head():
    """WAAM print head assembly: housing, 2 feed rollers, wire guide,
    arc nozzle, and feed motor."""
    parts = []

    # Position: in front of head dome (matches SCAD and MuJoCo)
    # MuJoCo: print_head pos="0.040 0 0.0" (40mm from thorax center)
    head_x = 40.0

    # Housing (rounded box 20x14x12mm)
    housing = (cq.Workplane("XY")
               .box(HEAD_MOUNT_L, HEAD_MOUNT_W, HEAD_MOUNT_H)
               .edges("|Z")
               .fillet(1.5)
               .translate((head_x, 0, 0)))
    parts.append(("head_housing", housing))

    # Two feed rollers (8mm dia x 5mm, with 3mm bore, inside housing)
    for r_side, r_name in ((1, "L"), (-1, "R")):
        roller = (cq.Workplane("XZ")
                  .circle(ROLLER_D / 2)
                  .circle(ROLLER_BORE / 2)
                  .extrude(ROLLER_W)
                  .translate((head_x + 2, r_side * 3 - ROLLER_W / 2, 0)))
        parts.append((f"roller_{r_name}", roller))

    # Wire guide tube (3mm dia x 8mm, extending forward from housing)
    guide = (cq.Workplane("YZ")
             .circle(WIRE_GUIDE_D / 2)
             .extrude(WIRE_GUIDE_L)
             .translate((head_x + HEAD_MOUNT_L / 2, 0, 0)))
    parts.append(("wire_guide", guide))

    # Arc nozzle (3mm dia x 15mm, at the front)
    nozzle = (cq.Workplane("YZ")
              .circle(ARC_TIP_D / 2)
              .extrude(ARC_TIP_L)
              .translate((head_x + HEAD_MOUNT_L / 2 + WIRE_GUIDE_L, 0, 0)))
    parts.append(("arc_nozzle", nozzle))

    # Feed motor (10mm dia x 12mm cylinder, on top of housing)
    motor = (cq.Workplane("XY")
             .circle(FEED_MOTOR_D / 2)
             .extrude(FEED_MOTOR_H)
             .translate((head_x, 0, HEAD_MOUNT_H / 2)))
    parts.append(("feed_motor", motor))

    # Motor shaft stub
    shaft = (cq.Workplane("XY")
             .circle(1.0)
             .extrude(3.0)
             .translate((head_x, 0, HEAD_MOUNT_H / 2 + FEED_MOTOR_H)))
    parts.append(("motor_shaft", shaft))

    # M2 mount bosses (on rear face of housing, mating to chassis)
    for boss_y in (-5, 5):
        boss = (cq.Workplane("YZ")
                .circle(2.0)
                .extrude(3)
                .translate((head_x - HEAD_MOUNT_L / 2 - 3, boss_y, 0)))
        parts.append((f"head_mount_boss_{boss_y}", boss))

    ledger.add("Print head housing", "PRINT_HEAD", 40.0,
               head_x, 0, 0)
    ledger.add("Feed rollers (2x)", "PRINT_HEAD", 4.0,
               head_x + 2, 0, 0)
    ledger.add("Wire guide tube", "PRINT_HEAD", 2.0,
               head_x + HEAD_MOUNT_L / 2 + WIRE_GUIDE_L / 2, 0, 0)
    ledger.add("Arc nozzle (tungsten)", "PRINT_HEAD", 6.0,
               head_x + HEAD_MOUNT_L / 2 + WIRE_GUIDE_L + ARC_TIP_L / 2, 0, 0)
    ledger.add("Feed motor", "PRINT_HEAD", 8.0,
               head_x, 0, HEAD_MOUNT_H / 2 + FEED_MOTOR_H / 2)

    return parts


# ---------------------------------------------------------------------------
# WIRE BOBBIN (rear-mounted spool)
# ---------------------------------------------------------------------------
def build_wire_bobbin():
    """Wire bobbin: two flanges, core, wound wire."""
    parts = []

    # Position: behind thorax (matches MuJoCo: pos="-0.034 0 0.003")
    bobbin_x = -34.0
    bobbin_z = 3.0

    # Bobbin axis is along Y (flanges face +Y and -Y)
    # Core cylinder
    core = (cq.Workplane("XZ")
            .circle(BOBBIN_INNER_D / 2)
            .extrude(BOBBIN_WIDTH)
            .translate((bobbin_x, -BOBBIN_WIDTH / 2, bobbin_z)))
    parts.append(("bobbin_core", core))

    # Two flanges
    for f_side, f_name in ((1, "L"), (-1, "R")):
        flange_y = f_side * (BOBBIN_WIDTH / 2 + 0.75)
        flange = (cq.Workplane("XZ")
                  .circle(BOBBIN_OUTER_D / 2)
                  .extrude(1.5)
                  .translate((bobbin_x, flange_y - 0.75, bobbin_z)))
        parts.append((f"bobbin_flange_{f_name}", flange))

    # Wound wire (visual: cylinder between flanges)
    wire = (cq.Workplane("XZ")
            .circle(BOBBIN_WIRE_D / 2)
            .circle(BOBBIN_INNER_D / 2 + 1)
            .extrude(BOBBIN_WIDTH - 3)
            .translate((bobbin_x, -(BOBBIN_WIDTH - 3) / 2, bobbin_z)))
    parts.append(("bobbin_wire", wire))

    ledger.add("Wire bobbin frame", "BOBBIN", 30.0,
               bobbin_x, 0, bobbin_z)
    ledger.add("Iron wire coil (5m)", "BOBBIN", 22.0,
               bobbin_x, 0, bobbin_z)

    return parts


# ---------------------------------------------------------------------------
# POWER TETHER (rear stub)
# ---------------------------------------------------------------------------
def build_tether():
    """Power tether: 5m copper cable, shown as 100mm stub."""
    parts = []

    tether_z = HIP_Z

    # Tether port (slightly larger cylinder)
    port = (cq.Workplane("YZ")
            .circle(TETHER_D / 2 + 1)
            .extrude(5)
            .translate((-THORAX_L / 2 - 5, 0, tether_z)))
    parts.append(("tether_port", port))

    # Cable stub (100mm extending behind)
    cable = (cq.Workplane("YZ")
             .circle(TETHER_D / 2)
             .extrude(TETHER_STUB_L)
             .translate((-THORAX_L / 2 - 5, 0, tether_z)))
    parts.append(("tether_cable", cable))

    ledger.add("Power tether stub (5m copper)", "TETHER", 50.0,
               -THORAX_L / 2 - 50, 0, tether_z)
    ledger.add("Wiring harness (internal)", "TETHER", 20.0,
               0, 0, -THORAX_H / 2 + WALL)
    ledger.add("Misc fasteners (M2 screws etc)", "MISC", 18.0,
               0, 0, 0)

    return parts


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    """Build the complete printer bot assembly with color-coded subsystems."""

    print("Building AstraAnt WAAM Printer Bot Assembly...")
    print(f"  Thorax: {THORAX_L:.0f} x {THORAX_W:.0f} x {THORAX_H:.0f} mm")
    print()

    assy = cq.Assembly(name="printer_bot")

    # Subsystem part collectors for individual STL export
    subsys_parts = {
        "chassis": [],
        "servos": [],
        "legs": [],
        "printhead": [],
        "electronics": [],
    }

    # --- Chassis ---
    print("  [1/7] Building chassis frame...")
    chassis = build_chassis()
    assy.add(chassis, name="chassis", color=COL_CHASSIS)
    subsys_parts["chassis"].append(chassis)

    # --- Servos ---
    print("  [2/7] Placing SG90 servos (8x)...")
    servo_parts = build_servos()
    for name, part in servo_parts:
        assy.add(part, name=name, color=COL_SERVO)
        subsys_parts["servos"].append(part)

    # --- Legs ---
    print("  [3/7] Building legs (8x upper + lower)...")
    leg_parts = build_legs()
    for name, part in leg_parts:
        col = COL_LEG if "knee" not in name else COL_CHASSIS
        assy.add(part, name=name, color=col)
        subsys_parts["legs"].append(part)

    # --- Foot pads ---
    print("  [4/7] Building foot pads (8x + magnets)...")
    foot_parts = build_foot_pads()
    for name, part in foot_parts:
        col = COL_MAGNET if "magnet" in name else COL_FOOT
        assy.add(part, name=name, color=col)
        subsys_parts["legs"].append(part)  # feet go with legs subsystem

    # --- Electronics ---
    print("  [5/7] Placing ESP32 module...")
    elec_parts = build_electronics()
    for name, part in elec_parts:
        col = (COL_MAGNET if "shield" in name
               else COL_COPPER if "antenna" in name
               else COL_PCB)
        assy.add(part, name=name, color=col)
        subsys_parts["electronics"].append(part)

    # --- Print head ---
    print("  [6/7] Building WAAM print head...")
    head_parts = build_print_head()
    for name, part in head_parts:
        col = (COL_COPPER if "nozzle" in name
               else COL_MOTOR if "motor" in name or "shaft" in name
               else COL_HOUSING)
        assy.add(part, name=name, color=col)
        subsys_parts["printhead"].append(part)

    # --- Wire bobbin ---
    print("  [7/7] Building wire bobbin + tether...")
    bobbin_parts = build_wire_bobbin()
    for name, part in bobbin_parts:
        col = COL_WIRE if "wire" in name else COL_BOBBIN
        assy.add(part, name=name, color=col)
        subsys_parts["printhead"].append(part)  # bobbin goes with printhead

    tether_parts = build_tether()
    for name, part in tether_parts:
        col = COL_COPPER
        assy.add(part, name=name, color=col)
        subsys_parts["electronics"].append(part)

    return assy, subsys_parts, chassis


def export_assembly(assy, subsys_parts, chassis):
    """Export STEP assembly, merged STL, chassis-only, and per-subsystem STLs."""

    os.makedirs(OUT_DIR, exist_ok=True)

    # --- Complete STEP assembly (preserves colors and structure) ---
    step_path = os.path.join(OUT_DIR, "printer_bot_assembly.step")
    print(f"\n  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assy.save(step_path, exportType="STEP")
    size_mb = os.path.getsize(step_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Merged STL ---
    stl_path = os.path.join(OUT_DIR, "printer_bot_assembly.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assy.save(stl_path, exportType="STL", tolerance=0.05, angularTolerance=0.1)
    size_mb = os.path.getsize(stl_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Chassis-only STEP (this is what you 3D print) ---
    chassis_step = os.path.join(OUT_DIR, "printer_bot_chassis.step")
    print(f"  Exporting chassis STEP: {chassis_step}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cq.exporters.export(chassis, chassis_step, exportType="STEP")
    size_kb = os.path.getsize(chassis_step) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    # --- Chassis-only STL ---
    chassis_stl = os.path.join(OUT_DIR, "printer_bot_chassis.stl")
    print(f"  Exporting chassis STL:  {chassis_stl}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cq.exporters.export(chassis, chassis_stl, exportType="STL",
                            tolerance=0.05, angularTolerance=0.1)
    size_kb = os.path.getsize(chassis_stl) / 1e3
    print(f"    Done ({size_kb:.0f} KB)")

    # --- Per-subsystem STLs ---
    print("  Exporting per-subsystem STLs:")
    for subsys_name, parts_list in subsys_parts.items():
        if not parts_list:
            continue
        sub_assy = cq.Assembly(name=subsys_name)
        for i, part in enumerate(parts_list):
            sub_assy.add(part, name=f"{subsys_name}_{i}")

        sub_path = os.path.join(OUT_DIR, f"printer_bot_{subsys_name}.stl")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sub_assy.save(sub_path, exportType="STL",
                          tolerance=0.05, angularTolerance=0.1)
        size_kb = os.path.getsize(sub_path) / 1e3
        print(f"    printer_bot_{subsys_name}.stl ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 70)
    print("  AstraAnt WAAM Printer Bot -- CadQuery Parametric Assembly")
    print("=" * 70)
    print()

    assy, subsys_parts, chassis = build_assembly()
    export_assembly(assy, subsys_parts, chassis)

    # --- Mass properties report ---
    print()
    print(ledger.report())

    # --- Output file listing ---
    print()
    print("  Output files:")
    for f in ["printer_bot_assembly.step", "printer_bot_assembly.stl",
              "printer_bot_chassis.step", "printer_bot_chassis.stl",
              "printer_bot_servos.stl", "printer_bot_legs.stl",
              "printer_bot_printhead.stl", "printer_bot_electronics.stl"]:
        fp = os.path.join(OUT_DIR, f)
        if os.path.isfile(fp):
            print(f"    {fp}")

    print()
    print("  Done. Import STEP into FreeCAD/Fusion360/Ansys for analysis.")
    print("  Chassis STEP/STL ready for 3D print slicing.")
    print("=" * 70)


if __name__ == "__main__":
    main()
