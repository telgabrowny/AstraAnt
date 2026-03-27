// AstraAnt Mothership -- Parametric 3D-Printable Scale Model
//
// Layer-cake design: modules stack vertically.
// Phase 2 cargo pods ring the outside.
// Solar panels fold out from the top.
// Drill on bottom, antenna on top.
//
// Default scale: 1:25 (fits on any desktop 3D printer)
// At 1:25: 60mm diameter core, 140mm tall
//
// Each module can be toggled on/off to match your mission config.
// This is the same geometry the GUI uses for the 3D visualization.

$fn = 48;

// === SCALE AND CONFIG ===
scale_factor = 1/25;  // 1:25 scale. Change to 1/50 for smaller, 1/10 for larger.

// Toggle modules (1 = included, 0 = excluded)
include_drill = 1;
include_sealing = 1;
include_thermal_sorter = 1;
include_bioreactor = 1;
include_water_tank = 1;
include_sugar_production = 1;
include_manufacturing = 1;
include_cargo_staging = 1;
include_micro_pods = 1;
include_comms = 1;
include_solar_panels = 1;
include_phase2_ring = 1;
include_ant_rack = 1;

// === DIMENSIONS (real meters, scaled at render) ===
core_diameter = 1.5;
core_radius = core_diameter / 2;

// Module heights (bottom to top)
drill_h = 0.3;
seal_h = 0.4;
sorter_h = 0.4;
bioreactor_h = 1.0;
water_h = 0.5;
sugar_h = 0.6;
mfg_h = 0.5;
cargo_h = 0.4;
pods_h = 0.3;
comms_h = 0.8;
solar_h = 0.2;

// === MODULES ===

module drill_module(z_offset) {
    if (include_drill) {
        translate([0, 0, z_offset])
        color("silver") {
            // Drill body (cone)
            cylinder(d1=0.2, d2=1.0, h=drill_h * 0.7);
            // Gasket ring
            translate([0, 0, drill_h * 0.7])
                difference() {
                    cylinder(d=1.2, h=drill_h * 0.3);
                    translate([0, 0, -0.01])
                        cylinder(d=0.8, h=drill_h * 0.3 + 0.02);
                }
        }
    }
}

module sealing_module(z_offset) {
    if (include_sealing) {
        translate([0, 0, z_offset])
        color("gray") {
            difference() {
                cylinder(d=1.2, h=seal_h);
                translate([0, 0, 0.05])
                    cylinder(d=0.6, h=seal_h);  // Tunnel opening
            }
        }
    }
}

module bioreactor_module(z_offset) {
    if (include_bioreactor) {
        translate([0, 0, z_offset])
        color("darkcyan") {
            // Three vats visible
            for (a = [0, 120, 240]) {
                rotate([0, 0, a])
                translate([core_radius * 0.4, 0, 0])
                    cylinder(d=0.4, h=bioreactor_h * 0.8);
            }
            // Outer shell
            difference() {
                cylinder(d=core_diameter, h=bioreactor_h);
                translate([0, 0, 0.05])
                    cylinder(d=core_diameter - 0.15, h=bioreactor_h);
            }
        }
    }
}

module water_tank(z_offset) {
    if (include_water_tank) {
        translate([0, 0, z_offset])
        color("deepskyblue", 0.6) {
            // Toroidal tank wrapping the bioreactor (radiation shield)
            difference() {
                cylinder(d=core_diameter + 0.3, h=water_h);
                translate([0, 0, -0.01])
                    cylinder(d=core_diameter - 0.1, h=water_h + 0.02);
            }
        }
    }
}

module manufacturing_module(z_offset) {
    if (include_manufacturing) {
        translate([0, 0, z_offset])
        color("orange", 0.7) {
            difference() {
                cylinder(d=core_diameter * 0.8, h=mfg_h);
                translate([0, 0, 0.05])
                    cylinder(d=core_diameter * 0.6, h=mfg_h);
            }
            // Furnace (small cylinder)
            translate([core_radius * 0.3, 0, 0])
                cylinder(d=0.15, h=mfg_h * 0.6);
        }
    }
}

module cargo_module(z_offset) {
    if (include_cargo_staging) {
        translate([0, 0, z_offset])
        color("olive") {
            difference() {
                cylinder(d=core_diameter, h=cargo_h);
                translate([0, 0, 0.05])
                    cylinder(d=core_diameter - 0.15, h=cargo_h);
            }
            // Loading arm
            translate([core_radius * 0.5, 0, cargo_h])
                cube([0.05, 0.05, 0.3]);
        }
    }
}

module comms_module(z_offset) {
    if (include_comms) {
        translate([0, 0, z_offset])
        color("white") {
            // Antenna mast
            cylinder(d=0.05, h=comms_h);
            // Dish
            translate([0, 0, comms_h * 0.7])
                scale([1, 1, 0.3])
                    sphere(d=0.3);
        }
    }
}

module solar_panels(z_offset) {
    if (include_solar_panels) {
        translate([0, 0, z_offset])
        color("midnightblue") {
            // Hub
            cylinder(d=core_diameter, h=solar_h);
            // Four panel wings (deployed)
            for (a = [0, 90, 180, 270]) {
                rotate([0, 0, a])
                translate([core_radius, 0, solar_h/2])
                    cube([2.0, 0.02, 0.8], center=true);
            }
        }
    }
}

module phase2_cargo_ring(z_offset) {
    if (include_phase2_ring) {
        translate([0, 0, z_offset])
        color("dimgray", 0.5) {
            // Ring of cargo containers around the core
            for (a = [0 : 30 : 330]) {
                rotate([0, 0, a])
                translate([core_radius + 0.3, 0, 0])
                    cube([0.3, 0.2, 2.0]);
            }
        }
    }
}

module ant_rack(z_offset) {
    if (include_ant_rack) {
        translate([0, 0, z_offset])
        color("darkorange") {
            // Tiny dots representing stored ants
            for (a = [0 : 36 : 324]) {
                rotate([0, 0, a])
                translate([core_radius * 0.3, 0, 0.1])
                    sphere(d=0.03);
            }
        }
    }
}

module grip_rails() {
    // Vertical rails on the outside of the hull
    color("darkgray")
    for (a = [0 : 45 : 315]) {
        rotate([0, 0, a])
        translate([core_radius + 0.02, 0, 0])
            cube([0.02, 0.01, 3.5]);
    }
}

// === ASSEMBLY ===

module mothership_assembly() {
    z = 0;

    drill_module(z); z = z + drill_h;
    sealing_module(z); z = z + seal_h;

    // Lower deck
    if (include_thermal_sorter) {
        translate([core_radius * 0.5, 0, z])
        color("firebrick")
            cylinder(d=0.4, h=sorter_h);
    }
    z = z + sorter_h;

    bioreactor_module(z);
    water_tank(z); // Wraps around bioreactor
    z = z + bioreactor_h;

    // Mid deck
    if (include_sugar_production) {
        translate([-core_radius * 0.3, 0, z])
        color("green", 0.6)
            cylinder(d=0.3, h=sugar_h);
    }
    z = z + max(sugar_h, water_h);

    manufacturing_module(z); z = z + mfg_h;
    cargo_module(z); z = z + cargo_h;

    ant_rack(z); z = z + 0.2;

    // Top
    solar_panels(z); z = z + solar_h;
    comms_module(z);

    // Phase 2 cargo ring (around the core)
    phase2_cargo_ring(drill_h + seal_h);

    // Grip rails on exterior
    grip_rails();
}

// Render at scale
scale([scale_factor * 1000, scale_factor * 1000, scale_factor * 1000])
    mothership_assembly();

// At 1:25 scale, this renders as:
// Core: ~60mm diameter, ~140mm tall
// Solar panels: ~200mm wingspan (deployed)
// Phase 2 ring: ~100mm diameter
//
// To print:
// 1. Export as STL
// 2. Slice at 0.2mm layer height
// 3. PETG or PLA
// 4. Print time: ~4-6 hours
// 5. Paint the modules different colors for visibility
