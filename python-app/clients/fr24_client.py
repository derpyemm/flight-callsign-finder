from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

from clients.http import FR24_HOST, get_json
from core.models import CallsignHit
from utils.formatters import duration_minutes_between, normalize_flight_number

MAX_PER_MINUTE = 9


def _day_slices(lookback_days: int) -> list[dict[str, str]]:
    slices: list[dict[str, str]] = []
    days = min(max(lookback_days, 1), 30)
    now = datetime.now(timezone.utc)
    for offset in range(days):
        day = now - timedelta(days=offset)
        start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        slices.append(
            {
                "from": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "to": end.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
    return slices


def _destination_of(row: dict[str, Any]) -> str | None:
    dest = (
        row.get("dest_icao_actual")
        or row.get("destination_icao_actual")
        or row.get("dest_icao")
        or row.get("destination_icao")
        or ""
    )
    dest = str(dest).upper()
    return dest or None


def _origin_of(row: dict[str, Any]) -> str | None:
    origin = str(row.get("orig_icao") or row.get("origin_icao") or "").upper()
    return origin or None


def _summary_params(
    slice_: dict[str, str],
    types: list[str],
    airports: str | None,
    routes: str | None,
) -> str:
    params = {
        "flight_datetime_from": slice_["from"],
        "flight_datetime_to": slice_["to"],
        "aircraft": ",".join(types),
        "limit": "20",
    }
    if airports:
        params["airports"] = airports
    if routes:
        params["routes"] = routes
    return urlencode(params)


def _fetch_summary(token: str, params: str) -> list[dict[str, Any]]:
    status, body = get_json(
        f"{FR24_HOST}/api/flight-summary/light?{params}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept-Version": "v1",
        },
    )
    if status == 401:
        raise RuntimeError("Flightradar24 token was rejected. Check the API token in settings.")
    if status == 429:
        raise RuntimeError("Flightradar24 rate or credit limit reached. Wait and try a shorter lookback.")
    if status != 200:
        raise RuntimeError(f"Flightradar24 search failed ({status})")
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        return [row for row in body["data"] if isinstance(row, dict)]
    return []


def search_fr24_flights(
    token: str,
    types: list[str],
    origin: str | None,
    destination: str | None,
    lookback_days: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[CallsignHit], int, bool]:
    slices = _day_slices(lookback_days)
    hits: list[CallsignHit] = []
    flights = 0
    truncated = False
    done = 0
    both_ends = bool(origin and destination)
    airports = None if both_ends else (f"inbound:{destination}" if destination else f"outbound:{origin}")
    routes = f"{origin}-{destination}" if both_ends else None

    def ingest(rows: list[dict[str, Any]]) -> None:
        nonlocal flights, truncated, done
        matched = []
        for row in rows:
            dest = _destination_of(row)
            from_icao = _origin_of(row)
            if destination and dest and dest != destination:
                continue
            if origin and from_icao and from_icao != origin:
                continue
            matched.append(row)
        if len(rows) >= 20:
            truncated = True
        flights += len(matched)
        for row in matched:
            callsign = str(row.get("callsign") or row.get("flight") or "").strip().upper()
            if not callsign:
                continue
            takeoff = row.get("datetime_takeoff") or None
            landed = row.get("datetime_landed") or None
            hits.append(
                CallsignHit(
                    callsign=callsign,
                    type=str(row.get("type") or types[0]).upper(),
                    count=1,
                    sources=["fr24"],
                    origin=_origin_of(row) or origin,
                    destination=_destination_of(row) or destination,
                    iata=normalize_flight_number(row.get("flight")),
                    duration_minutes=duration_minutes_between(row.get("datetime_takeoff"), row.get("datetime_landed")),
                    last_seen=takeoff or landed,
                )
            )
        done += 1
        if on_progress:
            on_progress(done, len(slices))

    def fetch_slice(slice_: dict[str, str]) -> list[dict[str, Any]]:
        return _fetch_summary(token, _summary_params(slice_, types, airports, routes))

    try:
        first_rows = fetch_slice(slices[0])
    except RuntimeError:
        if airports and airports.startswith("inbound:") and destination:
            airports = destination
            first_rows = fetch_slice(slices[0])
        elif airports and airports.startswith("outbound:") and origin:
            airports = origin
            first_rows = fetch_slice(slices[0])
        elif routes and destination:
            routes = None
            airports = f"inbound:{destination}"
            first_rows = fetch_slice(slices[0])
        else:
            raise
    ingest(first_rows)

    remaining = slices[1:]
    for start in range(0, len(remaining), MAX_PER_MINUTE):
        batch = remaining[start : start + MAX_PER_MINUTE]
        batch_started = time.monotonic()
        with ThreadPoolExecutor(max_workers=len(batch) or 1) as pool:
            rows_list = list(pool.map(fetch_slice, batch))
        for rows in rows_list:
            ingest(rows)
        if start + MAX_PER_MINUTE < len(remaining):
            wait = 60 - (time.monotonic() - batch_started)
            if wait > 0:
                time.sleep(wait)

    return hits, flights, truncated
