# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_DyberPet.py'],
    pathex=[],
    binaries=[],
    datas=[('res', 'res'), ('DyberPet', 'DyberPet')],
    hiddenimports=['pynput.mouse._win32', 'pynput.keyboard._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pkg_resources'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DyberPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icons\\arrow-204-32.ico'],
)
