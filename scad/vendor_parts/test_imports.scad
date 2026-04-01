// Test: verify all vendor STL files import correctly
// Open this in OpenSCAD and press F5 to preview

// SG90 Servo
translate([0, 0, 0]) color([0.2, 0.4, 0.8])
  import("sg90.stl");

// ESP32-S3
translate([40, 0, 0]) color([0.1, 0.5, 0.15])
  import("esp32_s3.stl");

// RP2040 Pico
translate([80, 0, 0]) color([0.1, 0.6, 0.2])
  import("rp2040_pico.stl");

// Peristaltic Pump
translate([0, 60, 0]) color([0.5, 0.5, 0.55])
  import("peristaltic_pump.stl");

// ANTS Antenna
translate([40, 60, 0]) color([0.7, 0.7, 0.72])
  import("ants_antenna.stl");

// Solar Clips Cover
translate([80, 60, 0]) color([0.15, 0.3, 0.75])
  import("solar_clips_cover.stl");
