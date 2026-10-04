from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from core.models import CallsignHit
from utils.formatters import split_iata_flight

DISPATCH_URL = "https://dispatch.simbrief.com/options/custom"
GENERATE_FORM_URL = "https://www.simbrief.com/system/dispatch.php"

# Official Synaptic / iniBuilds (MSFS) A220-300 airframe.
# https://forum.inibuilds.com/topic/37220-simbrief-profile-a220/
BCS3_AIRFRAME_ID = "347385_1783098201479"

AIRFRAMES: dict[str, str] = {
    "BCS3": BCS3_AIRFRAME_ID,
}

BCS3_PROFILES = {
    "climb": "250/275/78",
    "cruise": "M778",
    "descent": "78/275/250",
}

ICAO_PREFIX = re.compile(r"^([A-Z]{3})\d")
_TIME_ONLY = re.compile(r"^(\d{1,2})[:.]?(\d{2})$")
_DAY_MONTH_TIME = re.compile(
    r"^(\d{1,2})\s*([A-Z]{3})(?:\s*(\d{2}|\d{4}))?\s+(\d{1,2})[:.]?(\d{2})$"
)
_ISO_TIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2})[:.]?(\d{2})$")
_SIMBRIEF_MONTHS = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)
_MONTH_NUM = {name: index + 1 for index, name in enumerate(_SIMBRIEF_MONTHS)}
_TAXI_OUT = re.compile(r"^\d{1,2}$")


def icao_airline(callsign: str) -> str | None:
    match = ICAO_PREFIX.match(callsign.strip().upper())
    return match.group(1) if match else None


def iata_flight_number(iata: str | None) -> str | None:
    if not iata:
        return None
    split = split_iata_flight(iata)
    if not split:
        return None
    digits = "".join(ch for ch in split[1] if ch.isdigit())
    return digits or None


def parse_landing_utc(text: str, now: datetime | None = None) -> datetime | None:
    raw = (text or "").strip().upper().replace("Z", "").strip()
    if not raw:
        return None
    clock = now or datetime.now(timezone.utc)
    iso = _ISO_TIME.fullmatch(raw)
    if iso:
        year, month, day, hour, minute = (int(part) for part in iso.groups())
        return _aware(year, month, day, hour, minute)
    dated = _DAY_MONTH_TIME.fullmatch(raw)
    if dated:
        day_s, month_s, year_s, hour_s, minute_s = dated.groups()
        month = _MONTH_NUM.get(month_s)
        if not month:
            raise ValueError("Enter a landing time like 18:30, or 4 Oct 18:30.")
        if year_s is None:
            year = clock.year
        elif len(year_s) == 2:
            year = 2000 + int(year_s)
        else:
            year = int(year_s)
        return _aware(year, month, int(day_s), int(hour_s), int(minute_s))
    timed = _TIME_ONLY.fullmatch(raw.replace(" ", ""))
    if timed:
        hour, minute = int(timed.group(1)), int(timed.group(2))
        landing = _aware(clock.year, clock.month, clock.day, hour, minute)
        if landing < clock - timedelta(hours=1):
            landing += timedelta(days=1)
        return landing
    raise ValueError("Enter a landing time like 18:30, or 4 Oct 18:30.")


def parse_taxi_out(text: str) -> int | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if not _TAXI_OUT.fullmatch(raw):
        raise ValueError("Taxi-out must be minutes, such as 12, or left empty for SimBrief’s default.")
    minutes = int(raw)
    if minutes > 90:
        raise ValueError("Taxi-out must be between 0 and 90 minutes, or empty for SimBrief’s default.")
    return minutes


def _aware(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Landing time must be a valid UTC clock, such as 18:30.")
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def simbrief_date(value: datetime) -> str:
    return f"{value.day:02d}{_SIMBRIEF_MONTHS[value.month - 1]}{value.year % 100:02d}"


def shift_offblock(est_out: datetime, est_on: datetime, desired_on: datetime) -> datetime:
    minutes = round((desired_on - est_on).total_seconds() / 60)
    predicted = est_on + timedelta(minutes=minutes)
    if timedelta(0) < (predicted - desired_on) < timedelta(seconds=30):
        minutes += 1
    return est_out + timedelta(minutes=minutes)


def simbrief_params(
    hit: CallsignHit,
    offblock: datetime | None = None,
    taxiout: int | None = None,
) -> dict[str, str]:
    origin = (hit.origin or "").upper()
    destination = (hit.destination or "").upper()
    aircraft = (hit.type or "").upper()
    if len(origin) != 4 or len(destination) != 4 or not aircraft:
        raise ValueError("Need origin, destination, and aircraft type to open SimBrief.")

    params: dict[str, str] = {
        "orig": origin,
        "dest": destination,
        "type": AIRFRAMES.get(aircraft, aircraft),
        "callsign": hit.callsign,
    }
    airline = icao_airline(hit.callsign)
    if airline:
        params["airline"] = airline
    fltnum = iata_flight_number(hit.iata)
    if fltnum:
        params["fltnum"] = fltnum
    if aircraft == "BCS3":
        params.update(BCS3_PROFILES)
    if offblock:
        params["date"] = simbrief_date(offblock)
        params["deph"] = str(offblock.hour)
        params["depm"] = f"{offblock.minute:02d}"
    if taxiout is not None:
        params["taxiout"] = str(taxiout)
    return params


def simbrief_dispatch_url(
    hit: CallsignHit,
    offblock: datetime | None = None,
    taxiout: int | None = None,
) -> str:
    return f"{DISPATCH_URL}?{urlencode(simbrief_params(hit, offblock, taxiout))}"


def simbrief_generate_form_url(
    hit: CallsignHit,
    offblock: datetime,
    taxiout: int | None = None,
) -> str:
    return f"{GENERATE_FORM_URL}?{urlencode(simbrief_params(hit, offblock, taxiout))}"
