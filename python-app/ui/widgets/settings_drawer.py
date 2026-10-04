from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.widgets.status_panel import StatusLabel


class SettingsDrawer(QFrame):
    saved = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rail")

        heading = QLabel("CREDENTIALS")
        heading.setObjectName("sectionLabel")
        field_label = QLabel("FLIGHTRADAR24 API")
        field_label.setObjectName("sectionLabel")

        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("FR24 Explorer token")

        hint = QLabel(
            "Stored only on this computer. Silver website access is not an API token. "
            "Use an Explorer API token from fr24api.flightradar24.com."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        save = QPushButton("Save token")
        save.clicked.connect(self._save)
        self.status = StatusLabel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(heading)
        layout.addWidget(field_label)
        layout.addWidget(self.token)
        layout.addWidget(hint)
        layout.addWidget(save)
        layout.addWidget(self.status)

    def set_token(self, token: str) -> None:
        self.token.setText(token)

    def _save(self) -> None:
        self.saved.emit(self.token.text().strip())
