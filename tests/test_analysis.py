"""Tests for analysis/measurement functions."""

from __future__ import annotations

import math

import pytest

from molviz.parsers.molecule import Atom, Bond, Molecule
from molviz.analysis.measurements import distance, angle, dihedral, clash_score


def _atom(idx: int, x: float, y: float, z: float, elem: str = "C") -> Atom:
    return Atom(idx, elem, elem, x, y, z)


class TestDistance:
    def test_zero(self) -> None:
        a = _atom(1, 0, 0, 0)
        assert distance(a, a) == pytest.approx(0.0)

    def test_simple(self) -> None:
        a = _atom(1, 0, 0, 0)
        b = _atom(2, 3, 4, 0)
        assert distance(a, b) == pytest.approx(5.0)

    def test_3d(self) -> None:
        a = _atom(1, 1, 2, 3)
        b = _atom(2, 4, 6, 3)
        assert distance(a, b) == pytest.approx(5.0)

    def test_symmetric(self) -> None:
        a = _atom(1, 1, 2, 3)
        b = _atom(2, 7, 8, 9)
        assert distance(a, b) == pytest.approx(distance(b, a))

    def test_typical_cc_bond(self) -> None:
        a = _atom(1, 0.0, 0.0, 0.0)
        b = _atom(2, 1.54, 0.0, 0.0)
        assert distance(a, b) == pytest.approx(1.54, abs=0.001)


class TestAngle:
    def test_right_angle(self) -> None:
        a1 = _atom(1, 1, 0, 0)
        vertex = _atom(2, 0, 0, 0)
        a3 = _atom(3, 0, 1, 0)
        assert angle(a1, vertex, a3) == pytest.approx(90.0, abs=0.001)

    def test_straight_line(self) -> None:
        a1 = _atom(1, -1, 0, 0)
        vertex = _atom(2, 0, 0, 0)
        a3 = _atom(3, 1, 0, 0)
        assert angle(a1, vertex, a3) == pytest.approx(180.0, abs=0.001)

    def test_zero_angle(self) -> None:
        a1 = _atom(1, 1, 0, 0)
        vertex = _atom(2, 0, 0, 0)
        a3 = _atom(3, 2, 0, 0)
        assert angle(a1, vertex, a3) == pytest.approx(0.0, abs=0.001)

    def test_tetrahedral(self) -> None:
        """Carbon tetrahedral angle ≈ 109.47°"""
        # Approximate methane geometry
        a1 = _atom(1,  1,  1,  1)
        v  = _atom(2,  0,  0,  0)
        a3 = _atom(3, -1, -1,  1)
        ang = angle(a1, v, a3)
        assert abs(ang - 109.47) < 0.1


class TestDihedral:
    def test_trans(self) -> None:
        """Trans (180°) configuration."""
        a1 = _atom(1, -1,  1, 0)
        a2 = _atom(2, -1,  0, 0)
        a3 = _atom(3,  1,  0, 0)
        a4 = _atom(4,  1, -1, 0)
        d = dihedral(a1, a2, a3, a4)
        assert abs(d) == pytest.approx(180.0, abs=0.001)

    def test_cis(self) -> None:
        """Cis (0°) configuration."""
        a1 = _atom(1, -1,  1, 0)
        a2 = _atom(2, -1,  0, 0)
        a3 = _atom(3,  1,  0, 0)
        a4 = _atom(4,  1,  1, 0)
        d = dihedral(a1, a2, a3, a4)
        assert abs(d) == pytest.approx(0.0, abs=0.001)


class TestClashScore:
    def test_no_clashes_when_far(self) -> None:
        atoms = [_atom(1, 0, 0, 0), _atom(2, 10, 0, 0)]
        mol = Molecule("test", atoms=atoms, bonds=[Bond(1, 2)])
        clashes = clash_score(mol)
        assert len(clashes) == 0

    def test_clash_detected(self) -> None:
        # Two carbons at 0.5 Å (well within VDW threshold)
        atoms = [_atom(1, 0, 0, 0), _atom(2, 0.5, 0, 0)]
        mol = Molecule("test", atoms=atoms)
        clashes = clash_score(mol)
        assert len(clashes) == 1
        assert clashes[0]["distance"] == pytest.approx(0.5, abs=0.001)

    def test_bonded_atoms_not_clashed(self) -> None:
        atoms = [_atom(1, 0, 0, 0), _atom(2, 0.5, 0, 0)]
        mol = Molecule("test", atoms=atoms, bonds=[Bond(1, 2)])
        clashes = clash_score(mol)
        assert len(clashes) == 0
