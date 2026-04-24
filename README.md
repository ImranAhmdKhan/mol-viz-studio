# MolViz Studio

A PyQt6-based molecular visualization desktop application for opening **`.pdb`**, **`.mae`**, and **`.maegz`** structure files, producing publication-quality images, and performing interactive analysis and annotation.

---

## Features

| Category | Details |
|---|---|
| **File formats** | PDB (`.pdb`), Maestro (`.mae`), compressed Maestro (`.maegz`) |
| **3-D rendering** | Cartoon, stick, ball-and-stick, sphere, line, molecular surface |
| **Colour schemes** | Chain/Hetatm, element (Jmol), B-factor gradient, residue type |
| **Measurements** | Distance (2 atoms), angle (3 atoms), dihedral (4 atoms); results panel |
| **Annotations** | Text labels, arrows/distance markers with custom colour & font size; serialised to JSON |
| **Analysis** | Steric-clash detection, rough solvent-accessible surface area estimate |
| **Image export** | PNG / JPEG / TIFF at configurable resolution (up to 8192 × 8192 px) and DPI (up to 1200 DPI) |
| **Properties panel** | Per-structure summary, full atom table, chain/residue tree |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** PyQt6-WebEngine requires a working Qt installation.  On Linux
> you may also need `libxcb` and the Qt WebEngine system libraries.

### 2. Run the application

```bash
python main.py
# or, after installing the package:
molviz-studio

# Open a file directly from the command line:
python main.py /path/to/structure.pdb
```

### 3. Using the viewer

* **File ▸ Open** (or `Ctrl+O`) — open any `.pdb`, `.mae`, or `.maegz` file.
* **View ▸ Representation** / toolbar combo — switch rendering style.
* **View ▸ Color Scheme** / toolbar combo — change colouring.
* **Analysis ▸ Measure** — activate distance / angle / dihedral mode, then click atoms in the 3-D view.
* **Annotations ▸ Add Annotation** (`Ctrl+Shift+A`) — add text labels or arrow annotations anchored to 3-D coordinates.
* **File ▸ Export Image** (`Ctrl+E`) — save a high-resolution PNG/JPEG/TIFF.

---

## Project Layout

```
mol-viz-studio/
├── main.py                        # CLI entry point
├── requirements.txt
├── pyproject.toml
├── molviz/
│   ├── app.py                     # QApplication bootstrap
│   ├── main_window.py             # Main QMainWindow
│   ├── parsers/
│   │   ├── molecule.py            # Atom / Bond / Molecule data model
│   │   ├── pdb_parser.py          # PDB parser (ATOM, HETATM, CONECT)
│   │   └── mae_parser.py          # MAE / MAEGZ parser
│   ├── viewer/
│   │   ├── mol_viewer.py          # QWebEngineView hosting 3Dmol.js
│   │   ├── viewer_bridge.py       # Python ↔ JavaScript QWebChannel bridge
│   │   └── html/viewer.html       # Self-contained 3Dmol.js viewer page
│   ├── analysis/
│   │   └── measurements.py        # distance, angle, dihedral, clash score
│   ├── annotations/
│   │   └── annotation_manager.py  # CRUD + JSON serialisation + JS rendering
│   ├── export/
│   │   └── image_exporter.py      # High-res PNG/JPEG/TIFF export dialog
│   └── ui/
│       ├── properties_panel.py    # Atom table, residue tree, summary
│       └── dialogs.py             # Add-annotation and results dialogs
└── tests/
    ├── test_parsers.py            # 25 parser & molecule model tests
    ├── test_analysis.py           # 14 geometry measurement tests
    └── test_annotations.py        # 12 annotation manager tests
```

---

## Running Tests

```bash
pip install pytest
pytest
```

All tests run without a display (no GUI required) and complete in under a second.

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | Desktop GUI framework |
| `PyQt6-WebEngine` | Embeds 3Dmol.js for 3-D rendering |
| `numpy` | Numerical utilities |
| `Pillow` | DPI metadata embedding in exported images |

3-D rendering is provided by [3Dmol.js](https://3dmol.csb.pitt.edu) loaded
from its CDN at runtime (requires an internet connection on first load).
