from __future__ import annotations

import json

from core.models import Fr24Settings
from storage.paths import settings_path


def load_settings() -> Fr24Settings:
    path = settings_path()
    if not path.exists():
        return Fr24Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Fr24Settings()
    token = str(raw.get("token", "") or "")
    try:
        lookback = int(raw.get("lookback_days", 2))
    except (TypeError, ValueError):
        lookback = 2
    return Fr24Settings(
        token=token,
        lookback_days=max(1, min(lookback, 30)),
        simbrief_id=str(raw.get("simbrief_id", "") or ""),
    )


def save_settings(settings: Fr24Settings) -> None:
    payload = {
        "token": settings.token.strip(),
        "lookback_days": max(1, min(settings.lookback_days, 30)),
        "simbrief_id": settings.simbrief_id.strip(),
    }
    settings_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
