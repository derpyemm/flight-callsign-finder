from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.widgets.status_panel import StatusLabel


class SettingsDrawer(QFrame):
    saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rail")

        heading = QLabel("CREDENTIALS")
        heading.setObjectName("sectionLabel")

        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("FR24 Explorer token")

        self.simbrief_id = QLineEdit()
        self.simbrief_id.setPlaceholderText("Pilot ID or username")

        hint = QLabel(
            "Stored only on this computer. The FR24 token is from fr24api.flightradar24.com. "
            "Your SimBrief Pilot ID or username is in Account Settings."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        save = QPushButton("Save")
        save.clicked.connect(self.saved.emit)
        self.status = StatusLabel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(heading)
        layout.addLayout(self._field("FLIGHTRADAR24 API", self.token))
        layout.addLayout(self._field("SIMBRIEF ID", self.simbrief_id))
        layout.addWidget(hint)
        layout.addWidget(save)
        layout.addWidget(self.status)

    def _field(self, caption: str, widget: QWidget) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(4)
        label = QLabel(caption)
        label.setObjectName("sectionLabel")
        block.addWidget(label)
        block.addWidget(widget)
        return block

    def set_values(self, token: str, simbrief_id: str) -> None:
        self.token.setText(token)
        self.simbrief_id.setText(simbrief_id)
