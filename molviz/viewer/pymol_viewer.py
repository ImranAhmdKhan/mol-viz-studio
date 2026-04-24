"""PyMOL-backed 3D molecular viewer widget for MolViz Studio."""

from __future__ import annotations

import base64
import math
import os
import tempfile
from typing import Callable

import pymol2
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ..parsers.molecule import Molecule
from ..annotations.annotation_manager import Annotation, AnnotationManager, AnnotationType

# Maximum length of a PyMOL object name (PyMOL silently truncates at 255,
# but short names are safer and easier to read in the PyMOL log).
_MAX_PYMOL_NAME_LEN = 20


class _PyMOLGLWidget(QOpenGLWidget):
    """QOpenGLWidget that drives a pymol2.PyMOL rendering context."""

    atomPicked = pyqtSignal(dict)  # emitted after a left-click in measurement mode

    _BUTTON_MAP = {
        Qt.MouseButton.LeftButton: 0,
        Qt.MouseButton.MiddleButton: 1,
        Qt.MouseButton.RightButton: 2,
    }

    def __init__(self, pymol_instance: pymol2.PyMOL, parent=None) -> None:
        super().__init__(parent)
        self._pymol = pymol_instance
        self._cmd = pymol_instance.cmd
        self.fb_scale: float = 1.0
        self.measure_mode_active: bool = False

        # Render loop – poll idle every 20 ms via a single-shot timer chain
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._pymol_process)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # ------------------------------------------------------------------
    # OpenGL callbacks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:
        try:
            window = self.windowHandle()
            if window is None and self.parent() is not None:
                window = self.parent().windowHandle()
            if window is not None:
                self.fb_scale = window.devicePixelRatio()
                self._cmd.set("display_scale_factor", int(self.fb_scale))
        except Exception:
            pass

    def paintGL(self) -> None:
        self._pymol.draw()
        self._timer.start(0)

    def resizeGL(self, w: int, h: int) -> None:
        self._pymol.reshape(int(w * self.fb_scale), int(h * self.fb_scale), True)

    def _pymol_process(self) -> None:
        if self._pymol.idle() or self._pymol.getRedisplay():
            self.update()
        self._timer.start(20)

    # ------------------------------------------------------------------
    # Input: mouse & wheel → PyMOL
    # ------------------------------------------------------------------

    def _event_x_y_mod(self, ev) -> tuple[int, int, int]:
        pos = ev.position()
        x = int(self.fb_scale * pos.x())
        y = int(self.fb_scale * (self.height() - pos.y()))
        mods = 0
        m = ev.modifiers()
        if m & Qt.KeyboardModifier.ShiftModifier:
            mods |= 0x1
        if m & (Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ControlModifier):
            mods |= 0x2
        if m & Qt.KeyboardModifier.AltModifier:
            mods |= 0x4
        return x, y, mods

    def mousePressEvent(self, ev) -> None:
        button = self._BUTTON_MAP.get(ev.button())
        if button is None:
            return
        x, y, mods = self._event_x_y_mod(ev)
        self._pymol.button(button, 0, x, y, mods)
        # Schedule atom-pick read after PyMOL has processed the click
        if ev.button() == Qt.MouseButton.LeftButton and self.measure_mode_active:
            QTimer.singleShot(100, self._read_and_emit_pick)

    def mouseReleaseEvent(self, ev) -> None:
        button = self._BUTTON_MAP.get(ev.button())
        if button is None:
            return
        self._pymol.button(button, 1, *self._event_x_y_mod(ev))

    def mouseMoveEvent(self, ev) -> None:
        self._pymol.drag(*self._event_x_y_mod(ev))

    def wheelEvent(self, ev) -> None:
        ang = ev.angleDelta()
        delta = ang.y() if abs(ang.y()) >= abs(ang.x()) else (
            ang.x() if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0
        )
        if delta == 0:
            return
        button = 3 if delta > 0 else 4
        x, y, mods = self._event_x_y_mod(ev)
        self._pymol.button(button, 0, x, y, mods)
        self._pymol.button(button, 1, x, y, mods)

    def _read_and_emit_pick(self) -> None:
        """Read the last atom picked by PyMOL (pk1) and emit atomPicked."""
        try:
            model = self._cmd.get_model("pk1")
            if model and model.atom:
                a = model.atom[0]
                self.atomPicked.emit({
                    "x": a.coord[0], "y": a.coord[1], "z": a.coord[2],
                    "name": a.name, "resn": a.resn, "resi": a.resi,
                    "chain": a.chain, "elem": a.symbol,
                })
        except Exception:
            pass


class PyMOLViewer(QWidget):
    """
    A QWidget that hosts an embedded PyMOL 3D viewer.

    Drop-in replacement for :class:`molviz.viewer.MolViewer` with the
    same public signals and methods, backed by PyMOL instead of 3Dmol.js.

    Signals
    -------
    measurementReady(str, str)
        Emitted when a measurement is complete.  Arguments: (type, result).
    atomClicked(dict)
        Emitted when the user clicks an atom.
    viewerReady()
        Emitted once PyMOL has initialised.
    """

    measurementReady = pyqtSignal(str, str)
    atomClicked = pyqtSignal(dict)
    viewerReady = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Non-singleton embedded PyMOL instance (widget mode)
        self._pymol = pymol2.PyMOL(scheme="widget")
        self._pymol.start()
        self._cmd = self._pymol.cmd

        # Suppress PyMOL's own GUI chrome and configure appearance
        self._cmd.set("internal_gui", 0)
        self._cmd.set("internal_feedback", 0)
        self._cmd.set("ray_trace_mode", 0)
        self._cmd.set("antialias", 1)
        self._cmd.bg_color("black")

        # GL widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._gl = _PyMOLGLWidget(self._pymol, self)
        layout.addWidget(self._gl)

        # Wire atom-pick signal from GL widget
        self._gl.atomPicked.connect(self._on_atom_picked)

        # Measurement state
        self._measure_mode: str | None = None
        self._picked_atoms: list[dict] = []
        self._meas_counter: int = 0

        # Annotation state
        self._annotation_mgr = AnnotationManager()
        self._ann_counter: int = 0

        # Emit viewerReady after PyMOL finishes initial setup
        QTimer.singleShot(300, self.viewerReady.emit)

    # ------------------------------------------------------------------ #
    # Public API – structure loading
    # ------------------------------------------------------------------ #

    def load_molecule(self, molecule: Molecule) -> None:
        """Load a :class:`Molecule` into the viewer."""
        self._reset_scene()
        pdb_str = molecule.to_pdb_string()
        name = (molecule.name or "molecule").replace(" ", "_")[:_MAX_PYMOL_NAME_LEN]
        self._cmd.read_pdbstr(pdb_str, name)
        self._cmd.orient()
        self._cmd.zoom("all", 5.0)
        self._apply_style_and_color("cartoon", "chainHetatm")

    def load_raw(self, content: str, fmt: str = "pdb") -> None:
        """Load raw structure data already in *fmt* format."""
        self._reset_scene()
        if fmt == "pdb":
            self._cmd.read_pdbstr(content, "molecule")
        else:
            with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False, mode="w") as f:
                f.write(content)
                tmpfile = f.name
            try:
                self._cmd.load(tmpfile)
            finally:
                os.unlink(tmpfile)
        self._cmd.orient()
        self._apply_style_and_color("cartoon", "chainHetatm")

    def _reset_scene(self) -> None:
        """Clear the viewer state for a new molecule."""
        self._cmd.reinitialize("everything")
        self._picked_atoms.clear()
        self._annotation_mgr.clear()
        self._meas_counter = 0
        self._ann_counter = 0
        # Re-apply settings cleared by reinitialize
        self._cmd.set("internal_gui", 0)
        self._cmd.set("internal_feedback", 0)
        self._cmd.bg_color("black")

    # ------------------------------------------------------------------ #
    # Public API – visualisation style
    # ------------------------------------------------------------------ #

    def set_style(self, style: str, color_scheme: str = "chainHetatm") -> None:
        """Apply a representation style and colour scheme.

        *style*: ``cartoon`` | ``stick`` | ``sphere`` | ``line`` |
                 ``surface`` | ``ballstick``

        *color_scheme*: ``chainHetatm`` | ``element`` | ``bfactor`` |
                        ``residue``
        """
        self._apply_style_and_color(style, color_scheme)

    def _apply_style_and_color(self, style: str, color_scheme: str) -> None:
        cmd = self._cmd
        cmd.hide("everything", "all")

        # Representation
        if style == "cartoon":
            cmd.show("cartoon", "all")
        elif style == "stick":
            cmd.show("sticks", "all")
        elif style == "sphere":
            cmd.show("spheres", "all")
        elif style == "line":
            cmd.show("lines", "all")
        elif style == "surface":
            cmd.show("cartoon", "all")
            cmd.show("surface", "all")
            cmd.set("transparency", 0.3, "all")
        elif style == "ballstick":
            cmd.show("sticks", "all")
            cmd.show("spheres", "all")
            cmd.set("sphere_scale", 0.25, "all")
            cmd.set("stick_radius", 0.2, "all")
        else:
            cmd.show("cartoon", "all")

        # Colour scheme
        if color_scheme == "chainHetatm":
            cmd.util.cbc("all")
            try:
                cmd.color("grey60", "hetatm")
            except Exception:
                pass
        elif color_scheme == "element":
            cmd.util.cbaw("all")
        elif color_scheme == "bfactor":
            cmd.spectrum("b", "rainbow", "all")
        elif color_scheme == "residue":
            cmd.spectrum("resi", "rainbow", "all")

    def set_background(self, hex_color: str) -> None:
        """Set the viewer background colour (e.g. ``'0x1A2E46'``)."""
        try:
            rgb = int(hex_color.replace("0x", "").replace("#", ""), 16)
        except (ValueError, AttributeError):
            return
        r = ((rgb >> 16) & 0xFF) / 255.0
        g = ((rgb >> 8) & 0xFF) / 255.0
        b = (rgb & 0xFF) / 255.0
        self._cmd.set_color("_molviz_bg", [r, g, b])
        self._cmd.bg_color("_molviz_bg")

    def reset_view(self) -> None:
        self._cmd.orient()
        self._cmd.zoom("all", 5.0)

    def spin(self, enabled: bool) -> None:
        self._cmd.set("rock", 1 if enabled else 0)

    # ------------------------------------------------------------------ #
    # Public API – measurements
    # ------------------------------------------------------------------ #

    def set_measure_mode(self, mode: str | None) -> None:
        """mode: ``'distance'`` | ``'angle'`` | ``'dihedral'`` | ``None``"""
        self._measure_mode = mode
        self._picked_atoms.clear()
        self._gl.measure_mode_active = mode is not None

    def clear_measurements(self) -> None:
        self._picked_atoms.clear()
        names = self._cmd.get_names("objects")
        for name in names:
            if name.startswith("_meas_"):
                try:
                    self._cmd.delete(name)
                except Exception:
                    pass

    def _on_atom_picked(self, atom_info: dict) -> None:
        if not self._measure_mode or not atom_info:
            return
        self._picked_atoms.append(atom_info)
        self.atomClicked.emit(atom_info)
        needed = {"distance": 2, "angle": 3, "dihedral": 4}.get(self._measure_mode, 2)
        if len(self._picked_atoms) >= needed:
            self._compute_and_emit_measurement()

    def _compute_and_emit_measurement(self) -> None:
        atoms = self._picked_atoms[:]
        mode = self._measure_mode
        result = ""

        try:
            if mode == "distance" and len(atoms) >= 2:
                a, b = atoms[0], atoms[1]
                d = math.sqrt(
                    (a["x"] - b["x"]) ** 2
                    + (a["y"] - b["y"]) ** 2
                    + (a["z"] - b["z"]) ** 2
                )
                result = f"{d:.3f} Å"
                self._add_pymol_distance(a, b)

            elif mode == "angle" and len(atoms) >= 3:
                a, b, c = atoms[0], atoms[1], atoms[2]
                v1 = [a["x"] - b["x"], a["y"] - b["y"], a["z"] - b["z"]]
                v2 = [c["x"] - b["x"], c["y"] - b["y"], c["z"] - b["z"]]
                dot = sum(v1[i] * v2[i] for i in range(3))
                n1 = math.sqrt(sum(x ** 2 for x in v1))
                n2 = math.sqrt(sum(x ** 2 for x in v2))
                ang = math.degrees(math.acos(max(-1.0, min(1.0, dot / (n1 * n2)))))
                result = f"{ang:.2f}°"

            elif mode == "dihedral" and len(atoms) >= 4:
                a, b, c, d = atoms[0], atoms[1], atoms[2], atoms[3]

                def _sub(p, q):
                    return [p["x"] - q["x"], p["y"] - q["y"], p["z"] - q["z"]]

                def _cross(u, v):
                    return [
                        u[1] * v[2] - u[2] * v[1],
                        u[2] * v[0] - u[0] * v[2],
                        u[0] * v[1] - u[1] * v[0],
                    ]

                def _dot(u, v):
                    return sum(u[i] * v[i] for i in range(3))

                b1, b2, b3 = _sub(b, a), _sub(c, b), _sub(d, c)
                n1_v = _cross(b1, b2)
                n2_v = _cross(b2, b3)
                m = _cross(n1_v, b2)
                x_val = _dot(n1_v, n2_v)
                y_val = _dot(m, n2_v)
                di = math.degrees(math.atan2(y_val, x_val))
                result = f"{di:.2f}°"

        except Exception:
            pass

        if result:
            self.measurementReady.emit(mode, result)

        self._picked_atoms.clear()

    def _add_pymol_distance(self, a: dict, b: dict) -> None:
        """Add a visual distance indicator in PyMOL between two positions."""
        n = self._meas_counter = self._meas_counter + 1
        na, nb = f"_meas_a{n}", f"_meas_b{n}"
        try:
            self._cmd.pseudoatom(na, pos=[a["x"], a["y"], a["z"]])
            self._cmd.pseudoatom(nb, pos=[b["x"], b["y"], b["z"]])
            dist_name = f"_meas_d{n}"
            self._cmd.distance(dist_name, na, nb)
            self._cmd.set("dash_color", "yellow", dist_name)
            self._cmd.delete(na)
            self._cmd.delete(nb)
        except Exception:
            pass

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
        # Remove all existing annotation objects
        names = self._cmd.get_names("objects")
        for name in names:
            if name.startswith("_ann_"):
                try:
                    self._cmd.delete(name)
                except Exception:
                    pass

        self._ann_counter = 0
        for ann in self._annotation_mgr.visible:
            self._ann_counter += 1
            n = self._ann_counter
            try:
                if ann.ann_type == AnnotationType.LABEL:
                    pa = f"_ann_{n}"
                    self._cmd.pseudoatom(
                        pa, pos=[ann.x, ann.y, ann.z], label=ann.label
                    )
                elif ann.ann_type in (AnnotationType.DISTANCE, AnnotationType.ARROW):
                    pa, pb = f"_ann_{n}a", f"_ann_{n}b"
                    self._cmd.pseudoatom(pa, pos=[ann.x, ann.y, ann.z])
                    self._cmd.pseudoatom(pb, pos=[ann.x2, ann.y2, ann.z2])
                    self._cmd.distance(f"_ann_{n}d", pa, pb)
                    if ann.label:
                        mx = (ann.x + ann.x2) / 2
                        my = (ann.y + ann.y2) / 2
                        mz = (ann.z + ann.z2) / 2
                        self._cmd.pseudoatom(
                            f"_ann_{n}m", pos=[mx, my, mz], label=ann.label
                        )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Public API – image export
    # ------------------------------------------------------------------ #

    def capture_image(self, width: int, height: int, callback: Callable[[str], None]) -> None:
        """
        Capture a PNG of the viewer at *width*×*height* pixels.
        *callback* receives ``'data:image/png;base64,...'``.
        """
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmpfile = f.name
        try:
            self._cmd.png(tmpfile, width, height, ray=0, quiet=1)
            with open(tmpfile, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            callback(f"data:image/png;base64,{data}")
        except Exception:
            callback("")
        finally:
            try:
                os.unlink(tmpfile)
            except OSError:
                pass
