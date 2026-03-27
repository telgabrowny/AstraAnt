"""Equipment installation pipeline -- nothing is instant.

Every piece of equipment goes through a multi-step installation process.
Each step requires specific workers/humanoids, takes real time, and
can fail or stall if prerequisites aren't met.

The sim tracks installation state per item. The GUI shows progress.
The player can watch workers hauling equipment through tunnels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class InstallState(Enum):
    STOWED = auto()          # In cargo container, not yet unpacked
    UNPACKED = auto()        # Removed from container, sitting loose
    ON_RAIL = auto()         # Mounted on guide rail, being transported
    IN_TRANSIT = auto()      # Moving through tunnel via winch
    AT_POSITION = auto()     # Arrived at destination, not yet mounted
    BOLTING = auto()         # Being bolted to wall/floor
    CONNECTING_POWER = auto()
    CONNECTING_FLUID = auto()
    TESTING = auto()         # Power-on self-test
    OPERATIONAL = auto()     # Running and producing
    FAILED_INSTALL = auto()  # Something went wrong during installation


@dataclass
class InstallStep:
    """One step in the installation process."""
    name: str
    description: str
    duration_hours: float
    workers_needed: int          # Worker ants with cargo_gripper
    humanoids_needed: int        # Figure 02 robots (0 for Phase 1 equipment)
    requires_power: bool         # Needs the power bus connected?
    requires_fluid: bool         # Needs fluid connections?
    can_fail: bool               # Can this step go wrong?
    failure_probability: float   # Chance of failure per attempt (0-1)
    failure_description: str     # What goes wrong


# Standard installation steps for mothership equipment
MOTHERSHIP_INSTALL_STEPS = [
    InstallStep(
        name="Remove launch restraints",
        description="Workers unbolt launch straps, remove foam packing, "
                    "disconnect pyrotechnic hold-down bolts.",
        duration_hours=0.5,
        workers_needed=2,
        humanoids_needed=0,
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.02,
        failure_description="Bolt seized from launch vibration. Worker applies penetrating oil. Retry in 1 hour.",
    ),
    InstallStep(
        name="Load onto guide rail",
        description="Workers slide equipment onto the inter-deck guide rail. "
                    "Attach cable clamp to equipment hard point.",
        duration_hours=0.25,
        workers_needed=3,
        humanoids_needed=0,
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.05,
        failure_description="Equipment won't seat on rail bearings. Worker files a burr. Retry.",
    ),
    InstallStep(
        name="Transport to position",
        description="Winch pulls equipment along guide rail to destination deck/location. "
                    "Workers walk alongside, monitoring. 1 m/min movement speed.",
        duration_hours=0.5,
        workers_needed=4,
        humanoids_needed=0,
        requires_power=True,           # Winch needs power
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.03,
        failure_description="Equipment snagged on tunnel junction. Workers reposition. 30 min delay.",
    ),
    InstallStep(
        name="Final positioning (screw jacks)",
        description="Workers use screw jack positioners to align equipment with "
                    "mounting bolt holes. Precision: +/- 2mm.",
        duration_hours=0.5,
        workers_needed=2,
        humanoids_needed=0,
        requires_power=False,
        requires_fluid=False,
        can_fail=False,
        failure_probability=0,
        failure_description="",
    ),
    InstallStep(
        name="Bolt to mounting surface",
        description="Workers with hex_torque_driver tool head drive mounting bolts "
                    "into pre-drilled holes in the rock wall / steel deck plate.",
        duration_hours=1.0,
        workers_needed=2,
        humanoids_needed=0,
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.05,
        failure_description="Bolt hole misaligned. Worker drills new hole with drill_head tool. +1 hour.",
    ),
    InstallStep(
        name="Connect power",
        description="Worker plugs XT60 power connector into the equipment's input. "
                    "Verifies LED indicator shows standby. Checks circuit breaker on PDU.",
        duration_hours=0.25,
        workers_needed=1,
        humanoids_needed=0,
        requires_power=True,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.02,
        failure_description="Circuit breaker trips on connection. Wiring fault. Worker inspects. +2 hours.",
    ),
    InstallStep(
        name="Connect fluid lines",
        description="Worker attaches quick-disconnect fluid fittings. "
                    "Water in, slurry in, leachate out as applicable. "
                    "Pressure test each connection.",
        duration_hours=0.5,
        workers_needed=1,
        humanoids_needed=0,
        requires_power=False,
        requires_fluid=True,
        can_fail=True,
        failure_probability=0.08,
        failure_description="Quick-disconnect leaks under pressure. Worker replaces O-ring from spares. +1 hour.",
    ),
    InstallStep(
        name="Power-on and self-test",
        description="Taskmaster sends power-on command. Equipment runs internal "
                    "diagnostics. Verify all sensors reading, motors responding, "
                    "fluid flowing. Commissioning complete.",
        duration_hours=0.5,
        workers_needed=0,
        humanoids_needed=0,
        requires_power=True,
        requires_fluid=True,
        can_fail=True,
        failure_probability=0.05,
        failure_description="Self-test failed: sensor not reading. Worker reseats connector. Retry.",
    ),
]

# Chamber installation steps (Phase 2 -- uses humanoid robots)
CHAMBER_INSTALL_STEPS = [
    InstallStep(
        name="Lower cargo container from surface",
        description="Surface ant detaches sealed container from mothership exterior. "
                    "Guides it into the tunnel entrance. Container slides along main rail.",
        duration_hours=1.0,
        workers_needed=0,
        humanoids_needed=0,            # Surface ant handles this
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.05,
        failure_description="Container snagged at tunnel entrance. Surface ant repositions. +30 min.",
    ),
    InstallStep(
        name="Unpack in chamber",
        description="Humanoid robots open container, remove packing material, "
                    "inspect equipment for shipping damage.",
        duration_hours=0.5,
        workers_needed=0,
        humanoids_needed=2,
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.02,
        failure_description="Minor shipping damage. Humanoid repairs dent with tools. +1 hour.",
    ),
    InstallStep(
        name="Mount on chamber guide rails",
        description="Humanoid attaches equipment to chamber-mounted guide rail system. "
                    "Chamber has pre-installed rails on all surfaces (floor, walls, ceiling).",
        duration_hours=0.5,
        workers_needed=0,
        humanoids_needed=2,
        requires_power=False,
        requires_fluid=False,
        can_fail=False,
        failure_probability=0,
        failure_description="",
    ),
    InstallStep(
        name="Position and bolt",
        description="Humanoid uses winch + screw jacks to position equipment. "
                    "Bolts to chamber wall at the player-selected location. "
                    "Verifies placement with level/alignment tool.",
        duration_hours=1.5,
        workers_needed=0,
        humanoids_needed=2,
        requires_power=False,
        requires_fluid=False,
        can_fail=True,
        failure_probability=0.03,
        failure_description="Wall anchor doesn't hold (loose regolith). Humanoid drills deeper. +1 hour.",
    ),
    InstallStep(
        name="Connect power + fluid + data",
        description="Humanoid connects XT60/XT90 power, quick-disconnect fluid lines, "
                    "and CAN bus data cable. Pressure tests fluid connections.",
        duration_hours=1.0,
        workers_needed=0,
        humanoids_needed=1,
        requires_power=True,
        requires_fluid=True,
        can_fail=True,
        failure_probability=0.1,
        failure_description="Fluid fitting leaks. Humanoid replaces gasket. +1 hour.",
    ),
    InstallStep(
        name="Commission and test",
        description="Power on, full self-test, verify all subsystems. "
                    "Run at reduced capacity for 1 hour to confirm stability.",
        duration_hours=1.0,
        workers_needed=0,
        humanoids_needed=1,
        requires_power=True,
        requires_fluid=True,
        can_fail=True,
        failure_probability=0.05,
        failure_description="Commissioning test failed. Humanoid troubleshoots wiring. +2 hours.",
    ),
]


@dataclass
class EquipmentInstallation:
    """Tracks the installation progress of one piece of equipment."""
    equipment_id: str
    equipment_name: str
    state: InstallState = InstallState.STOWED
    current_step: int = 0
    steps: list[InstallStep] = field(default_factory=list)
    step_timer_hours: float = 0.0
    total_time_hours: float = 0.0
    workers_assigned: int = 0
    humanoids_assigned: int = 0
    failure_count: int = 0
    log: list[str] = field(default_factory=list)

    def start(self, is_chamber: bool = False):
        """Begin the installation process."""
        self.steps = CHAMBER_INSTALL_STEPS[:] if is_chamber else MOTHERSHIP_INSTALL_STEPS[:]
        self.state = InstallState.UNPACKED
        self.current_step = 0
        self.step_timer_hours = 0
        self.log.append(f"Installation started: {self.equipment_name}")

    def tick(self, dt_hours: float, workers_available: int = 10,
             humanoids_available: int = 0, power_on: bool = True,
             fluid_connected: bool = True) -> dict[str, Any]:
        """Advance installation by dt_hours. Returns events."""
        import random

        if self.state == InstallState.OPERATIONAL:
            return {}
        if self.state == InstallState.STOWED:
            return {}
        if self.current_step >= len(self.steps):
            self.state = InstallState.OPERATIONAL
            self.log.append(f"INSTALLATION COMPLETE: {self.equipment_name} is operational!")
            return {"type": "install_complete", "equipment": self.equipment_id}

        step = self.steps[self.current_step]

        # Check prerequisites
        if step.workers_needed > workers_available:
            return {"type": "waiting", "reason": f"Need {step.workers_needed} workers, {workers_available} available"}
        if step.humanoids_needed > humanoids_available:
            return {"type": "waiting", "reason": f"Need {step.humanoids_needed} humanoids, {humanoids_available} available"}
        if step.requires_power and not power_on:
            return {"type": "waiting", "reason": "Waiting for power bus connection"}
        if step.requires_fluid and not fluid_connected:
            return {"type": "waiting", "reason": "Waiting for fluid connections"}

        # Advance the timer
        self.step_timer_hours += dt_hours
        self.total_time_hours += dt_hours

        if self.step_timer_hours >= step.duration_hours:
            # Step complete -- check for failure
            if step.can_fail and random.random() < step.failure_probability:
                self.failure_count += 1
                self.step_timer_hours = 0  # Retry
                self.log.append(f"STEP FAILED: {step.name} -- {step.failure_description}")
                return {
                    "type": "step_failed",
                    "step": step.name,
                    "description": step.failure_description,
                    "message": f"Installation setback: {step.failure_description}",
                }

            # Step succeeded
            self.log.append(f"Step complete: {step.name}")
            self.current_step += 1
            self.step_timer_hours = 0

            # Update state
            state_map = {
                1: InstallState.UNPACKED,
                2: InstallState.ON_RAIL,
                3: InstallState.IN_TRANSIT,
                4: InstallState.AT_POSITION,
                5: InstallState.BOLTING,
                6: InstallState.CONNECTING_POWER,
                7: InstallState.CONNECTING_FLUID,
                8: InstallState.TESTING,
            }
            self.state = state_map.get(self.current_step, InstallState.TESTING)

            if self.current_step >= len(self.steps):
                self.state = InstallState.OPERATIONAL
                self.log.append(f"INSTALLATION COMPLETE: {self.equipment_name} is operational!")
                return {"type": "install_complete", "equipment": self.equipment_id,
                        "message": f"{self.equipment_name} is now OPERATIONAL after {self.total_time_hours:.1f} hours"}

            return {
                "type": "step_complete",
                "step": step.name,
                "next_step": self.steps[self.current_step].name,
                "message": f"{self.equipment_name}: {step.name} done. Next: {self.steps[self.current_step].name}",
            }

        # Still working on current step
        progress = self.step_timer_hours / step.duration_hours * 100
        return {
            "type": "in_progress",
            "step": step.name,
            "progress_pct": round(progress, 0),
        }

    def summary(self) -> dict[str, Any]:
        total_steps = len(self.steps)
        return {
            "equipment": self.equipment_id,
            "state": self.state.name,
            "step": f"{self.current_step}/{total_steps}",
            "current_step_name": self.steps[self.current_step].name if self.current_step < total_steps else "complete",
            "total_time_hours": round(self.total_time_hours, 1),
            "failures": self.failure_count,
        }
