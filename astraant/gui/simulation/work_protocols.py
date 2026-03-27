"""Work protocols -- the exact command sequences between taskmaster and workers.

The worker ant is dumb on purpose. It executes simple commands and reports
sensor data. The taskmaster makes all decisions. This is safer -- a worker
with a stripped gear just stops. It doesn't try to "fix itself" and make
things worse.

Command vocabulary (taskmaster -> worker via nRF24L01):
  MOVE_TO <rail_position>     Walk along rail to this position
  DETACH_RAIL                 Release rail contact, go off-rail
  ATTACH_RAIL                 Re-engage rail contact
  DRILL <duration_ms>         Run drill motor for N milliseconds
  DRILL_STOP                  Immediately stop drill motor
  SCOOP                       Close mandibles on material
  DUMP_HOPPER                 Open hopper hatch, release material
  SWAP_TOOL <dock_id>         Go to dock, swap to specified tool head
  REPORT_STATUS               Send back: position, supercap%, hopper%, servo currents
  HALT                        Stop all movement immediately
  RETURN_TO_RAIL              Navigate back to nearest rail section

Status reports (worker -> taskmaster):
  HEARTBEAT                   Every 5 seconds: position, supercap%, state
  DRILL_DONE                  Drill command completed, hopper fill level
  STALL <servo_id>            Servo drawing high current, not moving
  SUPERCAP_LOW                Below 20% -- heading back to rail
  HOPPER_FULL                 Hopper at capacity
  TOOL_SEATED                 New tool head magnetically locked
  AT_POSITION <pos>           Arrived at commanded position
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkCommand:
    """A single command from taskmaster to worker."""
    command: str
    params: dict[str, Any] = field(default_factory=dict)
    issued_at: float = 0.0          # Sim time when issued
    completed_at: float = 0.0       # Sim time when worker confirmed
    status: str = "pending"         # pending, executing, completed, failed


def generate_drill_cycle_commands(
    worker_id: int,
    rail_position: float,        # Where on the rail the worker starts
    face_distance_m: float,      # Distance from rail end to rock face
    drill_duration_ms: int = 3000,  # How long to drill per burst
    n_bursts: int = 3,           # Number of drill bursts before hauling
) -> list[WorkCommand]:
    """Generate the complete command sequence for one drill-and-haul cycle.

    This is what the taskmaster actually sends to a worker to make it
    mine one hopper-load of material.
    """
    commands = []

    # Phase 1: TRANSIT TO WORK FACE
    commands.append(WorkCommand(
        command="MOVE_TO",
        params={"rail_position": rail_position,
                "description": "Ride rail to the work face area"},
    ))
    commands.append(WorkCommand(
        command="DETACH_RAIL",
        params={"description": "Release rail contact. Now on supercapacitor power."},
    ))
    commands.append(WorkCommand(
        command="MOVE_TO",
        params={"distance_m": face_distance_m, "surface": "floor",
                "description": f"Crawl {face_distance_m:.1f}m off-rail to rock face "
                               f"using grip-pull locomotion"},
    ))

    # Phase 2: DRILLING (multiple short bursts)
    for burst in range(n_bursts):
        commands.append(WorkCommand(
            command="DRILL",
            params={"duration_ms": drill_duration_ms, "burst": burst + 1,
                    "description": f"Drill burst {burst+1}/{n_bursts}: "
                                   f"motor on for {drill_duration_ms}ms. "
                                   f"Mandibles brace against torque. "
                                   f"Debris particles float off the face."},
        ))
        # After each burst, taskmaster checks worker status
        commands.append(WorkCommand(
            command="REPORT_STATUS",
            params={"check": "supercap_level, hopper_fill, servo_currents",
                    "description": "Taskmaster checks: enough power to continue? "
                                   "Hopper full yet? Any servo drawing excess current?"},
        ))
        # Scoop loose debris into hopper
        commands.append(WorkCommand(
            command="SCOOP",
            params={"description": "Mandibles close around floating debris, "
                                   "guide it into the hopper on the ant's back. "
                                   "In microgravity, debris drifts slowly -- "
                                   "the scoop catches it before it disperses."},
        ))

    # Phase 3: DECISION POINT
    # Taskmaster evaluates: hopper full? Supercap OK? Continue or haul?
    commands.append(WorkCommand(
        command="REPORT_STATUS",
        params={"decision": "haul_or_continue",
                "description": "Taskmaster decides based on hopper fill level "
                               "and supercap remaining: send worker to dump, "
                               "or squeeze in one more drill burst?"},
    ))

    # Phase 4: RETURN TO RAIL
    commands.append(WorkCommand(
        command="RETURN_TO_RAIL",
        params={"description": "Worker turns around (rotation in place -- "
                               "no room for U-turn in narrow tunnel). "
                               "Grip-pulls back to the rail. "
                               "Supercap recharging begins on contact."},
    ))
    commands.append(WorkCommand(
        command="ATTACH_RAIL",
        params={"description": "Spring-loaded brush engages rail. "
                               "Power flowing. Supercap charging. "
                               "Worker's status LED goes green."},
    ))

    # Phase 5: HAUL TO DUMP POINT
    commands.append(WorkCommand(
        command="MOVE_TO",
        params={"rail_position": 0, "destination": "dump_point",
                "description": "Ride rail back toward the mothership. "
                               "Loaded hopper adds mass -- worker moves slower "
                               "but rail provides unlimited power. "
                               "Passes other workers going the opposite direction "
                               "on the ceiling rail."},
    ))

    # Phase 6: DUMP
    commands.append(WorkCommand(
        command="DUMP_HOPPER",
        params={"target": "thermal_sorter_intake",
                "description": "At the dump point: worker positions over "
                               "the thermal sorter intake hopper. "
                               "Opens hopper hatch. Material falls (slowly, "
                               "in microgravity) into the intake. "
                               "Some particles drift -- a small fan guides them in."},
    ))

    # Phase 7: RETURN FOR NEXT CYCLE
    commands.append(WorkCommand(
        command="MOVE_TO",
        params={"rail_position": rail_position, "destination": "work_face",
                "description": "Ride rail back to the work face. "
                               "Empty hopper -- faster this time. "
                               "Supercap topped off en route. "
                               "Ready for the next drill cycle."},
    ))

    return commands


def generate_hauler_collection_commands(
    hauler_id: int,
    drill_worker_position: float,
) -> list[WorkCommand]:
    """If the drilling worker's hopper is full but there's still loose
    debris at the face, a SECOND worker (hauler) is sent to collect it.

    This happens when:
    - Driller's hopper is full but debris is still floating
    - Driller has a drill_head (can't scoop efficiently)
    - Hauler has scoop_head (designed for collection)
    """
    return [
        WorkCommand(
            command="SWAP_TOOL",
            params={"tool": "scoop_head", "dock_id": "nearest",
                    "description": "Hauler visits tool dock, swaps current tool "
                                   "for scoop head. Magnetic clip releases old tool, "
                                   "grabs scoop. 30 seconds at the dock."},
        ),
        WorkCommand(
            command="MOVE_TO",
            params={"rail_position": drill_worker_position,
                    "description": "Ride rail to the work face area"},
        ),
        WorkCommand(
            command="DETACH_RAIL",
            params={"description": "Go off-rail toward the debris field"},
        ),
        WorkCommand(
            command="SCOOP",
            params={"repeat": 8,
                    "description": "Scoop floating debris into hopper. "
                                   "8 scoops to fill hopper. Material drifts "
                                   "slowly in 5 kPa atmosphere -- scoop catches "
                                   "particles within ~30cm of the face."},
        ),
        WorkCommand(
            command="RETURN_TO_RAIL",
            params={"description": "Full hopper. Back to rail."},
        ),
        WorkCommand(
            command="MOVE_TO",
            params={"destination": "dump_point"},
        ),
        WorkCommand(
            command="DUMP_HOPPER",
            params={"target": "thermal_sorter_intake"},
        ),
    ]


# How does the taskmaster know when to tell the worker to stop drilling?
DRILL_STOP_CONDITIONS = {
    "hopper_full": {
        "trigger": "Worker reports HOPPER_FULL status",
        "detection": "Hopper has a simple weight sensor (strain gauge on the hinge). "
                     "When mass exceeds 180g (of 200g capacity), reports full.",
        "response": "Taskmaster sends DRILL_STOP, then RETURN_TO_RAIL.",
    },
    "supercap_low": {
        "trigger": "Worker reports SUPERCAP_LOW (below 20%)",
        "detection": "Supercapacitor voltage monitored by the RP2040 ADC. "
                     "Below 20% = ~1 minute of power remaining.",
        "response": "Taskmaster sends DRILL_STOP, RETURN_TO_RAIL immediately. "
                    "Worker has enough charge to make it back to the rail.",
    },
    "servo_stall": {
        "trigger": "Worker reports STALL on any servo",
        "detection": "Each servo's current draw is monitored via a shunt resistor. "
                     "High current + no position change = stall (gear stripped or jammed).",
        "response": "Taskmaster sends HALT, assesses severity. "
                    "If one leg servo: worker can limp back on 5 legs. "
                    "If mandible: can't hold drill. Send recovery worker.",
    },
    "commanded_stop": {
        "trigger": "Taskmaster decides the burst is done (timer elapsed)",
        "detection": "Taskmaster counts drill_duration_ms per burst. "
                     "Sends DRILL_STOP after each burst, checks status.",
        "response": "Worker stops drill, reports hopper fill level. "
                    "Taskmaster decides: another burst or haul?",
    },
    "obstacle_detected": {
        "trigger": "Worker's VL53L0x reads unexpected distance change",
        "detection": "If proximity sensor shows the face suddenly moved "
                     "closer (chunk broke off toward the ant) or farther "
                     "(hit a void/cavity in the rock).",
        "response": "Taskmaster sends DRILL_STOP. Evaluates: "
                    "void = interesting (possible vein entry). "
                    "Chunk = danger (debris floating toward ant).",
    },
}


def format_drill_cycle_narrative(commands: list[WorkCommand]) -> str:
    """Format a drill cycle as a human-readable narrative."""
    lines = []
    lines.append("DRILL CYCLE NARRATIVE")
    lines.append("=" * 60)
    lines.append("Taskmaster #TM -> Worker #W\n")

    for i, cmd in enumerate(commands, 1):
        lines.append(f"Step {i}: {cmd.command}")
        if cmd.params.get("description"):
            for line in cmd.params["description"].split(". "):
                if line.strip():
                    lines.append(f"  {line.strip()}.")
        lines.append("")

    lines.append("\nDRILL STOP CONDITIONS:")
    for name, info in DRILL_STOP_CONDITIONS.items():
        lines.append(f"  {name}: {info['trigger']}")
        lines.append(f"    How: {info['detection'][:70]}...")

    lines.append("=" * 60)
    return "\n".join(lines)
