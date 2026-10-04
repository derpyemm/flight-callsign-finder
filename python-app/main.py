from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.resources import app_icon

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
except ImportError:
    pass

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Callsign finder")
    icon = app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
