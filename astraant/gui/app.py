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
from .models.asteroid_model import (
    create_asteroid_entity, create_tunnel_visual, update_tunnel_visual_from_state,
)
from .models.ant_model import create_ant_entity, animate_walk, CASTE_COLORS
from .simulation.sim_engine import SimEngine
from .simulation.ant_agent import AntState
from .simulation.microgravity import get_activity_description
from .simulation.save_load import save_game, load_game, list_saves, AutoSaver


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
                 track: str = "mechanical"):
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

        # Camera modes: "orbit", "taskmaster", "mothership", "follow_ant"
        self.camera_mode = "orbit"
        self.followed_agent_id: int | None = None
        self._tab_cooldown = 0.0
        self._m_cooldown = 0.0
        self._save_cooldown = 0.0

        # Auto-save every 5 minutes of real time
        self.autosaver = AutoSaver(interval_seconds=300)

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

        # Loan shark debt display (the pressure)
        self.debt_text = Text(
            text="", position=Vec2(-0.85, 0.38), scale=0.9,
            color=color.rgb(255, 100, 100),
        )

        # Revenue counter (the relief)
        self.revenue_text = Text(
            text="Revenue: $0", position=Vec2(-0.85, 0.34), scale=1.0,
            color=color.rgb(50, 255, 50),
        )
        self.profit_text = Text(
            text="", position=Vec2(-0.85, 0.30), scale=0.8,
            color=color.rgb(200, 200, 50),
        )

        # Loan shark comment (tutorial/mood)
        self.shark_text = Text(
            text="", position=Vec2(-0.85, 0.26), scale=0.7,
            color=color.rgb(200, 180, 100),
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
        # Close-up narration (visible only in follow/taskmaster mode)
        self.narration_text = Text(
            text="", position=Vec2(-0.85, -0.30), scale=0.7,
            color=color.rgb(200, 200, 150),
        )
        self._narration_timer = 0.0

        # Camera mode indicator
        self.camera_mode_text = Text(
            text="View: ORBIT", position=Vec2(-0.3, 0.48), scale=1.0,
            color=color.rgb(200, 200, 255),
        )

        Text(text="[1-5] Speed [Space] Pause [C] Cutaway [Tab] Taskmaster [F] Follow [M] Mother [F5] Save [F9] Load",
             position=Vec2(-0.85, -0.47), scale=0.7, color=color.gray)

    def _setup_ground_control(self):
        """Create ground control command buttons."""
        self.gc_label = Text(
            text="-- GROUND CONTROL --",
            position=Vec2(0.35, -0.15), scale=0.9,
            color=color.rgb(100, 200, 100),
        )

        commands = [
            ("Prioritize Water", {"type": "prioritize", "metal": "water"}),
            ("Prioritize Copper", {"type": "prioritize", "metal": "copper"}),
            ("Prioritize PGMs", {"type": "prioritize", "metal": "platinum"}),
            ("Scan Area", {"type": "scan_area"}),
            ("Branch Tunnel", {"type": "branch_tunnel"}),
            ("Dig Deep (-50m)", {"type": "dig_toward", "x": 0, "y": -50, "z": 0}),
            ("Start Chamber", {"type": "set_chamber_goal", "radius_m": 8, "purpose": "ops hub"}),
            ("Build 10 Ants", {"type": "build_ants", "count": 10}),
            ("+4 Motherships", {"type": "add_motherships", "count": 4}),
            ("Set Endgame", {"type": "set_endgame_target", "radius_m": 224, "length_m": 200}),
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

        # Camera mode switching
        self._tab_cooldown -= dt
        self._m_cooldown -= dt
        if held_keys["tab"] and self._tab_cooldown <= 0:
            self._switch_to_taskmaster_view()
            self._tab_cooldown = 0.5
        if held_keys["m"] and self._m_cooldown <= 0:
            self._switch_to_mothership_view()
            self._m_cooldown = 0.5
        # Save/load (F5 = quicksave, F9 = quickload)
        self._save_cooldown -= dt
        if held_keys["f5"] and self._save_cooldown <= 0:
            path = save_game(self.engine, slot_name="quicksave")
            self.gc_status.text = f"SAVED: {path.name}"
            self.gc_status.color = color.rgb(100, 255, 100)
            self._save_cooldown = 1.0
        if held_keys["f9"] and self._save_cooldown <= 0:
            saves = list_saves()
            quicksaves = [s for s in saves if "quicksave" in s.get("slot_name", "")]
            if quicksaves:
                load_game(quicksaves[0]["path"], self.engine)
                self.gc_status.text = f"LOADED: {quicksaves[0]['filename']}"
                self.gc_status.color = color.rgb(100, 200, 255)
            else:
                self.gc_status.text = "No quicksave found"
            self._save_cooldown = 1.0

        # Auto-save check
        auto_path = self.autosaver.check(self.engine)
        if auto_path:
            self.gc_status.text = f"AUTO-SAVED: {auto_path.name}"
            self.gc_status.color = color.rgb(100, 200, 100)

        if held_keys["f"] and self._tab_cooldown <= 0:
            self._switch_to_follow_ant()
            self._tab_cooldown = 0.5
        if held_keys["escape"]:
            self._switch_to_orbit_view()

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

        # Update tunnel visual from sim state (every ~60 frames to save perf)
        if self.tunnel_visual and self.cutaway_mode:
            if not hasattr(self, '_tunnel_update_counter'):
                self._tunnel_update_counter = 0
            self._tunnel_update_counter += 1
            if self._tunnel_update_counter % 60 == 0:  # Every ~1 second at 60fps
                update_tunnel_visual_from_state(
                    self.tunnel_visual, self.engine.tunnel,
                    self.asteroid_radius, scale_factor=0.3,
                )

        # Camera follow mode
        if self.camera_mode in ("taskmaster", "follow_ant") and self.followed_agent_id is not None:
            entity = self.ant_entities.get(self.followed_agent_id)
            if entity:
                # Position camera behind and above the followed ant
                if self.camera_mode == "follow_ant":
                    offset = Vec3(-0.5, 0.5, -0.5)  # Very close for worker follow
                else:
                    offset = Vec3(-2, 2, -2)  # Farther back for taskmaster view
                camera.position = entity.position + offset
                camera.look_at(entity.position)

            # Update narration text for close-up view
            self._narration_timer -= dt
            if self._narration_timer <= 0 and self.camera_mode == "follow_ant":
                agent = None
                for a in self.engine.agents:
                    if a.id == self.followed_agent_id:
                        agent = a
                        break
                if agent:
                    state_map = {
                        AntState.DIGGING: "DIGGING",
                        AntState.LOADING: "DIGGING",
                        AntState.HAULING: "HAULING",
                        AntState.MOVING: "HAULING",
                        AntState.RETURNING: "HAULING",
                        AntState.IDLE: "IDLE",
                        AntState.SORTING: "SORTING",
                        AntState.PLASTERING: "PLASTERING",
                        AntState.TENDING: "TENDING",
                    }
                    state_key = state_map.get(agent.state, "IDLE")
                    desc = get_activity_description(state_key)
                    tool = agent._current_tool or "none"
                    self.narration_text.text = (
                        f"[{agent.caste} #{agent.id}] Tool: {tool}\n"
                        f"Surface: {'floor' if agent._surface_angle < 45 else 'wall' if agent._surface_angle < 135 else 'ceiling'}\n"
                        f"{desc}"
                    )
                    self._narration_timer = 3.0  # Update every 3 seconds
        else:
            self.narration_text.text = ""  # Hide narration in other modes

        # Update camera mode indicator
        mode_labels = {
            "orbit": "ORBIT (free camera)",
            "taskmaster": "TASKMASTER VIEW",
            "mothership": "MOTHERSHIP OVERVIEW",
            "follow_ant": "FOLLOWING ANT",
        }
        agent_info = ""
        if self.followed_agent_id is not None:
            for a in self.engine.agents:
                if a.id == self.followed_agent_id:
                    agent_info = f" -- {a.caste} #{a.id}"
                    break
        self.camera_mode_text.text = f"View: {mode_labels.get(self.camera_mode, '?')}{agent_info}"

        # Update UI text
        self._update_ui()

    def _switch_to_taskmaster_view(self):
        """Hop into a taskmaster's viewpoint. Tab cycles through taskmasters."""
        taskmasters = [a for a in self.engine.agents if a.caste == "taskmaster" and a.state != AntState.FAILED]
        if not taskmasters:
            return

        # Cycle to next taskmaster
        current_idx = -1
        if self.followed_agent_id is not None:
            for i, tm in enumerate(taskmasters):
                if tm.id == self.followed_agent_id:
                    current_idx = i
                    break
        next_idx = (current_idx + 1) % len(taskmasters)
        tm = taskmasters[next_idx]
        self.followed_agent_id = tm.id
        self.camera_mode = "taskmaster"

        # Highlight ONLY this taskmaster's squad members
        squad_ids = set(tm._squad_member_ids)
        for agent in self.engine.agents:
            indicator = self.state_indicators.get(agent.id)
            if indicator:
                if agent.id in squad_ids:
                    indicator.scale = 0.15  # Big — in this squad
                elif agent.id == tm.id:
                    indicator.scale = 0.20  # Biggest — the taskmaster itself
                else:
                    indicator.scale = 0.04  # Tiny — not in this squad

    def _switch_to_mothership_view(self):
        """High-level overview from above the mothership."""
        self.camera_mode = "mothership"
        self.followed_agent_id = None
        camera.position = Vec3(0, self.asteroid_radius * 2.5, -self.asteroid_radius * 0.5)
        camera.look_at(Vec3(0, 0, 0))
        # Reset indicator sizes
        for indicator in self.state_indicators.values():
            indicator.scale = 0.08

    def _switch_to_follow_ant(self):
        """Follow a random worker ant up close. F cycles through workers."""
        workers = [a for a in self.engine.agents
                   if a.caste in ("worker", "sorter", "plasterer", "tender")
                   and a.state != AntState.FAILED]
        if not workers:
            return

        current_idx = -1
        if self.followed_agent_id is not None:
            for i, w in enumerate(workers):
                if w.id == self.followed_agent_id:
                    current_idx = i
                    break
        next_idx = (current_idx + 1) % len(workers)
        self.followed_agent_id = workers[next_idx].id
        self.camera_mode = "follow_ant"

        # Reset all indicators
        for indicator in self.state_indicators.values():
            indicator.scale = 0.06
        # Enlarge the followed ant's indicator
        ind = self.state_indicators.get(self.followed_agent_id)
        if ind:
            ind.scale = 0.20

    def _switch_to_orbit_view(self):
        """Return to free orbit camera."""
        self.camera_mode = "orbit"
        self.followed_agent_id = None
        camera.position = Vec3(0, 15, -25)
        camera.look_at(Vec3(0, 0, 0))
        for indicator in self.state_indicators.values():
            indicator.scale = 0.08

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
                        f"  Built: {m['ants_completed']} ants")

        chamber_line = ""
        ch = t.get("common_chamber")
        if ch:
            chamber_line = (f"\n\nChamber:\n"
                            f"  {ch['completion_pct']:.1f}% ({ch['current_radius_m']:.1f}m)")

        # Endgame habitat progress
        eg = status.get("endgame")
        endgame_line = ""
        if eg:
            endgame_line = (f"\n\nHabitat Goal:\n"
                            f"  {eg['overall_progress_pct']:.3f}%\n"
                            f"  Sections: {eg['sections_complete']}/{eg['total_sections']}\n"
                            f"  Gravity: {eg['current_gravity_g']:.2f}g\n"
                            f"  Radius: {eg['current_radius_m']:.0f}m")

        fleet = status.get("fleet", {})
        fleet_line = ""
        if fleet.get("motherships", 1) > 1:
            fleet_line = f"\n\nFleet: {fleet['motherships']} motherships (x{fleet['multiplier']:.0f})"

        self.stats_text.text = (
            f"Tunnels:\n"
            f"  Length: {t['total_length_m']:.0f}m  Depth: {t.get('deepest_point_m', 0):.0f}m\n"
            f"  Segs: {t['segments']}  Branches: {t.get('branches', 0)}\n"
            f"Production:\n"
            f"  Material: {s['material_kg']:.1f} kg\n"
            f"  Water:    {s['water_kg']:.1f} kg{bio_line}\n"
            f"  Ants:     {status['total_ants']}  Failed: {s['failures']}"
            f"{mfg_line}{fleet_line}{chamber_line}{endgame_line}"
        )

        # Loan shark debt display
        loan = status.get("loan", {})
        if loan and not loan.get("paid_off"):
            balance = loan.get("balance", 0)
            rate = loan.get("rate", "?")
            mood = loan.get("mood", "neutral")
            if balance >= 1e6:
                self.debt_text.text = f"DEBT: ${balance/1e6:.1f}M ({rate} interest)"
            else:
                self.debt_text.text = f"DEBT: ${balance:,.0f}"
            mood_colors = {
                "nervous": color.rgb(255, 200, 50),
                "angry": color.rgb(255, 50, 50),
                "pleased": color.rgb(100, 255, 100),
                "ecstatic": color.rgb(50, 255, 50),
            }
            self.debt_text.color = mood_colors.get(mood, color.rgb(255, 150, 100))
        elif loan and loan.get("paid_off"):
            self.debt_text.text = "DEBT: PAID OFF!"
            self.debt_text.color = color.rgb(50, 255, 50)

        # Shark comment
        from .simulation.loan_shark import LoanShark
        self.shark_text.text = f'"{self.engine.loan_shark.get_shark_comment()}"'

        # Revenue and profit (gamification)
        mi = status.get("mining", {})
        rev = mi.get("revenue_usd", 0)
        if rev >= 1_000_000:
            self.revenue_text.text = f"Revenue: ${rev/1_000_000:.2f}M"
        elif rev >= 1_000:
            self.revenue_text.text = f"Revenue: ${rev/1_000:.0f}K"
        else:
            self.revenue_text.text = f"Revenue: ${rev:.0f}"

        if mi.get("profitable"):
            hrs = mi.get("time_to_profit", 0)
            days = hrs / 24
            self.profit_text.text = f"PROFITABLE at day {days:.0f}!"
            self.profit_text.color = color.rgb(50, 255, 50)
        else:
            cost = 3_000_000
            pct = min(100, rev / cost * 100) if cost > 0 else 0
            self.profit_text.text = f"Break-even: {pct:.1f}%  Priority: {mi.get('priority', 'balanced')}"

        # Comms delay
        c = status["comms"]
        pending = ""
        if c["pending_commands"] > 0:
            pending = f"  [{c['pending_commands']} cmd in transit]"
        self.comms_text.text = (
            f"Earth delay: {c['delay_minutes']:.1f} min one-way{pending}"
        )

        # Show important events in ground control status
        for event in self.engine.event_log[-10:]:
            etype = event.get("type", "")
            if etype == "command_received":
                self.gc_status.text = f"CMD RECEIVED: {event['command'].get('type', '?')}"
            elif etype == "zone_discovered":
                self.gc_status.text = event["message"]
                self.gc_status.color = color.rgb(255, 200, 50)
            elif etype == "profitable":
                self.gc_status.text = "*** MISSION PROFITABLE ***"
                self.gc_status.color = color.rgb(50, 255, 50)
            elif etype == "ant_built":
                self.gc_status.text = event["message"]
            elif etype == "priority_set":
                self.gc_status.text = event["message"]
            elif etype == "anomaly_found":
                self.gc_status.text = event["message"][:70]
                self.gc_status.color = color.rgb(255, 100, 100)
            elif etype == "fleet_expanded":
                self.gc_status.text = event["message"][:70]
            elif etype == "insufficient_funds":
                self.gc_status.text = event["message"][:70]
                self.gc_status.color = color.rgb(255, 50, 50)
            elif etype == "revenue":
                self.gc_status.text = event["message"][:70]
                self.gc_status.color = color.rgb(50, 255, 50)
            elif etype == "endgame_milestone":
                self.gc_status.text = event["message"][:70]
                self.gc_status.color = color.rgb(100, 200, 255)
            elif etype == "scan_result":
                self.gc_status.text = event["message"][:70]


def run_app(asteroid: str = "bennu", workers: int = 20, taskmasters: int = 1,
            surface_ants: int = 2, track: str = "mechanical"):
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
