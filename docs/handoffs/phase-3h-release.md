# Handoff Brief — Phase 3h: Release Prep & Migration Closeout (MAIN)

> ⚠️ **HISTORICAL — superseded 2026-05-04.** This brief was the
> original v1.0.0-targeting plan for the release-prep slice of 3h.
> The actual Phase 3h execution was the broader tkinter-retirement
> in [`phase-3h-tkinter-retirement.md`](phase-3h-tkinter-retirement.md),
> and the version bump landed on **v1.0.19** rather than v1.0.0.
> The references to `1.0.0` below are kept as the original-plan
> record; the live version is in `shared/runtime.py:__version__`.

**For:** the user driving the v1 release.
**Phase reference:** Final sub-phase of Phase 3 in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3g (test audit complete 2026-05-03).
**Successor:** Phase 4 (AI BRANCH port — gated on this shipping).

---

## ⚠️ READ FIRST — Acceptance gate

**Phase 3f's manual smoke must pass before any 3h delete or
release work.**  Run:

```bat
build.bat
```

then walk the smoke checklist in
[`docs/release-process.md`](../release-process.md) on a clean
Windows machine or VM.  This is the v1 acceptance gate.  Without
it, the bundle could be missing Qt plugins, themes might not
render, MKV preview could fail, and the deletes below would
break the only working path.

If anything in the smoke fails, **fix before deleting tkinter**.
Most likely fixes are spec adjustments — extend
`GUI_QT_HIDDEN_IMPORTS` / `PYSIDE6_HIDDEN_IMPORTS` /
`GUI_QT_DATAS` in `JellyRip.spec` and rebuild.

---

## Branch identity guardrails

Same as every prior phase.  **No AI features in MAIN, ever.**
This phase deletes the tkinter implementation in MAIN; AI BRANCH
gets its parallel port in Phase 4.

---

## Goal

Retire the tkinter implementation in MAIN.  The Qt path becomes
the only path.  Ship v1.0.0.

---

## Pre-staged patch pack

Ready-to-apply diffs live under
[`3h-patches/`](3h-patches/README.md).  They cover the exact
changes for `shared/runtime.py`, `main.py`, `JellyRip.spec`, and
`tests/test_phase_3g_audit.py`, plus the full delete list.  The
checklist below is the conceptual order; the patch files have the
mechanical detail.

`requirements.txt` was already updated 2026-05-04 — no action
needed for that file during deletes.

---

## Deletion checklist (in order)

### 1. Drop the feature flag

Phase 3a wired `opt_use_pyside6` (default `False`) so users could
opt in.  After 3h, Qt is the only option.

* **`shared/runtime.py`** — remove the `"opt_use_pyside6"` and
  the documenting comment block above it.  Keep
  `"opt_pyside6_theme"` (Settings consumes it).
* **`main.py`** — remove the `if cfg.get("opt_use_pyside6", False):`
  branch.  The Qt path becomes the unconditional code path.

### 2. Delete the tkinter UI package

Phase 3 ports replaced everything.  Time to delete:

```
gui/__init__.py
gui/main_window.py            ← 7,825 lines
gui/setup_wizard.py           ← 825 lines
gui/session_setup_dialog.py
gui/secure_tk.py
gui/theme.py                  ← only used by tkinter; gui_qt has its own
gui/update_ui.py              ← Qt path now imports it directly; either keep at top-level or move to a tkinter-free location
```

**Note on `gui/update_ui.py`:** the Qt utility handler imports
this module directly (lazy).  It's not tkinter-coupled internally
but lives in the `gui/` package.  Either:

a) Move it to a tkinter-free home (e.g., `tools/update_check.py`)
   and update the import in `gui_qt/utility_handlers.py`.
b) Keep it where it is and exclude `gui/update_ui.py` from the
   delete (delete only the tkinter modules).

Option (a) is cleaner; option (b) is faster.  Pick one.

### 3. Delete tkinter-coupled tests

Per the [test audit](phase-3g-test-audit.md):

* **`tests/test_label_color_and_libredrive.py`** — delete entirely.
  UX fixes mirrored in the Qt wizard tests.
* **`tests/test_main_window_formatters.py`** — delete entirely.
  Qt equivalents in `tests/test_pyside6_formatters.py`.
* **`tests/test_imports.py`** — keep, but:
  - Delete the `_FakeTkBase` class.
  - Delete the `test_gui_import` function (it tests tkinter import).
  - The other 32 tests survive unchanged (pure import smoke).

### 4. Update `JellyRip.spec`

Phase 3f extended the spec with Qt assets while keeping tkinter
load-bearing.  Now drop tkinter:

* Remove `_configure_tcl_tk_environment()` call + helper.
* Remove `TK_DATAS` / `TK_BINARIES` collection.
* Drop `"tkinter"`, `"tkinter.ttk"`, `"tkinter.messagebox"`,
  `"tkinter.filedialog"`, `"tkinter.simpledialog"`, `"_tkinter"`
  from `hiddenimports`.
* Remove `pyinstaller_tk_runtime_hook.py` from `runtime_hooks`
  (and delete the hook file if it exists).
* **Verify** the existing `tests/test_pyinstaller_spec.py` still
  passes — but expect the test for "tkinter still in hidden
  imports" to fail intentionally; **delete that test** as part of
  this cleanup.

After spec cleanup, re-run `build.bat`.  Bundle size should
shrink by ~5-10 MB (Tcl/Tk DLLs).

### 5. Update test_phase_3g_audit.py

Remove the 3 tkinter-coupled files from
`_LEGITIMATE_TKINTER_TOUCHING_TESTS`:

```python
_LEGITIMATE_TKINTER_TOUCHING_TESTS: frozenset[str] = frozenset()
```

The audit becomes a regression guard against tkinter
re-introduction.

### 6. Update requirements.txt

The current file says "tkinter is included with Python on
Windows" in a comment block.  Drop that comment.  Add a
PySide6 runtime dependency note:

```
# Runtime
PySide6>=6.5
```

(The `requirements-dev.txt` already pins this.  But `requirements.txt`
is what end users / CI installs from for runtime.)

### 7. README + CHANGELOG

Both updated this session — see `README.md` and `CHANGELOG.md`.
Re-read after the deletes land to ensure the "Quick Start"
section still matches reality.

### 8. Version bump

Edit `shared/runtime.py:__version__` to `"1.0.0"` (or whatever
the user's release counter says).  The PyInstaller spec reads
this string at build time.

### 9. Final smoke + release

```bat
build.bat
```

Walk the smoke checklist one more time on a clean machine.

```bat
release.bat 1.0.0
```

The release script:
1. Verifies git state
2. Runs the full test suite
3. Builds the bundle
4. Builds the installer
5. Tags the release
6. Pushes to origin/main
7. Publishes to GitHub releases

**Do not run `release.bat` without explicit user go-ahead per
the migration plan's release etiquette.**

---

## Definition of done

- [ ] Phase 3f manual smoke passed on a clean Windows machine
- [ ] All deletions above complete
- [ ] All test files updated; suite still green
- [ ] `JellyRip.spec` no longer references tkinter
- [ ] `JellyRip.exe` builds cleanly via `build.bat`
- [ ] Smoke re-runs cleanly on the post-delete bundle
- [ ] Version bumped
- [ ] `release.bat 1.0.0` runs (on user's go-ahead)
- [ ] GitHub release page shows v1.0.0
- [ ] STATUS.md marks Phase 3 **complete**
- [ ] memory/MEMORY.md updated to reflect tkinter retirement

---

## After 3h ships

**Phase 4** (AI BRANCH port) is gated on Phase 3 shipping.  Once
v1.0.0 is published from MAIN, the AI BRANCH session can:

1. Pull the Qt port from MAIN
2. Re-add the AI features (chat sidebar, assist controller,
   workflow history) on top of the Qt UI
3. Verify branch-aware constants stay branch-aware
   (`APP_DISPLAY_NAME = "JellyRipAI"`, etc.)
4. Ship AI BRANCH v1.0.0 against the MAIN v1.0.0 baseline

That's the final phase of the multi-month migration.  After it
lands, both branches are on PySide6.

---

## Polish items still hanging (not v1-blocking)

Documented in their own briefs — none of these block 3h:

* Phase 3c full Prep transcode-queue UI port —
  [`phase-3c-iii-prep-workflow.md`](phase-3c-iii-prep-workflow.md)
* Phase 3d remaining Settings tabs (everyday/advanced/expert) —
  [`phase-3d-port-settings-tabs.md`](phase-3d-port-settings-tabs.md)
* Wizard Step 5 inline Preview button —
  `gui_qt/setup_wizard.py:_OutputPlanDialog` row-level wire-up
  using the existing `gui_qt.preview_widget.PreviewDialog`.

These can ship as v1.0.X point releases after v1.0.0.
