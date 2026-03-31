// AstraAnt Nautilus Station -- Logarithmic Spiral Growth Model
//
// Cutaway display model showing 5 generations of nautilus growth
// arranged as a LOGARITHMIC SPIRAL of adjacent chambers, like a
// real nautilus shell cross-section.
//
// How the station actually grows:
//   Gen 0: 2m rock processed inside a Kapton membrane bag (gold)
//   Gen 1: A slightly larger iron sphere built NEXT TO Gen 0
//   Gen 2: Another larger sphere next to Gen 1, continuing the spiral
//   Gen 3, Gen 4: Each new chamber adjacent, slightly larger
//   Chambers connected by siphuncle tubes (small pipe between neighbors)
//   Retired chambers sealed by bulkheads (flat disc with siphuncle hole)
//
// Logarithmic spiral: r(theta) = a * e^(b*theta)
// Growth factor per chamber: 1.15x diameter
// Diameters: [2.0, 2.8, 4.5, 9.3, 14.0] meters
//
// Scale: 1:100 (fits on a standard ~200mm printer bed)
// Half-shell cutaway so you can see inside each chamber.
//
// Print in PLA/PETG. Multi-material recommended for colors.

$fn = 48;

// === SCALE ===
scale_factor = 1/100;  // 1:100.  Use 1/50 for a bigger desk model.

// === CHAMBER DATA ===
// [diameter_m, wall_mm, label]
// From the bootstrap simulation (Mode B, scaling path)
chamber_diameters = [2.0, 2.8, 4.5, 9.3, 14.0];
chamber_walls_mm  = [0.5, 1.5, 1.5, 2.0, 3.0];

n_chambers = len(chamber_diameters);

// Colors per generation (Gen 0 = gold Kapton, older iron = darker)
gen_colors = [
    [0.85, 0.75, 0.25],  // Gen 0: Gold (Kapton membrane)
    [0.55, 0.57, 0.62],  // Gen 1: Dark iron (oldest iron shell)
    [0.60, 0.63, 0.68],  // Gen 2: Medium iron
    [0.65, 0.67, 0.72],  // Gen 3: Light iron
    [0.70, 0.72, 0.78],  // Gen 4: Bright iron (newest, still shiny)
];

// === LOGARITHMIC SPIRAL LAYOUT ===
// r(theta) = a * e^(b * theta)
// We fit the spiral so each chamber center sits on the curve, with
// adjacent chambers tangent (touching, not overlapping).
//
// Strategy: place Gen 0 at the origin, then walk outward along the
// spiral, spacing each chamber so its edge touches the previous one.

// Compute center positions for each chamber along a logarithmic spiral.
// The angular step between chambers is chosen so the distance between
// centers equals the sum of their radii (tangent spheres).
//
// We accumulate angle theta and radius r.  For a logarithmic spiral
// the growth parameter b controls tightness.

spiral_b = 0.18;  // Tightness of the spiral (tuned to look good)

// Pre-compute center positions using a recursive-style approach.
// OpenSCAD doesn't have mutable state, so we use a function.

// Helper: cumulative angle for chamber i.  Chamber 0 is at theta=0.
function spiral_theta(i) =
    i == 0 ? 0 :
    let(
        r_prev = chamber_diameters[i-1] / 2,
        r_curr = chamber_diameters[i] / 2,
        // Distance between centers = sum of radii (tangent)
        gap = r_prev + r_curr,
        // Current spiral radius (distance from origin) at the previous angle
        prev_theta = spiral_theta(i-1),
        // Spiral radius at previous position
        r_spiral_prev = (chamber_diameters[0]/2) * exp(spiral_b * prev_theta),
        // We need the angle step dtheta such that the chord length
        // between the two positions on the spiral equals gap.
        // For a smooth spiral, arc length ~ gap, so:
        //   dtheta ~ gap / r_spiral_prev (first-order approximation)
        // Refined: use the actual chord with the growing radius
        r_spiral_next_est = r_spiral_prev + gap * spiral_b,
        avg_r = (r_spiral_prev + r_spiral_next_est) / 2,
        dtheta = gap / max(avg_r, 0.01)
    )
    prev_theta + dtheta;

// Compute X,Y position on spiral for chamber i
function spiral_x(i) =
    let(theta = spiral_theta(i),
        r = (chamber_diameters[0]/2) * exp(spiral_b * theta))
    r * cos(theta * 180 / PI);

function spiral_y(i) =
    let(theta = spiral_theta(i),
        r = (chamber_diameters[0]/2) * exp(spiral_b * theta))
    r * sin(theta * 180 / PI);

// Actual center coordinates (computed from spiral)
function chamber_center(i) = [spiral_x(i), spiral_y(i), 0];


// === MODULES ===

// --- Half-sphere cutaway chamber ---
module chamber_shell(outer_d, wall_mm, col) {
    wall_m = wall_mm / 1000;
    // Ensure visible wall thickness at this scale
    vis_wall = max(wall_m, outer_d * 0.02);

    color(col)
    difference() {
        sphere(d = outer_d);
        // Hollow interior
        sphere(d = outer_d - vis_wall * 2);
        // Cut away front half (Y < 0) for cutaway view
        translate([0, -outer_d, 0])
            cube([outer_d * 2, outer_d * 2, outer_d * 2], center=true);
    }
}

// --- Original rock inside Gen 0 ---
module vault_rock() {
    // Irregular-ish rock (stretched sphere)
    color([0.55, 0.43, 0.3])
    scale([1.0, 0.85, 0.9])
        sphere(d = 1.6);
}

// --- Bulkhead disc (seals retired chamber, has siphuncle hole) ---
module bulkhead(diameter, siphuncle_d) {
    color([0.45, 0.47, 0.5])
    difference() {
        // Flat disc, slightly smaller than the chamber
        cylinder(d = diameter * 0.85, h = 0.06, center=true, $fn=48);
        // Siphuncle hole through the center
        cylinder(d = siphuncle_d, h = 0.12, center=true, $fn=16);
    }
}

// --- Siphuncle tube (small pipe connecting adjacent chambers) ---
module siphuncle_tube(start_pos, end_pos, tube_d) {
    color([0.6, 0.55, 0.5])
    hull() {
        translate(start_pos) sphere(d = tube_d, $fn=16);
        translate(end_pos)   sphere(d = tube_d, $fn=16);
    }
}

// --- Seed mothership (tiny at 1:100, sits on top of newest chamber) ---
module tiny_mothership() {
    s = 0.5;  // 0.5m body at real scale
    color([0.4, 0.4, 0.45])
    cube([s, s * 0.6, s * 0.7], center=true);

    // Solar panel wings
    for (side = [-1, 1]) {
        color([0.15, 0.3, 0.75])
        translate([0, side * 1.0, 0])
            cube([s * 0.8, 1.2, 0.02], center=true);
    }

    // Robotic arm stubs
    for (side = [-1, 1]) {
        color([0.6, 0.6, 0.65])
        translate([side * 0.35, 0, -0.15])
        rotate([0, side * 25, 0])
            cylinder(d = 0.05, h = 0.25, $fn=12);
    }
}

// --- Printer bots (small blobs on outer shell) ---
module tiny_bot(s = 0.15) {
    color([0.9, 0.65, 0.2])
    scale([1.5, 0.7, 1])
        sphere(d = s);
}

// --- Concentrator mirror ---
module concentrator_mirror(size) {
    color([0.75, 0.8, 0.9, 0.7])
    cube([size, size, 0.02], center=true);
}


// === MAIN ASSEMBLY ===

module nautilus_station() {

    // --- Place each chamber along the spiral ---
    for (i = [0 : n_chambers - 1]) {
        d = chamber_diameters[i];
        w = chamber_walls_mm[i];
        c = gen_colors[i];
        cx = spiral_x(i);
        cy = spiral_y(i);

        translate([cx, 0, cy]) {
            chamber_shell(d, w, c);

            // Gen 0 gets the vault rock inside
            if (i == 0) {
                vault_rock();
            }
        }
    }

    // --- Siphuncle tubes between adjacent chambers ---
    siphuncle_d = 0.20;  // 20cm diameter siphuncle pipe

    for (i = [0 : n_chambers - 2]) {
        // Edge of chamber i (toward chamber i+1)
        ci = [spiral_x(i), 0, spiral_y(i)];
        cn = [spiral_x(i+1), 0, spiral_y(i+1)];

        // Direction vector from i to i+1
        dx = cn[0] - ci[0];
        dz = cn[2] - ci[2];
        dist = sqrt(dx*dx + dz*dz);
        ux = dx / max(dist, 0.001);
        uz = dz / max(dist, 0.001);

        // Siphuncle starts at edge of chamber i, ends at edge of chamber i+1
        ri = chamber_diameters[i] / 2;
        rn = chamber_diameters[i+1] / 2;

        start_pt = [ci[0] + ux * ri * 0.85, 0, ci[2] + uz * ri * 0.85];
        end_pt   = [cn[0] - ux * rn * 0.85, 0, cn[2] - uz * rn * 0.85];

        siphuncle_tube(start_pt, end_pt, siphuncle_d);
    }

    // --- Bulkheads at each connection point (on the older chamber's wall) ---
    for (i = [0 : n_chambers - 2]) {
        ci = [spiral_x(i), 0, spiral_y(i)];
        cn = [spiral_x(i+1), 0, spiral_y(i+1)];

        dx = cn[0] - ci[0];
        dz = cn[2] - ci[2];
        dist = sqrt(dx*dx + dz*dz);

        ri = chamber_diameters[i] / 2;

        // Bulkhead sits on the wall of chamber i facing chamber i+1
        bx = ci[0] + (dx / max(dist, 0.001)) * ri * 0.95;
        bz = ci[2] + (dz / max(dist, 0.001)) * ri * 0.95;

        // Angle the bulkhead to face the connection direction
        angle = atan2(dz, dx);

        translate([bx, 0, bz])
        rotate([0, -angle, 0])
        rotate([0, 0, 90])
        rotate([90, 0, 0])
            bulkhead(chamber_diameters[i] * 0.4, siphuncle_d);
    }

    // --- Mothership on top of the newest (outermost) chamber ---
    newest = n_chambers - 1;
    newest_r = chamber_diameters[newest] / 2;
    newest_cx = spiral_x(newest);
    newest_cy = spiral_y(newest);

    translate([newest_cx, 0, newest_cy + newest_r + 0.6])
        tiny_mothership();

    // --- Printer bots on the outermost shell surface ---
    for (i = [0 : 5]) {
        a1 = i * 55 + 10;
        a2 = i * 40 + 20;
        bx = newest_cx + newest_r * cos(a1) * cos(a2);
        by = max(0.1, newest_r * 0.5 * sin(a2));  // Keep on visible (cutaway) half
        bz = newest_cy + newest_r * sin(a1) * cos(a2);
        translate([bx, by, bz])
            tiny_bot();
    }

    // --- Concentrator mirrors around the outside of the station ---
    // Placed around the newest chamber at some distance
    mirror_dist = newest_r + 3.0;
    for (i = [0 : 5]) {
        a = i * 60 + 15;
        mx = newest_cx + mirror_dist * cos(a);
        mz = newest_cy + mirror_dist * sin(a);
        translate([mx, 0.5, mz])
        rotate([0, -a, -15])
            concentrator_mirror(2.0);
    }

    // --- Generation labels (colored dot indicators) ---
    // Gold dot on Gen 0
    color([1, 0.9, 0.3])
    translate([spiral_x(0), chamber_diameters[0] / 2 + 0.3, spiral_y(0)])
        sphere(d = 0.15);

    // Green dot on newest
    color([0.3, 0.9, 0.3])
    translate([spiral_x(newest), chamber_diameters[newest] / 2 + 0.3, spiral_y(newest)])
        sphere(d = 0.15);

    // --- Spiral trace line (thin curve showing the growth path) ---
    // Render as a series of small cylinders tracing the spiral
    color([0.4, 0.4, 0.4, 0.5])
    for (t = [0 : 5 : 360]) {
        theta_rad = t * PI / 180;
        max_theta = spiral_theta(n_chambers - 1);
        frac = theta_rad / max(max_theta, 0.01);
        if (frac <= 1.0) {
            r_here = (chamber_diameters[0]/2) * exp(spiral_b * theta_rad);
            r_next = (chamber_diameters[0]/2) * exp(spiral_b * (theta_rad + 5*PI/180));
            x1 = r_here * cos(t);
            z1 = r_here * sin(t);
            x2 = r_next * cos(t + 5);
            z2 = r_next * sin(t + 5);
            hull() {
                translate([x1, -0.05, z1]) sphere(d=0.06, $fn=8);
                translate([x2, -0.05, z2]) sphere(d=0.06, $fn=8);
            }
        }
    }
}


// === RENDER ===
scale(scale_factor * 1000)  // Convert to mm at chosen scale
    nautilus_station();


// === PRINT NOTES ===
// At 1:100 scale:
//   Gen 0 (Kapton vault): 20mm diameter sphere
//   Gen 1: 28mm diameter sphere
//   Gen 2: 45mm diameter sphere
//   Gen 3: 93mm diameter sphere
//   Gen 4 (newest): 140mm diameter sphere
//   Total footprint: ~200mm across (fits standard bed)
//
// Multi-color printing recommended:
//   Gold (Gen 0) = Kapton membrane original vault
//   Dark-to-bright gray = iron generations (darker = older)
//   Blue = mothership solar panels
//   Orange dots = WAAM printer bots
//   Translucent silver = concentrator mirrors
//   Gray trace = spiral growth path
//
// Key difference from previous model:
//   Chambers are ADJACENT along a logarithmic spiral, NOT nested.
//   Like a real nautilus shell cross-section, each generation is a
//   separate sphere positioned next to the previous one, connected
//   by siphuncle tubes. Retired chambers are sealed by bulkheads.
//
// Print orientation: cutaway face down on build plate.
//   The flat cutaway plane provides a stable base.
//   Supports needed for siphuncle tubes and mothership.
//
// Assembly option: print each chamber separately and glue.
//   This allows different filament colors per generation.
//   Siphuncle tubes print as small cylinders (superglue to attach).
