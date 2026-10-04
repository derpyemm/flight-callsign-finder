from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import CallsignHit, SearchResult
from ui.widgets.route_map import RouteMap
from utils.formatters import (
    format_departure_utc,
    format_duration,
    format_flight_day,
    format_route,
    google_flight_url,
    route_summary,
)
from utils.simbrief import simbrief_dispatch_url


HEADERS = ["CALLSIGN", "IATA", "BLOCK", "TYPE", "ROUTE", "DAY", "DEP UTC", ""]


class ResultBoard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("board")

        heading = QLabel("TRAFFIC BOARD")
        heading.setObjectName("sectionLabel")
        self.summary = QLabel("Awaiting search.")
        self.summary.setObjectName("summaryText")
        self.summary.setWordWrap(True)
        self.meta = QLabel("")
        self.meta.setObjectName("hint")
        self.meta.setWordWrap(True)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(120)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setWordWrap(False)
        self.table.cellDoubleClicked.connect(self._copy_cell)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for index in range(len(HEADERS)):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.route_map = RouteMap()
        self.route_map.show_all_requested.connect(self._show_all_routes)
        self.route_map.route_clicked.connect(self._on_map_route)
        self.route_map.airport_clicked.connect(self._on_map_airport)
        self._hits: list[CallsignHit] = []
        self._syncing = False

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.route_map)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([250, 420])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(heading)
        layout.addWidget(self.summary)
        layout.addWidget(self.meta)
        layout.addWidget(splitter, 1)

    def set_status(self, text: str) -> None:
        self.summary.setText(text)
        self.meta.clear()

    def set_error(self, text: str) -> None:
        self.summary.setText(f"Error: {text}")
        self.meta.clear()
        self._hits = []
        self.table.setRowCount(0)
        self.route_map.clear()

    def show_result(self, result: SearchResult) -> None:
        where = route_summary(result.origin, result.destination)
        if not result.hits:
            self.summary.setText(f"No recent evidence that {'/'.join(result.types)} operates {where}.")
        else:
            noun = "callsign" if len(result.hits) == 1 else "callsigns"
            self.summary.setText(f"{len(result.hits)} {noun} for {'/'.join(result.types)} {where}.")

        bits = []
        if result.fr24_days:
            bits.append(f"FR24: {result.fr24_flights or 0} flights over {result.fr24_days} days")
        if result.hits:
            bits.append("Block is actual takeoff-to-landing; click it for Google’s scheduled time.")
        bits.extend(result.warnings)
        self.meta.setText("\n".join(bits))
        self._fill_table(result.hits)

    def _fill_table(self, hits: list[CallsignHit]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        ordered = sorted(hits, key=lambda hit: hit.last_seen or "", reverse=True)
        self._hits = ordered
        for hit in ordered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            google_url = google_flight_url(hit.iata)
            block_label = format_duration(hit.duration_minutes)
            values = [
                hit.callsign,
                hit.iata or "—",
                block_label if block_label != "—" or not hit.iata else hit.iata or "—",
                hit.type,
                format_route(hit.origin, hit.destination),
                format_flight_day(hit.last_seen),
                format_departure_utc(hit.last_seen),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)

            if google_url:
                link = QPushButton(values[2])
                link.setObjectName("ghost")
                link.clicked.connect(lambda _=False, url=google_url: webbrowser.open(url))
                self.table.setCellWidget(row, 2, link)

            send = QPushButton("SimBrief")
            send.clicked.connect(lambda _=False, item=hit: self._open_simbrief(item))
            self.table.setCellWidget(row, 7, send)

        self.table.clearSelection()
        self.table.blockSignals(False)
        self._fit_route_column()
        self.route_map.show_hits(ordered)

    def _fit_route_column(self) -> None:
        metrics = QFontMetrics(self.table.font())
        widest = metrics.horizontalAdvance("WXXX → WXXX") + 28
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 4)
            if item:
                widest = max(widest, metrics.horizontalAdvance(item.text()) + 28)
        self.table.setColumnWidth(4, widest)

    def _on_row_selected(self) -> None:
        if self._syncing:
            return
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows or not self._hits:
            self.route_map.show_hits(self._hits)
            return
        row = rows[0].row()
        if 0 <= row < len(self._hits):
            self.route_map.show_hits(self._hits, selected=self._hits[row])

    def _select_row(self, row: int) -> None:
        if not (0 <= row < len(self._hits)):
            return
        self._syncing = True
        self.table.selectRow(row)
        item = self.table.item(row, 0)
        if item:
            self.table.scrollToItem(item)
        self._syncing = False
        self.route_map.show_hits(self._hits, selected=self._hits[row])

    def _on_map_route(self, origin: str, destination: str, callsign: str) -> None:
        exact = -1
        pair = -1
        for index, hit in enumerate(self._hits):
            if hit.origin != origin or hit.destination != destination:
                continue
            if pair < 0:
                pair = index
            if callsign and hit.callsign == callsign:
                exact = index
                break
        chosen = exact if exact >= 0 else pair
        if chosen >= 0:
            self._select_row(chosen)

    def _on_map_airport(self, icao: str) -> None:
        self._syncing = True
        self.table.clearSelection()
        self._syncing = False
        self.route_map.show_hits(self._hits, airport=icao)

    def _show_all_routes(self) -> None:
        self._syncing = True
        self.table.clearSelection()
        self._syncing = False
        self.route_map.show_hits(self._hits)

    def _copy_cell(self, row: int, column: int) -> None:
        if column == 7:
            return
        item = self.table.item(row, column)
        text = item.text().strip() if item else ""
        if not text or text == "—":
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _open_simbrief(self, hit: CallsignHit) -> None:
        try:
            webbrowser.open(simbrief_dispatch_url(hit))
        except ValueError as exc:
            QMessageBox.warning(self, "SimBrief", str(exc))
