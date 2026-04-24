"""Custom dialogs for MolViz Studio."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QDialogButtonBox, QPushButton, QColorDialog, QCheckBox,
    QTextEdit, QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..annotations.annotation_manager import Annotation, AnnotationType


class AddAnnotationDialog(QDialog):
    """Dialog for creating a new annotation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Annotation")
        self.setMinimumWidth(400)
        self._color = "#FFD700"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Type
        self._type_combo = QComboBox()
        for t in AnnotationType:
            self._type_combo.addItem(t.value.capitalize(), t)
        self._type_combo.currentIndexChanged.connect(self._update_visibility)
        form.addRow("Type:", self._type_combo)

        # Label text
        self._label_edit = QLineEdit()
        form.addRow("Label text:", self._label_edit)

        # Primary position
        self._x_spin = self._make_coord_spin()
        self._y_spin = self._make_coord_spin()
        self._z_spin = self._make_coord_spin()
        pos_row = self._row_of(self._x_spin, QLabel("Y:"), self._y_spin, QLabel("Z:"), self._z_spin)
        form.addRow("Position (Å):", pos_row)

        # Secondary position (for arrow/distance)
        self._x2_spin = self._make_coord_spin()
        self._y2_spin = self._make_coord_spin()
        self._z2_spin = self._make_coord_spin()
        pos2_row = self._row_of(self._x2_spin, QLabel("Y:"), self._y2_spin, QLabel("Z:"), self._z2_spin)
        self._pos2_label = QLabel("End point (Å):")
        form.addRow(self._pos2_label, pos2_row)

        # Colour
        self._color_btn = QPushButton("Choose colour")
        self._color_btn.setStyleSheet(f"background-color: {self._color};")
        self._color_btn.clicked.connect(self._pick_color)
        form.addRow("Colour:", self._color_btn)

        # Font size
        self._font_spin = QSpinBox()
        self._font_spin.setRange(6, 72)
        self._font_spin.setValue(14)
        form.addRow("Font size:", self._font_spin)

        # Bold
        self._bold_cb = QCheckBox()
        form.addRow("Bold:", self._bold_cb)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_visibility()

    @staticmethod
    def _make_coord_spin() -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(-9999.0, 9999.0)
        sp.setDecimals(3)
        sp.setValue(0.0)
        return sp

    @staticmethod
    def _row_of(*widgets) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        for wgt in widgets:
            lay.addWidget(wgt)
        return w

    def _update_visibility(self) -> None:
        ann_type: AnnotationType = self._type_combo.currentData()
        show_p2 = ann_type in (AnnotationType.ARROW, AnnotationType.DISTANCE)
        self._pos2_label.setVisible(show_p2)
        self._x2_spin.parentWidget().setVisible(show_p2)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Choose Annotation Colour")
        if color.isValid():
            self._color = color.name()
            self._color_btn.setStyleSheet(f"background-color: {self._color};")

    def get_annotation(self) -> Annotation:
        ann_type: AnnotationType = self._type_combo.currentData()
        return Annotation(
            ann_type=ann_type,
            label=self._label_edit.text(),
            x=self._x_spin.value(),
            y=self._y_spin.value(),
            z=self._z_spin.value(),
            x2=self._x2_spin.value(),
            y2=self._y2_spin.value(),
            z2=self._z2_spin.value(),
            color=self._color,
            font_size=self._font_spin.value(),
            bold=self._bold_cb.isChecked(),
            visible=True,
        )


class MeasurementResultsDialog(QDialog):
    """Shows accumulated measurement results."""

    def __init__(self, results: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Measurement Results")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        lines: list[str] = []
        for r in results:
            t = r.get("type", "?")
            v = r.get("result", "?")
            atoms = r.get("atoms", [])
            atom_str = " – ".join(
                f"{a.get('atom','?')}({a.get('resn','?')}{a.get('resi','?')}{a.get('chain','?')})"
                for a in atoms
            )
            lines.append(f"{t.capitalize():12s}  {v:>14s}   {atom_str}")
        text.setPlainText("\n".join(lines) if lines else "No measurements yet.")
        lay.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
