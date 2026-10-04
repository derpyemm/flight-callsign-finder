from __future__ import annotations

import re
from typing import Callable

from clients.adsbdb_client import resolve_iata_numbers
from clients.fr24_client import search_fr24_flights
from core.models import SearchResult
from storage.cache_store import load_cached_hits, merge_hits, save_hits
from utils.aircraft_families import expand_aircraft_types, normalize_icao_type, optional_icao_airport
from utils.formatters import prefer_flight_number, route_phrase


ProgressFn = Callable[[str], None]


def _validate_airport(code: str | None, role: str) -> str | None:
    if not code:
        return None
    if not re.fullmatch(r"[A-Z]{4}", code):
        if role == "departure":
            raise ValueError("Enter a 4-letter ICAO departure code such as LSZH, or leave it blank.")
        raise ValueError("Enter a 4-letter ICAO arrival code such as EHAM, or leave it blank.")
    return code


def search_callsigns(
    aircraft: str,
    origin: str | None,
    destination: str | None,
    include_family: bool,
    fr24_token: str | None = None,
    fr24_lookback_days: int | None = None,
    on_progress: ProgressFn | None = None,
) -> SearchResult:
    aircraft_code = normalize_icao_type(aircraft)
    origin_code = _validate_airport(optional_icao_airport(origin), "departure")
    destination_code = _validate_airport(optional_icao_airport(destination), "arrival")
    types = expand_aircraft_types(aircraft_code, include_family)
    warnings: list[str] = []
    where = route_phrase(origin_code, destination_code)

    if not re.fullmatch(r"[A-Z0-9]{2,4}", aircraft_code):
        raise ValueError("Enter an ICAO aircraft type such as A320 or B738.")
    if not origin_code and not destination_code:
        raise ValueError("Enter a departure airport, an arrival airport, or both.")

    token = (fr24_token or "").strip()
    if not token:
        raise ValueError("Add a Flightradar24 API token in Settings before searching.")

    lookback = fr24_lookback_days or 0
    if lookback < 1:
        raise ValueError("Set history days to at least 1 in Settings.")

    if on_progress:
        if lookback == 1:
            on_progress("Asking Flightradar24 for today…")
        elif lookback == 2:
            on_progress("Asking Flightradar24 for today and yesterday…")
        else:
            on_progress(f"Asking Flightradar24 for the last {lookback} days…")

    def fr24_progress(done: int, total: int) -> None:
        if on_progress:
            on_progress(f"Flightradar24 lookback {done}/{total} days…")

    historic_hits, historic_flights, truncated = search_fr24_flights(
        token, types, origin_code, destination_code, lookback, fr24_progress
    )
    if truncated:
        warnings.append(
            "Flightradar24 Explorer returns at most 20 flights per day, so some busy days may be incomplete."
        )
    if historic_flights == 0:
        warnings.append(f"Flightradar24 found no {'/'.join(types)} flights {where} in that window.")

    cached = [hit for hit in load_cached_hits(aircraft_code, origin_code, destination_code) if "fr24" in hit.sources]
    hits = merge_hits(cached, historic_hits)
    missing_iata = [hit.callsign for hit in hits if not hit.iata]
    if missing_iata:
        if on_progress:
            on_progress("Looking up IATA flight numbers…")
        try:
            iata_by_callsign = resolve_iata_numbers(missing_iata)
        except RuntimeError:
            warnings.append("Could not look up IATA flight numbers.")
            iata_by_callsign = {}
        for hit in hits:
            hit.iata = prefer_flight_number(hit.iata, iata_by_callsign.get(hit.callsign))

    save_hits(aircraft_code, hits, origin_code, destination_code)

    return SearchResult(
        aircraft=aircraft_code,
        origin=origin_code,
        destination=destination_code,
        types=types,
        hits=hits,
        live_checked=0,
        live_matched=0,
        fr24_days=lookback,
        fr24_flights=historic_flights,
        truncated=truncated,
        warnings=warnings,
    )
