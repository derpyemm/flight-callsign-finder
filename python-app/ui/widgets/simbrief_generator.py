from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from clients.simbrief_client import (
    fetch_latest_ofp_or_none,
    ofp_matches_route,
    ofp_request_id,
    seed_offblock,
    timed_dispatch_url,
)
from core.models import CallsignHit
from storage.paths import simbrief_web_dir
from utils.simbrief import parse_landing_utc, simbrief_generate_form_url

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineScript = None
    QWebEngineView = None


_BOOTSTRAP_JS = """
window.confirm = function() { return true; };
window.alert = function() {};
window.prompt = function() { return ''; };
"""

_PAGE_JS = r"""
(function() {
  const href = (location.href || '').toLowerCase();
  const title = (document.title || '').toLowerCase();
  const body = (document.body && (document.body.innerText || document.body.textContent) || '').toLowerCase();
  const textOf = (el) => ((el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || '') + '')
    .replace(/\s+/g, ' ').trim().toLowerCase();
  const ownText = (el) => {
    let bits = [];
    for (const node of el.childNodes) {
      if (node.nodeType === 3) bits.push(node.textContent || '');
    }
    const labeled = (el.getAttribute('aria-label') || el.getAttribute('title') || el.value || '');
    return (bits.join(' ') + ' ' + labeled).replace(/\s+/g, ' ').trim().toLowerCase();
  };
  const docs = [document];
  for (const frame of document.querySelectorAll('iframe')) {
    try { if (frame.contentDocument) docs.push(frame.contentDocument); } catch (e) {}
  }
  const clickableSel = 'button, input, a, [role=button], [onclick], [tabindex], [class*="btn"], [class*="tab"], [class*="nav"]';
  const nodes = [];
  for (const doc of docs) {
    nodes.push(...doc.querySelectorAll(clickableSel));
    for (const el of doc.querySelectorAll('*')) {
      if (el.shadowRoot) nodes.push(...el.shadowRoot.querySelectorAll(clickableSel));
    }
  }
  const confirmClose = body.includes('unsaved') || body.includes('are you sure') || body.includes('close this flight');
  if (confirmClose) {
    for (const el of nodes) {
      const t = textOf(el);
      if (t === 'close flight' || t === 'close this flight') {
        el.click();
        return 'closing';
      }
    }
  }
  for (const el of nodes) {
    const t = textOf(el);
    if (t === 'close message' || t === "don't show this again") {
      el.click();
    }
  }
  if (body.includes('generating') && (body.includes('ofp') || body.includes('flight plan') || body.includes('progress'))) {
    return 'generating';
  }
  const onAuthUrl = (
    href.includes('login') || href.includes('signin') || href.includes('oauth') ||
    href.includes('auth.navigraph') || href.includes('id.navigraph')
  );
  if (onAuthUrl) {
    return 'login';
  }

  const compact = (t) => t.replace(/[^a-z0-9]/g, '');
  const isBtn = (el) => {
    const tag = (el.tagName || '').toUpperCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const oc = (el.getAttribute('onclick') || '').toLowerCase();
    return tag === 'BUTTON' || tag === 'INPUT' || type === 'submit' || role === 'button' || oc.includes('simbrief');
  };
  const realClick = (el) => {
    try { el.scrollIntoView({block: 'center', inline: 'center'}); } catch (e) {}
    const opts = {bubbles: true, cancelable: true, view: window, composed: true};
    try { el.dispatchEvent(new PointerEvent('pointerdown', opts)); } catch (e) {}
    try { el.dispatchEvent(new MouseEvent('mousedown', opts)); } catch (e) {}
    try { el.dispatchEvent(new PointerEvent('pointerup', opts)); } catch (e) {}
    try { el.dispatchEvent(new MouseEvent('mouseup', opts)); } catch (e) {}
    try { el.dispatchEvent(new MouseEvent('click', opts)); } catch (e) {}
    try { el.click(); } catch (e) {}
  };
  const rankOf = (t, el) => {
    const c = compact(t);
    if (!isBtn(el)) return 99;
    if (c.includes('generateofp') || t.includes('generate ofp')) return 0;
    if (c.includes('generateflightplan') || c.includes('generateplan')) return 1;
    if (c.includes('generateflight')) return 2;
    if (c === 'generate') return 3;
    if (c.startsWith('generate') && c.length > 8) return 4;
    return 99;
  };
  if (!window.__sbGenClicked) {
    const cands = [];
    const seen = new Set();
    const consider = (el) => {
      const short = ownText(el);
      const full = textOf(el);
      const t = (short && short.length <= 40 ? short : (full.length <= 40 ? full : ''));
      if (!t) return;
      const rank = rankOf(t, el);
      if (rank > 10) return;
      const key = t + '|' + (el.tagName || '');
      if (seen.has(key)) return;
      seen.add(key);
      cands.push({el, t, rank, len: t.length});
    };
    for (const el of nodes) consider(el);
    for (const doc of docs) {
      for (const el of doc.querySelectorAll('button, input[type=submit], input[type=button], [role=button], [onclick]')) consider(el);
      for (const el of doc.querySelectorAll('*')) {
        if ((el.innerText || '').length <= 48) consider(el);
      }
    }
    cands.sort((a, b) => a.rank - b.rank || a.len - b.len);
    if (cands.length) {
      realClick(cands[0].el);
      window.__sbGenClicked = true;
      return 'clicked:' + cands[0].t;
    }
    if (!window.__sbTabClicked) {
      for (const doc of docs) {
        for (const el of doc.querySelectorAll('*')) {
          const t = compact(ownText(el) || textOf(el));
          if ((t === 'generate' || t === 'generateflight' || t === 'generateofp') && el.childElementCount <= 2) {
            window.__sbTabClicked = true;
            realClick(el);
            return 'tab:generate';
          }
        }
      }
    }
  }
  if (href.includes('viewofp') || href.includes('ofp.loader') || href.includes('/ofp/')) {
    return 'done';
  }
  if (
    title.includes('sign in') || title.includes('log in') ||
    body.includes('sign in to navigraph') || body.includes('forgot password')
  ) {
    return 'login';
  }
  return 'form';
})();
"""

_PROFILE: QWebEngineProfile | None = None


if QWebEnginePage is not None:

    class _EnginePage(QWebEnginePage):
        def __init__(self, profile: QWebEngineProfile, owner: "SimbriefGenerator") -> None:
            super().__init__(profile, owner)
            self._owner = owner

        def createWindow(self, _type) -> QWebEnginePage:
            return self._owner._popup_page()

else:  # pragma: no cover
    _EnginePage = None  # type: ignore[misc,assignment]


def webengine_available() -> bool:
    return QWebEngineView is not None and QWebEngineProfile is not None


def _profile(parent: QWidget) -> QWebEngineProfile:
    global _PROFILE
    if _PROFILE is not None:
        return _PROFILE
    root = simbrief_web_dir()
    profile = QWebEngineProfile("simbrief", parent)
    try:
        policy = QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    except AttributeError:
        policy = QWebEngineProfile.ForcePersistentCookies
    profile.setPersistentCookiesPolicy(policy)
    profile.setPersistentStoragePath(str(root))
    profile.setCachePath(str(root / "cache"))
    profile.setHttpUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    if QWebEngineScript is not None:
        script = QWebEngineScript()
        script.setName("simbrief-quiet")
        try:
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        except AttributeError:
            script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(True)
        script.setSourceCode(_BOOTSTRAP_JS)
        profile.scripts().insert(script)
    _PROFILE = profile
    return profile


class _FetchWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, simbrief_id: str) -> None:
        super().__init__()
        self.simbrief_id = simbrief_id

    def run(self) -> None:
        try:
            ofp = fetch_latest_ofp_or_none(self.simbrief_id)
            self.finished.emit(ofp)
        except Exception as exc:
            self.failed.emit(str(exc) or "Could not read the SimBrief flight plan.")


class _WaitDialog(QWidget):
    def __init__(self, parent: QWidget | None, on_cancel) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setWindowTitle("Please wait")
        self.setFixedSize(400, 160)
        self._on_cancel = on_cancel

        title = QLabel("Please wait")
        title.setObjectName("sectionLabel")
        self.message = QLabel("Generating a SimBrief plan to read the landing time…")
        self.message.setObjectName("hint")
        self.message.setWordWrap(True)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(on_cancel)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(self.message)
        layout.addWidget(bar)
        layout.addLayout(buttons)

    def set_message(self, text: str) -> None:
        self.message.setText(text)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.isVisible():
            self._on_cancel()
            event.ignore()
            return
        event.accept()


class SimbriefGenerator(QWidget):
    succeeded = Signal(str)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("SimBrief login")
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.resize(1280, 900)
        self._wait = _WaitDialog(parent, self.cancel)

        self._hit: CallsignHit | None = None
        self._landing = ""
        self._taxiout: int | None = None
        self._simbrief_id = ""
        self._previous_id = ""
        self._clicked = False
        self._form_ticks = 0
        self._awaiting_previous = False
        self._login_visible = False
        self._login_ticks = 0
        self._login_dismissed = False
        self._post_login_ticks = 0
        self._polls = 0
        self._busy = False
        self._thread: QThread | None = None
        self._worker: _FetchWorker | None = None

        self.status = QLabel("Log into SimBrief once. Later reference plans stay in the background.")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)

        self.view = None
        self.close_now = QPushButton("Close now")
        self.close_now.clicked.connect(self._close_login)
        self.close_now.setVisible(False)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_now)
        buttons.addWidget(cancel)

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.status)
        self._layout.addLayout(buttons)

        self._tick = QTimer(self)
        self._tick.setInterval(2000)
        self._tick.timeout.connect(self._inspect_page)
        self._poll = QTimer(self)
        self._poll.setInterval(4000)
        self._poll.timeout.connect(self._poll_ofp)

    def busy(self) -> bool:
        return self._busy

    def _ensure_view(self) -> bool:
        if self.view is not None:
            return True
        if not webengine_available():
            return False
        self.view = QWebEngineView(self)
        self.view.setPage(_EnginePage(_profile(self), self))
        self.view.loadFinished.connect(self._on_load)
        self._layout.insertWidget(1, self.view, 1)
        return True

    def start(self, hit: CallsignHit, landing: str, simbrief_id: str, taxiout: int | None = None) -> None:
        if not self._ensure_view():
            self.failed.emit("SimBrief generate needs the app’s built-in browser (WebEngine).")
            return
        landing_at = parse_landing_utc(landing)
        if not landing_at:
            self.failed.emit("Enter a landing time like 18:30, or 4 Oct 18:30.")
            return
        self._hit = hit
        self._landing = landing
        self._taxiout = taxiout
        self._simbrief_id = simbrief_id
        self._previous_id = ""
        self._clicked = False
        self._form_ticks = 0
        self._awaiting_previous = True
        self._login_visible = False
        self._login_ticks = 0
        self._login_dismissed = False
        self._post_login_ticks = 0
        self._polls = 0
        self._busy = True
        self._set_hidden()
        self._set_progress("Generating a SimBrief plan to read the landing time…")
        self._show_wait()
        self._fetch(self._on_previous)

    def cancel(self) -> None:
        was_busy = self._busy
        self._stop()
        self._hide_wait()
        self._set_hidden()
        self.hide()
        if was_busy:
            self._busy = False
            self.failed.emit("SimBrief timing cancelled.")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._login_visible and self._busy:
            self._close_login()
            event.ignore()
            return
        if self._busy:
            self.cancel()
            event.ignore()
            return
        event.accept()

    def _popup_page(self) -> QWebEnginePage:
        page = _EnginePage(_profile(self), self)
        if self.view:
            self.view.setPage(page)
        return page

    def _set_hidden(self) -> None:
        self._login_visible = False
        self.close_now.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.resize(1280, 900)
        self.show()

    def _show_wait(self) -> None:
        owner = self.parentWidget()
        if owner is not None:
            center = owner.frameGeometry().center()
            self._wait.move(center.x() - self._wait.width() // 2, center.y() - self._wait.height() // 2)
        self._wait.show()
        self._wait.raise_()
        self._wait.activateWindow()

    def _hide_wait(self) -> None:
        self._wait.hide()

    def _set_progress(self, text: str) -> None:
        self._wait.set_message(text)
        self.progress.emit(text)

    def _show_login(self) -> None:
        if self._login_visible:
            return
        self._login_visible = True
        self._hide_wait()
        self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        self.resize(960, 700)
        self.status.setText("Sign into SimBrief here. When you are done, press Close now.")
        self.close_now.setVisible(True)
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _close_login(self) -> None:
        if not self._login_visible:
            return
        self._login_dismissed = True
        self._login_ticks = 0
        self._post_login_ticks = 0
        self._form_ticks = 0
        self._clicked = False
        self._set_hidden()
        if not self._busy:
            self.hide()
            return
        self._set_progress("Generating a SimBrief plan to read the landing time…")
        self._show_wait()
        self._load_generate_form()

    def _load_generate_form(self) -> None:
        if not self._busy or not self._hit or not self.view:
            return
        landing_at = parse_landing_utc(self._landing)
        if not landing_at:
            self._fail("Could not start the SimBrief reference plan.")
            return
        url = simbrief_generate_form_url(self._hit, seed_offblock(landing_at), self._taxiout)
        self.view.load(QUrl(url))
        if not self._tick.isActive():
            self._tick.start()

    def _on_previous(self, ofp: object) -> None:
        if not self._busy or not self._hit:
            return
        self._awaiting_previous = False
        self._previous_id = ofp_request_id(ofp if isinstance(ofp, dict) else None)
        self._load_generate_form()

    def _on_load(self, ok: bool) -> None:
        if not self._busy:
            return
        if not ok:
            return
        self._inspect_page()

    def _inspect_page(self) -> None:
        if not self._busy or not self.view or self._login_visible:
            return
        self.view.page().runJavaScript(_PAGE_JS, self._on_js)

    def _on_js(self, state: object) -> None:
        if not self._busy:
            return
        label = str(state or "")
        kind = label.split("|", 1)[0]
        if kind == "login":
            if self._login_dismissed:
                self._post_login_ticks += 1
                if self._post_login_ticks in {3, 8}:
                    self._load_generate_form()
                    return
                if self._post_login_ticks >= 12:
                    self._login_dismissed = False
                    self._login_ticks = 4
                    self.status.setText("Still not signed in. Finish login, then press Close now.")
                    self._show_login()
                return
            self._login_ticks += 1
            if self._login_ticks >= 4:
                self._show_login()
            return
        self._login_ticks = 0
        self._post_login_ticks = 0
        if kind == "closing" or kind.startswith("tab:"):
            return
        if kind == "clicked" or label.startswith("clicked:"):
            self._clicked = True
            self._set_progress("Generating a SimBrief plan to read the landing time…")
            if not self._poll.isActive():
                self._poll.start()
            return
        if kind in {"generating", "done"}:
            self._clicked = True
            self._set_progress("Reading the expected landing time…")
            if not self._poll.isActive():
                self._poll.start()
            return
        if kind == "form" and not self._clicked:
            self._form_ticks += 1
            if self._form_ticks >= 8 and not self._login_dismissed:
                self._show_login()
            if self._form_ticks >= 30 and not self._login_visible:
                self._fail("SimBrief did not generate the reference plan automatically. Sign in in the SimBrief window if it is shown.")

    def _poll_ofp(self) -> None:
        if not self._busy or not self._clicked:
            return
        if self._thread and self._thread.isRunning():
            return
        self._polls += 1
        if self._polls > 12:
            self._fail("SimBrief did not finish the reference plan in time. Try again.")
            return
        self._fetch(self._on_latest)

    def _on_latest(self, ofp: object) -> None:
        if not self._busy or not self._hit:
            return
        if not isinstance(ofp, dict):
            return
        latest_id = ofp_request_id(ofp)
        if latest_id == self._previous_id or not ofp_matches_route(ofp, self._hit):
            return
        try:
            url = timed_dispatch_url(self._hit, self._landing, ofp, self._taxiout)
        except Exception as exc:
            self._fail(str(exc) or "Could not time the SimBrief off-block.")
            return
        self._stop()
        self._busy = False
        self._hide_wait()
        self._set_hidden()
        self.hide()
        self.succeeded.emit(url)

    def _fetch(self, callback) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._thread = QThread(self)
        self._worker = _FetchWorker(self._simbrief_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(callback)
        self._worker.failed.connect(self._on_fetch_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_fetch)
        self._thread.start()

    def _on_fetch_error(self, message: str) -> None:
        if self._awaiting_previous:
            self._fail(message)

    def _fail(self, message: str) -> None:
        if not self._busy:
            return
        self._stop()
        self._busy = False
        self._hide_wait()
        self._set_hidden()
        self.hide()
        self.failed.emit(message)

    def _stop(self) -> None:
        self._tick.stop()
        self._poll.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()

    def _cleanup_fetch(self) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
