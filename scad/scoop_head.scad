// AstraAnt Tool: Regolith Scoop
// Print in PETG. No electronics — fully passive.
// Mandibles grip the handle, scoop digs into regolith.
//
// Print orientation: scoop-side up
// Supports: none needed

$fn = 48;


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
scoop_width = 25;
scoop_depth = 15;
scoop_length = 35;
wall_thickness = 1.5;
lip_height = 3;       // Rear lip prevents material sliding out

module scoop() {
    difference() {
        // Outer shell
        hull() {
            translate([0, 0, 0])
                cube([scoop_width, scoop_length, 0.1], center=true);
            translate([0, -scoop_length/4, scoop_depth])
                scale([1, 0.6, 1])
                    cylinder(d=scoop_width, h=0.1, center=true);
        }
        // Inner cavity
        translate([0, 0, wall_thickness])
            hull() {
                translate([0, 0, 0])
                    cube([scoop_width - 2*wall_thickness,
                          scoop_length - 2*wall_thickness, 0.1], center=true);
                translate([0, -scoop_length/4, scoop_depth - wall_thickness])
                    scale([1, 0.6, 1])
                        cylinder(d=scoop_width - 2*wall_thickness, h=0.1, center=true);
            }
    }
    // Rear lip
    translate([0, scoop_length/2 - wall_thickness, scoop_depth/2])
        cube([scoop_width, wall_thickness, lip_height], center=true);
}

module scoop_head_assembly() {
    // Mount
    magnetic_mount();
    // Handle connecting mount to scoop
    translate([0, 0, 3])
        cube([8, 10, 8], center=true);
    // Scoop
    translate([0, 10, 7])
        rotate([30, 0, 0])
            scoop();
}

scoop_head_assembly();
