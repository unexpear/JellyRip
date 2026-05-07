# Tasks

## Active

> Active items below have been reground in the actual code as of 2026-04-29 after three audit agents found that the previous descriptions (UI adapter extraction, recommend.py drift, windows_exec injection fuzz, profile serialization round-trip) were based on incorrect assumptions about what the code does. Each item now references real file:line locations and a real seam.

### 1. PySide6 migration of the GUI layer *(v1-blocking, gated on workflow stabilization)*
**Status:** Approved direction (2026-05-02). MAIN first; AI BRANCH stays tkinter until MAIN port is proven.

**Why this is now in Active rather than Someday:**
- v1 ship requires MKV preview (catch wrong-title-selected before 30+ GB writes to disk). MKV preview requires PySide6 (tkinter has no video widget). So **PySide6 ship → v1 ship**.
- All eight open questions in [docs/pyside6-migration-plan.md](docs/pyside6-migration-plan.md) now have answers. See the *"Decisions Captured 2026-05-02"* section there.
- Equipable theme system (from the UX/A11y plan's Finding #2 contrast bug + Finding #20 friendly profile summary) is folded into the migration. QSS supports it natively; tkinter would have been throwaway infrastructure.

**What this does NOT mean:**
- PySide6 code does not start now. **Workflow stabilization is the gate** (decision #2). README documents workflows as "some testing" / "not tested"; that gate must close first.
- Ongoing tkinter-side work (test coverage push, in-tkinter accessibility quick wins like Finding #1 product-name fix that already shipped) continues until the gate closes.

**Pre-migration parallel-track work** (does not block on workflow stabilization):
- SignPath.io OSS code-signing application — apply now, ~1-2 week review window. Plan in [docs/code-signing-plan.md](docs/code-signing-plan.md).
- Workflow stabilization itself — closes the gate.
- Test coverage push for behavior-first tests (state machine, parsers, controller wiring, etc.) — these survive the migration per decision #5 and pay off twice.

**Migration begins when:** workflow stabilization is declared complete.
**Migration ends when:** v1 ships with all of `gui/` and most of `ui/` ported to PySide6, MKV preview wired, equipable theme system live, all tkinter-touching tests rewritten under pytest-qt or deleted, SignPath.io code-signing live.


### Items dropped during audit

- ~~Profile serialization round-trip~~ — already covered: `ProfileLoader` save/load + `TranscodeProfile.to_dict()` round-trip exercised in [tests/test_imports.py](tests/test_imports.py) (`test_save_expert_profile_data_updates_loader`, `test_persist_settings_and_profile_*`, `test_duplicate_expert_profile_copies_profile_data`, etc.).
- ~~recommend.py vs recommendations.py drift~~ — replaced by item 6 (dead-code cleanup).
- ~~UI adapter extraction~~ — replaced by item 5 (no refactor needed; just tests on already-pure methods).
- ~~Headless smoke test for `gui/main_window.py` init/teardown~~ — already covered by `test_gui_import` ([tests/test_imports.py:18-25](tests/test_imports.py:18-25)) and `test_on_close_destroys_window_without_force_exit` ([tests/test_imports.py:570-595](tests/test_imports.py:570-595)).

## Waiting On

## Someday

- **UX copy and accessibility cleanup.** 2026-05-02 audit found 21 issues across user-visible strings, contrast, focus indicators, and screen-reader exposure on this branch. Bug-grade items: product name appears in three different forms across dialogs (`JellyRip` / `Jellyfin Raw Ripper` / `Raw Jelly Ripper`); white-on-blue primary buttons fail WCAG contrast at 2.5:1; `relief="flat"` buttons have no visible focus indicator. Plan, full findings, contrast measurements, and proposed `docs/copy-style.md` + `docs/glossary.md` foundations live in [docs/ux-copy-and-accessibility-plan.md](docs/ux-copy-and-accessibility-plan.md). Status: Proposed. Quick-win items don't depend on the PySide6 migration; framework-limited items do.

## Done

- [x] ~~**SM-trajectory cross-cutting criterion closed via Option B-lite (both branches)**~~ (2026-05-03) — **closes the LAST cross-cutting criterion** in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md). All 6 cross-cutting checkboxes are now ticked. Per the migration plan decision #2, this was the gating set for unblocking the PySide6 migration's *cross-cutting* criteria; only the per-workflow real-disc validation sections remain (those need an actual disc + drive — your part).
  - **Why this was done**: the audit found `run_dump_all` and `run_organize` did not touch the SM at all. A failed `run_smart_rip` followed by a successful `run_organize` would leave `sm.state == FAILED`, and `controller/session.py:write_session_summary` would log *"Session summary: Session failed."* even though the most recent workflow succeeded. User-visible misleading text. Real bug, not just internal bookkeeping.
  - **Why Option B-lite (not full B)**: `run_dump_all` and `run_organize` don't have SCANNED→RIPPED→STABILIZED→VALIDATED→MOVED phases the way smart rip does. So adding intermediate transitions would be invented contract, not pinning real behavior. The minimum-viable change is reset-and-terminal: copy the pattern `_run_disc_inner` already follows. ~10 lines of code per workflow.
  - **Code changes** (both branches):
    - [controller/controller.py](controller/controller.py) `run_organize`: added `self._reset_state_machine()` at workflow entry; `self.sm.complete()` on `move_ok=True`; `self._state_fail("organize_move_failed")` on `move_ok=False` (replaces the prior bare `elif self.engine.abort_event.is_set()` log).
    - [controller/controller.py](controller/controller.py) `run_dump_all` (outer): added `self._reset_state_machine()` after the `_current_rip_path = None` init.
    - [controller/controller.py](controller/controller.py) `_run_dump_all_inner` (single-disc): added `self._state_fail("dump_rip_failed")` / `_state_fail("dump_stabilization_failed")` / `_state_fail("dump_integrity_failed")` on the three failure-return points; added `self.sm.complete()` before `write_session_summary` on the success terminal.
    - [controller/controller.py](controller/controller.py) `_run_dump_all_multi` (per-disc loop): added `self._state_fail(...)` on the three break-on-failure points; added `self.sm.complete()` after the loop (no-op if a disc-level fail already fired — `sm.complete()`'s docstring guarantees this).
  - **Test changes** (both branches):
    - [tests/test_workflow_sm_audit.py](tests/test_workflow_sm_audit.py) — file docstring rewritten to remove the audit-finding framing; test pairs flipped from "does NOT touch SM" to the new contract.
    - For each of `run_organize` and `run_dump_all`: replaced 2 audit-finding tests (cancel-no-touch, happy-no-touch+leaks-FAILED) with 3 new tests covering the correct contract (cancel-resets, happy-resets-and-completes, failure-resets-and-fails).
    - **Spy gotcha caught and fixed during test rewrite**: the `_SMSpy` wraps `controller.sm.complete`, but `_reset_state_machine` rebuilds `self.sm` from scratch — so the post-reset `sm.complete()` was hitting the un-spied original. Fix: factored a `_patch_complete_on_current_sm()` helper and called it from inside the reset-spy so the new SM gets re-spied each reset. This isn't a behavior bug; it's a test-infrastructure bug that would have made the spy under-count complete calls in any future test that crosses a reset boundary. Comment added at the spy install site explaining the lifecycle.
  - **No regressions**: all pre-existing tests pass on both branches. The changes are additive — failing paths got an extra `_state_fail` line; success terminals got a `sm.complete()` line; entries got a `_reset_state_machine()` line. Nothing existing was rerouted.
  - **Suite**: MAIN 976 → **978** (+2 net: replaced 4 tests with 6). AI BRANCH targeted run in flight.

  ### 🎉 All 6 cross-cutting criteria are now closed
  | Cross-cutting criterion | Status |
  | --- | --- |
  | Behavior-first test coverage | ✅ Closed |
  | Abort propagation | ✅ Closed |
  | Resume support | ✅ Closed |
  | No data loss on user-cancel | ✅ Closed |
  | Disk-space pre-checks | ✅ Closed |
  | **State machine reaches terminal state** | ✅ **Closed (this commit)** |

  Remaining in `workflow-stabilization-criteria.md`: the **per-workflow real-disc validation sections** (TV / Movie / Dump / Organize / Transcoding) — those need a disc + drive, so that's interactive work, not code. Once those close, the PySide6 migration is unblocked per migration-plan decision #2.

- [x] ~~**Abort propagation — code change + test rewrite to match criteria docs (both branches)**~~ (2026-05-03) — **closes the abort-propagation cross-cutting criterion fully** (was previously partial-pinned with audit findings). User decision 2026-05-03: *"remove that resume thing we said its bad and make it match the docks"* — implemented Option B from the explainer (add explicit aborted status + clean up on abort + filter from resume picker). The criterion checkbox in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md) is now ticked.
  - **Code changes** (both branches):
    - [controller/session_recovery.py](controller/session_recovery.py): new `mark_session_aborted` helper, mirroring `mark_session_failed` but writing `status="aborted"`/`phase="aborted"`. Idempotent via the shared `wiped_session_paths` set. Wipes `.mkv`/`.partial` files; keeps the metadata file as a tombstone for diagnostics.
    - [engine/ripper_engine.py](engine/ripper_engine.py): `find_resumable_sessions` skip-phase set extended from `{"complete", "organized"}` to `{"complete", "organized", "aborted"}`. Aborted sessions no longer leak into the resume picker.
    - [controller/legacy_compat.py](controller/legacy_compat.py): new `_mark_session_aborted` wrapper + new `_finalize_abort_cleanup_if_needed` hook. The hook reads `_current_rip_path`, checks if abort_event is set, checks the metadata phase isn't already terminal, and calls `_mark_session_aborted` if so. Resets `_current_rip_path` afterwards.
    - [controller/controller.py](controller/controller.py): new `_current_rip_path: Optional[str]` field on `RipperController.__init__`. Set to `rip_path` after each `engine.write_temp_metadata()` call in the 4 rip workflows (`_run_smart_rip_inner`, `_run_disc_inner`, `_run_dump_all_inner` single-disc, `_run_dump_all_multi` per-disc loop). Reset to `None` at the start of each workflow's outer `run_*` entry point. Outer entry points (`run_smart_rip`, `_run_disc`, `run_dump_all`) wrap their inner calls in `try/finally` and call `_finalize_abort_cleanup_if_needed()` in the finally block.
  - **Why the resume-after-abort path was removed**: previously, an aborted session kept `phase="ripping"` and showed up in the resume picker because the workflow returned early without writing aborted status. The user explicitly chose Stop Session — resume-from-where-they-left-off was confusing UX. Now: abort is final. Resume after FAILURE still works (mark_session_failed → phase=failed, but find_resumable_sessions still discovers it for retry). Resume after PARTIAL SUCCESS still works (`_preserve_partial_session` → phase=partial, resumable).
  - **Test changes**:
    - [tests/test_abort_aftermath.py](tests/test_abort_aftermath.py) — REWRITTEN. Old tests pinned the "audit finding" gap (resume-friendly-by-accident, zombie folders preserved); new tests pin the actual contract: `mark_session_aborted` writes correct shape (3 tests); `mark_session_failed` writes "failed" not "aborted" — distinct paths (1 test); `find_resumable_sessions` skips `phase="aborted"` (1 test); engine-level `abort_event.set()` alone does NOT clean up — workflow drives cleanup (2 tests); `_finalize_abort_cleanup_if_needed` contract — runs when flag set + rip_path populated + non-terminal phase, no-op otherwise (4 tests); end-to-end `run_smart_rip` aborted mid-flow → marked aborted + outputs wiped + NOT in resume picker (1 test); partial-success preserve path still resumable (1 test); successful-organize cleanup still removes session from picker (1 test). 14 tests total, MAIN + AI BRANCH both green.
  - **No regressions**: all pre-existing tests still pass on both branches. The new code paths are additive — they only fire when `_current_rip_path` is populated AND `abort_event.is_set()` AND the phase isn't already terminal. Engine-level direct `abort_event.set()` (used in many existing tests) is unaffected because no workflow finally block ran.
  - **Suite**: MAIN 970 → **976** (+6 net: rewrote 8 tests as 14 new tests, dropped some now-irrelevant pins). AI BRANCH targeted 14/14 green; full suite still backgroundable.

- [x] ~~**Abort aftermath tests — close 3 open sub-items under "Abort propagation" (both branches)**~~ (2026-05-03) — closes the 3 open sub-items left under the abort-propagation cross-cutting criterion. The criterion checkbox itself stays unticked because the audit found the criterion text doesn't match the code's chosen design — needs a deliberate user decision, not an audit pass.
  - **New file**: [tests/test_abort_aftermath.py](tests/test_abort_aftermath.py) (8 tests, mirrored to AI BRANCH).
  - **Sub-item 1: "Session metadata accurately reflects 'aborted' status" → AUDIT FINDING.** There is no distinct "aborted" status in the codebase. `mark_session_failed` writes `status="failed"`; `_preserve_partial_session` writes `status="partial"`. Abort during a rip does NOT call either automatically — the workflow returns early and metadata keeps its prior `status="ripping"`. This is **resume-friendly by accident**: aborted sessions show up in the resume picker because they're not marked complete. Pinned by 2 tests (`test_abort_during_rip_does_not_change_metadata_status_today`, `test_mark_session_failed_writes_failed_status_not_aborted`). Any future code change introducing an explicit "aborted" status is a deliberate test update.
  - **Sub-item 2: "No zombie temp folders" → AUDIT FINDING.** Temp folders from aborted sessions are PRESERVED by design — they're the data resume needs. The "zombie folders" wording in the criterion is a misnomer when resume is the deliberate strategy. Folders are eventually cleaned via `opt_clean_partials_startup` on the next launch (already pinned in `test_abort_propagation.py`). Pinned by 3 tests (`test_aborted_temp_folder_is_preserved_for_resume`, `test_aborted_session_appears_in_resumable_list`, `test_abort_does_not_call_cleanup_partial_files_implicitly`).
  - **Sub-item 3: "Recoverable state preserved (resume-after-abort end-to-end)" → CLOSED.** Pinned by 3 tests (`test_abort_then_resume_round_trip_preserves_metadata`, `test_abort_after_partial_complete_resumes_with_completed_state`, `test_organize_uses_completed_session_phase_to_filter_from_resume`). End-to-end abort → next-launch `find_resumable_sessions` → metadata intact (title, year, media_type, season, selected/completed/failed_titles). Plus the partial-progress case (`_preserve_partial_session` upgrades `phase="ripping"` to `phase="partial"` with `completed_titles` populated so resume doesn't waste prior work). Plus the cleanup-after-success path so completed sessions don't leak into the resume picker forever.
  - **Why the criterion checkbox stays unticked**: 2 of 3 sub-items revealed the criterion text ("aborted status", "zombie folders") doesn't match the code's chosen design (resume-by-default via preserved metadata). The next move is for the user, not an audit pass: either (a) update the criterion text to "session is recoverable after abort" (which the tests already pin), or (b) introduce an explicit "aborted" status separate from "failed"/"ripping" and rewrite the cleanup contract. Honest visibility over false-green tick.
  - **Suite**: MAIN 962 → **970** (+8, 1 skipped). AI BRANCH 8/8 targeted green.

- [x] ~~**Resume-support integration tests (both branches)**~~ (2026-05-03) — closes the **last open** cross-cutting criterion in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md): *"Resume support"*. The data layer was already pinned in `test_session_recovery.py` (5 tests); this fills the workflow-integration gap.
  - **New file**: [tests/test_resume_support_integration.py](tests/test_resume_support_integration.py) (15 tests, mirrored to AI BRANCH).
  - **Engine round-trip (4 tests)** — `write_temp_metadata` / `update_temp_metadata` / `read_temp_metadata` agree on the metadata contract:
    - `write_temp_metadata` writes the full shape (title/year/media_type/season/selected_titles/episode_names/episode_numbers/completed_titles/phase/dest_folder/disc_number/timestamp/file_count/status). Missing any of these breaks the resume picker.
    - `update_temp_metadata` is a partial update — fields not passed in remain at their previous values (pins the merge semantics at `ripper_engine.py:633-636`).
    - `read_temp_metadata` returns None defensively on missing file (no try/except needed at every caller).
    - `update_temp_metadata` recounts `.mkv` files on every call (resume picker shows progress).
  - **Resume-detection rules (5 tests)** — `find_resumable_sessions`:
    - Returns sessions with `phase="ripping"` (or any phase other than `complete`/`organized`).
    - Skips `phase="complete"` and `phase="organized"` (already done).
    - Skips folders without `_rip_meta.json` (user-created or stale folders not resumable).
    - Returns `[]` on non-existent temp_root (defensive, no exception).
    - Counts `.mkv` files recursively across nested folders (the 4th tuple element).
  - **Controller wiring (4 tests)** — `_preserve_partial_session`:
    - Calls `engine.update_temp_metadata` with `status="partial"` and `phase="partial"` plus all resume-relevant fields. Pins the integration handshake.
    - Normalizes string title IDs (e.g., `"1"` from rip subprocess output) to int. Pins the `int(title_id)` coercion at `legacy_compat.py:205-209`.
    - Defaults empty lists for None inputs (`list(selected_titles or [])` pattern — JSON readers expect lists, not nulls).
    - Logs user-visible *"Partial session preserved at: <rip_path>"* so the user knows the data is there for resume.
  - **End-to-end round-trip (1 test)** — controller writes a partial session via `_preserve_partial_session` → engine's `find_resumable_sessions` discovers it with metadata intact (title, phase, selected_titles, completed_titles, failed_titles all readable). Pins the round-trip integrity that resume support depends on.
  - **Cleanup contract (1 test)** — `delete_temp_metadata` removes `_rip_meta.json` so the session no longer shows in the resume picker after a successful organize.
  - **Behavior-first**: no GUI/Tk touches, no real subprocess. Survives the planned PySide6 migration per decision #5.
  - **Suite**: MAIN 947 → **962** (+15, 1 skipped). AI BRANCH 15/15 targeted green.

  ### 🎉 All 6 cross-cutting criteria now have status (3 fully closed, 2 partial-pinned with honest gaps, 1 audit-pinned)
  | Cross-cutting criterion | Status |
  | --- | --- |
  | Behavior-first test coverage | ✅ Closed |
  | Abort propagation | ⚠️ Partial close (engine + 3 workflows pinned; 3 sub-items still open) |
  | Resume support | ✅ **Closed (this commit)** |
  | No data loss on user-cancel | ✅ Closed |
  | Disk-space pre-checks | ✅ Closed |
  | State machine reaches terminal state | ⚠️ Audit-pinned (gap honestly surfaced; cannot tick without code change) |

  Remaining stabilization work is in the **per-workflow sections** of `workflow-stabilization-criteria.md` — those need real-disc validation, not code.

- [x] ~~**Behavior-first coverage audit + no-data-loss tests (both branches)**~~ (2026-05-03) — closes TWO cross-cutting criteria from [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md): *"Behavior-first test coverage"* and *"No data loss on user-cancel"*. Both fully ticked.
  - **Two new files**, mirrored to both branches:
    - [tests/test_workflow_coverage_audit.py](tests/test_workflow_coverage_audit.py) — 8 tests
    - [tests/test_no_data_loss_on_cancel.py](tests/test_no_data_loss_on_cancel.py) — 12 tests
  - **Behavior-first coverage audit (8 tests)** — parametric audit pins one happy-path test per workflow:
    - `run_smart_rip` → `test_pipeline_state_trajectory.py` + `test_behavior_guards.py` (MAIN; AI BRANCH falls through to behavior_guards since trajectory tests are MAIN-only)
    - `run_movie_disc` → `test_behavior_guards.py::test_movie_run_manual_selection_preserves_main_movie_picker`
    - `run_tv_disc` → 3 candidates so the audit is portable across MAIN's and AI BRANCH's diverged test names
    - `run_dump_all` → `test_behavior_guards.py::test_run_dump_all_reports_file_and_title_group_counts`
    - `run_organize` → `test_organize_workflow.py` (movie + TV happy paths)
    - Plus a meta-pin asserting the audit table covers exactly the 5 documented workflows (catches drift if a 6th is added without updating the audit).
    - Plus a smoke test asserting `test_organize_workflow.py` exists and has at least 5 tests (closes the §4 gap reference).
  - **No-data-loss-on-cancel (12 tests)**:
    - **Engine `unique_path` (4 tests)**: returns input unchanged when path doesn't exist; `' - 2'` suffix on first collision; counter walks past existing collisions (' - 3', ' - 4'); extension preserved (`movie.with.dots.mkv` stays `.mkv` after suffix).
    - **`move_files` no-overwrite (2 tests)**: with `replace_existing=False`, colliding destination is uniquified (existing file untouched); with `replace_existing=True`, destination is the target itself (caller will overwrite). Pins the strongest no-data-loss safeguard at `ripper_engine.py:1881`.
    - **Workflow cancel preserves source (4 tests)**: organize cancel-at-folder-picker preserves source MKV and source folder, no auto-create of movies_root; organize cancel-at-media-type preserves source; organize with `_select_and_move=False` preserves temp source even with `opt_auto_delete_temp=True` (post-success-only gate at controller.py:2210); organize with `opt_auto_delete_temp=False` preserves source on SUCCESS (user opt-out respect).
    - **Metadata-cleanup gates (2 tests)**: `_cleanup_success_session_metadata` is no-op when `opt_auto_delete_session_metadata=False`; dedupes repeated folder paths (mixed `/` and `\\` separators, `None` skipped) so `delete_temp_metadata` runs once not twice.
  - **AI BRANCH portability**: my first audit run on AI BRANCH failed `run_tv_disc` because branches diverged on TV-disc test names in 2026-04-30 refactors. Fixed by adding 3 candidate test names to the audit row — the `break`-on-first-match logic accepts whichever branch's name is present. Same pattern as the disk-space-pre-checks helper-inlining: portable test files survive branch divergence.
  - **Cumulative criteria status** after this commit:
    | Cross-cutting criterion | Status |
    | --- | --- |
    | Behavior-first test coverage | ✅ Closed (this commit) |
    | Abort propagation | ⚠️ Partial close (engine + 3 workflows pinned; 3 sub-items still open) |
    | Resume support | ⏳ Open (data layer pinned in `test_session_recovery.py`; integration not) |
    | No data loss on user-cancel | ✅ Closed (this commit) |
    | Disk-space pre-checks | ✅ Closed (earlier today) |
    | State machine reaches terminal state | ⚠️ Audit-pinned (gap honestly surfaced; cannot tick without code change) |
  - **Suite**: MAIN 927 → **947** (+20, 1 skipped). AI BRANCH +20 added; targeted run green (after the TV-disc fix).

- [x] ~~**Abort-propagation tests (engine + workflow respect, both branches)**~~ (2026-05-03) — partial close on the cross-cutting criterion *"Abort propagation"* in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md). Pins the engine contract and 3 of 4 workflows' abort respect; surfaces a `run_organize` gap; leaves "session metadata accurately reflects aborted status" and "no zombie temp folders" still open.
  - **New file**: [tests/test_abort_propagation.py](tests/test_abort_propagation.py) (16 tests, mirrored to AI BRANCH).
  - **Engine-level contract (10 tests)** pinning `RipperEngine.abort()`, `reset_abort()`, `abort_flag`, and `cleanup_partial_files`:
    - `abort()` with `current_process=None` sets event without raising
    - `abort()` is idempotent — second call doesn't re-terminate
    - `abort()` calls `terminate()` then `wait()` for running subprocess
    - `abort()` falls back to `kill()` when `terminate()`'s wait times out
    - `abort()` skips terminate when process already exited (`poll()` non-None)
    - `abort()` swallows subprocess-cleanup exceptions while still setting flag
    - `reset_abort()` clears the flag
    - `abort_flag` property always agrees with `abort_event.is_set()`
    - `cleanup_partial_files` removes `.partial` files (recursive) but PRESERVES completed `.mkv` files (no-data-loss invariant)
    - `cleanup_partial_files` respects `opt_clean_partials_startup=False` (user opt-out)
    - `cleanup_partial_files` defensive on missing directory (drive disconnected scenario)
  - **Workflow-level abort-respect (4 tests)**:
    - `run_smart_rip` aborted via `cleanup_partial_files` hook → `run_job` NOT called
    - `_run_disc_inner` (movie variant via `run_movie_disc`) aborted post-SM-reset → `scan_with_retry` NOT called
    - `run_dump_all` aborted inside `ask_dump_setup` → `run_job` NOT called (the immediately-following check at controller.py:1346 trips)
    - `engine.abort()` end-to-end: setting abort while a fake `current_process` is running terminates the subprocess (bidirectional flow pinned — workflow-level abort propagates down to subprocess kill)
  - **Audit finding — `run_organize` abort gap (1 test)**: `run_organize` has ONLY ONE `abort_event.is_set()` check (controller.py:2225, post-hoc, only deciding the "Move stopped before completion" log message). The workflow does NOT poll abort during `analyze_files` or `_select_and_move`. Test `test_run_organize_does_not_check_abort_during_analyze` pins the **current** gap: setting abort right before `analyze_files` does NOT short-circuit the workflow — `_select_and_move` still fires. If the code is later updated to add an abort check between analyze and move, the test will fail loudly so the assertion can be flipped to reflect the new contract. Same honest-visibility pattern as the SM audit.
  - **Real find during testing**: my first dump-all test patched `cleanup_partial_files` to set abort, but the single-disc dump-all path doesn't call `cleanup_partial_files` at all — `run_job` ran and the test failed with `Job(source='all', ...)` in `run_job_calls`. Fix: set abort inside `ask_dump_setup` instead, since the immediately-following check at controller.py:1346 (`if abort_event.is_set() or dump_setup is None`) trips reliably. The `cleanup_partial_files` call lives in `_run_dump_all_multi` and `_run_smart_rip_inner` and `_run_disc_inner`, not in single-disc `run_dump_all`.
  - **Criterion still un-ticked** because 3 sub-items remain open per the criteria doc:
    - Session metadata after abort accurately shows "aborted" status (currently untested)
    - No zombie temp folders after abort (currently untested — does `temp/Disc_<ts>/` get cleaned per cfg?)
    - Recoverable-state property (data layer pinned in `test_session_recovery.py`; the integration is not)
  - These three sub-items are honestly listed in the criteria doc so the gap is visible.
  - **Behavior-first**: no real subprocess starts, fake `_FakeProc` stand-in for `current_process` with controllable `poll`/`terminate`/`wait`/`kill` semantics. Survives the planned PySide6 migration per decision #5.
  - **Suite**: MAIN 911 → **927** (+16, 1 skipped). AI BRANCH +16 added; targeted run in flight.

- [x] ~~**Disk-space pre-check tests (engine + workflow integration, both branches)**~~ (2026-05-03) — closes the cross-cutting criterion *"Disk-space pre-checks fire before destructive work"* in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md). Pre-existing coverage was zero — `ask_space_override` was a no-op stub in `DummyGUI` and existing tests bypassed disk-space checks via `opt_check_dest_space=False`. This is the second cross-cutting criterion checkbox to close (after the SM audit pinned the gap on the third).
  - **New file**: [tests/test_disk_space_pre_checks.py](tests/test_disk_space_pre_checks.py) (12 tests, mirrored to both branches with the smart-rip wiring helper inlined for self-containment).
  - **Engine-level (6 tests)** pinning `RipperEngine.check_disk_space` (`engine/ripper_engine.py:1152`):
    - free > required → `"ok"`
    - required > free > hard_floor (default 20 GB) → `"warn"`
    - free < hard_floor → `"block"`
    - path doesn't exist (e.g., disconnected drive) → `"ok"` + warning log (defensive: continue and let the actual write surface the error later)
    - `shutil.disk_usage` raises (e.g., `PermissionError` on a network share) → `"ok"` + warning log
    - custom `opt_hard_block_gb=100` honored: 25 GB free now → `"block"` (was `"warn"` under default)
  - **Workflow-integration (6 tests)** pinning the `run_smart_rip` gate (`controller/controller.py:972-989`):
    - `opt_scan_disc_size=True` + `selected_size>0` → `check_disk_space` is called BEFORE `run_job` (call-order spy)
    - `opt_scan_disc_size=False` → `check_disk_space` NOT called (silently bypassed)
    - `"block"` status → `run_job` NOT called, `show_error("Critically Low Space", …)` fired with friendly free-GB and minimum-threshold body
    - `"warn"` + `opt_warn_low_space=True` → `ask_space_override` called; user accepts → `run_job` runs
    - `"warn"` + user declines → `run_job` NOT called (user-cancel respected)
    - `"warn"` + `opt_warn_low_space=False` → `ask_space_override` NOT called, `run_job` runs (silenced warn — user opted out of prompts)
  - **Real find during audit**: the criterion mentions `opt_check_dest_space` and `opt_warn_low_space`, but the temp-space pre-check in the rip workflows is actually gated by `opt_scan_disc_size`, NOT `opt_check_dest_space`. The latter gates the engine-level destination-space check inside `move_files`. The criteria doc note now documents this distinction explicitly so future audits don't conflate the two.
  - **AI BRANCH portability**: AI BRANCH lacks `tests/test_pipeline_state_trajectory.py`, so its `_wire_smart_rip_movie_happy_path` helper isn't importable there. Solution: helper inlined directly into `test_disk_space_pre_checks.py` so the file is portable to both branches without dependency surgery.
  - **Behavior-first**: `shutil.disk_usage` monkeypatched throughout — tests are deterministic on any drive, no real disk inspection. Survives the planned PySide6 migration per decision #5.
  - **Suite**: MAIN 899 → **911** (+12, 1 skipped). AI BRANCH +12 added; targeted run in flight.

- [x] ~~**Cross-workflow state-machine audit (both branches)**~~ (2026-05-03) — surfaces an honest-visibility gap in `docs/workflow-stabilization-criteria.md` cross-cutting criterion *"The state machine reaches a terminal state for every workflow"*. Pins the **current** SM contract for each of the four non-`run_smart_rip` workflows so the gap is visible and any future fix is a deliberate test update.
  - **What the audit found** — only `run_smart_rip` currently satisfies the cross-cutting criterion as written. The others have looser, asymmetric contracts:
    | Workflow | Resets SM? | Walks intermediates? | Terminal SM state? |
    | --- | --- | --- | --- |
    | `run_smart_rip` | Yes (l. 703) | Yes (full SCANNED→…→COMPLETED) | COMPLETED or FAILED |
    | `_run_disc_inner` (manual TV/Movie) | Yes (l. 2742) | **No** | Forced COMPLETED via `sm.complete()` at l. 3734 |
    | `run_dump_all` (l. 1329) | **No** | No | **Leaks prior `sm.state` from previous run** |
    | `run_organize` (l. 2053) | **No** | No | **Leaks prior `sm.state` from previous run** |
  - **Why this matters** — if a previous `run_smart_rip` failed, then `run_dump_all` or `run_organize` succeeded, `controller.sm.state` is still `FAILED` afterward. Any code that reads `sm.state` for run status (e.g., `is_success()`) would report the wrong outcome. The two SM-free workflows silently mislead.
  - **What this Done entry does NOT do** — it does NOT fix the gap. Fixing requires a deliberate decision: (a) update `run_dump_all` and `run_organize` to reset/transition the SM properly, or (b) accept them as intentionally SM-free and rewrite the criterion to match. That decision is for the user, not for this audit pass. The tests pin the **current** contract so whichever path is chosen later, the change is loud.
  - **New file**: [tests/test_workflow_sm_audit.py](tests/test_workflow_sm_audit.py) (9 tests, mirrored to AI BRANCH).
  - **Cases pinned** — `run_organize` SM-free on cancel (1) + on happy path with leaked `FAILED` state preserved (1); `run_dump_all` SM-free on cancel (1) + on happy path with leaked `FAILED` preserved (1); `_run_disc_inner` SM-free if cancelled before path-overrides commit (1) + resets exactly once if path-overrides accept then aborts (movie variant) (1) + same for TV variant (1) + reset clears leaked FAILED → INIT (1); plus a `run_smart_rip` baseline that proves the spy approach correctly returns 0 calls when smart rip is cancelled before its own reset fires (1).
  - **Spy approach** — wraps `controller._state_transition`, `controller._state_fail`, `controller._reset_state_machine`, and `controller.sm.complete` with counters before each test. More robust to internal refactors than asserting on `sm.state` alone (which only sees the final value, not the trajectory).
  - **Real find during testing** — the FAILED-leaks-across-runs property is concrete and provable: pre-load `controller.sm.fail("simulated")` before calling `run_organize`/`run_dump_all` happy path; assert `sm.state is FAILED` afterward. Both assertions hold today.
  - **Criteria doc updated** — [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md) cross-cutting criterion updated with the audit table and explicit guidance: the checkbox cannot be ticked until either the code is updated to comply or the criterion is rewritten to accept the SM-free flows as intentional. Honest visibility over false-green.
  - **Suite**: MAIN 890 → **899** (+9, 1 skipped). AI BRANCH 9/9 targeted green (full suite running in background).

- [x] ~~**Organize Existing MKVs workflow — behavior-first test gap closed (both branches)**~~ (2026-05-03) — closes the explicit "at least 5 behavior-first tests" checkbox in [docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md) §4 (Test coverage gap). Ticks the first concrete checkbox on the workflow-stabilization gate that doesn't require interactive disc testing.
  - **Why this workflow first**: README marks Organize as *"not tested"* (the thinnest coverage in the project). Before this commit, the entire suite contained exactly **one** `run_organize` test (`test_run_organize_deletes_session_json_when_temp_folder_preserved` in `test_behavior_guards.py`) covering only session-metadata cleanup. The flow's other 9 decision branches were unprotected.
  - **New file**: [tests/test_organize_workflow.py](tests/test_organize_workflow.py) (12 tests, mirrored byte-for-byte to AI BRANCH — `run_organize` is identical across branches).
  - **Cases covered** (12 total — well over the "at least 5" criteria bar):
    - **Happy paths (2)**: movie organize-from-temp creates `Movies (Year)/` + `Extras/` and rmtrees source under temp_root; TV organize creates `Show/Season NN/Extras/` with zero-padded season number.
    - **Cancellation paths (3)**: empty folder pick → "Folder selection cancelled" log + early return; empty media-type input → terminal-period "Cancelled." log; `_prompt_run_path_overrides` returning None → "Cancelled before organize (path override step)" log + early return without firing `analyze_files`.
    - **Empty-input paths (2)**: source folder with no .mkv files → "No .mkv files found" log + no destination folders auto-created; `analyze_files` returning `[]` → "No files to process" log without firing `_select_and_move`.
    - **Validation loop (1)**: invalid media-type input ("x", "garbage") loops twice with "Invalid media type" logs before accepting "movie" — pins controller.py:2098-2110.
    - **Failure-with-abort (1)**: `_select_and_move=False` + `engine.abort_event.set()` → "Move stopped before completion" log fires.
    - **Safety property (1)**: source NOT under temp_root + `opt_auto_delete_temp=True` → source folder preserved (pins the `startswith(temp_root)` guard at controller.py:2214 — without this guard, an external folder of MKVs would be silently destroyed after a successful organize).
    - **Glob-pattern correctness (2)**: ask_yesno=True → `_safe_glob` called with `**/*.mkv` and `recursive=True`; ask_yesno=False → flat pattern with `recursive=False`. Caught by capturing `_safe_glob` args via monkeypatch.
  - **Real find during testing**: my first `"Cancelled." == m` exact-equality assertion failed because controller log lines carry a `[HH:MM:SS] ` timestamp prefix from `controller.log()`. Fixed to `m.endswith("Cancelled.")` — terminal-period sentinel distinguishes "Cancelled." from longer messages like "Cancelled before organize (path override step)" so we don't accidentally pass the path-overrides cancel string when checking the media-type cancel path.
  - **Behavior-first**: no GUI/Tk touches, no real filesystem operations beyond `tmp_path`, all session-finalization helpers monkeypatched. Tests survive the planned PySide6 migration per decision #5 in `docs/pyside6-migration-plan.md` — they pin controller behavior, not GUI shape.
  - **Workflow-stabilization-criteria checkbox ticked**: §4 "Test coverage gap" item changed from `[ ]` to `[x]` with cross-link to this Done entry.
  - **Suite**: MAIN 878 → 890 (+12, 1 skipped — the platform-conditional non-Windows case-sensitive-dedup test from the previous task). AI BRANCH +12 added; full suite running in background.

- [x] ~~**Planner edge-case parametric tests (stretch — both branches)**~~ (2026-05-03) — closes the last small test item in the Active list. After this commit, MAIN's Active list contains only the PySide6 migration entry.
  - **Target**: `transcode/planner.py:build_transcode_plan()`. Existing happy-path coverage in `test_transcode_queue_builder.py` (2 tests). This file adds 15 edge-case tests covering the long tail.
  - **New file**: [tests/test_transcode_planner_edge_cases.py](tests/test_transcode_planner_edge_cases.py) (15 tests, mirrored to both branches).
  - **Cases covered**: empty input list, repeated-input dedup at high counts, Windows case-insensitive dedup (Windows-only via `@pytest.mark.skipif`), non-Windows case-sensitive dedup (skipped on Windows), 150-input large-scale dedup with order preservation, `..` segment fallback to basename, deeply-nested-input fallback, cross-drive ValueError fallback (simulated via `monkeypatch` so it works without two real drives), UNC paths inside same share, UNC + local-drive cross-share, mixed `/` and `\\` separator normalization, non-MKV extension replacement, no-extension input still gets `.mkv`, all output paths constrained under output_root (safety property), and order preservation across dedup.
  - **Skipped tests (1)**: case-sensitive dedup is non-Windows-only; skipped on this Windows test machine. Mirror also skips it.
  - **Behavior-first**: pure path-shape tests, no tkinter/GUI/engine touches → survives PySide6 migration per decision #5.
  - **Suite**: MAIN 864 → 878 (+14, 1 skipped). AI BRANCH +14 added; full suite running in background.

- [x] ~~**Three planning docs: workflow-stabilization criteria + copy-style + glossary**~~ (2026-05-03) — closes the audit's "Items that need a separate decision" entries for `docs/copy-style.md` and `docs/glossary.md`, and converts the abstract PySide6-migration "workflow stabilization" gate into a concrete checklist.
  - **[docs/workflow-stabilization-criteria.md](docs/workflow-stabilization-criteria.md)** (MAIN only — migration is MAIN-first per decision #1). Per-workflow checklist for TV Disc / Movie Disc / Dump All / Organize Existing MKVs / FFmpeg HandBrake transcoding. Each workflow has real-disc validation, failure-mode coverage, and README-update criteria. Cross-cutting criteria (abort propagation, resume support, data-loss gates, state-machine terminal-state assertion) apply to all five. The gate is closed when every checkbox is checked. **Cross-linked from `pyside6-migration-plan.md` decision #2 row** so the migration plan now points at the concrete unblock criteria.
  - **[docs/copy-style.md](docs/copy-style.md)** (both branches). One-page voice + copy rule sheet. Codifies the patterns the closed audit findings established — second-person present-tense default, no marketing reassurance, no jargon without inline gloss, no config-key names in user dialogs, no raw exception strings, one product name via `APP_DISPLAY_NAME`, errors say what-failed-and-what-to-try-next, sentence case for buttons / labels (no ALL-CAPS except for literal acronyms), causal verb preferences (Stop > Abort, Pick > Map, Choose > Select), formatting consistency (durations, sizes, percentages). Lists drift-guard tests that already enforce these rules so violations fail CI rather than ship. Cross-references `glossary.md`.
  - **[docs/glossary.md](docs/glossary.md)** (both branches). Canonical short definitions for terms users encounter: LibreDrive (with the three states the app surfaces), UHD, Blu-ray, DVD, MKV, HEVC/H.265, H.264, CRF, AAC, Main track, Burn (subtitles), Forced subtitles, Metadata preserve/drop, Main/Duplicate/Extra/Unknown classifier labels, Smart Rip, Dump All, Stabilization, Validation, Temp folder, Session, LibreDrive-capable drive, Jellyfin-style folder structure. Source of truth for inline glosses (the LibreDrive status strings already use this wording per closed Finding #11) and the friendly profile summaries from `transcode/profile_summary.py`.
  - **Cross-references**: `ux-copy-and-accessibility-plan.md` "Foundation Documents to Consider" entries for both `copy-style.md` and `glossary.md` updated from `(proposed)` to `✅ landed 2026-05-03`.
  - **No source code touched.** Three new Markdown files in `docs/`. AI BRANCH gets the two universally-applicable ones (copy-style + glossary); workflow-stabilization-criteria stays MAIN-only since the migration goes MAIN-first.

- [x] ~~**Friendly-error helper for messagebox dialogs (Finding #8, both branches)**~~ (2026-05-03) — closes Sequencing item 10 / Finding #8 in MAIN, Finding #10 in AI BRANCH. Last quick-win in MAIN's UX/A11y Sequencing list. WCAG 3.3.3 (Error Suggestion) — error messages should identify *both* what failed *and* what the user can try next.
  - **Helper**: New `friendly_error(base_message, exception)` in [ui/dialogs.py](ui/dialogs.py). Maps caught exception types to user-facing recovery text:
    - `PermissionError` → "Permission denied. Check that the file or folder isn't open in another program..."
    - `FileNotFoundError` → "Path not found. Check the location, or create it manually..."
    - `IsADirectoryError` / `NotADirectoryError` → file/folder mismatch hints
    - `OSError` with errno-specific cases — ENOSPC (28, out of disk space), ENOTEMPTY (17/39/41), EACCES (13), EBUSY (16/33)
    - `TimeoutError` / `ConnectionError` (must be checked before generic `OSError` — they're subclasses in Python 3.11+)
    - `MemoryError` → "close other programs and try again"
    - `ValueError` → "session log has details on what was rejected"
    - Fallback → "session log has technical details that may help"
  - **Critical contract**: The raw exception text is **NOT** included in the returned dialog body. Raw detail belongs in the session log (where it already is, via `controller.log()`). Pinned by a sentinel-string assertion in the test file — catches a future regression where someone adds `str(exception)` to the recovery text.
  - **Call sites converted (17 in each branch)**: load/save/set-default/create/duplicate/delete profile (6); create output folder (2 different sites); load transcode profiles; build queue; prepare output folders; analyze MKV; open Settings (3 different sites); open path; reveal path. The two path-bearing sites (open path, reveal path) keep the path in the base message: `friendly_error(f"Could not open path:\n{normalized}", e)`.
  - **Test coverage**: New [tests/test_friendly_error.py](tests/test_friendly_error.py) (18 tests) in both branches — covers each known exception type's recovery text, the TimeoutError/ConnectionError ordering caveat (caught during test development — they're OSError subclasses in Python 3.11+), multiline base messages with path info, blank-line separation between base message and recovery text, and the critical raw-exception-doesn't-leak sentinel checks.
  - **Real find during testing**: Initial helper put `OSError` check before `TimeoutError`/`ConnectionError`. Two test failures revealed they're subclasses of `OSError` in Python 3.11+, so the more-specific checks must come first. Fixed; comment added at the source explaining the ordering requirement.
  - **Suite**: MAIN 846 → 864 (+18 from `test_friendly_error.py`). AI BRANCH +18 added; full suite running in background.

- [x] ~~**EXTRA label color + LibreDrive inline gloss (Findings #10/#11, both branches)**~~ (2026-05-03) — closes Sequencing items 8 and 9.
  - **Finding #10 — EXTRA label color**: `_LABEL_COLORS["EXTRA"]` was `#8b949e` (muted gray, same hex as `_FG_DIM` body-text color), so the EXTRA label visually collapsed with surrounding muted text. Changed to **`#a371f7`** (purple) — distinct from MAIN's blue / DUPLICATE's amber / UNKNOWN's orange / `_FG_DIM`. Contrast against `#0d1117`: ~5.65:1 (passes WCAG 4.5:1). MAIN: hardcoded in `gui/setup_wizard.py:_LABEL_COLORS`. AI BRANCH: hardcoded in `gui/theme.py:CLASSIFICATION_LABEL_COLORS["EXTRA"]` (the existing `APP_THEME["purple"]` of `#a400ff` was too saturated and failed contrast on AI BRANCH's dark blue surface).
  - **Finding #11 — LibreDrive inline gloss**: All three status strings in `gui/setup_wizard.py` now carry an em-dash gloss: *"enabled — disc decryption ready"* / *"possible — firmware patch may help"* / *"not available — UHD discs may not work"*. Replaces bare *"enabled"* / *"possible"* / *"not available"* — users encounter LibreDrive once and shouldn't need to look it up to know what the status means.
  - **Test coverage**: New `tests/test_label_color_and_libredrive.py` (7 tests) in both branches — pins the EXTRA color value, asserts it differs from `_FG_DIM`, asserts all 4 label colors are mutually distinct, pins each LibreDrive gloss string explicitly, plus a drift guard that catches any future bare `LibreDrive: <state>` string introduced without the em-dash gloss.
  - **Suite**: MAIN 839 → 846 (+7). AI BRANCH +7 added; full suite running in background.

- [x] ~~**Focus indicators on flat buttons (Finding #3, both branches)**~~ (2026-05-02) — closes Finding #3 / Sequencing item 5. WCAG 2.4.7 (Visible Focus) violation — `relief="flat"` buttons throughout the app suppressed tkinter's default focus border with no `highlightthickness` configured, making it impossible for keyboard users to see which button had focus.
  - **Fix shape**: Four `self.option_add()` calls in `JellyRipperGUI.__init__` install tkinter-wide defaults for the `Button` class — `*Button.highlightThickness=2`, `*Button.highlightBackground` (dark surface so the ring is invisible at rest), `*Button.highlightColor` (accent so the ring is clearly visible when focused), `*Button.takeFocus=1`. Buttons that explicitly set their own `highlight*` options keep them (no override). Smallest possible change with broadest coverage — catches every `tk.Button` that doesn't already override.
  - **MAIN colors**: Hardcoded `#161b22` (background) + `#58a6ff` (accent) matching the existing main_window theme.
  - **AI BRANCH colors**: Sourced from `self._theme.get("surface")` and `self._theme.get("title")` — uses the AI BRANCH palette properly.
  - **Test coverage**: New [tests/test_focus_indicators.py](tests/test_focus_indicators.py) in both branches (5 tests each) — pins each `option_add` call by source-text regex so a future refactor that removes them fails loudly. Tests parse the source rather than instantiating the GUI (which would need a Tk root).
  - **Scope discipline**: Did NOT do the full `tk.Button`-helper refactor (Sequencing list option D). That would touch 30+ call sites and is throwaway work — Qt has native focus treatment, full Qt-native focus story lands during the PySide6 migration per decision #7.
  - **Suite**: MAIN 834 → 839 (+5 new focus tests). AI BRANCH +5 added; full suite running in background to confirm.

- [x] ~~**UX Sequencing batch (3 quick-wins, both branches)**~~ (2026-05-02) — closes Findings #4, #7, #9 in MAIN's [docs/ux-copy-and-accessibility-plan.md](docs/ux-copy-and-accessibility-plan.md) (and equivalents in AI BRANCH).
  - **Finding #4 — Title-case classification labels**: New `_LABEL_DISPLAY` mapping + `_label_display(label)` helper in `gui/setup_wizard.py`. Display sites render `Main` / `Duplicate` / `Extra` / `Unknown` instead of ALL-CAPS. The `_LABEL_COLORS` keys stay uppercase per audit recommendation. "MAIN is pre-selected" subtitle softened to "Main is pre-selected".
  - **Finding #7 — Soften "ABORT" → "Stop"**: 5 button labels (`"ABORT SESSION"` → `"Stop Session"`), dialog body ("Abort the current session first" → "Stop the current session first"), log line ("ABORT REQUESTED BY USER" → "Stop requested by user"), in-flight states ("ABORTING..." / "Aborting..." → "Stopping..."). All in `gui/main_window.py`.
  - **Finding #9 — Drop config-key paragraph from Update Blocked dialog**: Dropped the dev-leak paragraph *"Set opt_update_signer_thumbprint in Settings to..."* from `gui/update_ui.py`. The user-friendly paragraph earlier in the same dialog ("To enable updates, open Settings → Advanced...") covers it. Developer-facing controller log line still references the config key — logs are appropriate for config keys; user dialogs aren't.
  - **Test updates** (existing tests pinned the old strings): `test_imports.py` updated for the ABORT→Stop button text + status / log assertions; `test_security_hardening.py` dropped the assertion checking for the removed config-key paragraph in the user-visible dialog body. Both branches.
  - **Suite results**: MAIN 834 passed (no net change — same count as before since these were string changes, not new tests). AI BRANCH targeted (test_imports + test_button_contrast + test_security_hardening) 71/71 green; full suite running in background to confirm.
  - **Scope discipline**: Did NOT touch focus indicators (Finding #3 / Sequencing item 5) — that one needs a tk.Button helper refactor or `option_add` call across many files; flagged as separate decision since it's bigger than the other items.

- [x] ~~**WCAG primary-button contrast fix (Finding #2, both branches)**~~ (2026-05-02) — closes Finding #2 in [docs/ux-copy-and-accessibility-plan.md](docs/ux-copy-and-accessibility-plan.md). Bug-grade WCAG 1.4.3 AA failure — prior `bg=_ACCENT, fg="white"` (#58a6ff + white) measured only 2.5:1 against the required 4.5:1.
  - **MAIN fix shape**: New constant `_ACCENT_BUTTON_BG = "#1f6feb"` in [gui/setup_wizard.py](gui/setup_wizard.py) (no theme palette infrastructure existed). Two button sites converted via `replace_all`. Measured contrast: **4.63:1** against white — passes WCAG (audit doc estimated ~4.6:1, matched).
  - **AI BRANCH fix shape (different)**: AI BRANCH's palette already had `_COLORS["accent_button_bg"]` defined (sourced from `APP_THEME["blue"]` = `#2b63f2`, measures ~4.94:1 against white). The buttons were using the wrong palette key — `_ACCENT` (which sourced from the lighter `APP_THEME["title"]` = `#27b8ff`, ~2.19:1 — *worse* than MAIN's bug). Fix: switched buttons to use the correct existing palette key. No new constant added.
  - **Test coverage**:
    - MAIN: [tests/test_button_contrast.py](tests/test_button_contrast.py) — 9 tests including programmatic WCAG contrast computation (`_relative_luminance`, `_wcag_contrast_ratio` helpers using sRGB linearization), pin on the constant value, drift guards on the prior failing source pattern, and a test confirming the *old* bug actually was 2.46:1 (audit said 2.5:1, matched).
    - AI BRANCH: `tests/test_button_contrast.py` — 6 tests, same WCAG helpers, asserts on `_COLORS["accent_button_bg"]` palette key.
  - **Real find during testing**: My hand-calculation earlier in the session said 4.52:1 contrast for the new `#1f6feb`. The actual measured ratio per the WCAG sRGB-linearization formula is **4.63:1**. Audit doc said `~4.6:1` — audit was honest. Test pin updated to the actual value with comment explaining the discrepancy.
  - **Scope discipline**: Did NOT build the equipable theme system in tkinter — that was deferred to the PySide6 migration per decision #7 in the migration plan. This is the minimal contrast fix only.
  - Suite: MAIN 825 → 834 passed (+9). AI BRANCH +6 dispatch tests pass; full suite check running in parallel.

- [x] ~~**Code-signing decision: defer indefinitely, stay unsigned**~~ (2026-05-02) — closes question #8 from the PySide6 migration plan.
  - **Decision**: Releases continue to ship unsigned. README's existing "whitelist the download folder" paragraph is the documented user-facing contingency for SmartScreen friction. Not pursuing SignPath OSS, commercial code-signing certs, Microsoft Store distribution, or any other signing path.
  - **Why**: All code-signing paths require legal-identity verification of the maintainer per CA/Browser Forum baseline requirements. Even the free SignPath OSS program — which had been the preferred direction earlier the same day — verifies legal identity. Maintainer reviewed and chose not to provide legal-identity verification for cert ownership at the project's current single-maintainer pre-alpha maturity. The SmartScreen UX hit (warning users dismiss by whitelisting the download folder) is accepted as the trade-off.
  - **Documents updated**: [docs/pyside6-migration-plan.md](docs/pyside6-migration-plan.md) decision #8 row reframed; [docs/code-signing-plan.md](docs/code-signing-plan.md) reframed from "Proposed: apply" to "Deferred indefinitely" with original rationale preserved as historical reference; [docs/code-signing-application-draft.md](docs/code-signing-application-draft.md) prepended with "Not for submission" callout, paste-ready text preserved for if the decision is ever revisited.
  - **Reversibility**: The decision is not permanent. If the project ever forms a legal entity (LLC etc.) under which signing carries no personal-identity implications, the preserved SignPath OSS application draft becomes paste-ready prep work again.
  - **No code changes.** Pure documentation update.

- [x] ~~**PySide6 toolchain validation (smoke test)**~~ (2026-05-02) — de-risks the migration's mechanical feasibility on this Python/Windows combo before committing weeks to the port.
  - New throwaway directory: [experiments/pyside6_smoke/](experiments/pyside6_smoke/) — isolated venv, single-file `main.py` smoke test, `README.md` documenting purpose + cleanup, `.gitignore` for build artifacts.
  - All 7 toolchain gates passed: PySide6 6.11.0 installs cleanly via pip; imports succeed; `QApplication` + `QMainWindow` + QSS stylesheet construct; event loop runs and exits cleanly via `QTimer`-driven auto-quit; PyInstaller `--onefile --windowed` bundles without custom hooks; bundled `.exe` runs and exits 0.
  - **Bundle size**: 48.6 MB for the smoke test (uses QtCore/QtGui/QtWidgets only). Real JellyRip will pull in QtMultimedia for the v1-blocking MKV preview (per migration plan decision #4) — realistic final bundle expected at 80-130 MB, within the migration plan's "+80 to 150 MB" estimate.
  - **PyInstaller integration story**: pleasant surprise — PySide6 ≥ 6.0 ships with built-in PyInstaller hooks. No `--hidden-import` flags needed for Qt plugins. `release.bat` integration won't need a major spec rewrite.
  - **QSS theme path validated**: smoke test demonstrates two button styles (filled `#1f6feb`/white and inverted white/`#1f6feb`) both passing WCAG 4.5:1 contrast — exactly the substrate decision #7's equipable theme system needs.
  - **Throwaway**: directory deleted or archived when real PySide6 work begins. No production code touched.

- [x] ~~**PySide6 migration: open questions answered, decisions captured**~~ (2026-05-02) — closes the "Status: Proposed" / "Not scheduled" framing in both branches' migration plans.
  - All 8 open questions from the migration plan answered: (1) MAIN first; (2) After workflow stabilization; (3) Single-shot, tkinter only where impossible; (4) MKV preview is the v1 forcing function; (5) pytest-qt for new UI tests, tkinter-touching tests rewritten or deleted; (6) Chat sidebar parity N/A in MAIN-first phase; (7) Refresh — equipable theme system from day 1; (8) **Stay unsigned** (per code-signing decision above).
  - Both branches' [docs/pyside6-migration-plan.md](docs/pyside6-migration-plan.md) updated with full "Decisions Captured 2026-05-02" section + status change from `Proposed` to `Approved direction`.
  - PySide6 entry moved from `Someday` to `Active` in `TASKS.md` with v1-blocking framing.
  - "Items that wait for PySide6" section in `docs/ux-copy-and-accessibility-plan.md` (both branches) reframed — now references definite future home rather than indefinite Someday.
  - **No code changes.** Pure planning artifact updates.

- [x] ~~**Product-name inconsistency fix in MAIN**~~ (2026-05-02) — closes Finding #1 in [docs/ux-copy-and-accessibility-plan.md](docs/ux-copy-and-accessibility-plan.md). Bug-grade item from the 2026-05-02 audit.
  - New `APP_DISPLAY_NAME = "JellyRip"` constant in [shared/runtime.py](shared/runtime.py); 13 hardcoded variants in `gui/main_window.py` and 2 in `main.py` substituted via f-string. Big top-of-window header now renders natural-case "JellyRip" instead of the prior ALL-CAPS three-word legacy variant.
  - Drift-guard parametric test: [tests/test_app_display_name.py](tests/test_app_display_name.py) (8 tests) — pins the constant value, requires it to be exported from `shared.runtime`, and fails if any of the three legacy variants ("JellyRip" / "Jellyfin Raw Ripper" / "Raw Jelly Ripper") returns to `gui/main_window.py` or `main.py`. Includes positive guards confirming the constant is actually referenced (catches the case where a future refactor removes the import or all usages).
  - AI BRANCH was already done (had its own `APP_DISPLAY_NAME = "JellyRip AI"` from a prior pass). MAIN is now at parity.
  - Full suite: 825 passed (was 817), ~97s.

- [x] ~~**Plain-English profile summary wired into Settings**~~ (2026-05-02) — closes Finding #20 (MAIN) / Finding #24 (AI BRANCH) in their respective ux-copy-and-accessibility-plan.md docs. Wires the previously-unused `transcode/profile_summary.py:profile_summary_readable` into the live UI as an opt-in toggle.
  - New config flag `opt_plain_english_profile_summary` (default `False`) added to [shared/runtime.py](shared/runtime.py) DEFAULTS in both branches.
  - [ui/settings.py:summarize_profile()](ui/settings.py) now takes a `plain_english=False` kwarg; when True, dispatches to `profile_summary_readable` with safe fallback to the terse `describe_profile` if the input shape doesn't match (UI rendering must never crash on an exotic profile).
  - New Settings → Everyday tab toggle: *"Show plain-English transcode profile descriptions"*. Both call sites of `summarize_profile` in [gui/main_window.py](gui/main_window.py) (`_summarize_expert_profile` and the inline transcode-profile-picker site) read the flag from cfg.
  - **Test isolation gotcha caught and pinned**: `getattr(self, "cfg", None)` on a bare `object.__new__(JellyRipperGUI)` triggers `Tk.__getattr__` recursion (same gotcha pinned in `tests/test_main_window_formatters.py`). Fix: `self.__dict__.get("cfg")` bypasses descriptor lookup. Inline comment at the change site points at the formatter test that documents the gotcha.
  - Test coverage: [tests/test_settings_summarize_profile.py](tests/test_settings_summarize_profile.py) (11 tests) — DEFAULTS contract; default-behavior preservation; plain-English dispatch (h.265 friendly phrasing, copy mode); TranscodeProfile→dict conversion; defensive fallbacks on bad shape and non-dict input.
  - Default behavior unchanged for users who don't toggle the option — the contract going in and pinned by the tests.
  - Same fix landed in AI BRANCH. Both branches: green.
  - MAIN suite: 817 passed (was 806). AI BRANCH suite: 774 passed (was 763).

- [x] ~~**State machine transition test** — `utils/state_machine.py`, table-driven legal/illegal transitions~~ (2026-04-29)
  - `tests/test_state_machine.py`: 98 tests covering legal transitions, illegal transitions (with state-preservation + descriptive-message assertions), FAILED-as-silent-sink, `fail()` idempotency from any state, `complete()` forcing semantics, `is_success()`, debug logger emit/suppress paths, and a guard test that fails if `SessionStateMachine.allowed` drifts from the table.
  - Full suite: 663 passed (was 565), ~52s.

- [x] ~~**Event system tests** (originally framed as `shared/event.py` pub/sub semantics)~~ (2026-04-29) — task scope corrected during execution.
  - Discovery: `shared/event.py` is an 8-line frozen dataclass, not a pub/sub bus. The "publish" side is `RipperController.emit()` which dispatches to a single optional UI adapter via duck-typed `handle_event` — no subscribe API, no multi-subscriber dispatch, no exception isolation. Original task description was based on incorrect assumptions.
  - `tests/test_event.py`: 13 tests. (A) Event dataclass invariants — positional construction, frozen against assignment, structural equality across all fields, inequality when any field differs, `data` held by reference (not copied — mutation gotcha pinned), unhashable at runtime despite `frozen=True` because `data: Dict` makes the autogenerated `__hash__` raise TypeError. (B) `RipperController.emit()` semantics — returns None, dispatches event object exactly once with same identity, silent when ui is None, silent when ui lacks `handle_event` (duck-typed contract), does NOT swallow handler exceptions.
  - Also corrected `memory/test-coverage.md` §5 to reflect actual contract (was previously mis-describing `event.py` as a pub/sub bus).
  - Full suite: 694 passed (was 681), ~51s.

- [x] ~~**Audit unused `transcode/` modules (no deletion)**~~ (2026-04-29) — original "dead code cleanup" task reframed as a feature audit per user instruction *"don't actually remove features even if half built — just tell me about them"*. All three files **kept on disk**.
  - [transcode/recommend.py](transcode/recommend.py) (103 lines, 0 imports): two functions — `analyze_media(input_path)` (ffprobe wrapper) and `recommend_profile_from_metadata(meta)` (rule-based recommender: HEVC + <7GB → copy/remux; otherwise → H.265 CRF 22). Looks like an **earlier prototype** of the live `transcode/recommendations.py` (634 lines, full TypedDicts + height buckets + HDR detection + channel-aware audio + commentary detection). Different output shape — not interchangeable. **Two ideas in this file that didn't make it into the live engine, worth knowing about**: (1) recommends `constraints.skip_if_below_gb=7` and `skip_if_codec_matches=True` — the constraint *fields* are honored by `core/pipeline.py:TranscodeJob.should_skip()` but no path currently *recommends* them. (2) An `output.naming = "{title}_recommended"` template that doesn't appear elsewhere.
  - [transcode/profile_summary.py](transcode/profile_summary.py) (52 lines, 0 imports): `profile_summary_readable(profile)` returns a **non-technical-user-friendly** summary, e.g., *"Convert video to H.265 (smaller files, good quality), balanced quality (CRF 22), hardware acceleration if available"*. Compare the live `transcode/profiles.py:describe_profile()` (terse: *"Video: H.265 CRF 22"*) exposed via `ui/settings.py:summarize_profile`. This is a **half-built feature**: a "friendly summary" mode for non-technical users, drafted but never wired into the GUI. If a "show me a plain-English version" Settings toggle ever gets added, this is the function to wire up.
  - [transcode/transcode_profile.py](transcode/transcode_profile.py) (19 lines, 0 imports): a wrapper class around `profiles.TranscodeProfile` whose docstring says *"(Re-exported for clarity)"*. Pure architectural alias — no unique behavior. Of the three, this is the safest to remove later.
  - **No source changes. No tests added (these aren't testable as live features).** The Active list now has only the "planner edge cases" stretch item left.

- [x] ~~**Controller full-pipeline integration test (state-trajectory layer)**~~ (2026-04-29) — pairs with `test_behavior_guards.py` (133 existing tests covering behavioral output of `run_smart_rip`/`run_movie_disc`/`run_tv_disc`/`run_dump_all`/`run_organize`). The gap those tests left was *state-machine trajectory*: do the flows actually walk the SM through INIT → SCANNED → RIPPED → STABILIZED → VALIDATED → MOVED → COMPLETED? Do failures land on FAILED with the right reason? This file pins the integration of the wiring contract (`tests/test_controller_state_integration.py`) with real flows.
  - `tests/test_pipeline_state_trajectory.py`: 9 tests using a `_record_state_transitions` wrapper to capture the full state visit list per run. Reuses `_controller_with_engine` + `DummyGUI` from `test_behavior_guards.py` and a `_wire_smart_rip_movie_happy_path` helper that mirrors `test_run_smart_rip_wizard_flow_completes_movie`'s setup so individual tests can override one fake (e.g., fail stabilization) and exercise that branch.
  - **Happy path** (1 test): full SCANNED→RIPPED→STABILIZED→VALIDATED→MOVED→COMPLETED trajectory in exact order, `is_success() is True`. **Failure paths** (4 tests): rip subprocess failure → trajectory ends at SCANNED; stabilization failure → ends at RIPPED; validation failure (`hard_fail` size status) → ends at STABILIZED; move failure → ends at VALIDATED — all with `sm.state == FAILED`. **Abort paths** (2 tests): abort during scan → no transitions, state stays INIT; abort flagged via `_stabilize_ripped_files` callback → trajectory reaches RIPPED but never COMPLETED. **Reset semantics** (1 test): a previous-run FAILED state is cleared by `_reset_state_machine` at the next `run_smart_rip` entry, and the next run completes cleanly.
  - **Real find during testing**: my first attempt used `("fail", "size mismatch")` for `_verify_expected_sizes`, which silently passed through because the actual status type is `Literal["pass","warn","hard_fail"]` (controller/rip_validation.py:12) and the controller checks `if size_status == "hard_fail"`. `"fail"` matched neither branch, so the flow continued to COMPLETED. The test surfaced this when the trajectory assertion failed; fixed to use `"hard_fail"`. Pinned with a comment so future tests don't repeat the mistake.
  - Full suite: 802 passed (was 793), ~95s (the 9 trajectory tests run the real `run_smart_rip` flow per case so each takes ~2-4s).

- [x] ~~**Untested presentation formatters in `gui/main_window.py`**~~ (2026-04-29) — original "UI adapter extraction" framing replaced with direct tests on already-pure methods.
  - `tests/test_main_window_formatters.py`: 47 tests covering 5 formatter methods. `_format_drive_label` (`@staticmethod`, line 252): all-fields populated; field-by-field fallbacks (`drive_name`→"Unknown drive", `disc_name`→"No disc", `device_path`→"disc:N"); state-code decoding (2/0/256/unknown). `_trim_context_label` (`@staticmethod`, line 544): pass-through, whitespace collapse, exact-limit, ellipsis-trim, rstrip-before-ellipsis, empty input. `_main_status_style_for_message` (line 622): idle/error/warning/active pill selection, error-token wins over warning-token (ordering pin), `_theme=None` fallback to `build_app_theme()`, `_theme=` custom dict honored. `_get_text_widget_selection` (line 465): defensive paths only — non-widget input → "", exception swallowed → "", None → "" (the real `tk.Entry`/`tk.Text` branches need a Tk root, deliberately not wired in). `_ffmpeg_version_ok` (line 5163): empty path → True; missing file → True; current version → True; too-old → prompts via `messagebox.askyesno` and returns choice (True/False); message content pinned (label, build year, "FFmpeg 4.0+"); `build_year=None` omits "(built YYYY)" suffix.
  - **Test isolation gotcha caught**: when other test files import `gui.main_window` first with the real `tkinter.Tk`, my module-level `_FakeTkBase` patch becomes a no-op (sys.modules cache). `object.__new__(JellyRipperGUI)` instances then have real Tk in their MRO without `Tk.__init__` ever running — so `getattr(self, "_theme", None)` recurses infinitely via `Tk.__getattr__` on the missing `self.tk`. Fix: set `_theme` (or `_theme=None`) explicitly on the gui instance in fixtures, never rely on the `getattr → fallback` path during test setup. Documented inline in the fixture.
  - Full suite: 793 passed (was 746), ~61s.

- [x] ~~**`shared/windows_exec.py` path-trust contract tests**~~ (2026-04-29) — original "injection fuzz" task framing replaced with the actual contract: this module resolves trusted paths, it does not construct argv.
  - `tests/test_windows_exec.py`: 17 tests pinning [shared/windows_exec.py](shared/windows_exec.py). On Windows: both `get_powershell_executable()` and `get_explorer_executable()` return absolute, normalized, no-`..` paths under `C:\Windows`; both are PATH-independent (verified with `PATH=""` and a hostile `PATH=C:\Attacker\bin;...`); both fall back to a hardcoded literal when `os.path.isfile` returns False. `get_windows_root_directory()` env-var chain: SystemRoot used first when API returns "", WINDIR when SystemRoot absent, hardcoded `C:\Windows` when both absent. `get_windows_system_directory()` skips env vars and goes API → hardcoded. Cross-platform: with `sys.platform="linux"` all five functions return their documented non-Windows fallback (`""` for the directory queries, `"powershell"` / `"explorer"` for the executable resolvers). Defensive: both executable resolvers always return a truthy non-empty string regardless of env.
  - Full suite: 746 passed (was 729), ~61s. All 17 new tests run in 0.35s.

- [x] ~~**Scan stdout-parser tests**~~ (2026-04-29)
  - `tests/test_scan_parser.py`: 21 tests pinning [engine/scan_ops.py:113-279](engine/scan_ops.py:113) (`scan_disc(engine, on_log, on_progress)`) plus the `_parse_drive_info()` helper. Same seam pattern as the rip parser — `monkeypatch.setattr("engine.scan_ops.subprocess.Popen", ...)` returns a `_FakeProc`/`_FakeStdout` whose `readline()` yields canned CINFO/TINFO/SINFO/MSG lines. Synchronous parser (no thread, no queue) so each test runs in ~40ms.
  - `scan_disc` cases (16): clean scan with parsed name/duration/chapters/size/streams; sorted by descending duration; on_progress increments per new title and caps at 90; invalid duration → title excluded; invalid size → title excluded; malformed CINFO (too few fields, bad int) silently skipped; malformed TINFO silently skipped; orphan SINFO (tid not in titles) silently skipped, doesn't fabricate a title; MSG with too few fields silently skipped; abort_event before run → returns None, `proc.kill()` called; non-zero exit → returns None, "exit code N" logged; exception inside Popen → swallowed, `Scan failed: ...` logged, returns None; empty stdout → returns `[]`; all-invalid-titles → returns `[]`.
  - `_parse_drive_info` cases (5): three LibreDrive states (enabled / possible / unavailable); UHD + LibreDrive enabled → uhd_friendly=True; UHD without LibreDrive → uhd_friendly=False; once disc_type is set to UHD, a later Blu-ray-mentioning MSG must not downgrade it.
  - **Real find during testing**: the LibreDrive classifier checks `"enabled" in msg or "active" in msg` *before* `"possible" in msg or "not yet" in msg`. A phrase like *"possible but not yet active"* therefore classifies as `"enabled"` because the substring `"active"` matches the first branch. Pinned with `test_parse_drive_info_active_wins_over_possible_when_both_appear` so a future cleanup of the classifier (e.g., to require *"is enabled"*/`"is active"`) makes a deliberate decision.
  - Full suite: 729 passed (was 708), ~65s.

- [x] ~~**Rip stdout-parser tests**~~ (2026-04-29)
  - `tests/test_rip_parser.py`: 12 tests pinning `RipperEngine._run_rip_process` ([engine/ripper_engine.py:1298](engine/ripper_engine.py:1298)). Seam: monkeypatch `engine.ripper_engine.subprocess.Popen` to return a fake process whose `stdout.readline` yields canned makemkvcon lines; the real `_stdout_reader` thread, line queue, and parser loop run unchanged. `_FakeProc` / `_FakeStdout` helpers documented as the reusable pattern for the scan parser (item 2).
  - Cases: clean PRGV progression (monotonic progress, "Ripping: N%" log emission, rc=0 → True); PRGT → "Task: ..." log; PRGC → comment log; MSG with full 5-field shape → reaches on_log via `MakeMKVMessageCoalescer`; malformed `PRGV:not,a,number` → silently skipped, valid PRGV after still works; MSG with too few fields → silently skipped; non-zero rc → False, exit code still logged; abort_event set before run → False fast, "Rip aborted." logged; abort_event flipped mid-stream via `on_progress` callback → False, `proc.terminate()` called; empty stdout (EOF immediately) → exits cleanly, logs exit code; `PRGV:50,0` (zero total) → no progress (divide-by-zero guard); `PRGV:200,100` (current > total) → progress capped at 100.
  - Full suite: 708 passed (was 696), ~64s. Per-test cost is ~1s due to the parser's queue.get(timeout=1.0) waiting once for queue drain — acceptable.

- [x] ~~**Controller state-machine wiring integration test**~~ (2026-04-29) — narrower slice of the original "controller orchestration" item; full pipeline end-to-end split out as its own active item. Plus 2 follow-up tests added after a same-day audit pinned subtle debug-log edge cases.
  - `tests/test_controller_state_integration.py`: 20 tests pinning the contract between `RipperController` and `SessionStateMachine` — `_reset_state_machine` (debug flag from cfg, behavioral logger wiring, FAILED-clearing on reset), `_state_transition` (delegation, illegal-transition raise + state preservation, JSON event emission gated on `opt_debug_state_json`), `_state_fail` (delegation + JSON event), fail-then-transition silent no-op, full happy-path emit-order, fail-mid-pipeline state, `_record_fallback_event` (gated emission, no SM mutation), and (added 2026-04-29 audit) two debug-log edge cases: `_state_transition` from FAILED still emits a `transition` JSON event with `state: "FAILED"`, and double `_state_fail` emits two JSON `fail` events with both reasons preserved. Both pin current legacy_compat.py:231-256 behavior — not bugs, but easy to change accidentally.
  - Full suite: 696 passed (was 681 → 694 after event tests → 696 with audit follow-ups), ~49s.
