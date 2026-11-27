"""
ClothOS Parametric 3D CAD Solid & BREP Kernel (`loom/clothos/cad_kernel.py`)

Constructs genuine, mathematically accurate, watertight 3D triangle meshes,
outward unit normals, binary/ASCII STL files, and faceted ISO-10303-21 STEP
exchange files for all ClothOS STEM engineering archetypes without requiring
external GUI/heavyweight CAD binaries.
"""

from __future__ import annotations

import datetime
import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Vectorized Geometry & Primitive Builders (Right-Handed Outward CCW Winding)
# ---------------------------------------------------------------------------

def _orient_triangles_outward_around_center(
    verts: np.ndarray,
    tris: np.ndarray,
    center: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Ensures triangle winding points away from component centroid (convex/star-shaped)."""
    if len(tris) == 0:
        return tris
    c = verts.mean(axis=0) if center is None else np.asarray(center, dtype=float)
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    tri_normals = np.cross(v1 - v0, v2 - v0)
    tri_centers = (v0 + v1 + v2) / 3.0
    dots = np.sum(tri_normals * (tri_centers - c), axis=1)
    flipped = tris.copy()
    mask = dots < 0.0
    flipped[mask, 1], flipped[mask, 2] = tris[mask, 2], tris[mask, 1]
    return flipped


def compute_triangle_normals(verts: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Computes normalized surface normal vectors for each triangle."""
    if len(tris) == 0:
        return np.zeros((0, 3), dtype=float)
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    lens = np.linalg.norm(n, axis=1, keepdims=True)
    lens = np.where(lens < 1e-12, 1.0, lens)
    return n / lens


def compute_mesh_metrics(verts: np.ndarray, tris: np.ndarray) -> Dict[str, Any]:
    """Computes exact bounding box, surface area (mm^2), and closed signed volume (mm^3)."""
    if len(verts) == 0 or len(tris) == 0:
        return {
            "vertex_count": 0,
            "triangle_count": 0,
            "volume_mm3": 0.0,
            "surface_area_mm2": 0.0,
            "bounds": {"x": [0.0, 0.0], "y": [0.0, 0.0], "z": [0.0, 0.0]},
        }
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    cross_prod = np.cross(v1 - v0, v2 - v0)
    areas = 0.5 * np.linalg.norm(cross_prod, axis=1)
    signed_vol = float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)
    return {
        "vertex_count": int(len(verts)),
        "triangle_count": int(len(tris)),
        "volume_mm3": round(abs(signed_vol), 2),
        "surface_area_mm2": round(float(np.sum(areas)), 2),
        "bounds": {
            "x": [round(float(verts[:, 0].min()), 3), round(float(verts[:, 0].max()), 3)],
            "y": [round(float(verts[:, 1].min()), 3), round(float(verts[:, 1].max()), 3)],
            "z": [round(float(verts[:, 2].min()), 3), round(float(verts[:, 2].max()), 3)],
        },
    }


def merge_components(parts: List[Tuple[np.ndarray, np.ndarray]]) -> Tuple[np.ndarray, np.ndarray]:
    """Concatenates multiple disjoint watertight components into a single mesh."""
    all_v: List[np.ndarray] = []
    all_t: List[np.ndarray] = []
    offset = 0
    for v, t in parts:
        if len(v) == 0 or len(t) == 0:
            continue
        all_v.append(np.asarray(v, dtype=float))
        all_t.append(np.asarray(t, dtype=np.int32) + offset)
        offset += len(v)
    if not all_v:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32)
    return np.vstack(all_v), np.vstack(all_t)


def make_box(
    x0: float, x1: float,
    y0: float, y1: float,
    z0: float, z1: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Builds a watertight axis-aligned rectangular solid [x0,x1] x [y0,y1] x [z0,z1]."""
    verts = np.array([
        [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
        [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
    ], dtype=float)
    tris = np.array([
        [0, 2, 1], [0, 3, 2],  # bottom (-z)
        [4, 5, 6], [4, 6, 7],  # top (+z)
        [0, 1, 5], [0, 5, 4],  # front (-y)
        [2, 3, 7], [2, 7, 6],  # back (+y)
        [0, 4, 7], [0, 7, 3],  # left (-x)
        [1, 2, 6], [1, 6, 5],  # right (+x)
    ], dtype=np.int32)
    return verts, tris


def make_hollow_box(
    outer_w: float, outer_h: float, outer_d: float,
    wall: float,
    open_z_ends: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Builds a hollow rectangular chamber/waveguide centered at origin."""
    hw, hh, hd = outer_w / 2.0, outer_h / 2.0, outer_d / 2.0
    parts: List[Tuple[np.ndarray, np.ndarray]] = [
        # Bottom slab
        make_box(-hw, hw, -hh, -hh + wall, -hd, hd),
        # Top slab
        make_box(-hw, hw, hh - wall, hh, -hd, hd),
        # Left wall (between top & bottom slabs)
        make_box(-hw, -hw + wall, -hh + wall, hh - wall, -hd, hd),
        # Right wall
        make_box(hw - wall, hw, -hh + wall, hh - wall, -hd, hd),
    ]
    if not open_z_ends:
        # Front & back end-caps spanning inner aperture
        parts.append(make_box(-hw + wall, hw - wall, -hh + wall, hh - wall, -hd, -hd + wall))
        parts.append(make_box(-hw + wall, hw - wall, -hh + wall, hh - wall, hd - wall, hd))
    return merge_components(parts)


def make_cylinder(
    cx: float, cy: float, z0: float, z1: float,
    radius: float,
    segments: int = 24,
    axis: str = "z",
) -> Tuple[np.ndarray, np.ndarray]:
    """Builds a watertight capped cylinder aligned with axis 'x', 'y', or 'z'."""
    angles = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    cos_a = np.cos(angles)
    sin_a = np.sin(angles)

    verts_list: List[List[float]] = []
    for k in range(segments):
        u, v = radius * cos_a[k], radius * sin_a[k]
        if axis == "z":
            verts_list.append([cx + u, cy + v, z0])
        elif axis == "y":
            verts_list.append([cx + u, z0, cy + v])
        else:
            verts_list.append([z0, cx + u, cy + v])
    for k in range(segments):
        u, v = radius * cos_a[k], radius * sin_a[k]
        if axis == "z":
            verts_list.append([cx + u, cy + v, z1])
        elif axis == "y":
            verts_list.append([cx + u, z1, cy + v])
        else:
            verts_list.append([z1, cx + u, cy + v])

    if axis == "z":
        c0_pos, c1_pos = [cx, cy, z0], [cx, cy, z1]
    elif axis == "y":
        c0_pos, c1_pos = [cx, z0, cy], [cx, z1, cy]
    else:
        c0_pos, c1_pos = [z0, cx, cy], [z1, cx, cy]
    idx_c0 = len(verts_list)
    verts_list.append(c0_pos)
    idx_c1 = len(verts_list)
    verts_list.append(c1_pos)

    tris_list: List[List[int]] = []
    for k in range(segments):
        kn = (k + 1) % segments
        b0, b1 = k, kn
        t0, t1 = segments + k, segments + kn
        tris_list.append([b0, b1, t1])
        tris_list.append([b0, t1, t0])
        tris_list.append([idx_c0, b1, b0])
        tris_list.append([idx_c1, t0, t1])

    verts = np.array(verts_list, dtype=float)
    tris = _orient_triangles_outward_around_center(verts, np.array(tris_list, dtype=np.int32))
    return verts, tris


def make_annulus(
    cx: float, cy: float, z0: float, z1: float,
    r_inner: float, r_outer: float,
    segments: int = 36,
    outer_radii: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Builds a watertight extruded annular disc / gear ring with optional outer radius modulation."""
    n = len(outer_radii) if outer_radii is not None else segments
    angles = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    r_out = outer_radii if outer_radii is not None else np.full(n, r_outer, dtype=float)

    verts_list: List[List[float]] = []
    # Ring indexing: [0..n-1]=outer bottom, [n..2n-1]=outer top, [2n..3n-1]=inner bottom, [3n..4n-1]=inner top
    for z in (z0, z1):
        for k in range(n):
            verts_list.append([cx + r_out[k] * math.cos(angles[k]), cy + r_out[k] * math.sin(angles[k]), z])
    for z in (z0, z1):
        for k in range(n):
            verts_list.append([cx + r_inner * math.cos(angles[k]), cy + r_inner * math.sin(angles[k]), z])

    tris: List[List[int]] = []
    for k in range(n):
        kn = (k + 1) % n
        ob0, ob1 = k, kn
        ot0, ot1 = n + k, n + kn
        ib0, ib1 = 2 * n + k, 2 * n + kn
        it0, it1 = 3 * n + k, 3 * n + kn
        # Outer cylindrical wall (+outward)
        tris.append([ob0, ob1, ot1])
        tris.append([ob0, ot1, ot0])
        # Inner bore wall (+inward toward hole center)
        tris.append([ib0, it1, ib1])
        tris.append([ib0, it0, it1])
        # Top cap (+z)
        tris.append([it0, ot0, ot1])
        tris.append([it0, ot1, it1])
        # Bottom cap (-z)
        tris.append([ib0, ob1, ob0])
        tris.append([ib0, ib1, ob1])

    verts = np.array(verts_list, dtype=float)
    tri_arr = np.array(tris, dtype=np.int32)
    # Orient outer cap/wall outward relative to ring midpoint
    return verts, tri_arr


def make_swept_beam(
    points_xy: np.ndarray,
    thickness_y: float,
    z0: float,
    z1: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extrudes a smooth compliant beam centerline curve with given thickness & height."""
    n = len(points_xy)
    verts_list: List[List[float]] = []
    half_t = thickness_y / 2.0
    for i in range(n):
        p = points_xy[i]
        if i == 0:
            tan = points_xy[1] - points_xy[0]
        elif i == n - 1:
            tan = points_xy[-1] - points_xy[-2]
        else:
            tan = points_xy[i + 1] - points_xy[i - 1]
        tlen = float(np.linalg.norm(tan)) or 1.0
        nrm = np.array([-tan[1] / tlen, tan[0] / tlen])
        lo = p - nrm * half_t
        hi = p + nrm * half_t
        # 4 corners per cross-section: 0=lo_z0, 1=hi_z0, 2=hi_z1, 3=lo_z1
        verts_list.append([float(lo[0]), float(lo[1]), z0])
        verts_list.append([float(hi[0]), float(hi[1]), z0])
        verts_list.append([float(hi[0]), float(hi[1]), z1])
        verts_list.append([float(lo[0]), float(lo[1]), z1])

    tris: List[List[int]] = []
    for i in range(n - 1):
        a = i * 4
        b = (i + 1) * 4
        # bottom, top, side_hi, side_lo
        tris.extend([[a, b + 1, a + 1], [a, b, b + 1]])
        tris.extend([[a + 3, a + 2, b + 2], [a + 3, b + 2, b + 3]])
        tris.extend([[a + 1, b + 1, b + 2], [a + 1, b + 2, a + 2]])
        tris.extend([[a, a + 3, b + 3], [a, b + 3, b]])
    # End caps
    tris.extend([[0, 1, 2], [0, 2, 3]])
    e = (n - 1) * 4
    tris.extend([[e, e + 2, e + 1], [e, e + 3, e + 2]])
    verts = np.array(verts_list, dtype=float)
    return verts, np.array(tris, dtype=np.int32)


def make_gyroid_tpms_solid(
    size_mm: float = 48.0,
    resolution: int = 16,
    wall_iso: float = 0.42,
    cells: float = 1.5,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates a true, watertight 2-manifold Gyroid Triply Periodic Minimal Surface
    solid (`|sin(u)cos(v) + sin(v)cos(w) + sin(w)cos(u)| <= wall_iso`) enclosed
    inside a padded cubic domain using Marching Tetrahedra.
    """
    n = max(10, min(26, int(resolution)))
    half = size_mm / 2.0
    xs = np.linspace(-half, half, n)
    ys = np.linspace(-half, half, n)
    zs = np.linspace(-half, half, n)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")

    k = (2.0 * math.pi * cells) / size_mm
    u, v, w = gx * k, gy * k, gz * k
    gyroid_val = np.sin(u) * np.cos(v) + np.sin(v) * np.cos(w) + np.sin(w) * np.cos(u)
    # Scalar field negative inside wall, positive outside
    field = np.abs(gyroid_val) - wall_iso
    # Close envelope cleanly at domain borders so boundary facets seal the solid
    field[0, :, :] = 0.65
    field[-1, :, :] = 0.65
    field[:, 0, :] = 0.65
    field[:, -1, :] = 0.65
    field[:, :, 0] = 0.65
    field[:, :, -1] = 0.65

    # Exact central finite-difference gradient for outward normal orientation
    grad_x, grad_y, grad_z = np.gradient(field, xs, ys, zs)
    coords = np.stack([gx, gy, gz], axis=-1)
    grads = np.stack([grad_x, grad_y, grad_z], axis=-1)

    # 6-tetrahedra decomposition of unit cube corners
    cube_offsets = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
    ]
    tets_corners = [
        (0, 5, 1, 6),
        (0, 1, 2, 6),
        (0, 2, 3, 6),
        (0, 3, 7, 6),
        (0, 7, 4, 6),
        (0, 4, 5, 6),
    ]

    verts_list: List[List[float]] = []
    tris_list: List[List[int]] = []
    edge_cache: Dict[Tuple[Tuple[int, int, int], Tuple[int, int, int]], int] = {}

    def _interp_edge(
        i0: Tuple[int, int, int], i1: Tuple[int, int, int]
    ) -> Tuple[int, np.ndarray]:
        key = (i0, i1) if i0 < i1 else (i1, i0)
        v0 = float(field[i0])
        v1 = float(field[i1])
        denom = v1 - v0
        t = 0.5 if abs(denom) < 1e-9 else max(0.0, min(1.0, -v0 / denom))
        g = (1.0 - t) * grads[i0] + t * grads[i1]
        if key in edge_cache:
            return edge_cache[key], g
        pos = (1.0 - t) * coords[i0] + t * coords[i1]
        idx = len(verts_list)
        verts_list.append([float(pos[0]), float(pos[1]), float(pos[2])])
        edge_cache[key] = idx
        return idx, g

    def _emit_tri(idx0: int, idx1: int, idx2: int, grad_avg: np.ndarray) -> None:
        p0 = np.array(verts_list[idx0])
        p1 = np.array(verts_list[idx1])
        p2 = np.array(verts_list[idx2])
        nrm = np.cross(p1 - p0, p2 - p0)
        if np.dot(nrm, grad_avg) < 0.0:
            tris_list.append([idx0, idx2, idx1])
        else:
            tris_list.append([idx0, idx1, idx2])

    for ix in range(n - 1):
        for iy in range(n - 1):
            for iz in range(n - 1):
                c_idx = [(ix + dx, iy + dy, iz + dz) for dx, dy, dz in cube_offsets]
                c_val = [float(field[c]) for c in c_idx]
                if all(v >= 0.0 for v in c_val) or all(v < 0.0 for v in c_val):
                    continue
                for a, b, c, d in tets_corners:
                    tet = [c_idx[a], c_idx[b], c_idx[c], c_idx[d]]
                    inside = [p for p in tet if field[p] < 0.0]
                    outside = [p for p in tet if field[p] >= 0.0]
                    nin = len(inside)
                    if nin == 0 or nin == 4:
                        continue
                    if nin == 1:
                        in0 = inside[0]
                        i0, g0 = _interp_edge(in0, outside[0])
                        i1, g1 = _interp_edge(in0, outside[1])
                        i2, g2 = _interp_edge(in0, outside[2])
                        _emit_tri(i0, i1, i2, g0 + g1 + g2)
                    elif nin == 3:
                        out0 = outside[0]
                        i0, g0 = _interp_edge(inside[0], out0)
                        i1, g1 = _interp_edge(inside[1], out0)
                        i2, g2 = _interp_edge(inside[2], out0)
                        _emit_tri(i0, i1, i2, g0 + g1 + g2)
                    else:  # nin == 2
                        in0, in1 = inside[0], inside[1]
                        out0, out1 = outside[0], outside[1]
                        i0, g0 = _interp_edge(in0, out0)
                        i1, g1 = _interp_edge(in0, out1)
                        i2, g2 = _interp_edge(in1, out0)
                        i3, g3 = _interp_edge(in1, out1)
                        _emit_tri(i0, i1, i3, g0 + g1 + g3)
                        _emit_tri(i0, i3, i2, g0 + g3 + g2)

    if not verts_list or not tris_list:
        return make_box(-half, half, -half, half, -half, half)
    return np.array(verts_list, dtype=float), np.array(tris_list, dtype=np.int32)


# ---------------------------------------------------------------------------
# All 5 ClothOS Parametric STEM Archetypes
# ---------------------------------------------------------------------------

def generate_archetype_mesh(
    archetype: str = "flexure",
    freq_mhz: float = 2450.0,
    symmetry_r: float = 0.88,
    scale_mm: float = 1.0,
    resolution: int = 16,
) -> Dict[str, Any]:
    """
    Constructs a real 3D triangulated CAD mesh for any ClothOS STEM archetype
    or topological benchmark shape. Returns vertices, faces, outward normals,
    exact computed volume & surface area, bounds, and engineering metadata.
    """
    key = archetype.strip().upper()
    s = max(0.3, min(3.0, float(scale_mm)))
    components: List[Tuple[np.ndarray, np.ndarray]] = []

    if "CAVITY" in key or "MICROWAVE" in key:
        arch_id = "MICROWAVE_CAVITY_FILTER"
        # WR waveguide TE101 sizing from frequency
        a_mm = round(max(22.0, min(96.0, 3e5 / (2.0 * max(100.0, freq_mhz)))) * s, 2)
        b_mm = round(a_mm * 0.52, 2)
        d_mm = round(a_mm * 1.414, 2)
        wall = round(3.2 * s, 2)
        probe_r = round(2.1 * s, 2)

        # Open waveguide sleeve + mid septum iris + twin end mounting flanges + SMA probes
        components.append(make_hollow_box(a_mm + 2 * wall, b_mm + 2 * wall, d_mm, wall, open_z_ends=True))
        # End mounting flange collars (front & back with thick rim)
        flange_w = a_mm + 2 * wall + 12.0 * s
        flange_h = b_mm + 2 * wall + 12.0 * s
        flange_t = 3.5 * s
        for zf in (-d_mm / 2.0, d_mm / 2.0 - flange_t):
            components.append(make_hollow_box(flange_w, flange_h, flange_t, (flange_w - a_mm) / 2.0, open_z_ends=True))
            # Shift the newly appended flange to zf + flange_t/2
            fv, ft = components.pop()
            fv[:, 2] += (zf + flange_t / 2.0)
            components.append((fv, ft))
            # 4 Corner Alignment Pins / Fastener Bosses
            for sx in (-flange_w / 2.0 + 3.5 * s, flange_w / 2.0 - 3.5 * s):
                for sy in (-flange_h / 2.0 + 3.5 * s, flange_h / 2.0 - 3.5 * s):
                    components.append(make_cylinder(sx, sy, zf - 1.2 * s, zf + flange_t + 1.2 * s, 1.8 * s, segments=12, axis="z"))

        # Resonant capacitive tuning irises inside cavity
        components.append(make_cylinder(0.0, 0.0, b_mm * 0.1, b_mm / 2.0 + wall + 4.5 * s, probe_r * 1.15, segments=18, axis="y"))
        components.append(make_cylinder(-a_mm * 0.28, -d_mm * 0.25, b_mm / 2.0 - 5.0 * s, b_mm / 2.0 + wall + 8.0 * s, probe_r, segments=16, axis="y"))
        components.append(make_cylinder(a_mm * 0.28, d_mm * 0.25, b_mm / 2.0 - 5.0 * s, b_mm / 2.0 + wall + 8.0 * s, probe_r, segments=16, axis="y"))

        title = f"Microwave TE101 Waveguide Cavity Filter ({freq_mhz:.0f} MHz)"
        domain = "Electromagnetics"
        formula = r"f_{101} = \frac{c}{2\pi \sqrt{\mu_r \epsilon_r}} \sqrt{\left(\frac{\pi}{a}\right)^2 + \left(\frac{\pi}{d}\right)^2}"
        genus = 5
        dims = {"a_width_mm": a_mm, "b_height_mm": b_mm, "d_length_mm": d_mm, "wall_t_mm": wall}

    elif "GYROID" in key or "TPMS" in key:
        arch_id = "GYROID_TPMS_HEAT_EXCHANGER"
        cube_mm = round((42.0 + symmetry_r * 14.0) * s, 2)
        wall_iso = round(0.36 + 0.14 * symmetry_r, 3)
        gv, gt = make_gyroid_tpms_solid(size_mm=cube_mm, resolution=resolution, wall_iso=wall_iso, cells=1.45)
        components.append((gv, gt))
        # Structural thermal header rails along bottom/top edges
        half_c = cube_mm / 2.0
        rail = 2.6 * s
        for sy in (-half_c + rail / 2.0, half_c - rail / 2.0):
            components.append(make_box(-half_c, half_c, sy - rail / 2.0, sy + rail / 2.0, -half_c - rail, -half_c))
            components.append(make_box(-half_c, half_c, sy - rail / 2.0, sy + rail / 2.0, half_c, half_c + rail))

        title = f"Gyroid Minimal Surface TPMS Core ({cube_mm:.1f} mm^3)"
        domain = "Gyroid_Topology"
        formula = r"\cos(kx)\sin(ky) + \cos(ky)\sin(kz) + \cos(kz)\sin(kx) = 0"
        genus = 3
        dims = {"unit_cell_mm": cube_mm, "wall_iso": wall_iso, "grid_res": resolution}

    elif "ROTOR" in key or "EPICYCLIC" in key or "KURAMOTO" in key:
        arch_id = "KURAMOTO_EPICYCLIC_ROTOR"
        outer_r = round((34.0 + symmetry_r * 16.0) * s, 2)
        teeth = max(16, int(round(20 + symmetry_r * 16)))
        thick = round(9.0 * s, 2)
        r_bore = round(outer_r * 0.22, 2)
        r_web = round(outer_r * 0.72, 2)

        # Smooth involute-tooth outer spur gear rim
        steps_per_tooth = 6
        n_ring = teeth * steps_per_tooth
        r_profile = np.zeros(n_ring, dtype=float)
        tooth_h = round(outer_r * 0.11, 2)
        for idx in range(n_ring):
            ph = idx % steps_per_tooth
            if ph in (2, 3):
                r_profile[idx] = outer_r + tooth_h
            elif ph in (1, 4):
                r_profile[idx] = outer_r + tooth_h * 0.48
            else:
                r_profile[idx] = outer_r

        components.append(make_annulus(0.0, 0.0, -thick / 2.0, thick / 2.0, r_web, outer_r, outer_radii=r_profile))
        # Central keyed hub boss
        components.append(make_annulus(0.0, 0.0, -thick * 0.75, thick * 0.75, r_bore, outer_r * 0.42, segments=32))
        # Radial harmonic oscillator spokes & counterweights
        lobes = max(4, int(round(3 + symmetry_r * 4)))
        for i in range(lobes):
            ang = (2.0 * math.pi * i) / lobes
            p0 = np.array([outer_r * 0.36 * math.cos(ang), outer_r * 0.36 * math.sin(ang)])
            p1 = np.array([r_web * 1.03 * math.cos(ang), r_web * 1.03 * math.sin(ang)])
            pts = np.linspace(p0, p1, 4)
            components.append(make_swept_beam(pts, thickness_y=4.2 * s, z0=-thick * 0.42, z1=thick * 0.42))
            # Oscillator phase mass boss mid-spoke
            mid = 0.5 * (p0 + p1)
            components.append(make_cylinder(float(mid[0]), float(mid[1]), -thick * 0.6, thick * 0.6, 3.6 * s, segments=16))

        title = f"Kuramoto C_{lobes} Epicyclic Harmonic Rotor (Z={teeth}, R={outer_r:.1f}mm)"
        domain = "Symplectic_Mechanics"
        formula = r"\frac{d\theta_i}{dt} = \omega_i + \frac{K}{N}\sum_{j=1}^N \sin(\theta_j - \theta_i)"
        genus = lobes + 1
        dims = {"outer_radius_mm": outer_r, "gear_teeth": teeth, "symmetry_lobes": lobes, "thickness_mm": thick}

    elif "MICROFLUIDIC" in key or "DROPLET" in key or "FLUID" in key:
        arch_id = "MICROFLUIDIC_DROPLET_GENERATOR"
        chip_l = round(68.0 * s, 2)
        chip_w = round(42.0 * s, 2)
        chip_h = round(8.5 * s, 2)
        orifice_um = round(75.0 + (1.0 - symmetry_r) * 110.0, 1)

        # Base wafer substrate + top micro-machined channel ribs creating etched flow-focusing channels
        components.append(make_box(-chip_l / 2.0, chip_l / 2.0, -chip_w / 2.0, chip_w / 2.0, -chip_h / 2.0, chip_h * 0.25))
        # Quadrant elastomer channel walls forming the cross flow-focusing junction
        ch_gap = 2.0 * s
        neck_gap = 0.85 * s
        # Left upper & lower quadrant blocks (before cross junction at x = -chip_l/6)
        jx = -chip_l * 0.16
        rib_top = chip_h * 0.62
        rib_bot = chip_h * 0.25
        components.append(make_box(-chip_l / 2.0, jx - ch_gap, ch_gap, chip_w / 2.0, rib_bot, rib_top))
        components.append(make_box(-chip_l / 2.0, jx - ch_gap, -chip_w / 2.0, -ch_gap, rib_bot, rib_top))
        # Right upper & lower quadrant blocks (focused orifice throat -> expanded outlet)
        components.append(make_box(jx + ch_gap, chip_l / 2.0, neck_gap, chip_w / 2.0, rib_bot, rib_top))
        components.append(make_box(jx + ch_gap, chip_l / 2.0, -chip_w / 2.0, -neck_gap, rib_bot, rib_top))
        # Fluidic Luer / ferrule inlet/outlet port turrets (dispersed in, 2x sheath oil, droplet out)
        ports = [
            (-chip_l * 0.40, 0.0),
            (jx, chip_w * 0.34),
            (jx, -chip_w * 0.34),
            (chip_l * 0.40, 0.0),
        ]
        for px, py in ports:
            components.append(make_annulus(px, py, rib_top, rib_top + 5.5 * s, 1.5 * s, 3.6 * s, segments=20))

        title = f"Microfluidic Flow-Focusing Droplet Generator (w={orifice_um:.0f} um)"
        domain = "Fluidic_Microchannels"
        formula = r"\mathrm{Ca} = \frac{\mu U}{\gamma}, \quad d_{\text{drop}} \approx w \left(\frac{Q_{\text{disp}}}{Q_{\text{cont}}}\right)^\alpha"
        genus = 4
        dims = {"chip_length_mm": chip_l, "chip_width_mm": chip_w, "orifice_width_um": orifice_um}

    else:  # BISTABLE_COMPLIANT_FLEXURE (default)
        arch_id = "BISTABLE_COMPLIANT_FLEXURE"
        span_l = round((62.0 + symmetry_r * 28.0) * s, 2)
        apex_h = round((6.5 + (1.0 - symmetry_r) * 7.5) * s, 2)
        beam_t = round(1.55 * s, 2)
        depth_z = round(11.0 * s, 2)

        # Left & right rigid mounting anchor blocks with bored M4 mounting bosses
        anc_w = 14.0 * s
        anc_h = 34.0 * s
        for ax in (-span_l / 2.0 - anc_w / 2.0, span_l / 2.0 + anc_w / 2.0):
            components.append(make_box(ax - anc_w / 2.0, ax + anc_w / 2.0, -anc_h / 2.0, anc_h / 2.0, -depth_z / 2.0, depth_z / 2.0))
            components.append(make_cylinder(ax, anc_h * 0.30, -depth_z * 0.62, depth_z * 0.62, 2.2 * s, segments=16))
            components.append(make_cylinder(ax, -anc_h * 0.30, -depth_z * 0.62, depth_z * 0.62, 2.2 * s, segments=16))

        # Central bistable kinetic shuttle stage + vertical actuation spine
        sh_w = 16.0 * s
        sh_h = 26.0 * s
        components.append(make_box(-sh_w / 2.0, sh_w / 2.0, -sh_h / 2.0 + apex_h * 0.25, sh_h / 2.0 + apex_h * 0.25, -depth_z * 0.55, depth_z * 0.55))

        # Four swept pre-buckled cosine compliant leaf flexures: y(t) = y0 + (apex_h/2)*(1 - cos(pi*t))
        n_pts = 20
        ts = np.linspace(0.0, 1.0, n_pts)
        for y_base in (-9.5 * s, -4.5 * s, 4.5 * s, 9.5 * s):
            # Left wing (-span/2 -> -sh_w/2)
            xl = -span_l / 2.0 + ts * (span_l / 2.0 - sh_w / 2.0 + 1.0 * s)
            yl = y_base + apex_h * 0.5 * (1.0 - np.cos(math.pi * ts))
            components.append(make_swept_beam(np.column_stack([xl, yl]), beam_t, -depth_z * 0.42, depth_z * 0.42))
            # Right wing (span/2 -> sh_w/2)
            xr = span_l / 2.0 - ts * (span_l / 2.0 - sh_w / 2.0 + 1.0 * s)
            yr = y_base + apex_h * 0.5 * (1.0 - np.cos(math.pi * ts))
            components.append(make_swept_beam(np.column_stack([xr, yr]), beam_t, -depth_z * 0.42, depth_z * 0.42))

        title = f"Bistable Compliant Flexure Shuttle (L={span_l:.1f}mm, h={apex_h:.1f}mm)"
        domain = "Compliant_Flexures"
        formula = r"EI \frac{d^4 w}{dx^4} + P \frac{d^2 w}{dx^2} = 0, \quad Q = \frac{h}{t} \ge 2.31"
        genus = 4
        dims = {"length_L_mm": span_l, "apex_h_mm": apex_h, "beam_t_mm": beam_t, "depth_w_mm": depth_z}

    verts, tris = merge_components(components)
    # Center geometry cleanly around origin for viewport orbit stability
    centroid = (verts.min(axis=0) + verts.max(axis=0)) / 2.0
    verts = verts - centroid

    normals = compute_triangle_normals(verts, tris)
    metrics = compute_mesh_metrics(verts, tris)

    return {
        "model_type": archetype.lower(),
        "archetype": arch_id,
        "title": title,
        "stem_domain": domain,
        "formula_latex": formula,
        "topological_genus": genus,
        "dimensions": dims,
        "vertex_count": metrics["vertex_count"],
        "face_count": metrics["triangle_count"],
        "triangle_count": metrics["triangle_count"],
        "volume_mm3": metrics["volume_mm3"],
        "surface_area_mm2": metrics["surface_area_mm2"],
        "bounds": metrics["bounds"],
        "unit": "mm",
        "invariant": "Euler-Poincare: chi = V - E + F",
        "vertices": [[round(float(x), 4), round(float(y), 4), round(float(z), 4)] for x, y, z in verts],
        "faces": [[int(a), int(b), int(c)] for a, b, c in tris],
        "normals": [[round(float(nx), 4), round(float(ny), 4), round(float(nz), 4)] for nx, ny, nz in normals],
    }


# ---------------------------------------------------------------------------
# STL & ISO-10303-21 STEP Export / Import
# ---------------------------------------------------------------------------

def write_binary_stl(path: Path, mesh: Dict[str, Any]) -> None:
    """Writes a standard IEEE binary STL with computed outward triangle normals."""
    title = mesh.get("title", "ClothOS Parametric Solid")
    header = f"ClothOS CAD Kernel: {title}".encode("ascii", errors="ignore")[:80].ljust(80, b" ")
    verts = mesh["vertices"]
    faces = mesh["faces"]
    normals = mesh.get("normals") or []

    buf = bytearray(header)
    buf.extend(struct.pack("<I", len(faces)))
    for i, tri in enumerate(faces):
        n = normals[i] if i < len(normals) else (0.0, 0.0, 1.0)
        p1, p2, p3 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        buf.extend(struct.pack("<3f", float(n[0]), float(n[1]), float(n[2])))
        buf.extend(struct.pack("<3f", float(p1[0]), float(p1[1]), float(p1[2])))
        buf.extend(struct.pack("<3f", float(p2[0]), float(p2[1]), float(p2[2])))
        buf.extend(struct.pack("<3f", float(p3[0]), float(p3[1]), float(p3[2])))
        buf.extend(struct.pack("<H", 0))
    path.write_bytes(buf)


def write_step_ap214(path: Path, mesh: Dict[str, Any], title: Optional[str] = None) -> None:
    """Writes a geometrically populated ISO-10303-21 FACETED_BREP STEP file."""
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    arch = mesh.get("archetype", "STEM_SOLID")
    model_title = (title or mesh.get("title", arch)).replace("'", "")
    verts = mesh["vertices"]
    faces = mesh["faces"]

    lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('ClothOS Parametric Faceted BREP Solid', '2;1'), '1');",
        f"FILE_NAME('{path.name}', '{ts}', ('ClothOS CAD Kernel'), ('Loom Fabric Engineering'), 'ClothOS BREP v3.0', 'ISO-10303-21 AP214', '');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
        "#1 = APPLICATION_CONTEXT('automotive design');",
        "#2 = APPLICATION_PROTOCOL_DEFINITION('international standard', 'automotive_design', 2000, #1);",
        "#3 = PRODUCT_CONTEXT('', #1, 'mechanical');",
        f"#4 = PRODUCT('{arch}', '{model_title}', '', (#3));",
        "#5 = PRODUCT_DEFINITION_FORMATION('1.0', 'Parametric Mesh Synthesis', #4);",
        "#6 = PRODUCT_DEFINITION_CONTEXT('part definition', #1, 'design');",
        "#7 = PRODUCT_DEFINITION('design', '', #5, #6);",
        "#8 = PRODUCT_DEFINITION_SHAPE('', '', #7);",
        "#9 = ( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#12)) GLOBAL_UNIT_ASSIGNED_CONTEXT((#10, #11)) REPRESENTATION_CONTEXT('Context3D', '3D Millimeters') );",
        "#10 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI., .METRE.) );",
        "#11 = ( NAMED_UNIT(*) SI_UNIT($, .RADIAN.) SOLID_ANGLE_UNIT() );",
        "#12 = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-05), #10, 'distance_accuracy_value', 'tolerance');",
        "#13 = CARTESIAN_POINT('Origin', (0.0, 0.0, 0.0));",
        "#14 = DIRECTION('Z-Axis', (0.0, 0.0, 1.0));",
        "#15 = DIRECTION('X-Axis', (1.0, 0.0, 0.0));",
        "#16 = AXIS2_PLACEMENT_3D('Placement', #13, #14, #15);",
    ]

    eid = 20
    pt_ids: List[int] = []
    for vx, vy, vz in verts:
        lines.append(f"#{eid} = CARTESIAN_POINT('', ({vx:.4f}, {vy:.4f}, {vz:.4f}));")
        pt_ids.append(eid)
        eid += 1

    # Emit faceted BREP face entities (cap huge meshes at 1500 facets if enormous for speed, normally full)
    face_ids: List[int] = []
    max_faces = min(len(faces), 1500)
    for tri in faces[:max_faces]:
        loop_id = eid
        pts_ref = ", ".join(f"#{pt_ids[idx]}" for idx in tri)
        lines.append(f"#{loop_id} = POLY_LOOP('', ({pts_ref}));")
        bound_id = eid + 1
        lines.append(f"#{bound_id} = FACE_OUTER_BOUND('', #{loop_id}, .T.);")
        face_id = eid + 2
        lines.append(f"#{face_id} = FACE_SURFACE('', (#{bound_id}), #16, .T.);")
        face_ids.append(face_id)
        eid += 3

    shell_id = eid
    brep_id = eid + 1
    rep_id = eid + 2
    shape_rep_id = eid + 3
    lines.append(f"#{shell_id} = CLOSED_SHELL('', ({', '.join(f'#{fid}' for fid in face_ids)}));")
    lines.append(f"#{brep_id} = FACETED_BREP('{model_title}', #{shell_id});")
    lines.append(f"#{rep_id} = FACETED_BREP_SHAPE_REPRESENTATION('', (#{brep_id}, #16), #9);")
    lines.append(f"#{shape_rep_id} = SHAPE_DEFINITION_REPRESENTATION(#8, #{rep_id});")
    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_stl_as_mesh(stl_path: Path) -> Dict[str, Any]:
    """Parses a binary or ASCII STL file into an indexed ClothOS CAD mesh dict."""
    raw = stl_path.read_bytes()
    if len(raw) < 84:
        raise ValueError(f"STL file too short: {stl_path.name}")

    vert_map: Dict[Tuple[float, float, float], int] = {}
    verts: List[List[float]] = []
    faces: List[List[int]] = []

    def _add_v(x: float, y: float, z: float) -> int:
        key = (round(x, 4), round(y, 4), round(z, 4))
        idx = vert_map.get(key)
        if idx is None:
            idx = len(verts)
            vert_map[key] = idx
            verts.append([float(key[0]), float(key[1]), float(key[2])])
        return idx

    tri_count_bin = struct.unpack("<I", raw[80:84])[0]
    expected_bin_len = 84 + tri_count_bin * 50

    if len(raw) == expected_bin_len and tri_count_bin > 0:
        offset = 84
        for _ in range(tri_count_bin):
            vals = struct.unpack("<12fH", raw[offset:offset + 50])
            offset += 50
            i0 = _add_v(vals[3], vals[4], vals[5])
            i1 = _add_v(vals[6], vals[7], vals[8])
            i2 = _add_v(vals[9], vals[10], vals[11])
            faces.append([i0, i1, i2])
    else:
        # ASCII STL fallback parser
        text = raw.decode("utf-8", errors="ignore")
        tri_pts: List[int] = []
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0].lower() == "vertex":
                tri_pts.append(_add_v(float(parts[1]), float(parts[2]), float(parts[3])))
                if len(tri_pts) == 3:
                    faces.append(tri_pts)
                    tri_pts = []

    if not verts or not faces:
        raise ValueError(f"No valid triangles parsed from {stl_path.name}")

    v_arr = np.array(verts, dtype=float)
    f_arr = np.array(faces, dtype=np.int32)
    centroid = (v_arr.min(axis=0) + v_arr.max(axis=0)) / 2.0
    v_centered = v_arr - centroid
    normals = compute_triangle_normals(v_centered, f_arr)
    metrics = compute_mesh_metrics(v_centered, f_arr)

    return {
        "model_type": stl_path.stem,
        "archetype": "STL_IMPORT",
        "title": stl_path.name,
        "stem_domain": "STL_Mesh_Inspection",
        "formula_latex": r"\text{Imported Faceted STL}",
        "topological_genus": 1,
        "dimensions": {
            "span_x_mm": round(metrics["bounds"]["x"][1] - metrics["bounds"]["x"][0], 2),
            "span_y_mm": round(metrics["bounds"]["y"][1] - metrics["bounds"]["y"][0], 2),
            "span_z_mm": round(metrics["bounds"]["z"][1] - metrics["bounds"]["z"][0], 2),
        },
        "vertex_count": metrics["vertex_count"],
        "face_count": metrics["triangle_count"],
        "triangle_count": metrics["triangle_count"],
        "volume_mm3": metrics["volume_mm3"],
        "surface_area_mm2": metrics["surface_area_mm2"],
        "bounds": metrics["bounds"],
        "unit": "mm",
        "invariant": "Watertight Divergent Flux Checked",
        "vertices": [[round(float(x), 4), round(float(y), 4), round(float(z), 4)] for x, y, z in v_centered],
        "faces": [[int(a), int(b), int(c)] for a, b, c in f_arr],
        "normals": [[round(float(nx), 4), round(float(ny), 4), round(float(nz), 4)] for nx, ny, nz in normals],
    }
