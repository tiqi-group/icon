# -*- mode: python ; coding: utf-8 -*-

import pydase, os

pydase_path = os.path.dirname(pydase.__file__)


a = Analysis(
    ["src/icon/server/__main__.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("src/icon/server/frontend", "frontend"),
        ("src/icon/server/data_access/db_context/sqlite/alembic", "icon/server/data_access/db_context/sqlite/alembic"),
        ("src/icon/server/data_access/templates/", "icon/server/data_access/templates"),
        (pydase_path, "pydase")
    ],
    hiddenimports=[
        "engineio.async_drivers.aiohttp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pyInstaller", "setuptools", "pkg_resources",

        # --- GUI / plotting / REPL not used in the server ---
        'matplotlib', 'PIL', 'IPython', 'pygments', 'colorama',

        # --- engineio/socketio unused async backends and managers ---
        'engineio.async_drivers.tornado',
        'eventlet', 'gevent', 'kombu', 'kafka',
        'anyio._backends._trio',

        # --- aiohttp extras not used in the server ---
        'aiohttp.worker', 'gunicorn', 'aiodns',

        # --- unused SQLAlchemy dialects (SQLite/postgres only) ---
        'sqlalchemy.dialects.mysql', 'sqlalchemy.dialects.oracle',

        # --- platform-specific / Windows-only bits (Linux build) ---
        'win32evtlog', 'win32evtlogutil', 'msvcrt', '_winreg', '_overlapped',
    ],
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
    name="icon",
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
