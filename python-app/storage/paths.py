from pathlib import Path
import os


APP_NAME = "CallsignFinder"


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def cache_path() -> Path:
    return app_data_dir() / "cache.json"


def iata_cache_path() -> Path:
    return app_data_dir() / "iata-cache.json"


def airport_cache_path() -> Path:
    return app_data_dir() / "airports.json"


def airport_catalog_path() -> Path:
    return app_data_dir() / "airports-catalog.json"
