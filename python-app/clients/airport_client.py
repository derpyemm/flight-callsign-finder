from __future__ import annotations

import csv
import io
import json
import time
from urllib.parse import quote

from clients.http import get_json, get_text
from storage.paths import airport_cache_path, airport_catalog_path


OPENFLIGHTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

_catalog: dict[str, list[float]] | None = None


def _read_json(path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path, payload: dict[str, list[float]]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _as_coords(value: object) -> tuple[float, float] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        lat = float(value[0])
        lon = float(value[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _parse_openflights(text: str) -> dict[str, list[float]]:
    catalog: dict[str, list[float]] = {}
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 8:
            continue
        icao = row[5].strip().upper()
        if len(icao) != 4 or icao == "\\N":
            continue
        try:
            lat = float(row[6])
            lon = float(row[7])
        except ValueError:
            continue
        catalog[icao] = [lat, lon]
    return catalog


def _load_catalog() -> dict[str, list[float]]:
    global _catalog
    if _catalog is not None:
        return _catalog
    path = airport_catalog_path()
    cached = _read_json(path)
    if len(cached) > 100:
        _catalog = cached
        return _catalog
    try:
        status, text = get_text(OPENFLIGHTS_URL, timeout=45)
    except RuntimeError:
        _catalog = cached
        return _catalog
    if status != 200 or not text:
        _catalog = cached
        return _catalog
    parsed = _parse_openflights(text)
    if parsed:
        _write_json(path, parsed)
        _catalog = parsed
        return _catalog
    _catalog = cached
    return _catalog


def _nominatim(icao: str) -> tuple[float, float] | None:
    url = (
        "https://nominatim.openstreetmap.org/search"
        f"?q={quote(icao + ' airport')}&format=json&limit=1"
    )
    status, body = get_json(url, timeout=12)
    if status != 200 or not isinstance(body, list) or not body:
        return None
    first = body[0]
    if not isinstance(first, dict):
        return None
    try:
        return float(first["lat"]), float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def lookup_airports(icaos: list[str]) -> dict[str, tuple[float, float]]:
    extras = _read_json(airport_cache_path())
    catalog = _load_catalog()
    found: dict[str, tuple[float, float]] = {}
    missing: list[str] = []
    seen: set[str] = set()

    for raw in icaos:
        icao = raw.strip().upper()
        if len(icao) != 4 or icao in seen:
            continue
        seen.add(icao)
        coords = _as_coords(extras.get(icao)) or _as_coords(catalog.get(icao))
        if coords:
            found[icao] = coords
        else:
            missing.append(icao)

    dirty = False
    for index, icao in enumerate(missing):
        if index:
            time.sleep(1)
        try:
            coords = _nominatim(icao)
        except RuntimeError:
            coords = None
        if coords:
            extras[icao] = [coords[0], coords[1]]
            found[icao] = coords
            dirty = True
    if dirty:
        _write_json(airport_cache_path(), extras)
    return found
