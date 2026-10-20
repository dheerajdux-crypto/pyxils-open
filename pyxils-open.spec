# PyInstaller build description for the Windows desktop app.
from pathlib import Path

project = Path(SPECPATH)
datas = []
for folder, target in ((project / "build" / "_tcl_data", "_tcl_data"),
                       (project / "build" / "_tk_data", "_tk_data")):
    if folder.exists():
        datas.append((str(folder), target))

a = Analysis(
    [str(project / "build_entry.py")],
    pathex=[str(project / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PyxilsOpen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
