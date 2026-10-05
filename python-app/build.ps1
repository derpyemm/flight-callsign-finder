$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is required to build Callsign Finder."
}

python -m pip install -r requirements.txt

# Folder build (not --onefile): a one-file exe unpacks Qt/WebEngine on every launch.
$excludes = @(
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DRender", "PySide6.QtBluetooth", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtTextToSpeech"
)
$excludeArgs = foreach ($module in $excludes) { @("--exclude-module", $module) }

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --noupx `
    --name "CallsignFinder" `
    --icon assets/app.ico `
    --add-data "assets/app.ico;assets" `
    --add-data "assets/app.png;assets" `
    --hidden-import PySide6.QtWebEngineWidgets `
    --hidden-import PySide6.QtWebEngineCore `
    --hidden-import PySide6.QtWebChannel `
    --collect-all PySide6.QtWebEngineCore `
    --collect-all PySide6.QtWebEngineWidgets `
    @excludeArgs `
    main.py

$built = Join-Path $PSScriptRoot "dist\CallsignFinder\CallsignFinder.exe"
$zip = Join-Path $PSScriptRoot "dist\CallsignFinder.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
Compress-Archive -Path (Join-Path $PSScriptRoot "dist\CallsignFinder") -DestinationPath $zip -Force
Write-Host "Built $built"
Write-Host "Shareable zip: $zip"
