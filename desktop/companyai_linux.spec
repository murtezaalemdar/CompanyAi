# -*- mode: python ; coding: utf-8 -*-
"""
CompanyAI Desktop — Linux PyInstaller Spec Dosyası
Kullanım: pyinstaller desktop/companyai_linux.spec --noconfirm --clean
Gereksinimler: gir1.2-webkit2-4.0, python3-gi
"""

import os

block_cipher = None
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

a = Analysis(
    [os.path.join(ROOT, 'desktop', 'app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        'webview',
        'webview.platforms.gtk',
        'gi',
        'gi.repository.Gtk',
        'gi.repository.WebKit2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CompanyAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
