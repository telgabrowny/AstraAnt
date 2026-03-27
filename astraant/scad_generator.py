"""OpenSCAD parametric model generator for tool heads and ant chassis.

Generates .scad files that can be opened in OpenSCAD, previewed, and
exported to STL for 3D printing. All dimensions from the tool catalog.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SCAD_DIR = Path(__file__).parent.parent / "scad"
CATALOG_TOOLS_DIR = Path(__file__).parent.parent / "catalog" / "tools"


def _magnetic_mount_scad(width: float = 15, depth: float = 10, magnet_d: float = 4) -> str:
    """Generate the universal magnetic mount interface (shared by all tools)."""
    return f"""
// Universal magnetic mount interface
// Clips between ant mandibles, held by neodymium magnets
module magnetic_mount(width={width}, depth={depth}, magnet_d={magnet_d}) {{
    difference() {{
        // Mount body
        cube([width, depth, 6], center=true);
        // Magnet pocket (recessed)
        translate([0, 0, 1.5])
            cylinder(d={magnet_d}+0.2, h=3, center=true, $fn=32);
        // Mandible grip grooves (two channels for ant mandibles)
        for (side = [-1, 1]) {{
            translate([side * (width/2 - 1.5), 0, 0])
                cube([2, depth+1, 3], center=true);
        }}
    }}
}}
"""


def generate_drill_head() -> str:
    """Generate OpenSCAD for the rotary drill head."""
    return f"""// AstraAnt Tool: Rotary Drill Head
// Print in PETG. Motor (N20) press-fits into body cavity.
// Bit is replaceable (insert from front).
//
// Print orientation: mount face on build plate (standing up)
// Supports: none needed
// Tolerance: 0.2mm for press-fit pockets

$fn = 64;

{_magnetic_mount_scad()}

// Parameters (edit these to customize)
body_diameter = 12;
body_length = 30;
bit_diameter = 8;
bit_length = 20;
motor_pocket_d = 12.2;   // N20 motor diameter + clearance
motor_pocket_depth = 25;
flute_count = 4;
flute_depth = 1.5;

module drill_body() {{
    difference() {{
        // Cylindrical body
        cylinder(d=body_diameter, h=body_length);
        // Motor pocket (hollowed from rear)
        translate([0, 0, -0.1])
            cylinder(d=motor_pocket_d, h=motor_pocket_depth);
        // Shaft hole through the front
        translate([0, 0, motor_pocket_depth - 1])
            cylinder(d=3.2, h=body_length, $fn=32);  // 3mm motor shaft + clearance
    }}
}}

module drill_bit() {{
    // Conical fluted bit (decorative — real bit is tungsten carbide insert)
    difference() {{
        cylinder(d1=bit_diameter, d2=2, h=bit_length);
        // Flutes (spiral approximated as straight channels)
        for (i = [0:flute_count-1]) {{
            rotate([0, 0, i * 360/flute_count])
                translate([bit_diameter/4, 0, -1])
                    cube([bit_diameter, flute_depth, bit_length+2]);
        }}
    }}
}}

// Assembly
module drill_head_assembly() {{
    // Mount interface at bottom
    magnetic_mount();
    // Body
    translate([0, 0, 3])
        drill_body();
    // Bit
    translate([0, 0, 3 + body_length])
        drill_bit();
}}

drill_head_assembly();
"""


def generate_scoop_head() -> str:
    """Generate OpenSCAD for the regolith scoop."""
    return f"""// AstraAnt Tool: Regolith Scoop
// Print in PETG. No electronics — fully passive.
// Mandibles grip the handle, scoop digs into regolith.
//
// Print orientation: scoop-side up
// Supports: none needed

$fn = 48;

{_magnetic_mount_scad()}

// Parameters
scoop_width = 25;
scoop_depth = 15;
scoop_length = 35;
wall_thickness = 1.5;
lip_height = 3;       // Rear lip prevents material sliding out

module scoop() {{
    difference() {{
        // Outer shell
        hull() {{
            translate([0, 0, 0])
                cube([scoop_width, scoop_length, 0.1], center=true);
            translate([0, -scoop_length/4, scoop_depth])
                scale([1, 0.6, 1])
                    cylinder(d=scoop_width, h=0.1, center=true);
        }}
        // Inner cavity
        translate([0, 0, wall_thickness])
            hull() {{
                translate([0, 0, 0])
                    cube([scoop_width - 2*wall_thickness,
                          scoop_length - 2*wall_thickness, 0.1], center=true);
                translate([0, -scoop_length/4, scoop_depth - wall_thickness])
                    scale([1, 0.6, 1])
                        cylinder(d=scoop_width - 2*wall_thickness, h=0.1, center=true);
            }}
    }}
    // Rear lip
    translate([0, scoop_length/2 - wall_thickness, scoop_depth/2])
        cube([scoop_width, wall_thickness, lip_height], center=true);
}}

module scoop_head_assembly() {{
    // Mount
    magnetic_mount();
    // Handle connecting mount to scoop
    translate([0, 0, 3])
        cube([8, 10, 8], center=true);
    // Scoop
    translate([0, 10, 7])
        rotate([30, 0, 0])
            scoop();
}}

scoop_head_assembly();
"""


def generate_paste_nozzle() -> str:
    """Generate OpenSCAD for the paste applicator nozzle."""
    return f"""// AstraAnt Tool: Paste Applicator Nozzle
// Print body in PETG. Silicone tube reservoir purchased separately.
// Mandible squeeze pushes paste through slit nozzle.
// Trowel blade on bottom smooths the applied layer.
//
// Print orientation: mount face down
// Supports: needed for nozzle overhang

$fn = 48;

{_magnetic_mount_scad()}

// Parameters
reservoir_od = 20;      // Silicone tube outer diameter
reservoir_length = 35;
nozzle_width = 20;
nozzle_slit = 2;        // Slit height controls paste thickness
trowel_width = 25;
trowel_angle = 45;

module reservoir_cradle() {{
    // Holds the silicone tube reservoir
    difference() {{
        cube([reservoir_od + 4, reservoir_length, reservoir_od + 4], center=true);
        // Tube channel
        rotate([90, 0, 0])
            cylinder(d=reservoir_od + 0.5, h=reservoir_length + 1, center=true);
        // Squeeze access (open sides for mandible grip)
        for (side = [-1, 1]) {{
            translate([side * (reservoir_od/2 + 2), 0, 0])
                cube([4, reservoir_length + 1, reservoir_od - 4], center=true);
        }}
    }}
}}

module nozzle() {{
    // Flat slit nozzle
    difference() {{
        cube([nozzle_width, 8, 6], center=true);
        // Slit opening
        cube([nozzle_width - 4, 4, nozzle_slit], center=true);
    }}
}}

module trowel() {{
    // Flat blade for smoothing
    translate([0, 0, -3])
        rotate([trowel_angle, 0, 0])
            cube([trowel_width, 0.8, 12], center=true);
}}

module paste_nozzle_assembly() {{
    magnetic_mount();
    translate([0, 0, 3 + reservoir_od/2 + 2])
        reservoir_cradle();
    translate([0, reservoir_length/2 + 4, 3])
        nozzle();
    translate([0, reservoir_length/2 + 8, 0])
        trowel();
}}

paste_nozzle_assembly();
"""


def generate_thermal_rake() -> str:
    """Generate OpenSCAD for the thermal sorting rake."""
    return f"""// AstraAnt Tool: Thermal Sorting Rake
// Print handle in PETG. Ceramic tine inserts press-fit into holes.
// (Buy 3mm alumina rods from McMaster-Carr or Amazon)
//
// Print orientation: flat (handle horizontal)
// Supports: none needed

$fn = 32;

{_magnetic_mount_scad()}

// Parameters
handle_length = 25;
handle_diameter = 10;
tine_count = 5;
tine_length = 15;
tine_diameter = 3;      // Matches standard alumina rod
tine_spacing = 6;
rake_width = (tine_count - 1) * tine_spacing;

module handle() {{
    rotate([0, 90, 0])
        cylinder(d=handle_diameter, h=handle_length);
}}

module rake_head() {{
    // Cross-bar connecting tines
    cube([rake_width + tine_spacing, handle_diameter, 4], center=true);
    // Tine sockets
    for (i = [0:tine_count-1]) {{
        translate([(i - (tine_count-1)/2) * tine_spacing, 0, -2]) {{
            difference() {{
                cylinder(d=tine_diameter + 2, h=5, $fn=16);
                // Hole for ceramic rod press-fit
                translate([0, 0, -0.1])
                    cylinder(d=tine_diameter + 0.1, h=5.2, $fn=16);
            }}
        }}
    }}
}}

module pusher_face() {{
    // Flat back of rake doubles as pusher
    translate([0, handle_diameter/2, 0])
        cube([rake_width + tine_spacing, 2, 15], center=true);
}}

module thermal_rake_assembly() {{
    magnetic_mount();
    translate([0, 0, 3])
        handle();
    translate([handle_length/2, 0, 3 + handle_length])
        rake_head();
    translate([handle_length/2, 0, 3 + handle_length])
        pusher_face();
}}

thermal_rake_assembly();
"""


def generate_cargo_gripper() -> str:
    """Generate OpenSCAD for the cargo gripper."""
    return f"""// AstraAnt Tool: Cargo Gripper
// Print in PETG. Glue silicone grip pads to jaw faces.
// Passive — mandibles provide all grip force.
//
// Print orientation: jaw-side up
// Supports: none needed

$fn = 32;

{_magnetic_mount_scad()}

// Parameters
jaw_width = 35;
jaw_opening = 40;
jaw_depth = 20;
wall = 3;
grip_pad_area = 10;  // Size of silicone pad bonding area

module gripper_jaw() {{
    // U-shaped fork
    difference() {{
        cube([jaw_width, jaw_depth, jaw_opening/2 + wall], center=true);
        // Inner cavity
        translate([0, 0, wall])
            cube([jaw_width - 2*wall, jaw_depth - 2*wall, jaw_opening/2 + 1], center=true);
    }}
    // Grip pad recesses (for silicone pads)
    for (side = [-1, 1]) {{
        translate([side * (jaw_width/2 - wall/2), 0, jaw_opening/4]) {{
            difference() {{
                cube([wall + 0.1, grip_pad_area, grip_pad_area], center=true);
                // Shallow recess for pad
                translate([side * 0.5, 0, 0])
                    cube([1.2, grip_pad_area - 1, grip_pad_area - 1], center=true);
            }}
        }}
    }}
}}

module cargo_gripper_assembly() {{
    magnetic_mount();
    translate([0, jaw_depth/2 + 5, 3])
        gripper_jaw();
}}

cargo_gripper_assembly();
"""


def generate_sampling_probe() -> str:
    """Generate OpenSCAD for the bioreactor sampling probe."""
    return f"""// AstraAnt Tool: Bioreactor Sampling Probe
// Print body in PETG. pH electrode and turbidity sensor purchased separately.
// Syringe barrel is a standard 5ml lab syringe body.
//
// Print orientation: mount face down
// Supports: needed for probe tip

$fn = 48;

{_magnetic_mount_scad()}

// Parameters
body_diameter = 10;
body_length = 50;
probe_tip_length = 15;
syringe_diameter = 12;    // 5ml syringe barrel OD
sensor_pocket_d = 6;      // pH electrode diameter

module probe_body() {{
    difference() {{
        union() {{
            // Main body
            cylinder(d=body_diameter, h=body_length);
            // Syringe holder (side mount)
            translate([body_diameter/2 + 2, 0, body_length/2])
                cylinder(d=syringe_diameter + 3, h=body_length * 0.6, center=true);
        }}
        // pH electrode pocket
        translate([0, 0, -0.1])
            cylinder(d=sensor_pocket_d + 0.3, h=body_length * 0.7);
        // Turbidity sensor window
        translate([body_diameter/2 - 1, 0, body_length * 0.3])
            cube([3, 4, 4], center=true);
        // Syringe barrel hole
        translate([body_diameter/2 + 2, 0, body_length * 0.2])
            cylinder(d=syringe_diameter + 0.3, h=body_length * 0.6);
        // Wire channel (runs up the back)
        translate([-body_diameter/2 + 1, 0, 0])
            cylinder(d=2.5, h=body_length + 1);
    }}
}}

module sampling_probe_assembly() {{
    magnetic_mount();
    translate([0, 0, 3])
        probe_body();
}}

sampling_probe_assembly();
"""


def generate_worker_chassis() -> str:
    """Generate OpenSCAD for the worker ant chassis (6 legs + 2 mandibles)."""
    return f"""// AstraAnt Worker Chassis -- 6 Legs + 2 Mandible Arms
// 3D printable body frame for the universal worker ant.
// Designed for SG90 servos (legs) and SG51R micro servos (mandibles).
//
// After printing:
//   1. Press-fit SG90 servos into leg sockets
//   2. Press-fit SG51R servos into mandible sockets
//   3. Route wires through internal channels
//   4. Mount RP2040 Pico on the electronics bay
//   5. Clip magnetic tool mount between mandible tips
//
// Print material: PETG recommended (heat/impact resistant)
// Print time: ~3-4 hours
// Supports: needed for leg sockets

$fn = 48;

// === PARAMETERS (edit to customize) ===

// Body dimensions (mm)
thorax_length = 55;
thorax_width = 35;
thorax_height = 20;
abdomen_length = 45;
abdomen_width = 30;
abdomen_height = 18;
head_diameter = 18;

// Servo dimensions (SG90)
sg90_length = 22.5;
sg90_width = 12.2;
sg90_height = 22.7;
sg90_shaft_offset = 5.5;  // Shaft center from edge

// Micro servo dimensions (SG51R for mandibles)
sg51_length = 16;
sg51_width = 8;
sg51_height = 12;

// Leg geometry
leg_socket_spacing = 18;   // Distance between leg pairs along body
leg_socket_angle = 30;     // Angle of servo mount from horizontal
n_leg_pairs = 3;

// Mandible geometry
mandible_length = 35;
mandible_spacing = 20;     // Distance between mandible tips

// Electronics bay
pico_length = 51;
pico_width = 21;
pico_clearance = 3;

// Tool mount
magnet_diameter = 4;
magnet_depth = 2;

// Wall thickness
wall = 2.0;

// === MODULES ===

module rounded_box(size, r=3) {{
    hull() {{
        for (x = [-1, 1], y = [-1, 1], z = [-1, 1]) {{
            translate([x*(size[0]/2-r), y*(size[1]/2-r), z*(size[2]/2-r)])
                sphere(r=r);
        }}
    }}
}}

module servo_pocket_sg90() {{
    // Pocket for SG90 servo (slightly oversized for press-fit)
    cube([sg90_length + 0.4, sg90_width + 0.4, sg90_height + 0.4], center=true);
    // Shaft hole
    translate([sg90_shaft_offset, 0, sg90_height/2])
        cylinder(d=5, h=5, center=true);
    // Wire exit slot
    translate([-sg90_length/2, 0, -sg90_height/2])
        cube([5, 4, 5], center=true);
}}

module servo_pocket_sg51() {{
    cube([sg51_length + 0.3, sg51_width + 0.3, sg51_height + 0.3], center=true);
    translate([sg51_length/4, 0, sg51_height/2])
        cylinder(d=4, h=4, center=true);
}}

module thorax() {{
    difference() {{
        // Outer shell
        rounded_box([thorax_length, thorax_width, thorax_height], r=4);
        // Hollow interior (electronics bay)
        translate([0, 0, wall])
            rounded_box([thorax_length - 2*wall, thorax_width - 2*wall,
                         thorax_height - wall], r=3);
        // Leg servo pockets (6 total: 3 pairs)
        for (pair = [0 : n_leg_pairs-1]) {{
            x_pos = (pair - 1) * leg_socket_spacing;
            for (side = [-1, 1]) {{
                translate([x_pos, side * thorax_width/2, -2])
                    rotate([side * leg_socket_angle, 0, 0])
                        servo_pocket_sg90();
            }}
        }}
    }}
    // Servo mount reinforcement ribs
    for (pair = [0 : n_leg_pairs-1]) {{
        x_pos = (pair - 1) * leg_socket_spacing;
        for (side = [-1, 1]) {{
            translate([x_pos, side * (thorax_width/2 - wall), 0])
                cube([sg90_length + 2, wall, thorax_height - 2], center=true);
        }}
    }}
}}

module abdomen() {{
    difference() {{
        rounded_box([abdomen_length, abdomen_width, abdomen_height], r=5);
        // Hollow for battery
        translate([0, 0, wall])
            rounded_box([abdomen_length - 2*wall, abdomen_width - 2*wall,
                         abdomen_height - wall], r=4);
        // Hopper mount holes (top)
        for (x = [-10, 10]) {{
            translate([x, 0, abdomen_height/2])
                cylinder(d=3.2, h=5, center=true, $fn=16);
        }}
    }}
}}

module head() {{
    difference() {{
        sphere(d=head_diameter);
        // Mandible servo pockets (2)
        for (side = [-1, 1]) {{
            translate([head_diameter/4, side * mandible_spacing/3, -2])
                rotate([0, 90, side * 10])
                    servo_pocket_sg51();
        }}
        // VL53L0x sensor window (front)
        translate([head_diameter/2 - 1, 0, 2])
            cube([3, 6, 6], center=true);
        // Wire channel to thorax
        translate([-head_diameter/2, 0, 0])
            cylinder(d=8, h=head_diameter, center=true);
    }}
}}

module mandible_arm(side=1) {{
    // Mandible arm extends forward from head
    // Tip has magnet pocket for tool mount
    hull() {{
        sphere(d=5);
        translate([mandible_length, side * 3, 0])
            sphere(d=4);
    }}
    // Magnet pocket at tip
    translate([mandible_length, side * 3, 0])
        difference() {{
            sphere(d=7);
            translate([0, 0, 2])
                cylinder(d=magnet_diameter + 0.2, h=magnet_depth + 0.2, center=true, $fn=24);
        }}
}}

module electronics_bay_mounts() {{
    // RP2040 Pico mounting posts (4 corners)
    for (x = [-pico_length/2 + 2, pico_length/2 - 2]) {{
        for (y = [-pico_width/2 + 1, pico_width/2 - 1]) {{
            translate([x, y, -thorax_height/2 + wall + 2])
                cylinder(d=4, h=3, $fn=16);
        }}
    }}
}}

module wire_channels() {{
    // Internal channels for routing servo wires
    for (pair = [0 : n_leg_pairs-1]) {{
        x_pos = (pair - 1) * leg_socket_spacing;
        for (side = [-1, 1]) {{
            hull() {{
                translate([x_pos, side * thorax_width/3, 0])
                    sphere(d=4);
                translate([x_pos, 0, thorax_height/4])
                    sphere(d=4);
            }}
        }}
    }}
    // Main wire trunk (front to back)
    hull() {{
        translate([-thorax_length/3, 0, thorax_height/4]) sphere(d=5);
        translate([thorax_length/3, 0, thorax_height/4]) sphere(d=5);
    }}
}}

// === ASSEMBLY ===

module worker_chassis() {{
    // Thorax (main body with leg servos and electronics)
    color("orange", 0.8) thorax();
    // Electronics mounting posts
    color("gray") electronics_bay_mounts();
    // Abdomen (battery + hopper mount)
    color("orange", 0.7)
        translate([-thorax_length/2 - abdomen_length/2 + 8, 0, -2])
            abdomen();
    // Head (mandible servos + sensors)
    color("orange", 0.9)
        translate([thorax_length/2 + head_diameter/3, 0, 2])
            head();
    // Mandible arms
    color("darkgray")
        translate([thorax_length/2 + head_diameter/2 + 3, 0, 0]) {{
            mandible_arm(side=1);
            mandible_arm(side=-1);
        }}
}}

worker_chassis();

// To export for printing:
// 1. Comment out colors (or OpenSCAD ignores them for STL)
// 2. File -> Export -> STL
// 3. Slice in your slicer (PrusaSlicer, Cura, etc.)
// 4. Print in PETG at 0.2mm layer height, 20% infill
// 5. Print supports for leg servo pockets (overhang)
"""


def generate_pod_scaffold() -> str:
    """Generate OpenSCAD for the ferrocement cargo pod scaffold."""
    return f"""// AstraAnt Cargo Pod Scaffold (Ferrocement)
// Print this lattice, then fill cells with bioreactor waste paste.
// After paste sets (~4 hours), you have a durable pod shell.
//
// Print material: PETG
// Print time: ~30 minutes
// Fill material: bioreactor waste slurry mixed with water

$fn = 32;

// Parameters
pod_length = 120;
pod_width = 80;
pod_height = 60;
wall = 2;
cell_size = 8;        // Lattice cell size
strut_width = 1.5;    // Lattice strut thickness

module lattice_box(size, cell, strut) {{
    // Open lattice box -- print this, fill with paste
    difference() {{
        cube(size, center=true);
        // Hollow interior
        cube([size[0]-2*wall, size[1]-2*wall, size[2]-2*wall], center=true);
    }}
    // Internal lattice struts (X direction)
    for (y = [-size[1]/2 + cell : cell : size[1]/2 - cell]) {{
        for (z = [-size[2]/2 + cell : cell : size[2]/2 - cell]) {{
            translate([0, y, z])
                cube([size[0] - 2*wall, strut, strut], center=true);
        }}
    }}
    // Internal lattice struts (Y direction)
    for (x = [-size[0]/2 + cell : cell : size[0]/2 - cell]) {{
        for (z = [-size[2]/2 + cell : cell : size[2]/2 - cell]) {{
            translate([x, 0, z])
                cube([strut, size[1] - 2*wall, strut], center=true);
        }}
    }}
}}

module sail_mount() {{
    // Attachment point for solar sail deployment booms
    translate([0, 0, pod_height/2]) {{
        cylinder(d=10, h=5);
        // Boom socket holes (4 directions)
        for (a = [0, 90, 180, 270]) {{
            rotate([0, 0, a])
                translate([8, 0, 2.5])
                    rotate([0, 90, 0])
                        cylinder(d=3.2, h=5, center=true, $fn=16);
        }}
    }}
}}

module guidance_mount() {{
    // Mount point for the guidance unit (stripped surface ant brain)
    translate([pod_length/2 - 15, 0, pod_height/2]) {{
        difference() {{
            cube([30, 25, 3], center=true);
            // Screw holes
            for (x = [-10, 10], y = [-8, 8]) {{
                translate([x, y, 0])
                    cylinder(d=2.5, h=5, center=true, $fn=16);
            }}
        }}
    }}
}}

module thruster_mount() {{
    // Mount for CO2 cold gas thruster (rear)
    translate([-pod_length/2, 0, 0]) {{
        difference() {{
            cylinder(d=35, h=15, center=true);
            cylinder(d=30.5, h=16, center=true);  // Tank OD + clearance
        }}
    }}
}}

module pod_scaffold() {{
    lattice_box([pod_length, pod_width, pod_height], cell_size, strut_width);
    sail_mount();
    guidance_mount();
    thruster_mount();
}}

pod_scaffold();
"""


# All generators
TOOL_GENERATORS = {
    "drill_head": generate_drill_head,
    "scoop_head": generate_scoop_head,
    "paste_nozzle": generate_paste_nozzle,
    "thermal_rake": generate_thermal_rake,
    "cargo_gripper": generate_cargo_gripper,
    "sampling_probe": generate_sampling_probe,
    "worker_chassis": generate_worker_chassis,
    "pod_scaffold": generate_pod_scaffold,
}


def generate_tool_scad(tool_id: str) -> str:
    """Generate OpenSCAD code for a specific tool head."""
    gen = TOOL_GENERATORS.get(tool_id)
    if gen is None:
        return f"// No OpenSCAD model for tool: {tool_id}"
    return gen()


def generate_all_tools(output_dir: Path | None = None) -> list[Path]:
    """Generate all tool head .scad files. Returns list of created files."""
    out = output_dir or SCAD_DIR
    out.mkdir(parents=True, exist_ok=True)
    created = []
    for tool_id, gen in TOOL_GENERATORS.items():
        filepath = out / f"{tool_id}.scad"
        filepath.write_text(gen())
        created.append(filepath)
    return created
