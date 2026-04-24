"""PDB file parser."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .molecule import Atom, Bond, Molecule

# Standard covalent radii in Å used for bond inference when CONECT records
# are absent.
_COVALENT_RADII: dict[str, float] = {
    "H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "S": 1.05,
    "P": 1.07, "F": 0.57, "CL": 1.02, "BR": 1.20, "I": 1.39,
    "FE": 1.32, "ZN": 1.22, "MG": 1.41, "CA": 1.76, "NA": 1.66,
    "K": 2.03, "SE": 1.20, "CU": 1.32, "MN": 1.61, "CO": 1.26,
}
_DEFAULT_RADIUS = 0.77


def _cov_radius(element: str) -> float:
    return _COVALENT_RADII.get(element.upper(), _DEFAULT_RADIUS)


def _infer_bonds(atoms: list[Atom], tolerance: float = 0.45) -> list[Bond]:
    """Infer bonds based on covalent radii (O(n²) but adequate for typical structures)."""
    bonds: list[Bond] = []
    n = len(atoms)
    for i in range(n):
        a1 = atoms[i]
        r1 = _cov_radius(a1.element)
        for j in range(i + 1, n):
            a2 = atoms[j]
            # Skip same-residue check for large structures to keep it fast
            r2 = _cov_radius(a2.element)
            threshold = r1 + r2 + tolerance
            dx = a1.x - a2.x
            if abs(dx) > threshold:
                continue
            dy = a1.y - a2.y
            if abs(dy) > threshold:
                continue
            dz = a1.z - a2.z
            dist2 = dx * dx + dy * dy + dz * dz
            if dist2 < threshold * threshold:
                bonds.append(Bond(atom1_index=a1.index, atom2_index=a2.index))
    return bonds


class PDBParser:
    """Parse PDB-format files into a :class:`Molecule` object."""

    def parse(self, path: str | Path, infer_bonds: bool = True) -> Molecule:
        path = Path(path)
        molecule = Molecule(name=path.stem, source_format="pdb")
        atom_index = 1
        conect_map: dict[int, list[int]] = {}
        serial_to_index: dict[int, int] = {}

        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                record = line[:6].strip()

                if record in ("ATOM", "HETATM"):
                    try:
                        serial = int(line[6:11])
                        name = line[12:16].strip()
                        res_name = line[17:20].strip()
                        chain = line[21].strip() or "A"
                        res_seq = int(line[22:26])
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        occupancy = float(line[54:60]) if len(line) > 54 else 1.0
                        b_factor = float(line[60:66]) if len(line) > 60 else 0.0
                        element = line[76:78].strip() if len(line) > 76 else ""
                        if not element:
                            # Derive element from atom name
                            element = re.sub(r"[^A-Za-z]", "", name)[:2].strip()
                            if len(element) > 1 and element[0].isdigit():
                                element = element[1:]
                    except (ValueError, IndexError):
                        continue

                    atom = Atom(
                        index=atom_index,
                        name=name,
                        element=element.capitalize(),
                        x=x, y=y, z=z,
                        residue_name=res_name,
                        residue_seq=res_seq,
                        chain_id=chain,
                        b_factor=b_factor,
                        occupancy=occupancy,
                    )
                    molecule.atoms.append(atom)
                    serial_to_index[serial] = atom_index
                    atom_index += 1

                elif record == "CONECT":
                    serials = [int(line[i:i+5]) for i in range(6, min(len(line), 31), 5)
                               if line[i:i+5].strip()]
                    if len(serials) >= 2:
                        src = serials[0]
                        conect_map.setdefault(src, []).extend(serials[1:])

                elif record in ("COMPND", "TITLE"):
                    value = line[10:].strip()
                    if value:
                        key = "title" if record == "TITLE" else record.lower()
                        molecule.properties[key] = (
                            molecule.properties.get(key, "") + " " + value
                        ).strip()

        # Build bonds from CONECT records
        seen: set[frozenset[int]] = set()
        for src_serial, tgt_serials in conect_map.items():
            src_idx = serial_to_index.get(src_serial)
            if src_idx is None:
                continue
            for tgt_serial in tgt_serials:
                tgt_idx = serial_to_index.get(tgt_serial)
                if tgt_idx is None:
                    continue
                key = frozenset({src_idx, tgt_idx})
                if key not in seen:
                    seen.add(key)
                    molecule.bonds.append(Bond(atom1_index=src_idx, atom2_index=tgt_idx))

        if not molecule.bonds and infer_bonds:
            molecule.bonds = _infer_bonds(molecule.atoms)

        return molecule
