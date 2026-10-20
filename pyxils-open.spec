# PyInstaller build description for the Windows desktop app.
from pathlib import Path

project = Path(SPECPATH)

a = Analysis(
    [str(project / "src" / "pyxils_open" / "__main__.py")],
    pathex=[str(project / "src")],
    binaries=[],
    datas=[],
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
