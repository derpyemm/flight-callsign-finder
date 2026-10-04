from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from urllib.parse import quote

from clients.http import ADSBDB_HOST, get_json
from storage.paths import iata_cache_path
from utils.formatters import normalize_flight_number


def _read_cache() -> dict[str, str]:
    path = iata_cache_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_cache(cache: dict[str, str]) -> None:
    iata_cache_path().write_text(json.dumps(cache), encoding="utf-8")


def _lookup_iata(callsign: str) -> str | None:
    status, body = get_json(f"{ADSBDB_HOST}/v0/callsign/{quote(callsign)}")
    if status != 200 or not isinstance(body, dict):
        return None
    response = body.get("response")
    if not isinstance(response, dict):
        return None
    flightroute = response.get("flightroute")
    if not isinstance(flightroute, dict):
        return None
    return normalize_flight_number(flightroute.get("callsign_iata"))


def resolve_iata_numbers(
    callsigns: list[str],
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, str]:
    cache = _read_cache()
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for raw in callsigns:
        callsign = raw.strip().upper()
        if not callsign:
            continue
        if cache.get(callsign):
            resolved[callsign] = cache[callsign]
        else:
            missing.append(callsign)

    concurrency = 6
    done = len(callsigns) - len(missing)
    if on_progress:
        on_progress(done, len(callsigns))

    for index in range(0, len(missing), concurrency):
        chunk = missing[index : index + concurrency]
        with ThreadPoolExecutor(max_workers=len(chunk) or 1) as pool:
            found = list(pool.map(_lookup_iata, chunk))
        for callsign, iata in zip(chunk, found):
            if iata:
                cache[callsign] = iata
                resolved[callsign] = iata
        done += len(chunk)
        if on_progress:
            on_progress(done, len(callsigns))

    _write_cache(cache)
    return resolved
