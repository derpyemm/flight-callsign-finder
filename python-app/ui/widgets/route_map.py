from __future__ import annotations

import json

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from clients.airport_client import lookup_airports
from core.models import CallsignHit

try:
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover
    QWebChannel = None
    QWebEngineSettings = None
    QWebEngineView = None


MAP_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet"/>
  <style>
    html, body, #map { height: 100%; margin: 0; background: #0e0e0e; }
    .maplibregl-ctrl-attrib { background: rgba(20,20,20,0.72); color: #8a8a8a; }
    .maplibregl-ctrl-attrib a { color: #b0b0b0; }
    .maplibregl-ctrl-group { background: #2b2b2b; border: 1px solid #5a5a5a; }
    .maplibregl-ctrl-group button { background-color: #2b2b2b; }
    .maplibregl-ctrl button + button { border-top-color: #3d3d3d; }
    .maplibregl-popup-content {
      background: #2b2b2b; color: #e8e8e8; border: 1px solid #5a5a5a;
      padding: 4px 8px; font: 12px Segoe UI, sans-serif;
    }
    .maplibregl-popup-tip { border-top-color: #2b2b2b; }
  </style>
</head>
<body>
<div id="map"></div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const empty = { type: 'FeatureCollection', features: [] };
const map = new maplibregl.Map({
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/dark',
  center: [8, 50.5],
  zoom: 3.5
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
let pending = null;
window.bridge = null;

function gc(a, b, steps) {
  const toRad = Math.PI / 180;
  const lat1 = a[0] * toRad, lon1 = a[1] * toRad;
  const lat2 = b[0] * toRad, lon2 = b[1] * toRad;
  const d = 2 * Math.asin(Math.sqrt(
    Math.pow(Math.sin((lat2 - lat1) / 2), 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin((lon2 - lon1) / 2), 2)
  ));
  if (!d) return [[a[1], a[0]], [b[1], b[0]]];
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
    const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
    const z = A * Math.sin(lat1) + B * Math.sin(lat2);
    pts.push([Math.atan2(y, x) / toRad, Math.atan2(z, Math.sqrt(x * x + y * y)) / toRad]);
  }
  return pts;
}

function hubIcao(routes) {
  const counts = {};
  routes.forEach((route) => {
    counts[route.origin] = (counts[route.origin] || 0) + 1;
    counts[route.destination] = (counts[route.destination] || 0) + 1;
  });
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
}

function ensureLayers(focus) {
  if (!map.getSource('routes')) {
    map.addSource('routes', { type: 'geojson', data: empty });
    map.addSource('airports', { type: 'geojson', data: empty });
    map.addLayer({
      id: 'routes-hit', type: 'line', source: 'routes',
      paint: { 'line-color': '#000000', 'line-width': 14, 'line-opacity': 0 }
    });
    map.addLayer({
      id: 'routes', type: 'line', source: 'routes',
      paint: { 'line-color': '#e53935', 'line-width': 1.4, 'line-opacity': 0.9 }
    });
    map.addLayer({
      id: 'airports-hit', type: 'circle', source: 'airports',
      paint: { 'circle-radius': 14, 'circle-color': '#000000', 'circle-opacity': 0 }
    });
    map.addLayer({
      id: 'airports', type: 'circle', source: 'airports',
      paint: {
        'circle-radius': ['case', ['get', 'hub'], 7, 5],
        'circle-color': ['case', ['get', 'hub'], '#ffffff', '#7eb6ff'],
        'circle-stroke-width': 1,
        'circle-stroke-color': ['case', ['get', 'hub'], '#d0d0d0', '#4a90d9']
      }
    });
    map.on('mousemove', (event) => {
      const over = map.queryRenderedFeatures(event.point, { layers: ['airports-hit', 'routes-hit'] });
      map.getCanvas().style.cursor = over.length ? 'pointer' : '';
      if (!over.length) {
        popup.remove();
        return;
      }
      const feature = over[0];
      const text = feature.properties.code || feature.properties.label;
      if (text) popup.setLngLat(event.lngLat).setText(text).addTo(map);
    });
    map.on('click', (event) => {
      const airports = map.queryRenderedFeatures(event.point, { layers: ['airports-hit', 'airports'] });
      if (airports.length && window.bridge) {
        window.bridge.onAirport(String(airports[0].properties.code || ''));
        return;
      }
      const routes = map.queryRenderedFeatures(event.point, { layers: ['routes-hit', 'routes'] });
      if (routes.length && window.bridge) {
        const props = routes[0].properties;
        window.bridge.onRoute(
          String(props.origin || ''),
          String(props.destination || ''),
          String(props.callsign || '')
        );
      }
    });
  }
  map.setPaintProperty('routes', 'line-color', focus ? '#ff8a80' : '#e53935');
  map.setPaintProperty('routes', 'line-width', focus ? 3 : 1.4);
}

function styleReady() {
  return typeof map.isStyleLoaded === 'function' ? map.isStyleLoaded() : map.loaded();
}

function setRoutes(payload) {
  pending = payload;
  if (!styleReady()) return false;
  try {
    map.resize();
    ensureLayers(Boolean(payload.focus));
    const airports = payload.airports || {};
    const routes = payload.routes || [];
    const hub = payload.hub || hubIcao(routes);
    const lineFeatures = [];
    const pointFeatures = [];
    const marked = {};
    const bounds = new maplibregl.LngLatBounds();
    routes.forEach((route) => {
      const start = airports[route.origin];
      const end = airports[route.destination];
      if (!start || !end) return;
      const coords = gc(start, end, 32);
      lineFeatures.push({
        type: 'Feature',
        properties: {
          label: route.label || '',
          origin: route.origin,
          destination: route.destination,
          callsign: route.callsign || ''
        },
        geometry: { type: 'LineString', coordinates: coords }
      });
      coords.forEach((coord) => bounds.extend(coord));
      [[route.origin, start], [route.destination, end]].forEach(([code, latlon]) => {
        if (marked[code]) return;
        marked[code] = true;
        pointFeatures.push({
          type: 'Feature',
          properties: { code, hub: code === hub },
          geometry: { type: 'Point', coordinates: [latlon[1], latlon[0]] }
        });
      });
    });
    map.getSource('routes').setData({ type: 'FeatureCollection', features: lineFeatures });
    map.getSource('airports').setData({ type: 'FeatureCollection', features: pointFeatures });
    if (lineFeatures.length) map.fitBounds(bounds, { padding: 36, maxZoom: 7, duration: 0 });
    pending = null;
    window.mapReady = true;
    return true;
  } catch (error) {
    return false;
  }
}
function flushPending() {
  if (pending) setRoutes(pending);
}
window.setRoutes = setRoutes;
window.mapReady = false;
window.mapResize = () => { map.resize(); flushPending(); };
map.on('load', () => { window.mapReady = true; flushPending(); });
if (typeof QWebChannel === 'function' && typeof qt !== 'undefined' && qt.webChannelTransport) {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    window.bridge = channel.objects.bridge;
  });
}
</script>
</body>
</html>
"""


class MapBridge(QObject):
    route_clicked = Signal(str, str, str)
    airport_clicked = Signal(str)

    @Slot(str, str, str)
    def onRoute(self, origin: str, destination: str, callsign: str) -> None:
        if origin and destination:
            self.route_clicked.emit(origin, destination, callsign)

    @Slot(str)
    def onAirport(self, icao: str) -> None:
        if icao:
            self.airport_clicked.emit(icao)


class _AirportWorker(QObject):
    finished = Signal(object, int)

    def __init__(self, icaos: list[str], token: int) -> None:
        super().__init__()
        self.icaos = icaos
        self.token = token

    def run(self) -> None:
        try:
            found = lookup_airports(self.icaos)
        except Exception:
            found = {}
        self.finished.emit(found, self.token)


class RouteMap(QFrame):
    show_all_requested = Signal()
    route_clicked = Signal(str, str, str)
    airport_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapFrame")
        self.setMinimumHeight(240)
        self._hits: list[CallsignHit] = []
        self._selected: CallsignHit | None = None
        self._airport: str | None = None
        self._airports: dict[str, tuple[float, float]] = {}
        self._pending: dict | None = None
        self._ready = False
        self._retries = 0
        self._lookup = 0
        self._thread: QThread | None = None
        self._worker: _AirportWorker | None = None
        self._bridge: MapBridge | None = None
        self._channel = None

        title = QLabel("ROUTE MAP")
        title.setObjectName("sectionLabel")
        self.show_all = QPushButton("Show all routes")
        self.show_all.setObjectName("compact")
        self.show_all.setEnabled(False)
        self.show_all.clicked.connect(self.show_all_requested.emit)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.show_all, 0, Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.hint)

        if QWebEngineView is None:
            missing = QLabel("Install PySide6-Addons to show the dark OpenStreetMap view.")
            missing.setObjectName("hint")
            layout.addWidget(missing, 1)
            self.view = None
            return

        self.view = QWebEngineView(self)
        self.view.setMinimumHeight(220)
        if QWebEngineSettings is not None:
            settings = self.view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        if QWebChannel is not None:
            self._bridge = MapBridge(self)
            self._bridge.route_clicked.connect(self.route_clicked.emit)
            self._bridge.airport_clicked.connect(self.airport_clicked.emit)
            self._channel = QWebChannel(self.view.page())
            self._channel.registerObject("bridge", self._bridge)
            self.view.page().setWebChannel(self._channel)
        self.view.loadFinished.connect(self._on_ready)
        self.view.setHtml(MAP_HTML, QUrl("qrc:/"))
        layout.addWidget(self.view, 1)

    def clear(self) -> None:
        self._hits = []
        self._selected = None
        self._airport = None
        self.show_all.setEnabled(False)
        self.hint.clear()
        self._push_routes()

    def show_hits(
        self,
        hits: list[CallsignHit],
        selected: CallsignHit | None = None,
        airport: str | None = None,
    ) -> None:
        self._hits = hits
        self._selected = selected
        self._airport = airport.upper() if airport else None
        self.show_all.setEnabled(bool(hits) and (selected is not None or bool(self._airport)))
        icaos = sorted({code for hit in hits for code in (hit.origin, hit.destination) if code})
        if not icaos:
            self.hint.clear()
            self._push_routes()
            return
        missing = [code for code in icaos if code not in self._airports]
        if not missing:
            self._push_routes()
            return
        self.hint.setText("Placing airports on the map…")
        self._lookup += 1
        token = self._lookup
        if self._thread and self._thread.isRunning():
            self._thread.quit()
        self._thread = QThread(self)
        self._worker = _AirportWorker(missing, token)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_airports)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()

    def _source_hits(self) -> list[CallsignHit]:
        if self._selected:
            return [self._selected]
        if self._airport:
            code = self._airport
            return [hit for hit in self._hits if hit.origin == code or hit.destination == code]
        return self._hits

    def _on_airports(self, found: object, token: int) -> None:
        if token != self._lookup:
            return
        if isinstance(found, dict):
            self._airports.update(found)
        self._push_routes()

    def _push_routes(self) -> None:
        source = self._source_hits()
        routes = []
        seen: set[tuple[str, str, str]] = set()
        wanted: set[str] = set()
        for hit in source:
            if not hit or not hit.origin or not hit.destination:
                continue
            key = (hit.origin, hit.destination, hit.callsign if self._selected else "")
            if key in seen:
                continue
            seen.add(key)
            wanted.add(hit.origin)
            wanted.add(hit.destination)
            routes.append(
                {
                    "origin": hit.origin,
                    "destination": hit.destination,
                    "callsign": hit.callsign,
                    "label": f"{hit.callsign}  {hit.origin} → {hit.destination}",
                }
            )
        missing = sorted(code for code in wanted if code not in self._airports)
        if not routes:
            self.hint.setText("No airport coordinates for these flights." if self._hits else "")
        elif missing:
            self.hint.setText("Could not place " + ", ".join(missing) + ".")
        elif self._selected:
            self.hint.setText(f"{self._selected.callsign}  {self._selected.origin} → {self._selected.destination}")
        elif self._airport:
            noun = "route" if len(routes) == 1 else "routes"
            self.hint.setText(f"{len(routes)} {noun} through {self._airport}. Click a line to isolate one.")
        else:
            noun = "route" if len(routes) == 1 else "routes"
            self.hint.setText(f"{len(routes)} {noun} on the map. Click a line or airport.")

        payload = {
            "airports": {icao: [lat, lon] for icao, (lat, lon) in self._airports.items()},
            "routes": routes,
            "focus": bool(self._selected),
            "hub": self._airport or "",
        }
        self._pending = payload
        self._retries = 0
        if not self.view:
            return
        self._send(payload)

    def _send(self, payload: dict) -> None:
        if not self.view:
            return
        encoded = json.dumps(payload)
        script = f"window.setRoutes ? setRoutes({encoded}) : false;"
        self.view.page().runJavaScript(script, self._after_js)

    def _after_js(self, ok: object) -> None:
        if ok:
            self._retries = 0
            return
        if self._pending is None or self._retries >= 25:
            return
        self._retries += 1
        QTimer.singleShot(200, self._retry_send)

    def _retry_send(self) -> None:
        if self._pending is not None:
            self._send(self._pending)

    def _on_ready(self, ok: bool) -> None:
        self._ready = bool(ok)
        if self._pending is not None:
            self._retries = 0
            self._send(self._pending)
        elif self._hits:
            self._push_routes()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.view and self._pending is not None:
            self.view.page().runJavaScript("if (window.mapResize) mapResize();")

    def _cleanup(self) -> None:
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
