// AstraAnt Tool: Rotary Drill Head
// Print in PETG. Motor (N20) press-fits into body cavity.
// Bit is replaceable (insert from front).
//
// Print orientation: mount face on build plate (standing up)
// Supports: none needed
// Tolerance: 0.2mm for press-fit pockets

$fn = 64;


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


// Parameters (edit these to customize)
body_diameter = 12;
body_length = 30;
bit_diameter = 8;
bit_length = 20;
motor_pocket_d = 12.2;   // N20 motor diameter + clearance
motor_pocket_depth = 25;
flute_count = 4;
flute_depth = 1.5;

module drill_body() {
    difference() {
        // Cylindrical body
        cylinder(d=body_diameter, h=body_length);
        // Motor pocket (hollowed from rear)
        translate([0, 0, -0.1])
            cylinder(d=motor_pocket_d, h=motor_pocket_depth);
        // Shaft hole through the front
        translate([0, 0, motor_pocket_depth - 1])
            cylinder(d=3.2, h=body_length, $fn=32);  // 3mm motor shaft + clearance
    }
}

module drill_bit() {
    // Conical fluted bit (decorative — real bit is tungsten carbide insert)
    difference() {
        cylinder(d1=bit_diameter, d2=2, h=bit_length);
        // Flutes (spiral approximated as straight channels)
        for (i = [0:flute_count-1]) {
            rotate([0, 0, i * 360/flute_count])
                translate([bit_diameter/4, 0, -1])
                    cube([bit_diameter, flute_depth, bit_length+2]);
        }
    }
}

// Assembly
module drill_head_assembly() {
    // Mount interface at bottom
    magnetic_mount();
    // Body
    translate([0, 0, 3])
        drill_body();
    // Bit
    translate([0, 0, 3 + body_length])
        drill_bit();
}

drill_head_assembly();
