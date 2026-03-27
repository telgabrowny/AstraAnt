// AstraAnt Cargo Pod Scaffold (Ferrocement)
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

module lattice_box(size, cell, strut) {
    // Open lattice box -- print this, fill with paste
    difference() {
        cube(size, center=true);
        // Hollow interior
        cube([size[0]-2*wall, size[1]-2*wall, size[2]-2*wall], center=true);
    }
    // Internal lattice struts (X direction)
    for (y = [-size[1]/2 + cell : cell : size[1]/2 - cell]) {
        for (z = [-size[2]/2 + cell : cell : size[2]/2 - cell]) {
            translate([0, y, z])
                cube([size[0] - 2*wall, strut, strut], center=true);
        }
    }
    // Internal lattice struts (Y direction)
    for (x = [-size[0]/2 + cell : cell : size[0]/2 - cell]) {
        for (z = [-size[2]/2 + cell : cell : size[2]/2 - cell]) {
            translate([x, 0, z])
                cube([strut, size[1] - 2*wall, strut], center=true);
        }
    }
}

module sail_mount() {
    // Attachment point for solar sail deployment booms
    translate([0, 0, pod_height/2]) {
        cylinder(d=10, h=5);
        // Boom socket holes (4 directions)
        for (a = [0, 90, 180, 270]) {
            rotate([0, 0, a])
                translate([8, 0, 2.5])
                    rotate([0, 90, 0])
                        cylinder(d=3.2, h=5, center=true, $fn=16);
        }
    }
}

module guidance_mount() {
    // Mount point for the guidance unit (stripped surface ant brain)
    translate([pod_length/2 - 15, 0, pod_height/2]) {
        difference() {
            cube([30, 25, 3], center=true);
            // Screw holes
            for (x = [-10, 10], y = [-8, 8]) {
                translate([x, y, 0])
                    cylinder(d=2.5, h=5, center=true, $fn=16);
            }
        }
    }
}

module thruster_mount() {
    // Mount for CO2 cold gas thruster (rear)
    translate([-pod_length/2, 0, 0]) {
        difference() {
            cylinder(d=35, h=15, center=true);
            cylinder(d=30.5, h=16, center=true);  // Tank OD + clearance
        }
    }
}

module pod_scaffold() {
    lattice_box([pod_length, pod_width, pod_height], cell_size, strut_width);
    sail_mount();
    guidance_mount();
    thruster_mount();
}

pod_scaffold();
