# -*- mode: python ; coding: utf-8 -*-

import os

# En el contexto de PyInstaller, __file__ puede no estar definido al ejecutar el spec.
# Usa el directorio de trabajo actual, que PyInstaller establece al del spec.
project_root = os.path.abspath('.')

datas = [
    (os.path.join(project_root, 'templates'), 'templates'),
    (os.path.join(project_root, 'static'), 'static'),
    (os.path.join(project_root, 'reports'), 'reports'),
    (os.path.join(project_root, 'SQL'), 'SQL'),
    (os.path.join(project_root, 'install'), 'install'),
    (os.path.join(project_root, '.env'), '.'),
]

hiddenimports = [
    'jinja2',
    'markupsafe',
    'dotenv',
]

a = Analysis(
    ['app.py'],
    pathex=[project_root],
    binaries=[],
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
    name='RepoStock',
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
