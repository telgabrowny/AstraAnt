// AstraAnt WAAM Printer Bot -- Asteroid-Built Construction Ant
//
// An 8-legged mobile WAAM (Wire Arc Additive Manufacturing) printer
// that crawls on the iron shell of the nautilus station and 3D prints
// metal structures from electroformed iron wire.
//
// Chassis and legs are WAAM-printed from asteroid iron by the mothership
// arms. Only the servos, magnets, ESP32, and wire feed rollers come
// from Earth (~$9 of Earth parts per bot, 411g total).
//
// After assembly:
//   1. WAAM-printed iron chassis (from mothership arms)
//   2. Press-fit 8x SG90 servos into leg sockets
//   3. Press-fit 8x NdFeB magnets into foot pads (iron shell grip)
//   4. Mount ESP32-S3 in electronics bay
//   5. Install WAAM print head (wire feed motor + 2 rollers + arc tip)
//   6. Clip wire bobbin onto rear mount
//   7. Connect power tether (5m copper, from asteroid copper)
//
// Material: WAAM iron (in space), or PETG for Earth prototype
// This file prints a 1:1 Earth-testable prototype.
// Functional: press-fit real SG90 servos and test the gait.

$fn = 48;

// =========================================================================
// PARAMETERS -- all dimensions in mm, matching real purchasable parts
// =========================================================================

// --- SG90 Micro Servo (the off-the-shelf part) ---
// Datasheet: 22.5 x 12.2 x 22.7mm, 9g, $0.30
sg90_l = 22.5;    // length (along output shaft axis)
sg90_w = 12.2;    // width
sg90_h = 22.7;    // height (including mounting tabs)
sg90_tab_h = 16;  // height to bottom of mounting tabs
sg90_tab_t = 2.5; // tab thickness
sg90_tab_w = 32.5; // tab tip-to-tip width
sg90_shaft_d = 4.8; // output shaft diameter
sg90_shaft_h = 3.5; // shaft protrusion above body
sg90_clearance = 0.3; // press-fit clearance

// --- ESP32-S3 DevKitC-1 (the off-the-shelf brain) ---
// $5, 25.5 x 18mm board, can also use RP2040 Pico (51 x 21mm)
esp32_l = 25.5;
esp32_w = 18;
esp32_h = 3;      // board + components height

// --- NdFeB Disc Magnet (8x, for foot grip on iron shell) ---
// N52, 6mm dia x 2mm thick, ~$0.20 each
mag_d = 6;
mag_h = 2;

// --- Wire Feed Rollers (2x, from Earth parts tray) ---
// 8mm dia x 5mm wide, with 1.5mm wire groove
roller_d = 8;
roller_w = 5;
roller_bore = 3;   // M3 shaft

// --- Wire Bobbin (rear-mounted, carries 5m of 1.5mm iron wire) ---
bobbin_outer_d = 30;
bobbin_inner_d = 10;
bobbin_width = 15;

// --- Arc Tip (tungsten electrode, from Earth parts tray) ---
arc_tip_d = 3;
arc_tip_l = 15;

// --- Body Dimensions ---
thorax_l = 45;     // main body length (shorter than worker -- no hopper)
thorax_w = 30;     // width
thorax_h = 16;     // height
head_d = 14;       // head dome diameter

// --- Leg Geometry ---
n_leg_pairs = 4;   // 8 legs total
leg_socket_spacing = 9;  // mm between leg pair centers
leg_upper_l = 18;  // coxa length (horizontal)
leg_lower_l = 22;  // femur length (angled down to ground)
leg_dia = 3;       // leg rod diameter (iron wire, WAAM-built)
foot_pad_d = 8;    // foot pad disc diameter (same as worker)

// --- Print Head Mount ---
head_mount_l = 20;  // extends forward from head

// --- Power Tether ---
tether_d = 3;      // 5m copper cable, 3mm OD with silicone jacket

// --- Wall Thickness ---
wall = 2.0;

// =========================================================================
// MODULES
// =========================================================================

module rounded_box(size, r=2) {
    hull() {
        for (x = [-1, 1], y = [-1, 1], z = [-1, 1])
            translate([x*(size[0]/2-r), y*(size[1]/2-r), z*(size[2]/2-r)])
                sphere(r=r);
    }
}

// --- SG90 Servo (visual + pocket) ---
module sg90_visual() {
    // The actual servo body (blue, recognizable SG90 shape)
    color([0.2, 0.4, 0.8]) {
        // Main body
        cube([sg90_l, sg90_w, sg90_tab_h], center=true);
        // Mounting tabs
        translate([0, 0, sg90_tab_h/2 - sg90_tab_t/2])
            cube([sg90_tab_w, sg90_w, sg90_tab_t], center=true);
        // Top cap
        translate([0, 0, sg90_tab_h/2])
            cube([sg90_l, sg90_w, sg90_h - sg90_tab_h], center=true);
    }
    // Output shaft (white gear)
    color([0.9, 0.9, 0.9])
    translate([sg90_l/2 - 5.5, 0, sg90_h/2])
        cylinder(d=sg90_shaft_d, h=sg90_shaft_h, $fn=24);
}

module servo_pocket() {
    // Slightly oversized cavity for press-fit
    c = sg90_clearance;
    cube([sg90_l + c, sg90_w + c, sg90_tab_h + c + 2], center=true);
    // Tab slot
    translate([0, 0, sg90_tab_h/2 - sg90_tab_t/2])
        cube([sg90_tab_w + c, sg90_w + c, sg90_tab_t + c], center=true);
    // Wire exit hole
    translate([0, 0, -(sg90_tab_h/2 + 1)])
        cylinder(d=4, h=5, center=true, $fn=16);
}

// --- Foot Pad with Magnet ---
module mag_foot_pad() {
    // Disc pad (WAAM iron or PETG print)
    color([0.5, 0.5, 0.55])
    cylinder(d=foot_pad_d, h=3, $fn=32);

    // NdFeB magnet (silver disc, recessed)
    color([0.75, 0.75, 0.78])
    translate([0, 0, -0.5])
        cylinder(d=mag_d, h=mag_h, $fn=32);

    // Magnet pocket indicator (ring)
    color([0.4, 0.4, 0.42])
    difference() {
        cylinder(d=mag_d + 1, h=1, $fn=32);
        cylinder(d=mag_d - 0.5, h=2, center=true, $fn=32);
    }
}

// --- Wire Feed Print Head ---
module waam_print_head() {
    // Housing (WAAM iron box)
    color([0.55, 0.55, 0.6])
    rounded_box([head_mount_l, 14, 12], r=1.5);

    // Two feed rollers (visible through side window)
    for (side = [-1, 1]) {
        color([0.7, 0.7, 0.72])
        translate([2, side * 3, 0])
        rotate([0, 90, 0])
            difference() {
                cylinder(d=roller_d, h=roller_w, center=true, $fn=24);
                cylinder(d=roller_bore, h=roller_w + 1, center=true, $fn=16);
            }
    }

    // Wire guide tube
    color([0.6, 0.55, 0.5])
    translate([head_mount_l/2 + 3, 0, 0])
    rotate([0, 90, 0])
        cylinder(d=3, h=8, center=true, $fn=16);

    // Arc tip (tungsten rod, copper colored)
    color([0.8, 0.5, 0.3])
    translate([head_mount_l/2 + 8, 0, 0])
    rotate([0, 90, 0])
        cylinder(d=arc_tip_d, h=arc_tip_l, $fn=16);

    // Feed motor (small DC motor on top)
    color([0.4, 0.4, 0.45])
    translate([0, 0, 8])
        cylinder(d=10, h=12, center=true, $fn=24);

    // Motor shaft
    color([0.7, 0.7, 0.7])
    translate([0, 0, 14])
        cylinder(d=2, h=3, $fn=12);
}

// --- Wire Bobbin (rear spool) ---
module wire_bobbin() {
    color([0.65, 0.67, 0.72]) {
        // Flanges
        for (z = [-1, 1])
            translate([0, 0, z * bobbin_width/2])
                cylinder(d=bobbin_outer_d, h=1.5, center=true, $fn=32);
        // Core
        cylinder(d=bobbin_inner_d, h=bobbin_width, center=true, $fn=24);
    }
    // Wire wound on bobbin (thicker cylinder between flanges)
    color([0.72, 0.72, 0.75])
    cylinder(d=bobbin_outer_d - 4, h=bobbin_width - 3, center=true, $fn=32);
}

// --- ESP32 Board ---
module esp32_board() {
    // PCB (green)
    color([0.1, 0.5, 0.15])
    cube([esp32_l, esp32_w, 1.6], center=true);

    // ESP32 module (silver RF shield)
    color([0.75, 0.75, 0.78])
    translate([3, 0, 1.5])
        cube([18, 13, 2.5], center=true);

    // USB connector
    color([0.7, 0.7, 0.7])
    translate([-esp32_l/2, 0, 1])
        cube([7, 9, 3.5], center=true);

    // Antenna area (gold trace)
    color([0.85, 0.75, 0.3])
    translate([esp32_l/2 - 3, 0, 0.9])
        cube([5, esp32_w - 2, 0.2], center=true);
}


// =========================================================================
// MAIN ASSEMBLY
// =========================================================================

module printer_bot_chassis() {
    // --- Thorax (main body, WAAM-printed iron) ---
    color([0.5, 0.5, 0.55])
    difference() {
        rounded_box([thorax_l, thorax_w, thorax_h]);

        // 8 servo pockets (4 pairs along body)
        for (pair = [0 : n_leg_pairs - 1]) {
            x_pos = -thorax_l/2 + 8 + pair * leg_socket_spacing;
            for (side = [-1, 1]) {
                translate([x_pos, side * (thorax_w/2 - 2), -2])
                rotate([side * 30, 0, 0])
                    servo_pocket();
            }
        }

        // ESP32 bay (top cavity)
        translate([5, 0, thorax_h/2 - 2])
            cube([esp32_l + 2, esp32_w + 2, esp32_h + 2], center=true);

        // Wire channel from rear to front (for power tether routing)
        translate([0, 0, -2])
        rotate([0, 90, 0])
            cylinder(d=tether_d + 1, h=thorax_l + 10, center=true, $fn=16);

        // Bobbin mount slot (rear)
        translate([-thorax_l/2 - 2, 0, 2])
            cube([6, bobbin_width + 2, 12], center=true);
    }

    // --- Head dome ---
    color([0.5, 0.5, 0.55])
    translate([thorax_l/2 + head_d/2 - 3, 0, 2])
        sphere(d=head_d);
}

module printer_bot_assembled() {
    // Chassis
    printer_bot_chassis();

    // --- 8 SG90 servos (press-fit into pockets) ---
    for (pair = [0 : n_leg_pairs - 1]) {
        x_pos = -thorax_l/2 + 8 + pair * leg_socket_spacing;
        for (side = [-1, 1]) {
            translate([x_pos, side * (thorax_w/2 - 2), -2])
            rotate([side * 30, 0, 0])
                sg90_visual();
        }
    }

    // --- 8 Legs (iron rods, WAAM-built) ---
    for (pair = [0 : n_leg_pairs - 1]) {
        x_pos = -thorax_l/2 + 8 + pair * leg_socket_spacing;
        for (side = [-1, 1]) {
            // Upper leg (coxa, horizontal)
            color([0.55, 0.55, 0.6])
            translate([x_pos, side * (thorax_w/2 + leg_upper_l/2), -2])
                rotate([0, 90, 0])
                    cylinder(d=leg_dia, h=leg_upper_l, center=true, $fn=12);

            // Lower leg (femur, angled down)
            color([0.55, 0.55, 0.6])
            translate([x_pos, side * (thorax_w/2 + leg_upper_l), -2])
            rotate([side * -55, 0, 0])
            translate([0, 0, -leg_lower_l/2])
                cylinder(d=leg_dia, h=leg_lower_l, center=true, $fn=12);

            // Foot pad with magnet
            translate([x_pos, side * (thorax_w/2 + leg_upper_l + 8),
                       -leg_lower_l + 2])
                mag_foot_pad();
        }
    }

    // --- ESP32 board (in top bay) ---
    translate([5, 0, thorax_h/2 - 1])
        esp32_board();

    // --- WAAM Print Head (front-mounted) ---
    translate([thorax_l/2 + head_mount_l/2 + head_d/2 - 2, 0, 2])
        waam_print_head();

    // --- Wire Bobbin (rear-mounted) ---
    translate([-thorax_l/2 - bobbin_outer_d/2 - 2, 0, 4])
    rotate([90, 0, 0])
        wire_bobbin();

    // --- Power Tether Port (rear) ---
    color([0.6, 0.4, 0.2])
    translate([-thorax_l/2 - 1, 0, -2])
    rotate([0, -90, 0])
        cylinder(d=tether_d + 2, h=5, $fn=16);

    // Tether cable stub
    color([0.7, 0.45, 0.2])
    translate([-thorax_l/2 - 5, 0, -2])
    rotate([0, -90, 0])
        cylinder(d=tether_d, h=15, $fn=12);
}

// =========================================================================
// RENDER
// =========================================================================

printer_bot_assembled();

// =========================================================================
// BILL OF MATERIALS (matches seed_bom.py)
// =========================================================================
//
// EARTH-ORIGIN PARTS ($9 total):
//   8x SG90 micro servo ............ $2.40 (72g)
//   1x ESP32-S3 DevKitC ............ $5.00 (3g)
//   8x NdFeB disc 6x2mm ............ $1.60 (16g)
//   2x Wire feed roller bearings .... $0.10 (2g)
//                             TOTAL:  $9.10 (93g)
//
// ASTEROID-ORIGIN PARTS (WAAM-printed + extracted):
//   Chassis (iron) .................. 80g
//   8x leg segments (iron rod) ...... 40g
//   WAAM print head housing (iron) .. 60g
//   Wire bobbin (iron) .............. 30g
//   Foot pads (iron) ................ 16g
//   Wiring harness (copper) ......... 20g
//   Power tether 5m (copper) ........ 50g
//   Wire coil 5m (iron) ............. 22g
//                             TOTAL:  318g
//
// GRAND TOTAL: 411g, $9.10 of Earth parts
//
// PRINT NOTES:
//   For Earth prototype: print chassis in PETG
//   Press-fit real SG90 servos (test the gait!)
//   Use M2 screws where shown
//   Foot pads: glue 6mm magnets in recesses
//   Legs: 3mm steel rod or 3D printed
