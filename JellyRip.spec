# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (r'c:/Users/micha/Desktop/ffmpeg/ffmpeg-2026-04-01-git-eedf8f0165-full_build/ffmpeg-2026-04-01-git-eedf8f0165-full_build/bin/ffmpeg.exe', '.'),
        (r'c:/Users/micha/Desktop/ffmpeg/ffmpeg-2026-04-01-git-eedf8f0165-full_build/ffmpeg-2026-04-01-git-eedf8f0165-full_build/bin/ffprobe.exe', '.'),
        (r'c:/Users/micha/Desktop/ffmpeg/ffmpeg-2026-04-01-git-eedf8f0165-full_build/ffmpeg-2026-04-01-git-eedf8f0165-full_build/bin/ffplay.exe', '.'),
    ],
    datas=[],
    hiddenimports=[],
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
    name='JellyRip',
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
)
