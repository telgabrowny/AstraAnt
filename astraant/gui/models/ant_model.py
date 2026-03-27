"""Ant model builder — uses CAD-derived .obj models when available,
falls back to procedural primitives from Ursina when not.

This means the ants in the sim look exactly like what you'd 3D print,
using the same OpenSCAD source files.
"""

from __future__ import annotations

import math
from pathlib import Path

from ursina import Entity, Vec3, color, destroy

# Try to find compiled CAD models
_CAD_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"
_USE_CAD_MODELS = _CAD_MODELS_DIR.exists() and (_CAD_MODELS_DIR / "worker_chassis.obj").exists()


# Caste visual properties
CASTE_COLORS = {
    "worker": color.rgb(220, 160, 50),       # Orange/amber (mining role)
    "taskmaster": color.rgb(60, 160, 200),    # Blue/teal
    "surface_ant": color.rgb(200, 210, 200),  # Silver/white (hardened)
    "courier": color.rgb(200, 210, 200),      # Legacy alias for surface_ant
    # Worker role colors (same body, different tool = different indicator)
    "sorter": color.rgb(200, 100, 100),       # Rust red
    "plasterer": color.rgb(180, 180, 130),    # Khaki/clay
    "tender": color.rgb(140, 100, 200),       # Purple
}

CASTE_SCALES = {
    "worker": 1.0,
    "taskmaster": 1.3,
    "surface_ant": 1.5,
    "courier": 1.5,
    # Worker roles use worker scale
    "sorter": 1.0,
    "plasterer": 1.0,
    "tender": 1.0,
}


def create_ant_entity(caste: str = "worker", parent: Entity = None) -> Entity:
    """Create an ant entity, using CAD-derived models when available.

    If compiled .obj models exist (from OpenSCAD -> STL -> OBJ pipeline),
    uses those for accurate visual representation matching 3D-printable designs.
    Otherwise falls back to procedural primitives.

    Returns the root Entity. All parts are children.
    """
    # Try CAD model first
    cad_entity = _try_load_cad_model(caste, parent)
    if cad_entity is not None:
        return cad_entity

    # Fall back to procedural primitives
    scale = CASTE_SCALES.get(caste, 1.0)
    ant_color = CASTE_COLORS.get(caste, color.orange)
    body_length = 0.4 * scale  # Scene units

    # Root entity (empty transform)
    root = Entity(parent=parent)

    # -- Thorax (front body segment) --
    thorax = Entity(
        parent=root,
        model="sphere",
        color=ant_color,
        scale=Vec3(body_length * 0.5, body_length * 0.25, body_length * 0.35),
        position=Vec3(body_length * 0.15, 0, 0),
    )

    # -- Abdomen (rear body segment) --
    abdomen = Entity(
        parent=root,
        model="sphere",
        color=ant_color * 0.85,  # Slightly darker
        scale=Vec3(body_length * 0.45, body_length * 0.22, body_length * 0.32),
        position=Vec3(-body_length * 0.25, 0, 0),
    )

    # -- Head --
    head = Entity(
        parent=root,
        model="sphere",
        color=ant_color * 1.1,
        scale=Vec3(body_length * 0.18, body_length * 0.15, body_length * 0.18),
        position=Vec3(body_length * 0.45, body_length * 0.05, 0),
    )

    # -- Legs (6 total, 3 pairs) --
    leg_positions = [
        (0.25, "front"),
        (0.05, "mid"),
        (-0.15, "rear"),
    ]
    root._legs = []  # Store for animation

    for x_offset, pos_name in leg_positions:
        for side in (-1, 1):  # Left and right
            z_offset = side * body_length * 0.3

            # Upper leg (coxa + femur)
            upper = Entity(
                parent=root,
                model="cube",
                color=ant_color * 0.7,
                scale=Vec3(body_length * 0.04, body_length * 0.04, body_length * 0.25),
                position=Vec3(
                    body_length * x_offset,
                    -body_length * 0.05,
                    z_offset,
                ),
                rotation=Vec3(0, 0, side * 30),
            )

            # Lower leg (tibia)
            lower = Entity(
                parent=upper,
                model="cube",
                color=ant_color * 0.6,
                scale=Vec3(0.8, 0.8, 0.9),  # Relative to upper
                position=Vec3(0, 0, side * 0.5),
                rotation=Vec3(0, 0, side * 20),
            )

            # Foot (small sphere)
            foot = Entity(
                parent=lower,
                model="sphere",
                color=ant_color * 0.5,
                scale=Vec3(1.5, 1.5, 1.5),
                position=Vec3(0, 0, side * 0.5),
            )

            root._legs.append({
                "upper": upper,
                "lower": lower,
                "foot": foot,
                "side": side,
                "position": pos_name,
                "phase": 0.0 if pos_name in ("front", "rear") else math.pi,
            })

    # -- Mandible arms (all castes have these) --
    for side in (-1, 1):
        mandible = Entity(
            parent=root,
            model="cube",
            color=ant_color * 0.65,
            scale=Vec3(body_length * 0.15, body_length * 0.03, body_length * 0.03),
            position=Vec3(body_length * 0.5, -body_length * 0.05, side * body_length * 0.1),
            rotation=Vec3(0, side * 15, 0),
        )
        # Mandible tip (gripper pad)
        Entity(
            parent=mandible,
            model="sphere",
            color=ant_color * 0.5,
            scale=Vec3(0.3, 0.5, 0.5),
            position=Vec3(0.5, 0, 0),
        )

    # -- Caste-specific details --
    if caste in ("worker", "sorter", "plasterer", "tender"):
        # Hopper on abdomen (small box)
        Entity(
            parent=root,
            model="cube",
            color=color.rgb(100, 100, 100),
            scale=Vec3(body_length * 0.2, body_length * 0.15, body_length * 0.2),
            position=Vec3(-body_length * 0.25, body_length * 0.15, 0),
        )
        # Drill tool on front
        Entity(
            parent=root,
            model="cylinder",
            color=color.rgb(150, 150, 150),
            scale=Vec3(body_length * 0.05, body_length * 0.15, body_length * 0.05),
            position=Vec3(body_length * 0.55, 0, 0),
            rotation=Vec3(0, 0, 90),
        )

    elif caste == "taskmaster":
        # Sensor cluster on head (small spheres)
        for angle in [0, 120, 240]:
            rad = math.radians(angle)
            Entity(
                parent=head,
                model="sphere",
                color=color.rgb(50, 255, 50),  # Green sensor dots
                scale=Vec3(0.3, 0.3, 0.3),
                position=Vec3(0.6, 0.3 * math.sin(rad), 0.3 * math.cos(rad)),
            )
        # Tether attachment point (small cylinder at rear)
        Entity(
            parent=root,
            model="cylinder",
            color=color.rgb(80, 80, 80),
            scale=Vec3(body_length * 0.03, body_length * 0.05, body_length * 0.03),
            position=Vec3(-body_length * 0.5, 0, 0),
        )

    elif caste in ("courier", "surface_ant"):
        # Solar panel on back
        Entity(
            parent=root,
            model="quad",
            color=color.rgb(30, 30, 120),  # Dark blue
            scale=Vec3(body_length * 0.6, body_length * 0.4, 1),
            position=Vec3(0, body_length * 0.2, 0),
            rotation=Vec3(0, 0, 10),  # Slight angle
            double_sided=True,
        )
        # Folded sail (thin triangles at rear)
        Entity(
            parent=root,
            model="cube",
            color=color.rgb(200, 200, 200),  # Silver
            scale=Vec3(body_length * 0.02, body_length * 0.3, body_length * 0.15),
            position=Vec3(-body_length * 0.4, body_length * 0.1, 0),
        )

    # Store metadata
    root._caste = caste
    root._walk_time = 0.0

    return root


def animate_walk(ant: Entity, dt: float, speed: float = 1.0) -> None:
    """Animate the ant's tripod gait walk cycle.

    Call this each frame when the ant is moving.
    Uses alternating tripod gait (legs 1L,2R,3L move together, then 1R,2L,3R).
    """
    if not hasattr(ant, "_legs"):
        return

    ant._walk_time += dt * speed * 8.0  # Frequency

    for leg in ant._legs:
        # Tripod gait: alternate phase groups
        phase = ant._walk_time + leg["phase"]
        swing = math.sin(phase) * 15  # Degrees of rotation

        leg["upper"].rotation_z = leg["side"] * 30 + swing


def _try_load_cad_model(caste: str, parent: Entity = None) -> Entity | None:
    """Try to load a CAD-derived .obj model for this caste.

    Returns an Entity if successful, None to fall back to procedural.
    """
    if not _USE_CAD_MODELS:
        return None

    # Map caste to CAD model file
    model_map = {
        "worker": "worker_chassis",
        "sorter": "worker_chassis",       # Same body, different color
        "plasterer": "worker_chassis",
        "tender": "worker_chassis",
        "taskmaster": "worker_chassis",    # Same body with sensor cluster
        "surface_ant": "worker_chassis",   # Same body, different materials
        "courier": "worker_chassis",
    }

    model_name = model_map.get(caste, "worker_chassis")
    obj_path = _CAD_MODELS_DIR / f"{model_name}.obj"

    if not obj_path.exists():
        return None

    try:
        ant_color = CASTE_COLORS.get(caste, color.orange)
        scale = CASTE_SCALES.get(caste, 1.0)

        root = Entity(
            parent=parent,
            model=str(obj_path),
            color=ant_color,
            scale=0.01 * scale,  # OpenSCAD outputs in mm, Ursina in scene units
        )
        root._caste = caste
        root._walk_time = 0.0
        root._legs = []  # CAD models don't have animatable legs (yet)
        root._from_cad = True

        return root
    except Exception as e:
        print(f"Failed to load CAD model {obj_path}: {e}")
        return None
