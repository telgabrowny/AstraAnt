// AstraAnt Tool: Paste Applicator Nozzle
// Print body in PETG. Silicone tube reservoir purchased separately.
// Mandible squeeze pushes paste through slit nozzle.
// Trowel blade on bottom smooths the applied layer.
//
// Print orientation: mount face down
// Supports: needed for nozzle overhang

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
reservoir_od = 20;      // Silicone tube outer diameter
reservoir_length = 35;
nozzle_width = 20;
nozzle_slit = 2;        // Slit height controls paste thickness
trowel_width = 25;
trowel_angle = 45;

module reservoir_cradle() {
    // Holds the silicone tube reservoir
    difference() {
        cube([reservoir_od + 4, reservoir_length, reservoir_od + 4], center=true);
        // Tube channel
        rotate([90, 0, 0])
            cylinder(d=reservoir_od + 0.5, h=reservoir_length + 1, center=true);
        // Squeeze access (open sides for mandible grip)
        for (side = [-1, 1]) {
            translate([side * (reservoir_od/2 + 2), 0, 0])
                cube([4, reservoir_length + 1, reservoir_od - 4], center=true);
        }
    }
}

module nozzle() {
    // Flat slit nozzle
    difference() {
        cube([nozzle_width, 8, 6], center=true);
        // Slit opening
        cube([nozzle_width - 4, 4, nozzle_slit], center=true);
    }
}

module trowel() {
    // Flat blade for smoothing
    translate([0, 0, -3])
        rotate([trowel_angle, 0, 0])
            cube([trowel_width, 0.8, 12], center=true);
}

module paste_nozzle_assembly() {
    magnetic_mount();
    translate([0, 0, 3 + reservoir_od/2 + 2])
        reservoir_cradle();
    translate([0, reservoir_length/2 + 4, 3])
        nozzle();
    translate([0, reservoir_length/2 + 8, 0])
        trowel();
}

paste_nozzle_assembly();
