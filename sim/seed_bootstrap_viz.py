"""Seed Bootstrap Visualization -- 'Garbage Bag to Space Station'.

Animated Ursina 3D visualization of the bootstrap sequence.
Controls: SPACE=next phase, R=restart, ESC=quit, Mouse=orbit/zoom

Run: python sim/seed_bootstrap_viz.py
"""

from __future__ import annotations
import math
import random
import sys

from ursina import (
    Ursina, Entity, Vec3, camera, color, window,
    held_keys, time, Text, EditorCamera, destroy,
)
from panda3d.core import VBase4


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
CLEAR_COLOR = VBase4(0.02, 0.02, 0.06, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def bright(r, g, b):
    """Create a bright color value."""
    return color.rgb(r, g, b)


def make_rock(pos=Vec3(0, 0, 0)):
    """Brown bumpy asteroid -- scale 3 for visibility."""
    root = Entity(position=pos)
    # Main body -- big and visible
    Entity(parent=root, model="sphere", color=bright(140, 110, 75),
           scale=3.0, unlit=True)
    # Bumps for texture
    for _ in range(14):
        d = Vec3(random.uniform(-1, 1), random.uniform(-1, 1),
                 random.uniform(-1, 1)).normalized() * random.uniform(1.0, 1.5)
        Entity(parent=root, model="sphere", color=bright(120, 95, 65),
               scale=random.uniform(0.5, 0.9), position=d, unlit=True)
    return root


def make_mothership(pos=Vec3(6, 2, 4)):
    """The seed mothership plug -- large enough to see clearly."""
    root = Entity(position=pos)

    # Main body (dark gray box)
    Entity(parent=root, model="cube", color=bright(100, 100, 110),
           scale=Vec3(1.0, 0.6, 0.6), unlit=True)

    # Solar wings (bright blue cubes)
    for side in (-1, 1):
        Entity(parent=root, model="cube", color=bright(40, 80, 220),
               scale=Vec3(0.08, 2.8, 1.2),
               position=Vec3(0, side * 1.8, 0), unlit=True)

    # Arms (light gray, angled out)
    root._arms = []
    for side in (-1, 1):
        arm = Entity(parent=root, model="cube", color=bright(180, 180, 190),
                     scale=Vec3(0.08, 0.08, 0.8),
                     position=Vec3(-0.15, 0, side * 0.6),
                     rotation=Vec3(0, 0, side * 25), unlit=True)
        # Gripper tip
        Entity(parent=arm, model="sphere", color=bright(220, 180, 50),
               scale=0.2, position=Vec3(0, 0, side * 0.8), unlit=True)
        root._arms.append(arm)

    # Ion engine (cyan glow at back)
    root._ion = Entity(parent=root, model="sphere", color=bright(80, 200, 255),
                       scale=0.18, position=Vec3(0.7, 0, 0), unlit=True)

    # Membrane bundle (golden lump underneath)
    root._bundle = Entity(parent=root, model="sphere", color=bright(220, 190, 60),
                          scale=Vec3(0.4, 0.2, 0.35),
                          position=Vec3(-0.3, -0.4, 0), unlit=True)

    return root


def make_bot(pos=Vec3(0, 0, 0), scale=0.2):
    """An orange printer bot on the shell surface."""
    root = Entity(position=pos)
    # Body (sphere)
    Entity(parent=root, model="sphere", color=bright(230, 170, 50),
           scale=Vec3(scale * 2.5, scale * 1.2, scale * 1.5), unlit=True)
    # 8 legs (small cubes)
    for i in range(8):
        angle = i * 45
        rad = math.radians(angle)
        lx = math.cos(rad) * scale * 1.8
        lz = math.sin(rad) * scale * 1.8
        Entity(parent=root, model="cube", color=bright(180, 130, 40),
               scale=Vec3(0.03, 0.03, scale * 1.0),
               position=Vec3(lx, -scale * 0.6, lz),
               rotation=Vec3(0, -angle, 45), unlit=True)
    # WAAM nozzle (red tip)
    Entity(parent=root, model="sphere", color=bright(255, 80, 50),
           scale=scale * 0.5, position=Vec3(scale * 1.8, 0, 0), unlit=True)
    return root


# ---------------------------------------------------------------------------
# Main Visualization
# ---------------------------------------------------------------------------
class BootstrapViz:

    PHASES = [
        ("Phase 0: The Seed",
         "41 kg | $654K | Carry-on suitcase",
         "A small spacecraft near a 2m asteroid fragment.\n"
         "Two solar wings. Two arms. A golden membrane. And bacteria."),

        ("Phase 1: Approach and Capture",
         "Ion engine: 3.3 km/s delta-V | Arms: 30cm reach",
         "Mothership approaches. Arms grip.\n"
         "Kapton membrane unfolds and wraps the rock."),

        ("Phase 2: Bioleaching",
         "90 days | Bacteria dissolve 855 kg iron",
         "Solar concentrator heats rock to 33C.\n"
         "Acid forms. Iron dissolves. Deposits on membrane walls."),

        ("Phase 3: Wire Factory",
         "544A | 14 kg/day iron wire",
         "Iron electroforms onto cathode wire inside the bag.\n"
         "Cut to length. Coiled. Passed through airlock."),

        ("Phase 4: First Printer Bots",
         "411g each | $9 of Earth parts",
         "WAAM printer bots built from asteroid iron.\n"
         "Magnetic feet grip the shell. Arc-melt wire. Print anything."),

        ("Phase 5: Shell Growth",
         "Year 1: 20 bots | 240 kg/day | Shell thickening",
         "Bot fleet multiplies. Next chamber built by WAAM.\n"
         "Concentrator mirrors expand. Power scales up."),

        ("Phase 6: Nautilus Station",
         "41 kg -> 12,000,000 tonnes | $654K -> $8.5 billion",
         "Each generation bigger than the last.\n"
         "The membrane is used once. Everything after is iron."),
    ]

    def __init__(self):
        self.phase = 0
        self.phase_time = 0.0
        self.space_cd = 0.0
        self.r_cd = 0.0

        self.rock = None
        self.mothership = None
        self.membrane = None
        self.iron_shell = None
        self.concentrator = None
        self.wire_segments = []
        self.bots = []
        self.bot_trails = []
        self.particles = []
        self.shells = []
        self._outer_shell = None
        self._mirrors = None

    def setup(self):
        # Rock at origin, scale=3
        self.rock = make_rock()

        # Mothership starts off to the side
        self.mothership = make_mothership(Vec3(10, 4, 7))

        # Membrane (starts hidden, will grow around rock)
        self.membrane = Entity(model="sphere", scale=0.01,
                               color=color.rgba(220, 190, 60, 100),
                               unlit=True, visible=False)

        # Iron shell (starts hidden)
        self.iron_shell = Entity(model="sphere", scale=0.01,
                                 color=color.rgba(180, 180, 195, 0),
                                 unlit=True, visible=False)

        # Concentrator mirror (starts hidden) -- use cube as flat panel
        self.concentrator = Entity(model="cube", scale=Vec3(1.5, 1.5, 0.05),
                                   color=bright(200, 210, 230),
                                   position=Vec3(5.0, 2.0, 0),
                                   rotation=Vec3(-20, -30, 0),
                                   double_sided=True, unlit=True,
                                   visible=False)

        # -- UI Text (yellow/green on dark background) --
        self.header_text = Text(
            text="AstraAnt -- Garbage Bag to Space Station",
            origin=(-0.5, 0), y=0.48, scale=1.0,
            color=color.rgb(150, 150, 180))
        self.title_text = Text(
            text="", origin=(-0.5, 0), y=0.44,
            scale=1.6, color=color.yellow)
        self.stats_text = Text(
            text="", origin=(-0.5, 0), y=0.39,
            scale=1.0, color=color.rgb(140, 220, 140))
        self.desc_text = Text(
            text="", origin=(-0.5, 0), y=0.33,
            scale=0.85, color=color.rgb(200, 200, 170))
        self.ctrl_text = Text(
            text="[SPACE] Next Phase   [R] Restart   [ESC] Quit   |   Mouse: orbit + zoom",
            origin=(-0.5, 0), y=-0.47, scale=0.7,
            color=color.rgb(180, 180, 120))

        self._go_phase(0)

    def _go_phase(self, n):
        self.phase = n
        self.phase_time = 0.0
        name, stats, desc = self.PHASES[n]
        self.title_text.text = name
        self.stats_text.text = stats
        self.desc_text.text = desc

        if n == 0:
            self._init_p0()
        elif n == 1:
            self._init_p1()
        elif n == 2:
            self._init_p2()
        elif n == 3:
            self._init_p3()
        elif n == 4:
            self._init_p4()
        elif n == 5:
            self._init_p5()
        elif n == 6:
            self._init_p6()

    # -- Phase initializers --

    def _init_p0(self):
        self.mothership.position = Vec3(10, 4, 7)
        self.mothership.visible = True
        self.mothership._ion.visible = True
        self.mothership._bundle.visible = True
        self.membrane.visible = False
        self.iron_shell.visible = False
        self.concentrator.visible = False
        self._clear_extras()
        self.rock.visible = True

    def _init_p1(self):
        self.membrane.visible = True
        self.membrane.scale = Vec3(0.01, 0.01, 0.01)
        self.membrane.color = color.rgba(220, 190, 60, 80)

    def _init_p2(self):
        self.concentrator.visible = True
        self.iron_shell.visible = True
        self.iron_shell.scale = Vec3(3.6, 3.6, 3.6)
        self.iron_shell.color = color.rgba(180, 180, 195, 0)
        # Floating yellow particles inside
        self._clear_particles()
        for _ in range(25):
            p = Entity(model="sphere", scale=random.uniform(0.06, 0.15),
                       color=bright(200, 200, 80),
                       position=Vec3(random.uniform(-1.0, 1.0),
                                     random.uniform(-1.0, 1.0),
                                     random.uniform(-1.0, 1.0)),
                       unlit=True)
            self.particles.append(p)

    def _init_p3(self):
        self._clear_particles()
        self.wire_segments = []

    def _init_p4(self):
        self._clear_bots()

    def _init_p5(self):
        pass  # builds on phase 4 state

    def _init_p6(self):
        self._clear_bots()
        self._clear_extras()
        self.membrane.visible = False
        self.iron_shell.visible = False
        self.concentrator.visible = False
        self.mothership.visible = False
        self.rock.visible = False

        # Build 5 spheres in a SPIRAL arrangement
        self.shells = []
        colors_list = [
            bright(160, 160, 175),
            bright(170, 175, 185),
            bright(180, 185, 195),
            bright(185, 190, 200),
            bright(200, 205, 220),
        ]
        for i, c in enumerate(colors_list):
            # Spiral: each sphere offset further along a spiral path
            angle = i * 72  # degrees apart
            rad = math.radians(angle)
            dist = i * 2.0  # increasing distance from center
            r = 1.2 + i * 0.8  # increasing radius
            pos = Vec3(math.cos(rad) * dist,
                       i * 0.8 - 1.5,
                       math.sin(rad) * dist)
            s = Entity(model="sphere", scale=r * 2,
                       color=color.rgba(
                           int(c.r * 255) if hasattr(c, 'r') and c.r <= 1.0 else 180,
                           int(c.g * 255) if hasattr(c, 'g') and c.g <= 1.0 else 190,
                           int(c.b * 255) if hasattr(c, 'b') and c.b <= 1.0 else 200,
                           80 + i * 20),
                       position=pos,
                       unlit=True, visible=False)
            self.shells.append(s)

    # -- Cleanup helpers --

    def _clear_particles(self):
        for p in self.particles:
            destroy(p)
        self.particles = []

    def _clear_bots(self):
        for b in self.bots:
            destroy(b)
        self.bots = []
        for t in self.bot_trails:
            destroy(t)
        self.bot_trails = []

    def _clear_extras(self):
        self._clear_particles()
        self._clear_bots()
        for s in self.shells:
            destroy(s)
        self.shells = []
        for w in self.wire_segments:
            destroy(w)
        self.wire_segments = []
        if self._outer_shell is not None:
            destroy(self._outer_shell)
            self._outer_shell = None
        if self._mirrors is not None:
            for m in self._mirrors:
                destroy(m)
            self._mirrors = None

    def _restart(self):
        self._clear_extras()
        self.membrane.visible = False
        self.membrane.scale = Vec3(0.01, 0.01, 0.01)
        self.iron_shell.visible = False
        self.concentrator.visible = False
        self.mothership.visible = True
        self.rock.visible = True
        self._go_phase(0)

    # -- Update --

    def update(self):
        # Force dark background every frame (EditorCamera overrides it)
        base.win.setClearColor(CLEAR_COLOR)

        dt = time.dt
        self.phase_time += dt
        self.space_cd -= dt
        self.r_cd -= dt

        if held_keys["space"] and self.space_cd <= 0:
            self.space_cd = 0.5
            if self.phase < 6:
                self._go_phase(self.phase + 1)

        if held_keys["r"] and self.r_cd <= 0:
            self.r_cd = 0.5
            self._restart()

        if held_keys["escape"]:
            sys.exit()

        # Rock rotates slowly
        if self.rock and self.rock.visible:
            self.rock.rotation_y += dt * 3

        # Phase animations
        p = self.phase
        t = self.phase_time
        if p == 0:
            self._anim_p0(dt, t)
        elif p == 1:
            self._anim_p1(dt, t)
        elif p == 2:
            self._anim_p2(dt, t)
        elif p == 3:
            self._anim_p3(dt, t)
        elif p == 4:
            self._anim_p4(dt, t)
        elif p == 5:
            self._anim_p5(dt, t)
        elif p == 6:
            self._anim_p6(dt, t)

    # -- Phase animations --

    def _anim_p0(self, dt, t):
        """Mothership drifts, ion engine pulses."""
        self.mothership.position = Vec3(
            10 + math.sin(t * 0.3) * 0.2,
            4 + math.cos(t * 0.5) * 0.15,
            7 + math.sin(t * 0.4) * 0.18)
        pulse = 0.18 + 0.06 * math.sin(t * 5)
        self.mothership._ion.scale = pulse

    def _anim_p1(self, dt, t):
        """Approach, arms extend, membrane wraps."""
        if t < 4.0:
            # Approach -- mothership moves toward rock
            frac = min(1.0, t / 4.0)
            f = frac * frac * (3 - 2 * frac)  # smoothstep
            self.mothership.position = Vec3(
                10 + (0 - 10) * f,
                4 + (3.0 - 4) * f,
                7 + (0 - 7) * f)
            self.mothership._ion.scale = 0.18 * (1 - f * 0.8)

        elif t < 6.0:
            # Arms extend toward rock
            self.mothership.position = Vec3(0, 3.0, 0)
            self.mothership._ion.visible = False
            af = min(1.0, (t - 4) / 2.0)
            for i, arm in enumerate(self.mothership._arms):
                side = 1 if i == 0 else -1
                arm.rotation = Vec3(0, 0, side * (25 + af * 55))

        elif t < 12.0:
            # Membrane deploys -- gold sphere grows around rock
            mf = min(1.0, (t - 6) / 6.0)
            s = 3.5 * mf  # grows to slightly larger than rock
            self.membrane.scale = Vec3(s, s, s)
            a = int(60 + mf * 120)
            self.membrane.color = color.rgba(220, 190, 60, a)
            # Bundle shrinks as membrane deploys
            bs = max(0.01, 1.0 - mf)
            self.mothership._bundle.scale = Vec3(0.4 * bs, 0.2 * bs, 0.35 * bs)
            if mf > 0.95:
                self.mothership._bundle.visible = False

    def _anim_p2(self, dt, t):
        """Bioleaching: membrane goes green, iron layer grows."""
        # Membrane color shifts gold -> green
        gf = min(1.0, t / 8.0)
        r = int(220 - gf * 100)
        g = int(190 - gf * 10)
        b = int(60 + gf * 40)
        self.membrane.color = color.rgba(r, g, b, 140)

        # Iron shell fades in (silver layer)
        ia = min(150, int(t / 8.0 * 150))
        self.iron_shell.color = color.rgba(180, 185, 200, ia)

        # Particles drift inside membrane
        for p in self.particles:
            p.position += Vec3(
                math.sin(t * 2 + id(p) % 7) * dt * 0.2,
                math.cos(t * 1.5 + id(p) % 5) * dt * 0.2,
                math.sin(t * 1.8 + id(p) % 3) * dt * 0.2)
            # Keep inside sphere
            if p.position.length() > 1.2:
                p.position = p.position.normalized() * 0.4

        # Concentrator wobbles
        self.concentrator.rotation_y = -30 + math.sin(t * 0.5) * 5

    def _anim_p3(self, dt, t):
        """Wire segments appear, showing electroforming."""
        # Add a new wire segment every 0.4 seconds (use cube, not cylinder)
        if t > len(self.wire_segments) * 0.4 and len(self.wire_segments) < 15:
            yi = 2.8 - len(self.wire_segments) * 0.16
            w = Entity(model="cube", color=bright(210, 210, 220),
                       scale=Vec3(0.06, 0.16, 0.06),
                       position=Vec3(0.4, yi, 0.2), unlit=True)
            self.wire_segments.append(w)

        # Existing wires pulse slightly
        for i, w in enumerate(self.wire_segments):
            w.color = bright(
                200 + int(10 * math.sin(t * 3 + i)),
                200 + int(10 * math.sin(t * 3 + i)),
                220)

    def _anim_p4(self, dt, t):
        """Printer bots crawl on the shell."""
        # Spawn 2 bots over time
        if len(self.bots) < 2 and t > 1.0 + len(self.bots) * 2.0:
            angle = len(self.bots) * 137  # golden angle
            rad = math.radians(angle)
            r = 2.0  # on the shell surface
            pos = Vec3(math.cos(rad) * r, math.sin(rad) * r, 0)
            bot = make_bot(pos, scale=0.2)
            self.bots.append(bot)

        # Bots orbit on the shell surface
        for i, bot in enumerate(self.bots):
            a = t * 0.4 + i * math.pi
            elev = math.sin(t * 0.3 + i * 2) * 0.5
            r = 2.0
            bot.position = Vec3(
                math.cos(a) * r * math.cos(elev),
                math.sin(elev) * r,
                math.sin(a) * r * math.cos(elev))
            bot.look_at(Vec3(0, 0, 0))

            # Leave silver WAAM trail dots
            if int(t * 5) % 3 == 0 and random.random() < 0.3:
                trail = Entity(model="sphere", scale=0.06,
                               color=bright(200, 200, 210),
                               position=bot.position, unlit=True)
                self.bot_trails.append(trail)

    def _anim_p5(self, dt, t):
        """More bots, shell thickens, outer wireframe."""
        # Spawn more bots (up to 8)
        if len(self.bots) < 8 and t > len(self.bots) * 0.8:
            angle = len(self.bots) * 137
            rad = math.radians(angle)
            r = 2.0
            pos = Vec3(math.cos(rad) * r, 0, math.sin(rad) * r)
            bot = make_bot(pos, scale=0.2)
            self.bots.append(bot)

        # Animate all bots
        for i, bot in enumerate(self.bots):
            a = t * 0.5 + i * math.pi * 0.25
            elev = math.sin(t * 0.2 + i) * 0.8
            r = 2.1
            bot.position = Vec3(
                math.cos(a) * r * math.cos(elev),
                math.sin(elev) * r,
                math.sin(a) * r * math.cos(elev))
            bot.look_at(Vec3(0, 0, 0))

            if random.random() < 0.15:
                trail = Entity(model="sphere", scale=0.06,
                               color=bright(200, 200, 210),
                               position=bot.position, unlit=True)
                self.bot_trails.append(trail)

        # Iron shell gets more opaque
        ia = min(200, 150 + int(t * 5))
        self.iron_shell.color = color.rgba(180, 185, 200, ia)

        # Outer shell wireframe grows at t>3
        if t > 3.0 and self._outer_shell is None:
            self._outer_shell = Entity(
                model="sphere", scale=Vec3(5.0, 5.0, 5.0),
                color=color.rgba(150, 200, 255, 40),
                unlit=True)

        # Concentrator mirrors appear at t>2
        if t > 2.0 and self._mirrors is None:
            self._mirrors = []
            for i in range(4):
                a = i * 90
                rad = math.radians(a)
                # Use cube with thin z for a flat mirror panel
                m = Entity(model="cube", scale=Vec3(1.2, 1.2, 0.04),
                           color=bright(190, 200, 220),
                           position=Vec3(math.cos(rad) * 4.5, 0.5,
                                         math.sin(rad) * 4.5),
                           rotation=Vec3(0, -a, -20),
                           unlit=True)
                self._mirrors.append(m)

    def _anim_p6(self, dt, t):
        """Spiral of shells appear one by one. Camera orbits and zooms out."""
        # Reveal shells progressively
        for i, s in enumerate(self.shells):
            reveal_time = 1.0 + i * 1.5
            if t > reveal_time and not s.visible:
                s.visible = True

        # Shells pulse gently
        for i, s in enumerate(self.shells):
            if s.visible:
                base_r = 1.2 + i * 0.8
                pulse = base_r + math.sin(t * 0.5 + i * 0.5) * 0.1
                s.scale = Vec3(pulse * 2, pulse * 2, pulse * 2)

        # Camera slowly orbits outward
        dist = 12 + t * 0.8
        ca = t * 0.15
        camera.position = Vec3(
            math.cos(ca) * dist,
            6 + t * 0.3,
            math.sin(ca) * dist)
        camera.look_at(Vec3(0, 0, 0))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app = Ursina(
        title="AstraAnt -- Garbage Bag to Space Station",
        borderless=False,
        size=(1280, 720),
    )

    # EditorCamera BEFORE scene entities
    ec = EditorCamera(rotation_smoothing=4, zoom_speed=2)

    # Force background color
    base.win.setClearColor(CLEAR_COLOR)

    # Stars -- small bright spheres scattered far away
    for _ in range(300):
        Entity(model="sphere", scale=random.uniform(0.03, 0.08),
               color=bright(220, 220, 255),
               position=Vec3(random.uniform(-80, 80),
                             random.uniform(-80, 80),
                             random.uniform(-80, 80)),
               unlit=True)

    viz = BootstrapViz()
    viz.setup()

    def update():
        viz.update()

    sys.modules[__name__].update = update
    app.run()


if __name__ == "__main__":
    main()
