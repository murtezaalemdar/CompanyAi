# -*- mode: python ; coding: utf-8 -*-
"""
CompanyAI Desktop — macOS PyInstaller Spec Dosyası
Kullanım: pyinstaller desktop/companyai_mac.spec
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
        'webview.platforms.cocoa',   # macOS WebKit backend
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# İkon dosyası (varsa .icns formatında)
icon_path = os.path.join(ROOT, 'desktop', 'icon.icns')
icon_param = icon_path if os.path.exists(icon_path) else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CompanyAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    icon=icon_param,
)

# macOS .app bundle
app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='CompanyAI.app',
    icon=icon_param,
    bundle_identifier='com.companyai.desktop',
    info_plist={
        'CFBundleDisplayName': 'CompanyAI',
        'CFBundleShortVersionString': '2.6.0',
        'CFBundleVersion': '2.6.0',
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': False,
            'NSExceptionDomains': {
                '192.168.0.12': {
                    'NSExceptionAllowsInsecureHTTPLoads': True,
                    'NSIncludesSubdomains': True,
                }
            }
        },
    },
)
