// AstraAnt Worker Chassis -- 8 Legs + 2 Mandible Arms
// 3D printable body frame for the universal worker ant.
// Designed for SG90 servos (legs) and SG51R micro servos (mandibles).
// 8-leg config verified by MuJoCo sim: 50% less grip needed vs 6-leg.
//
// After printing:
//   1. Press-fit SG90 servos into 8 leg sockets
//   2. Press-fit SG51R servos into mandible sockets
//   3. Route wires through internal channels
//   4. Mount RP2040 Pico on the electronics bay
//   5. Clip magnetic tool mount between mandible tips
//   6. Press-fit foot pads onto each leg tip
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

// Leg geometry (8 legs = 4 pairs)
leg_socket_spacing = 12;   // Distance between leg pairs along body (was 18 for 3 pairs)
leg_socket_angle = 30;     // Angle of servo mount from horizontal
n_leg_pairs = 4;           // 8 legs total (was 3 pairs / 6 legs)

// Abdomen grip socket (for ant-to-ant chaining)
grip_groove_width = 3;     // Mandible-width channels on rear of abdomen
grip_groove_depth = 1.5;   // Same profile as tool head mount grooves
grip_groove_spacing = 10;  // Distance between the two grooves

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

module rounded_box(size, r=3) {
    hull() {
        for (x = [-1, 1], y = [-1, 1], z = [-1, 1]) {
            translate([x*(size[0]/2-r), y*(size[1]/2-r), z*(size[2]/2-r)])
                sphere(r=r);
        }
    }
}

module servo_pocket_sg90() {
    // Pocket for SG90 servo (slightly oversized for press-fit)
    cube([sg90_length + 0.4, sg90_width + 0.4, sg90_height + 0.4], center=true);
    // Shaft hole
    translate([sg90_shaft_offset, 0, sg90_height/2])
        cylinder(d=5, h=5, center=true);
    // Wire exit slot
    translate([-sg90_length/2, 0, -sg90_height/2])
        cube([5, 4, 5], center=true);
}

module servo_pocket_sg51() {
    cube([sg51_length + 0.3, sg51_width + 0.3, sg51_height + 0.3], center=true);
    translate([sg51_length/4, 0, sg51_height/2])
        cylinder(d=4, h=4, center=true);
}

module thorax() {
    difference() {
        // Outer shell
        rounded_box([thorax_length, thorax_width, thorax_height], r=4);
        // Hollow interior (electronics bay)
        translate([0, 0, wall])
            rounded_box([thorax_length - 2*wall, thorax_width - 2*wall,
                         thorax_height - wall], r=3);
        // Leg servo pockets (6 total: 3 pairs)
        for (pair = [0 : n_leg_pairs-1]) {
            x_pos = (pair - 1) * leg_socket_spacing;
            for (side = [-1, 1]) {
                translate([x_pos, side * thorax_width/2, -2])
                    rotate([side * leg_socket_angle, 0, 0])
                        servo_pocket_sg90();
            }
        }
    }
    // Servo mount reinforcement ribs
    for (pair = [0 : n_leg_pairs-1]) {
        x_pos = (pair - 1) * leg_socket_spacing;
        for (side = [-1, 1]) {
            translate([x_pos, side * (thorax_width/2 - wall), 0])
                cube([sg90_length + 2, wall, thorax_height - 2], center=true);
        }
    }
}

module abdomen() {
    difference() {
        rounded_box([abdomen_length, abdomen_width, abdomen_height], r=5);
        // Hollow for battery
        translate([0, 0, wall])
            rounded_box([abdomen_length - 2*wall, abdomen_width - 2*wall,
                         abdomen_height - wall], r=4);
        // Hopper mount holes (top)
        for (x = [-10, 10]) {
            translate([x, 0, abdomen_height/2])
                cylinder(d=3.2, h=5, center=true, $fn=16);
        }
    }
}

module head() {
    difference() {
        sphere(d=head_diameter);
        // Mandible servo pockets (2)
        for (side = [-1, 1]) {
            translate([head_diameter/4, side * mandible_spacing/3, -2])
                rotate([0, 90, side * 10])
                    servo_pocket_sg51();
        }
        // VL53L0x sensor window (front)
        translate([head_diameter/2 - 1, 0, 2])
            cube([3, 6, 6], center=true);
        // Wire channel to thorax
        translate([-head_diameter/2, 0, 0])
            cylinder(d=8, h=head_diameter, center=true);
    }
}

module mandible_arm(side=1) {
    // Mandible arm extends forward from head
    // Tip has magnet pocket for tool mount
    hull() {
        sphere(d=5);
        translate([mandible_length, side * 3, 0])
            sphere(d=4);
    }
    // Magnet pocket at tip
    translate([mandible_length, side * 3, 0])
        difference() {
            sphere(d=7);
            translate([0, 0, 2])
                cylinder(d=magnet_diameter + 0.2, h=magnet_depth + 0.2, center=true, $fn=24);
        }
}

module electronics_bay_mounts() {
    // RP2040 Pico mounting posts (4 corners)
    for (x = [-pico_length/2 + 2, pico_length/2 - 2]) {
        for (y = [-pico_width/2 + 1, pico_width/2 - 1]) {
            translate([x, y, -thorax_height/2 + wall + 2])
                cylinder(d=4, h=3, $fn=16);
        }
    }
}

module wire_channels() {
    // Internal channels for routing servo wires
    for (pair = [0 : n_leg_pairs-1]) {
        x_pos = (pair - 1) * leg_socket_spacing;
        for (side = [-1, 1]) {
            hull() {
                translate([x_pos, side * thorax_width/3, 0])
                    sphere(d=4);
                translate([x_pos, 0, thorax_height/4])
                    sphere(d=4);
            }
        }
    }
    // Main wire trunk (front to back)
    hull() {
        translate([-thorax_length/3, 0, thorax_height/4]) sphere(d=5);
        translate([thorax_length/3, 0, thorax_height/4]) sphere(d=5);
    }
}

// === ASSEMBLY ===

module worker_chassis() {
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
        translate([thorax_length/2 + head_diameter/2 + 3, 0, 0]) {
            mandible_arm(side=1);
            mandible_arm(side=-1);
        }
}

worker_chassis();

// To export for printing:
// 1. Comment out colors (or OpenSCAD ignores them for STL)
// 2. File -> Export -> STL
// 3. Slice in your slicer (PrusaSlicer, Cura, etc.)
// 4. Print in PETG at 0.2mm layer height, 20% infill
// 5. Print supports for leg servo pockets (overhang)
