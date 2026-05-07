# Patch — `JellyRip.spec`

Strip tkinter / Tcl-Tk bundling, hidden imports, and the runtime
hook.  Keep all PySide6 / `gui_qt` collection in place — that's
what's actually shipping.

## Drops

### 1. The `_configure_tcl_tk_environment` helper + call (around lines 27-42)

```python
def _configure_tcl_tk_environment() -> None:
    base_prefix = Path(getattr(sys, "base_prefix", "") or "")
    if not base_prefix:
        return

    tcl_root = base_prefix / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"

    if not os.environ.get("TCL_LIBRARY") and tcl_library.is_dir():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
    if not os.environ.get("TK_LIBRARY") and tk_library.is_dir():
        os.environ["TK_LIBRARY"] = str(tk_library)


_configure_tcl_tk_environment()
```

→ delete the function and the call.

### 2. The TK collection block (around lines 247-260)

```python
PYTHON_BASE = Path(getattr(sys, "base_prefix", "") or "")
PYTHON_DLLS = PYTHON_BASE / "DLLs"
PYTHON_TCL_ROOT = PYTHON_BASE / "tcl"
TCL_BUILD_DIR = PYTHON_TCL_ROOT / "tcl8.6"
TK_BUILD_DIR = PYTHON_TCL_ROOT / "tk8.6"
TK_DATAS = _collect_tree(TCL_BUILD_DIR, "_tcl_data")
TK_DATAS += _collect_tree(TK_BUILD_DIR, "_tk_data")
TK_BINARIES = []
for dll_name in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll"):
    dll_path = PYTHON_DLLS / dll_name
    if dll_path.is_file():
        TK_BINARIES.append((str(dll_path), "."))
FFMPEG_BINARIES = [(_find_bundle_file(name), ".") for name in FFMPEG_FILENAMES]
FFMPEG_BINARIES = [*TK_BINARIES, *FFMPEG_BINARIES]
```

→ replace with:

```python
FFMPEG_BINARIES = [(_find_bundle_file(name), ".") for name in FFMPEG_FILENAMES]
```

### 3. Inside `Analysis(...)` `datas=[ ... ]`

Drop the leading `*TK_DATAS,` line.

### 4. Inside `Analysis(...)` `hiddenimports=[ ... ]`

Drop these six entries and the `# tkinter path stays load-bearing
through Phase 3h.` comment above them:

```python
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.simpledialog",
        "_tkinter",
```

### 5. Inside `Analysis(...)` `runtime_hooks=[ ... ]`

Replace:

```python
runtime_hooks=[str(PROJECT_ROOT / "pyinstaller_tk_runtime_hook.py")],
```

→ with:

```python
runtime_hooks=[],
```

### 6. Delete the runtime hook file

`pyinstaller_tk_runtime_hook.py` (project root) — delete the file
itself.

## Update tests

`tests/test_pyinstaller_spec.py` has assertions that pin the
tkinter hidden imports.  After the spec change, those assertions
will flip — they should be deleted or rewritten to assert the
**absence** of tkinter hidden imports (regression guard).

## Verification

```bat
build.bat
```

Bundle size should shrink ~5-10 MB (Tcl/Tk DLLs + libraries).
Walk the smoke checklist again.
