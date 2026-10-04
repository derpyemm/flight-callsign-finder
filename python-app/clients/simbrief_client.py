from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from clients.http import _DEFAULT_HEADERS, _network_error
from core.models import CallsignHit
from utils.simbrief import parse_landing_utc, shift_offblock, simbrief_dispatch_url, simbrief_generate_form_url, simbrief_params


GENERATE_URL = "https://www.simbrief.com/ofp/ofp.loader.api.php"
FETCH_URL = "https://www.simbrief.com/api/xml.fetcher.php"
_ERROR_TAG = re.compile(r"<error[^>]*>(.*?)</error>", re.IGNORECASE | re.DOTALL)


class SimbriefError(RuntimeError):
    pass


class SimbriefAuthError(SimbriefError):
    pass


class SimbriefNoOfpError(SimbriefError):
    pass


def user_params(simbrief_id: str) -> dict[str, str]:
    ident = simbrief_id.strip()
    if ident.isdigit():
        return {"userid": ident}
    return {"username": ident}


def seed_offblock(landing: datetime) -> datetime:
    return landing - timedelta(hours=2)


def reference_dispatch_url(
    hit: CallsignHit,
    landing_text: str,
    taxiout: int | None = None,
) -> str:
    landing = parse_landing_utc(landing_text)
    if not landing:
        raise ValueError("Enter a landing time like 18:30, or 4 Oct 18:30.")
    return simbrief_generate_form_url(hit, seed_offblock(landing), taxiout)


def try_generate_plan(
    hit: CallsignHit,
    offblock: datetime,
    simbrief_id: str,
    previous_id: str,
    taxiout: int | None = None,
) -> dict[str, Any] | None:
    params = {**simbrief_params(hit, offblock, taxiout), **user_params(simbrief_id)}
    try:
        requests.get(
            GENERATE_URL,
            params=params,
            headers=_DEFAULT_HEADERS,
            timeout=20,
            allow_redirects=True,
        )
    except requests.RequestException:
        return None
    try:
        ofp = fetch_latest_ofp(simbrief_id)
    except SimbriefError:
        return None
    if ofp_request_id(ofp) != previous_id and ofp_matches_route(ofp, hit):
        return ofp
    return None


def fetch_latest_ofp(simbrief_id: str) -> dict[str, Any]:
    last_error = "Could not read the SimBrief flight plan."
    for json_mode in ("v2", "1"):
        params = {**user_params(simbrief_id), "json": json_mode}
        try:
            response = requests.get(
                f"{FETCH_URL}?{urlencode(params)}",
                headers=_DEFAULT_HEADERS,
                timeout=45,
            )
        except requests.RequestException as exc:
            raise _network_error(FETCH_URL, exc) from exc
        if response.status_code == 200:
            body = _parse_json(response.text)
            if isinstance(body, dict) and (body.get("times") or body.get("origin")):
                return body
        extracted = _simbrief_error(response.text)
        if extracted:
            last_error = extracted
        if response.status_code == 400:
            break
    raise _error_from_text(last_error)


def fetch_latest_ofp_or_none(simbrief_id: str) -> dict[str, Any] | None:
    try:
        return fetch_latest_ofp(simbrief_id)
    except SimbriefAuthError:
        raise
    except SimbriefError:
        return None


def ofp_request_id(ofp: dict[str, Any] | None) -> str:
    if not ofp:
        return ""
    params = ofp.get("params") if isinstance(ofp.get("params"), dict) else {}
    return str(params.get("request_id") or "")


def ofp_matches_route(ofp: dict[str, Any], hit: CallsignHit) -> bool:
    return _ofp_route(ofp) == ((hit.origin or "").upper(), (hit.destination or "").upper())


def timed_dispatch_url(
    hit: CallsignHit,
    landing_text: str,
    ofp: dict[str, Any],
    taxiout: int | None = None,
) -> str:
    landing = parse_landing_utc(landing_text)
    if not landing:
        return simbrief_dispatch_url(hit, taxiout=taxiout)
    est_out, est_on = ofp_landing_times(ofp)
    return simbrief_dispatch_url(hit, offblock=shift_offblock(est_out, est_on, landing), taxiout=taxiout)


def ofp_from_reference(hit: CallsignHit, simbrief_id: str, previous_id: str) -> dict[str, Any]:
    ofp = fetch_latest_ofp(simbrief_id)
    if ofp_request_id(ofp) == previous_id:
        raise SimbriefError("Generate the reference plan in SimBrief first, then click Continue.")
    if not ofp_matches_route(ofp, hit):
        raise SimbriefError("SimBrief's latest plan is a different route. Generate the reference flight, then Continue.")
    return ofp


def ofp_landing_times(ofp: dict[str, Any]) -> tuple[datetime, datetime]:
    times = ofp.get("times")
    if not isinstance(times, dict):
        times = {}
    offblock = _parse_ofp_time(times.get("est_out") or times.get("sched_out"))
    landing = _parse_ofp_time(times.get("est_on") or times.get("sched_on"))
    if not offblock or not landing:
        raise SimbriefError("SimBrief did not return an expected landing time.")
    return offblock, landing


def _ofp_route(ofp: dict[str, Any]) -> tuple[str, str]:
    origin = ofp.get("origin") if isinstance(ofp.get("origin"), dict) else {}
    dest = ofp.get("destination") if isinstance(ofp.get("destination"), dict) else {}
    return str(origin.get("icao_code") or "").upper(), str(dest.get("icao_code") or "").upper()


def _parse_ofp_time(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        stamp = int(value)
        if stamp > 10_000_000:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        return None
    text = str(value).strip()
    if text.isdigit():
        stamp = int(text)
        if stamp > 10_000_000:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_json(text: str) -> Any:
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _simbrief_error(text: str) -> str | None:
    if not text:
        return None
    match = _ERROR_TAG.search(text)
    if match:
        return " ".join(match.group(1).split())
    body = _parse_json(text)
    if isinstance(body, dict):
        for key in ("Error", "error", "message"):
            value = body.get(key)
            if value:
                return str(value)
    return None


def _error_from_text(text: str) -> SimbriefError:
    lowered = text.lower()
    if "invalid" in lowered and (
        "user" in lowered or "username" in lowered or "userid" in lowered or "pilot" in lowered
    ):
        return SimbriefAuthError("SimBrief rejected that Pilot ID or username. Check it in API settings.")
    if "no flight" in lowered or "not found" in lowered or "no ofp" in lowered or "on file" in lowered:
        return SimbriefNoOfpError("No SimBrief flight plan on file yet.")
    compact = " ".join(text.split())
    return SimbriefError(compact[:220] if compact else "Could not read the SimBrief flight plan.")
