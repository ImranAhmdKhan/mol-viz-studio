"""3D Molecular Viewer widget backed by 3Dmol.js inside QWebEngineView."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Any

from PyQt6.QtCore import QUrl, QTimer, pyqtSignal, QObject
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PyQt6.QtWebChannel import QWebChannel

from .viewer_bridge import ViewerBridge
from ..parsers.molecule import Molecule
from ..annotations.annotation_manager import Annotation, AnnotationManager


_HTML_PATH = Path(__file__).parent / "html" / "viewer.html"


class MolViewer(QWebEngineView):
    """
    A QWebEngineView that hosts a 3Dmol.js-powered molecular viewer.

    Signals
    -------
    measurementReady(str, str)
        Emitted when a measurement is complete.  Arguments: (type, result).
    atomClicked(dict)
        Emitted when the user clicks an atom.
    viewerReady()
        Emitted once 3Dmol.js has initialised.
    """

    measurementReady = pyqtSignal(str, str)
    atomClicked = pyqtSignal(dict)
    viewerReady = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ready = False
        self._pending: list[str] = []    # JS calls queued before viewer ready
        self._annotation_mgr = AnnotationManager()

        # WebEngine settings
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # WebChannel for Python ↔ JS communication
        self._channel = QWebChannel(self.page())
        self._bridge = ViewerBridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        # Wire bridge events
        self._bridge.on("ready", self._on_viewer_ready)
        self._bridge.on("measurement", self._on_measurement)

        # Load the HTML viewer page
        url = QUrl.fromLocalFile(str(_HTML_PATH))
        self.load(url)

    # ------------------------------------------------------------------ #
    # Internal event handlers
    # ------------------------------------------------------------------ #

    def _on_viewer_ready(self, _data: dict) -> None:
        self._ready = True
        self.viewerReady.emit()
        # Flush any queued commands
        for js in self._pending:
            self.page().runJavaScript(js)
        self._pending.clear()

    def _on_measurement(self, data: dict) -> None:
        mtype = data.get("type", "")
        result = data.get("result", "")
        self.measurementReady.emit(mtype, result)

    # ------------------------------------------------------------------ #
    # Private JS execution helper
    # ------------------------------------------------------------------ #

    def _run_js(self, js: str, callback: Callable | None = None) -> None:
        if not self._ready:
            self._pending.append(js)
            return
        if callback:
            self.page().runJavaScript(js, callback)
        else:
            self.page().runJavaScript(js)

    # ------------------------------------------------------------------ #
    # Public API – structure loading
    # ------------------------------------------------------------------ #

    def load_molecule(self, molecule: Molecule) -> None:
        """Load a :class:`Molecule` into the viewer."""
        pdb_str = molecule.to_pdb_string()
        # Escape for safe embedding in a JS string literal
        escaped = pdb_str.replace("\\", "\\\\").replace("`", "\\`")
        js = f"loadStructure(`{escaped}`, 'pdb');"
        self._run_js(js)

    def load_raw(self, content: str, fmt: str = "pdb") -> None:
        """Load raw structure data (already in *fmt* format)."""
        escaped = content.replace("\\", "\\\\").replace("`", "\\`")
        js = f"loadStructure(`{escaped}`, {json.dumps(fmt)});"
        self._run_js(js)

    # ------------------------------------------------------------------ #
    # Public API – visualisation style
    # ------------------------------------------------------------------ #

    def set_style(self, style: str, color_scheme: str = "chainHetatm") -> None:
        """Apply a representation style.

        *style* can be: cartoon, stick, sphere, line, surface, ballstick
        *color_scheme* can be: chainHetatm, element, bfactor, residue, or a hex colour.
        """
        js = f"applyStyle({json.dumps(style)}, {json.dumps(color_scheme)});"
        self._run_js(js)

    def set_background(self, hex_color: str) -> None:
        """Set the viewer background colour (e.g. ``'0xFFFFFF'``)."""
        js = f"setBackground({json.dumps(hex_color)});"
        self._run_js(js)

    def reset_view(self) -> None:
        self._run_js("resetView();")

    def spin(self, enabled: bool) -> None:
        js = f"spin({'true' if enabled else 'false'});"
        self._run_js(js)

    # ------------------------------------------------------------------ #
    # Public API – measurements
    # ------------------------------------------------------------------ #

    def set_measure_mode(self, mode: str | None) -> None:
        """mode: 'distance' | 'angle' | 'dihedral' | None"""
        js = f"setMeasureMode({json.dumps(mode)});"
        self._run_js(js)

    def clear_measurements(self) -> None:
        self._run_js("clearMeasurements();")

    # ------------------------------------------------------------------ #
    # Public API – annotations
    # ------------------------------------------------------------------ #

    @property
    def annotation_manager(self) -> AnnotationManager:
        return self._annotation_mgr

    def add_annotation(self, ann: Annotation) -> Annotation:
        ann = self._annotation_mgr.add(ann)
        self._sync_annotations()
        return ann

    def remove_annotation(self, ann_id: int) -> None:
        self._annotation_mgr.remove(ann_id)
        self._sync_annotations()

    def clear_annotations(self) -> None:
        self._annotation_mgr.clear()
        self._sync_annotations()

    def _sync_annotations(self) -> None:
        data = json.dumps([a.to_dict() for a in self._annotation_mgr.all])
        js = f"applyAnnotations({data});"
        self._run_js(js)

    # ------------------------------------------------------------------ #
    # Public API – image export
    # ------------------------------------------------------------------ #

    def capture_image(self, width: int, height: int, callback: Callable[[str], None]) -> None:
        """
        Capture a PNG image of the viewer at *width*×*height* pixels.
        *callback* receives the data-URL string ``'data:image/png;base64,...'``.
        """
        js = f"captureImage({width}, {height});"
        self._run_js(js, callback)
