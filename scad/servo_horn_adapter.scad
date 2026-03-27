// AstraAnt Servo Horn to Leg Segment Adapter
// Connects the SG90 servo output horn to the ant's leg segment.
// Press-fit on both ends — servo horn star shape on one end,
// cylindrical socket for leg segment on the other.
//
// Print in PETG at 0.15mm layer height for best fit.
// May need +/- 0.1mm adjustment after test fit.

$fn = 32;

// SG90 servo horn dimensions (standard star/cross pattern)
horn_arm_length = 7;    // From center to tip of horn arm
horn_arm_width = 4;     // Width of each arm
horn_center_hole_d = 4.8; // Center bore (fits servo shaft spline)
horn_thickness = 2;

// Leg segment dimensions
leg_segment_od = 4;     // Outer diameter of leg tube
leg_socket_depth = 8;   // How deep the leg inserts
leg_socket_id = 4.2;    // Slightly oversized for press-fit (adjust!)

// Adapter body
adapter_length = 12;    // Total length from horn face to leg socket end
adapter_od = 8;         // Outer diameter of adapter body

module servo_horn_socket() {
    // Negative space matching the SG90 horn shape
    // Cross/star pattern with 4 arms
    for (a = [0, 90]) {
        rotate([0, 0, a])
            cube([horn_arm_length * 2, horn_arm_width, horn_thickness + 0.2], center=true);
    }
    // Center shaft hole
    cylinder(d=horn_center_hole_d, h=horn_thickness + 1, center=true);
}

module leg_socket() {
    // Socket for the leg segment tube
    cylinder(d=leg_socket_id, h=leg_socket_depth);
}

module adapter() {
    difference() {
        // Main body
        cylinder(d=adapter_od, h=adapter_length);

        // Servo horn socket (bottom end)
        translate([0, 0, -0.1])
            servo_horn_socket();

        // Leg segment socket (top end)
        translate([0, 0, adapter_length - leg_socket_depth])
            leg_socket();

        // Weight reduction holes
        for (a = [0, 120, 240]) {
            rotate([0, 0, a])
            translate([adapter_od/3, 0, adapter_length/2])
                cylinder(d=2, h=adapter_length * 0.6, center=true);
        }
    }
}

adapter();

// Print orientation: horn socket face on build plate
// No supports needed
// Test fit: if loose, reduce leg_socket_id by 0.1mm
//           if tight, increase by 0.1mm
