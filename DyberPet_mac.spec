# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_DyberPet.py'],
    pathex=[],
    binaries=[],
    datas=[('res', 'res'), ('DyberPet', 'DyberPet')],
    hiddenimports=['pynput.mouse._darwin', 'pynput.keyboard._darwin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DyberPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DyberPet',
)
app = BUNDLE(
    coll,
    name='DyberPet.app',
    icon=None,
    bundle_identifier=None,
)
