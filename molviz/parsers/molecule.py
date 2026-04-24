"""Molecule data model used across the application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Atom:
    """Represents a single atom in a molecular structure."""

    index: int
    name: str
    element: str
    x: float
    y: float
    z: float
    residue_name: str = ""
    residue_seq: int = 0
    chain_id: str = "A"
    b_factor: float = 0.0
    occupancy: float = 1.0
    charge: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class Bond:
    """Represents a covalent bond between two atoms."""

    atom1_index: int
    atom2_index: int
    order: int = 1  # 1=single, 2=double, 3=triple, 4=aromatic


@dataclass
class Molecule:
    """Container for a parsed molecular structure."""

    name: str
    atoms: List[Atom] = field(default_factory=list)
    bonds: List[Bond] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    source_format: str = ""

    # ------------------------------------------------------------------ #
    # Derived properties
    # ------------------------------------------------------------------ #

    @property
    def num_atoms(self) -> int:
        return len(self.atoms)

    @property
    def num_bonds(self) -> int:
        return len(self.bonds)

    @property
    def chains(self) -> List[str]:
        return sorted({a.chain_id for a in self.atoms})

    @property
    def residue_names(self) -> List[str]:
        return sorted({a.residue_name for a in self.atoms if a.residue_name})

    def atom_by_index(self, index: int) -> Optional[Atom]:
        for atom in self.atoms:
            if atom.index == index:
                return atom
        return None

    def centroid(self) -> tuple[float, float, float]:
        """Return the geometric centroid of all atoms."""
        if not self.atoms:
            return (0.0, 0.0, 0.0)
        n = len(self.atoms)
        cx = sum(a.x for a in self.atoms) / n
        cy = sum(a.y for a in self.atoms) / n
        cz = sum(a.z for a in self.atoms) / n
        return (cx, cy, cz)

    def bounding_box(self) -> Dict[str, float]:
        """Return axis-aligned bounding box."""
        if not self.atoms:
            return {"xmin": 0, "xmax": 0, "ymin": 0, "ymax": 0, "zmin": 0, "zmax": 0}
        xs = [a.x for a in self.atoms]
        ys = [a.y for a in self.atoms]
        zs = [a.z for a in self.atoms]
        return {
            "xmin": min(xs), "xmax": max(xs),
            "ymin": min(ys), "ymax": max(ys),
            "zmin": min(zs), "zmax": max(zs),
        }

    def to_pdb_string(self) -> str:
        """Serialise back to PDB format for passing to 3Dmol.js."""
        lines: List[str] = []
        for atom in self.atoms:
            elem = atom.element.upper().rjust(2)
            lines.append(
                f"ATOM  {atom.index:5d} {atom.name:<4s}{atom.residue_name:>3s} "
                f"{atom.chain_id}{atom.residue_seq:4d}    "
                f"{atom.x:8.3f}{atom.y:8.3f}{atom.z:8.3f}"
                f"{atom.occupancy:6.2f}{atom.b_factor:6.2f}          {elem}"
            )
        lines.append("END")
        return "\n".join(lines)
