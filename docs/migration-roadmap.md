# JellyRip Migration Roadmap

**Status:** Living document (created 2026-05-03). Lays out the full
path from today's pre-alpha state (v1.0.18, tkinter, all 6
cross-cutting workflow-stabilization criteria closed) to v1.0
(PySide6, MKV preview, both branches ported). This is the high-level
plan. Per-phase implementation briefs live under `docs/handoffs/`.

This document does not authorize work, set dates, or replace the
existing planning artifacts. It is the single page that lets you (or
a fresh Claude session) understand the whole picture without
spelunking through TASKS.md history.

## Table of contents

- [Phase 1 — Final code prep](#phase-1--final-code-prep)
- [Phase 2 — Real-disc validation](#phase-2--real-disc-validation)
- [Phase 3 — PySide6 migration on MAIN](#phase-3--pyside6-migration-on-main)
- [Phase 4 — PySide6 migration on AI BRANCH](#phase-4--pyside6-migration-on-ai-branch)
- [Branch identity guardrails](#branch-identity-guardrails)
- [How to use this doc](#how-to-use-this-doc)

## Status snapshot (2026-05-03)

| Phase | Status | Who can do it |
| --- | --- | --- |
| Phase 1 — Final code prep | Mostly complete; optional `utils/scoring.py` test push remaining | Claude |
| Phase 2 — Real-disc validation | Open; gates Phase 3 per migration plan decision #2 | **You with a disc + drive** |
| Phase 3 — PySide6 migration on MAIN | Not started; gated on Phase 2 | Claude (with you reviewing) |
| Phase 4 — PySide6 migration on AI BRANCH | Not started; gated on Phase 3 ship | Claude (with you reviewing) |

Cross-cutting workflow-stabilization criteria: **6/6 closed**.
Per-workflow real-disc sections: **0/5 closed.**
Suite: MAIN 978 passed / 1 skipped; AI BRANCH targeted parity verified.

## Phase 1 — Final code prep

**Goal:** every code-only blocker between today and starting Phase 3
is closed. Phase 2 can begin in parallel; Phase 3 cannot start until
Phase 2 closes.

**Done in this phase already** (this session, 2026-05-03):

- Organize workflow test gap closed (`test_organize_workflow.py`, 12 tests)
- Cross-workflow SM behavior pinned + Option B-lite implementation (`test_workflow_sm_audit.py`, 11 tests; new `_state_fail` / `sm.complete()` calls in `run_organize` and `run_dump_all`)
- Disk-space pre-checks pinned (`test_disk_space_pre_checks.py`, 12 tests)
- Abort propagation + aftermath fully pinned (`test_abort_propagation.py` 16 + `test_abort_aftermath.py` 14 tests; new `mark_session_aborted` + `_finalize_abort_cleanup_if_needed`)
- No-data-loss-on-cancel pinned (`test_no_data_loss_on_cancel.py`, 12 tests)
- Behavior-first coverage audit (`test_workflow_coverage_audit.py`, 8 tests)
- Resume-support integration pinned (`test_resume_support_integration.py`, 15 tests)

**Optionally remaining** (does NOT block Phase 2 or Phase 3):

- **`utils/scoring.py` test push.** Per `memory/test-coverage.md`, this is the highest-value remaining unit-test gap. Scoring drives main-title selection in the classifier. Behavior-first tests here survive Phase 3 per migration decision #5, so the work pays off twice (today + after migration).
- **`shared/runtime.py` and `shared/ai_diagnostics.py` coverage.** Less urgent.
- **`utils/fallback.py` / `utils/media.py` / `utils/session_result.py` coverage.** Lower value.

**Estimated remaining effort if you do the optional work:** ~1-2 hour Claude session.

## Phase 2 — Real-disc validation

**Goal:** every per-workflow checkbox in `workflow-stabilization-criteria.md`
sections 1-5 ticked. README workflow-status table flips from "some
testing" / "not tested" to "validated: …".

**Why this is your part, not Claude's:** the checkboxes describe
real-disc behavior — drive eject during rip, disk full, multi-disc
TV set, classifier low-confidence, output folder collision, etc.
These need an actual disc and an actual drive. Claude can support
(write tests for issues you find, update README, ask clarifying
questions) but cannot do the validation itself.

**Per-workflow checklist** (full detail in
[workflow-stabilization-criteria.md](workflow-stabilization-criteria.md)):

1. **TV Disc** — clean rip (≥4 episodes), partial-rip recovery (abort mid-episode-3), multi-disc TV set, drive-eject failure, disk-full, title-selection-cancelled
2. **Movie Disc** — clean Smart Rip (main + ≥2 extras), manual movie selection override, multi-version disc (theatrical + extended), classifier low-confidence routing, output folder collision, stabilization timeout
3. **Dump All** — single-disc dump, multi-disc batch, disk-full mid-dump, user-aborted dump
4. **Organize Existing MKVs** — organize-from-temp, organize-from-arbitrary-folder, unknown-file prompt, move-target-collision, readonly source, network-share dropout
5. **FFmpeg / HandBrake transcoding** — FFmpeg encode, HandBrake encode, safe-copy mode, FFmpeg-too-old, HandBrake-binary-missing, disk-full-during-encode, distribution criteria

**Estimated effort:** 1-3 evenings of your time, depending on how many edge cases you hit. Each evening's worth of testing produces a small set of follow-up code/test fixes Claude can land same-week.

**Sequencing recommendation:** start with **Movie Disc** — it's the
most-used workflow, the smart-rip flow has the most existing test
coverage so issues will be most isolated, and the failure modes are
the clearest. TV Disc and Dump All next; Organize and Transcoding
last (those are "not tested" baseline, expect more findings).

## Phase 3 — PySide6 migration on MAIN

**Goal:** MAIN ships v1.0 with PySide6 GUI replacing tkinter, MKV
preview before commit (the v1-blocking feature per migration plan
decision #4), equipable theme system, native Windows feel.

**Gated on:** Phase 2 closing.

**Per migration plan decision #1:** MAIN goes first; AI BRANCH stays
on tkinter the whole time MAIN is migrating. AI BRANCH gets ported
in Phase 4.

**Sub-phases** (each is a candidate handoff brief):

### 3a — PySide6 scaffolding + theme system

- Create `gui_qt/` directory structure (parallel to `gui/`)
- Wire `main.py` with a feature flag (`opt_use_pyside6=True/False`) to launch either UI
- Build the equipable theme system per migration plan decision #7 — QSS files in `gui_qt/qss/`, theme picker in Settings
- Initial themes per decision #7. **Updated 2026-05-03:** user delivered 6 themes (not the original 3 placeholders). Set: `dark_github` (current palette ported), `light_inverted` (closes UX/A11y Finding #2 contrast bug), `dracula_light`, `hc_dark`, `slate`, `frost`. Source-of-truth tokens + layout + recipe live in `docs/design/themes/` ([README](design/themes/README.md))
- Smoke test: launch with feature flag on, verify themed window appears, no real workflows wired yet

**Branch:** MAIN only. AI BRANCH untouched.

**Estimated:** 1 focused Claude session (4-6 hours).

### 3b — Port setup wizard

- `gui/setup_wizard.py` (the longest screen) → `gui_qt/setup_wizard.py`
- All wizard step screens (scan results, content mapping, extras classification, output plan)
- Wire to existing controller methods unchanged

**Estimated:** 1-2 sessions.

### 3c — Port main window + dialogs

- `gui/main_window.py` (~7,800 lines today) — split into per-screen modules
- All `messagebox` and custom-dialog call sites get Qt equivalents
- Status bar, log pane, progress bar, per-task queue view (new in Qt — migration plan capability)

**Estimated:** 2-3 sessions.

### 3d — Port settings + ancillary screens

- `gui/settings_window.py` and tabs
- `update_ui.py`, ad-hoc dialogs
- Theme picker UI (consumes the system from sub-phase 3a)

**Estimated:** 1 session.

### 3e — Wire MKV preview (the v1-blocking feature)

- `QtMultimedia` `QMediaPlayer` widget in the wizard's "review output plan" step
- User can play any selected title's first 30 seconds before committing the rip
- Catch wrong-title-selected before 30+ GB writes to disk

**Estimated:** 1 session. This is the headline feature.

### 3f — Update build/release scripts

- `JellyRip.spec` — add Qt plugins to PyInstaller bundling
- `build.bat` / `build_installer.bat` — verify Qt artifacts bundle correctly
- `release.bat` — runs the test suite; needs `pytest-qt` integration
- Smoke test: built `.exe` on a clean Windows machine

**Estimated:** 1 session.

### 3g — Rewrite tkinter-touching tests under pytest-qt

- Tests in `test_imports.py` and `test_main_window_formatters.py` that touch tkinter widgets get rewritten or deleted per migration plan decision #5
- Behavior-first tests survive untouched

**Estimated:** 1-2 sessions.

### 3h — tkinter retirement + v1.0 release prep ✅ DONE 2026-05-04

Two passes landed under the 3h header:

- **3h prep (earlier in 2026-05-04)** — README + CHANGELOG entry for
  v1.0.19, Phase 3h handoff brief written, requirements.txt updated.
- **3h execution (this turn)** — tkinter retirement per
  `docs/handoffs/phase-3h-tkinter-retirement.md`. Shared types lifted
  to `shared/wizard_types.py` and `shared/session_setup_types.py`,
  every `from gui.<X>` import switched, `gui/*.py` and three
  tkinter-only test files tombstoned, entrypoints cleaned. Repo-wide
  grep confirms zero live `gui.<retired-module>` imports.

**Still TBD before tagging v1.0.19:**

- Manual smoke on a fresh `build.bat` — sections 3-9 of
  `docs/handoffs/bot-smoke-test.md` against the rebuilt `.exe`.
- Recovery of 4-5 truncated behavior-first test files (separate
  issue, see STATUS.md task list).
- `release.bat 1.0.19` on explicit user go-ahead.

**Total Phase 3 estimate:** 8-12 focused Claude sessions, spread over
2-4 weeks of calendar time.

## Phase 4 — PySide6 migration on AI BRANCH

**Goal:** AI BRANCH ports to PySide6, reusing MAIN's port as the
base, adding back the AI features in Qt-native form.

**Gated on:** MAIN shipping v1.0 from Phase 3.

**Detailed handoff brief:**
[docs/handoffs/phase-4-ai-branch-port.md](handoffs/phase-4-ai-branch-port.md)
— full step-by-step plan with merge conflict guidance,
risk register, and acceptance criteria. Read that before starting
Phase 4 work.

**Per migration plan decision #1:** AI BRANCH stays tkinter the whole
time MAIN is migrating. The port is a defined event, not a parallel
track.

**Sub-phases:**

### 4a — Rebase AI BRANCH on MAIN's PySide6 base

- Bring the `gui_qt/` foundation from MAIN into AI BRANCH
- Resolve any merge conflicts in non-AI-feature files
- Verify all of MAIN's PySide6 functionality works on AI BRANCH

### 4b — Port the AI chat sidebar to Qt

- `gui/ai_chat_sidebar.*` → `gui_qt/ai_chat_sidebar.py`
- Use `QTextBrowser` + `QTextDocument` for native markdown / code-block rendering (per migration plan rationale)
- Streaming responses via Qt signals instead of tkinter `after()` polling
- Keep all current capability — sidebar is AI BRANCH's identity

### 4c — Port AI provider dialog + identity assist UI

- `gui/ai_provider_dialog.py` → `QDialog` + `QFormLayout` (cleaner shape in Qt)
- `controller/assist.py` UI surfaces (confidence sliders, alternate suggestions, undo)

### 4d — AI BRANCH v1.0 release

**Total Phase 4 estimate:** 4-6 focused Claude sessions, after MAIN
v1.0 ships.

## Branch identity guardrails

These apply to every phase. They should be repeated verbatim in
every handoff brief Claude is given for migration work.

1. **No AI features in MAIN, ever.** The chat sidebar
   (`gui/ai_chat_sidebar.py`), identity assist (`controller/assist.py`),
   workflow history (`shared/workflow_history.py`), and the Anthropic
   SDK dependency exist only on AI BRANCH. Migration must not pull
   them into MAIN.
2. **Preserve AI BRANCH's AI surface.** When AI BRANCH ports in
   Phase 4, the chat sidebar must keep its current capability. The
   migration improves rendering (`QTextBrowser` markdown), it does
   not strip features.
3. **Test symmetry where it makes sense, divergence where it doesn't.**
   Both branches share most tests. Some test names already diverged
   (per `test_workflow_coverage_audit.py`'s multi-candidate row for
   TV-disc). Preserve current divergence; do not align unless you
   have a specific reason.
4. **Both branches use the same QSS theme system.** AI BRANCH can
   add chat-specific styling, but the base palette matches MAIN.
   Themes live in `gui_qt/qss/*.qss` per migration plan decision #7.
5. **Branch-aware constants stay branch-aware.** `APP_DISPLAY_NAME =
   "JellyRip"` on MAIN, `"JellyRip AI"` on AI BRANCH. Anywhere a
   branch-specific value lives, preserve it.
6. **No "while we're here" cross-branch cleanup.** The migration
   isn't a refactor opportunity to homogenize the branches. Stay on
   the migration goal.
7. **Git rules from CLAUDE.md still apply.** No commits, pushes,
   tags, or `release.bat` runs without explicit user go-ahead.
   Local file edits are fine.

## How to use this doc

- **You** — re-read this when starting a new Claude session about
  migration work, or when you've lost track of what comes next.
- **Future Claude session** — start every migration-related
  conversation by reading this file. The handoff brief tells you
  *what to do this session*; this document tells you *how it fits
  into the whole plan*.
- **When something changes** — update this doc. It's a living
  document. If a sub-phase's estimate is wrong, fix it. If a guard
  rail needs to be added, add it.
- **When a phase closes** — update the status snapshot table at
  the top, update the corresponding `workflow-stabilization-criteria.md`
  or other artifact, then move on.

This document is the long view. Specific sessions still need their
own focused brief — see `docs/handoffs/` for those.
