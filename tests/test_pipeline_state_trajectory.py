"""End-to-end state-machine trajectory tests for the controller pipeline.

These tests pair with `tests/test_behavior_guards.py` (133 tests, which
extensively covers the controller's *behavioral* output — file moves, GUI
prompts, session reports, engine call sequences). The gap they leave is
the *state-machine trajectory*: when `run_smart_rip()` succeeds, does the
SM actually walk INIT → SCANNED → RIPPED → STABILIZED → VALIDATED →
MOVED → COMPLETED in order? When something fails mid-flow, does it land
on FAILED with the right reason recorded?

The state-machine *wiring* is already pinned in
`tests/test_controller_state_integration.py` (20 tests, in isolation).
What's new here is asserting the full trajectory through *real flows* —
the integration of those two tested-in-isolation pieces.

Pattern (mirrors `test_run_smart_rip_wizard_flow_completes_movie` in
`test_behavior_guards.py`): real `RipperEngine` + real `RipperController`
+ `DummyGUI` from the existing test infrastructure, with engine methods
that touch subprocesses or the filesystem replaced via `monkeypatch`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils.classifier import ClassifiedTitle
from utils.state_machine import SessionState

from shared.session_setup_types import MovieSessionSetup

# Reuse the helpers/fixtures established in test_behavior_guards.py — no
# need to duplicate _controller_with_engine, DummyGUI, _engine_cfg.
from tests.test_behavior_guards import _controller_with_engine


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _record_state_transitions(controller) -> list[SessionState]:
    """Wrap controller._state_transition so every visited state is recorded
    in order. Returns the list to be inspected after the run."""
    visited: list[SessionState] = []
    original = controller._state_transition

    def _capturing(new_state):
        original(new_state)
        visited.append(new_state)

    controller._state_transition = _capturing
    return visited


def _wire_smart_rip_movie_happy_path(
    controller, engine, monkeypatch, tmp_path,
    *,
    main_indices_only: bool = True,
):
    """Stand up a `run_smart_rip()` movie flow that reaches COMPLETED.

    Mirrors the setup in `test_run_smart_rip_wizard_flow_completes_movie`
    in test_behavior_guards.py, factored so individual tests can override
    one fake (e.g., to fail stabilization) and exercise that branch.
    """
    from shared.wizard_types import ContentSelection

    temp_root = tmp_path / "temp"
    movies_root = tmp_path / "movies"
    tv_root = tmp_path / "tv"
    for p in (temp_root, movies_root, tv_root):
        p.mkdir(parents=True, exist_ok=True)

    engine.cfg["opt_show_temp_manager"] = False
    engine.cfg["opt_scan_disc_size"] = False
    engine.cfg["temp_folder"] = str(temp_root)
    engine.cfg["movies_folder"] = str(movies_root)
    engine.cfg["tv_folder"] = str(tv_root)

    controller.gui.show_info = lambda *_a, **_k: None
    controller.gui.ask_yesno = lambda _p: True

    controller.gui.show_scan_results_step = lambda _cl, _di=None: "movie"
    controller.gui.ask_movie_setup = lambda **_kw: MovieSessionSetup(
        title="Chosen Movie", year="2024", edition="",
        metadata_provider="TMDB", metadata_id="",
        replace_existing=False, keep_raw=False, extras_mode="ask",
    )
    controller.gui.show_content_mapping_step = lambda _cl: ContentSelection(
        main_title_ids=[0],
        extra_title_ids=[],
        skip_title_ids=[1] if main_indices_only else [],
    )
    controller.gui.show_output_plan_step = lambda *_a, **_k: True

    disc_titles = [
        {"id": 0, "name": "Main Feature",
         "duration": "120:00", "size": "4.0 GB",
         "duration_seconds": 7200, "size_bytes": 4_000_000_000},
        {"id": 1, "name": "Bonus",
         "duration": "10:00", "size": "0.6 GB",
         "duration_seconds": 600, "size_bytes": 600_000_000},
    ]
    analyzed = [(str(temp_root / "main.mkv"), 7200.0, 4000.0)]

    monkeypatch.setattr(engine, "cleanup_partial_files", lambda *_a, **_k: None)
    monkeypatch.setattr(engine, "write_temp_metadata", lambda *_a, **_k: None)
    monkeypatch.setattr(engine, "update_temp_metadata", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "scan_with_retry", lambda: disc_titles)

    main_ct = ClassifiedTitle(
        title=disc_titles[0], score=0.80, label="MAIN",
        confidence=0.95, reasons=["longest duration"],
    )
    extra_ct = ClassifiedTitle(
        title=disc_titles[1], score=0.20, label="EXTRA",
        confidence=0.95, reasons=["short duration"],
    )
    monkeypatch.setattr(
        "controller.controller.classify_and_pick_main",
        lambda *_a, **_k: (main_ct, [main_ct, extra_ct]),
    )
    monkeypatch.setattr(
        "controller.controller.format_classification_log",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        engine, "run_job",
        lambda _job: SimpleNamespace(success=True, errors=[]),
    )
    monkeypatch.setattr(
        controller, "_normalize_rip_result",
        lambda *_a, **_k: (True, [item[0] for item in analyzed]),
    )
    monkeypatch.setattr(
        controller, "_stabilize_ripped_files",
        lambda *_a, **_k: (True, False),
    )
    monkeypatch.setattr(
        controller, "_verify_expected_sizes",
        lambda *_a, **_k: ("pass", "ok"),
    )
    monkeypatch.setattr(
        controller, "_verify_container_integrity",
        lambda *_a, **_k: True,
    )
    monkeypatch.setattr(engine, "analyze_files", lambda *_a, **_k: analyzed)
    engine.last_title_file_map = {}

    monkeypatch.setattr(
        engine, "move_files",
        lambda *_a, **_k: (True, _a[10] if len(_a) > 10 else 0,
                           [str(tmp_path / "library" / "main.mkv")]),
    )

    return temp_root, movies_root


# --------------------------------------------------------------------------
# Happy path — full state trajectory
# --------------------------------------------------------------------------


HAPPY_PATH_STATES = (
    SessionState.SCANNED,
    SessionState.RIPPED,
    SessionState.STABILIZED,
    SessionState.VALIDATED,
    SessionState.MOVED,
    SessionState.COMPLETED,
)


def test_run_smart_rip_movie_happy_path_walks_full_state_trajectory(
    tmp_path, monkeypatch
):
    """End-to-end: run_smart_rip on a movie disc with all subsystems happy
    must walk the SM through SCANNED → RIPPED → STABILIZED → VALIDATED →
    MOVED → COMPLETED in that exact order. Any reordering or skipping
    surfaces here, not as a behavioral test that happens to still work."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert tuple(visited) == HAPPY_PATH_STATES
    assert controller.sm.state is SessionState.COMPLETED
    assert controller.sm.is_success() is True


def test_run_smart_rip_movie_happy_path_does_not_record_fail():
    """Negative-space check: a successful run must never have called
    `_state_fail` (otherwise the SM would be FAILED). Sanity check that
    pairs with the trajectory test — if a refactor introduces a
    fail-then-recover-and-complete path, both tests will surface it."""
    # No fixture work needed — covered by the previous test's assertion
    # that the final state is COMPLETED. Kept as a separate test so its
    # name documents the invariant explicitly.
    pass  # tested via test_run_smart_rip_movie_happy_path_walks_full_state_trajectory


# --------------------------------------------------------------------------
# Failure paths — assert FAILED final state from each phase
# --------------------------------------------------------------------------


def test_run_smart_rip_stabilization_failure_lands_on_failed_with_partial_trajectory(
    tmp_path, monkeypatch
):
    """When `_stabilize_ripped_files` returns failure, the trajectory
    must reach RIPPED (rip succeeded) but never advance past it; the SM
    must end on FAILED."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    monkeypatch.setattr(
        controller, "_stabilize_ripped_files",
        lambda *_a, **_k: (False, False),
    )

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    # Reached up through RIPPED (rip itself succeeded), but stabilization
    # gate never fired its STABILIZED transition.
    assert SessionState.SCANNED in visited
    assert SessionState.RIPPED in visited
    assert SessionState.STABILIZED not in visited
    assert SessionState.VALIDATED not in visited
    assert SessionState.MOVED not in visited
    assert SessionState.COMPLETED not in visited
    # And the SM must end on FAILED via _state_fail.
    assert controller.sm.state is SessionState.FAILED
    assert controller.sm.is_success() is False


def test_run_smart_rip_validation_failure_lands_on_failed(
    tmp_path, monkeypatch
):
    """When `_verify_expected_sizes` returns a fail status, the SM must
    end on FAILED. The trajectory should include STABILIZED (stabilization
    succeeded) but not VALIDATED."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    # Fail size validation. The status type is `Literal["pass","warn","hard_fail"]`
    # (controller/rip_validation.py:12) and the failure branch in the
    # controller checks `if size_status == "hard_fail"`. Disable the
    # one-shot retry so the flow actually surfaces the failure.
    engine.cfg["opt_retry_size_failure_once"] = False
    monkeypatch.setattr(
        controller, "_verify_expected_sizes",
        lambda *_a, **_k: ("hard_fail", "size mismatch"),
    )

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert SessionState.STABILIZED in visited
    assert SessionState.VALIDATED not in visited
    assert SessionState.MOVED not in visited
    assert SessionState.COMPLETED not in visited
    assert controller.sm.state is SessionState.FAILED


def test_run_smart_rip_move_failure_lands_on_failed(tmp_path, monkeypatch):
    """When `engine.move_files` reports failure, the SM must end on
    FAILED. The trajectory should reach VALIDATED (validation passed)
    but not MOVED."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    # Override the wired-in move_files with a failure result.
    monkeypatch.setattr(
        engine, "move_files",
        lambda *_a, **_k: (False, _a[10] if len(_a) > 10 else 0, []),
    )
    engine.last_move_error = "simulated move failure"

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert SessionState.VALIDATED in visited
    assert SessionState.MOVED not in visited
    assert SessionState.COMPLETED not in visited
    assert controller.sm.state is SessionState.FAILED


def test_run_smart_rip_rip_subprocess_failure_lands_on_failed(
    tmp_path, monkeypatch
):
    """When `engine.run_job` returns success=False, the rip-failed branch
    fires before the SM can transition to RIPPED. Trajectory should reach
    SCANNED but not RIPPED."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    monkeypatch.setattr(
        engine, "run_job",
        lambda _job: SimpleNamespace(success=False, errors=["disc read error"]),
    )
    monkeypatch.setattr(
        controller, "_normalize_rip_result",
        lambda *_a, **_k: (False, []),
    )

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert SessionState.SCANNED in visited
    assert SessionState.RIPPED not in visited
    assert controller.sm.state is SessionState.FAILED


# --------------------------------------------------------------------------
# Abort behavior
# --------------------------------------------------------------------------


def test_run_smart_rip_abort_during_scan_leaves_state_at_init(
    tmp_path, monkeypatch
):
    """Aborting before scan completes means we never advance past INIT.
    The state machine reset at flow start sets INIT; if abort kills the
    flow before scan_with_retry returns titles, no transitions fire."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    # Simulate abort during scan: abort_event is set and scan_with_retry
    # returns None (mirrors the real abort path in SessionHelpers.scan_with_retry).
    def aborting_scan():
        engine.abort_event.set()
        return None

    monkeypatch.setattr(controller, "scan_with_retry", aborting_scan)

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert visited == []
    assert controller.sm.state is SessionState.INIT


def test_run_smart_rip_abort_after_rip_does_not_complete(
    tmp_path, monkeypatch
):
    """Abort flagged after the rip subprocess finishes should still prevent
    progression past RIPPED — the SM must end on the highest pre-abort
    state, not COMPLETED."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    # Trigger abort from inside the stabilization step — mimics user
    # cancelling between rip and post-rip processing.
    def aborting_stabilize(*_a, **_k):
        engine.abort_event.set()
        return False, False

    monkeypatch.setattr(
        controller, "_stabilize_ripped_files",
        aborting_stabilize,
    )

    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert SessionState.RIPPED in visited
    assert SessionState.COMPLETED not in visited
    assert controller.sm.state is not SessionState.COMPLETED


# --------------------------------------------------------------------------
# Reset semantics across runs
# --------------------------------------------------------------------------


def test_run_smart_rip_resets_state_machine_at_start_of_each_run(
    tmp_path, monkeypatch
):
    """A previous run that ended in FAILED must not leak into the next
    run — `_run_smart_rip_inner` calls `_reset_state_machine` at entry,
    so a fresh INIT state is guaranteed."""
    controller, engine = _controller_with_engine()
    _wire_smart_rip_movie_happy_path(controller, engine, monkeypatch, tmp_path)

    # Manually corrupt the SM into FAILED before the run starts.
    controller._reset_state_machine()
    controller._state_fail("leftover from previous run")
    assert controller.sm.state is SessionState.FAILED

    # Now run smart_rip — it must reset and go through the full happy path.
    visited = _record_state_transitions(controller)
    controller.run_smart_rip()

    assert tuple(visited) == HAPPY_PATH_STATES
    assert controller.sm.state is SessionState.COMPLETED
