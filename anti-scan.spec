# -*- mode: python ; coding: utf-8 -*-

import os

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.')],
    hiddenimports=['psutil'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Exclure python3.dll (DLL de redirection qui fait echouer LoadLibrary dans _MEIxxxx sur Windows)
a.binaries = [x for x in a.binaries if x[0].lower() != 'python3.dll']

pyz = PYZ(a.pure)

# MODE --onefile : tout est bundle dans UN SEUL EXE autonome
# Fonctionne en distribution directe ET via install.ps1
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='anti-scan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
