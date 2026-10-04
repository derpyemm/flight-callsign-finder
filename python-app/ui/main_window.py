from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from core.models import Fr24Settings, SearchResult
from core.search_service import search_callsigns
from storage.settings_store import load_settings, save_settings
from ui.resources import app_icon
from ui.theme import STYLESHEET
from ui.widgets.result_table import ResultBoard
from ui.widgets.search_form import SearchForm
from ui.widgets.settings_drawer import SettingsDrawer
from ui.widgets.status_panel import StatusPanel


class SearchWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        aircraft: str,
        origin: str,
        destination: str,
        include_family: bool,
        token: str,
        lookback_days: int,
    ) -> None:
        super().__init__()
        self.aircraft = aircraft
        self.origin = origin
        self.destination = destination
        self.include_family = include_family
        self.token = token
        self.lookback_days = lookback_days

    def run(self) -> None:
        try:
            result = search_callsigns(
                aircraft=self.aircraft,
                origin=self.origin,
                destination=self.destination,
                include_family=self.include_family,
                fr24_token=self.token or None,
                fr24_lookback_days=self.lookback_days if self.token else None,
                on_progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc) or "Search failed.")


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Callsign finder")
        self.resize(1100, 880)
        self.setStyleSheet(STYLESHEET)
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.settings = load_settings()
        self._thread: QThread | None = None
        self._worker: SearchWorker | None = None

        self.status_panel = StatusPanel()
        self.search_form = SearchForm()
        self.settings_drawer = SettingsDrawer()
        self.board = ResultBoard()

        self.settings_drawer.set_token(self.settings.token)
        self.search_form.lookback.setValue(self.settings.lookback_days)
        self.search_form.submitted.connect(self._on_search)
        self.settings_drawer.saved.connect(self._on_save_token)
        self.status_panel.toggle_settings.connect(self._toggle_settings)

        left = QWidget()
        left.setFixedWidth(300)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)
        left_layout.addWidget(self.search_form, 1)
        left_layout.addWidget(self.settings_drawer)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.addWidget(self.board, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(left, 0)
        body.addWidget(right, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.status_panel)
        layout.addLayout(body, 1)
        self._sync_settings_visibility(force_open=not bool(self.settings.token.strip()))

    def _token(self) -> str:
        return self.settings_drawer.token.text().strip()

    def _sync_settings_visibility(self, force_open: bool | None = None) -> None:
        saved = bool(self._token())
        self.status_panel.set_states(fr24=False, token=saved)
        if force_open is None:
            return
        self.settings_drawer.setVisible(force_open)

    def _toggle_settings(self) -> None:
        self.settings_drawer.setVisible(not self.settings_drawer.isVisible())

    def _on_save_token(self, token: str) -> None:
        self.settings = Fr24Settings(token=token, lookback_days=self.search_form.lookback.value())
        save_settings(self.settings)
        self.settings_drawer.status.set_ok("Saved.")
        self._sync_settings_visibility(force_open=not bool(token))

    def _on_search(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        aircraft, origin, destination, include_family, lookback = self.search_form.values()
        token = self._token()
        if not token:
            self.settings_drawer.setVisible(True)
            self.board.set_error("Add a Flightradar24 API token before searching.")
            self.status_panel.set_states(fr24=False, token=False)
            return
        self.settings = Fr24Settings(token=token, lookback_days=lookback)
        save_settings(self.settings)
        self.search_form.set_busy(True)
        self.board.set_status("Searching…")
        self.status_panel.set_states(fr24=False, token=True)

        self._thread = QThread(self)
        self._worker = SearchWorker(aircraft, origin, destination, include_family, token, lookback)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.board.set_status)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def _on_finished(self, result: object) -> None:
        assert isinstance(result, SearchResult)
        self.board.show_result(result)
        self.search_form.set_busy(False)
        self.status_panel.set_states(fr24=(result.fr24_flights or 0) > 0, token=True)

    def _on_failed(self, message: str) -> None:
        self.board.set_error(message)
        self.search_form.set_busy(False)
        self.status_panel.set_states(fr24=False, token=bool(self._token()))

    def _cleanup_worker(self) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1500)
        super().closeEvent(event)
