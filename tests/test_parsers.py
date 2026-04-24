"""Tests for PDB and MAE parsers."""

from __future__ import annotations

import gzip
import textwrap
from pathlib import Path

import pytest

from molviz.parsers.pdb_parser import PDBParser
from molviz.parsers.mae_parser import MAEParser
from molviz.parsers.molecule import Atom, Bond, Molecule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_PDB = textwrap.dedent("""\
    ATOM      1  N   ALA A   1       1.000   2.000   3.000  1.00  5.00           N
    ATOM      2  CA  ALA A   1       2.500   2.000   3.000  1.00  5.00           C
    ATOM      3  C   ALA A   1       3.000   3.500   3.000  1.00  5.00           C
    ATOM      4  O   ALA A   1       2.200   4.500   3.000  1.00  5.00           O
    CONECT    1    2
    CONECT    2    3
    CONECT    3    4
    END
""")

MINIMAL_MAE = textwrap.dedent("""\
    { s_m_m2io_version }
     2.0.0

    f_m_ct {
      s_m_title = TestMol
      m_atom[4] {
        # First column block
        i_m_mmod_type
        r_m_x_coord
        r_m_y_coord
        r_m_z_coord
        s_m_element_symbol
        s_m_pdb_atom_name
        s_m_pdb_residue_name
        i_m_residue_number
        s_m_chain_name
        :::
        1    14    1.000    2.000    3.000    N    N    ALA    1    A
        2     1    2.500    2.000    3.000    C    CA    ALA    1    A
        3     1    3.000    3.500    3.000    C    C    ALA    1    A
        4     4    2.200    4.500    3.000    O    O    ALA    1    A
        :::
      }
      m_bond[3] {
        i_m_from
        i_m_to
        i_m_order
        :::
        1    1    2    1
        2    2    3    1
        3    3    4    2
        :::
      }
    }
""")


@pytest.fixture
def pdb_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.pdb"
    p.write_text(MINIMAL_PDB)
    return p


@pytest.fixture
def mae_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.mae"
    p.write_text(MINIMAL_MAE)
    return p


@pytest.fixture
def maegz_file(tmp_path: Path) -> Path:
    p = tmp_path / "test.maegz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write(MINIMAL_MAE)
    return p


# ---------------------------------------------------------------------------
# PDB parser tests
# ---------------------------------------------------------------------------

class TestPDBParser:
    def test_atom_count(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        assert mol.num_atoms == 4

    def test_element_parsed(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        elements = {a.element for a in mol.atoms}
        assert "N" in elements
        assert "C" in elements
        assert "O" in elements

    def test_coordinates(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        first = mol.atoms[0]
        assert first.x == pytest.approx(1.0, abs=0.001)
        assert first.y == pytest.approx(2.0, abs=0.001)
        assert first.z == pytest.approx(3.0, abs=0.001)

    def test_chain_id(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        assert all(a.chain_id == "A" for a in mol.atoms)

    def test_residue(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        assert all(a.residue_name == "ALA" for a in mol.atoms)

    def test_bonds_from_conect(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file, infer_bonds=False)
        assert mol.num_bonds == 3

    def test_source_format(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        assert mol.source_format == "pdb"

    def test_name_from_stem(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        assert mol.name == "test"

    def test_to_pdb_round_trip(self, pdb_file: Path) -> None:
        mol = PDBParser().parse(pdb_file)
        pdb_out = mol.to_pdb_string()
        assert "ATOM" in pdb_out
        assert "END" in pdb_out
        assert len(pdb_out.splitlines()) == mol.num_atoms + 1  # +1 for END

    def test_no_atoms_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.pdb"
        p.write_text("REMARK empty file\nEND\n")
        mol = PDBParser().parse(p)
        assert mol.num_atoms == 0

    def test_infer_bonds(self, tmp_path: Path) -> None:
        """Bonds should be inferred when no CONECT records present."""
        # Two C atoms at 1.54 Å apart – a typical C-C bond
        content = (
            "ATOM      1  C1  LIG A   1       0.000   0.000   0.000  1.00  0.00           C\n"
            "ATOM      2  C2  LIG A   1       1.540   0.000   0.000  1.00  0.00           C\n"
            "END\n"
        )
        p = tmp_path / "twoc.pdb"
        p.write_text(content)
        mol = PDBParser().parse(p, infer_bonds=True)
        assert mol.num_bonds == 1


# ---------------------------------------------------------------------------
# MAE parser tests
# ---------------------------------------------------------------------------

class TestMAEParser:
    def test_returns_list(self, mae_file: Path) -> None:
        mols = MAEParser().parse(mae_file)
        assert isinstance(mols, list)
        assert len(mols) >= 1

    def test_atom_count(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        assert mol.num_atoms == 4

    def test_bond_count(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        assert mol.num_bonds == 3

    def test_bond_order(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        # The third bond should have order 2
        orders = {(b.atom1_index, b.atom2_index): b.order for b in mol.bonds}
        assert orders.get((3, 4)) == 2

    def test_element_symbol(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        elements = {a.element for a in mol.atoms}
        assert "N" in elements
        assert "C" in elements
        assert "O" in elements

    def test_coordinates(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        first = mol.atoms[0]
        assert first.x == pytest.approx(1.0, abs=0.001)

    def test_molecule_name(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        assert mol.name == "TestMol"

    def test_source_format(self, mae_file: Path) -> None:
        mol = MAEParser().parse(mae_file)[0]
        assert mol.source_format == "mae"

    def test_maegz_parsing(self, maegz_file: Path) -> None:
        mols = MAEParser().parse(maegz_file)
        assert len(mols) >= 1
        assert mols[0].num_atoms == 4

    def test_maegz_same_as_mae(self, mae_file: Path, maegz_file: Path) -> None:
        mol_mae = MAEParser().parse(mae_file)[0]
        mol_gz = MAEParser().parse(maegz_file)[0]
        assert mol_mae.num_atoms == mol_gz.num_atoms
        assert mol_mae.num_bonds == mol_gz.num_bonds


# ---------------------------------------------------------------------------
# Molecule model tests
# ---------------------------------------------------------------------------

class TestMolecule:
    def test_centroid(self) -> None:
        atoms = [
            Atom(1, "C", "C", 0.0, 0.0, 0.0),
            Atom(2, "C", "C", 2.0, 0.0, 0.0),
            Atom(3, "C", "C", 1.0, 2.0, 0.0),
        ]
        mol = Molecule("test", atoms=atoms)
        cx, cy, cz = mol.centroid()
        assert cx == pytest.approx(1.0)
        assert cy == pytest.approx(2.0 / 3.0, abs=1e-6)
        assert cz == pytest.approx(0.0)

    def test_bounding_box(self) -> None:
        atoms = [
            Atom(1, "C", "C", -1.0, -2.0, -3.0),
            Atom(2, "C", "C",  4.0,  5.0,  6.0),
        ]
        mol = Molecule("bb", atoms=atoms)
        bb = mol.bounding_box()
        assert bb["xmin"] == -1.0
        assert bb["xmax"] == 4.0
        assert bb["ymin"] == -2.0
        assert bb["zmax"] == 6.0

    def test_chains(self) -> None:
        atoms = [
            Atom(1, "N", "N", 0, 0, 0, chain_id="A"),
            Atom(2, "C", "C", 1, 0, 0, chain_id="B"),
        ]
        mol = Molecule("ch", atoms=atoms)
        assert set(mol.chains) == {"A", "B"}

    def test_atom_by_index(self) -> None:
        atoms = [Atom(1, "N", "N", 0, 0, 0), Atom(5, "C", "C", 1, 0, 0)]
        mol = Molecule("idx", atoms=atoms)
        assert mol.atom_by_index(5) is not None
        assert mol.atom_by_index(5).element == "C"
        assert mol.atom_by_index(999) is None
