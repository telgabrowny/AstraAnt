// AstraAnt Tool: Bioreactor Sampling Probe
// Print body in PETG. pH electrode and turbidity sensor purchased separately.
// Syringe barrel is a standard 5ml lab syringe body.
//
// Print orientation: mount face down
// Supports: needed for probe tip

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
body_diameter = 10;
body_length = 50;
probe_tip_length = 15;
syringe_diameter = 12;    // 5ml syringe barrel OD
sensor_pocket_d = 6;      // pH electrode diameter

module probe_body() {
    difference() {
        union() {
            // Main body
            cylinder(d=body_diameter, h=body_length);
            // Syringe holder (side mount)
            translate([body_diameter/2 + 2, 0, body_length/2])
                cylinder(d=syringe_diameter + 3, h=body_length * 0.6, center=true);
        }
        // pH electrode pocket
        translate([0, 0, -0.1])
            cylinder(d=sensor_pocket_d + 0.3, h=body_length * 0.7);
        // Turbidity sensor window
        translate([body_diameter/2 - 1, 0, body_length * 0.3])
            cube([3, 4, 4], center=true);
        // Syringe barrel hole
        translate([body_diameter/2 + 2, 0, body_length * 0.2])
            cylinder(d=syringe_diameter + 0.3, h=body_length * 0.6);
        // Wire channel (runs up the back)
        translate([-body_diameter/2 + 1, 0, 0])
            cylinder(d=2.5, h=body_length + 1);
    }
}

module sampling_probe_assembly() {
    magnetic_mount();
    translate([0, 0, 3])
        probe_body();
}

sampling_probe_assembly();
