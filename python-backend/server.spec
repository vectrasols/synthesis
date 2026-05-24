# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


backend_dir = Path(SPECPATH).resolve()
datas = []
binaries = []
hiddenimports = [
    'data_service',
    'chart_service',
    'ml_service',
]

for package in ('numpy', 'pandas', 'sklearn', 'scipy', 'pyarrow', 'openpyxl'):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for distribution in ('numpy', 'pandas', 'scikit-learn', 'scipy', 'pyarrow', 'openpyxl'):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass


a = Analysis(
    [str(backend_dir / 'server.py')],
    pathex=[str(backend_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
