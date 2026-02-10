# -*- mode: python ; coding: utf-8 -*-
"""
CompanyAI Desktop — PyInstaller Spec Dosyası
Kullanım: pyinstaller desktop/companyai.spec
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
        'webview.platforms.edgechromium',   # Windows Edge WebView2
        'webview.platforms.winforms',
        'clr_loader',
        'pythonnet',
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

# İkon dosyası varsa kullan
icon_path = os.path.join(ROOT, 'desktop', 'icon.ico')
icon_param = icon_path if os.path.exists(icon_path) else None

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
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI modu — konsol penceresi açılmaz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_param,
    version_info=None,
)
