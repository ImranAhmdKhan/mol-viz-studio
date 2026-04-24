"""Side-panel showing molecule properties and atom list."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QSizePolicy, QGroupBox, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..parsers.molecule import Molecule


class PropertiesPanel(QWidget):
    """Displays molecule properties, atom table, and residue tree."""

    atomSelected = pyqtSignal(int)   # atom index

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(260)
        self.setMaximumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        tabs.addTab(self._build_summary_tab(), "Summary")
        tabs.addTab(self._build_atom_tab(), "Atoms")
        tabs.addTab(self._build_residue_tab(), "Residues")
        root.addWidget(tabs)

    # ------------------------------------------------------------------ #
    # Summary tab
    # ------------------------------------------------------------------ #

    def _build_summary_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Molecule")
        grp_lay = QVBoxLayout(grp)
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setFont(QFont("Courier", 10))
        self._summary_text.setPlaceholderText("Open a file to see structure summary…")
        grp_lay.addWidget(self._summary_text)
        lay.addWidget(grp)
        return w

    # ------------------------------------------------------------------ #
    # Atom table tab
    # ------------------------------------------------------------------ #

    def _build_atom_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._atom_table = QTableWidget(0, 7)
        self._atom_table.setHorizontalHeaderLabels(
            ["#", "Name", "Elem", "Chain", "Res", "SeqNo", "B-factor"]
        )
        hdr = self._atom_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._atom_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._atom_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._atom_table.verticalHeader().setVisible(False)
        self._atom_table.itemSelectionChanged.connect(self._on_atom_selection)
        lay.addWidget(self._atom_table)
        return w

    # ------------------------------------------------------------------ #
    # Residue tree tab
    # ------------------------------------------------------------------ #

    def _build_residue_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self._res_tree = QTreeWidget()
        self._res_tree.setHeaderLabels(["Chain / Residue", "Atoms"])
        self._res_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self._res_tree)
        return w

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def populate(self, molecule: Molecule) -> None:
        """Populate all tabs with data from *molecule*."""
        self._populate_summary(molecule)
        self._populate_atom_table(molecule)
        self._populate_residue_tree(molecule)

    def clear(self) -> None:
        self._summary_text.clear()
        self._atom_table.setRowCount(0)
        self._res_tree.clear()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _populate_summary(self, mol: Molecule) -> None:
        bb = mol.bounding_box()
        lines = [
            f"Name:      {mol.name}",
            f"Format:    {mol.source_format.upper()}",
            f"Atoms:     {mol.num_atoms}",
            f"Bonds:     {mol.num_bonds}",
            f"Chains:    {', '.join(mol.chains) or '—'}",
            f"Residues:  {len(mol.residue_names)}",
            "",
            "Bounding box (Å):",
            f"  X: {bb['xmin']:.2f} → {bb['xmax']:.2f}",
            f"  Y: {bb['ymin']:.2f} → {bb['ymax']:.2f}",
            f"  Z: {bb['zmin']:.2f} → {bb['zmax']:.2f}",
        ]
        if mol.properties:
            lines.append("")
            lines.append("Properties:")
            for k, v in list(mol.properties.items())[:12]:
                lines.append(f"  {k}: {v}")
        self._summary_text.setPlainText("\n".join(lines))

    def _populate_atom_table(self, mol: Molecule) -> None:
        self._atom_table.setRowCount(0)
        self._atom_table.setRowCount(len(mol.atoms))
        for row, atom in enumerate(mol.atoms):
            def _item(text: str) -> QTableWidgetItem:
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                return item

            self._atom_table.setItem(row, 0, _item(atom.index))
            self._atom_table.setItem(row, 1, _item(atom.name))
            self._atom_table.setItem(row, 2, _item(atom.element))
            self._atom_table.setItem(row, 3, _item(atom.chain_id))
            self._atom_table.setItem(row, 4, _item(atom.residue_name))
            self._atom_table.setItem(row, 5, _item(atom.residue_seq))
            self._atom_table.setItem(row, 6, _item(f"{atom.b_factor:.2f}"))
        self._atom_table.resizeRowsToContents()

    def _populate_residue_tree(self, mol: Molecule) -> None:
        self._res_tree.clear()
        # Build chain → residue → atoms mapping
        chain_map: dict[str, dict[tuple[str, int], list]] = {}
        for atom in mol.atoms:
            chain_map.setdefault(atom.chain_id, {})
            res_key = (atom.residue_name, atom.residue_seq)
            chain_map[atom.chain_id].setdefault(res_key, []).append(atom)

        for chain_id in sorted(chain_map):
            chain_item = QTreeWidgetItem(self._res_tree, [f"Chain {chain_id}", ""])
            chain_item.setExpanded(True)
            for (res_name, res_seq) in sorted(chain_map[chain_id]):
                atoms = chain_map[chain_id][(res_name, res_seq)]
                res_item = QTreeWidgetItem(chain_item,
                                           [f"{res_name} {res_seq}", str(len(atoms))])
        self._res_tree.expandAll()

    def _on_atom_selection(self) -> None:
        rows = self._atom_table.selectedItems()
        if rows:
            row = self._atom_table.row(rows[0])
            item = self._atom_table.item(row, 0)
            if item:
                try:
                    self.atomSelected.emit(int(item.text()))
                except ValueError:
                    pass
