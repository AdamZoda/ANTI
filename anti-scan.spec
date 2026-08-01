# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Localiser le dossier psutil pour forcer l'inclusion de son .pyd natif
psutil_dir = None
for p in sys.path:
    candidate = os.path.join(p, 'psutil')
    if os.path.isdir(candidate):
        psutil_dir = candidate
        break

# Construire la liste des binaires psutil (.pyd) à forcer dans le bundle
psutil_binaries = []
if psutil_dir:
    for f in os.listdir(psutil_dir):
        if f.endswith('.pyd') or f.endswith('.dll'):
            psutil_binaries.append((os.path.join(psutil_dir, f), 'psutil'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=psutil_binaries,
    datas=[('config.json', '.')],
    hiddenimports=[
        'psutil',
        'psutil._pswindows',
        'psutil._psutil_windows',
        'psutil._common',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'tk', 'tcl'],
    noarchive=False,
    optimize=0,
)

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
