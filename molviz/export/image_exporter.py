"""Publication-quality image export for MolViz Studio."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Callable

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout
from PyQt6.QtWidgets import QLabel, QLineEdit, QSpinBox, QComboBox
from PyQt6.QtWidgets import QDialogButtonBox, QFileDialog, QCheckBox
from PyQt6.QtCore import Qt


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def data_url_to_bytes(data_url: str) -> bytes:
    """Convert a ``data:image/png;base64,...`` URL to raw PNG bytes."""
    match = re.match(r"data:[^;]+;base64,(.+)", data_url, re.DOTALL)
    if not match:
        raise ValueError("Invalid data URL")
    return base64.b64decode(match.group(1))


def save_image(data_url: str, output_path: str | Path, dpi: int = 300) -> Path:
    """
    Save the viewer screenshot to *output_path*.

    Supported formats: PNG, JPEG, TIFF (detected from suffix).
    *dpi* metadata is embedded when Pillow is available; otherwise the raw
    PNG is written directly.

    Returns the resolved output path.
    """
    output_path = Path(output_path)
    raw_bytes = data_url_to_bytes(data_url)

    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(raw_bytes))
        suffix = output_path.suffix.lower()
        fmt_map = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".tif": "TIFF", ".tiff": "TIFF"}
        pil_fmt = fmt_map.get(suffix, "PNG")

        save_kwargs: dict = {"dpi": (dpi, dpi)}
        if pil_fmt == "JPEG":
            save_kwargs["quality"] = 95
            save_kwargs["optimize"] = True
        elif pil_fmt == "PNG":
            save_kwargs["optimize"] = True

        img.save(output_path, format=pil_fmt, **save_kwargs)
    except ImportError:
        # Pillow not installed – write PNG bytes directly
        output_path.with_suffix(".png").write_bytes(raw_bytes)
        output_path = output_path.with_suffix(".png")

    return output_path


# ---------------------------------------------------------------------------
# Export dialog
# ---------------------------------------------------------------------------

class ExportImageDialog(QDialog):
    """Dialog for configuring and triggering a high-resolution image export."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Publication Image")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Output file
        file_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Click Browse to choose output file…")
        browse_btn = self._make_button("Browse…", self._browse)
        file_row.addWidget(self._path_edit)
        file_row.addWidget(browse_btn)
        form.addRow("Output file:", file_row)

        # Format
        self._fmt_combo = QComboBox()
        for fmt in ("PNG", "JPEG", "TIFF"):
            self._fmt_combo.addItem(fmt)
        form.addRow("Format:", self._fmt_combo)

        # Resolution
        self._width_spin = QSpinBox()
        self._width_spin.setRange(256, 8192)
        self._width_spin.setValue(2400)
        self._width_spin.setSuffix(" px")

        self._height_spin = QSpinBox()
        self._height_spin.setRange(256, 8192)
        self._height_spin.setValue(1800)
        self._height_spin.setSuffix(" px")

        res_row = QHBoxLayout()
        res_row.addWidget(self._width_spin)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self._height_spin)
        form.addRow("Resolution:", res_row)

        # DPI
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 1200)
        self._dpi_spin.setValue(300)
        self._dpi_spin.setSuffix(" DPI")
        form.addRow("Print DPI:", self._dpi_spin)

        # Transparent background (PNG only)
        self._transparent_cb = QCheckBox("Transparent background (PNG only)")
        form.addRow("", self._transparent_cb)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _make_button(text: str, slot) -> "QPushButton":  # type: ignore[name-defined]
        from PyQt6.QtWidgets import QPushButton
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        return btn

    def _browse(self) -> None:
        fmt = self._fmt_combo.currentText()
        filters = {
            "PNG": "PNG Images (*.png)",
            "JPEG": "JPEG Images (*.jpg *.jpeg)",
            "TIFF": "TIFF Images (*.tif *.tiff)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", filters.get(fmt, "Images (*)")
        )
        if path:
            self._path_edit.setText(path)

    # Public getters
    def output_path(self) -> str:
        return self._path_edit.text()

    def image_width(self) -> int:
        return self._width_spin.value()

    def image_height(self) -> int:
        return self._height_spin.value()

    def dpi(self) -> int:
        return self._dpi_spin.value()

    def transparent(self) -> bool:
        return self._transparent_cb.isChecked()
