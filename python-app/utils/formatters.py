from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
IATA_FLIGHT = re.compile(r"^([A-Z]{2}|[A-Z]\d|\d[A-Z])(\d{1,4}[A-Z]?)$")


def normalize_flight_number(value: str | None) -> str | None:
    if not value:
        return None
    flight = re.sub(r"\s+", "", value).upper()
    return flight or None


def split_iata_flight(flight: str) -> tuple[str, str] | None:
    match = IATA_FLIGHT.match(flight.strip().upper())
    if not match:
        return None
    return match.group(1), match.group(2)


def prefer_flight_number(left: str | None, right: str | None) -> str | None:
    first = normalize_flight_number(left)
    second = normalize_flight_number(right)
    if not first:
        return second
    if not second:
        return first
    digits = lambda value: len(re.search(r"\d+", value).group(0) if re.search(r"\d+", value) else "")
    return second if digits(second) > digits(first) else first


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if "T" not in text:
        text = text.replace(" ", "T", 1)
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_millis(value: str) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    return parsed.timestamp() * 1000


def duration_minutes_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    start_ms = _parse_millis(start)
    end_ms = _parse_millis(end)
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        return None
    return round((end_ms - start_ms) / 60000)


def scheduled_minutes_from_times(dep: str | None, arr: str | None) -> int | None:
    if not dep or not arr:
        return None
    if re.search(r"\d{4}-\d{2}-\d{2}", dep) and re.search(r"\d{4}-\d{2}-\d{2}", arr):
        return duration_minutes_between(dep, arr)
    dep_clock = re.search(r"(\d{1,2}):(\d{2})\s*$", dep)
    arr_clock = re.search(r"(\d{1,2}):(\d{2})\s*$", arr)
    if not dep_clock or not arr_clock:
        return None
    minutes = (
        int(arr_clock.group(1)) * 60
        + int(arr_clock.group(2))
        - (int(dep_clock.group(1)) * 60 + int(dep_clock.group(2)))
    )
    if minutes <= 0:
        minutes += 24 * 60
    return minutes


def google_flight_url(flight: str | None) -> str | None:
    iata = normalize_flight_number(flight)
    if not iata or not split_iata_flight(iata):
        return None
    return f"https://www.google.com/search?q={quote(iata)}"


def format_flight_day(iso: str | None) -> str:
    date = parse_utc(iso)
    if not date:
        return "—"
    return f"{date.day} {MONTHS[date.month - 1]} {date.year}"


def format_departure_utc(iso: str | None) -> str:
    date = parse_utc(iso)
    if not date:
        return "—"
    return f"{date.hour:02d}:{date.minute:02d}"


def format_departure(iso: str | None) -> str:
    date = parse_utc(iso)
    if not date:
        return "—"
    return f"{date.day} {MONTHS[date.month - 1]} {date.hour:02d}:{date.minute:02d}Z"


def format_route(origin: str | None, destination: str | None) -> str:
    if origin and destination:
        return f"{origin} → {destination}"
    if origin:
        return f"{origin} →"
    if destination:
        return f"→ {destination}"
    return "—"


def format_duration(minutes: int | None) -> str:
    if minutes is None or minutes <= 0:
        return "—"
    hours, rest = divmod(minutes, 60)
    if hours == 0:
        return f"{rest}m"
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h {rest}m"


def route_summary(origin: str | None, destination: str | None) -> str:
    if origin and destination:
        return f"{origin} → {destination}"
    if destination:
        return f"into {destination}"
    if origin:
        return f"out of {origin}"
    return ""


def route_phrase(origin: str | None, destination: str | None) -> str:
    if origin and destination:
        return f"on {origin} → {destination}"
    if destination:
        return f"into {destination}"
    return f"out of {origin}"
