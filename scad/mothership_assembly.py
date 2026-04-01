"""
AstraAnt Seed Mothership -- Parametric Spacecraft Bus Assembly
==============================================================

CadQuery parametric model of the ESPA-class seed mothership.
Every component placed at real positions with real clearances.

VEHICLE SPECS:
  Envelope:  400 x 300 x 300 mm (external)
  Structure: Al 6061-T6, corner longerons + sheet panels
  Total:     ~41 kg (dry)

Usage:
  python scad/mothership_assembly.py

Outputs:
  scad/vendor_parts/mothership_assembly.step   (colored assembly)
  scad/vendor_parts/mothership_assembly.stl    (merged mesh)
  scad/vendor_parts/propulsion.stl             (per-subsystem)
  scad/vendor_parts/electronics.stl
  scad/vendor_parts/chemistry.stl
  scad/vendor_parts/biology.stl
  scad/vendor_parts/deployables.stl
  scad/vendor_parts/structure.stl
"""

import os
import sys
import math
import warnings

import cadquery as cq
from cadquery import importers, Location, Vector, Color

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_RAW = os.path.join(SCRIPT_DIR, "vendor_parts", "raw")
OUT_DIR = os.path.join(SCRIPT_DIR, "vendor_parts")

ESP32_STEP = os.path.join(VENDOR_RAW, "esp32",
                          "ESP32-S3-WROOM-1_devkit_2xUSBC_c.step")
PUMP_STEP = os.path.join(VENDOR_RAW, "pump", "Peristaltic Pump head.stp")

# ---------------------------------------------------------------------------
# Material constants (densities in kg/m^3)
# ---------------------------------------------------------------------------
RHO_AL = 2700       # Al 6061-T6
RHO_STEEL = 7900    # Stainless steel
RHO_IODINE = 4930   # Solid iodine
RHO_LEAD = 11340    # Lead alloy anode
RHO_PCB = 1850      # FR4 PCB
RHO_LIPO = 2100     # Li-ion prismatic cell avg
RHO_KAPTON = 1420   # Kapton polyimide
RHO_GENERIC = 1500  # Generic placeholder

# ---------------------------------------------------------------------------
# Envelope (all dimensions in mm)
# ---------------------------------------------------------------------------
ENV_X = 400.0   # length (thrust axis, longerons run along X)
ENV_Y = 300.0   # width
ENV_Z = 300.0   # height

# Structural members
LONGERON = 20.0       # L-channel leg width
LONG_T = 2.0          # L-channel wall thickness
PANEL_T = 1.5         # skin panel thickness
SHELF_T = 1.5         # internal shelf thickness

# Shelf positions (from bottom face, measured along X axis)
SHELF_1 = 100.0
SHELF_2 = 200.0
SHELF_3 = 300.0

# Bay boundaries (X range, origin at bottom-center of bus)
# Bay 1: 0 to 100 mm   (propulsion)
# Bay 2: 100 to 200 mm  (electronics + power)
# Bay 3: 200 to 300 mm  (chemistry)
# Bay 4: 300 to 400 mm  (biology + wire factory)

# Thruster cutout
THRUSTER_CUTOUT_DIA = 30.0

# ---------------------------------------------------------------------------
# Color palette (subsystem coding)
# ---------------------------------------------------------------------------
COL_STRUCT    = Color(0.70, 0.70, 0.72, 1.0)   # light aluminum
COL_SHELF     = Color(0.60, 0.60, 0.62, 1.0)   # slightly darker shelf
COL_PROP      = Color(0.20, 0.60, 0.85, 1.0)   # propulsion blue
COL_ELECT     = Color(0.15, 0.65, 0.25, 1.0)   # electronics green
COL_POWER     = Color(0.85, 0.55, 0.10, 1.0)   # power orange
COL_CHEM      = Color(0.75, 0.20, 0.20, 1.0)   # chemistry red
COL_BIO       = Color(0.55, 0.80, 0.30, 1.0)   # biology lime
COL_DEPLOY    = Color(0.15, 0.30, 0.75, 1.0)   # deployable navy
COL_SOLAR     = Color(0.10, 0.20, 0.60, 1.0)   # solar panel dark blue
COL_ARM       = Color(0.50, 0.50, 0.55, 1.0)   # arm gray
COL_MEMBRANE  = Color(0.85, 0.75, 0.25, 1.0)   # membrane gold
COL_COMP      = Color(0.30, 0.30, 0.35, 1.0)   # compute dark gray
COL_FLUID     = Color(0.40, 0.70, 0.75, 1.0)   # fluid teal
COL_EWIN      = Color(0.60, 0.35, 0.20, 1.0)   # electro-winning copper
COL_WIRE      = Color(0.80, 0.45, 0.15, 1.0)   # wire spool copper

# ---------------------------------------------------------------------------
# Vendor STEP import helper
# ---------------------------------------------------------------------------
def load_step(path, fallback_dims=None):
    """Import a STEP file. If it fails, return a parametric box approximation."""
    if os.path.isfile(path):
        try:
            wp = importers.importStep(path)
            return wp
        except Exception as e:
            print(f"  WARN: STEP import failed for {path}: {e}")
    if fallback_dims:
        x, y, z = fallback_dims
        return cq.Workplane("XY").box(x, y, z)
    return cq.Workplane("XY").box(10, 10, 10)

# ---------------------------------------------------------------------------
# Mass ledger -- every component tracked
# ---------------------------------------------------------------------------
class MassLedger:
    """Track every component mass, position, and subsystem."""
    def __init__(self):
        self.entries = []  # (name, subsystem, mass_kg, x, y, z)

    def add(self, name, subsys, mass_kg, x, y, z):
        self.entries.append((name, subsys, mass_kg, x, y, z))

    def total_mass(self):
        return sum(e[2] for e in self.entries)

    def center_of_mass(self):
        m_tot = self.total_mass()
        if m_tot == 0:
            return (0, 0, 0)
        cx = sum(e[2] * e[3] for e in self.entries) / m_tot
        cy = sum(e[2] * e[4] for e in self.entries) / m_tot
        cz = sum(e[2] * e[5] for e in self.entries) / m_tot
        return (cx, cy, cz)

    def moments_of_inertia(self):
        """Point-mass approximation of Ixx, Iyy, Izz about CoM."""
        cx, cy, cz = self.center_of_mass()
        Ixx = Iyy = Izz = 0.0
        for _, _, m, x, y, z in self.entries:
            dx, dy, dz = x - cx, y - cy, z - cz
            Ixx += m * (dy**2 + dz**2)
            Iyy += m * (dx**2 + dz**2)
            Izz += m * (dx**2 + dy**2)
        # Convert mm^2 to m^2 for kg*m^2
        return (Ixx * 1e-6, Iyy * 1e-6, Izz * 1e-6)

    def report(self):
        lines = []
        lines.append("=" * 90)
        lines.append("  SEED MOTHERSHIP ASSEMBLY -- MASS PROPERTIES REPORT")
        lines.append("=" * 90)
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
            lines.append(f"--- {subsys} ({sub_mass:.2f} kg) ---")
            for name, mass, x, y, z in items:
                lines.append(
                    f"  {name:<40} {mass:>6.3f} kg  "
                    f"@ ({x:>7.1f}, {y:>7.1f}, {z:>7.1f}) mm"
                )
            lines.append("")

        m_tot = self.total_mass()
        cx, cy, cz = self.center_of_mass()
        Ixx, Iyy, Izz = self.moments_of_inertia()

        lines.append("=" * 90)
        lines.append(f"  TOTAL MASS:         {m_tot:.2f} kg")
        lines.append(f"  CENTER OF MASS:     ({cx:.1f}, {cy:.1f}, {cz:.1f}) mm")
        lines.append(f"  GEOMETRIC CENTER:   ({ENV_X/2:.1f}, 0.0, 0.0) mm")
        lines.append(f"  CoM OFFSET:         "
                     f"dX={cx - ENV_X/2:.1f}  dY={cy:.1f}  dZ={cz:.1f} mm")
        lines.append("")
        lines.append(f"  MOMENTS OF INERTIA (about CoM, point-mass approx):")
        lines.append(f"    Ixx = {Ixx:.4f} kg*m^2  (roll)")
        lines.append(f"    Iyy = {Iyy:.4f} kg*m^2  (pitch)")
        lines.append(f"    Izz = {Izz:.4f} kg*m^2  (yaw)")
        lines.append("")

        # Thrust axis check
        # Ion thruster at X=0, nozzle -X. Thrust axis is +X.
        # Ideal: CoM on X axis (Y=0, Z=0)
        offset_yz = math.sqrt(cy**2 + cz**2)
        lines.append(f"  THRUST AXIS CHECK:")
        lines.append(f"    Ion thruster axis: +X through (0, 0, 0)")
        lines.append(f"    CoM lateral offset: {offset_yz:.1f} mm "
                     f"({'PASS' if offset_yz < 20 else 'WARN'} -- limit 20 mm)")
        lines.append("=" * 90)
        return "\n".join(lines)

# ---------------------------------------------------------------------------
# Coordinate system
# ---------------------------------------------------------------------------
# Origin: center of bottom panel (thruster face)
#   X: thrust axis, 0 at bottom, +X toward top (400mm)
#   Y: solar panel axis, 0 at center
#   Z: vertical in stowed config, 0 at center
#
# Bottom panel is at X=0, top panel at X=400.
# Side panels at Y=+/-150, Z=+/-150.

ledger = MassLedger()

# ===========================================================================
# STRUCTURE
# ===========================================================================
def build_structure():
    """Build the structural frame: 4 longerons, 6 panels, 3 shelves."""
    parts = []

    # --- 4 corner longerons (L-channel along X axis) ---
    # Positions: (Y, Z) at four corners of the 300x300 cross-section
    # Longerons sit at corners, inset by their own width
    inner_y = ENV_Y / 2 - LONGERON
    inner_z = ENV_Z / 2 - LONGERON

    long_idx = 0
    for sy in (-1, 1):
        for sz in (-1, 1):
            yc = sy * (ENV_Y / 2 - LONGERON / 2)
            zc = sz * (ENV_Z / 2 - LONGERON / 2)

            # L-channel = two perpendicular flanges
            # Flange 1: along Y face
            f1 = (cq.Workplane("YZ")
                  .center(yc, zc)
                  .rect(LONGERON, LONG_T)
                  .extrude(ENV_X))
            # Shift flange so bottom face aligns with inner corner
            f1 = f1.translate((0,
                               0,
                               sz * (LONGERON / 2 - LONG_T / 2)))

            # Flange 2: along Z face
            f2 = (cq.Workplane("YZ")
                  .center(yc, zc)
                  .rect(LONG_T, LONGERON)
                  .extrude(ENV_X))
            f2 = f2.translate((0,
                               sy * (LONGERON / 2 - LONG_T / 2),
                               0))

            parts.append((f"longeron_{long_idx}_flange_y", f1))
            parts.append((f"longeron_{long_idx}_flange_z", f2))
            long_idx += 1

    # Mass: 4 longerons, each ~2 flanges x (20 x 2 x 400) mm = 32000 mm^3
    # Total Al volume ~4 * 2 * 32000 = 256000 mm^3 but with overlap at corners
    # BOM says 2.5 kg for entire frame, so log structure mass at geometric center
    ledger.add("Al frame (longerons)", "STRUCTURE", 1.8,
               ENV_X / 2, 0, 0)

    # --- 6 skin panels ---
    # Bottom panel (X=0 face) with thruster cutout
    bottom = (cq.Workplane("YZ")
              .rect(ENV_Y, ENV_Z)
              .circle(THRUSTER_CUTOUT_DIA / 2)
              .extrude(PANEL_T))
    parts.append(("panel_bottom", bottom))

    # Top panel (X=400 face)
    top = (cq.Workplane("YZ")
           .rect(ENV_Y, ENV_Z)
           .extrude(PANEL_T)
           .translate((ENV_X - PANEL_T, 0, 0)))
    parts.append(("panel_top", top))

    # +Y side panel
    py_panel = (cq.Workplane("XZ")
                .rect(ENV_X, ENV_Z)
                .extrude(PANEL_T)
                .translate((ENV_X / 2, ENV_Y / 2 - PANEL_T, 0)))
    parts.append(("panel_+Y", py_panel))

    # -Y side panel
    my_panel = (cq.Workplane("XZ")
                .rect(ENV_X, ENV_Z)
                .extrude(PANEL_T)
                .translate((ENV_X / 2, -ENV_Y / 2, 0)))
    parts.append(("panel_-Y", my_panel))

    # +Z side panel
    pz_panel = (cq.Workplane("XY")
                .rect(ENV_X, ENV_Y)
                .extrude(PANEL_T)
                .translate((ENV_X / 2, 0, ENV_Z / 2 - PANEL_T)))
    parts.append(("panel_+Z", pz_panel))

    # -Z side panel
    mz_panel = (cq.Workplane("XY")
                .rect(ENV_X, ENV_Y)
                .extrude(PANEL_T)
                .translate((ENV_X / 2, 0, -ENV_Z / 2)))
    parts.append(("panel_-Z", mz_panel))

    ledger.add("Al panels (6x skin)", "STRUCTURE", 0.5,
               ENV_X / 2, 0, 0)

    # --- 3 internal shelves ---
    for i, sx in enumerate([SHELF_1, SHELF_2, SHELF_3]):
        shelf = (cq.Workplane("YZ")
                 .rect(ENV_Y - 2 * LONGERON, ENV_Z - 2 * LONGERON)
                 .extrude(SHELF_T)
                 .translate((sx - SHELF_T / 2, 0, 0)))
        parts.append((f"shelf_{i+1}", shelf))

    ledger.add("Al shelves (3x internal)", "STRUCTURE", 0.2,
               ENV_X / 2, 0, 0)

    # Deployment springs, rock clamp, fasteners
    ledger.add("Deployment springs + hinges", "STRUCTURE", 0.3,
               ENV_X - 20, 0, 0)
    ledger.add("Rock clamp + aperture frame", "STRUCTURE", 0.4,
               ENV_X - 10, 0, 0)
    ledger.add("Fasteners + brackets (SS)", "STRUCTURE", 0.2,
               ENV_X / 2, 0, 0)

    return parts


# ===========================================================================
# BAY 1: PROPULSION (X = 0 to 100 mm)
# ===========================================================================
def build_propulsion():
    """BIT-3 ion thruster, PPU, iodine tank, N2 cold gas system."""
    parts = []
    bay_center_x = 50.0  # midpoint of bay 1

    # --- BIT-3 ion thruster ---
    # Cylinder 30mm dia x 50mm, nozzle pointing -X (out the bottom)
    thruster_body = (cq.Workplane("YZ")
                     .circle(15)
                     .extrude(50)
                     .translate((0, 0, 0)))

    # Conical nozzle (flares outward toward -X)
    nozzle = (cq.Workplane("YZ")
              .circle(15)
              .workplane(offset=-20)
              .circle(10)
              .loft())
    nozzle = nozzle.translate((-20, 0, 0))

    # Grid face (thin disc at +X end of thruster body)
    grid = (cq.Workplane("YZ")
            .circle(14)
            .circle(12)
            .extrude(2)
            .translate((50, 0, 0)))

    parts.append(("thruster_body", thruster_body))
    parts.append(("thruster_nozzle", nozzle))
    parts.append(("thruster_grid", grid))

    ledger.add("BIT-3 ion thruster", "PROPULSION", 0.8,
               25, 0, 0)

    # --- PPU (Power Processing Unit) ---
    # Box 80x60x30mm, beside thruster
    ppu = (cq.Workplane("XY")
           .box(80, 60, 30)
           .translate((bay_center_x, -60, 50)))

    parts.append(("ppu", ppu))
    ledger.add("BIT-3 PPU", "PROPULSION", 0.7,
               bay_center_x, -60, 50)

    # --- Iodine tank ---
    # 5 kg iodine at 4930 kg/m^3 = 1015 cm^3 = 1,015,000 mm^3
    # Cylinder 80mm dia x 60mm tall (fits in bay 1 height)
    # CENTERED on Y=0 and Z=-30 for CoM balance (heaviest propulsion item)
    iodine_tank = (cq.Workplane("YZ")
                   .circle(40)
                   .extrude(60)
                   .translate((20, 0, -30)))

    parts.append(("iodine_tank", iodine_tank))
    ledger.add("Iodine propellant tank (5 kg I2)", "PROPULSION", 5.5,
               50, 0, -30)

    # --- N2 cold gas system ---
    # Sphere 60mm dia
    n2_tank = (cq.Workplane("XY")
               .sphere(30))
    n2_tank = n2_tank.translate((bay_center_x, 0, 80))

    parts.append(("n2_tank", n2_tank))
    ledger.add("N2 cold gas tank + thrusters", "PROPULSION", 1.1,
               bay_center_x, 0, 80)

    # 4 small thruster nozzles on exterior corners (attitude control)
    for sy in (-1, 1):
        for sz in (-1, 1):
            noz = (cq.Workplane("XY")
                   .circle(4)
                   .workplane(offset=8)
                   .circle(2)
                   .loft())
            ny = sy * (ENV_Y / 2 - 5)
            nz = sz * (ENV_Z / 2 - 5)
            noz = noz.translate((10, ny, nz))
            parts.append((f"rcs_nozzle_{sy}_{sz}", noz))

    return parts


# ===========================================================================
# BAY 2: ELECTRONICS + POWER (X = 100 to 200 mm)
# ===========================================================================
def build_electronics():
    """ESP32-S3 TMR cluster, star tracker, radios, MPPT, batteries."""
    parts = []
    bay_center_x = 150.0

    # --- 3x ESP32-S3 modules (TMR voting) ---
    esp32_spacing = 35.0  # center-to-center along Y
    for i in range(3):
        y_pos = (i - 1) * esp32_spacing
        esp = load_step(ESP32_STEP, fallback_dims=(25.5, 18, 5))
        # Vendor STEP is at origin; translate to bay position
        # ESP32 board: ~28 x 64 x 5.5 mm from measured BB
        # Place on shelf 1 (X=100), standing in Y
        esp = esp.translate((SHELF_1 + 5, y_pos - 10, 60))
        parts.append((f"esp32_s3_{i}", esp))

    ledger.add("ESP32-S3 TMR cluster (3x)", "ELECTRONICS", 0.045,
               bay_center_x, 0, 60)

    # --- Star tracker ---
    # Box 30x30x30mm with lens tube on top
    tracker_body = (cq.Workplane("XY")
                    .box(30, 30, 30))
    tracker_lens = (cq.Workplane("XY")
                    .circle(8)
                    .extrude(15)
                    .translate((0, 0, 22.5)))
    tracker = tracker_body.union(tracker_lens)
    tracker = tracker.translate((bay_center_x, -80, 80))
    parts.append(("star_tracker", tracker))
    ledger.add("Star tracker (nano class)", "ELECTRONICS", 0.15,
               bay_center_x, -80, 80)

    # --- Watchdog board ---
    watchdog = (cq.Workplane("XY").box(40, 30, 8)
                .translate((bay_center_x, 80, 80)))
    parts.append(("watchdog_board", watchdog))
    ledger.add("Watchdog + power cycling board", "ELECTRONICS", 0.05,
               bay_center_x, 80, 80)

    # --- UHF radio + patch antenna ---
    uhf = (cq.Workplane("XY").box(80, 80, 15)
           .translate((bay_center_x, 0, -70)))
    parts.append(("uhf_radio", uhf))
    ledger.add("UHF radio + patch antenna", "ELECTRONICS", 0.3,
               bay_center_x, 0, -70)

    # --- X-band backup transmitter ---
    xband = (cq.Workplane("XY").box(50, 30, 15)
             .translate((bay_center_x + 30, 0, -90)))
    parts.append(("xband_tx", xband))
    ledger.add("X-band backup transmitter", "ELECTRONICS", 0.15,
               bay_center_x + 30, 0, -90)

    # --- Sun sensor + magnetometer ---
    sun_sensor = (cq.Workplane("XY").box(20, 20, 10)
                  .translate((bay_center_x, -100, -30)))
    parts.append(("sun_sensor_mag", sun_sensor))
    ledger.add("Sun sensor + magnetometer", "ELECTRONICS", 0.1,
               bay_center_x, -100, -30)

    # --- AS7341 spectral sensors (2x) ---
    for i, yz in enumerate([(100, 30), (-100, 30)]):
        spec = (cq.Workplane("XY").box(10, 10, 5)
                .translate((bay_center_x, yz[0], yz[1])))
        parts.append((f"as7341_{i}", spec))
    ledger.add("AS7341 spectral sensors (2x)", "ELECTRONICS", 0.04,
               bay_center_x, 0, 30)

    # --- MPPT + power distribution ---
    mppt = (cq.Workplane("XY").box(60, 40, 20)
            .translate((bay_center_x, 60, -30)))
    parts.append(("mppt", mppt))
    ledger.add("MPPT + power distribution", "ELECTRONICS", 0.4,
               bay_center_x, 60, -30)

    # --- Battery pack (2x prismatic cells) ---
    # Positioned at geometric center of bay for CoM balance
    for i, y_off in enumerate((-25, 25)):
        batt = (cq.Workplane("XY").box(80, 60, 20)
                .translate((bay_center_x, y_off, 0)))
        parts.append((f"battery_{i}", batt))
    ledger.add("Li-ion battery pack (2x 100Wh)", "POWER", 1.6,
               bay_center_x, 0, 0)

    # --- Wiring harness mass ---
    ledger.add("Wiring harness (main bus)", "ELECTRONICS", 0.5,
               ENV_X / 2, 0, 0)

    return parts


# ===========================================================================
# BAY 3: CHEMISTRY (X = 200 to 300 mm)
# ===========================================================================
def build_chemistry():
    """Peristaltic pump, electro-winning cell, DC-DC, fluid system."""
    parts = []
    bay_center_x = 250.0

    # --- Peristaltic pump (vendor STEP) ---
    pump = load_step(PUMP_STEP, fallback_dims=(63, 85, 58))
    # Center pump on shelf 2 (X=200), motor shaft pointing +X
    pump = pump.translate((SHELF_2 + 5, 0, -20))
    parts.append(("peristaltic_pump", pump))
    ledger.add("Peristaltic pump (2000 L/hr)", "CHEMISTRY", 2.5,
               bay_center_x - 20, 0, -20)

    # --- Spare pump head ---
    spare_pump = load_step(PUMP_STEP, fallback_dims=(63, 85, 58))
    spare_pump = spare_pump.translate((SHELF_2 + 5, -90, -20))
    parts.append(("spare_pump_head", spare_pump))
    ledger.add("Spare pump head + hoses", "CHEMISTRY", 1.0,
               bay_center_x - 20, -90, -20)

    # --- Electro-winning cell ---
    # Rectangular tank 120x80x60mm
    # Outer shell
    ew_outer = cq.Workplane("XY").box(120, 80, 60)
    # Hollow interior (wall thickness 3mm)
    ew_inner = cq.Workplane("XY").box(114, 74, 57).translate((0, 0, 1.5))
    ew_tank = ew_outer.cut(ew_inner)

    # Lead anode plate (center)
    anode = (cq.Workplane("XY").box(100, 2, 50))
    ew_tank = ew_tank.union(anode)

    # 2 SS cathode plates (flanking the anode at +/-20mm Y)
    for y_off in (-20, 20):
        cathode = (cq.Workplane("XY").box(100, 1.5, 50)
                   .translate((0, y_off, 0)))
        ew_tank = ew_tank.union(cathode)

    ew_tank = ew_tank.translate((bay_center_x, 70, 40))
    parts.append(("electrowinning_cell", ew_tank))
    ledger.add("Electro-winning cell (Pb anode + SS cathodes)", "CHEMISTRY", 3.1,
               bay_center_x, 70, 40)

    # Electrode mounting frame
    ledger.add("Electrode mounting frame", "CHEMISTRY", 0.3,
               bay_center_x, 70, 40)

    # --- DC-DC converter ---
    dcdc = (cq.Workplane("XY").box(50, 40, 20)
            .translate((bay_center_x + 30, 70, -40)))
    parts.append(("dcdc_converter", dcdc))
    ledger.add("DC-DC converter (2V, 500A)", "CHEMISTRY", 0.3,
               bay_center_x + 30, 70, -40)

    # --- PTFE tubing (routed along walls) ---
    # Model as a curved tube path along the bay interior
    tube_path = (cq.Workplane("XZ")
                 .moveTo(SHELF_2 + 10, -100)
                 .lineTo(SHELF_3 - 10, -100)
                 .lineTo(SHELF_3 - 10, 100)
                 .lineTo(SHELF_2 + 10, 100))
    # Simple representation: thin box along -Z wall
    tubing = (cq.Workplane("XY").box(80, 6, 6)
              .translate((bay_center_x, -110, -90)))
    parts.append(("ptfe_tubing", tubing))
    ledger.add("PTFE tubing + fittings (10m)", "CHEMISTRY", 0.8,
               bay_center_x, -110, -90)

    # --- Collapsible bladder (stowed) ---
    bladder = (cq.Workplane("XY").box(60, 40, 15)
               .translate((bay_center_x - 30, -80, -60)))
    parts.append(("bladder_200L", bladder))
    ledger.add("Collapsible bladder (200L, stowed)", "CHEMISTRY", 0.4,
               bay_center_x - 30, -80, -60)

    # --- Flow + pressure sensors ---
    flow_sns = (cq.Workplane("XY").box(20, 15, 10)
                .translate((bay_center_x, -110, -70)))
    parts.append(("flow_sensors", flow_sns))
    ledger.add("Flow + pressure sensors", "CHEMISTRY", 0.1,
               bay_center_x, -110, -70)

    # --- Chemistry package items (mounted externally or stowed) ---
    # Copper seed tape
    ledger.add("Copper seed tape (25m roll)", "CHEMISTRY", 0.1,
               bay_center_x, -100, 50)
    # NdFeB magnet
    ledger.add("NdFeB permanent magnet", "CHEMISTRY", 0.1,
               bay_center_x + 40, -100, 50)

    return parts


# ===========================================================================
# BAY 4: BIOLOGY + WIRE FACTORY (X = 300 to 400 mm)
# ===========================================================================
def build_biology():
    """Bacteria bay, wire factory, fluid manifold, printer bot seed tray."""
    parts = []
    bay_center_x = 350.0

    # --- Bacteria bay (insulated box) ---
    # Outer shell with thicker walls for thermal isolation
    bact_outer = cq.Workplane("XY").box(60, 40, 30)
    bact_inner = cq.Workplane("XY").box(50, 30, 24).translate((0, 0, 1))
    bacteria_bay = bact_outer.cut(bact_inner)
    bacteria_bay = bacteria_bay.translate((bay_center_x, -60, 60))
    parts.append(("bacteria_bay", bacteria_bay))
    ledger.add("Freeze-dried bacteria (4 species)", "BIOLOGY", 0.2,
               bay_center_x, -60, 60)
    ledger.add("Nutrient salts + trace minerals", "BIOLOGY", 0.3,
               bay_center_x, -60, 60)
    ledger.add("Backup culture vials (sealed)", "BIOLOGY", 0.1,
               bay_center_x, -60, 40)
    ledger.add("pH + temperature sensors", "BIOLOGY", 0.05,
               bay_center_x, -60, 50)

    # --- Wire factory ---
    # Spool mechanism 40mm dia x 30mm + cutter + motor
    spool = (cq.Workplane("YZ")
             .circle(20)
             .extrude(30)
             .translate((bay_center_x - 15, 60, 60)))
    # Cutter blade (thin disc)
    cutter = (cq.Workplane("YZ")
              .circle(12)
              .extrude(1)
              .translate((bay_center_x + 18, 60, 60)))
    # Coiling motor
    motor = (cq.Workplane("YZ")
             .circle(8)
             .extrude(20)
             .translate((bay_center_x - 30, 60, 60)))

    parts.append(("wire_spool", spool))
    parts.append(("wire_cutter", cutter))
    parts.append(("wire_motor", motor))
    ledger.add("Wire factory (spool + cutter + motor)", "BIOLOGY", 0.5,
               bay_center_x, 60, 60)
    ledger.add("Seed wire spool (0.5mm Cu, 200m)", "BIOLOGY", 0.3,
               bay_center_x, 60, 60)

    # --- WAAM print heads (2x, stowed) ---
    for i, y_off in enumerate((-40, 40)):
        waam = (cq.Workplane("XY").box(30, 20, 15)
                .translate((bay_center_x, y_off, -60)))
        parts.append((f"waam_head_{i}", waam))
    ledger.add("WAAM print heads (2x)", "BIOLOGY", 0.6,
               bay_center_x, 0, -60)

    # --- Fluid manifold ---
    # T-junction plumbing block
    manifold_body = cq.Workplane("XY").box(60, 40, 20)
    # 3 tube ports (cylinders)
    for angle in (0, 120, 240):
        port = (cq.Workplane("XY")
                .circle(4)
                .extrude(10)
                .translate((math.cos(math.radians(angle)) * 20,
                            math.sin(math.radians(angle)) * 15,
                            10)))
        manifold_body = manifold_body.union(port)
    manifold_body = manifold_body.translate((bay_center_x, 0, -20))
    parts.append(("fluid_manifold", manifold_body))
    ledger.add("Fluid manifold (T-junction)", "BIOLOGY", 0.5,
               bay_center_x, 0, -20)

    # --- Printer bot seed tray ---
    tray = (cq.Workplane("XY").box(80, 60, 15)
            .translate((bay_center_x, 0, 20)))
    parts.append(("printer_bot_tray", tray))
    ledger.add("SG90 servo tray (50 units)", "BIOLOGY", 0.45,
               bay_center_x, 0, 25)
    ledger.add("ESP32/RP2040 tray (10 units)", "BIOLOGY", 0.03,
               bay_center_x, 0, 20)
    ledger.add("NdFeB magnet discs (80 units)", "BIOLOGY", 0.16,
               bay_center_x, 0, 15)
    ledger.add("Wire feed roller bearings (20)", "BIOLOGY", 0.04,
               bay_center_x, 0, 10)

    # Tool heads
    ledger.add("Tool heads (gripper/driver/probe, 2x)", "BIOLOGY", 0.3,
               bay_center_x, 40, 20)

    return parts


# ===========================================================================
# DEPLOYABLES (exterior)
# ===========================================================================
def build_deployables():
    """Solar wings, robotic arms, membrane spool, concentrators, airlock."""
    parts = []

    # --- Solar wings (2x, stowed against +Y/-Y panels) ---
    # Each: 2000 x 800 x 15 mm deployed
    # Stowed: folded flat against the Y-face, so 800 x 400 x 15
    # Model STOWED configuration (folded in half against body)
    for side, label in ((1, "+Y"), (-1, "-Y")):
        # Stowed panel: folded flat against side face
        # Two folds: 800mm becomes 2 x 400mm stacked
        wing_folded = (cq.Workplane("XZ")
                       .rect(ENV_X - 20, ENV_Z - 20)
                       .extrude(15))
        y_pos = side * (ENV_Y / 2 + 7.5)
        wing_folded = wing_folded.translate((ENV_X / 2, y_pos, 0))
        parts.append((f"solar_wing_{label}_stowed", wing_folded))

        # Hinge cylinder at attachment edge
        hinge = (cq.Workplane("XY")
                 .circle(3)
                 .extrude(ENV_X - 40)
                 .translate((20, side * (ENV_Y / 2), -ENV_Z / 2 + 15)))
        parts.append((f"solar_hinge_{label}", hinge))

    ledger.add("Solar wing +Y (2 m^2)", "DEPLOYABLES", 1.5,
               ENV_X / 2, ENV_Y / 2 + 7.5, 0)
    ledger.add("Solar wing -Y (2 m^2)", "DEPLOYABLES", 1.5,
               ENV_X / 2, -ENV_Y / 2 - 7.5, 0)

    # --- Robotic arms (2x, stowed along +Z/-Z longerons) ---
    for side, label in ((1, "+Z"), (-1, "-Z")):
        # Each arm: 3 segments (shoulder 150mm, upper 150mm, forearm 150mm)
        # Stowed: folded along the longeron
        # Shoulder joint at mid-bus for CoM balance
        shoulder_x = ENV_X * 0.4
        shoulder_z = side * (ENV_Z / 2 + 10)

        shoulder = (cq.Workplane("XY").sphere(10)
                    .translate((shoulder_x, 0, shoulder_z)))
        parts.append((f"arm_shoulder_{label}", shoulder))

        # Upper segment (along X, folded against body)
        upper = (cq.Workplane("YZ")
                 .circle(7.5)
                 .extrude(150)
                 .translate((shoulder_x, 0, shoulder_z)))
        parts.append((f"arm_upper_{label}", upper))

        # Elbow joint
        elbow = (cq.Workplane("XY").sphere(8)
                 .translate((shoulder_x + 150, 0, shoulder_z)))
        parts.append((f"arm_elbow_{label}", elbow))

        # Forearm segment
        forearm = (cq.Workplane("YZ")
                   .circle(6)
                   .extrude(120)
                   .translate((shoulder_x + 150, 0, shoulder_z)))
        parts.append((f"arm_forearm_{label}", forearm))

        # Wrist joint
        wrist = (cq.Workplane("XY").sphere(6)
                 .translate((shoulder_x + 270, 0, shoulder_z)))
        parts.append((f"arm_wrist_{label}", wrist))

        # Gripper (fork shape)
        grip_base = (cq.Workplane("YZ")
                     .rect(20, 5)
                     .extrude(15)
                     .translate((shoulder_x + 270, 0, shoulder_z)))
        for g_side in (-1, 1):
            finger = (cq.Workplane("YZ")
                      .rect(4, 4)
                      .extrude(25)
                      .translate((shoulder_x + 285,
                                  g_side * 8,
                                  shoulder_z)))
            grip_base = grip_base.union(finger)
        parts.append((f"arm_gripper_{label}", grip_base))

    ledger.add("Robotic arm +Z (3-DOF + gripper)", "DEPLOYABLES", 1.85,
               ENV_X * 0.4 + 135, 0, ENV_Z / 2 + 10)
    ledger.add("Robotic arm -Z (3-DOF + gripper)", "DEPLOYABLES", 1.85,
               ENV_X * 0.4 + 135, 0, -ENV_Z / 2 - 10)
    ledger.add("Arm cable harnesses (2x)", "DEPLOYABLES", 0.2,
               ENV_X * 0.4, 0, 0)
    ledger.add("Vacuum lubricant Braycote (2x)", "DEPLOYABLES", 0.1,
               ENV_X * 0.4, 0, 0)

    # --- Membrane spool ---
    # Cylinder 150mm dia x 300mm, mounted on +X face (top panel)
    # CENTERED on Y=0 for CoM balance (this is the heaviest single item)
    # Spool axis along Y, sitting flush on top panel
    membrane = (cq.Workplane("XZ")
                .circle(75)
                .circle(30)  # hollow core
                .extrude(300)
                .translate((ENV_X + 75, -150, 0)))  # centered on Y
    parts.append(("membrane_spool", membrane))
    # CoM of spool is at its geometric center
    ledger.add("Kapton+Kevlar membrane spool (55 m^2)", "DEPLOYABLES", 8.0,
               ENV_X + 75, 0, 0)

    # --- Mylar concentrators (2x, stowed on -Z face) ---
    for i, z_off in enumerate((60, -60)):
        mylar = (cq.Workplane("XY")
                 .rect(200, 200)
                 .extrude(5)
                 .translate((ENV_X / 2, 0, -ENV_Z / 2 - 5 * (i + 1))))
        parts.append((f"mylar_concentrator_{i}", mylar))
    ledger.add("Mylar concentrator (2 m^2)", "DEPLOYABLES", 0.4,
               ENV_X / 2, 0, -ENV_Z / 2 - 5)
    ledger.add("Spare Mylar concentrator (2 m^2)", "DEPLOYABLES", 0.4,
               ENV_X / 2, 0, -ENV_Z / 2 - 10)

    # --- Material airlock ---
    # Centered on Y=0 on bottom face for CoM balance
    airlock = (cq.Workplane("XY").box(60, 60, 40)
               .translate((20, 0, -ENV_Z / 2 - 20)))
    parts.append(("material_airlock", airlock))
    ledger.add("Material airlock", "DEPLOYABLES", 0.3,
               20, 0, -ENV_Z / 2 - 20)

    # --- Miscellaneous exterior ---
    ledger.add("Silicone gaskets + sealant", "MISC", 0.4,
               ENV_X / 2, 0, 0)
    ledger.add("MLI thermal blanket", "MISC", 0.3,
               ENV_X / 2, 0, 0)

    return parts


# ===========================================================================
# ASSEMBLY
# ===========================================================================
def build_assembly():
    """Build the complete mothership assembly with color-coded subsystems."""

    print("Building AstraAnt Seed Mothership Assembly...")
    print(f"  Envelope: {ENV_X:.0f} x {ENV_Y:.0f} x {ENV_Z:.0f} mm")
    print()

    assy = cq.Assembly(name="seed_mothership")

    # Subsystem part collectors for individual STL export
    subsys_parts = {
        "structure": [],
        "propulsion": [],
        "electronics": [],
        "chemistry": [],
        "biology": [],
        "deployables": [],
    }

    # --- Structure ---
    print("  [1/6] Building structural frame...")
    struct_parts = build_structure()
    for name, part in struct_parts:
        assy.add(part, name=f"struct_{name}", color=COL_STRUCT)
        subsys_parts["structure"].append(part)

    # --- Propulsion (Bay 1) ---
    print("  [2/6] Building propulsion bay...")
    prop_parts = build_propulsion()
    for name, part in prop_parts:
        assy.add(part, name=f"prop_{name}", color=COL_PROP)
        subsys_parts["propulsion"].append(part)

    # --- Electronics + Power (Bay 2) ---
    print("  [3/6] Building electronics bay...")
    elec_parts = build_electronics()
    for name, part in elec_parts:
        col = COL_POWER if "battery" in name else COL_ELECT
        assy.add(part, name=f"elec_{name}", color=col)
        subsys_parts["electronics"].append(part)

    # --- Chemistry (Bay 3) ---
    print("  [4/6] Building chemistry bay...")
    chem_parts = build_chemistry()
    for name, part in chem_parts:
        col = COL_EWIN if "electro" in name else (
              COL_FLUID if "pump" in name or "tube" in name or "bladder" in name
              else COL_CHEM)
        assy.add(part, name=f"chem_{name}", color=col)
        subsys_parts["chemistry"].append(part)

    # --- Biology + Wire Factory (Bay 4) ---
    print("  [5/6] Building biology bay...")
    bio_parts = build_biology()
    for name, part in bio_parts:
        col = COL_WIRE if "wire" in name or "spool" in name else (
              COL_BIO if "bact" in name else COL_BIO)
        assy.add(part, name=f"bio_{name}", color=col)
        subsys_parts["biology"].append(part)

    # --- Deployables ---
    print("  [6/6] Building deployables...")
    deploy_parts = build_deployables()
    for name, part in deploy_parts:
        col = (COL_SOLAR if "solar" in name or "hinge" in name
               else COL_MEMBRANE if "membrane" in name
               else COL_ARM if "arm" in name
               else COL_DEPLOY)
        assy.add(part, name=f"deploy_{name}", color=col)
        subsys_parts["deployables"].append(part)

    return assy, subsys_parts


def export_assembly(assy, subsys_parts):
    """Export STEP assembly, merged STL, and per-subsystem STLs."""

    os.makedirs(OUT_DIR, exist_ok=True)

    # --- Complete STEP assembly (preserves colors and structure) ---
    step_path = os.path.join(OUT_DIR, "mothership_assembly.step")
    print(f"\n  Exporting STEP: {step_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(step_path, exportType="STEP")
    size_mb = os.path.getsize(step_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Merged STL ---
    stl_path = os.path.join(OUT_DIR, "mothership_assembly.stl")
    print(f"  Exporting STL:  {stl_path}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        assy.save(stl_path, exportType="STL", tolerance=0.05, angularTolerance=0.1)
    size_mb = os.path.getsize(stl_path) / 1e6
    print(f"    Done ({size_mb:.1f} MB)")

    # --- Per-subsystem STLs ---
    print("  Exporting per-subsystem STLs:")
    for subsys_name, parts_list in subsys_parts.items():
        if not parts_list:
            continue
        sub_assy = cq.Assembly(name=subsys_name)
        for i, part in enumerate(parts_list):
            sub_assy.add(part, name=f"{subsys_name}_{i}")

        sub_path = os.path.join(OUT_DIR, f"{subsys_name}.stl")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            sub_assy.save(sub_path, exportType="STL",
                          tolerance=0.05, angularTolerance=0.1)
        size_kb = os.path.getsize(sub_path) / 1e3
        print(f"    {subsys_name}.stl ({size_kb:.0f} KB)")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 70)
    print("  AstraAnt Seed Mothership -- CadQuery Parametric Assembly")
    print("=" * 70)
    print()

    assy, subsys_parts = build_assembly()
    export_assembly(assy, subsys_parts)

    # --- Mass properties report ---
    print()
    print(ledger.report())

    # --- Quick sanity checks ---
    m_tot = ledger.total_mass()
    cx, cy, cz = ledger.center_of_mass()
    offset_yz = math.sqrt(cy**2 + cz**2)

    print()
    if abs(m_tot - 41) > 5:
        print(f"  WARNING: Total mass {m_tot:.1f} kg deviates from 41 kg target")
    else:
        print(f"  OK: Total mass {m_tot:.1f} kg within 5 kg of 41 kg target")

    if offset_yz > 20:
        print(f"  WARNING: CoM lateral offset {offset_yz:.1f} mm exceeds 20 mm limit")
    else:
        print(f"  OK: CoM lateral offset {offset_yz:.1f} mm within 20 mm limit")

    geo_cx = ENV_X / 2
    axial_off = cx - geo_cx
    # 60mm axial tolerance: membrane spool (8 kg external deployable) shifts
    # CoM forward. Ion thruster gimbal provides +/-5 deg TVC to compensate.
    if abs(axial_off) > 60:
        print(f"  WARNING: CoM axial offset {axial_off:.1f} mm exceeds 60 mm limit")
    else:
        print(f"  OK: CoM axial offset {axial_off:.1f} mm within 60 mm limit "
              f"(membrane spool is external)")
        print(f"      Ion thruster TVC compensates at {math.degrees(math.atan2(offset_yz, cx)):.1f} deg")

    print()
    print("  Output files:")
    for f in ["mothership_assembly.step", "mothership_assembly.stl",
              "structure.stl", "propulsion.stl", "electronics.stl",
              "chemistry.stl", "biology.stl", "deployables.stl"]:
        fp = os.path.join(OUT_DIR, f)
        if os.path.isfile(fp):
            print(f"    {fp}")

    print()
    print("  Done. Import STEP into FreeCAD/Fusion360 for full color assembly.")
    print("  Import individual STLs into Blender for rendering with materials.")
    print("=" * 70)


if __name__ == "__main__":
    main()
