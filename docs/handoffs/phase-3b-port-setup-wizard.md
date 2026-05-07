# Handoff Brief — Phase 3b: Port Setup Wizard (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3b in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3a (`docs/handoffs/phase-3a-pyside6-scaffolding.md`).
**Successor:** Phase 3c (port main window).

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md` — phase context and branch guardrails
- `docs/handoffs/phase-3a-pyside6-scaffolding.md` — what's already in `gui_qt/`
- `STATUS.md` — current Phase 3 state
- The user's Claude Design mockups (if available) — visual reference

If `STATUS.md` says 3a-themes hasn't run yet, that's fine. 3b's
structural port doesn't depend on theme content; just leave styling
hooks (`setObjectName`, semantic class names) that themes can target.

## Goal

Port `gui/setup_wizard.py` (825 lines) to `gui_qt/setup_wizard.py`.
The wizard's job is the disc-setup flow:

1. Scan results step (display detected titles)
2. Content mapping step (select main, extras, skip)
3. Extras classification step
4. Output plan review step

The Qt port keeps the **same controller-facing API** (`show_scan_results_step`, `show_content_mapping_step`, etc.) so `controller/controller.py` doesn't change. Internally, replace tkinter widgets with Qt equivalents.

## Branch identity guardrails

Repeated from the roadmap — non-negotiable:

1. No AI features in MAIN, ever.
2. Both branches use the same QSS theme system.
3. Branch-aware constants stay branch-aware (`APP_DISPLAY_NAME`).
4. No commits/pushes/release.bat without explicit user go-ahead.
5. No "while we're here" cross-branch homogenization.

## Concrete plan

1. **Read** `gui/setup_wizard.py` start to finish. Map every screen's
   widgets and bindings.
2. **Create** `gui_qt/setup_wizard.py` with `QDialog`-based wizard
   class. Use `QStackedWidget` for the step navigation.
3. **Translate** each step:
   - `Listbox` → `QListWidget` or `QTableWidget`
   - `Treeview` → `QTreeWidget`
   - `Checkbutton` → `QCheckBox`
   - `Button` → `QPushButton`
   - `Label` → `QLabel`
   - `Entry` → `QLineEdit`
4. **Preserve** the controller-facing API. Test by reading every
   `controller.gui.show_*_step` call site to confirm signatures match.
5. **Apply themeing hooks** — every styled widget gets a meaningful
   `setObjectName` so QSS can target it (`mainTitleRow`,
   `extraCheckbox`, etc.). Don't bake colors into Python.
6. **Write tests** under `tests/test_pyside6_setup_wizard.py` — use
   pytest-qt's `qtbot` for instantiation. If pytest-qt isn't installed,
   `pip install pytest-qt` and add to `requirements-dev.txt` (create
   if needed).
7. **Wire** the new wizard into `gui_qt/app.py` — when the user opens
   a workflow, the Qt wizard appears (NOT the tkinter one).
8. **Update STATUS.md** after each major step.

## Definition of done

- [ ] `gui_qt/setup_wizard.py` exists with the 4 wizard steps
- [ ] Controller API unchanged (no `controller.py` edits required)
- [ ] At least 8 pytest-qt tests covering: dialog construction,
      step transitions, content selection, output plan review
- [ ] Themeing hooks applied (every styled widget has `setObjectName`)
- [ ] Manual smoke test: launch with `opt_use_pyside6=True`, click
      through the wizard with a fake disc-titles list, every step
      renders and transitions
- [ ] Full suite green: 988 → ~1000 (depending on test count added)
- [ ] STATUS.md reflects 3b complete

## Stop-and-report

After EVERY major step, update `STATUS.md`. Same format as 3a's
brief. If you stop mid-port, the next session reads STATUS.md and
picks up cleanly.

## Hand off to 3c

When done, the user reviews. Once authorized, request the next
brief: `docs/handoffs/phase-3c-port-main-window.md`.
