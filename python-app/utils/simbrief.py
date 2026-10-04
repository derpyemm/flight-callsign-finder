from __future__ import annotations

import re
from urllib.parse import urlencode

from core.models import CallsignHit
from utils.formatters import split_iata_flight

DISPATCH_URL = "https://dispatch.simbrief.com/options/custom"

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


def _icao_airline(callsign: str) -> str | None:
    match = ICAO_PREFIX.match(callsign.strip().upper())
    return match.group(1) if match else None


def _iata_flight_number(iata: str | None) -> str | None:
    if not iata:
        return None
    split = split_iata_flight(iata)
    if not split:
        return None
    digits = "".join(ch for ch in split[1] if ch.isdigit())
    return digits or None


def simbrief_dispatch_url(hit: CallsignHit) -> str:
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
    airline = _icao_airline(hit.callsign)
    if airline:
        params["airline"] = airline
    fltnum = _iata_flight_number(hit.iata)
    if fltnum:
        params["fltnum"] = fltnum
    if aircraft == "BCS3":
        params.update(BCS3_PROFILES)

    return f"{DISPATCH_URL}?{urlencode(params)}"
