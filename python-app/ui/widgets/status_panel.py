from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.resources import app_pixmap
from ui.theme import ERROR_COLOR, OK_COLOR


class StatusLabel(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)

    def set_ok(self, text: str) -> None:
        self.setStyleSheet(f"color: {OK_COLOR};")
        self.setText(text)

    def set_error(self, text: str) -> None:
        self.setStyleSheet(f"color: {ERROR_COLOR};")
        self.setText(text)

    def set_plain(self, text: str) -> None:
        self.setStyleSheet("color: #b0b0b0;")
        self.setText(text)


class StatusPanel(QFrame):
    toggle_settings = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("masthead")

        brand = QVBoxLayout()
        mark = QLabel("FLIGHT LOOKUP")
        mark.setObjectName("brandMark")
        title = QLabel("CALLSIGN FINDER")
        title.setObjectName("brandTitle")
        brand.addWidget(mark)
        brand.addWidget(title)
        brand.setSpacing(0)

        logo = QLabel()
        logo.setObjectName("brandIcon")
        pixmap = app_pixmap(36)
        if not pixmap.isNull():
            logo.setPixmap(pixmap)
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.fr24_pill = self._pill("FR24")
        self.token_pill = self._pill("TOKEN")
        self.settings_button = QPushButton("API settings")
        self.settings_button.setObjectName("ghost")
        self.settings_button.clicked.connect(self.toggle_settings.emit)
        self.clock = QLabel("--:--:--Z")
        self.clock.setObjectName("clockLabel")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pills = QHBoxLayout()
        pills.setSpacing(8)
        pills.addWidget(self.fr24_pill)
        pills.addWidget(self.token_pill)
        pills.addWidget(self.settings_button)

        right = QVBoxLayout()
        right.addLayout(pills)
        right.addWidget(self.clock)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addWidget(logo)
        layout.addLayout(brand)
        layout.addStretch(1)
        layout.addLayout(right)

        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000)
        self._tick()

    def _pill(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("pill")
        label.setProperty("state", "off")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _tick(self) -> None:
        self.clock.setText(datetime.now(timezone.utc).strftime("%H:%M:%SZ"))

    def set_states(self, *, fr24: bool, token: bool) -> None:
        self._set_pill(self.fr24_pill, "on" if fr24 else "off")
        self._set_pill(self.token_pill, "on" if token else "off")
        self.settings_button.setText("API settings" if token else "Add API token")

    def _set_pill(self, label: QLabel, state: str) -> None:
        label.setProperty("state", state)
        if state == "on":
            label.setStyleSheet("color: #66bb6a; border: 1px solid #66bb6a; padding: 3px 8px;")
        else:
            label.setStyleSheet("color: #6a6a6a; border: 1px solid #3d3d3d; padding: 3px 8px;")
        label.style().unpolish(label)
        label.style().polish(label)
