"""Procedural asteroid mesh generator using icosphere + Perlin noise displacement.

Supports two render modes:
- Full: complete asteroid (exterior view)
- Cutaway: hemisphere slice showing tunnel interior (ant farm view)
"""

from __future__ import annotations

import math
from typing import Any

from ursina import Entity, Mesh, Vec3, color

try:
    from noise import pnoise3
except ImportError:
    def pnoise3(x, y, z, octaves=1, persistence=0.5):
        h = hash((round(x * 1000), round(y * 1000), round(z * 1000)))
        return ((h % 10000) / 10000.0 - 0.5) * 2


def _icosahedron_vertices() -> tuple[list[list[float]], list[list[int]]]:
    """Generate the 12 vertices and 20 faces of a regular icosahedron."""
    t = (1 + math.sqrt(5)) / 2
    verts = [
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ]
    for v in verts:
        length = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
        v[0] /= length; v[1] /= length; v[2] /= length
    faces = [
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ]
    return verts, faces


def _subdivide(verts, faces):
    edge_midpoints = {}
    def get_midpoint(i1, i2):
        key = (min(i1, i2), max(i1, i2))
        if key in edge_midpoints:
            return edge_midpoints[key]
        v1, v2 = verts[i1], verts[i2]
        mid = [(v1[0]+v2[0])/2, (v1[1]+v2[1])/2, (v1[2]+v2[2])/2]
        length = math.sqrt(mid[0]**2 + mid[1]**2 + mid[2]**2)
        mid[0] /= length; mid[1] /= length; mid[2] /= length
        idx = len(verts)
        verts.append(mid)
        edge_midpoints[key] = idx
        return idx
    new_faces = []
    for f in faces:
        a, b, c = f
        ab, bc, ca = get_midpoint(a, b), get_midpoint(b, c), get_midpoint(c, a)
        new_faces.extend([[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]])
    return verts, new_faces


def _make_asteroid_mesh(radius, subdivisions, noise_scale, noise_octaves, shape,
                        cutaway=False):
    """Core mesh generation — supports full and cutaway modes."""
    verts, faces = _icosahedron_vertices()
    for _ in range(subdivisions):
        verts, faces = _subdivide(verts, faces)

    displaced_verts = []
    vert_colors = []
    for v in verts:
        x, y, z = v
        if shape == "spinning_top":
            lat = math.asin(max(-1, min(1, y)))
            shape_factor = 1.0 + 0.12 * math.cos(2 * lat)
        elif shape == "elongated":
            shape_factor = 1.0 + 0.3 * abs(x)
        else:
            shape_factor = 1.0

        noise_val = pnoise3(x * 2.0, y * 2.0, z * 2.0,
                            octaves=noise_octaves, persistence=0.5)
        displacement = radius * shape_factor * (1.0 + noise_scale * noise_val)
        displaced_verts.append([x * displacement, y * displacement, z * displacement])

        base_gray = 0.12
        variation = 0.05 * noise_val
        gray = max(0.05, min(0.25, base_gray + variation))
        vert_colors.append(color.rgb(
            int(gray * 255 * 1.1), int(gray * 255), int(gray * 255 * 0.85)
        ))

    # For cutaway: filter faces where all vertices have z > 0 (keep z <= 0 half)
    if cutaway:
        kept_faces = []
        for f in faces:
            # Keep face if ANY vertex has z <= 0 (shows cross-section at z=0)
            if any(displaced_verts[vi][2] <= 0.5 for vi in f):
                kept_faces.append(f)
        faces = kept_faces

        # Add cross-section face coloring — exposed interior is lighter/reddish
        for i, v in enumerate(displaced_verts):
            if v[2] > -0.5 and v[2] < 0.5:
                # Near the cut plane — show interior color (lighter, reddish)
                vert_colors[i] = color.rgb(80, 55, 40)

    triangles = []
    for f in faces:
        triangles.extend(f)

    mesh = Mesh(
        vertices=displaced_verts,
        triangles=triangles,
        colors=vert_colors,
        mode='triangle',
    )
    mesh.generate_normals()
    return mesh


def create_asteroid_mesh(radius=10.0, subdivisions=4, noise_scale=0.3,
                         noise_octaves=4, shape="rubble_pile") -> Mesh:
    """Generate a full asteroid mesh."""
    return _make_asteroid_mesh(radius, subdivisions, noise_scale, noise_octaves, shape,
                               cutaway=False)


def create_cutaway_mesh(radius=10.0, subdivisions=4, noise_scale=0.3,
                        noise_octaves=4, shape="rubble_pile") -> Mesh:
    """Generate a cutaway (half) asteroid mesh showing the interior."""
    return _make_asteroid_mesh(radius, subdivisions, noise_scale, noise_octaves, shape,
                               cutaway=True)


def create_asteroid_entity(radius=10.0, subdivisions=4, shape="rubble_pile",
                           cutaway=False, **kwargs) -> Entity:
    """Create an asteroid Entity ready to add to the scene."""
    if cutaway:
        mesh = create_cutaway_mesh(radius=radius, subdivisions=subdivisions, shape=shape)
    else:
        mesh = create_asteroid_mesh(radius=radius, subdivisions=subdivisions, shape=shape)
    return Entity(model=mesh, color=color.white, **kwargs)


ZONE_COLORS = {
    "hydrated_matrix": color.rgb(60, 80, 100),      # Blue-gray
    "sulfide_pocket": color.rgb(140, 100, 40),       # Bronze/copper
    "metal_grain": color.rgb(200, 200, 180),         # Bright metallic
    "organic_rich": color.rgb(50, 70, 40),           # Dark green
    "silicate_bulk": color.rgb(80, 70, 60),          # Brown-gray
    "void_rubble": color.rgb(30, 25, 20),            # Very dark
    "": color.rgb(40, 35, 30),                        # Default tunnel color
}


def create_tunnel_visual(radius=10.0, tunnel_length=5.0, tunnel_diameter=0.4) -> Entity:
    """Create a basic tunnel visual (used before sim starts)."""
    root = Entity()

    # Main shaft from surface downward
    shaft = Entity(
        parent=root,
        model="cylinder",
        color=color.rgb(30, 25, 20),
        scale=Vec3(tunnel_diameter, tunnel_length / 2, tunnel_diameter),
        position=Vec3(0, radius - tunnel_length / 2, 0),
    )

    # Work lights along shaft
    for i in range(int(tunnel_length)):
        Entity(
            parent=shaft, model="sphere",
            color=color.rgb(255, 180, 50), scale=0.05,
            position=Vec3(0.18, -0.3 + i * 0.15, 0), unlit=True,
        )

    return root


def update_tunnel_visual_from_state(root_entity: Entity, tunnel_network,
                                     asteroid_radius: float = 10.0,
                                     scale_factor: float = 0.3) -> None:
    """Update tunnel visual entities to match the simulation's tunnel network state.

    Creates/updates cylinder entities for each tunnel segment, colored by zone type.
    Also shows nodes as small spheres (branch points brighter).
    """
    # Clear old children (except work lights from initial creation)
    for child in list(root_entity.children):
        child.enabled = False

    # Scale tunnel coords to visual space
    # Tunnel network uses meters, visual uses scene units
    # Map: sim Y (negative = deeper) -> visual Y (relative to asteroid center)
    def sim_to_visual(pos) -> Vec3:
        return Vec3(
            pos.x * scale_factor,
            asteroid_radius + pos.y * scale_factor,  # y is negative in sim
            pos.z * scale_factor,
        )

    # Draw segments as cylinders
    for seg in tunnel_network.segments:
        from_node = next((n for n in tunnel_network.nodes if n.id == seg.from_node_id), None)
        to_node = next((n for n in tunnel_network.nodes if n.id == seg.to_node_id), None)
        if from_node is None or to_node is None:
            continue

        start = sim_to_visual(from_node.position)
        end = sim_to_visual(to_node.position)

        # Midpoint and length
        mid = Vec3((start.x + end.x) / 2, (start.y + end.y) / 2, (start.z + end.z) / 2)
        length = (Vec3(end.x - start.x, end.y - start.y, end.z - start.z)).length()
        if length < 0.01:
            continue

        zone_color = ZONE_COLORS.get(seg.zone_type, ZONE_COLORS[""])

        # Sealed segments are slightly brighter
        if seg.sealed:
            zone_color = color.rgb(
                min(255, int(zone_color.r * 255 * 1.3)),
                min(255, int(zone_color.g * 255 * 1.3)),
                min(255, int(zone_color.b * 255 * 1.3)),
            )

        seg_entity = Entity(
            parent=root_entity,
            model="cube",  # Simpler than cylinder for many segments
            color=zone_color,
            scale=Vec3(0.15, length, 0.15),
            position=mid,
        )
        # Orient toward the end point
        if length > 0.01:
            seg_entity.look_at(end)
            seg_entity.rotation_x += 90  # Cylinder alignment

    # Draw branch points as small bright spheres
    for node in tunnel_network.nodes:
        pos = sim_to_visual(node.position)
        node_color = color.rgb(255, 200, 50) if node.is_entrance else color.rgb(150, 130, 100)
        Entity(
            parent=root_entity,
            model="sphere",
            color=node_color,
            scale=0.08 if node.is_entrance else 0.04,
            position=pos,
            unlit=True,
        )

    # Draw common chamber if it exists
    if tunnel_network.common_chamber and tunnel_network.common_chamber.current_radius_m > 0:
        ch = tunnel_network.common_chamber
        ch_pos = sim_to_visual(ch.center)
        ch_r = ch.current_radius_m * scale_factor
        Entity(
            parent=root_entity,
            model="sphere",
            color=color.rgb(100, 150, 200) if ch.sealed else color.rgb(60, 50, 40),
            scale=ch_r * 2,
            position=ch_pos,
        )
