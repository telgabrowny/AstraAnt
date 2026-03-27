"""Main Ursina application for AstraAnt 3D simulation."""

from __future__ import annotations

import math
import random
from typing import Any

from ursina import (
    Ursina, Entity, Vec3, Vec2, camera, color, window, application,
    held_keys, time, Text, Button, Slider, EditorCamera,
    PointLight, AmbientLight, DirectionalLight,
)

from ..catalog import Catalog
from .models.asteroid_model import create_asteroid_entity
from .models.ant_model import create_ant_entity, animate_walk, CASTE_COLORS


class AstraAntApp:
    """The main 3D simulation application."""

    def __init__(self, asteroid_id: str = "bennu", workers: int = 20,
                 taskmasters: int = 1, couriers: int = 1, track: str = "a"):
        self.asteroid_id = asteroid_id
        self.num_workers = workers
        self.num_taskmasters = taskmasters
        self.num_couriers = couriers
        self.track = track

        self.catalog = Catalog()
        self.asteroid_data = self.catalog.get_asteroid(asteroid_id)

        self.ants: list[dict[str, Any]] = []
        self.asteroid_entity: Entity = None
        self.asteroid_radius = 10.0
        self.sim_speed = 1.0
        self.paused = False

    def setup_scene(self):
        """Create the 3D scene: asteroid, mothership, ants, lighting."""
        # Determine asteroid shape from data
        shape = "rubble_pile"
        if self.asteroid_data:
            spec_class = self.asteroid_data.get("physical", {}).get("spectral_class", "")
            name = self.asteroid_data.get("name", "")
            if "bennu" in name.lower():
                shape = "spinning_top"
            elif "itokawa" in name.lower():
                shape = "elongated"

        # Create asteroid
        self.asteroid_entity = create_asteroid_entity(
            radius=self.asteroid_radius,
            subdivisions=4,
            shape=shape,
        )

        # Lighting
        sun = DirectionalLight(
            direction=Vec3(1, -1, -0.5).normalized(),
            color=color.rgb(255, 250, 240),
        )
        sun.look_at(Vec3(0, 0, 0))

        ambient = AmbientLight(color=color.rgb(20, 20, 30))

        # Mothership on surface (simplified for Phase 1)
        # Place at "north pole" of asteroid
        ms_pos = Vec3(0, self.asteroid_radius * 1.05, 0)
        self.mothership = Entity(
            model="cube",
            color=color.rgb(180, 180, 180),
            scale=Vec3(0.8, 0.4, 0.6),
            position=ms_pos,
        )
        # Solar panels
        for side in (-1, 1):
            Entity(
                parent=self.mothership,
                model="quad",
                color=color.rgb(30, 30, 130),
                scale=Vec3(2.0, 0.05, 1.0),
                position=Vec3(side * 1.5, 0.3, 0),
                double_sided=True,
            )
        # Antenna
        Entity(
            parent=self.mothership,
            model="cylinder",
            color=color.rgb(200, 200, 200),
            scale=Vec3(0.05, 0.8, 0.05),
            position=Vec3(0, 0.5, 0),
        )

        # Spawn ants on the asteroid surface
        self._spawn_ants()

        # Starfield background (simple: scattered small dots)
        for _ in range(200):
            star_dist = random.uniform(80, 150)
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0, math.pi)
            Entity(
                model="sphere",
                color=color.white,
                scale=random.uniform(0.02, 0.08),
                position=Vec3(
                    star_dist * math.sin(phi) * math.cos(theta),
                    star_dist * math.cos(phi),
                    star_dist * math.sin(phi) * math.sin(theta),
                ),
                unlit=True,
            )

    def _spawn_ants(self):
        """Spawn ant entities on the asteroid surface."""
        def random_surface_point() -> tuple[Vec3, Vec3]:
            """Get a random point on the asteroid surface and its normal."""
            theta = random.uniform(0, math.pi * 2)
            phi = random.uniform(0.2, math.pi - 0.2)  # Avoid exact poles
            normal = Vec3(
                math.sin(phi) * math.cos(theta),
                math.cos(phi),
                math.sin(phi) * math.sin(theta),
            )
            pos = normal * (self.asteroid_radius * 1.02)  # Slightly above surface
            return pos, normal

        ant_configs = [
            ("worker", self.num_workers),
            ("taskmaster", self.num_taskmasters),
            ("courier", self.num_couriers),
        ]

        for caste, count in ant_configs:
            for _ in range(count):
                pos, normal = random_surface_point()
                ant_entity = create_ant_entity(caste=caste)
                ant_entity.position = pos
                # Orient ant to stand on surface (y-up aligned with surface normal)
                ant_entity.look_at(pos + Vec3(random.uniform(-1, 1), random.uniform(-1, 1),
                                              random.uniform(-1, 1)).normalized())

                # Random walk target (another point on the surface)
                target_pos, _ = random_surface_point()

                self.ants.append({
                    "entity": ant_entity,
                    "caste": caste,
                    "position": pos,
                    "target": target_pos,
                    "speed": random.uniform(0.3, 0.6),
                    "state": "moving",
                    "state_timer": 0.0,
                })

    def setup_ui(self):
        """Create the UI overlay."""
        # Title
        self.title_text = Text(
            text=f"AstraAnt -- {self.asteroid_id.upper()} -- Track {self.track.upper()}",
            position=Vec2(-0.85, 0.48),
            scale=1.2,
            color=color.white,
        )

        # Ant count display
        self.status_text = Text(
            text="",
            position=Vec2(-0.85, 0.43),
            scale=0.9,
            color=color.light_gray,
        )
        self._update_status_text()

        # Speed controls
        self.speed_text = Text(
            text="Speed: 1x",
            position=Vec2(0.55, 0.48),
            scale=1.0,
            color=color.white,
        )

        # Instructions
        Text(
            text="[Mouse] Orbit  [Scroll] Zoom  [1-5] Speed  [Space] Pause",
            position=Vec2(-0.85, -0.47),
            scale=0.8,
            color=color.gray,
        )

    def _update_status_text(self):
        workers = sum(1 for a in self.ants if a["caste"] == "worker")
        taskmasters = sum(1 for a in self.ants if a["caste"] == "taskmaster")
        couriers = sum(1 for a in self.ants if a["caste"] == "courier")
        self.status_text.text = (
            f"Workers: {workers}  Taskmasters: {taskmasters}  Couriers: {couriers}  "
            f"Total: {len(self.ants)}"
        )

    def update(self):
        """Called every frame by Ursina."""
        dt = time.dt

        # Speed controls (keyboard)
        if held_keys["1"]:
            self.sim_speed = 1.0
        elif held_keys["2"]:
            self.sim_speed = 10.0
        elif held_keys["3"]:
            self.sim_speed = 100.0
        elif held_keys["4"]:
            self.sim_speed = 1000.0
        elif held_keys["5"]:
            self.sim_speed = 0.1
        if held_keys["space"]:
            self.paused = not self.paused

        self.speed_text.text = f"Speed: {self.sim_speed}x" + (" [PAUSED]" if self.paused else "")

        if self.paused:
            return

        sim_dt = dt * self.sim_speed

        # Update ant positions — simple wander behavior for Phase 1
        for ant in self.ants:
            entity = ant["entity"]

            if ant["state"] == "moving":
                # Move toward target
                direction = (ant["target"] - entity.position).normalized()
                move = direction * ant["speed"] * sim_dt
                new_pos = entity.position + move

                # Keep on asteroid surface (project back to radius)
                dist = new_pos.length()
                if dist > 0:
                    new_pos = new_pos.normalized() * (self.asteroid_radius * 1.02)

                entity.position = new_pos

                # Face movement direction, aligned to surface
                if move.length() > 0.001:
                    entity.look_at(entity.position + direction)

                # Animate legs
                animate_walk(entity, dt, speed=ant["speed"])

                # Check if reached target
                if (entity.position - ant["target"]).length() < 0.5:
                    ant["state"] = "idle"
                    ant["state_timer"] = random.uniform(1.0, 3.0)

            elif ant["state"] == "idle":
                ant["state_timer"] -= sim_dt
                if ant["state_timer"] <= 0:
                    # Pick new target
                    theta = random.uniform(0, math.pi * 2)
                    phi = random.uniform(0.2, math.pi - 0.2)
                    normal = Vec3(
                        math.sin(phi) * math.cos(theta),
                        math.cos(phi),
                        math.sin(phi) * math.sin(theta),
                    )
                    ant["target"] = normal * (self.asteroid_radius * 1.02)
                    ant["state"] = "moving"

        # Slowly rotate asteroid (visual effect showing rotation period)
        if self.asteroid_entity:
            self.asteroid_entity.rotation_y += 0.5 * sim_dt


def run_app(asteroid: str = "bennu", workers: int = 20, taskmasters: int = 1,
            couriers: int = 1, track: str = "a"):
    """Launch the Ursina application."""
    app_instance = Ursina(
        title="AstraAnt -- Asteroid Mining Simulator",
        borderless=False,
        size=(1280, 720),
    )

    sim = AstraAntApp(
        asteroid_id=asteroid,
        workers=workers,
        taskmasters=taskmasters,
        couriers=couriers,
        track=track,
    )

    sim.setup_scene()
    sim.setup_ui()

    # Camera
    editor_cam = EditorCamera(rotation_smoothing=4, zoom_speed=2)
    camera.position = Vec3(0, 15, -25)
    camera.look_at(Vec3(0, 0, 0))

    # Wire up update
    def update():
        sim.update()

    # Ursina needs update in module scope
    import sys
    sys.modules[__name__].update = update

    app_instance.run()
