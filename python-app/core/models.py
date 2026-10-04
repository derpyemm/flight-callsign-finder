from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SearchSource = Literal["live", "fr24", "cache"]


@dataclass
class CallsignHit:
    callsign: str
    type: str
    count: int
    sources: list[SearchSource] = field(default_factory=list)
    origin: str | None = None
    destination: str | None = None
    iata: str | None = None
    duration_minutes: int | None = None
    last_seen: str | None = None


@dataclass
class SearchResult:
    aircraft: str
    types: list[str]
    hits: list[CallsignHit]
    live_checked: int
    live_matched: int
    warnings: list[str]
    origin: str | None = None
    destination: str | None = None
    fr24_days: int | None = None
    fr24_flights: int | None = None
    truncated: bool = False


@dataclass
class Fr24Settings:
    token: str = ""
    lookback_days: int = 2
