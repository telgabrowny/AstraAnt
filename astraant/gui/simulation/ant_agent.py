"""Individual ant agent with state machine behavior.

Each ant has a position, state, and role-specific behavior.
The state machine runs headlessly — no dependency on Ursina.
The GUI layer reads agent state to update visuals.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class AntState(Enum):
    IDLE = auto()
    MOVING = auto()
    DIGGING = auto()
    LOADING = auto()
    HAULING = auto()
    DUMPING = auto()
    RETURNING = auto()
    SORTING = auto()        # Sorter: operating thermal drum
    PLASTERING = auto()     # Plasterer: applying wall paste
    TENDING = auto()        # Tender: monitoring bioreactors
    PATROLLING = auto()     # Taskmaster/Tender: walking a circuit
    SURFACE_OPS = auto()    # Courier: exterior work
    FAILED = auto()


@dataclass
class Position:
    """3D position on/in the asteroid."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def distance_to(self, other: Position) -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)

    def move_toward(self, target: Position, speed: float, dt: float) -> None:
        dist = self.distance_to(target)
        if dist < 0.01:
            return
        frac = min(1.0, speed * dt / dist)
        self.x += (target.x - self.x) * frac
        self.y += (target.y - self.y) * frac
        self.z += (target.z - self.z) * frac


@dataclass
class AntAgent:
    """A single ant with state machine behavior."""
    id: int
    caste: str                          # worker, taskmaster, courier, sorter, plasterer, tender
    position: Position = field(default_factory=Position)
    state: AntState = AntState.IDLE
    health: float = 1.0                 # 0.0 = dead, 1.0 = perfect
    cargo_g: float = 0.0               # Current cargo load
    max_cargo_g: float = 200.0
    speed: float = 0.3                  # Units per second
    power_level: float = 1.0           # 0.0 = dead battery, 1.0 = full

    # State machine internals
    _state_timer: float = 0.0
    _target: Position = field(default_factory=Position)
    _assigned_segment_id: int = 0
    _cycle_count: int = 0

    # Degradation
    hours_operated: float = 0.0
    mtbf_hours: float = 8000.0         # Mean time between failures

    def tick(self, dt: float, tunnel=None) -> dict[str, Any]:
        """Advance the agent by dt seconds. Returns events dict."""
        events: dict[str, Any] = {}
        self.hours_operated += dt / 3600.0

        # Random failure based on MTBF
        if self.state != AntState.FAILED:
            failure_prob = dt / (self.mtbf_hours * 3600.0)
            if random.random() < failure_prob:
                self.state = AntState.FAILED
                self.health = 0.0
                events["failure"] = f"Ant {self.id} ({self.caste}) failed at {self.hours_operated:.0f}h"
                return events

        # Dispatch to caste-specific behavior
        if self.caste == "worker":
            events.update(self._tick_worker(dt, tunnel))
        elif self.caste == "taskmaster":
            events.update(self._tick_taskmaster(dt))
        elif self.caste == "sorter":
            events.update(self._tick_sorter(dt))
        elif self.caste == "plasterer":
            events.update(self._tick_plasterer(dt, tunnel))
        elif self.caste == "tender":
            events.update(self._tick_tender(dt))
        elif self.caste in ("courier", "surface_ant"):
            events.update(self._tick_courier(dt))

        return events

    def _tick_worker(self, dt: float, tunnel=None) -> dict[str, Any]:
        """Worker state machine: dig -> load -> haul -> dump -> return."""
        events: dict[str, Any] = {}

        if self.state == AntState.IDLE:
            self.state = AntState.MOVING
            self._state_timer = random.uniform(2.0, 5.0)  # Travel time to work face

        elif self.state == AntState.MOVING:
            self.position.move_toward(self._target, self.speed, dt)
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.DIGGING
                self._state_timer = random.uniform(5.0, 15.0)  # Dig time

        elif self.state == AntState.DIGGING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                # Excavated some material
                dig_amount_g = random.uniform(15, 25)  # Per dig cycle
                if tunnel:
                    tunnel.extend_tunnel(
                        self._assigned_segment_id,
                        amount_m=dig_amount_g / 2000.0,  # Rough: 2kg per meter
                        regolith_kg=dig_amount_g / 1000.0,
                    )
                self.state = AntState.LOADING
                self._state_timer = 2.0

        elif self.state == AntState.LOADING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.cargo_g = min(self.max_cargo_g, self.cargo_g + random.uniform(150, 200))
                self.state = AntState.HAULING
                self._state_timer = random.uniform(3.0, 8.0)  # Travel to dump

        elif self.state == AntState.HAULING:
            self.position.move_toward(self._target, self.speed * 0.7, dt)  # Slower with load
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.DUMPING
                self._state_timer = 2.0

        elif self.state == AntState.DUMPING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                events["material_dumped_g"] = self.cargo_g
                self.cargo_g = 0.0
                self._cycle_count += 1
                self.state = AntState.RETURNING
                self._state_timer = random.uniform(2.0, 5.0)

        elif self.state == AntState.RETURNING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.DIGGING
                self._state_timer = random.uniform(5.0, 15.0)

        return events

    def _tick_taskmaster(self, dt: float) -> dict[str, Any]:
        """Taskmaster: patrol, survey, monitor workers."""
        if self.state == AntState.IDLE:
            self.state = AntState.PATROLLING
            self._state_timer = random.uniform(20.0, 40.0)

        elif self.state == AntState.PATROLLING:
            self.position.move_toward(self._target, self.speed, dt)
            self._state_timer -= dt
            if self._state_timer <= 0:
                # Pick new patrol point
                self._target = Position(
                    random.uniform(-5, 5),
                    random.uniform(-5, 5),
                    random.uniform(-5, 5),
                )
                self._state_timer = random.uniform(20.0, 40.0)

        return {}

    def _tick_sorter(self, dt: float) -> dict[str, Any]:
        """Sorter: load drum, monitor, rake output."""
        events: dict[str, Any] = {}

        if self.state == AntState.IDLE:
            self.state = AntState.SORTING
            self._state_timer = random.uniform(10.0, 20.0)  # One drum cycle

        elif self.state == AntState.SORTING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                events["drum_cycle_complete"] = True
                events["water_recovered_g"] = random.uniform(50, 100)  # Per drum load
                self._cycle_count += 1
                self._state_timer = random.uniform(10.0, 20.0)

        return events

    def _tick_plasterer(self, dt: float, tunnel=None) -> dict[str, Any]:
        """Plasterer: fill, traverse, apply, smooth."""
        events: dict[str, Any] = {}

        if self.state == AntState.IDLE:
            self.state = AntState.LOADING  # Fill paste reservoir
            self._state_timer = 3.0

        elif self.state == AntState.LOADING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.cargo_g = 150  # Paste reservoir full
                self.state = AntState.MOVING
                self._state_timer = random.uniform(3.0, 8.0)

        elif self.state == AntState.MOVING:
            self.position.move_toward(self._target, self.speed, dt)
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.PLASTERING
                self._state_timer = random.uniform(8.0, 15.0)

        elif self.state == AntState.PLASTERING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                area_sealed = 0.3  # m^2 per reservoir load
                if tunnel:
                    tunnel.seal_segment(self._assigned_segment_id, quality=0.15)
                events["area_sealed_m2"] = area_sealed
                self.cargo_g = 0.0
                self._cycle_count += 1
                self.state = AntState.RETURNING
                self._state_timer = random.uniform(3.0, 8.0)

        elif self.state == AntState.RETURNING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.IDLE

        return events

    def _tick_tender(self, dt: float) -> dict[str, Any]:
        """Tender: patrol bioreactor vats, spot-check sensors."""
        events: dict[str, Any] = {}

        if self.state == AntState.IDLE:
            self.state = AntState.PATROLLING
            self._state_timer = random.uniform(30.0, 60.0)  # Patrol interval

        elif self.state == AntState.PATROLLING:
            self.position.move_toward(self._target, self.speed * 0.5, dt)
            self._state_timer -= dt
            if self._state_timer <= 0:
                self.state = AntState.TENDING
                self._state_timer = random.uniform(5.0, 10.0)

        elif self.state == AntState.TENDING:
            self._state_timer -= dt
            if self._state_timer <= 0:
                events["vat_checked"] = True
                # Small chance of detecting an anomaly
                if random.random() < 0.02:
                    events["anomaly_detected"] = "pH drift detected in vat"
                self._cycle_count += 1
                self.state = AntState.PATROLLING
                self._target = Position(
                    random.uniform(-3, 3),
                    random.uniform(-3, 3),
                    random.uniform(-3, 3),
                )
                self._state_timer = random.uniform(30.0, 60.0)

        return events

    def _tick_courier(self, dt: float) -> dict[str, Any]:
        """Courier: surface operations, cargo staging, maintenance."""
        if self.state == AntState.IDLE:
            self.state = AntState.SURFACE_OPS
            self._state_timer = random.uniform(20.0, 60.0)

        elif self.state == AntState.SURFACE_OPS:
            self.position.move_toward(self._target, self.speed * 0.8, dt)
            self._state_timer -= dt
            if self._state_timer <= 0:
                self._target = Position(
                    random.uniform(-8, 8),
                    random.uniform(8, 12),  # Surface level
                    random.uniform(-8, 8),
                )
                self._state_timer = random.uniform(20.0, 60.0)

        return {}
