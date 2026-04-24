"""Molecular geometry analysis: distances, angles, and dihedral angles."""

from __future__ import annotations

import math
from typing import Optional

from ..parsers.molecule import Atom, Molecule


def distance(a1: Atom, a2: Atom) -> float:
    """Euclidean distance in Ångströms between two atoms."""
    dx = a1.x - a2.x
    dy = a1.y - a2.y
    dz = a1.z - a2.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def angle(a1: Atom, a2: Atom, a3: Atom) -> float:
    """Valence angle a1–a2–a3 in degrees (vertex at a2)."""
    v1 = (a1.x - a2.x, a1.y - a2.y, a1.z - a2.z)
    v2 = (a3.x - a2.x, a3.y - a2.y, a3.z - a2.z)
    dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
    n1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2 + v1[2] ** 2)
    n2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2 + v2[2] ** 2)
    if n1 < 1e-10 or n2 < 1e-10:
        return 0.0
    cos_theta = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_theta))


def dihedral(a1: Atom, a2: Atom, a3: Atom, a4: Atom) -> float:
    """Dihedral (torsion) angle a1–a2–a3–a4 in degrees."""

    def sub(p: Atom, q: Atom) -> tuple[float, float, float]:
        return (p.x - q.x, p.y - q.y, p.z - q.z)

    def cross(u: tuple, v: tuple) -> tuple[float, float, float]:
        return (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )

    def dot(u: tuple, v: tuple) -> float:
        return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]

    def norm(u: tuple) -> float:
        return math.sqrt(dot(u, u))

    b1 = sub(a2, a1)
    b2 = sub(a3, a2)
    b3 = sub(a4, a3)

    n1 = cross(b1, b2)
    n2 = cross(b2, b3)
    m1 = cross(n1, b2)

    nb2 = norm(b2)
    if nb2 < 1e-10:
        return 0.0

    b2_hat = (b2[0] / nb2, b2[1] / nb2, b2[2] / nb2)
    x = dot(n1, n2)
    y = dot(m1, n2)
    return math.degrees(math.atan2(y, x))


def clash_score(molecule: Molecule, vdw_scale: float = 0.75) -> list[dict]:
    """
    Identify steric clashes (atom pairs closer than the sum of
    scaled van der Waals radii).

    Returns a list of dicts with keys: atom1, atom2, distance, clash.
    """
    _VDW: dict[str, float] = {
        "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80,
        "P": 1.80, "F": 1.47, "CL": 1.75, "BR": 1.85, "I": 1.98,
        "FE": 1.80, "ZN": 1.39, "MG": 1.73, "CA": 1.97,
    }
    default_vdw = 1.70

    atoms = molecule.atoms
    bonded: set[frozenset[int]] = {
        frozenset({b.atom1_index, b.atom2_index}) for b in molecule.bonds
    }
    clashes: list[dict] = []
    for i, a1 in enumerate(atoms):
        r1 = _VDW.get(a1.element.upper(), default_vdw) * vdw_scale
        for a2 in atoms[i + 1:]:
            pair = frozenset({a1.index, a2.index})
            if pair in bonded:
                continue
            r2 = _VDW.get(a2.element.upper(), default_vdw) * vdw_scale
            d = distance(a1, a2)
            if d < r1 + r2:
                clashes.append({
                    "atom1": a1,
                    "atom2": a2,
                    "distance": round(d, 3),
                    "clash": round(r1 + r2 - d, 3),
                })
    return clashes


def surface_area_estimate(molecule: Molecule) -> float:
    """
    Rough solvent-accessible surface area estimate (Lee–Richards-like,
    using a 1.4 Å probe radius).  Returns area in Å².
    """
    import math

    _VDW: dict[str, float] = {
        "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80,
        "P": 1.80, "F": 1.47,
    }
    probe = 1.4
    n_points = 92  # Fibonacci sphere points

    # Fibonacci sphere sampling
    golden = (1 + math.sqrt(5)) / 2
    sphere_pts: list[tuple[float, float, float]] = []
    for k in range(n_points):
        theta = math.acos(1 - 2 * (k + 0.5) / n_points)
        phi = 2 * math.pi * k / golden
        sphere_pts.append((
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta),
        ))

    total_area = 0.0
    for atom in molecule.atoms:
        r = _VDW.get(atom.element.upper(), 1.70) + probe
        exposed = 0
        for sx, sy, sz in sphere_pts:
            px = atom.x + r * sx
            py = atom.y + r * sy
            pz = atom.z + r * sz
            buried = False
            for other in molecule.atoms:
                if other.index == atom.index:
                    continue
                ro = _VDW.get(other.element.upper(), 1.70) + probe
                dx = px - other.x
                dy = py - other.y
                dz = pz - other.z
                if dx * dx + dy * dy + dz * dz < ro * ro:
                    buried = True
                    break
            if not buried:
                exposed += 1
        total_area += 4 * math.pi * r * r * exposed / n_points

    return round(total_area, 2)
