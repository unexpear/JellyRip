# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


project_root = Path(SPEC).resolve().parent
python_base = Path(getattr(__import__("sys"), "base_prefix"))
python_dlls = python_base / "DLLs"
python_tcl_root = python_base / "tcl"

tcl_build_dir = python_tcl_root / "tcl8.6"
tk_build_dir = python_tcl_root / "tk8.6"
if (tcl_build_dir / "init.tcl").is_file() and tk_build_dir.is_dir():
    os.environ.setdefault("TCL_LIBRARY", str(tcl_build_dir))
    os.environ.setdefault("TK_LIBRARY", str(tk_build_dir))

def collect_tree(root_dir, dest_root):
    entries = []
    root_dir = Path(root_dir)
    if not root_dir.is_dir():
        return entries

    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        relative_parent = path.parent.relative_to(root_dir)
        destination = str(Path(dest_root) / relative_parent).replace("\\", "/")
        entries.append((str(path), destination))
    return entries


datas = []
datas += collect_tree(tcl_build_dir, "_tcl_data")
datas += collect_tree(tk_build_dir, "_tk_data")

# Explicitly bundle _tkinter.pyd and the Tcl/Tk DLLs from the base Python
# installation.  A venv does not copy these into its own DLLs folder so
# PyInstaller analysis may miss them when invoked from a venv.
tk_binaries = []
for dll_name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll"):
    dll_path = python_dlls / dll_name
    if dll_path.is_file():
        tk_binaries.append((str(dll_path), "."))


a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=tk_binaries,
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.simpledialog',
        '_tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / 'pyinstaller_tk_runtime_hook.py')],
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
