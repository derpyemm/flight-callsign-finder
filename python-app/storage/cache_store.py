from __future__ import annotations

import json
from pathlib import Path

from core.models import CallsignHit, SearchSource
from storage.paths import cache_path
from utils.formatters import prefer_flight_number


def _cache_key(aircraft: str, origin: str | None, destination: str | None) -> str:
    return f"{aircraft}|{origin or ''}|{destination or ''}"


def _read_store() -> dict[str, list[dict]]:
    path = cache_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_store(store: dict[str, list[dict]]) -> None:
    path: Path = cache_path()
    path.write_text(json.dumps(store), encoding="utf-8")


def _hit_from_dict(raw: dict) -> CallsignHit | None:
    callsign = str(raw.get("callsign", "")).strip().upper()
    if not callsign:
        return None
    sources = [source for source in raw.get("sources", []) if source in ("live", "fr24", "cache")]
    duration = raw.get("duration_minutes")
    if duration is None:
        duration = raw.get("durationMinutes")
    return CallsignHit(
        callsign=callsign,
        type=str(raw.get("type", "")).upper(),
        count=int(raw.get("count", 1) or 1),
        sources=sources,  # type: ignore[arg-type]
        origin=raw.get("origin") or None,
        destination=raw.get("destination") or None,
        iata=raw.get("iata") or None,
        duration_minutes=int(duration) if duration is not None else None,
        last_seen=raw.get("last_seen") or raw.get("lastSeen"),
    )


def _hit_to_dict(hit: CallsignHit) -> dict:
    return {
        "callsign": hit.callsign,
        "type": hit.type,
        "count": hit.count,
        "sources": hit.sources,
        "origin": hit.origin,
        "destination": hit.destination,
        "iata": hit.iata,
        "duration_minutes": hit.duration_minutes,
        "last_seen": hit.last_seen,
    }


def load_cached_hits(aircraft: str, origin: str | None, destination: str | None) -> list[CallsignHit]:
    rows = _read_store().get(_cache_key(aircraft, origin, destination), [])
    hits: list[CallsignHit] = []
    for row in rows:
        if isinstance(row, dict):
            hit = _hit_from_dict(row)
            if hit:
                hits.append(hit)
    return hits


def merge_hits(existing: list[CallsignHit], incoming: list[CallsignHit]) -> list[CallsignHit]:
    by_callsign: dict[str, CallsignHit] = {}
    for hit in [*existing, *incoming]:
        key = hit.callsign
        prev = by_callsign.get(key)
        if not prev:
            by_callsign[key] = CallsignHit(
                callsign=hit.callsign,
                type=hit.type,
                count=hit.count,
                sources=list(hit.sources),
                origin=hit.origin,
                destination=hit.destination,
                iata=hit.iata,
                duration_minutes=hit.duration_minutes,
                last_seen=hit.last_seen,
            )
            continue
        sources: list[SearchSource] = []
        for source in [*prev.sources, *hit.sources]:
            if source not in sources:
                sources.append(source)
        seen = [value for value in (prev.last_seen, hit.last_seen) if value]
        by_callsign[key] = CallsignHit(
            callsign=key,
            type=prev.type or hit.type,
            count=prev.count + hit.count,
            sources=sources,
            origin=hit.origin or prev.origin,
            destination=hit.destination or prev.destination,
            iata=prefer_flight_number(prev.iata, hit.iata),
            duration_minutes=hit.duration_minutes if hit.duration_minutes is not None else prev.duration_minutes,
            last_seen=sorted(seen)[-1] if seen else None,
        )
    return sorted(by_callsign.values(), key=lambda item: item.callsign)


def save_hits(aircraft: str, hits: list[CallsignHit], origin: str | None, destination: str | None) -> None:
    store = _read_store()
    store[_cache_key(aircraft, origin, destination)] = [_hit_to_dict(hit) for hit in hits]
    _write_store(store)
