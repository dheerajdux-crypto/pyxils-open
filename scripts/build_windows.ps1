$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\pyinstaller.exe")) {
    Write-Error "PyInstaller is not installed. Run: .venv\Scripts\python.exe -m pip install -r requirements-dev.lock"
}

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist

# Python 3.14 ships Tcl/Tk libraries as zip archives. Extract them into the
# directories expected by PyInstaller's Tk runtime hook before building. Older
# Python versions are collected by PyInstaller's normal Tk hook.
$TclRoot = Join-Path $Root "build\_tcl_data"
$TkRoot = Join-Path $Root "build\_tk_data"
$TclTemp = Join-Path $Root "build\_tcl_temp"
$TkTemp = Join-Path $Root "build\_tk_temp"
$PythonHome = (& ".venv\Scripts\python.exe" -c "import sys; print(sys.base_prefix)").Trim()
$TclZip = Get-ChildItem (Join-Path $PythonHome "tcl") -Filter "libtcl*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
$TkZip = Get-ChildItem (Join-Path $PythonHome "tcl") -Filter "libtk*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($TclZip -and $TkZip) {
    New-Item -ItemType Directory -Force $TclTemp, $TkTemp | Out-Null
    Expand-Archive -LiteralPath $TclZip.FullName -DestinationPath $TclTemp -Force
    Expand-Archive -LiteralPath $TkZip.FullName -DestinationPath $TkTemp -Force
    New-Item -ItemType Directory -Force $TclRoot, $TkRoot | Out-Null
    Copy-Item (Join-Path $TclTemp "tcl_library\*") $TclRoot -Recurse -Force
    Copy-Item (Join-Path $TkTemp "tk_library\*") $TkRoot -Recurse -Force
}

& ".venv\Scripts\pyinstaller.exe" --noconfirm --clean "pyxils-open.spec"
Write-Host "Built dist\PyxilsOpen.exe"
