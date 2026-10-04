from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        root = Path(sys._MEIPASS) / "assets"
    else:
        root = Path(__file__).resolve().parent.parent / "assets"
    return root / name


def app_icon() -> QIcon:
    icon = QIcon()
    ico = asset_path("app.ico")
    png = asset_path("app.png")
    if ico.exists():
        icon.addFile(str(ico))
    if png.exists():
        icon.addFile(str(png))
    return icon


def app_pixmap(size: int = 28) -> QPixmap:
    png = asset_path("app.png")
    if not png.exists():
        return QPixmap()
    pixmap = QPixmap(str(png))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
