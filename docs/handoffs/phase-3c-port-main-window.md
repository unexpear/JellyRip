# Handoff Brief — Phase 3c: Port Main Window + Dialogs (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3c in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3b (setup wizard).
**Successor:** Phase 3d (settings).
**Estimated:** 2-3 sessions — `gui/main_window.py` is 7,825 lines.

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md`
- `docs/handoffs/phase-3a-pyside6-scaffolding.md`
- `docs/handoffs/phase-3b-port-setup-wizard.md`
- `STATUS.md`

## Goal

Port `gui/main_window.py` (~7,825 lines) to `gui_qt/main_window.py`
**and split it into per-screen modules** so the Qt version doesn't
become its own monolith. Target structure:

```
gui_qt/
  main_window.py          # ~500 lines — top-level window shell
  workflow_launchers.py   # buttons that trigger run_smart_rip etc.
  log_pane.py             # log display widget
  status_bar.py           # status + progress bar
  dialogs/
    duplicate_resolution.py
    space_override.py
    error_with_recovery.py    # uses friendly_error helper
    update_blocked.py
  formatters.py           # the pure helpers (already tested)
```

The 47 formatter tests in `tests/test_main_window_formatters.py`
pin the pure helpers — those translate to `formatters.py` with
**zero behavior change**.

## Branch identity guardrails

Same as 3a/3b. Repeated for emphasis: **no AI features in MAIN**.

## Concrete plan

This phase is too big for one session. Split into 3 sub-sessions:

### 3c-i — Main window shell + log pane + status bar

- `main_window.py` (the new ~500-line shell)
- `log_pane.py` (replaces tkinter `Text` widget with `QPlainTextEdit`)
- `status_bar.py` (replaces tkinter status frame with `QStatusBar` +
  `QProgressBar`)
- `formatters.py` (port the 5 already-tested helpers)
- Tests: pytest-qt instantiation, formatter parity (the existing
  47 tests should all still pass, just point them at new module)

### 3c-ii — Workflow launchers + main dialogs

- `workflow_launchers.py` — the buttons + their action handlers
- `dialogs/duplicate_resolution.py`, `dialogs/space_override.py`
- `dialogs/error_with_recovery.py` — wires `friendly_error` helper
  from `ui/dialogs.py`. The existing 18 tests in
  `tests/test_friendly_error.py` cover the helper itself; you only
  need new tests for the Qt dialog wrapper.
- Tests: workflow-launch button wiring; dialog construction.

### 3c-iii — Update-blocked dialog + remaining bits

- `dialogs/update_blocked.py`
- Anything left over from the 7,825-line monolith
- Final sweep: confirm `gui_qt/main_window.py` imports nothing from
  `gui/` (other than possibly the controller, which is in
  `controller/` not `gui/`)

## Definition of done (3c overall)

- [ ] All workflow launches reach the controller via Qt path when
      `opt_use_pyside6=True`
- [ ] Formatter tests still pass (47 existing) plus new pytest-qt
      tests (~30-40 new)
- [ ] No imports from `gui/` in `gui_qt/`
- [ ] Manual smoke test: launch with flag on, every button works,
      log pane renders, status updates
- [ ] STATUS.md tracks all 3 sub-sessions

## Critical: do not delete `gui/main_window.py` yet

The tkinter path stays runnable until Phase 3 ships. `gui/main_window.py`
keeps existing through 3c-3g; deletion happens at the start of Phase
3h (release prep).
