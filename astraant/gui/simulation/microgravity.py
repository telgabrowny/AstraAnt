"""Microgravity locomotion model for ant movement in tunnels.

In near-zero gravity, ants don't walk — they grip and pull. Movement
is along surfaces (floor, walls, ceiling equally), using alternating
3-leg grip for traction. Debris floats. There is no "down."

This module provides movement physics and animation states for
realistic microgravity behavior in the close-up camera view.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum, auto


class GripState(Enum):
    """Which legs are gripping vs reaching."""
    TRIPOD_A = auto()    # Legs 1L, 2R, 3L gripping; 1R, 2L, 3R reaching
    TRIPOD_B = auto()    # Opposite set gripping
    ALL_GRIP = auto()    # All 6 legs anchored (working, bracing)
    FLOATING = auto()    # No grip — transitioning between surfaces
    DOCKED = auto()      # At tool dock or equipment


class Surface(Enum):
    """Which surface the ant is attached to in the cylindrical tunnel."""
    FLOOR = auto()       # Bottom (arbitrary convention)
    WALL_LEFT = auto()
    WALL_RIGHT = auto()
    CEILING = auto()
    EQUIPMENT = auto()   # Attached to a piece of infrastructure


@dataclass
class MicrogravityState:
    """Locomotion state for one ant in microgravity."""
    grip: GripState = GripState.ALL_GRIP
    surface: Surface = Surface.FLOOR
    surface_angle_deg: float = 0.0    # Position around the tunnel circumference (0=floor, 180=ceiling)
    tunnel_position_m: float = 0.0    # Distance along the tunnel from entrance
    movement_speed_m_per_s: float = 0.05  # Slower than Earth walking (~5 cm/s)
    grip_cycle_phase: float = 0.0     # 0-1 animation phase for grip alternation
    heading_sign: int = 1             # +1 = toward work face, -1 = toward entrance
    drift_velocity: list[float] = None  # [x,y,z] m/s when floating between surfaces

    def __post_init__(self):
        if self.drift_velocity is None:
            self.drift_velocity = [0, 0, 0]


def tick_locomotion(state: MicrogravityState, dt: float,
                    is_moving: bool = True, is_working: bool = False) -> dict:
    """Update microgravity locomotion state for one tick.

    Returns animation hints for the visual renderer.
    """
    animation = {
        "grip_state": state.grip.name,
        "surface": state.surface.name,
        "surface_angle": state.surface_angle_deg,
        "tunnel_pos": state.tunnel_position_m,
        "legs_gripping": [],      # Which legs are anchored
        "legs_reaching": [],      # Which legs are moving
        "debris_particles": 0,    # Floating debris from drilling
        "body_rotation": 0.0,     # Body orientation relative to surface
    }

    if is_working:
        # Anchored at work face — all legs grip, mandibles active
        state.grip = GripState.ALL_GRIP
        animation["legs_gripping"] = [0, 1, 2, 3, 4, 5]
        animation["legs_reaching"] = []
        # Drilling produces floating debris
        animation["debris_particles"] = random.randint(2, 8)
        return animation

    if not is_moving:
        # Stationary — all grip
        state.grip = GripState.ALL_GRIP
        animation["legs_gripping"] = [0, 1, 2, 3, 4, 5]
        return animation

    # Moving: alternating tripod grip-and-pull
    state.grip_cycle_phase = (state.grip_cycle_phase + dt * 2.0) % 1.0

    if state.grip_cycle_phase < 0.5:
        state.grip = GripState.TRIPOD_A
        animation["legs_gripping"] = [0, 3, 4]  # Front-L, Mid-R, Rear-L
        animation["legs_reaching"] = [1, 2, 5]  # Front-R, Mid-L, Rear-R
    else:
        state.grip = GripState.TRIPOD_B
        animation["legs_gripping"] = [1, 2, 5]
        animation["legs_reaching"] = [0, 3, 4]

    # Advance along tunnel
    state.tunnel_position_m += state.heading_sign * state.movement_speed_m_per_s * dt

    # Occasionally switch surfaces (ants use walls and ceiling too)
    if random.random() < 0.001:
        surfaces = [Surface.FLOOR, Surface.WALL_LEFT, Surface.WALL_RIGHT, Surface.CEILING]
        state.surface = random.choice(surfaces)
        state.surface_angle_deg = {
            Surface.FLOOR: 0,
            Surface.WALL_LEFT: 90,
            Surface.CEILING: 180,
            Surface.WALL_RIGHT: 270,
        }.get(state.surface, 0)

    animation["surface_angle"] = state.surface_angle_deg
    animation["tunnel_pos"] = state.tunnel_position_m

    return animation


def get_ant_visual_transform(micro_state: MicrogravityState,
                              tunnel_radius_m: float = 0.2) -> dict:
    """Convert microgravity state to visual position/rotation for rendering.

    Returns position and rotation that places the ant on the tunnel
    surface at the correct circumferential angle and distance along the tunnel.
    """
    angle_rad = math.radians(micro_state.surface_angle_deg)

    # Position on the tunnel wall (cylindrical coordinates -> cartesian)
    # Tunnel runs along Y axis, with X-Z being the cross-section
    x = tunnel_radius_m * math.sin(angle_rad)
    z = tunnel_radius_m * math.cos(angle_rad)
    y = -micro_state.tunnel_position_m  # Negative = deeper

    # Rotation: the ant's "up" points toward the tunnel center (inward)
    # This means ants on the ceiling are upside down (from an outside view)
    # but from the ant's perspective, they're always "standing" on a surface
    rotation_around_tunnel = micro_state.surface_angle_deg

    return {
        "position": [x, y, z],
        "rotation_deg": rotation_around_tunnel,
        "on_surface": micro_state.surface.name,
        "heading": micro_state.heading_sign,
    }


# Pre-made descriptions for the close-up camera narration
ACTIVITY_DESCRIPTIONS = {
    "DIGGING": [
        "Mandibles extend drill head into rock face. Body braced against torque.",
        "Drill bit spinning — fine regolith particles drift off the surface.",
        "Scooping debris into hopper. Material floats lazily in 5 kPa atmosphere.",
    ],
    "HAULING": [
        "Grip-pull locomotion along tunnel wall. Loaded hopper on back.",
        "Alternating tripod grip: three legs anchor, three reach forward.",
        "Passing another worker on the ceiling going the other direction.",
    ],
    "IDLE": [
        "All six legs anchored to wall surface. Mandibles folded. Waiting.",
        "Recharging from tunnel power tap. Tether connected.",
    ],
    "SORTING": [
        "At thermal drum station. Raking dried material with ceramic-tipped tool.",
        "Heat shimmer visible from the 120C drum. Ant keeps body clear of hot zone.",
    ],
    "PLASTERING": [
        "Mandibles squeeze paste nozzle — waste slurry extrudes onto tunnel wall.",
        "Trowel edge smooths the coating as the ant creeps forward along the surface.",
    ],
    "TENDING": [
        "Dipping sampling probe into bioreactor port. pH reading stabilizing.",
        "Checking turbidity — culture looks healthy. Moving to next vat.",
    ],
    "TOOL_SWAP": [
        "At tool dock. Mandibles release magnetic clip — drill head detaches.",
        "Picking up scoop head from dock. Magnetic click as it seats.",
    ],
}


def get_activity_description(state_name: str) -> str:
    """Get a random flavor text description for the close-up camera view."""
    descs = ACTIVITY_DESCRIPTIONS.get(state_name, ["Working..."])
    return random.choice(descs)
