from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget


def _labeled_field(caption: str, widget: QWidget) -> QVBoxLayout:
    block = QVBoxLayout()
    block.setSpacing(4)
    label = QLabel(caption)
    label.setObjectName("sectionLabel")
    block.addWidget(label)
    block.addWidget(widget)
    return block


class SearchForm(QFrame):
    submitted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rail")

        heading = QLabel("SEARCH")
        heading.setObjectName("sectionLabel")

        self.aircraft = QLineEdit()
        self.aircraft.setMaxLength(4)
        self.aircraft.setPlaceholderText("A320")
        self.origin = QLineEdit()
        self.origin.setMaxLength(4)
        self.origin.setPlaceholderText("Any")
        self.destination = QLineEdit()
        self.destination.setMaxLength(4)
        self.destination.setPlaceholderText("Any")
        for field in (self.aircraft, self.origin, self.destination):
            field.returnPressed.connect(self.submitted.emit)

        self.lookback = QSpinBox()
        self.lookback.setRange(1, 30)
        self.lookback.setValue(2)

        self.include_family = QCheckBox("Include family variants")
        self.include_family.setChecked(True)

        self.landing_utc = QLineEdit()
        self.landing_utc.setPlaceholderText("Optional, 18:30")
        landing_hint = QLabel(
            "If set, a reference plan is generated in the background. Only the timed "
            "dispatch page is opened afterwards."
        )
        landing_hint.setObjectName("hint")
        landing_hint.setWordWrap(True)

        self.taxi_out = QLineEdit()
        self.taxi_out.setMaxLength(2)
        self.taxi_out.setPlaceholderText("Default")
        taxi_hint = QLabel("Taxi time in minutes. Leave empty to keep SimBrief’s standard taxi-out.")
        taxi_hint.setObjectName("hint")
        taxi_hint.setWordWrap(True)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.submitted.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addLayout(_labeled_field("AIRCRAFT", self.aircraft))
        layout.addLayout(_labeled_field("DEPARTURE", self.origin))
        layout.addLayout(_labeled_field("ARRIVAL", self.destination))
        layout.addLayout(_labeled_field("HISTORY DAYS", self.lookback))
        layout.addWidget(self.include_family)
        layout.addLayout(_labeled_field("LANDING UTC", self.landing_utc))
        layout.addWidget(landing_hint)
        layout.addLayout(_labeled_field("TAXI OUT", self.taxi_out))
        layout.addWidget(taxi_hint)
        layout.addWidget(self.search_button)
        layout.addStretch(1)

    def set_busy(self, busy: bool) -> None:
        self.search_button.setEnabled(not busy)
        self.search_button.setText("Searching…" if busy else "Search")

    def landing_time(self) -> str:
        return self.landing_utc.text().strip()

    def taxi_out_minutes(self) -> str:
        return self.taxi_out.text().strip()

    def values(self) -> tuple[str, str, str, bool, int]:
        return (
            self.aircraft.text(),
            self.origin.text(),
            self.destination.text(),
            self.include_family.isChecked(),
            self.lookback.value(),
        )
