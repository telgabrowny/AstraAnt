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


def create_tunnel_visual(radius=10.0, tunnel_length=5.0, tunnel_diameter=0.4) -> Entity:
    """Create a visual tunnel inside the asteroid for cutaway view.

    Returns an entity representing the excavated tunnel space.
    """
    # Tunnel is a dark cylinder descending from the surface
    tunnel = Entity(
        model="cylinder",
        color=color.rgb(20, 15, 10),   # Very dark interior
        scale=Vec3(tunnel_diameter, tunnel_length / 2, tunnel_diameter),
        position=Vec3(0, radius - tunnel_length / 2, 0),
    )

    # Work lights (amber dots along the tunnel)
    for i in range(int(tunnel_length)):
        light = Entity(
            parent=tunnel,
            model="sphere",
            color=color.rgb(255, 180, 50),
            scale=0.05,
            position=Vec3(0.18, -0.3 + i * 0.15, 0),
            unlit=True,
        )

    return tunnel
