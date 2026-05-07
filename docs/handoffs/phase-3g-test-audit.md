# Phase 3g — Test Suite Audit

**Phase reference:** Sub-phase 3g in `docs/migration-roadmap.md`.
**Date:** 2026-05-03

---

## Summary

Per migration plan decision #5 (behavior-first tests survive
unchanged; tkinter-touching tests get rewritten under pytest-qt
or deleted in place), Phase 3g audits the test corpus and confirms
the surface is clean.

**Finding:** the heavy lifting already happened inline during Phases
3b / 3c / 3d / 3e.  Each Qt port shipped its own pytest-qt test
file; only **3 test files** still touch tkinter, and each is justifiable
through Phase 3h (when `gui/` retires).

The audit below documents each remaining tkinter touch and what
happens to it in Phase 3h.

---

## Test surface today (sandbox-verified count: 503)

### Pure behavior-first / non-UI tests (untouched, no migration needed)

These don't import any GUI module and exercise pure logic
(controller, engine, transcode, classifier, etc.).  They survive
unchanged through every phase.

* `test_imports.py` — module-boundary smoke (mostly).  See note
  below: one test in this file does patch `tkinter.Tk`.
* `test_label_color_and_libredrive.py` — text introspection of
  `gui/setup_wizard.py` source file.  No tkinter widgets actually
  constructed.
* (Many others — controller, engine, transcode, classifier,
  organizer tests, etc.)

### pytest-qt tests (Phase 3a–3f deliverables)

20 test files, **503 sandbox-verified tests** — all use
`pytest.importorskip("pytestqt")` so they skip cleanly on
environments without pytest-qt.

| File | Tests | Phase |
|------|------:|-------|
| `test_pyside6_scaffolding.py` | 7 | 3a |
| `test_pyside6_themes.py` | 18 (98 parametrized) | 3a-themes |
| `test_pyside6_formatters.py` | 42 | 3c-i |
| `test_pyside6_log_pane.py` | 21 | 3c-i |
| `test_pyside6_status_bar.py` | 16 | 3c-i |
| `test_pyside6_main_window.py` | 44 | 3c-i + later passes |
| `test_pyside6_main_window_controller_gaps.py` | 9 | 3c-iii |
| `test_pyside6_dialogs.py` | 29 | 3c-ii |
| `test_pyside6_dialogs_session_setup.py` | 30 | 3c-ii |
| `test_pyside6_dialogs_disc_tree.py` | 22 | 3c-iii |
| `test_pyside6_dialogs_list_picker.py` | 20 | 3c-iii |
| `test_pyside6_dialogs_temp_manager.py` | 33 | 3c-iii |
| `test_pyside6_thread_safety.py` | 9 | 3c-ii |
| `test_pyside6_workflow_launchers.py` | 16 | 3c-ii |
| `test_pyside6_utility_handlers.py` | 11 | 3c-ii |
| `test_pyside6_drive_handler.py` | 17 | 3c-iii |
| `test_pyside6_prep_workflow.py` | 13 | 3c-iii |
| `test_pyside6_settings_themes.py` | 20 | 3d |
| `test_pyside6_preview_widget.py` | 34 | 3e |
| `test_pyinstaller_spec.py` | 12 | 3f |

(Wizard tests `test_pyside6_setup_wizard_*.py` exist but require
Python 3.11+ for `transcode/recommendations.NotRequired`; they run
on the user's Windows venv only.  Sandbox is Python 3.10.)

---

## tkinter-touching tests (3 files — fates documented)

### 1. `tests/test_imports.py:test_gui_import`

```python
def test_gui_import():
    """GUI import must not require a live display."""
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window  # noqa: F401
```

**Verdict:** **Keep through Phase 3h.**  This test legitimately
asserts that the tkinter side of the codebase imports cleanly
without a display.  The tkinter path is still load-bearing
(`opt_use_pyside6=False` is the default).

**Phase 3h fate:** delete alongside `gui/main_window.py`.

The other 32 tests in this file are pure import smoke (no tkinter
mocking) and survive unchanged.

### 2. `tests/test_label_color_and_libredrive.py`

124 lines, 7 tests.  Despite the name, this file does **not**
construct tkinter widgets.  It introspects the source text of
`gui/setup_wizard.py` to verify two specific UX fixes
(EXTRA-label-color and LibreDrive inline-gloss) landed.

**Verdict:** **Keep through Phase 3h.**  Pure source-text checks;
behavior-first.  The fixes it pins are tkinter-side because they
were applied to `gui/setup_wizard.py`.

**Phase 3h fate:** delete alongside `gui/setup_wizard.py`.  The
PySide6 wizard ports preserve the same UX fixes; equivalent pins
are baked into the Qt-side wizard tests already.

### 3. `tests/test_main_window_formatters.py`

412 lines, 25 tests.  Tests 5 pure helper methods on
`JellyRipperGUI`: `_format_drive_label`, `_trim_context_label`,
`_main_status_style_for_message`, `_get_text_widget_selection`,
`_ffmpeg_version_ok`.

The file uses `unittest.mock.patch("tkinter.Tk", new=_FakeTkBase)`
to import the class without a display, then `object.__new__()` to
construct without running `__init__`.  Pure helper logic — no widget
construction.

**Verdict:** **Keep through Phase 3h.**  These pin the tkinter
implementation of helpers that haven't been collapsed into shared
utilities yet.  The Qt path has a parallel `test_pyside6_formatters.py`
covering the equivalent helpers (3 of 5 are ported as
module-level functions in `gui_qt/formatters.py`; 2 are widget-
coupled and don't have Qt equivalents).

**Phase 3h fate:** delete alongside `gui/main_window.py`.

---

## Phase 3h's clean-up checklist

When Phase 3h runs, these test deletions accompany the `gui/`
package retirement:

* [ ] Delete `tests/test_imports.py:test_gui_import` (the one test
      that needs `_FakeTkBase`); keep the other 32 tests.
* [ ] Delete `tests/test_label_color_and_libredrive.py` entirely
      (UX fixes are pinned in the Qt wizard test files).
* [ ] Delete `tests/test_main_window_formatters.py` entirely (Qt
      equivalents are in `tests/test_pyside6_formatters.py`).
* [ ] Drop the `_FakeTkBase` helper class from
      `tests/test_imports.py`.
* [ ] Remove the tkinter / Tcl / Tk bundling from `JellyRip.spec`.
* [ ] Remove the `tkinter*` hidden imports from `JellyRip.spec`.
* [ ] Update `requirements.txt` to drop the "tkinter is included
      with Python on Windows" comment block.

---

## What NOT to do in Phase 3g

* **Don't delete `gui/main_window.py`** — that's Phase 3h.  The
  default cfg keeps users on the tkinter path until v1.0 ships.
* **Don't delete the 3 tkinter-coupled test files** — they pin
  the tkinter side which is still shipping.
* **Don't rewrite tests as pytest-qt unless they're testing UI
  widgets** — the 3 files audited above are not testing widgets;
  they're testing pure helpers / source content.

---

## Definition of done — 3g

- [x] Audit complete (this document)
- [x] `requirements-dev.txt` exists with pytest-qt + PySide6 +
      pyinstaller pins
- [x] Test surface verified uniformly behavior-first or pytest-qt
- [x] No surprise tkinter-coupled tests ported in error
- [x] Phase 3h test-deletion checklist documented above

3g is **complete**.  Phase 3h (release prep) starts next.
