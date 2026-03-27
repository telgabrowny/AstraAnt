"""Procedural asteroid mesh generator using icosphere + Perlin noise displacement."""

from __future__ import annotations

import math
from typing import Any

from ursina import Entity, Mesh, Vec3, color

try:
    from noise import pnoise3
except ImportError:
    # Fallback: simple hash-based noise if noise package not installed
    def pnoise3(x, y, z, octaves=1, persistence=0.5):
        h = hash((round(x * 1000), round(y * 1000), round(z * 1000)))
        return ((h % 10000) / 10000.0 - 0.5) * 2


def _icosahedron_vertices() -> tuple[list[list[float]], list[list[int]]]:
    """Generate the 12 vertices and 20 faces of a regular icosahedron."""
    t = (1 + math.sqrt(5)) / 2  # Golden ratio

    verts = [
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ]
    # Normalize to unit sphere
    for v in verts:
        length = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
        v[0] /= length
        v[1] /= length
        v[2] /= length

    faces = [
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ]
    return verts, faces


def _subdivide(verts: list[list[float]], faces: list[list[int]]) -> tuple[list[list[float]], list[list[int]]]:
    """Subdivide each triangle face into 4 smaller triangles."""
    edge_midpoints: dict[tuple[int, int], int] = {}

    def get_midpoint(i1: int, i2: int) -> int:
        key = (min(i1, i2), max(i1, i2))
        if key in edge_midpoints:
            return edge_midpoints[key]
        v1, v2 = verts[i1], verts[i2]
        mid = [(v1[0]+v2[0])/2, (v1[1]+v2[1])/2, (v1[2]+v2[2])/2]
        # Normalize to unit sphere
        length = math.sqrt(mid[0]**2 + mid[1]**2 + mid[2]**2)
        mid[0] /= length
        mid[1] /= length
        mid[2] /= length
        idx = len(verts)
        verts.append(mid)
        edge_midpoints[key] = idx
        return idx

    new_faces = []
    for f in faces:
        a, b, c = f
        ab = get_midpoint(a, b)
        bc = get_midpoint(b, c)
        ca = get_midpoint(c, a)
        new_faces.extend([
            [a, ab, ca],
            [b, bc, ab],
            [c, ca, bc],
            [ab, bc, ca],
        ])
    return verts, new_faces


def create_asteroid_mesh(radius: float = 10.0, subdivisions: int = 4,
                         noise_scale: float = 0.3, noise_octaves: int = 4,
                         shape: str = "rubble_pile") -> Mesh:
    """Generate a procedural asteroid mesh.

    Args:
        radius: Base radius of the asteroid in scene units.
        subdivisions: Icosphere subdivision level (3=320 faces, 4=1280, 5=5120).
        noise_scale: How much noise displaces the surface (fraction of radius).
        noise_octaves: Perlin noise octaves (more = more detail).
        shape: 'rubble_pile' (irregular), 'spinning_top' (Bennu-like equatorial bulge),
               or 'elongated' (Itokawa-like).
    """
    verts, faces = _icosahedron_vertices()
    for _ in range(subdivisions):
        verts, faces = _subdivide(verts, faces)

    # Apply shape and noise displacement
    displaced_verts = []
    vert_colors = []
    for v in verts:
        x, y, z = v

        # Base shape modifier
        if shape == "spinning_top":
            # Bennu's equatorial bulge: wider at equator
            lat = math.asin(max(-1, min(1, y)))  # y is up
            shape_factor = 1.0 + 0.12 * math.cos(2 * lat)
        elif shape == "elongated":
            # Itokawa-like: stretched along one axis
            shape_factor = 1.0 + 0.3 * abs(x)
        else:
            shape_factor = 1.0

        # Perlin noise displacement
        noise_val = pnoise3(
            x * 2.0, y * 2.0, z * 2.0,
            octaves=noise_octaves,
            persistence=0.5,
        )
        displacement = radius * shape_factor * (1.0 + noise_scale * noise_val)

        displaced_verts.append(Vec3(x * displacement, y * displacement, z * displacement))

        # Vertex color: dark gray with noise variation (asteroid surface)
        base_gray = 0.12  # Very dark (Bennu albedo ~0.044, but we brighten for visibility)
        variation = 0.05 * noise_val
        gray = max(0.05, min(0.25, base_gray + variation))
        # Slight brownish tint
        vert_colors.append(color.rgb(
            int(gray * 255 * 1.1),
            int(gray * 255 * 1.0),
            int(gray * 255 * 0.85),
        ))

    # Build triangle list for Mesh
    triangles = []
    for f in faces:
        triangles.extend(f)

    mesh = Mesh(
        vertices=[list(v) for v in displaced_verts],
        triangles=triangles,
        colors=[c for c in vert_colors],
        mode='triangle',
    )
    mesh.generate_normals()

    return mesh


def create_asteroid_entity(radius: float = 10.0, subdivisions: int = 4,
                           shape: str = "rubble_pile", **kwargs: Any) -> Entity:
    """Create an asteroid Entity ready to add to the scene."""
    mesh = create_asteroid_mesh(radius=radius, subdivisions=subdivisions, shape=shape)

    asteroid = Entity(
        model=mesh,
        color=color.white,  # Let vertex colors control appearance
        **kwargs,
    )
    return asteroid
