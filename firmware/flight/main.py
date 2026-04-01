"""AstraAnt Seed Mothership -- Main Mission Loop

Flight computer for the 41 kg seed mothership. Runs the mission
state machine from launch detection through autonomous operation.

State machine:
  LAUNCH_DETECT -> DEPLOY_PANELS -> TRANSIT -> APPROACH ->
  STATION_KEEP -> CAPTURE -> BIOLEACH -> ELECTROFORM ->
  WAAM_OPS -> GROWTH -> AUTONOMOUS

Each state delegates to the appropriate lib module. The main loop
runs at ~10 Hz (100ms tick), sends telemetry beacons every 30s,
and checks for ground commands continuously.

Safe mode: If anything critical fails (battery low, thermal limit,
repeated exceptions), the spacecraft enters sun-pointing mode with
beacon-only telemetry. Ground must explicitly command exit from
safe mode.

Target: ESP32-S3 with MicroPython
Flash:  mpremote connect /dev/ttyUSB0 cp -r firmware/flight/ :
"""

import machine
import time
import gc

# Boot.py has already run: config loaded, watchdog started, I2C/SPI init
from boot import CONFIG, wdt, i2c0, spi1, FORCE_SAFE_MODE, reboot_count

# Library modules
from lib import health
from lib import comms
from lib import adcs
from lib import navigator
from lib import capture
from lib import bioleach
from lib import waam

# ---------------------------------------------------------------------------
# Mission state codes
# ---------------------------------------------------------------------------
ST_LAUNCH_DETECT = 0
ST_DEPLOY_PANELS = 1
ST_TRANSIT = 2
ST_APPROACH = 3
ST_STATION_KEEP = 4
ST_CAPTURE = 5
ST_BIOLEACH = 6
ST_ELECTROFORM = 7
ST_WAAM_OPS = 8
ST_GROWTH = 9
ST_AUTONOMOUS = 10
ST_SAFE_MODE = 255

STATE_NAMES = {
    0: "LAUNCH_DETECT", 1: "DEPLOY_PANELS", 2: "TRANSIT",
    3: "APPROACH", 4: "STATION_KEEP", 5: "CAPTURE",
    6: "BIOLEACH", 7: "ELECTROFORM", 8: "WAAM_OPS",
    9: "GROWTH", 10: "AUTONOMOUS", 255: "SAFE_MODE",
}

# Control loop timing
TICK_MS = 100           # 10 Hz main loop
PROP_DT_S = 1.0         # Orbit propagation every 1 second
WAAM_DT_HR = 1.0 / 3600  # WAAM tick = 1 second in hours


def init_all():
    """Initialize all subsystem modules.

    Returns:
        Dict with all subsystem state objects.
    """
    modules = {}
    modules["health"] = health.init_health(CONFIG)
    modules["comms"] = comms.init_comms(CONFIG)
    modules["adcs"] = adcs.init_adcs(CONFIG)
    modules["nav"] = navigator.init_navigator(CONFIG)
    modules["capture"] = capture.init_capture(CONFIG)
    modules["bioleach"] = bioleach.init_bioleach(CONFIG)
    modules["waam"] = waam.init_waam(CONFIG)
    return modules


def enter_safe_mode(modules, reason):
    """Enter safe mode: sun-pointing, beacon-only, all actuators safe.

    Args:
        modules: Dict of all subsystem states.
        reason: String description of why safe mode was entered.
    """
    print("!!! SAFE MODE: %s" % reason)

    # Shut down all active subsystems safely
    try:
        adcs.safe_shutdown(modules["adcs"])
    except Exception:
        pass
    try:
        capture.safe_shutdown(modules["capture"])
    except Exception:
        pass
    try:
        bioleach.safe_shutdown(modules["bioleach"])
    except Exception:
        pass
    try:
        waam.safe_shutdown(modules["waam"])
    except Exception:
        pass

    # Send event notification
    try:
        comms.send_event(modules["comms"], 0xFF, "SAFE:%s" % reason[:48])
    except Exception:
        pass


def handle_state_transition(sm, modules, new_state):
    """Perform any actions needed when transitioning between states.

    Args:
        sm: State machine dict.
        modules: Dict of all subsystem states.
        new_state: Target state code.
    """
    old_state = sm["state"]
    if new_state == old_state:
        return

    print("STATE: %s -> %s" % (
        STATE_NAMES.get(old_state, "?"),
        STATE_NAMES.get(new_state, "?")))

    sm["state"] = new_state
    sm["state_entry_ms"] = time.ticks_ms()
    sm["state_ticks"] = 0

    # Send state transition event
    try:
        comms.send_event(modules["comms"], new_state,
                         "TRANSITION:%s->%s" % (
                             STATE_NAMES.get(old_state, "?"),
                             STATE_NAMES.get(new_state, "?")))
    except Exception:
        pass

    # State-specific entry actions
    if new_state == ST_SAFE_MODE:
        enter_safe_mode(modules, "commanded")

    elif new_state == ST_BIOLEACH:
        bioleach.start_bioleach(modules["bioleach"])

    elif new_state == ST_CAPTURE:
        # Capture must be armed by ground command first
        if not modules["capture"].get("armed", False):
            print("CAPTURE: not armed -- staying in current state")
            sm["state"] = old_state
            return


def tick_state(sm, modules):
    """Execute one tick of the current mission state.

    Args:
        sm: State machine dict.
        modules: Dict of all subsystem states.
    """
    state = sm["state"]
    sm["state_ticks"] += 1

    # ---- LAUNCH_DETECT ----
    if state == ST_LAUNCH_DETECT:
        # Detect launch by monitoring accelerometer spike then freefall.
        # Simplified: wait for stable power (solar panels still stowed
        # but battery is providing power from pre-launch charge).
        pwr = health.read_power(modules["health"])
        bat_soc = pwr.get("battery_soc", 0)
        if bat_soc > 20 or sm["state_ticks"] > 300:  # 30 seconds timeout
            handle_state_transition(sm, modules, ST_DEPLOY_PANELS)

    # ---- DEPLOY_PANELS ----
    elif state == ST_DEPLOY_PANELS:
        # First action after separation: deploy solar panels, detumble.
        # Step 1: Detumble (rate-damp all axes)
        detumbled = adcs.detumble(modules["adcs"], i2c0)

        if detumbled:
            # Step 2: Sun-point to start charging
            pointed = adcs.sun_point(modules["adcs"], i2c0)
            if pointed:
                # Check that solar power is flowing
                pwr = health.read_power(modules["health"])
                if pwr.get("solar_w", 0) > 10.0:  # >10W = panels deployed
                    handle_state_transition(sm, modules, ST_TRANSIT)
                elif sm["state_ticks"] > 6000:  # 10 minutes
                    # Panel deployment may have failed
                    enter_safe_mode(modules, "solar power not detected")
                    handle_state_transition(sm, modules, ST_SAFE_MODE)

    # ---- TRANSIT ----
    elif state == ST_TRANSIT:
        # Ion thruster spiral trajectory toward target.
        # Ground provides waypoints; onboard propagates between updates.
        nav = modules["nav"]

        # Compute thrust direction
        thrust_dir = navigator.compute_burn_direction(nav)
        nav["thrust_direction"] = thrust_dir
        nav["thrusting"] = True

        # Point spacecraft for thrust
        adcs.point_at_target(modules["adcs"], i2c0, thrust_dir)

        # Propagate orbit
        navigator.propagate_orbit(nav, PROP_DT_S)
        navigator.apply_thrust(nav, PROP_DT_S)

        # Check range to target
        dist = navigator.get_distance_to_target(nav)
        if dist >= 0 and dist < 100_000:  # Within 100 km
            nav["thrusting"] = False
            handle_state_transition(sm, modules, ST_APPROACH)

    # ---- APPROACH ----
    elif state == ST_APPROACH:
        nav = modules["nav"]
        nav["approach_phase"] = True

        # Low-thrust approach, ground-guided
        dist = navigator.get_distance_to_target(nav)
        thrust_dir = navigator.compute_burn_direction(nav)
        nav["thrust_direction"] = thrust_dir

        # Slow approach with intermittent thrust
        if dist > 1000:
            nav["thrusting"] = True
            navigator.apply_thrust(nav, PROP_DT_S)
        else:
            nav["thrusting"] = False

        adcs.point_at_target(modules["adcs"], i2c0, thrust_dir)
        navigator.propagate_orbit(nav, PROP_DT_S)

        if dist >= 0 and dist < 50:  # Within 50m
            handle_state_transition(sm, modules, ST_STATION_KEEP)

    # ---- STATION_KEEP ----
    elif state == ST_STATION_KEEP:
        # Hold position near asteroid, wait for capture command
        nav = modules["nav"]
        nav["thrusting"] = False
        navigator.propagate_orbit(nav, PROP_DT_S)

        # Maintain attitude
        adcs.sun_point(modules["adcs"], i2c0)

        # Transition to capture when armed by ground
        if sm.get("capture_armed", False):
            modules["capture"]["armed"] = True
            handle_state_transition(sm, modules, ST_CAPTURE)

    # ---- CAPTURE ----
    elif state == ST_CAPTURE:
        nav = modules["nav"]
        dist = navigator.get_distance_to_target(nav)
        nav_state = navigator.get_nav_summary(nav)

        cap_state = capture.tick_capture(
            modules["capture"], dist, nav_state)

        if cap_state == capture.CAP_DONE:
            handle_state_transition(sm, modules, ST_BIOLEACH)
        elif cap_state == capture.CAP_ABORT:
            reason = modules["capture"].get("abort_reason", "unknown")
            enter_safe_mode(modules, "capture abort: %s" % reason)
            handle_state_transition(sm, modules, ST_SAFE_MODE)

    # ---- BIOLEACH ----
    elif state == ST_BIOLEACH:
        temps = health.read_temperatures(modules["health"])
        bio_state = bioleach.tick_bioleach(modules["bioleach"], temps)

        # ADCS: sun-point for power
        adcs.sun_point(modules["adcs"], i2c0)

        # When bioleach transitions to ELECTROFORM, we advance
        if bio_state == bioleach.BIO_ELECTROFORM:
            handle_state_transition(sm, modules, ST_ELECTROFORM)

    # ---- ELECTROFORM ----
    elif state == ST_ELECTROFORM:
        temps = health.read_temperatures(modules["health"])
        bio_state = bioleach.tick_bioleach(modules["bioleach"], temps)

        # ADCS: sun-point for power
        adcs.sun_point(modules["adcs"], i2c0)

        # Wire production feeds WAAM inventory
        rate, metal = bioleach.wire_production_rate(modules["bioleach"])
        wire_kg = rate * (TICK_MS / 3_600_000.0) / 1000.0  # g/hr -> kg/tick
        waam.manage_wire_factory(modules["waam"], wire_kg)

        # When enough wire is stockpiled, start WAAM ops
        if modules["waam"]["wire_inventory_kg"] > 0.5:  # 500g minimum
            handle_state_transition(sm, modules, ST_WAAM_OPS)

    # ---- WAAM_OPS ----
    elif state == ST_WAAM_OPS:
        # Bioleaching + electroforming + WAAM all running in parallel
        temps = health.read_temperatures(modules["health"])
        bioleach.tick_bioleach(modules["bioleach"], temps)

        # Wire production
        rate, metal = bioleach.wire_production_rate(modules["bioleach"])
        wire_kg = rate * (TICK_MS / 3_600_000.0) / 1000.0
        waam.manage_wire_factory(modules["waam"], wire_kg)

        # WAAM printing
        pwr = health.read_power(modules["health"])
        available_kw = max(0, pwr.get("solar_w", 0) / 1000.0 - 0.2)  # Reserve 200W
        waam_result = waam.tick_waam(modules["waam"], WAAM_DT_HR, available_kw)

        if waam_result.get("completed"):
            print("WAAM: built %s" % waam_result["completed"])
            try:
                comms.send_event(modules["comms"], ST_WAAM_OPS,
                                 "BUILT:%s" % waam_result["completed"])
            except Exception:
                pass

        # ADCS: sun-point for power
        adcs.sun_point(modules["adcs"], i2c0)

        # Transition to GROWTH after Stirling is built
        if modules["waam"].get("stirling_built", False):
            handle_state_transition(sm, modules, ST_GROWTH)

    # ---- GROWTH ----
    elif state == ST_GROWTH:
        # Full autonomous growth: bioleach + electroform + WAAM
        # Building concentrators, bots, shell plates, eventually tugs
        temps = health.read_temperatures(modules["health"])
        bioleach.tick_bioleach(modules["bioleach"], temps)

        rate, metal = bioleach.wire_production_rate(modules["bioleach"])
        wire_kg = rate * (TICK_MS / 3_600_000.0) / 1000.0
        waam.manage_wire_factory(modules["waam"], wire_kg)

        pwr = health.read_power(modules["health"])
        available_kw = max(0, pwr.get("solar_w", 0) / 1000.0 - 0.2)
        waam.tick_waam(modules["waam"], WAAM_DT_HR, available_kw)

        # Manage bot fleet
        waam.manage_bot_fleet(modules["waam"])

        # ADCS: sun-point
        adcs.sun_point(modules["adcs"], i2c0)

        # Refresh build queue periodically
        if sm["state_ticks"] % 36000 == 0:  # Every hour
            waam.build_priority_queue(modules["waam"])

        # Transition to AUTONOMOUS after bot fleet > 5
        if modules["waam"].get("bot_count", 0) >= 5:
            handle_state_transition(sm, modules, ST_AUTONOMOUS)

    # ---- AUTONOMOUS ----
    elif state == ST_AUTONOMOUS:
        # Fully self-sustaining. All systems running.
        # Ground commands are optional at this point.
        temps = health.read_temperatures(modules["health"])
        bioleach.tick_bioleach(modules["bioleach"], temps)

        rate, metal = bioleach.wire_production_rate(modules["bioleach"])
        wire_kg = rate * (TICK_MS / 3_600_000.0) / 1000.0
        waam.manage_wire_factory(modules["waam"], wire_kg)

        pwr = health.read_power(modules["health"])
        available_kw = max(0, pwr.get("solar_w", 0) / 1000.0 - 0.2)
        waam.tick_waam(modules["waam"], WAAM_DT_HR, available_kw)
        waam.manage_bot_fleet(modules["waam"])

        adcs.sun_point(modules["adcs"], i2c0)

        # Periodic housekeeping
        if sm["state_ticks"] % 36000 == 0:
            waam.build_priority_queue(modules["waam"])
            gc.collect()

    # ---- SAFE_MODE ----
    elif state == ST_SAFE_MODE:
        # Sun-pointing + beacon only. All actuators off.
        adcs.sun_point(modules["adcs"], i2c0)
        # Everything else is shut down.
        # Only ground commands can exit safe mode.


def process_commands(sm, modules):
    """Check for and process ground commands.

    Args:
        sm: State machine dict.
        modules: Dict of all subsystem states.
    """
    cmd_pkt = comms.check_for_commands(modules["comms"])
    if cmd_pkt is None:
        return

    cmd = comms.decode_command(cmd_pkt)
    if cmd is None:
        return

    # Handle via comms module (dispatches to state machine flags)
    comms.handle_command(modules["comms"], cmd, sm)

    # Process state machine flags set by command handler
    if sm.get("requested_state") is not None:
        target = sm["requested_state"]
        sm["requested_state"] = None
        if target == 255:
            enter_safe_mode(modules, "ground command")
        handle_state_transition(sm, modules, target)

    if sm.get("abort_requested", False):
        sm["abort_requested"] = False
        enter_safe_mode(modules, "ground abort")
        handle_state_transition(sm, modules, ST_SAFE_MODE)

    if sm.get("status_requested", False):
        sm["status_requested"] = False
        hp = health.generate_health_packet(modules["health"])
        nav_sum = navigator.get_nav_summary(modules["nav"])
        cap_sum = capture.get_capture_summary(modules["capture"])
        comms.send_status_full(modules["comms"], sm["state"],
                                hp, nav_sum, cap_sum)

    if sm.get("rcs_command") is not None:
        thruster_id, dur_ms = sm["rcs_command"]
        sm["rcs_command"] = None
        adcs._fire_thruster(modules["adcs"], thruster_id, dur_ms)

    if sm.get("ewin_voltage") is not None:
        voltage = sm["ewin_voltage"]
        sm["ewin_voltage"] = None
        bioleach.run_electrowinning(modules["bioleach"], voltage)

    if sm.get("capture_armed", False):
        modules["capture"]["armed"] = True


def main():
    """Main entry point -- mission control loop."""
    print("AstraAnt Seed Mothership v%s" % CONFIG.get("firmware_version", "?"))
    print("Mission: %s -> %s" % (
        CONFIG.get("mission", "?"), CONFIG.get("target_asteroid", "?")))
    print("Initializing subsystems...")

    # Initialize all modules
    modules = init_all()
    print("  Health: OK")
    print("  Comms:  %s" % ("OK" if modules["comms"]["uart"] else "NO UART"))
    print("  ADCS:   %d sun sensors, %d RCS" % (
        len(modules["adcs"]["sun_adcs"]),
        len(modules["adcs"]["rcs_pins"])))
    print("  Nav:    dv_budget=%.0f m/s" % navigator.get_total_dv_remaining(modules["nav"]))
    print("  Capture: %d arm servos, %d grippers" % (
        len(modules["capture"]["arm_servos"]),
        len(modules["capture"]["gripper_servos"])))
    print("  Bioleach: heater=%s, pump=%s" % (
        "OK" if modules["bioleach"]["heater_pwm"] else "NONE",
        "OK" if modules["bioleach"]["pump_pwm"] else "NONE"))
    print("  WAAM: %d heads" % modules["waam"]["mothership_heads"])

    # State machine
    sm = {
        "state": ST_SAFE_MODE if FORCE_SAFE_MODE else ST_LAUNCH_DETECT,
        "state_entry_ms": time.ticks_ms(),
        "state_ticks": 0,
        "requested_state": None,
        "abort_requested": False,
        "status_requested": False,
        "capture_armed": False,
        "rcs_command": None,
        "param_update": None,
        "ewin_voltage": None,
        "exception_count": 0,
    }

    if FORCE_SAFE_MODE:
        print("*** FORCED SAFE MODE (reboot count: %d) ***" % reboot_count)
        enter_safe_mode(modules, "reboot limit (%d)" % reboot_count)

    print("Entering main loop at state: %s" % STATE_NAMES.get(sm["state"], "?"))
    print("")

    # Clear reboot counter on successful boot
    # (gets re-incremented by boot.py on next reboot)
    try:
        with open("reboot_count.dat", "w") as f:
            f.write("0")
    except Exception:
        pass

    # Main control loop
    while True:
        try:
            loop_start = time.ticks_ms()

            # Feed watchdog
            if wdt is not None:
                try:
                    wdt.feed()
                except Exception:
                    pass

            # 1. Check health limits
            ok, alerts = health.check_limits(modules["health"])
            if not ok and sm["state"] != ST_SAFE_MODE:
                # Critical alert -- enter safe mode
                alert_str = "|".join(alerts[:3])
                print("HEALTH ALERT: %s" % alert_str)
                sm["exception_count"] += 1
                if sm["exception_count"] >= 3:
                    enter_safe_mode(modules, "health: %s" % alert_str)
                    handle_state_transition(sm, modules, ST_SAFE_MODE)
            elif ok:
                sm["exception_count"] = max(0, sm["exception_count"] - 1)

            # 2. Process ground commands
            process_commands(sm, modules)

            # 3. Execute current state
            tick_state(sm, modules)

            # 4. Send telemetry beacon if due
            if comms.is_beacon_due(modules["comms"]):
                hp = health.generate_health_packet(modules["health"])
                comms.send_beacon(modules["comms"], sm["state"], hp)

            # 5. Periodic garbage collection (every 100 ticks = 10 seconds)
            if sm["state_ticks"] % 100 == 0:
                gc.collect()

            # Sleep to maintain tick rate
            elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
            if elapsed < TICK_MS:
                time.sleep_ms(TICK_MS - elapsed)

        except KeyboardInterrupt:
            print("Manual stop.")
            enter_safe_mode(modules, "keyboard interrupt")
            break

        except MemoryError:
            gc.collect()
            print("MEMORY ERROR -- forcing GC")
            sm["exception_count"] += 1
            if sm["exception_count"] >= 5:
                enter_safe_mode(modules, "memory")
                handle_state_transition(sm, modules, ST_SAFE_MODE)

        except Exception as e:
            print("MAIN LOOP ERROR: %s" % str(e))
            sm["exception_count"] += 1
            if sm["exception_count"] >= 5:
                enter_safe_mode(modules, "exceptions: %s" % str(e)[:32])
                handle_state_transition(sm, modules, ST_SAFE_MODE)
            time.sleep_ms(500)


if __name__ == "__main__":
    main()
