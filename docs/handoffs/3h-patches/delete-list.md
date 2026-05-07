# Files / Directories to Delete in Phase 3h

After the Phase 3f manual smoke clears, delete these paths.  Each
is justified in [`docs/handoffs/phase-3h-release.md`](../phase-3h-release.md)
and the [test audit](../phase-3g-test-audit.md).

## tkinter UI package

```
gui/__init__.py
gui/main_window.py            (~7,825 lines)
gui/setup_wizard.py           (~825 lines)
gui/session_setup_dialog.py
gui/secure_tk.py
gui/theme.py
```

### `gui/update_ui.py` — pick one of two options

**Option A (cleaner, recommended):**

1. Move the file to `tools/update_check.py`.
2. In `gui_qt/utility_handlers.py`, change the lazy import to
   reference the new location.
3. Delete `gui/update_ui.py`.

**Option B (faster):**

Keep `gui/update_ui.py` where it is and exclude it from the
delete.  The `gui/` package becomes a one-file package containing
only `update_ui.py` (and its `__init__.py`, which can stay empty).

## tkinter-coupled tests

```
tests/test_label_color_and_libredrive.py     — delete entirely
tests/test_main_window_formatters.py         — delete entirely
```

## Test surgery (don't delete the file, edit it)

### `tests/test_imports.py`

Delete:
- The `_FakeTkBase` class.
- The `test_gui_import` function.

Keep the other 32 tests unchanged (pure import smoke, no tkinter).

### `tests/test_pyinstaller_spec.py`

Delete or rewrite any assertion that pins `tkinter` / `_tkinter`
in `hiddenimports` — after the spec patch, those imports are
gone.  Regression-guard: assert their **absence**.

## Runtime hook

```
pyinstaller_tk_runtime_hook.py    — delete entirely
```

## Stragglers worth grepping for

```bash
grep -rn "from gui\." --include="*.py"
grep -rn "import gui\b" --include="*.py"
grep -rn "tkinter" --include="*.py"
grep -rn "opt_use_pyside6"
grep -rn "_FakeTkBase"
```

Each hit either gets the import switched to its `gui_qt` /
`tools/` equivalent, or the line gets deleted.  CHANGELOG and
migration docs are allowed to retain the strings as historical
record.

## Sanity check after deletes

```bat
python -m pytest -q
build.bat
```

Then walk the smoke checklist on the post-delete bundle.
