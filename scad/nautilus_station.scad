// AstraAnt Nautilus Station -- Multi-Generation Growth Model
//
// Cutaway display model showing 5 generations of nautilus growth.
// Each chamber is slightly larger than the last. The original
// 2m rock and membrane are at the center (the vault).
//
// Scale: 1:100 (full station on a desk)
// At 1:100: Generation 1 = 20mm, Generation 5 = ~55mm
//
// Half-shell cutaway shows the internal chamber progression.
// Print in one piece or print each shell separately for assembly.

$fn = 48;

scale_factor = 1/100;

// Chamber data: [diameter_m, wall_mm, label]
// From the bootstrap simulation (Mode B, scaling path)
chambers = [
    [2.0,  0.5,  "Gen 0: Kapton bag + 2m rock (the vault)"],
    [2.8,  1.5,  "Gen 1: First iron sphere"],
    [4.5,  1.5,  "Gen 2: Steam turbine built here"],
    [9.3,  2.0,  "Gen 3: Full bot fleet"],
    [14.0, 3.0,  "Gen 4: Commercial operations"],
];

// Colors per generation (inner = oldest = darkest)
gen_colors = [
    [0.85, 0.75, 0.25],  // Gold (Kapton membrane)
    [0.55, 0.57, 0.62],  // Dark iron
    [0.60, 0.63, 0.68],  // Medium iron
    [0.65, 0.67, 0.72],  // Light iron
    [0.70, 0.72, 0.78],  // Bright iron
];


// === SINGLE CHAMBER SHELL (half-sphere cutaway) ===
module chamber_shell(outer_d, wall_mm, col) {
    wall_m = wall_mm / 1000;
    // Minimum visible wall thickness at this scale
    vis_wall = max(wall_m, outer_d * 0.02);

    color(col)
    difference() {
        sphere(d=outer_d);
        sphere(d=outer_d - vis_wall * 2);
        // Cut away front half for visibility
        translate([0, -outer_d, 0])
            cube([outer_d * 2, outer_d * 2, outer_d * 2], center=true);
    }
}

// === BULKHEAD / SEPTUM between chambers ===
module bulkhead(diameter, position_z) {
    color([0.5, 0.52, 0.55])
    translate([0, 0, position_z])
    rotate([90, 0, 0])
        cylinder(d=diameter * 0.9, h=0.05, center=true);
}

// === SIPHUNCLE TUBE (connects chambers) ===
module siphuncle(start_d, end_d, length) {
    color([0.6, 0.55, 0.5])
    translate([0, 0, 0])
    rotate([90, 0, 0])
        cylinder(d=min(start_d, end_d) * 0.08, h=length, center=true);
}

// === SEED MOTHERSHIP (tiny at this scale, on the outermost shell) ===
module tiny_mothership() {
    s = 0.5;  // At real scale, 0.5m body
    color([0.4, 0.4, 0.45])
    cube([s, s * 0.6, s * 0.7], center=true);

    // Wings
    for (side = [-1, 1]) {
        color([0.15, 0.3, 0.75])
        translate([0, side * 1.0, 0])
            cube([s * 0.8, 1.2, 0.02], center=true);
    }
}

// === PRINTER BOTS (on outer shell) ===
module tiny_bot(s=0.15) {
    color([0.9, 0.65, 0.2])
    scale([1.5, 0.7, 1])
        sphere(d=s);
}

// === FULL NAUTILUS STATION ===
module nautilus_station() {

    // The original rock at the very center (the vault)
    color([0.55, 0.43, 0.3])
    sphere(d=1.8);

    // Chamber shells (cutaway, nested)
    for (i = [0 : len(chambers) - 1]) {
        d = chambers[i][0] * 1.15;  // Shell is ~15% larger than rock
        w = chambers[i][1];
        c = gen_colors[i];
        chamber_shell(d, w, c);
    }

    // Bulkheads between chambers (at each shell boundary)
    for (i = [1 : len(chambers) - 1]) {
        d = chambers[i-1][0] * 1.15;
        // Offset slightly along Y so visible in cutaway
        color([0.45, 0.47, 0.5])
        translate([0, d * 0.45, 0])
        rotate([90, 0, 0])
            difference() {
                cylinder(d=d * 0.95, h=0.04, center=true, $fn=32);
                cylinder(d=d * 0.15, h=0.05, center=true, $fn=16); // Siphuncle hole
            }
    }

    // Siphuncle running through all chambers
    outer_d = chambers[len(chambers)-1][0] * 1.15;
    color([0.5, 0.45, 0.4])
    rotate([90, 0, 0])
        cylinder(d=outer_d * 0.04, h=outer_d, center=true, $fn=16);

    // Mothership on top of outermost shell
    translate([0, 0, chambers[len(chambers)-1][0] * 1.15 / 2 + 0.5])
        tiny_mothership();

    // Printer bots on outermost surface
    outer_r = chambers[len(chambers)-1][0] * 1.15 / 2;
    for (i = [0 : 5]) {
        a1 = i * 60 + 15;
        a2 = i * 37;
        bx = outer_r * cos(a1) * cos(a2);
        by = max(0.1, outer_r * sin(a2));  // Keep on visible half
        bz = outer_r * sin(a1) * cos(a2);
        translate([bx, by, bz])
            tiny_bot();
    }

    // Concentrator mirrors (4 around the station)
    for (i = [0 : 3]) {
        a = i * 90 + 20;
        mr = outer_r + 2.0;
        color([0.75, 0.8, 0.9])
        translate([cos(a) * mr, 1, sin(a) * mr])
        rotate([0, -a, -15])
            cube([1.5, 1.5, 0.02], center=true);
    }

    // Labels (as positioned text indicators -- small spheres)
    // Gen 0 indicator (gold dot at center)
    color([1, 0.9, 0.3])
    translate([0, 1.0, 0])
        sphere(d=0.15);

    // Outermost label (green dot)
    color([0.3, 0.9, 0.3])
    translate([0, outer_r + 0.3, 0])
        sphere(d=0.15);
}


// === RENDER ===
scale(scale_factor * 1000)  // mm at chosen scale
    nautilus_station();

// === PRINT NOTES ===
// At 1:100 scale:
//   Inner vault (Gen 0): 23mm diameter
//   Outer shell (Gen 4): 161mm diameter
//   Total width with concentrators: ~200mm
//   Height with mothership: ~100mm
//
// Multi-color printing recommended:
//   Gold center = Kapton membrane (Gen 0)
//   Darkening iron shells = progressive generations
//   Blue wings = solar panels
//   Orange dots = printer bots
//
// The cutaway half-shell design lets you see all 5 generations
// nested inside each other. The gold center is the original
// garbage bag -- still there at the heart of the station.
//
// Print orientation: cutaway face down on build plate.
// Supports: minimal (for overhanging shell edges).
