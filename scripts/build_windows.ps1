$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\pyinstaller.exe")) {
    Write-Error "PyInstaller is not installed. Run: .venv\Scripts\python.exe -m pip install -r requirements-dev.lock"
}

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
& ".venv\Scripts\pyinstaller.exe" --noconfirm --clean "pyxils-open.spec"
Write-Host "Built dist\PyxilsOpen.exe"
