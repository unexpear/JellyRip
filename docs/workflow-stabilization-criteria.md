# Workflow Stabilization — Completion Criteria

**Status:** Proposed (2026-05-03). Defines what "workflow
stabilization complete" actually means for the JellyRip MAIN
branch. This document is the gate criteria for the PySide6
migration per decision #2 in
[pyside6-migration-plan.md](pyside6-migration-plan.md). Every
checkbox below is a concrete observable thing — not "more
testing", not "feels stable" — so the gate has a finish line.

## Why this document exists

The migration plan says PySide6 work starts *"after workflow
stabilization."* Without a definition of "complete," that gate is
indefinite. This file converts the abstract gate into a per-workflow
checklist. When every checkbox is checked, the gate is closed and
PySide6 work is unblocked. Until then, the gate is open.

Concrete acceptance criteria below are deliberately calibrated for
a **single-maintainer pre-alpha project**, not enterprise QA. The
bar is "users with reasonable expectations on Windows 11 + a
LibreDrive-capable optical drive can complete this workflow without
losing data, without corrupted output, and without needing to
escalate to GitHub Issues for first-order paths."

## Workflow status as of 2026-05-03

Per [README.md](../README.md):

| Workflow | Current README status | Stabilization gate |
| --- | --- | --- |
| TV Disc | Some testing | Section 1 below |
| Movie Disc | Some testing | Section 2 below |
| Dump All | Some testing | Section 3 below |
| Organize Existing MKVs | Not tested | Section 4 below |
| FFmpeg / HandBrake transcoding | Not tested | Section 5 below |

The first three are partially exercised; the last two need first-
contact validation before any stabilization-of-known-issues work.

## Cross-cutting criteria (apply to all workflows)

These apply to every workflow before its workflow-specific section
can be considered complete:

- [x] **Behavior-first test coverage**: at least one
  `tests/test_behavior_guards.py` test (or analogous) exists that
  drives the workflow happy-path and pins the state-machine
  trajectory. The 825+ test baseline already covers most of these;
  a quick audit pass confirms no workflow is unprotected.
  *Closed 2026-05-03 by [tests/test_workflow_coverage_audit.py](../tests/test_workflow_coverage_audit.py) — 8 tests parametrically pin one happy-path test per workflow (run_smart_rip → trajectory + behavior_guards; run_movie_disc, run_tv_disc, run_dump_all → behavior_guards; run_organize → dedicated test_organize_workflow.py). The audit table is the single source of truth — if a workflow is renamed or its happy-path test deleted, the audit fails loudly. Plus a meta-pin asserting the table covers all 5 documented workflows (catches drift if a 6th is added).*
- [x] **Abort propagation**: aborting mid-flow (`engine.abort_event.set()`
  via the Stop Session button) marks the session aborted with
  partial outputs cleaned up — session metadata reflects
  `status="aborted"` / `phase="aborted"`, no zombie temp folders
  leak into the resume picker.
  *Closed 2026-05-03 — both code change and test coverage. New
  helper `mark_session_aborted` (mirrors `mark_session_failed`)
  writes `status="aborted"`/`phase="aborted"` and wipes
  `.mkv`/`.partial` files. New controller hook
  `_finalize_abort_cleanup_if_needed` runs in each rip-producing
  workflow's outer `try/finally`; it skips terminal phases
  (complete/organized/failed/aborted) so already-finalized sessions
  aren't overwritten. `find_resumable_sessions` filters
  `phase="aborted"` so aborted sessions do NOT appear in the resume
  picker — user-cancel actually means cancelled. Wired into
  `run_smart_rip`, `_run_disc` (manual TV/Movie), and `run_dump_all`
  (single + multi-disc). The previous "resume-friendly by accident"
  behavior is removed by user decision 2026-05-03 ("remove that
  resume thing we said its bad and make it match the docks") —
  resume after USER ABORT is now intentionally unavailable; resume
  after FAILURE (mark_session_failed path) and PARTIAL SUCCESS
  (`_preserve_partial_session` path) still work. Pinned by:
  - [tests/test_abort_propagation.py](../tests/test_abort_propagation.py) (16 tests) — engine-level abort contract, workflow-level abort respect.
  - [tests/test_abort_aftermath.py](../tests/test_abort_aftermath.py) (14 tests) — `mark_session_aborted` writes correct shape, wipes outputs, idempotent; `find_resumable_sessions` skips aborted phase; engine-level `abort_event.set()` alone doesn't clean up (cleanup is workflow-driven); `_finalize_abort_cleanup_if_needed` skips terminal phases / no-rip-path / no-flag; end-to-end `run_smart_rip` aborted mid-flow lands at `phase="aborted"` with outputs wiped and NOT in resume picker; partial-success path still resumable.*
- [x] **Resume support**: when a session fails or is aborted mid-rip,
  the partial-session metadata correctly captures `failed_titles` /
  `completed_titles` / `phase`, and the resume prompt offers the
  user the right choice. Pinned by `tests/test_session_recovery.py`
  for the data layer; the workflow integration is what stabilizes.
  *Integration closed 2026-05-03 by [tests/test_resume_support_integration.py](../tests/test_resume_support_integration.py) (15 tests). Engine round-trip (4): `write_temp_metadata` writes the full contract shape; `update_temp_metadata` preserves existing fields on partial update; `read_temp_metadata` returns None defensively; file-count recount on every update. Resume-detection rules (5): `find_resumable_sessions` returns partial sessions, skips complete/organized, skips folders without metadata, returns empty on missing temp_root, counts `.mkv` files recursively. Controller wiring (4): `_preserve_partial_session` writes `status="partial"`/`phase="partial"` plus all resume-relevant fields; normalizes string title IDs to int; defaults empty lists for None inputs; logs user-visible "Partial session preserved at:" message. End-to-end round-trip (1): controller-written partial session is discoverable via `find_resumable_sessions` with metadata intact. `delete_temp_metadata` cleanup (1): removes `_rip_meta.json` after success so the session no longer shows in the resume picker.*
- [x] **No data loss on user-cancel**: at no point during the
  workflow can the user lose original disc content, source files,
  or partial outputs without explicit confirmation.
  *Closed 2026-05-03 by [tests/test_no_data_loss_on_cancel.py](../tests/test_no_data_loss_on_cancel.py) (12 tests) — 4 engine-level (`unique_path` collision-walking, extension preservation), 2 `move_files` no-overwrite-without-`replace_existing` flag (the strongest single safeguard at `ripper_engine.py:1881`), 4 workflow-level (organize cancel-at-folder-picker preserves source MKV; cancel-at-media-type preserves; move-failure does NOT auto-delete temp folder even with `opt_auto_delete_temp=True`; `opt_auto_delete_temp=False` preserves source on success), 2 metadata-cleanup gates (`_cleanup_success_session_metadata` respects `opt_auto_delete_session_metadata=False`; dedups repeated folder paths to avoid double-action). Combined with prior pins in `test_organize_workflow.py` (source-outside-temp_root preserved) and `test_abort_propagation.py` (`cleanup_partial_files` preserves completed `.mkv`s), the user-cancel surface is now fully pinned.*
- [x] **Disk-space pre-checks fire before destructive work**: per
  `opt_check_dest_space` and `opt_warn_low_space` — workflows
  must call these gates before write-heavy operations.
  *Closed 2026-05-03 by [tests/test_disk_space_pre_checks.py](../tests/test_disk_space_pre_checks.py) — 12 tests, 6 engine-level (block/warn/ok decision tree, path-missing fallback, disk_usage exception fallback, custom hard_block_gb override) plus 6 workflow-integration on `run_smart_rip` (check fires before run_job; opt_scan_disc_size=False bypasses; block stops with friendly dialog; warn+opt_warn_low_space=True prompts user; user-decline stops; opt_warn_low_space=False silences prompt). Pinned the slight criterion misalignment found during audit: the temp-space pre-check is gated by `opt_scan_disc_size`, not `opt_check_dest_space` — the latter gates the engine-level destination-space check during move_files. See TASKS.md Done entry from 2026-05-03 for the full breakdown.*
- [x] **The state machine reaches a terminal state**: every workflow
  run, regardless of outcome (success / failure / abort), ends with
  `controller.sm.state` in either `COMPLETED` or `FAILED` — not
  stuck in an intermediate state.
  *Closed 2026-05-03 via Option B-lite — code change + test rewrite.
  Previously only `run_smart_rip` satisfied this; the audit found
  `run_dump_all` and `run_organize` did not touch the SM at all,
  leaking prior FAILED state into next-workflow session-summary log
  lines via `controller/session.py:write_session_summary`. Fixed by
  adding `_reset_state_machine()` at the entry of `run_organize`
  and `run_dump_all` (the outer entry point — covers both single-
  and multi-disc paths), plus `sm.complete()` on success terminals
  and `_state_fail("…")` on every failure terminal. Failure reasons
  are workflow-specific: `organize_move_failed`, `dump_rip_failed`,
  `dump_stabilization_failed`, `dump_integrity_failed`. No
  intermediate transitions added (those flows have no
  SCANNED→RIPPED→… phases — reset-and-terminal is the right
  shape, mirroring `_run_disc_inner`'s existing pattern). Pinned by
  [tests/test_workflow_sm_audit.py](../tests/test_workflow_sm_audit.py)
  (11 tests — reset-on-cancel, happy-path-completes, failure-path-
  fails for both `run_organize` and `run_dump_all`; plus the
  pre-existing `_run_disc_inner` and `run_smart_rip` baselines).
  The cross-cutting criterion is now uniformly satisfied across all
  five workflow entry points.*

---

## 1. TV Disc workflow

**Entry point**: `controller.run_tv_disc()` →
`controller._run_disc(is_tv=True)`.

### Real-disc validation
- [ ] One **clean rip** of a multi-episode DVD or Blu-ray TV disc
  (≥ 4 episodes detected) end-to-end without intervention beyond
  expected prompts. Output files land in the correct
  `Show Name (Year)/Season N/` structure with episode numbering
  matching MakeMKV's title order or user override.
- [ ] One **partial rip recovery**: deliberately abort mid-rip on
  episode 3 of N. Verify session metadata captures `partial`
  status with completed_titles, and the next run offers resume.
- [ ] One **disc-swap multi-disc TV set**: 2+ discs from the same
  show, ripped sequentially. Episodes from disc 2 land in the
  correct season folder without user re-entering metadata.

### Failure-mode coverage
- [ ] **Drive eject during rip** → state ends FAILED, partial files
  cleaned, no zombie temp folder.
- [ ] **Disk full during rip** (simulate with a small destination
  drive) → workflow surfaces the friendly error and ends FAILED.
- [ ] **Title selection cancelled** → workflow ends cleanly with
  no temp folder created.

### Documentation
- [ ] README updated: TV Disc status changes from *"some testing"*
  to *"validated: clean rip, partial-recovery, disc-swap, abort,
  disk-full"*.

---

## 2. Movie Disc workflow

**Entry point**: `controller.run_movie_disc()` or
`controller.run_smart_rip()` → `_run_smart_rip_inner()`.

### Real-disc validation
- [ ] One **clean Smart Rip** on a movie disc with multiple titles
  (main feature + ≥ 2 extras). Classifier picks the correct main
  title. Extras correctly classified into the chosen
  `featurettes` / `behind the scenes` / etc. folders.
- [ ] One **manual movie selection**: user overrides the classifier's
  pick. Output filename matches the user-entered title and year.
- [ ] One **multi-version disc**: theatrical + extended versions on
  the same disc → user can pick which to rip via edition picker.

### Failure-mode coverage
- [ ] **Classifier low-confidence** (no clear main title) → wizard
  routes through manual picker; user selection is honored.
- [ ] **Output folder collision** (same title already exists) →
  user gets a clear duplicate-resolution prompt; no overwrite
  without explicit confirmation.
- [ ] **Stabilization timeout** on a slow drive → workflow surfaces
  the warning, completes the rip, validates downstream.

### Documentation
- [ ] README updated: Movie Disc status changes from *"some testing"*
  to *"validated: smart rip, manual override, multi-version,
  classifier fallback, duplicate resolution"*.

---

## 3. Dump All workflow

**Entry point**: `controller.run_dump_all()`.

### Real-disc validation
- [ ] One **single-disc dump** of all titles to a temp folder.
  All ripped files appear under the temp root with correct
  size and duration metadata.
- [ ] One **multi-disc dump session** (≥ 2 discs in one batch).
  Per-disc folder organization is correct.

### Failure-mode coverage
- [ ] **Disk full mid-dump** → friendly error, partial outputs
  preserved (this is dump mode — partial is acceptable).
- [ ] **User-aborted dump** → temp folder is preserved with the
  ripped-so-far files; resume picks up from the next title.

### Documentation
- [ ] README updated: Dump All status changes from *"some testing"*
  to *"validated: single-disc dump, multi-disc batch, abort-with-
  partial-preservation, disk-full"*.

---

## 4. Organize Existing MKVs workflow

**Entry point**: `controller.run_organize()`.

### First-contact validation (currently "not tested")
- [ ] One **organize-from-temp** run: take an already-dumped temp
  folder (from Dump All) and walk it through movie classification
  → naming → move into `Movies (Year)/` structure.
- [ ] One **organize-from-arbitrary-folder**: point the workflow
  at an external folder of MKVs. Files get scanned, classified,
  and moved to the correct library structure.

### Failure-mode coverage
- [ ] **Unknown / unclassifiable file** → user gets a manual-naming
  prompt; no silent guessing.
- [ ] **Move target collision** → duplicate-resolution prompt
  fires, no silent overwrite.
- [ ] **Source folder readonly** → friendly error, no half-moved
  state.
- [ ] **Network share source disconnects mid-organize** →
  workflow surfaces the friendly error and ends FAILED with
  whatever was already moved staying intact.

### Test coverage gap
- [x] At least 5 behavior-first tests in
  `tests/test_behavior_guards.py` (or a new
  `tests/test_organize_workflow.py`) covering the happy path +
  the four failure modes above. Currently this workflow has the
  thinnest test coverage in the project.
  *Closed 2026-05-03 by [tests/test_organize_workflow.py](../tests/test_organize_workflow.py) — 12 tests covering 2 happy paths (movie + TV), 3 cancellation paths, 2 empty-input paths, the media-type validation loop, abort-with-failed-move, the temp-root safety property, and recursive-vs-flat glob patterns. See TASKS.md Done entry from 2026-05-03 for the full breakdown.*

### Documentation
- [ ] README updated: Organize Existing MKVs status changes from
  *"not tested"* to *"validated: temp-folder organize, external-
  folder organize, unknown-file prompt, collision resolution,
  readonly-source, network-share dropout"*.

---

## 5. FFmpeg / HandBrake transcoding workflow

**Entry point**: post-rip transcode via the queue builder, or the
explicit "Prep for FFmpeg / HandBrake" entry point.

### First-contact validation (currently "not tested")
- [ ] One **FFmpeg transcode** of a real ripped MKV. The encoded
  output exists, plays in a media player, and matches the
  selected profile's CRF/codec.
- [ ] One **HandBrake transcode** equivalent.
- [ ] One **safe-copy mode** (`opt_ffmpeg_source_mode = "safe_copy"`)
  end-to-end — staged copy completes, source remains intact, and
  the encoded output is correct.

### Failure-mode coverage
- [ ] **FFmpeg too old** → blocking dialog fires (existing
  `_ffmpeg_version_ok` check, already tested), user can abort or
  proceed.
- [ ] **HandBrake binary missing** → friendly error before queue
  starts, not mid-encode.
- [ ] **Disk full during encode** → friendly error, partial
  encoded file cleaned up, source MKV intact.
- [ ] **Skip-recommendation flag** (the half-built `recommend.py`
  feature, currently disabled): if/when wired, verify a
  small-HEVC source actually skips encode rather than re-encoding
  pointlessly. *(Can be deferred — this is a future-feature
  validation.)*

### Distribution criteria
- [ ] Bundled FFmpeg (`dist\main\ffmpeg.exe`,
  `dist\main\ffprobe.exe`, `dist\main\ffplay.exe`) verified to
  match the Gyan full-build that `release.bat` is configured for.
- [ ] FFmpeg-LICENSE.txt and FFmpeg-README.txt verified present.
- [ ] HandBrake distribution path documented in README — does the
  release ship HandBrake, or is it user-supplied?

### Documentation
- [ ] README updated: FFmpeg / HandBrake transcoding status changes
  from *"not tested"* to *"validated: FFmpeg encode, HandBrake
  encode, safe-copy mode, version-gate, missing-binary, disk-full"*.

---

## Stabilization signoff

The gate is closed when:

- [ ] All five workflow sections above have every checkbox checked.
- [ ] `pytest -q` is green at ≥ 95% behavior-first test pass rate
  (the existing 864+ tests bar, plus new tests for any
  workflow-specific gaps surfaced during stabilization).
- [ ] The README workflow-status table no longer says
  *"some testing"* or *"not tested"* anywhere.
- [ ] [TASKS.md](../TASKS.md) Active list contains a Done entry
  pointing at this document with the date the gate closed.

When that's all true, the PySide6 migration is unblocked per
decision #2.

## Out of scope

This document is **only** about workflow logic stability. Out of
scope:

- UI-level accessibility — handled by
  [ux-copy-and-accessibility-plan.md](ux-copy-and-accessibility-plan.md);
  several quick-wins already closed
- Code signing — decided in
  [code-signing-plan.md](code-signing-plan.md) (deferred indefinitely)
- AI BRANCH workflows — the AI BRANCH port follows MAIN per
  decision #1
- v1 release polish (CHANGELOG, screenshots, marketing copy) —
  separate concern, post-migration

## Update cadence

Update this document as workflows get tested. Each completed
checkbox is a small commit (or cluster of commits) with a
"closes criteria from workflow-stabilization-criteria.md" message.
The gate is concrete; progress should be visible.

## Not a commitment

This document captures the criteria, not the schedule. Workflow
stabilization is incrementally achievable; nothing here forces a
deadline. Update if the bar needs adjusting (e.g., bumping a "5
behavior tests" target up or down) — the goal is honest visibility,
not arbitrary thresholds.
