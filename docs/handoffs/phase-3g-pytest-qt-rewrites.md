# Handoff Brief — Phase 3g: Rewrite tkinter-touching tests under pytest-qt

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3g in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3f (build scripts).
**Successor:** Phase 3h (v1.0 release prep).

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md`
- `docs/pyside6-migration-plan.md` decision #5 (test rewrite policy)
- The behavior-first test list in `memory/test-coverage.md` —
  these survive the migration unchanged.

## Goal

Per migration plan decision #5: behavior-first tests survive
unchanged; tkinter-touching tests get rewritten under pytest-qt
or deleted in place.

By the time you reach this phase, a lot of tkinter-touching tests
have already been migrated alongside their corresponding screen
ports (3b/3c/3d). This phase mops up anything that's left and
verifies the test suite is uniformly behavior-first or pytest-qt.

## Branch identity guardrails

Same. **No AI features in MAIN.**

## Concrete plan

1. **Audit** — find every test file that imports from `gui/` or
   uses `unittest.mock.patch("tkinter.Tk", ...)`:

   ```bash
   grep -rln "from gui\." tests/
   grep -rln "tkinter.Tk" tests/
   ```

2. **Categorize** each hit:
   - **Behavior-first** (no UI assertions) → leave alone
   - **Pure formatters** (already in `gui_qt/formatters.py` after
     Phase 3c) → repoint imports, no logic change
   - **UI assertions** (tests that exercise widget behavior) →
     rewrite under pytest-qt OR delete if the underlying widget
     was replaced wholesale

3. **Delete `gui/`** — at this point the tkinter UI is fully
   replaced. Schedule deletion for early Phase 3h. Update README
   to drop the tkinter references.

## Definition of done

- [ ] No test file imports from `gui/`
- [ ] No test file uses `tkinter.Tk` mocking
- [ ] All UI tests use `pytest-qt`
- [ ] Test count similar or higher (don't lose coverage in the
      rewrite — convert, don't drop)
- [ ] STATUS.md reflects 3g complete

## After this phase

Phase 3h: README + CHANGELOG + screenshots + tag + `release.bat 1.0.0`.

The migration ships.
