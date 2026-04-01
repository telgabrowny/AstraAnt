"""WAAM wire factory and bot fleet management.

Manages the Wire Arc Additive Manufacturing pipeline:
  1. Electroforming produces metal wire from dissolved solution
  2. Wire is cut to lengths, coiled onto bobbins
  3. Bobbins are passed through the material airlock to exterior
  4. Printer bots consume wire to build structures via WAAM

Build priority queue (what to build first):
  1. Stirling engine (25 kg iron) -- unlocks unlimited power
  2. More printer bots (0.411 kg each) -- scales construction
  3. Solar concentrators (5 kg each) -- more heat for bioleaching
  4. Shell plates (2 kg each) -- armor over membrane

The mothership has 2 arm-mounted WAAM heads from launch. Printer
bots built later add more heads. Each head deposits 0.5 kg/hr
at 1.1 kW.

Bot fleet management: track active bots, assign tasks via UHF radio
to individual bots (same protocol as ant workers -- pack_command).
"""

import time


# -- Build priority codes --
BUILD_STIRLING = 0
BUILD_BOT = 1
BUILD_CONCENTRATOR = 2
BUILD_SHELL = 3
BUILD_TUG = 4
BUILD_CUSTOM = 5

BUILD_NAMES = {
    0: "STIRLING", 1: "BOT", 2: "CONCENTRATOR",
    3: "SHELL", 4: "TUG", 5: "CUSTOM",
}


def init_waam(cfg):
    """Initialize WAAM subsystem state.

    Args:
        cfg: Full mission config dict.

    Returns:
        Dict with WAAM pipeline state and fleet tracking.
    """
    waam_cfg = cfg.get("waam", {})

    return {
        # Wire production
        "wire_rate_kg_hr": waam_cfg.get("wire_rate_kg_per_hr", 0.5),
        "wire_inventory_kg": 0.0,
        "wire_consumed_kg": 0.0,
        "bobbin_count": 0,
        "bobbin_size_kg": 0.15,  # Each bobbin holds 150g of wire

        # WAAM heads
        "mothership_heads": 2,    # Built-in arm-mounted heads
        "power_per_head_kw": waam_cfg.get("power_per_head_kw", 1.1),
        "active_heads": 0,

        # Bot fleet
        "bot_mass_kg": waam_cfg.get("bot_mass_kg", 0.411),
        "bot_count": 0,
        "bots": {},  # bot_id -> {state, task, position, health}
        "next_bot_id": 1,

        # Build queue
        "build_queue": [],        # List of dicts: {type, kg_total, kg_done, priority}
        "current_build": None,

        # Infrastructure tracking
        "stirling_built": False,
        "stirling_iron_kg": waam_cfg.get("stirling_iron_kg", 25.0),
        "concentrators_built": 0,
        "concentrator_iron_kg": waam_cfg.get("concentrator_iron_kg", 5.0),
        "shell_plates_built": 0,
        "shell_plate_kg": waam_cfg.get("shell_plate_kg", 2.0),

        # Production stats
        "total_printed_kg": 0.0,
        "total_print_hours": 0.0,
    }


def manage_wire_factory(waam, wire_produced_kg):
    """Update wire inventory with new production from electroforming.

    Called periodically with the amount of wire produced since last call.

    Args:
        waam: WAAM state dict.
        wire_produced_kg: New wire mass produced (kg).

    Returns:
        Current wire inventory (kg).
    """
    waam["wire_inventory_kg"] += wire_produced_kg

    # Auto-spool into bobbins
    bobbin_size = waam.get("bobbin_size_kg", 0.15)
    while waam["wire_inventory_kg"] >= bobbin_size:
        # Don't consume, just count available bobbins
        waam["bobbin_count"] = int(waam["wire_inventory_kg"] / bobbin_size)
        break

    return waam["wire_inventory_kg"]


def build_priority_queue(waam):
    """Generate or refresh the build priority queue.

    Priority order:
      1. Stirling engine (if not built) -- 25 kg iron
      2. Printer bots -- 0.411 kg each, up to fleet capacity
      3. Solar concentrators -- 5 kg each
      4. Shell armor plates -- 2 kg each

    Args:
        waam: WAAM state dict.

    Returns:
        List of build task dicts, highest priority first.
    """
    queue = []

    # Priority 1: Stirling engine (the most important single build)
    if not waam.get("stirling_built", False):
        queue.append({
            "type": BUILD_STIRLING,
            "name": "Stirling engine",
            "kg_total": waam.get("stirling_iron_kg", 25.0),
            "kg_done": 0.0,
            "priority": 0,
        })

    # Priority 2: Printer bots (exponential growth)
    # Build new bots when wire supply can support another head
    wire_rate = waam.get("wire_rate_kg_hr", 0.5)
    current_demand = waam.get("active_heads", 0) * waam.get("wire_rate_kg_hr", 0.5)
    if wire_rate > current_demand:
        queue.append({
            "type": BUILD_BOT,
            "name": "Printer bot",
            "kg_total": waam.get("bot_mass_kg", 0.411),
            "kg_done": 0.0,
            "priority": 1,
        })

    # Priority 3: Solar concentrators
    queue.append({
        "type": BUILD_CONCENTRATOR,
        "name": "Solar concentrator",
        "kg_total": waam.get("concentrator_iron_kg", 5.0),
        "kg_done": 0.0,
        "priority": 2,
    })

    # Priority 4: Shell armor plates
    queue.append({
        "type": BUILD_SHELL,
        "name": "Shell armor plate",
        "kg_total": waam.get("shell_plate_kg", 2.0),
        "kg_done": 0.0,
        "priority": 3,
    })

    waam["build_queue"] = queue
    return queue


def tick_waam(waam, dt_hr, available_power_kw):
    """Advance WAAM operations by one tick.

    Consumes wire inventory to build the highest-priority item.
    Only prints if power is available for the active heads.

    Args:
        waam: WAAM state dict.
        dt_hr: Time step in hours.
        available_power_kw: Power budget available for WAAM (kW).

    Returns:
        Dict with tick results (what was printed, how much).
    """
    result = {
        "printed_kg": 0.0,
        "completed": None,
        "active_heads": 0,
    }

    # How many heads can we power?
    power_per_head = waam.get("power_per_head_kw", 1.1)
    max_heads = int(available_power_kw / power_per_head) if power_per_head > 0 else 0
    total_heads = waam.get("mothership_heads", 2) + waam.get("bot_count", 0)
    active = min(max_heads, total_heads)
    waam["active_heads"] = active
    result["active_heads"] = active

    if active <= 0 or dt_hr <= 0:
        return result

    # Ensure build queue exists
    if not waam.get("build_queue"):
        build_priority_queue(waam)

    # Get current build task
    queue = waam.get("build_queue", [])
    if not queue:
        return result

    task = queue[0]

    # Wire consumption: active_heads * rate * dt
    rate_kg_hr = waam.get("wire_rate_kg_hr", 0.5)
    wire_needed = active * rate_kg_hr * dt_hr
    wire_available = waam.get("wire_inventory_kg", 0.0)
    wire_used = min(wire_needed, wire_available)

    if wire_used <= 0:
        return result

    # Apply to current build
    task["kg_done"] = task.get("kg_done", 0.0) + wire_used
    waam["wire_inventory_kg"] -= wire_used
    waam["wire_consumed_kg"] += wire_used
    waam["total_printed_kg"] += wire_used
    waam["total_print_hours"] += dt_hr
    result["printed_kg"] = wire_used

    # Check if build is complete
    if task["kg_done"] >= task["kg_total"]:
        result["completed"] = task["name"]
        _complete_build(waam, task)
        queue.pop(0)

    return result


def _complete_build(waam, task):
    """Handle completion of a build task.

    Args:
        waam: WAAM state dict.
        task: Completed build task dict.
    """
    build_type = task.get("type", BUILD_CUSTOM)

    if build_type == BUILD_STIRLING:
        waam["stirling_built"] = True

    elif build_type == BUILD_BOT:
        bot_id = waam.get("next_bot_id", 1)
        waam["bots"][bot_id] = {
            "id": bot_id,
            "state": "IDLE",
            "task": None,
            "health": "OK",
            "built_ms": time.ticks_ms(),
        }
        waam["bot_count"] = len(waam["bots"])
        waam["next_bot_id"] = bot_id + 1

    elif build_type == BUILD_CONCENTRATOR:
        waam["concentrators_built"] += 1

    elif build_type == BUILD_SHELL:
        waam["shell_plates_built"] += 1


def manage_bot_fleet(waam):
    """Update bot fleet status and assign idle bots to tasks.

    Args:
        waam: WAAM state dict.

    Returns:
        Dict with fleet status summary.
    """
    bots = waam.get("bots", {})
    idle = 0
    printing = 0
    error = 0

    for bot_id, bot in bots.items():
        state = bot.get("state", "IDLE")
        if state == "IDLE":
            idle += 1
            # Auto-assign to WAAM printing if queue has work
            if waam.get("build_queue") and waam.get("wire_inventory_kg", 0) > 0:
                bot["state"] = "PRINTING"
                bot["task"] = "WAAM"
                printing += 1
                idle -= 1
        elif state == "PRINTING":
            printing += 1
        elif state == "ERROR":
            error += 1

    return {
        "total": len(bots),
        "idle": idle,
        "printing": printing,
        "error": error,
    }


def command_bot(waam, bot_id, task, params=None):
    """Send a task command to a specific printer bot.

    Args:
        waam: WAAM state dict.
        bot_id: Integer bot ID.
        task: Task string ("PRINT", "MOVE", "IDLE", "RETURN").
        params: Optional dict of task parameters.

    Returns:
        True if command was queued, False if bot not found.
    """
    bots = waam.get("bots", {})
    if bot_id not in bots:
        return False

    bot = bots[bot_id]
    bot["state"] = task
    bot["task"] = params if params else task
    return True


def get_waam_summary(waam):
    """Get WAAM subsystem summary for telemetry.

    Returns:
        Dict with production stats and fleet status.
    """
    fleet = manage_bot_fleet(waam)
    queue = waam.get("build_queue", [])
    current = queue[0]["name"] if queue else "NONE"

    return {
        "wire_inventory_kg": round(waam.get("wire_inventory_kg", 0.0), 3),
        "wire_consumed_kg": round(waam.get("wire_consumed_kg", 0.0), 3),
        "bobbin_count": waam.get("bobbin_count", 0),
        "active_heads": waam.get("active_heads", 0),
        "total_heads": waam.get("mothership_heads", 2) + waam.get("bot_count", 0),
        "total_printed_kg": round(waam.get("total_printed_kg", 0.0), 3),
        "total_print_hours": round(waam.get("total_print_hours", 0.0), 1),
        "stirling_built": waam.get("stirling_built", False),
        "concentrators": waam.get("concentrators_built", 0),
        "shell_plates": waam.get("shell_plates_built", 0),
        "bot_fleet": fleet,
        "current_build": current,
        "queue_depth": len(queue),
    }


def safe_shutdown(waam):
    """Emergency shutdown: stop all WAAM heads, idle all bots."""
    waam["active_heads"] = 0
    for bot_id, bot in waam.get("bots", {}).items():
        bot["state"] = "IDLE"
        bot["task"] = None
