// AstraAnt Tool: Thermal Sorting Rake
// Print handle in PETG. Ceramic tine inserts press-fit into holes.
// (Buy 3mm alumina rods from McMaster-Carr or Amazon)
//
// Print orientation: flat (handle horizontal)
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
handle_length = 25;
handle_diameter = 10;
tine_count = 5;
tine_length = 15;
tine_diameter = 3;      // Matches standard alumina rod
tine_spacing = 6;
rake_width = (tine_count - 1) * tine_spacing;

module handle() {
    rotate([0, 90, 0])
        cylinder(d=handle_diameter, h=handle_length);
}

module rake_head() {
    // Cross-bar connecting tines
    cube([rake_width + tine_spacing, handle_diameter, 4], center=true);
    // Tine sockets
    for (i = [0:tine_count-1]) {
        translate([(i - (tine_count-1)/2) * tine_spacing, 0, -2]) {
            difference() {
                cylinder(d=tine_diameter + 2, h=5, $fn=16);
                // Hole for ceramic rod press-fit
                translate([0, 0, -0.1])
                    cylinder(d=tine_diameter + 0.1, h=5.2, $fn=16);
            }
        }
    }
}

module pusher_face() {
    // Flat back of rake doubles as pusher
    translate([0, handle_diameter/2, 0])
        cube([rake_width + tine_spacing, 2, 15], center=true);
}

module thermal_rake_assembly() {
    magnetic_mount();
    translate([0, 0, 3])
        handle();
    translate([handle_length/2, 0, 3 + handle_length])
        rake_head();
    translate([handle_length/2, 0, 3 + handle_length])
        pusher_face();
}

thermal_rake_assembly();
