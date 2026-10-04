from __future__ import annotations

import json
from typing import Any

import requests

ADSB_HOST = "https://api.adsb.lol"
FR24_HOST = "https://fr24api.flightradar24.com"
ADSBDB_HOST = "https://api.adsbdb.com"

_DEFAULT_HEADERS = {"User-Agent": "CallsignFinder/1.0"}


def _network_error(url: str, exc: requests.RequestException) -> RuntimeError:
    host = "the flight data service"
    if "flightradar24" in url:
        host = "Flightradar24"
    elif "adsbdb" in url:
        host = "the IATA lookup service"
    elif "openstreetmap.org" in url or "openflights" in url:
        host = "the airport map catalog"
    elif "adsb.lol" in url:
        host = "the airport lookup service"
    if isinstance(exc, requests.Timeout):
        return RuntimeError(f"{host} timed out. Try again.")
    return RuntimeError(f"Could not reach {host}. Check your internet connection and try again.")


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> tuple[int, Any]:
    try:
        response = requests.get(url, headers={**_DEFAULT_HEADERS, **(headers or {})}, timeout=timeout)
    except requests.RequestException as exc:
        raise _network_error(url, exc) from exc
    return response.status_code, _parse_body(response)


def get_text(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> tuple[int, str]:
    try:
        response = requests.get(url, headers={**_DEFAULT_HEADERS, **(headers or {})}, timeout=timeout)
    except requests.RequestException as exc:
        raise _network_error(url, exc) from exc
    return response.status_code, response.text


def post_json(url: str, payload: Any, headers: dict[str, str] | None = None, timeout: int = 30) -> tuple[int, Any]:
    try:
        response = requests.post(url, json=payload, headers={**_DEFAULT_HEADERS, **(headers or {})}, timeout=timeout)
    except requests.RequestException as exc:
        raise _network_error(url, exc) from exc
    return response.status_code, _parse_body(response)


def _parse_body(response: requests.Response) -> Any:
    text = response.text
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
