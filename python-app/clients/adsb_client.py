from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

from clients.http import ADSB_HOST, get_json, post_json
from core.models import CallsignHit


def _trim_callsign(value: str | None) -> str | None:
    callsign = (value or "").strip().upper()
    return callsign or None


def _fetch_airport(icao: str) -> dict[str, Any]:
    status, body = get_json(f"{ADSB_HOST}/api/0/airport/{quote(icao)}")
    if status != 200:
        raise RuntimeError(f"Unknown airport {icao} ({status})")
    if not isinstance(body, dict) or body.get("lat") is None or body.get("lon") is None:
        raise RuntimeError(f"No coordinates for {icao}.")
    return body


def _fetch_nearby(lat: float, lon: float, dist: int) -> list[dict[str, Any]]:
    for attempt in range(3):
        status, body = get_json(f"{ADSB_HOST}/v2/lat/{lat}/lon/{lon}/dist/{dist}")
        if status == 429:
            time.sleep(1.5 * (attempt + 1))
            continue
        if status != 200:
            raise RuntimeError(f"Live area search failed ({status})")
        if isinstance(body, dict) and isinstance(body.get("ac"), list):
            return body["ac"]
        return []
    return []


def _fetch_routes(planes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    chunk_size = 15
    index = 0
    while index < len(planes):
        chunk = planes[index : index + chunk_size]
        status, body = post_json(
            f"{ADSB_HOST}/api/0/routeset",
            {"planes": chunk},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if status == 429:
            time.sleep(1.5)
            continue
        if status == 200 and isinstance(body, list):
            routes.extend(item for item in body if isinstance(item, dict))
        index += chunk_size
    return routes


def _destination_icao(row: dict[str, Any]) -> str | None:
    airports = row.get("_airports")
    if isinstance(airports, list) and airports:
        last = airports[-1]
        if isinstance(last, dict) and last.get("icao"):
            return str(last["icao"]).upper()
    codes = [part.strip().upper() for part in str(row.get("airport_codes") or "").split("-")]
    return codes[-1] if codes and codes[-1] else None


def _origin_icao(row: dict[str, Any]) -> str | None:
    airports = row.get("_airports")
    if isinstance(airports, list) and airports:
        first = airports[0]
        if isinstance(first, dict) and first.get("icao"):
            return str(first["icao"]).upper()
    codes = [part.strip().upper() for part in str(row.get("airport_codes") or "").split("-")]
    return codes[0] if codes and codes[0] else None


def _is_at_airport(item: dict[str, Any] | None) -> bool:
    if not item or item.get("dst") is None:
        return False
    alt = item.get("alt_baro")
    on_ground = alt == "ground" or alt == 0
    return bool(on_ground and item["dst"] < 8)


def _fetch_type_worldwide(type_code: str) -> list[dict[str, Any]]:
    status, body = get_json(f"{ADSB_HOST}/v2/type/{quote(type_code)}")
    if status != 200 or not isinstance(body, dict) or not isinstance(body.get("ac"), list):
        return []
    return body["ac"]


def _airport_codes(icao: str) -> set[str]:
    info = _fetch_airport(icao)
    return {code.upper() for code in (icao, info.get("icao"), info.get("iata")) if code}


def search_live_flights(
    types: list[str],
    origin: str | None,
    destination: str | None,
) -> tuple[list[CallsignHit], int, int]:
    nearby_airport = destination or origin
    if not nearby_airport:
        return [], 0, 0

    info = _fetch_airport(nearby_airport)
    wanted = {code.upper() for code in types}
    nearby = _fetch_nearby(float(info["lat"]), float(info["lon"]), 250)
    worldwide: list[dict[str, Any]] = []
    for type_code in types:
        all_of_type = _fetch_type_worldwide(type_code)
        if all_of_type and len(all_of_type) <= 80:
            worldwide.extend(all_of_type)

    of_type = [
        item
        for item in [*nearby, *worldwide]
        if isinstance(item, dict) and item.get("t") and str(item["t"]).upper() in wanted
    ]

    by_callsign: dict[str, dict[str, Any]] = {}
    for item in of_type:
        callsign = _trim_callsign(item.get("flight"))
        if callsign:
            by_callsign[callsign] = item

    planes = [
        {"callsign": callsign, "lat": item.get("lat") or 0, "lng": item.get("lon") or 0}
        for callsign, item in by_callsign.items()
    ]
    routes = _fetch_routes(planes) if planes else []
    dest_codes = _airport_codes(destination) if destination else None
    origin_codes = _airport_codes(origin) if origin else None
    hits: list[CallsignHit] = []
    matched: set[str] = set()

    for row in routes:
        callsign = _trim_callsign(row.get("callsign"))
        if not callsign:
            continue
        dest = _destination_icao(row)
        from_icao = _origin_icao(row)
        dest_ok = not dest_codes or (dest in dest_codes if dest else _is_at_airport(by_callsign.get(callsign)))
        origin_ok = not origin_codes or (from_icao in origin_codes if from_icao else _is_at_airport(by_callsign.get(callsign)))
        if not dest_ok or not origin_ok:
            continue
        if origin and destination and (not from_icao or not dest):
            continue
        matched.add(callsign)
        hits.append(
            CallsignHit(
                callsign=callsign,
                type=str(by_callsign.get(callsign, {}).get("t") or types[0]).upper(),
                count=1,
                sources=["live"],
                origin=from_icao,
                destination=dest,
            )
        )

    if not (origin and destination):
        for callsign, item in by_callsign.items():
            if callsign in matched or not _is_at_airport(item):
                continue
            hits.append(
                CallsignHit(
                    callsign=callsign,
                    type=str(item.get("t") or types[0]).upper(),
                    count=1,
                    sources=["live"],
                    origin=origin,
                    destination=destination,
                )
            )

    return hits, len(by_callsign), len(hits)
