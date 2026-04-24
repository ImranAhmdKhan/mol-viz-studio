"""Main application window for MolViz Studio."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QToolBar, QStatusBar,
    QDockWidget, QMessageBox, QFileDialog, QApplication,
    QLabel, QComboBox, QColorDialog, QPushButton, QActionGroup,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QColor, QFont, QPalette,
)

from .viewer.pymol_viewer import PyMOLViewer as MolViewer
from .parsers.pdb_parser import PDBParser
from .parsers.mae_parser import MAEParser
from .parsers.molecule import Molecule
from .annotations.annotation_manager import Annotation, AnnotationType
from .export.image_exporter import ExportImageDialog, save_image
from .ui.properties_panel import PropertiesPanel
from .ui.dialogs import AddAnnotationDialog, MeasurementResultsDialog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUPPORTED_FILE_FILTER = (
    "Molecular Structures (*.pdb *.mae *.maegz);;"
    "PDB Files (*.pdb);;"
    "MAE Files (*.mae);;"
    "MAEGZ Files (*.maegz);;"
    "All Files (*)"
)


def _icon_from_text(text: str) -> QIcon:
    """Fallback text-based icon when no icon files are available."""
    from PyQt6.QtGui import QPixmap, QPainter, QBrush
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Central window that hosts the 3-D viewer and all tooling."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MolViz Studio")
        self.resize(1400, 860)

        self._molecule: Optional[Molecule] = None
        self._measurement_results: list[dict] = []

        # Apply dark palette
        self._apply_dark_palette()

        # Central viewer
        self._viewer = MolViewer(self)
        self._viewer.measurementReady.connect(self._on_measurement)
        self._viewer.viewerReady.connect(self._on_viewer_ready)

        # Properties panel (dock)
        self._props = PropertiesPanel()
        dock = QDockWidget("Properties", self)
        dock.setWidget(self._props)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.setCentralWidget(self._viewer)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("Ready – open a molecular file to begin")
        self._status.addWidget(self._status_label, 1)

        # Build menus & toolbars
        self._build_menu_bar()
        self._build_toolbars()

    # ------------------------------------------------------------------ #
    # Dark palette
    # ------------------------------------------------------------------ #

    def _apply_dark_palette(self) -> None:
        pal = QPalette()
        dark = QColor(30, 30, 46)
        mid = QColor(49, 50, 68)
        bright = QColor(205, 214, 244)
        accent = QColor(116, 199, 236)
        pal.setColor(QPalette.ColorRole.Window, dark)
        pal.setColor(QPalette.ColorRole.WindowText, bright)
        pal.setColor(QPalette.ColorRole.Base, QColor(24, 24, 37))
        pal.setColor(QPalette.ColorRole.AlternateBase, mid)
        pal.setColor(QPalette.ColorRole.ToolTipBase, mid)
        pal.setColor(QPalette.ColorRole.ToolTipText, bright)
        pal.setColor(QPalette.ColorRole.Text, bright)
        pal.setColor(QPalette.ColorRole.Button, mid)
        pal.setColor(QPalette.ColorRole.ButtonText, bright)
        pal.setColor(QPalette.ColorRole.Link, accent)
        pal.setColor(QPalette.ColorRole.Highlight, accent)
        pal.setColor(QPalette.ColorRole.HighlightedText, dark)
        self.setPalette(pal)

    # ------------------------------------------------------------------ #
    # Menu bar
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        # ---- File --------------------------------------------------------
        file_menu = mb.addMenu("&File")
        open_act = QAction("&Open…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.setStatusTip("Open a PDB, MAE, or MAEGZ molecular structure file")
        open_act.triggered.connect(self._open_file)
        file_menu.addAction(open_act)

        file_menu.addSeparator()
        export_img_act = QAction("Export &Image…", self)
        export_img_act.setShortcut("Ctrl+E")
        export_img_act.setStatusTip("Export a publication-quality image of the current view")
        export_img_act.triggered.connect(self._export_image)
        file_menu.addAction(export_img_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(quit_act)

        # ---- View --------------------------------------------------------
        view_menu = mb.addMenu("&View")

        style_menu = view_menu.addMenu("Representation")
        for label, style in [
            ("Cartoon", "cartoon"), ("Stick", "stick"),
            ("Ball and Stick", "ballstick"), ("Sphere", "sphere"),
            ("Line", "line"), ("Molecular Surface", "surface"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked, s=style: self._set_style(s))
            style_menu.addAction(act)

        color_menu = view_menu.addMenu("Color Scheme")
        for label, scheme in [
            ("Chain / Heteroatom", "chainHetatm"),
            ("Element (Jmol)", "element"),
            ("B-factor", "bfactor"),
            ("Residue", "residue"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked, s=scheme: self._set_color_scheme(s))
            color_menu.addAction(act)

        view_menu.addSeparator()
        bg_act = QAction("&Background Colour…", self)
        bg_act.triggered.connect(self._pick_background)
        view_menu.addAction(bg_act)

        view_menu.addSeparator()
        reset_act = QAction("&Reset View", self)
        reset_act.setShortcut("Ctrl+R")
        reset_act.triggered.connect(self._viewer.reset_view)
        view_menu.addAction(reset_act)

        spin_act = QAction("&Spin", self, checkable=True)
        spin_act.triggered.connect(lambda on: self._viewer.spin(on))
        view_menu.addAction(spin_act)

        # ---- Analysis ----------------------------------------------------
        analysis_menu = mb.addMenu("&Analysis")

        measure_menu = analysis_menu.addMenu("&Measure")
        dist_act = QAction("&Distance  (2 atoms)", self)
        dist_act.triggered.connect(lambda: self._viewer.set_measure_mode("distance"))
        measure_menu.addAction(dist_act)

        angle_act = QAction("&Angle  (3 atoms)", self)
        angle_act.triggered.connect(lambda: self._viewer.set_measure_mode("angle"))
        measure_menu.addAction(angle_act)

        dihedral_act = QAction("&Dihedral  (4 atoms)", self)
        dihedral_act.triggered.connect(lambda: self._viewer.set_measure_mode("dihedral"))
        measure_menu.addAction(dihedral_act)

        stop_measure_act = QAction("Stop Measuring", self)
        stop_measure_act.triggered.connect(lambda: self._viewer.set_measure_mode(None))
        measure_menu.addAction(stop_measure_act)

        analysis_menu.addSeparator()
        clear_meas_act = QAction("&Clear Measurements", self)
        clear_meas_act.triggered.connect(self._viewer.clear_measurements)
        analysis_menu.addAction(clear_meas_act)

        show_meas_act = QAction("Show &Results…", self)
        show_meas_act.triggered.connect(self._show_measurements)
        analysis_menu.addAction(show_meas_act)

        # ---- Annotations -------------------------------------------------
        ann_menu = mb.addMenu("A&nnotations")

        add_ann_act = QAction("&Add Annotation…", self)
        add_ann_act.setShortcut("Ctrl+Shift+A")
        add_ann_act.triggered.connect(self._add_annotation)
        ann_menu.addAction(add_ann_act)

        clear_ann_act = QAction("&Clear All Annotations", self)
        clear_ann_act.triggered.connect(self._viewer.clear_annotations)
        ann_menu.addAction(clear_ann_act)

        # ---- Help --------------------------------------------------------
        help_menu = mb.addMenu("&Help")
        about_act = QAction("&About MolViz Studio", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------ #
    # Toolbars
    # ------------------------------------------------------------------ #

    def _build_toolbars(self) -> None:
        # ---- File toolbar ------------------------------------------------
        tb = QToolBar("File", self)
        tb.setIconSize(QSize(28, 28))
        tb.setObjectName("tb_file")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open a molecular file (.pdb, .mae, .maegz)")
        open_btn.clicked.connect(self._open_file)
        tb.addWidget(open_btn)

        export_btn = QPushButton("🖼 Export")
        export_btn.setToolTip("Export publication-quality image")
        export_btn.clicked.connect(self._export_image)
        tb.addWidget(export_btn)

        tb.addSeparator()

        # ---- Style toolbar -----------------------------------------------
        tb2 = QToolBar("View Style", self)
        tb2.setObjectName("tb_style")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb2)
        tb2.addWidget(QLabel("  Style: "))

        self._style_combo = QComboBox()
        for label, val in [
            ("Cartoon", "cartoon"), ("Stick", "stick"),
            ("Ball+Stick", "ballstick"), ("Sphere", "sphere"),
            ("Line", "line"), ("Surface", "surface"),
        ]:
            self._style_combo.addItem(label, val)
        self._style_combo.currentIndexChanged.connect(
            lambda _: self._set_style(self._style_combo.currentData())
        )
        tb2.addWidget(self._style_combo)

        tb2.addWidget(QLabel("  Color: "))
        self._color_combo = QComboBox()
        for label, val in [
            ("Chain/Hetatm", "chainHetatm"), ("Element", "element"),
            ("B-factor", "bfactor"), ("Residue", "residue"),
        ]:
            self._color_combo.addItem(label, val)
        self._color_combo.currentIndexChanged.connect(
            lambda _: self._set_color_scheme(self._color_combo.currentData())
        )
        tb2.addWidget(self._color_combo)

        reset_btn = QPushButton("⟳ Reset")
        reset_btn.setToolTip("Reset to default view")
        reset_btn.clicked.connect(self._viewer.reset_view)
        tb2.addWidget(reset_btn)

        tb2.addSeparator()

        # ---- Measurement toolbar ----------------------------------------
        tb3 = QToolBar("Measurements", self)
        tb3.setObjectName("tb_measure")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb3)
        tb3.addWidget(QLabel("  Measure: "))

        dist_btn = QPushButton("📏 Distance")
        dist_btn.setToolTip("Measure distance between two atoms (click 2 atoms)")
        dist_btn.clicked.connect(lambda: self._viewer.set_measure_mode("distance"))
        tb3.addWidget(dist_btn)

        angle_btn = QPushButton("∠ Angle")
        angle_btn.setToolTip("Measure angle formed by three atoms (click 3 atoms)")
        angle_btn.clicked.connect(lambda: self._viewer.set_measure_mode("angle"))
        tb3.addWidget(angle_btn)

        dihedral_btn = QPushButton("↻ Dihedral")
        dihedral_btn.setToolTip("Measure dihedral angle of four atoms (click 4 atoms)")
        dihedral_btn.clicked.connect(lambda: self._viewer.set_measure_mode("dihedral"))
        tb3.addWidget(dihedral_btn)

        stop_btn = QPushButton("✕ Stop")
        stop_btn.setToolTip("Stop measuring")
        stop_btn.clicked.connect(lambda: self._viewer.set_measure_mode(None))
        tb3.addWidget(stop_btn)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setToolTip("Clear all measurements")
        clear_btn.clicked.connect(self._viewer.clear_measurements)
        tb3.addWidget(clear_btn)

        tb3.addSeparator()

        ann_btn = QPushButton("🏷 Annotate")
        ann_btn.setToolTip("Add a text annotation, label, or arrow")
        ann_btn.clicked.connect(self._add_annotation)
        tb3.addWidget(ann_btn)

    # ------------------------------------------------------------------ #
    # Slots / callbacks
    # ------------------------------------------------------------------ #

    def _on_viewer_ready(self) -> None:
        self._set_status("3D viewer ready")

    def _on_measurement(self, mtype: str, result: str) -> None:
        self._measurement_results.append({"type": mtype, "result": result, "atoms": []})
        self._set_status(f"{mtype.capitalize()}: {result}")

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    # ------------------------------------------------------------------ #
    # File I/O
    # ------------------------------------------------------------------ #

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Molecular Structure", "",
            SUPPORTED_FILE_FILTER,
        )
        if not path:
            return
        self._load_file(Path(path))

    def _load_file(self, path: Path) -> None:
        self._set_status(f"Loading {path.name}…")
        QApplication.processEvents()

        suffix = path.suffix.lower()
        try:
            if suffix == ".pdb":
                parser = PDBParser()
                mol = parser.parse(path)
                self._set_molecule(mol)
            elif suffix in (".mae", ".maegz"):
                parser = MAEParser()
                mols = parser.parse(path)
                if not mols:
                    QMessageBox.warning(self, "No Structures",
                                        f"No structures found in {path.name}.")
                    return
                # Load first structure; TODO: multi-structure selector
                mol = mols[0]
                if len(mols) > 1:
                    self._set_status(
                        f"Loaded {len(mols)} structures from {path.name}; showing first."
                    )
                self._set_molecule(mol)
            else:
                QMessageBox.warning(self, "Unsupported Format",
                                    f"Cannot open '{path.suffix}' files.\n"
                                    "Supported: .pdb, .mae, .maegz")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error",
                                 f"Failed to load {path.name}:\n{exc}")
            self._set_status("Load failed")
            return

    def _set_molecule(self, mol: Molecule) -> None:
        self._molecule = mol
        self._viewer.load_molecule(mol)
        self._props.populate(mol)
        self._set_status(
            f"Loaded '{mol.name}' — {mol.num_atoms} atoms, "
            f"{mol.num_bonds} bonds, chains: {', '.join(mol.chains)}"
        )
        self.setWindowTitle(f"MolViz Studio — {mol.name}")

    # ------------------------------------------------------------------ #
    # View actions
    # ------------------------------------------------------------------ #

    def _set_style(self, style: str) -> None:
        scheme = self._color_combo.currentData() if hasattr(self, "_color_combo") else "chainHetatm"
        self._viewer.set_style(style, scheme)

    def _set_color_scheme(self, scheme: str) -> None:
        style = self._style_combo.currentData() if hasattr(self, "_style_combo") else "cartoon"
        self._viewer.set_style(style, scheme)

    def _pick_background(self) -> None:
        color = QColorDialog.getColor(QColor(26, 26, 46), self, "Choose Background Colour")
        if color.isValid():
            hex_rgb = f"0x{color.red():02X}{color.green():02X}{color.blue():02X}"
            self._viewer.set_background(hex_rgb)

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #

    def _show_measurements(self) -> None:
        dlg = MeasurementResultsDialog(self._measurement_results, self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Annotations
    # ------------------------------------------------------------------ #

    def _add_annotation(self) -> None:
        if self._molecule is None:
            QMessageBox.information(self, "No Structure",
                                    "Please open a molecular file first.")
            return
        dlg = AddAnnotationDialog(self)
        if dlg.exec() == AddAnnotationDialog.DialogCode.Accepted:
            ann = dlg.get_annotation()
            self._viewer.add_annotation(ann)
            self._set_status(
                f"Annotation '{ann.label}' ({ann.ann_type.value}) added."
            )

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def _export_image(self) -> None:
        if self._molecule is None:
            QMessageBox.information(self, "No Structure",
                                    "Please open a molecular file first.")
            return

        dlg = ExportImageDialog(self)
        if dlg.exec() != ExportImageDialog.DialogCode.Accepted:
            return

        out_path = dlg.output_path()
        if not out_path:
            QMessageBox.warning(self, "No Path", "Please specify an output file path.")
            return

        width = dlg.image_width()
        height = dlg.image_height()
        dpi = dlg.dpi()

        self._set_status(f"Capturing {width}×{height} image…")

        def _on_capture(data_url: str) -> None:
            if not data_url:
                QMessageBox.critical(self, "Export Failed",
                                     "The viewer returned no image data.")
                self._set_status("Export failed")
                return
            try:
                saved = save_image(data_url, out_path, dpi=dpi)
                self._set_status(f"Image saved: {saved}")
                QMessageBox.information(self, "Export Complete",
                                        f"Image saved to:\n{saved}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", str(exc))
                self._set_status("Export failed")

        self._viewer.capture_image(width, height, _on_capture)

    # ------------------------------------------------------------------ #
    # About
    # ------------------------------------------------------------------ #

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About MolViz Studio",
            "<h3>MolViz Studio</h3>"
            "<p>A PyQt6-based molecular visualization application.</p>"
            "<ul>"
            "<li>Open <b>.pdb</b>, <b>.mae</b>, <b>.maegz</b> files</li>"
            "<li>Multiple representations: cartoon, stick, ball+stick, sphere, surface</li>"
            "<li>Colour schemes: chain, element, B-factor, residue</li>"
            "<li>Distance, angle, and dihedral measurements</li>"
            "<li>Text labels and arrow annotations</li>"
            "<li>Publication-quality image export (PNG/JPEG/TIFF, up to 1200 DPI)</li>"
            "</ul>"
            "<p>3D rendering powered by <a href='https://pymol.org'>PyMOL</a>.</p>",
        )
