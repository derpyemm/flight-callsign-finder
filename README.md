# Callsign finder

Standalone Windows app that finds which callsigns an ICAO aircraft type uses into or out of an ICAO airport.

This Python desktop build is the application. It talks to Flightradar24 directly, stores the API token on this computer, and exits completely when you close the window.

Search uses a Flightradar24 Explorer token for scheduled and landed flights, up to 30 days. Results include IATA numbers, block times, SimBrief dispatch prefill, and a dark OpenStreetMap route map.

## Run

Needs Python 3.11 or newer.

```powershell
cd python-app
python -m pip install -r requirements.txt
python main.py
```

Or double-click `start.cmd` after the packages are installed.

## Build

```powershell
cd python-app
.\build.ps1
```

The packaged file is `python-app/dist/CallsignFinder.exe`.

Settings, token, and caches live in `%APPDATA%\CallsignFinder\`.

## Earlier web prototype

The TypeScript code in this repo is the previous browser prototype and is no longer the supported app.
