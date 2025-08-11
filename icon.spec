# -*- mode: python ; coding: utf-8 -*-

import pydase, os

pydase_path = os.path.dirname(pydase.__file__)


a = Analysis(
    ['src/icon/server/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/icon/server/frontend', 'frontend'),
        ('src/icon/server/data_access/db_context/sqlite/alembic', 'icon/server/data_access/db_context/sqlite/alembic'),
        ('src/icon/server/data_access/templates/', 'icon/server/data_access/templates'),
        (pydase_path, 'pydase')
    ],
    hiddenimports=[
        'engineio.async_drivers.aiohttp',
    ],
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
    name='icon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# vim: ft=py
