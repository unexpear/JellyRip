# JellyRip — Testing Strategy

Last updated: 2026-04-29 — second-pass audit. Three claims in the original draft turned out not to match the actual code (`shared/event.py` was not a pub/sub bus, `shared/windows_exec.py` does not construct argv, `transcode/recommend.py` is dead code) and were corrected after agents verified each one against the source. Tasks below are now grounded in real file:line locations.

Baseline: **802 tests passing** in ~95s. ~12s of overhead is from `tests/test_rip_parser.py` (each test waits ~1s for `queue.get(timeout=1.0)` to drain — unavoidable when testing the real threading path). The other ~30s of growth is from `tests/test_pipeline_state_trajectory.py` (9 tests, ~34s total — each runs the full `run_smart_rip` flow with real threading per case to assert state-machine trajectories end-to-end). All other new files are sub-second: scan parser ~0.9s, windows_exec ~0.4s, controller state integration ~0.6s, event ~0.4s, main_window formatters ~0.7s. Pyright strict mode: 8292 baseline errors (mostly missing annotations, treated as a trend rather than a gate).

## Pyramid mapping

| Tier | What it covers here | Speed budget |
|---|---|---|
| **Unit** (majority) | parsers, builders, planners, classifiers, validators, state machine | <100ms each |
| **Integration** | controller orchestration, session lifecycle, full transcode queue with fakes for ffmpeg/HandBrake, makemkvcon stdout parsing | <2s each |
| **E2E / smoke** | startup → scan → analyze → rip plan (no real disc), update flow against fixture, GUI-headless smoke (already covered by `test_gui_import` + `test_on_close_destroys_window_without_force_exit`) | small handful |

## Coverage by component type

### 1. Transcode subsystem — well covered
- Covered: queue builder, engine progress mapping, abort handling, recommendations across HDR/SDR/8/10-bit, command validator, encoder probe, fallback, post-encode verifier, `ProfileLoader` save/load + `TranscodeProfile.to_dict()` round-trip (in `tests/test_imports.py`), planner happy-path (`test_transcode_queue_builder.py`).
- **Unused modules audited and kept on disk** (verified zero imports project-wide; not deleted per user direction *"don't remove features even if half built — just tell me them"*):
  - `transcode/recommend.py` — earlier prototype of the recommendation engine, superseded by the live `recommendations.py`. Two ideas in it didn't migrate to the live engine: a "skip if source already small/efficient" recommendation (constraint fields exist in `core/pipeline.py:TranscodeJob.should_skip` but no live recommender emits them) and a `{title}_recommended` output-naming template.
  - `transcode/profile_summary.py` — half-built "non-technical-user friendly summary" view (e.g., *"Convert video to H.265 (smaller files, good quality)"* vs the live terse *"Video: H.265 CRF 22"* in `describe_profile`). Drafted but never wired into the GUI; revivable as a Settings toggle.
  - `transcode/transcode_profile.py` — vestigial re-export shim around `profiles.TranscodeProfile`. No unique behavior. Of the three, the safest to remove later.
- **Stretch**: planner edge cases — Windows drive letters, UNC paths, `..` segments, symlinks, 100+-file dedup.
- **Correction**: an earlier draft framed this section's gaps as "profile serialization round-trip" (already covered) and "verify `recommend.py` vs `recommendations.py` aren't drifting" (premise wrong: `recommend.py` is dead code). Both were dropped.

### 2. Controller / pipeline — covered
- Per-module unit tests: `controller/library_scan.py`, `controller/naming.py`, `controller/rip_validation.py`, `controller/session_paths.py`, `controller/session_recovery.py`.
- **State-machine wiring contract**: `tests/test_controller_state_integration.py` (20 tests, includes 2 audit follow-ups for debug-log edge cases) — `_reset_state_machine`, `_state_transition`, `_state_fail`, `_record_fallback_event`, illegal-transition guard, JSON-event emission gating, FAILED-as-sink semantics.
- **Behavioral output through real flows**: `tests/test_behavior_guards.py` (133 tests, pre-existing) — drives `run_smart_rip`, `run_movie_disc`, `run_tv_disc`, `run_dump_all`, `run_organize` and asserts on file moves, GUI prompts, session reports, engine call sequences.
- **State-machine trajectory through real flows**: `tests/test_pipeline_state_trajectory.py` (9 tests) — wraps `_state_transition` to record visit order, drives `run_smart_rip` with a `_wire_smart_rip_movie_happy_path` helper that mirrors the existing happy-path setup. Pins: full SCANNED→RIPPED→STABILIZED→VALIDATED→MOVED→COMPLETED order; partial trajectories ending in FAILED for failures at each phase (rip / stabilize / validate / move); abort-during-scan stays at INIT; abort-mid-stabilize doesn't reach COMPLETED; previous-run FAILED state is cleared on next run.
- **Real find while writing the trajectory file**: `_verify_expected_sizes` returns `Literal["pass","warn","hard_fail"]` (controller/rip_validation.py:12), not `"fail"`. The controller's failure branch checks `if size_status == "hard_fail"` so a test using `"fail"` silently passes through to COMPLETED. Pinned with a comment at the call site so future tests don't repeat the mistake.
- Open (lower priority): `controller/legacy_compat.py` outside the state-machine helpers; `core/pipeline.py` (`TranscodeJob`, `choose_available_output_path`, `PipelineController` — already partially exercised via `test_transcode_queue_builder.py`).

### 3. Engine ops — covered
- **Rip parser**: `tests/test_rip_parser.py` (12 tests) pins `engine/ripper_engine.py:_run_rip_process` (lines 1298–1518) — clean PRGV progression, PRGT/PRGC/MSG dispatch, malformed PRGV silently skipped, MSG with too few fields silently skipped, non-zero rc → False, abort before run → False fast, abort mid-stream via on_progress callback → False with terminate() called, empty stdout (immediate EOF), zero-total PRGV (divide-by-zero guard), current > total (capped at 100). Seam: `monkeypatch.setattr("engine.ripper_engine.subprocess.Popen", lambda *a, **kw: fake)` returns a `_FakeProc` whose `stdout.readline` yields canned lines; the real `_stdout_reader` thread, line queue, and parser loop run unchanged.
- **Scan parser**: `tests/test_scan_parser.py` (21 tests) pins `engine/scan_ops.py:scan_disc` (lines 113–279) and the `_parse_drive_info()` helper. Same seam pattern (`engine.scan_ops.subprocess.Popen`). Synchronous parser, no thread — each test runs in ~40ms. Covered: clean CINFO+TINFO+SINFO with all parsed fields; sorted by descending duration; per-title progress capped at 90; invalid duration/size marks title `_invalid` and excludes it; malformed CINFO/TINFO silently skipped; orphan SINFO (no parent TINFO) silently skipped; MSG with too few fields silently skipped; abort → returns None + `proc.kill()`; non-zero exit → None + log; Popen exception → swallowed; empty stdout → `[]`; all-invalid → `[]`. Plus `_parse_drive_info` tri-state classifier (enabled/possible/unavailable), UHD + LibreDrive heuristics, and a documented ordering quirk: the `"enabled"`/`"active"` substring check runs before `"possible"`/`"not yet"`, so phrases like *"possible but not yet active"* classify as `"enabled"` (pinned by `test_parse_drive_info_active_wins_over_possible_when_both_appear`).
- **Correction (kept for posterity)**: an earlier draft listed `engine/rip_ops.py` and `engine/scan_ops.py` as direct test targets. `rip_ops.py` is a thin wrapper — its three functions build commands and delegate to `_run_rip_process`/`_run_preview_process`. There is no parsing in `rip_ops.py`. `scan_ops.scan_disc` is the right target, but only because it owns its subprocess (unlike `rip_ops`).

### 4. Utils — partial
- Covered: classifier, helpers, parsing, makemkv_log, updater, **state machine** (`tests/test_state_machine.py`, 98 tests — table-driven legal/illegal transitions, FAILED-as-sink, debug-logger paths, drift guard against `SessionStateMachine.allowed`).
- Missing: `utils/fallback.py`, `utils/media.py`, `utils/scoring.py`, `utils/session_result.py`. Scoring is the highest-value of these — it drives title selection.

### 5. Shared runtime — partial
- Covered: `shared/event.py` — `Event` dataclass invariants + `RipperController.emit()` semantics (`tests/test_event.py`, 13 tests). `shared/windows_exec.py` — path-trust contract for the five public resolvers (`tests/test_windows_exec.py`, 17 tests): absolute + normalized + under `C:\Windows`, PATH-independent, hardcoded fallback when on-disk file missing, env-var chain (`SystemRoot` → `WINDIR` → hardcoded) for the root directory, documented non-Windows return values.
- Missing: `shared/ai_diagnostics.py`, `shared/runtime.py`.
- **Correction (event.py)**: earlier draft described `shared/event.py` as a pub/sub bus needing subscriber-order / exception-isolation / unsubscribe-during-emit tests. That was wrong — it's an 8-line frozen dataclass. The "publish" side is `RipperController.emit()`, which dispatches to a *single* optional UI adapter via duck-typed `handle_event`. No multi-subscriber dispatch, no subscribe/unsubscribe API, and `emit()` does not isolate exceptions.
- **Correction (windows_exec.py)**: earlier draft described `shared/windows_exec.py` as an "injection fuzz" target — implying argv construction and shell-metacharacter quoting. The module does *neither*. It resolves trusted absolute paths only (PowerShell, Explorer, Windows system dirs). The actual security property to pin is **path trust**: every public function returns an absolute path under `C:\Windows`, normalized, PATH-independent, with hardcoded fallback when the on-disk file is missing. The real injection-risk surface is at *callers* of these helpers (where `subprocess.run` is built), and that's already partially covered by `tests/test_security_hardening.py`.

### 6. GUI / UI — covered
- Existing: 30+ tests in `tests/test_imports.py` exercise GUI presentation logic via `unittest.mock.patch("tkinter.Tk", new=_FakeTkBase)`. Hits: `_parse_expert_profile_value`, `_collect_expert_profile_data`, `_load_expert_profile_snapshot`, `_expert_profile_form_is_dirty`, `_populate_expert_profile_vars`, `_summarize_expert_profile`, `_confirm_profile_hdr_metadata_save`, `_confirm_discard_dirty_expert_changes`, `_save_expert_profile_data`, `_persist_settings_and_profile_*` (success + rollback), `_create/_duplicate/_delete/_set_default_expert_profile`, `_resolve_transcode_backend_path`, `_run_on_main`, `ask_duplicate_resolution`, `ask_space_override`, `ask_input`, `ask_yesno`, `_confirm_input`, `on_close`, `_pick_movie_mode`, `disable_buttons`. Plus `ui.dialogs.ask_yes_no` and `ui.settings.summarize_profile`.
- Headless smoke covered by `test_gui_import` (`tests/test_imports.py:18-25`) + `test_on_close_destroys_window_without_force_exit` (lines 570–595).
- New (`tests/test_main_window_formatters.py`, 47 tests): `_format_drive_label` (label format + 3 fallbacks + 4 state-code decodings), `_trim_context_label` (pass-through, whitespace-collapse, at-limit, ellipsis-trim, rstrip-before-ellipsis, empty), `_main_status_style_for_message` (4 pill categories with parametric token coverage, error-vs-warning ordering pin, `_theme=None` fallback, custom `_theme` honored), `_get_text_widget_selection` (defensive paths — non-widget, exception, None), `_ffmpeg_version_ok` (5 paths + message-content pin).
- **Test-isolation gotcha pinned for future contributors**: `JellyRipperGUI` inherits from `tk.Tk` via `SecureTk`. `object.__new__(JellyRipperGUI)` after a module-level `unittest.mock.patch("tkinter.Tk", new=_FakeTkBase)` works only if no other test has already imported `gui.main_window` (sys.modules cache). When the cache is warm, the patch is a no-op and `getattr(self, "_theme", None)` recurses infinitely via `Tk.__getattr__` on the missing `self.tk`. Fix: in any fixture/test that constructs `JellyRipperGUI` via `object.__new__`, set the attributes the method reads (e.g., `_theme`) explicitly — never rely on a default-to-None branch via `getattr`.
- **Correction (kept for posterity)**: original draft said "Extract any remaining presentation logic from widgets into `ui/adapters.py`". That's wrong on two counts:
  1. Presentation logic in `gui/main_window.py` (7782 lines) is *already separated* from Tk calls — the formatters above are pure. No source refactor was needed.
  2. `ui/adapters.py` is a `Protocol` for dependency injection (10 lines: `handle_event`, `on_progress`, `on_log`, `on_error`, `on_complete`). Mixing utilities into it would violate single responsibility. If a presenter module is ever needed, the right home is a new `ui/presenters.py` — but a 5-method count doesn't warrant that yet.
  3. `test_gui_import` and `test_on_close_destroys_window_without_force_exit` already cover the "init/teardown smoke" goal.

### 7. Security boundaries — already covered, keep tight
- Covered: `tests/test_security_hardening.py` — signer thumbprint, trusted-explorer/powershell, resolved binary paths.
- Adjacent: items 4 (windows_exec path-trust contract) and a possible follow-up that audits every `subprocess.run` / `subprocess.Popen` call site for user-controlled input. The latter is bigger and is *the* real "injection fuzz" target — `windows_exec.py` is the path-resolution side, not the argv-construction side.

## Coverage targets

| Area | Today (rough) | Target |
|---|---|---|
| transcode/ | ~85% | 90% (mostly via item 7 in TASKS.md, plus dead-file cleanup) |
| controller/ + core/pipeline | ~75% (wiring + behavioral + state-trajectory all pinned) | met |
| engine/ | ~50% (rip + scan parsers pinned) | 65% (remaining: `analyze_files`, `_quick_ffprobe_ok`, drive probing, file ops) |
| utils/ | ~70% (state machine done) | 85% (scoring is highest-value remaining) |
| shared/ | ~50% (event.py + windows_exec.py done) | 70% (`runtime.py`, `ai_diagnostics.py` remain) |
| gui/ + ui/ | substantial — 30+ existing tests + 47 new formatter tests | met (no extraction needed; 5 untested formatters now covered) |

## Concrete additions, ranked by value (mirrors TASKS.md Active)

1. **Planner edge cases** *(stretch)* — Windows path quirks, UNC, symlinks, dedup at scale.

Done in this audit cycle: state machine table tests, event system contract, controller state-machine wiring (+ 2 audit follow-ups), rip stdout-parser, scan stdout-parser (incl. `_parse_drive_info` tri-state quirk pin), `windows_exec.py` path-trust contract, `gui/main_window.py` formatters (incl. test-isolation gotcha), controller pipeline state-trajectory through real flows (incl. `hard_fail` status quirk pin), **unused `transcode/` audit** (kept on disk per user direction; half-built features documented).

## Example tests (reflecting actual implementation patterns)

The state-machine table-driven pattern is the cleanest reference (`tests/test_state_machine.py`):

```python
@pytest.mark.parametrize("src,dst", LEGAL_TRANSITIONS)
def test_legal_transition_updates_state(src, dst):
    sm = _machine_at(src)
    sm.transition(dst)
    assert sm.state is dst

@pytest.mark.parametrize("src,dst", ILLEGAL_TRANSITIONS)
def test_illegal_transition_raises_with_descriptive_message(src, dst):
    sm = _machine_at(src)
    with pytest.raises(RuntimeError) as excinfo:
        sm.transition(dst)
    assert sm.state is src
    assert src.name in str(excinfo.value)
    assert dst.name in str(excinfo.value)
```

For the rip stdout parser, the seam is `_stdout_reader` — pre-populate the line queue with canned lines:

```python
# Sketch only — feeds canned makemkvcon output into the line queue
# that engine/ripper_engine.py:_run_rip_process reads.
def test_rip_parser_handles_progressive_prgv(monkeypatch, ...):
    canned_lines = [
        'PRGV:0,65536\n',
        'PRGV:32768,65536\n',
        'PRGV:65536,65536\n',
        'MSG:5036,...,...,Title 1 ripped successfully.\n',
    ]
    monkeypatch.setattr(engine, "_stdout_reader",
                        lambda *_a, **_kw: iter(canned_lines))
    progress = []
    rc = engine._run_rip_process(["fake-cmd"], on_progress=progress.append, on_log=lambda _: None)
    assert rc == 0
    assert progress == [0, 50, 100]
```

For controller end-to-end (item 1), follow the existing pattern in `tests/test_behavior_guards.py` — real `RipperEngine`, real `RipperController`, `DummyGUI`, monkeypatch the engine's subprocess-touching methods only.
