"""Main Ursina application for AstraAnt 3D simulation.

The GUI is a pure observer of the headless SimEngine.
Each frame: engine.tick() -> sync visual entities to agent positions.
"""

from __future__ import annotations

import math
import random
from typing import Any

from ursina import (
    Ursina, Entity, Vec3, Vec2, camera, color, window,
    held_keys, time, Text, Button, EditorCamera,
    AmbientLight, DirectionalLight, input_handler,
)

from ..catalog import Catalog
from .models.asteroid_model import create_asteroid_entity, create_tunnel_visual
from .models.ant_model import create_ant_entity, animate_walk, CASTE_COLORS
from .simulation.sim_engine import SimEngine
from .simulation.ant_agent import AntState


# Map sim states to status indicator colors
STATE_COLORS = {
    AntState.IDLE: color.gray,
    AntState.MOVING: color.yellow,
    AntState.DIGGING: color.red,
    AntState.LOADING: color.orange,
    AntState.HAULING: color.rgb(200, 150, 50),
    AntState.DUMPING: color.green,
    AntState.RETURNING: color.cyan,
    AntState.SORTING: color.rgb(200, 100, 100),
    AntState.PLASTERING: color.rgb(180, 180, 130),
    AntState.TENDING: color.rgb(140, 100, 200),
    AntState.PATROLLING: color.rgb(60, 160, 200),
    AntState.SURFACE_OPS: color.rgb(160, 200, 160),
    AntState.FAILED: color.rgb(80, 0, 0),
}


class AstraAntApp:
    """The main 3D simulation application backed by SimEngine."""

    def __init__(self, asteroid_id: str = "bennu", workers: int = 20,
                 taskmasters: int = 1, surface_ants: int = 2,
                 track: str = "a"):
        self.asteroid_id = asteroid_id
        self.track = track

        self.catalog = Catalog()
        self.asteroid_data = self.catalog.get_asteroid(asteroid_id)
        self.asteroid_radius = 10.0

        # Headless simulation engine
        distance_au = 1.0
        if self.asteroid_data:
            distance_au = (self.asteroid_data
                           .get("orbit", {})
                           .get("semi_major_axis_au", 1.0))
        self.engine = SimEngine(
            workers=workers, taskmasters=taskmasters,
            surface_ants=surface_ants,
            track=track, asteroid_distance_au=distance_au,
        )

        # Visual entity map: agent.id -> Ursina Entity
        self.ant_entities: dict[int, Entity] = {}
        self.state_indicators: dict[int, Entity] = {}

        self.asteroid_entity: Entity = None
        self.asteroid_cutaway: Entity = None
        self.tunnel_visual: Entity = None
        self.cutaway_mode = False
        self._space_cooldown = 0.0
        self._c_cooldown = 0.0

    def setup_scene(self):
        """Create the 3D scene."""
        # Asteroid shape
        shape = "rubble_pile"
        if self.asteroid_data:
            name = self.asteroid_data.get("name", "")
            if "bennu" in name.lower():
                shape = "spinning_top"
            elif "itokawa" in name.lower():
                shape = "elongated"

        self.asteroid_entity = create_asteroid_entity(
            radius=self.asteroid_radius, subdivisions=4, shape=shape,
        )

        # Cutaway version (hidden initially)
        self.asteroid_cutaway = create_asteroid_entity(
            radius=self.asteroid_radius, subdivisions=4, shape=shape, cutaway=True,
        )
        self.asteroid_cutaway.visible = False

        # Tunnel visual (visible in cutaway mode)
        self.tunnel_visual = create_tunnel_visual(
            radius=self.asteroid_radius, tunnel_length=5.0, tunnel_diameter=0.4,
        )
        self.tunnel_visual.visible = False

        # Lighting
        DirectionalLight(direction=Vec3(1, -1, -0.5).normalized(),
                         color=color.rgb(255, 250, 240))
        AmbientLight(color=color.rgb(20, 20, 30))

        # Mothership at north pole
        ms_pos = Vec3(0, self.asteroid_radius * 1.05, 0)
        self.mothership = Entity(
            model="cube", color=color.rgb(180, 180, 180),
            scale=Vec3(0.8, 0.4, 0.6), position=ms_pos,
        )
        for side in (-1, 1):
            Entity(parent=self.mothership, model="quad",
                   color=color.rgb(30, 30, 130),
                   scale=Vec3(2.0, 0.05, 1.0),
                   position=Vec3(side * 1.5, 0.3, 0), double_sided=True)
        Entity(parent=self.mothership, model="cylinder",
               color=color.rgb(200, 200, 200),
               scale=Vec3(0.05, 0.8, 0.05), position=Vec3(0, 0.5, 0))

        # Tunnel entrance marker (dark circle below mothership)
        Entity(model="cylinder", color=color.rgb(30, 20, 15),
               scale=Vec3(0.4, 0.02, 0.4),
               position=Vec3(0, self.asteroid_radius * 1.01, 0))

        # Initialize simulation and spawn visual entities
        self.engine.setup()
        self._create_ant_visuals()

        # Starfield
        for _ in range(200):
            d = random.uniform(80, 150)
            t = random.uniform(0, math.pi * 2)
            p = random.uniform(0, math.pi)
            Entity(model="sphere", color=color.white,
                   scale=random.uniform(0.02, 0.08),
                   position=Vec3(d * math.sin(p) * math.cos(t),
                                 d * math.cos(p),
                                 d * math.sin(p) * math.sin(t)),
                   unlit=True)

    def _create_ant_visuals(self):
        """Create a visual Entity for each agent in the SimEngine."""
        for agent in self.engine.agents:
            entity = create_ant_entity(caste=agent.caste)
            # Place on asteroid surface
            pos = self._sim_to_surface(agent.position)
            entity.position = pos
            self.ant_entities[agent.id] = entity

            # State indicator (small sphere above ant)
            indicator = Entity(
                parent=entity, model="sphere",
                color=STATE_COLORS.get(agent.state, color.gray),
                scale=0.08, position=Vec3(0, 0.3, 0), unlit=True,
            )
            self.state_indicators[agent.id] = indicator

    def _sim_to_surface(self, sim_pos) -> Vec3:
        """Map a simulation position to the asteroid surface.

        Sim positions are in a small coordinate space. We project them
        onto the asteroid sphere surface for visual display.
        """
        # Use sim position as a direction vector from center
        x, y, z = sim_pos.x, sim_pos.y, sim_pos.z
        length = math.sqrt(x*x + y*y + z*z)
        if length < 0.01:
            # Default to near mothership
            return Vec3(0, self.asteroid_radius * 1.02, 0)

        # Normalize and project to surface
        scale = self.asteroid_radius * 1.02 / length
        return Vec3(x * scale, y * scale, z * scale)

    def setup_ui(self):
        """Create the UI overlay."""
        # Title bar
        self.title_text = Text(
            text=f"AstraAnt -- {self.asteroid_id.upper()} -- Track {self.track.upper()}",
            position=Vec2(-0.85, 0.48), scale=1.2, color=color.white,
        )

        # Left panel: swarm status
        self.swarm_text = Text(
            text="", position=Vec2(-0.85, 0.42), scale=0.8,
            color=color.light_gray,
        )

        # Right panel: production stats
        self.stats_text = Text(
            text="", position=Vec2(0.35, 0.42), scale=0.8,
            color=color.light_gray,
        )

        # Bottom left: mission clock and speed
        self.clock_text = Text(
            text="", position=Vec2(-0.85, -0.40), scale=1.0,
            color=color.white,
        )

        # Bottom center: comms delay
        self.comms_text = Text(
            text="", position=Vec2(-0.2, -0.40), scale=0.8,
            color=color.rgb(100, 200, 100),
        )

        # Ground control command buttons
        self._setup_ground_control()

        # Controls help
        Text(text="[Mouse] Orbit  [Scroll] Zoom  [1-5] Speed  [Space] Pause  [C] Cutaway",
             position=Vec2(-0.85, -0.47), scale=0.7, color=color.gray)

    def _setup_ground_control(self):
        """Create ground control command buttons."""
        self.gc_label = Text(
            text="-- GROUND CONTROL --",
            position=Vec2(0.35, -0.15), scale=0.9,
            color=color.rgb(100, 200, 100),
        )

        commands = [
            ("Build 10 Ants", {"type": "build_ants", "count": 10}),
            ("Build 50 Pods", {"type": "build_pods", "count": 50}),
            ("Retarget Mining", {"type": "retarget", "area": "sector_b"}),
            ("Emergency Stop", {"type": "emergency_stop"}),
        ]

        self.gc_buttons = []
        for i, (label, cmd) in enumerate(commands):
            btn = Button(
                text=label, scale=(0.18, 0.03),
                position=Vec2(0.45, -0.20 - i * 0.04),
                color=color.rgb(30, 60, 30),
                highlight_color=color.rgb(50, 100, 50),
            )
            btn._command_data = cmd
            btn.on_click = lambda b=btn: self._send_command(b._command_data)
            self.gc_buttons.append(btn)

        self.gc_status = Text(
            text="", position=Vec2(0.35, -0.38), scale=0.7,
            color=color.rgb(100, 200, 100),
        )

    def _send_command(self, command: dict):
        """Send a ground control command (enters delay queue)."""
        self.engine.send_player_command(command)
        delay = self.engine.comms.one_way_delay_minutes
        self.gc_status.text = (
            f"TRANSMITTING: {command['type']}  "
            f"(arrives in {delay:.1f} min)"
        )

    def update(self):
        """Called every frame by Ursina."""
        dt = time.dt

        # Speed controls
        if held_keys["1"]:
            self.engine.clock.speed = 1.0
        elif held_keys["2"]:
            self.engine.clock.speed = 10.0
        elif held_keys["3"]:
            self.engine.clock.speed = 100.0
        elif held_keys["4"]:
            self.engine.clock.speed = 1000.0
        elif held_keys["5"]:
            self.engine.clock.speed = 0.1

        # Pause toggle with debounce
        self._space_cooldown -= dt
        if held_keys["space"] and self._space_cooldown <= 0:
            self.engine.clock.toggle_pause()
            self._space_cooldown = 0.3

        # Cutaway toggle
        self._c_cooldown -= dt
        if held_keys["c"] and self._c_cooldown <= 0:
            self.cutaway_mode = not self.cutaway_mode
            self.asteroid_entity.visible = not self.cutaway_mode
            self.asteroid_cutaway.visible = self.cutaway_mode
            self.tunnel_visual.visible = self.cutaway_mode
            self._c_cooldown = 0.3

        # Tick simulation
        events = self.engine.tick(dt)

        # Spawn visual entities for any new agents (from manufacturing)
        for agent in self.engine.agents:
            if agent.id not in self.ant_entities:
                entity = create_ant_entity(caste=agent.caste)
                pos = self._sim_to_surface(agent.position)
                entity.position = pos
                self.ant_entities[agent.id] = entity
                indicator = Entity(
                    parent=entity, model="sphere",
                    color=STATE_COLORS.get(agent.state, color.gray),
                    scale=0.08, position=Vec3(0, 0.3, 0), unlit=True,
                )
                self.state_indicators[agent.id] = indicator

        # Sync visual entities to sim agents
        for agent in self.engine.agents:
            entity = self.ant_entities.get(agent.id)
            if entity is None:
                continue

            if agent.state == AntState.FAILED:
                # Grey out failed ants and stop animation
                entity.color = color.rgb(60, 60, 60)
                indicator = self.state_indicators.get(agent.id)
                if indicator:
                    indicator.color = STATE_COLORS[AntState.FAILED]
                continue

            # Map sim position to asteroid surface
            new_pos = self._sim_to_surface(agent.position)
            old_pos = entity.position

            # Move visual toward target (smoothed)
            entity.position = Vec3(
                old_pos.x + (new_pos.x - old_pos.x) * min(1.0, dt * 5),
                old_pos.y + (new_pos.y - old_pos.y) * min(1.0, dt * 5),
                old_pos.z + (new_pos.z - old_pos.z) * min(1.0, dt * 5),
            )

            # Face movement direction
            move_dir = entity.position - old_pos
            if move_dir.length() > 0.001:
                entity.look_at(entity.position + move_dir)

            # Animate legs when moving
            moving_states = {AntState.MOVING, AntState.HAULING, AntState.RETURNING,
                             AntState.PATROLLING, AntState.SURFACE_OPS}
            if agent.state in moving_states:
                animate_walk(entity, dt, speed=agent.speed)

            # Update state indicator color
            indicator = self.state_indicators.get(agent.id)
            if indicator:
                indicator.color = STATE_COLORS.get(agent.state, color.gray)

        # Rotate asteroid (both full and cutaway)
        if not self.engine.clock.paused:
            rot = 0.5 * (dt * self.engine.clock.speed)
            if self.asteroid_entity:
                self.asteroid_entity.rotation_y += rot
            if self.asteroid_cutaway:
                self.asteroid_cutaway.rotation_y += rot

        # Update tunnel visual length from sim state
        if self.tunnel_visual and self.cutaway_mode:
            tunnel_len = max(1.0, self.engine.tunnel.total_length_m / 10.0)  # Scale factor
            self.tunnel_visual.scale_y = tunnel_len / 2

        # Update UI text
        self._update_ui()

    def _update_ui(self):
        """Refresh all UI text from simulation state."""
        status = self.engine.status()

        # Clock and speed
        paused = " [PAUSED]" if status["paused"] else ""
        self.clock_text.text = (
            f"Mission: {status['clock']}  "
            f"Speed: {status['speed']}x{paused}"
        )

        # Swarm status
        lines = []
        for caste, counts in status["ants_by_caste"].items():
            failed_str = f" ({counts['failed']} failed)" if counts["failed"] > 0 else ""
            lines.append(f"  {caste:12s} {counts['active']}{failed_str}")
        self.swarm_text.text = "Swarm:\n" + "\n".join(lines)

        # Production stats
        s = status["stats"]
        t = status["tunnel"]
        metals = s.get('metals_extracted_kg', 0)
        biomass = s.get('biomass_g_per_l', 0)
        bio_line = f"\n  Metals:   {metals:.3f} kg\n  Biomass:  {biomass:.2f} g/L" if metals > 0 else ""

        m = status.get("manufacturing", {})
        mfg_line = ""
        if m.get("enabled"):
            mfg_line = (f"\n\nManufacturing:\n"
                        f"  Iron: {m['iron_stockpile_kg']:.1f}kg\n"
                        f"  Queue: {m['ants_queued']}  Build: {m['ants_in_progress']}\n"
                        f"  Built: {m['ants_completed']} ants\n"
                        f"  Pods:  {m['pods_completed']}")

        self.stats_text.text = (
            f"Production:\n"
            f"  Material: {s['material_kg']:.1f} kg\n"
            f"  Water:    {s['water_kg']:.1f} kg\n"
            f"  Sealed:   {s['sealed_m2']:.1f} m2\n"
            f"  Tunnel:   {t['total_length_m']:.1f} m{bio_line}\n"
            f"  Failures: {s['failures']}\n"
            f"  Ants:     {status['total_ants']}"
            f"{mfg_line}"
        )

        # Comms delay
        c = status["comms"]
        pending = ""
        if c["pending_commands"] > 0:
            pending = f"  [{c['pending_commands']} cmd in transit]"
        self.comms_text.text = (
            f"Earth delay: {c['delay_minutes']:.1f} min one-way{pending}"
        )

        # Check for arrived commands in recent events
        for event in self.engine.event_log[-5:]:
            if event.get("type") == "command_received":
                self.gc_status.text = (
                    f"CMD RECEIVED: {event['command'].get('type', '?')}"
                )


def run_app(asteroid: str = "bennu", workers: int = 20, taskmasters: int = 1,
            surface_ants: int = 2, track: str = "a"):
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
        surface_ants=surface_ants,
        track=track,
    )

    sim.setup_scene()
    sim.setup_ui()

    # Camera
    EditorCamera(rotation_smoothing=4, zoom_speed=2)
    camera.position = Vec3(0, 15, -25)
    camera.look_at(Vec3(0, 0, 0))

    def update():
        sim.update()

    import sys
    sys.modules[__name__].update = update

    app_instance.run()
