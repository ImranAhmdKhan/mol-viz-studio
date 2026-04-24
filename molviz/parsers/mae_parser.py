"""Schrodinger MAE / MAEGZ file parser.

The MAE (Maestro) format is a text-based hierarchical format.  The top level
consists of one or more "Content Tables" (``f_m_ct`` blocks).  Each block has:

    f_m_ct {
      <property-name> = <value>
      ...
      m_atom[<N>] {
        # First section: column definitions (one per line until :::)
        <col_name>
        ...
        :::
        # Second section: data rows (<N> rows, one per atom)
        <col_index> <v1> <v2> ... <vN>
        :::
      }
      m_bond[<M>] {
        <col_name>
        ...
        :::
        <col_index> <v1> ...
        :::
      }
    }

MAEGZ is simply a gzip-compressed MAE.
"""

from __future__ import annotations

import gzip
import re
from io import StringIO
from pathlib import Path
from typing import IO, Iterator

from .molecule import Atom, Bond, Molecule

# ---------------------------------------------------------------------------
# Tokeniser helpers
# ---------------------------------------------------------------------------

_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')
_TOKEN = re.compile(r'\S+')


def _tokenise_value(text: str) -> str:
    """Strip surrounding quotes and unescape a single value token."""
    text = text.strip()
    m = _QUOTED.fullmatch(text)
    if m:
        return m.group(1).replace('\\"', '"').replace("\\\\", "\\")
    return text


def _read_lines(fh: IO[str]) -> Iterator[str]:
    for raw in fh:
        line = raw.rstrip("\r\n")
        # Strip inline comments (# not inside a string literal)
        stripped = re.sub(r'(?<!["\w])#.*$', '', line).rstrip()
        if stripped:
            yield stripped


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------

class _MAEBlock:
    """Represents one f_m_ct or m_atom/m_bond sub-block."""

    def __init__(self, block_type: str, rows: list[dict], properties: dict):
        self.block_type = block_type
        self.rows = rows
        self.properties = properties


def _parse_table_block(lines: list[str]) -> tuple[list[str], list[dict]]:
    """Parse the column-defs + data-rows of an m_atom or m_bond table."""
    columns: list[str] = []
    rows: list[dict] = []
    phase = "cols"
    for line in lines:
        if line == ":::":
            if phase == "cols":
                phase = "data"
            else:
                break
            continue
        if phase == "cols":
            columns.append(line.strip())
        else:
            # Data row: first token is the row index (1-based), rest are values
            tokens = re.split(r'\s+(?=(?:[^"]*"[^"]*")*[^"]*$)', line.strip(), maxsplit=1)
            if len(tokens) < 2:
                continue
            values_str = tokens[1]
            # Split respecting quoted strings
            values = re.findall(r'"[^"]*"|\S+', values_str)
            row: dict = {}
            for col, val in zip(columns, values):
                row[col] = _tokenise_value(val)
            rows.append(row)
    return columns, rows


def _parse_ct_block(lines: list[str]) -> tuple[dict, list[_MAEBlock]]:
    """Parse one f_m_ct block, returning (properties, sub-blocks)."""
    properties: dict = {}
    sub_blocks: list[_MAEBlock] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        # Sub-block header, e.g. "m_atom[237] {"
        m = re.match(r'^(m_\w+)\[(\d+)\]\s*\{', line)
        if m:
            block_name = m.group(1)
            # Collect until the matching closing brace
            depth = 1
            block_lines: list[str] = []
            i += 1
            while i < n and depth > 0:
                bl = lines[i].strip()
                if bl.endswith("{"):
                    depth += 1
                elif bl == "}":
                    depth -= 1
                    if depth == 0:
                        break
                block_lines.append(bl)
                i += 1
            _, rows = _parse_table_block(block_lines)
            sub_blocks.append(_MAEBlock(block_name, rows, {}))

        elif "=" in line:
            # Simple property: key = value
            key, _, val = line.partition("=")
            properties[key.strip()] = _tokenise_value(val.strip())

        i += 1

    return properties, sub_blocks


# ---------------------------------------------------------------------------
# Public parser class
# ---------------------------------------------------------------------------

_ELEMENT_FROM_NAME = re.compile(r'^([A-Za-z]+)')


def _element_from_atom_name(name: str) -> str:
    m = _ELEMENT_FROM_NAME.match(name.strip())
    return m.group(1).capitalize() if m else "C"


class MAEParser:
    """Parse Maestro (.mae) and compressed Maestro (.maegz) files."""

    def parse(self, path: str | Path) -> list[Molecule]:
        path = Path(path)
        if path.suffix.lower() == ".maegz":
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        else:
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()

        return self._parse_string(content, stem=path.stem)

    def _parse_string(self, content: str, stem: str = "mol") -> list[Molecule]:
        molecules: list[Molecule] = []
        lines = [ln for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        i = 0
        n = len(lines)
        ct_index = 0

        while i < n:
            line = lines[i].strip()

            # Look for f_m_ct { opening
            if line == "f_m_ct {" or line.startswith("f_m_ct {"):
                # Collect until matching closing brace
                depth = 1
                ct_lines: list[str] = []
                i += 1
                while i < n and depth > 0:
                    cl = lines[i].strip()
                    if cl.endswith("{"):
                        depth += 1
                    elif cl == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    ct_lines.append(cl)
                    i += 1
                mol = self._ct_to_molecule(ct_lines, f"{stem}_{ct_index}")
                if mol:
                    ct_index += 1
                    molecules.append(mol)
            i += 1

        return molecules

    def _ct_to_molecule(self, ct_lines: list[str], name: str) -> Molecule | None:
        props, sub_blocks = _parse_ct_block(ct_lines)

        mol_name = props.get("s_m_title", props.get("s_m_entry_name", name))
        molecule = Molecule(name=mol_name, properties=dict(props), source_format="mae")

        atom_block = next((b for b in sub_blocks if b.block_type == "m_atom"), None)
        bond_block = next((b for b in sub_blocks if b.block_type == "m_bond"), None)

        if atom_block is None:
            return None

        for idx, row in enumerate(atom_block.rows, start=1):
            try:
                x = float(row.get("r_m_x_coord", row.get("r_m_pdb_x", "0")))
                y = float(row.get("r_m_y_coord", row.get("r_m_pdb_y", "0")))
                z = float(row.get("r_m_z_coord", row.get("r_m_pdb_z", "0")))
            except ValueError:
                x = y = z = 0.0

            element = row.get("s_m_element_symbol", "")
            if not element:
                atom_name_raw = row.get("s_m_pdb_atom_name", row.get("s_m_atom_name", f"X{idx}"))
                element = _element_from_atom_name(atom_name_raw)

            atom_name = row.get("s_m_pdb_atom_name", row.get("s_m_atom_name", element + str(idx))).strip()
            res_name = row.get("s_m_pdb_residue_name", "LIG").strip()
            chain = row.get("s_m_chain_name", "A").strip() or "A"
            try:
                res_seq = int(row.get("i_m_residue_number", "1"))
            except ValueError:
                res_seq = 1

            try:
                charge = float(row.get("r_m_charge1", row.get("r_m_formal_charge", "0")))
            except ValueError:
                charge = 0.0

            atom = Atom(
                index=idx,
                name=atom_name,
                element=element.capitalize(),
                x=x, y=y, z=z,
                residue_name=res_name,
                residue_seq=res_seq,
                chain_id=chain,
                charge=charge,
                properties={k: v for k, v in row.items()},
            )
            molecule.atoms.append(atom)

        if bond_block:
            for row in bond_block.rows:
                try:
                    a1 = int(row.get("i_m_from", "0"))
                    a2 = int(row.get("i_m_to", "0"))
                    order = int(row.get("i_m_order", "1"))
                    if a1 and a2:
                        molecule.bonds.append(Bond(atom1_index=a1, atom2_index=a2, order=order))
                except ValueError:
                    continue

        return molecule
