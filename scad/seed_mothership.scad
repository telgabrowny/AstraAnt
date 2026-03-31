// AstraAnt Seed Mothership -- "Garbage Bag to Space Station"
//
// The minimum viable asteroid mining seed: 41 kg, $654K.
// A carry-on suitcase that grows into a space station.
//
// Default scale: 1:10 (seed is small, so bigger scale)
// At 1:10: body = 50mm x 35mm x 30mm (actual suitcase dimensions)
//          solar wings = 200mm tip-to-tip
//
// This is a display model showing the seed mothership with:
//   - Main body (electronics, pump, electro-winning cell)
//   - Two deployable solar panel wings (4 m^2 total)
//   - Two robotic arms with WAAM print heads
//   - Ion thruster at rear
//   - Folded Kapton membrane bundle underneath
//   - Material airlock port
//
// Print in PLA/PETG. No supports needed if printed upright.

$fn = 48;

// === SCALE ===
scale_factor = 1/10;  // 1:10. Use 1/5 for a big desk model, 1/20 for keychain.

// === REAL DIMENSIONS (meters) ===
body_w = 0.50;   // width (along solar axis)
body_h = 0.35;   // height
body_d = 0.30;   // depth

solar_span = 2.0; // Each wing is 1.0m from body center
solar_w = 0.80;   // Wing width (perpendicular to span)
solar_t = 0.02;   // Wing thickness

arm_length = 0.30;
arm_dia = 0.03;
gripper_dia = 0.04;

ion_dia = 0.08;
ion_depth = 0.06;

membrane_bundle_w = 0.25;
membrane_bundle_h = 0.12;
membrane_bundle_d = 0.20;

airlock_dia = 0.06;

// === COLORS (for OpenSCAD preview) ===
// Main body: dark gray
// Solar panels: blue
// Arms: light gray with gold grippers
// Ion engine: cyan
// Membrane bundle: gold

module seed_mothership() {
    // Main body
    color([0.4, 0.4, 0.45])
    cube([body_w, body_d, body_h], center=true);

    // Raised electronics bay on top
    color([0.35, 0.35, 0.4])
    translate([0, 0, body_h/2])
        cube([body_w * 0.6, body_d * 0.6, 0.04], center=true);

    // Solar panel wings (deployed, one on each side along Y axis)
    for (side = [-1, 1]) {
        color([0.15, 0.3, 0.75])
        translate([0, side * (body_d/2 + solar_span/2), 0])
            cube([solar_w, solar_span - body_d, solar_t], center=true);

        // Panel hinge
        color([0.5, 0.5, 0.5])
        translate([0, side * body_d/2, 0])
            cube([0.04, 0.04, body_h * 0.8], center=true);
    }

    // Robotic arms (2x, one on each side along X axis)
    for (side = [-1, 1]) {
        // Arm base (shoulder joint)
        color([0.6, 0.6, 0.65])
        translate([side * (body_w/2 + 0.02), 0, -body_h * 0.1]) {
            // Upper arm
            rotate([0, side * 35, 0])
            translate([side * arm_length/2, 0, 0]) {
                cube([arm_length, arm_dia, arm_dia], center=true);

                // Forearm
                translate([side * arm_length/2, 0, -0.02])
                rotate([0, side * -25, 0])
                translate([side * arm_length * 0.4, 0, 0]) {
                    cube([arm_length * 0.8, arm_dia * 0.8, arm_dia * 0.8], center=true);

                    // WAAM print head / gripper
                    color([0.85, 0.7, 0.2])
                    translate([side * arm_length * 0.4, 0, 0])
                        sphere(d=gripper_dia);

                    // Nozzle tip (red)
                    color([0.9, 0.3, 0.2])
                    translate([side * (arm_length * 0.4 + gripper_dia/2), 0, 0])
                        cylinder(d=0.015, h=0.025, center=true);
                }
            }
        }
    }

    // Ion thruster (rear, +X direction)
    color([0.3, 0.7, 0.9])
    translate([body_w/2 + ion_depth/2, 0, 0])
        sphere(d=ion_dia);

    // Ion nozzle cone
    color([0.5, 0.5, 0.55])
    translate([body_w/2, 0, 0])
    rotate([0, 90, 0])
        cylinder(d1=ion_dia * 1.2, d2=ion_dia * 0.5, h=ion_depth);

    // Membrane bundle (golden lump underneath)
    color([0.85, 0.75, 0.25])
    translate([-body_w * 0.1, 0, -(body_h/2 + membrane_bundle_h/2)])
        scale([membrane_bundle_w, membrane_bundle_d, membrane_bundle_h])
            sphere(d=1);

    // Material airlock port (small cylinder on underside)
    color([0.55, 0.55, 0.6])
    translate([body_w * 0.15, body_d * 0.2, -body_h/2])
    rotate([0, 0, 0])
        cylinder(d=airlock_dia, h=0.03, center=true);

    // Star tracker (tiny dome on top)
    color([0.2, 0.2, 0.25])
    translate([body_w * 0.15, -body_d * 0.15, body_h/2 + 0.01])
        sphere(d=0.03);

    // UHF antenna (small rod on top)
    color([0.7, 0.7, 0.7])
    translate([-body_w * 0.15, 0, body_h/2])
        cylinder(d=0.008, h=0.08);

    // AS7341 spectral sensor (small window on front)
    color([0.1, 0.3, 0.1])
    translate([-body_w/2 - 0.005, 0, 0])
        cube([0.01, 0.04, 0.04], center=true);
}


// === RENDER ===
scale(scale_factor * 1000)  // Convert to mm at chosen scale
    seed_mothership();

// === ANNOTATION ===
// To print: Export as STL from OpenSCAD (F6 then File > Export STL)
// Recommended: 0.2mm layer height, 20% infill, no supports
// At 1:10 scale: fits in 200mm x 100mm x 50mm
// At 1:5 scale:  400mm wingspan (needs large printer)
