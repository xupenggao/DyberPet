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

# Remove unnecessary large files to reduce exe size and avoid decompression errors
a.binaries = [x for x in a.binaries if not any(
    name in x[0] for name in [
        'Qt6WebEngine',
        'opengl32sw',
        'Qt6Pdf',
    ]
)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='爪爪宠物',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
