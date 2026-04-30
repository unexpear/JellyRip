"""Integration tests for the controller's state-machine wiring.

Validates that RipperController correctly drives `SessionStateMachine`
through `_reset_state_machine`, `_state_transition`, `_state_fail`, and
`_record_fallback_event`, with the right side effects (delegation,
JSON-event logging, illegal-transition guard, fail-then-no-op semantics).

This is intentionally narrower than a full disc-pipeline end-to-end test:
it pins the state-machine *contract* the controller offers to the rest of
the pipeline. A follow-up test should cover scan → rip → ... → finalize
with a fully faked engine.
"""

import json

import pytest

from controller.controller import RipperController
from engine.ripper_engine import RipperEngine
from utils.state_machine import SessionState

from tests.test_behavior_guards import DummyGUI, _engine_cfg


def _make_controller(**cfg_overrides):
    engine = RipperEngine(_engine_cfg(**cfg_overrides))
    gui = DummyGUI()
    return RipperController(engine, gui), engine, gui


def _state_json_events(gui: DummyGUI) -> list[dict]:
    """Pull STATE_JSON events emitted via gui.append_log."""
    events: list[dict] = []
    for line in gui.messages:
        marker = "STATE_JSON: "
        idx = line.find(marker)
        if idx == -1:
            continue
        payload = line[idx + len(marker):]
        events.append(json.loads(payload))
    return events


def test_initial_state_is_init():
    controller, _, _ = _make_controller()
    assert controller.sm.state is SessionState.INIT


def test_reset_state_machine_replaces_sm_and_returns_to_init():
    controller, _, _ = _make_controller()
    controller._state_transition(SessionState.SCANNED)
    assert controller.sm.state is SessionState.SCANNED

    original_sm = controller.sm
    controller._reset_state_machine()

    assert controller.sm is not original_sm
    assert controller.sm.state is SessionState.INIT


def test_reset_state_machine_picks_up_debug_flag_from_engine_cfg():
    controller, _, gui = _make_controller(opt_debug_state=True)
    controller._reset_state_machine()
    assert controller.sm.debug is True

    # Behavioral: the SM's logger must route through the controller's
    # logging path so [STATE] debug lines reach the GUI append_log.
    controller.sm.transition(SessionState.SCANNED)
    assert any("[STATE] INIT -> SCANNED" in msg for msg in gui.messages)


def test_reset_state_machine_defaults_debug_off_when_unset():
    controller, _, _ = _make_controller()
    controller._reset_state_machine()
    assert controller.sm.debug is False


def test_state_transition_delegates_to_state_machine():
    controller, _, _ = _make_controller()
    controller._state_transition(SessionState.SCANNED)
    controller._state_transition(SessionState.RIPPED)
    assert controller.sm.state is SessionState.RIPPED


def test_state_transition_raises_on_illegal_transition_and_preserves_state():
    controller, _, _ = _make_controller()
    with pytest.raises(RuntimeError, match="INIT -> RIPPED"):
        controller._state_transition(SessionState.RIPPED)
    assert controller.sm.state is SessionState.INIT


def test_state_transition_emits_json_event_when_debug_state_json_enabled():
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_transition(SessionState.SCANNED)

    events = _state_json_events(gui)

    assert len(events) == 1
    event = events[0]
    assert event["event"] == "transition"
    assert event["state"] == "SCANNED"
    assert "time" in event


def test_state_transition_emits_no_json_event_when_debug_state_json_disabled():
    controller, _, gui = _make_controller(opt_debug_state_json=False)
    controller._state_transition(SessionState.SCANNED)
    assert _state_json_events(gui) == []


def test_state_fail_delegates_to_state_machine():
    controller, _, _ = _make_controller()
    controller._state_fail("scan_failed")
    assert controller.sm.state is SessionState.FAILED


def test_state_fail_emits_json_event_when_debug_state_json_enabled():
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_fail("rip_failed")

    events = _state_json_events(gui)

    assert len(events) == 1
    event = events[0]
    assert event["event"] == "fail"
    assert event["reason"] == "rip_failed"
    assert event["state"] == "FAILED"
    assert "time" in event


def test_state_fail_then_transition_is_silent_no_op():
    """FAILED is sticky: once _state_fail has fired, downstream
    cleanup paths can call _state_transition without re-raising.
    Mirrors the contract documented in test_state_machine.py."""
    controller, _, _ = _make_controller()
    controller._state_fail("rip_failed")
    controller._state_transition(SessionState.STABILIZED)  # must not raise
    assert controller.sm.state is SessionState.FAILED


def test_full_happy_path_through_controller_transitions_reaches_completed():
    controller, _, _ = _make_controller()
    for step in (
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ):
        controller._state_transition(step)
    assert controller.sm.state is SessionState.COMPLETED
    assert controller.sm.is_success() is True


def test_full_happy_path_emits_json_events_in_order_when_enabled():
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    for step in (
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ):
        controller._state_transition(step)

    events = _state_json_events(gui)
    states = [e["state"] for e in events]

    assert states == [
        "SCANNED",
        "RIPPED",
        "STABILIZED",
        "VALIDATED",
        "MOVED",
        "COMPLETED",
    ]
    assert all(e["event"] == "transition" for e in events)


def test_fail_mid_pipeline_records_correct_failed_state():
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_transition(SessionState.SCANNED)
    controller._state_transition(SessionState.RIPPED)
    controller._state_fail("stabilization_failed")

    events = _state_json_events(gui)

    assert [e["event"] for e in events] == ["transition", "transition", "fail"]
    assert events[-1]["reason"] == "stabilization_failed"
    assert events[-1]["state"] == "FAILED"
    assert controller.sm.state is SessionState.FAILED


def test_record_fallback_event_emits_when_debug_state_json_enabled():
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._record_fallback_event(
        reason="size_warning",
        accepted=True,
        strict=False,
    )

    events = _state_json_events(gui)

    assert len(events) == 1
    event = events[0]
    assert event["event"] == "fallback"
    assert event["reason"] == "size_warning"
    assert event["accepted"] is True
    assert event["strict"] is False


def test_record_fallback_event_silent_when_debug_state_json_disabled():
    controller, _, gui = _make_controller(opt_debug_state_json=False)
    controller._record_fallback_event(
        reason="size_warning",
        accepted=False,
        strict=True,
    )
    assert _state_json_events(gui) == []


def test_record_fallback_event_does_not_change_state_machine_state():
    controller, _, _ = _make_controller(opt_debug_state_json=True)
    controller._state_transition(SessionState.SCANNED)
    controller._record_fallback_event(
        reason="size_warning",
        accepted=True,
        strict=False,
    )
    assert controller.sm.state is SessionState.SCANNED


def test_reset_state_machine_clears_failed_state():
    """After a session fails, _reset_state_machine must let a new run
    transition cleanly from INIT — it does not leave FAILED behind."""
    controller, _, _ = _make_controller()
    controller._state_fail("first run failed")
    assert controller.sm.state is SessionState.FAILED

    controller._reset_state_machine()
    assert controller.sm.state is SessionState.INIT
    controller._state_transition(SessionState.SCANNED)
    assert controller.sm.state is SessionState.SCANNED


# --------------------------------------------------------------------------
# Edge cases for the debug-state-json log paths.
# These pin subtle current behavior of _state_transition / _state_fail under
# the opt_debug_state_json flag — they're not bugs (they accurately record
# that the controller method was *invoked*), but they're easy to change
# accidentally during a refactor of legacy_compat.py:_state_transition /
# _state_fail. See `controller/legacy_compat.py:231-256`.
# --------------------------------------------------------------------------


def test_state_transition_from_failed_emits_json_event_with_failed_state():
    """When state is already FAILED, _state_transition is a silent no-op
    at the SM level — but the JSON-log `if` branch in legacy_compat.py:233
    fires unconditionally, so a STATE_JSON entry is still emitted with
    `event: "transition"` and `state: "FAILED"`. Pin the current behavior
    so a refactor that suppresses this log (or that makes _state_transition
    skip when FAILED) shows up here instead of silently changing behavior."""
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_fail("rip_failed")

    # Before the post-fail call, only the fail event should be present.
    pre_events = _state_json_events(gui)
    assert [e["event"] for e in pre_events] == ["fail"]

    controller._state_transition(SessionState.STABILIZED)  # silent at SM layer

    events = _state_json_events(gui)
    assert [e["event"] for e in events] == ["fail", "transition"]
    transition_event = events[-1]
    assert transition_event["state"] == "FAILED"  # SM did not move
    assert controller.sm.state is SessionState.FAILED


def test_state_fail_called_twice_emits_two_json_events():
    """`_state_fail` runs the JSON-log branch unconditionally after
    delegating to sm.fail(), so calling it twice during a cleanup cascade
    yields two STATE_JSON entries — both with `state: "FAILED"` and the
    second carrying the second reason. Pin so a future change to dedupe
    fail events surfaces here."""
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_fail("rip_failed")
    controller._state_fail("cleanup_also_failed")

    events = _state_json_events(gui)

    assert [e["event"] for e in events] == ["fail", "fail"]
    assert [e["reason"] for e in events] == ["rip_failed", "cleanup_also_failed"]
    assert all(e["state"] == "FAILED" for e in events)
    assert controller.sm.state is SessionState.FAILED
