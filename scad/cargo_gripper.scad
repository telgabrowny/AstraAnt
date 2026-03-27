// AstraAnt Tool: Cargo Gripper
// Print in PETG. Glue silicone grip pads to jaw faces.
// Passive — mandibles provide all grip force.
//
// Print orientation: jaw-side up
// Supports: none needed

$fn = 32;


// Universal magnetic mount interface
// Clips between ant mandibles, held by neodymium magnets
module magnetic_mount(width=15, depth=10, magnet_d=4) {
    difference() {
        // Mount body
        cube([width, depth, 6], center=true);
        // Magnet pocket (recessed)
        translate([0, 0, 1.5])
            cylinder(d=4+0.2, h=3, center=true, $fn=32);
        // Mandible grip grooves (two channels for ant mandibles)
        for (side = [-1, 1]) {
            translate([side * (width/2 - 1.5), 0, 0])
                cube([2, depth+1, 3], center=true);
        }
    }
}


// Parameters
jaw_width = 35;
jaw_opening = 40;
jaw_depth = 20;
wall = 3;
grip_pad_area = 10;  // Size of silicone pad bonding area

module gripper_jaw() {
    // U-shaped fork
    difference() {
        cube([jaw_width, jaw_depth, jaw_opening/2 + wall], center=true);
        // Inner cavity
        translate([0, 0, wall])
            cube([jaw_width - 2*wall, jaw_depth - 2*wall, jaw_opening/2 + 1], center=true);
    }
    // Grip pad recesses (for silicone pads)
    for (side = [-1, 1]) {
        translate([side * (jaw_width/2 - wall/2), 0, jaw_opening/4]) {
            difference() {
                cube([wall + 0.1, grip_pad_area, grip_pad_area], center=true);
                // Shallow recess for pad
                translate([side * 0.5, 0, 0])
                    cube([1.2, grip_pad_area - 1, grip_pad_area - 1], center=true);
            }
        }
    }
}

module cargo_gripper_assembly() {
    magnetic_mount();
    translate([0, jaw_depth/2 + 5, 3])
        gripper_jaw();
}

cargo_gripper_assembly();
