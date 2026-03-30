// AstraAnt Universal Hybrid Grip Foot Pad
// 8mm disc with 3 passive grip layers:
//   Center: N52 neodymium magnet (metallic surfaces)
//   Ring: 8 spring-steel microspines (rocky surfaces)
//   Perimeter: 4 penetrator studs (loose regolith)
//
// Print in PETG, press-fit magnet and spines after printing.
// Attaches to SG90 servo horn arm at leg tip.

// --- Parameters (all in mm) ---
pad_diameter = 8;
pad_thickness = 3;
pad_radius = pad_diameter / 2;

// Magnet pocket (center)
magnet_d = 3.2;           // 3mm magnet + 0.2mm press-fit clearance
magnet_depth = 1.7;       // 1.5mm magnet + 0.2mm clearance
magnet_from_bottom = 0.4; // thin floor below magnet

// Microspine holes (ring of 8)
spine_count = 8;
spine_hole_d = 0.4;       // 0.3mm wire + 0.1mm clearance
spine_ring_radius = 2.8;  // distance from center to spine holes
spine_angle = 30;          // inward angle from vertical
spine_depth = 3.5;         // through most of pad thickness

// Penetrator studs (perimeter, 4 at 45/135/225/315 degrees)
stud_count = 4;
stud_height = 2;
stud_base_d = 1.5;
stud_tip_d = 0.3;
stud_ring_radius = pad_radius - 0.5;

// Servo horn attachment (top)
horn_bore_d = 2.2;        // for M2 screw or servo horn shaft
horn_bore_depth = 2.0;

// --- Modules ---

module foot_pad_body() {
    // Main disc
    cylinder(d=pad_diameter, h=pad_thickness, $fn=64);
}

module magnet_pocket() {
    // Centered pocket from bottom face
    translate([0, 0, magnet_from_bottom])
        cylinder(d=magnet_d, h=magnet_depth, $fn=32);
}

module spine_hole(index) {
    // Angled hole for spring-steel microspine
    angle_around = index * (360 / spine_count);
    rotate([0, 0, angle_around])
        translate([spine_ring_radius, 0, pad_thickness])
            rotate([spine_angle, 0, 0])
                cylinder(d=spine_hole_d, h=spine_depth + 1, $fn=16);
}

module spine_holes() {
    for (i = [0 : spine_count - 1]) {
        spine_hole(i);
    }
}

module penetrator_stud(index) {
    // Conical stud protruding from bottom face
    stud_angle = 45 + index * (360 / stud_count);
    rotate([0, 0, stud_angle])
        translate([stud_ring_radius, 0, 0])
            // Cone: base at pad bottom, tip extending down
            rotate([180, 0, 0])
                cylinder(d1=stud_base_d, d2=stud_tip_d,
                         h=stud_height, $fn=16);
}

module penetrator_studs() {
    for (i = [0 : stud_count - 1]) {
        penetrator_stud(i);
    }
}

module horn_attachment() {
    // Bore from top for servo horn connection
    translate([0, 0, pad_thickness - horn_bore_depth])
        cylinder(d=horn_bore_d, h=horn_bore_depth + 0.1, $fn=16);
}

// --- Assembly ---

module foot_pad() {
    union() {
        difference() {
            foot_pad_body();
            magnet_pocket();
            spine_holes();
            horn_attachment();
        }
        penetrator_studs();
    }
}

// Render
foot_pad();

// --- Cross-section view (uncomment to inspect internals) ---
// difference() {
//     foot_pad();
//     translate([0, -10, -5]) cube([20, 20, 20]);
// }
