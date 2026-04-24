"""Application bootstrap for MolViz Studio."""

from __future__ import annotations

import sys


def main() -> None:
    # Must be imported before QApplication in some configurations
    import os
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("MolViz Studio")
    app.setOrganizationName("MolViz")
    app.setApplicationVersion("1.0.0")

    from .main_window import MainWindow
    win = MainWindow()
    win.show()

    # If a file path was passed as CLI argument, open it immediately
    if len(sys.argv) > 1:
        from pathlib import Path
        path = Path(sys.argv[1])
        if path.exists():
            win._load_file(path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
