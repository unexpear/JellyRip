# Handoff Brief — Phase 3h: Tkinter Retirement (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3h in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3g (test audit) — done 2026-05-03.
**Successor:** Phase 4 (AI BRANCH port).
**User direction:** *"get rid of tkinter we are moving to pyside6"*
(2026-05-04). Aligned with original migration plan; just
accelerated to one focused execution.

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md` (Phase 3h section)
- `STATUS.md` (current PySide6 coverage)
- This brief is the deletion plan. **Do not deviate from the
  ordering** — out-of-order edits will break the suite mid-run
  and you'll be debugging instead of porting.

## State entering this phase

- **Feature flag locked 2026-05-04**: `main.py` no longer reads
  `opt_use_pyside6`. PySide6 is the only path. tkinter files
  remain on disk as fallback safety.
- **gui_qt/ coverage verified**: every `self.gui.X()` method the
  controller calls has a corresponding implementation in
  `gui_qt/`. No missing methods.
- **gui_qt/setup_wizard.py re-exports** the shared dataclasses
  (`ContentSelection`, `ExtrasAssignment`, `OutputPlan`,
  `JELLYFIN_EXTRAS_CATEGORIES`, `build_output_tree`,
  `_format_duration`, `_format_size`, `_label_display`) **from
  `gui/setup_wizard.py`**. Step 1 of this brief moves them out.

## Branch identity guardrails

Repeated from the roadmap — non-negotiable:

1. No AI features in MAIN, ever
2. Branch-aware constants stay branch-aware
3. No commits/pushes/release.bat without explicit user go-ahead
4. AI BRANCH untouched (Phase 4)

---

## Step 1 — Move shared dataclasses to a neutral home

**Why first:** every other deletion depends on this. If you delete
`gui/setup_wizard.py` before moving its dataclasses, every test
file that imports `ContentSelection` (and similar) blows up.

### 1a. Create `shared/wizard_types.py`

Lift these from `gui/setup_wizard.py`:

- `ContentSelection` (dataclass, lines 97-102)
- `ExtrasAssignment` (dataclass, lines 105-108)
- `OutputPlan` (dataclass, lines 111-117)
- `JELLYFIN_EXTRAS_CATEGORIES` (constant, line 83-91)
- `build_output_tree` (function, line 682-713)
- `_format_duration` (function, line 141-148)
- `_format_size` (function, line 151-157)
- `_label_display` (function, line 72-79)
- `_LABEL_DISPLAY` (constant, line 64-69)

Drop the `tkinter` / `tk.*` imports — these are pure Python.

### 1b. Create `shared/session_setup_types.py`

Lift these from `gui/session_setup_dialog.py`:

- `MovieSessionSetup` (dataclass, line 18)
- `TVSessionSetup` (dataclass, line 30)
- `DumpSessionSetup` (dataclass, line 45)

Drop the `tkinter` / `tk.*` imports.

### 1c. Update imports — production code

```python
# Before
from gui.setup_wizard import ContentSelection, JELLYFIN_EXTRAS_CATEGORIES
from gui.session_setup_dialog import MovieSessionSetup
# After
from shared.wizard_types import ContentSelection, JELLYFIN_EXTRAS_CATEGORIES
from shared.session_setup_types import MovieSessionSetup
```

Files to update:

- `gui_qt/setup_wizard.py` — currently re-exports from `gui.setup_wizard`; switch to `shared.wizard_types`
- `gui_qt/main_window.py` — if it imports any of the dataclasses
- `gui_qt/dialogs/*.py` — same
- `gui_qt/settings/*.py` — same
- `gui_qt/workflow_launchers.py` — uses `MovieSessionSetup` etc.
- `controller/*.py` — check; should be minimal but verify

### 1d. Update imports — tests

Every test file that imports from `gui.setup_wizard` or
`gui.session_setup_dialog`:

- `tests/test_abort_propagation.py`
- `tests/test_behavior_guards.py` (multiple lines)
- `tests/test_disk_space_pre_checks.py`
- `tests/test_pipeline_state_trajectory.py`
- `tests/test_workflow_sm_audit.py`

Plus the dedicated wizard tests under `tests/test_pyside6_setup_wizard_*.py`.

### 1e. Verify

Run the full suite — should pass with the same count as before
(no behavior change, just import paths). If anything breaks,
fix the missed import before continuing.

---

## Step 2 — Delete tkinter UI files

**Order matters:** delete tests first (so you don't get pytest
errors on imports during the file-deletion step).

### 2a. Delete tkinter-only test files

These tests pin tkinter implementation details that no longer
exist after deletion:

- `tests/test_main_window_formatters.py` — pure tkinter formatters; `gui_qt/formatters.py` has its own equivalents (covered by `tests/test_pyside6_formatters.py` per Phase 3c-i)
- `tests/test_button_contrast.py` — pins `gui/setup_wizard.py:_ACCENT_BUTTON_BG`. WCAG contrast is now pinned per-theme in `tests/test_pyside6_themes.py` (98 tests).
- `tests/test_label_color_and_libredrive.py` — pins tkinter widget colors. Same: covered by `tests/test_pyside6_themes.py` + the per-step pytest-qt tests' theming-hook drift guards.

### 2b. Trim tests that have both tkinter and Qt parts

- `tests/test_imports.py` — keeps the `_FakeTkBase` patch only for `test_gui_import` and a few related tests. After 2c, those tests are obsolete. Either delete them or delete the whole file (per the audit in `docs/handoffs/phase-3g-test-audit.md`, this file is mostly behavior-first imports that don't need tkinter).
- `tests/test_security_hardening.py` — has `test_main_gui_uses_secure_tk_root` which pins `JellyRipperGUI` subclasses `SecureTk`. After we delete `gui/main_window.py`, this test pins dead code; delete it. The other tests in this file are still relevant.

### 2c. Delete `gui/` files

```
gui/__init__.py
gui/main_window.py        # ~7,825 lines
gui/secure_tk.py
gui/session_setup_dialog.py
gui/setup_wizard.py
gui/theme.py              # tkinter color constants
gui/update_ui.py          # tkinter update dialog
```

If any of these grew an `ai_*` file on AI BRANCH, leave that
branch alone (Phase 4 handles it).

### 2d. Verify

Run the full suite — should pass at a reduced test count (the
deleted tests + maybe a couple more). Fix any import errors.

---

## Step 3 — Clean up entrypoints

### 3a. Update `main.py`

- Delete `JellyRipperGUI = None` global (no longer used)
- Delete `_resolve_gui_class()` function (no longer called)
- Both became dead code when the feature flag was locked
  2026-05-04

### 3b. Update `JellyRip.py`

This is the compatibility entrypoint. It probably imports tkinter
classes for backward-compat. Update it to:

- Import from `gui_qt` instead
- OR delete the file if it's no longer needed (check what calls
  it from outside the codebase; the README mentions it)

### 3c. Decide on `tools/ui_sandbox_launcher.py`

Currently a tkinter UI sandbox. Options:

- **Delete** — sandbox is rarely used; pytest-qt covers most
  needs
- **Port to Qt** — `tools/ui_qt_sandbox_launcher.py` that calls
  `gui_qt.app.run_qt_app` with a fake config

Default: delete. If user pushes back, port.

---

## Step 4 — Documentation pass

Update these to reflect the tkinter-retirement:

- `README.md` — drop "tkinter UI layer" mention; add PySide6
- `CHANGELOG.md` — add an entry for v1.0.0 (or whatever the
  PySide6-ship version becomes): "GUI rewritten in PySide6;
  tkinter retired"
- `docs/architecture.md` — update the GUI layer description
- `docs/repository-layout.md` — update the gui_qt vs gui split
- `docs/release-process.md` — drop the "Tkinter path" section
  (still pinned in the smoke checklist; remove)
- `docs/migration-roadmap.md` — mark Phase 3h complete; update
  status snapshot
- `docs/pyside6-migration-plan.md` — add a "Phase 3h closed"
  note (don't delete; historical record)
- `STATUS.md` — replace the "tkinter files remain on disk as
  fallback" note with a "tkinter retired" note

---

## Step 5 — Final verification

- [ ] Full suite green: ~1559 - <deleted_test_count> tests passing
- [ ] `python main.py` launches PySide6 UI (smoke this manually)
- [ ] `build.bat` produces a working `.exe` on PySide6 path
- [ ] No `from gui.` imports remain anywhere except the
      deprecated `JellyRip.py` if you kept it as a thin shim
- [ ] STATUS.md updated: 6 / 6 cross-cutting + Phase 3a-3h all
      ✅ closed; only Phase 4 (AI BRANCH port) remains

## Step 6 — Hand off

Tell the user: tkinter is retired. v1.0 candidate is ready for
real-disc validation (Phase 2 of the roadmap). After that closes,
Phase 4 (AI BRANCH port) starts.

---

## Estimated effort

- Step 1 (move + update imports): ~45 min — mechanical but
  involves ~25 files
- Step 2 (delete files + tests): ~20 min
- Step 3 (entrypoint cleanup): ~15 min
- Step 4 (docs pass): ~30 min
- Step 5-6 (verify + handoff): ~15 min

**Total: ~2-2.5 hours of focused Claude session.**

---

## Risks + mitigations

- **Hidden import** — some test or helper imports a tkinter
  class indirectly. Run the suite after EACH step to catch
  these early. Don't batch-delete and run once at the end.
- **`tools/ui_sandbox_launcher.py`** — if anyone has a
  workflow built around this script, deletion is annoying.
  Quick PSA in the deletion log.
- **AI BRANCH parity drift** — AI BRANCH still has the old
  tkinter `gui/` and `JellyRipperGUI` shape. Phase 4 will
  redo this same retirement on AI BRANCH after MAIN ships.
  Don't try to keep them in sync during MAIN's retirement;
  they'll re-converge at Phase 4 ship.
- **External tools that link `gui/main_window.py` line
  numbers** — the audit doc references many. Update those in
  Step 4's doc pass, or accept that the line-number references
  become historical.

## Self-check before starting

- [ ] You've read this brief end-to-end
- [ ] You've read STATUS.md to confirm gui_qt/ coverage is still
      complete (no regressions since 2026-05-04)
- [ ] You've confirmed the user wants this NOW (not "plan only")
- [ ] You understand the ordering: dataclasses move first, files
      delete last. Out-of-order = broken suite.

If any of these is no, stop and clarify.
