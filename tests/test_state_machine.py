"""Tests for utils.state_machine.SessionStateMachine.

Table-driven coverage of the session lifecycle: every legal transition
must succeed; every illegal transition from a non-FAILED state must raise;
FAILED is a terminal sink that silently absorbs further transition attempts.
"""

from itertools import product

import pytest

from utils.state_machine import SessionState, SessionStateMachine

ALL_STATES = list(SessionState)

LEGAL_TRANSITIONS = [
    (SessionState.INIT, SessionState.SCANNED),
    (SessionState.INIT, SessionState.FAILED),
    (SessionState.SCANNED, SessionState.RIPPED),
    (SessionState.SCANNED, SessionState.FAILED),
    (SessionState.RIPPED, SessionState.STABILIZED),
    (SessionState.RIPPED, SessionState.FAILED),
    (SessionState.STABILIZED, SessionState.VALIDATED),
    (SessionState.STABILIZED, SessionState.FAILED),
    (SessionState.VALIDATED, SessionState.MOVED),
    (SessionState.VALIDATED, SessionState.FAILED),
    (SessionState.MOVED, SessionState.COMPLETED),
    (SessionState.MOVED, SessionState.FAILED),
]

# Every (from, to) pair where `from` is not FAILED and the pair is not legal.
# FAILED is excluded as a source because transitions from FAILED are a silent
# no-op rather than a raise (covered by its own test).
ILLEGAL_TRANSITIONS = [
    (src, dst)
    for src, dst in product(ALL_STATES, ALL_STATES)
    if src is not SessionState.FAILED and (src, dst) not in LEGAL_TRANSITIONS
]


def _force_state(sm: SessionStateMachine, target: SessionState) -> None:
    """Walk the machine forward through a happy path to `target` for setup.

    Avoids reaching into private state — only uses the public API. FAILED is
    reached via fail(); intermediate states via transition() along the
    canonical happy path.
    """
    if target is SessionState.FAILED:
        sm.fail()
        return

    happy_path = [
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ]
    for step in happy_path:
        if sm.state is target:
            return
        sm.transition(step)
    if sm.state is not target:  # pragma: no cover - sanity
        raise AssertionError(f"could not reach {target.name}")


def _machine_at(state: SessionState) -> SessionStateMachine:
    sm = SessionStateMachine()
    _force_state(sm, state)
    assert sm.state is state
    return sm


def test_initial_state_is_init():
    sm = SessionStateMachine()
    assert sm.state is SessionState.INIT


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
    assert sm.state is src, "illegal transition must not mutate state"
    assert src.name in str(excinfo.value)
    assert dst.name in str(excinfo.value)


def test_full_happy_path_reaches_completed():
    sm = SessionStateMachine()
    for step in (
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ):
        sm.transition(step)
    assert sm.state is SessionState.COMPLETED
    assert sm.is_success() is True


@pytest.mark.parametrize("dst", ALL_STATES)
def test_transition_from_failed_is_silent_no_op(dst):
    """FAILED is terminal: transition() returns silently and leaves state
    unchanged regardless of target. This is the documented behavior — fail
    must be sticky and idempotent so cleanup paths can call transition()
    blindly without re-raising."""
    sm = _machine_at(SessionState.FAILED)
    sm.transition(dst)  # must not raise
    assert sm.state is SessionState.FAILED


@pytest.mark.parametrize("src", ALL_STATES)
def test_fail_sets_state_to_failed_from_any_state(src):
    sm = _machine_at(src)
    sm.fail()
    assert sm.state is SessionState.FAILED


def test_fail_is_idempotent():
    sm = SessionStateMachine()
    sm.fail()
    sm.fail("second time")
    sm.fail()
    assert sm.state is SessionState.FAILED


@pytest.mark.parametrize(
    "src",
    [s for s in ALL_STATES if s is not SessionState.FAILED],
)
def test_complete_forces_completed_from_any_non_failed_state(src):
    sm = _machine_at(src)
    sm.complete()
    assert sm.state is SessionState.COMPLETED
    assert sm.is_success() is True


def test_complete_from_failed_is_a_no_op():
    sm = _machine_at(SessionState.FAILED)
    sm.complete()
    assert sm.state is SessionState.FAILED
    assert sm.is_success() is False


@pytest.mark.parametrize(
    "state,expected",
    [(s, s is SessionState.COMPLETED) for s in ALL_STATES],
)
def test_is_success_is_true_only_for_completed(state, expected):
    sm = _machine_at(state)
    assert sm.is_success() is expected


def test_debug_logger_emits_message_on_transition():
    messages: list[str] = []
    sm = SessionStateMachine(debug=True, logger=messages.append)
    sm.transition(SessionState.SCANNED)
    sm.transition(SessionState.RIPPED)
    assert messages == [
        "[STATE] INIT -> SCANNED",
        "[STATE] SCANNED -> RIPPED",
    ]


def test_debug_logger_emits_message_on_complete():
    messages: list[str] = []
    sm = SessionStateMachine(debug=True, logger=messages.append)
    sm.complete()  # forced from INIT
    assert messages == ["[STATE] INIT -> COMPLETED (forced)"]


def test_debug_logger_emits_reason_on_fail():
    messages: list[str] = []
    sm = SessionStateMachine(debug=True, logger=messages.append)
    sm.fail("disc eject")
    assert messages == ["[STATE] FAIL: disc eject"]


def test_debug_off_suppresses_logger_calls():
    messages: list[str] = []
    sm = SessionStateMachine(debug=False, logger=messages.append)
    sm.transition(SessionState.SCANNED)
    sm.fail("oops")
    sm.complete()
    assert messages == []


def test_debug_on_without_logger_does_not_raise():
    sm = SessionStateMachine(debug=True, logger=None)
    sm.transition(SessionState.SCANNED)
    sm.fail("oops")
    sm.complete()  # already FAILED, no-op
    assert sm.state is SessionState.FAILED


def test_fail_without_reason_does_not_emit_log_line():
    messages: list[str] = []
    sm = SessionStateMachine(debug=True, logger=messages.append)
    sm.fail()
    assert messages == []


def test_legal_transitions_table_matches_implementation():
    """Guard: if SessionStateMachine.allowed changes shape, this test must
    fail loudly so the LEGAL_TRANSITIONS table above stays in sync."""
    sm = SessionStateMachine()
    actual = {
        (src, dst)
        for src, dsts in sm.allowed.items()
        for dst in dsts
    }
    assert actual == set(LEGAL_TRANSITIONS)
