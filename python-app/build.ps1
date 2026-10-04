$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is required to build Callsign Finder."
}

python -m pip install -r requirements.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "CallsignFinder" `
    --icon assets/app.ico `
    --add-data "assets/app.ico;assets" `
    --add-data "assets/app.png;assets" `
    --hidden-import PySide6.QtWebEngineWidgets `
    --hidden-import PySide6.QtWebEngineCore `
    --collect-all PySide6.QtWebEngineCore `
    --collect-all PySide6.QtWebEngineWidgets `
    main.py

Write-Host "Built python-app/dist/CallsignFinder.exe"
