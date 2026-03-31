// AstraAnt Seed Capture Scene -- Mothership + Rock + Membrane
//
// Display model showing the moment of capture: the seed mothership
// has wrapped a 2m C-type asteroid fragment in its Kapton membrane
// and is beginning bioleaching.
//
// The model shows:
//   - 2m asteroid rock (bumpy sphere)
//   - Kapton+Kevlar membrane wrapped around it (thin shell)
//   - Seed mothership docked on top ("the plug")
//   - Solar concentrator mirror aimed at the bag
//   - Arms gripping the membrane seal
//
// Scale: 1:20 (fits on a standard printer bed)
// At 1:20: rock = 100mm diameter, mothership = 25mm body
//
// Print as a display piece. Clear/transparent filament for the
// membrane shell looks amazing if your printer supports it.
// Or print the membrane separately in clear PETG.

$fn = 48;

scale_factor = 1/20;

// === ASTEROID ROCK ===
module asteroid_rock(diameter=2.0) {
    r = diameter / 2;
    color([0.55, 0.43, 0.3])
    union() {
        // Main body
        sphere(d=diameter);

        // Surface boulders / bumps (procedural roughness)
        for (i = [0 : 11]) {
            a1 = i * 137.5;  // golden angle
            a2 = i * 63.4;
            dx = r * 0.85 * cos(a1) * cos(a2);
            dy = r * 0.85 * sin(a2);
            dz = r * 0.85 * sin(a1) * cos(a2);
            translate([dx, dy, dz])
                sphere(d = diameter * 0.15 + (i % 3) * diameter * 0.05);
        }
    }
}

// === KAPTON MEMBRANE (thin shell around rock) ===
module membrane_shell(inner_d=2.0, thickness=0.015) {
    // Thin spherical shell -- the bag
    // Print in clear PETG for best effect, or gold PLA
    color([0.85, 0.75, 0.25, 0.5])
    difference() {
        sphere(d=inner_d + thickness * 2 + 0.3); // Slight clearance
        sphere(d=inner_d + 0.3 - 0.001);
    }

    // Seam line (equatorial weld where membrane was sealed)
    color([0.7, 0.6, 0.2])
    rotate([90, 0, 0])
        difference() {
            cylinder(d=inner_d + 0.32, h=0.02, center=true);
            cylinder(d=inner_d + 0.25, h=0.03, center=true);
        }
}

// === SEED MOTHERSHIP (simplified for this scale) ===
module seed_plug() {
    body_w = 0.50;
    body_h = 0.35;
    body_d = 0.30;

    // Main body
    color([0.4, 0.4, 0.45])
    cube([body_w, body_d, body_h], center=true);

    // Solar wings
    for (side = [-1, 1]) {
        color([0.15, 0.3, 0.75])
        translate([0, side * 0.65, 0])
            cube([0.6, 0.8, 0.015], center=true);
    }

    // Arms (gripping downward toward membrane)
    for (side = [-1, 1]) {
        color([0.6, 0.6, 0.65])
        translate([side * 0.15, 0, -body_h/2]) {
            rotate([0, side * 30, 0])
            translate([0, 0, -0.15])
                cube([0.025, 0.025, 0.30], center=true);

            // Gripper at membrane contact
            color([0.85, 0.7, 0.2])
            translate([side * 0.12, 0, -0.28])
                sphere(d=0.04);
        }
    }

    // Ion engine
    color([0.3, 0.7, 0.9])
    translate([0, 0, body_h/2 + 0.03])
        sphere(d=0.06);

    // Airlock port (bottom)
    color([0.55, 0.55, 0.6])
    translate([0.1, 0.08, -body_h/2])
        cylinder(d=0.05, h=0.025, center=true);

    // Antenna
    color([0.7, 0.7, 0.7])
    translate([-0.1, 0, body_h/2])
        cylinder(d=0.006, h=0.06);
}

// === SOLAR CONCENTRATOR ===
module concentrator(size=0.6) {
    color([0.75, 0.8, 0.9])
    cube([size, size, 0.01], center=true);

    // Support strut
    color([0.5, 0.5, 0.5])
    translate([0, 0, -0.3])
    rotate([20, 0, 0])
        cube([0.015, 0.015, 0.6], center=true);
}

// === PRINTER BOT (on shell surface) ===
module printer_bot(s=0.08) {
    // Ellipsoid body
    color([0.9, 0.65, 0.2])
    scale([1.5, 0.8, 1])
        sphere(d=s);

    // 8 legs
    for (i = [0 : 7]) {
        a = i * 45;
        lx = cos(a) * s * 0.9;
        ly = sin(a) * s * 0.9;
        color([0.7, 0.5, 0.15])
        translate([lx, -s * 0.3, ly])
        rotate([0, -a, 45])
            cube([0.008, 0.008, s * 0.6], center=true);
    }

    // WAAM nozzle (red tip, front)
    color([0.95, 0.3, 0.15])
    translate([s * 1.0, 0, 0])
        sphere(d=s * 0.3);
}

// === IRON SHELL LAYER (inside membrane, partial cutaway) ===
module iron_shell(diameter=2.0) {
    color([0.65, 0.67, 0.72])
    difference() {
        sphere(d=diameter + 0.25);
        sphere(d=diameter + 0.25 - 0.06);  // 0.5mm iron at 1:20 = 0.03mm... thicken for visibility
        // Cutaway: remove front quarter to show interior
        translate([0, -diameter, 0])
            cube([diameter * 2, diameter * 2, diameter * 2], center=true);
    }
}


// === FULL CAPTURE SCENE ===
module capture_scene() {
    rock_d = 2.0;

    // The asteroid rock
    asteroid_rock(rock_d);

    // Iron shell (partial cutaway to show rock inside)
    iron_shell(rock_d);

    // Membrane (outermost layer)
    membrane_shell(rock_d);

    // Seed mothership docked on top
    translate([0, 0, rock_d/2 + 0.35/2 + 0.05])
        seed_plug();

    // Solar concentrator (offset, aimed at bag)
    translate([2.0, 0, 0.5])
    rotate([0, -15, 30])
        concentrator();

    // A few printer bots on the iron shell surface
    translate([0, rock_d/2 + 0.16, 0.3])
    rotate([75, 0, 0])
        printer_bot();

    translate([rock_d/2 + 0.14, 0, -0.2])
    rotate([0, 0, -80])
        printer_bot();

    translate([-0.3, 0, rock_d/2 + 0.14])
    rotate([0, 80, 20])
        printer_bot();

    // WAAM trail deposits (small silver blobs where bots printed)
    for (i = [0 : 8]) {
        a1 = i * 40 + 10;
        a2 = i * 27;
        dx = (rock_d/2 + 0.14) * cos(a1) * cos(a2);
        dy = (rock_d/2 + 0.14) * sin(a2);
        dz = (rock_d/2 + 0.14) * sin(a1) * cos(a2);
        color([0.78, 0.78, 0.82])
        translate([dx, dy, dz])
            sphere(d=0.03);
    }
}


// === RENDER ===
scale(scale_factor * 1000)  // mm at chosen scale
    capture_scene();

// === PRINT NOTES ===
// At 1:20 scale:
//   Rock diameter: 100mm
//   Mothership body: 25 x 15 x 17mm
//   Solar wingspan: ~100mm
//   Total scene: fits in 150 x 120 x 120mm
//
// For multi-material printers:
//   Rock: brown PLA
//   Membrane: clear/gold PETG (print separately, assemble)
//   Mothership: gray PLA
//   Solar panels: blue PLA
//   Bots: orange PLA
//   Iron shell: silver PLA (the cutaway section)
//
// For single-material: print in gray, hand-paint details.
// The cutaway lets you see the rock inside the membrane.
