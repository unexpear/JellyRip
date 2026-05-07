"""Cancel-class regression tests for the controller (2026-05-04).

Pins the fix for the SM-leak class the smoke bot caught:
``_run_disc_inner`` cancel-return paths left the SM at INIT, the
post-loop ``sm.complete()`` then forced it to COMPLETED, and
``write_session_summary`` falsely claimed
"All discs completed successfully" — even though the user had
cancelled the movie-setup form.

The fix was four-layered:

1. ``SessionStateMachine.cancel(reason)`` — sets state=FAILED AND
   ``was_cancelled=True`` so callers can distinguish a real error
   from a user dismissal.
2. ``RipperController._state_cancelled(reason)`` — sibling to
   ``_state_fail`` that delegates to ``sm.cancel`` + emits the
   STATE_JSON event.
3. ``write_session_summary`` — checks ``sm.was_cancelled`` first
   and emits "Cancelled by user." instead of falling through.
   Defensive INIT-with-no-work branch added too.
4. Cancel points in ``_run_disc_inner`` — each ``break`` cancel
   path now calls ``_state_cancelled(...)`` first, so by the time
   the post-loop ``sm.complete()`` runs it's a no-op.

The "Done" dialog wording is also conditional on the SM state now —
no more "Session complete!" pop-up after a user cancel.

These tests verify the contract end-to-end with a faked GUI.  They
deliberately exercise each user-cancel point individually so a
future refactor that drops the ``_state_cancelled`` call at any one
of them surfaces immediately.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from controller.controller import RipperController
from engine.ripper_engine import RipperEngine
from utils.state_machine import SessionState

from tests.test_behavior_guards import DummyGUI, _engine_cfg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_controller(**cfg_overrides):
    """Same shape as test_controller_state_integration._make_controller —
    duplicated here because importing across test files is fragile."""
    engine = RipperEngine(_engine_cfg(**cfg_overrides))
    gui = DummyGUI()
    return RipperController(engine, gui), engine, gui


def _summary_lines(gui: DummyGUI) -> list[str]:
    """Return the lines emitted by ``write_session_summary``.  Useful
    for asserting on summary content without depending on log-line
    timestamps."""
    return [
        msg for msg in gui.messages if "Session summary:" in msg
    ]


# ---------------------------------------------------------------------------
# _state_cancelled — controller helper
# ---------------------------------------------------------------------------


def test_state_cancelled_marks_sm_as_cancelled():
    """The controller helper delegates to ``sm.cancel`` — sm ends in
    FAILED, was_cancelled flips to True, fail_reason captures the
    string we passed in."""
    controller, _, _ = _make_controller()
    controller._state_cancelled("user_cancelled_movie_setup")
    assert controller.sm.state is SessionState.FAILED
    assert controller.sm.was_cancelled is True
    assert controller.sm.fail_reason == "user_cancelled_movie_setup"


def test_state_cancelled_emits_state_json_when_debug_on():
    """The cancel event must surface in the STATE_JSON debug stream
    so post-mortem tooling can distinguish cancels from failures."""
    import json
    controller, _, gui = _make_controller(opt_debug_state_json=True)
    controller._state_cancelled("user_cancelled_disc_tree")
    json_events = []
    for line in gui.messages:
        marker = "STATE_JSON: "
        idx = line.find(marker)
        if idx == -1:
            continue
        json_events.append(json.loads(line[idx + len(marker):]))
    assert any(
        e["event"] == "cancel" and e["reason"] == "user_cancelled_disc_tree"
        for e in json_events
    )


def test_state_cancelled_makes_complete_a_noop():
    """After ``_state_cancelled``, calling ``sm.complete()`` (which
    happens at the end of ``_run_disc_inner``) is a no-op — the SM
    stays FAILED with was_cancelled=True.  This is what makes the
    post-loop fallthrough safe."""
    controller, _, _ = _make_controller()
    controller._state_cancelled("user_cancelled_setup")
    controller.sm.complete()
    assert controller.sm.state is SessionState.FAILED
    assert controller.sm.was_cancelled is True


# ---------------------------------------------------------------------------
# write_session_summary — message routing per state
# ---------------------------------------------------------------------------


def test_summary_after_cancel_says_cancelled_by_user():
    """The bug class: after user cancellation, the summary must NOT
    say "All discs completed successfully".  Pinned tightly because
    that exact string was the v1-blocker the smoke bot caught."""
    controller, _, gui = _make_controller()
    controller._state_cancelled("user_cancelled_movie_setup")
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert summary, "summary line was never emitted"
    assert any("Cancelled by user" in line for line in summary)
    assert not any(
        "completed successfully" in line for line in summary
    )


def test_summary_after_cancel_takes_precedence_over_session_report():
    """If both was_cancelled is True AND there are warnings in the
    session_report, "Cancelled by user" still wins.  The user
    bailed; the warnings are secondary."""
    controller, _, gui = _make_controller()
    controller.session_report = ["warning: temp folder near full"]
    controller._state_cancelled("user_cancelled_setup")
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert any("Cancelled by user" in line for line in summary)


def test_summary_after_real_failure_says_session_failed():
    """Real failure (``_state_fail``, not cancel) — summary must say
    "Session failed.", not "Cancelled by user."  Pinned because the
    distinction matters for user perception."""
    controller, _, gui = _make_controller()
    controller._state_fail("makemkvcon_exited_1")
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert any("Session failed" in line for line in summary)
    assert not any("Cancelled by user" in line for line in summary)


def test_summary_at_init_with_no_work_says_no_discs_ripped():
    """Defensive safety net: if the SM never advances past INIT
    AND no warnings — i.e., we entered the summary path without
    doing any work — emit a neutral "Session ended without ripping
    any discs" message instead of falling through to the
    misleading "All discs completed successfully".

    Catches future cancel paths that forget to call
    ``_state_cancelled`` first."""
    controller, _, gui = _make_controller()
    # SM stays at INIT — simulating a cancel-leak that bypassed
    # _state_cancelled.
    assert controller.sm.state is SessionState.INIT
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert any(
        "without ripping any discs" in line for line in summary
    )
    assert not any(
        "completed successfully" in line for line in summary
    )


def test_summary_after_clean_completion_unchanged():
    """The fix must not regress the happy path.  After
    ``sm.complete()``, summary still says
    "All discs completed successfully."  No was_cancelled, no
    session_report → the canonical success message."""
    controller, _, gui = _make_controller()
    controller.sm.complete()
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert any(
        "All discs completed successfully" in line for line in summary
    )


def test_summary_after_completed_with_warnings_unchanged():
    """Another regression guard — completion + warnings still emits
    the warnings table.  Not affected by the fix."""
    controller, _, gui = _make_controller()
    controller.session_report = ["warning: low disk space"]
    controller.sm.complete()
    controller.write_session_summary()
    # Match either the lead line or the divider — whichever survives
    # the format change.
    assert any(
        "Completed with warnings" in line for line in gui.messages
    )


def test_summary_skipped_when_failure_report_disabled():
    """``opt_session_failure_report=False`` suppresses the entire
    summary write.  Not affected by the fix.  Pinned to make sure
    the new ``was_cancelled`` branch doesn't sneak past the gate."""
    controller, _, gui = _make_controller(opt_session_failure_report=False)
    controller._state_cancelled("user_cancelled_setup")
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert summary == []


# ---------------------------------------------------------------------------
# _open_manual_disc_picker — disc-tree cancel marks the SM
# ---------------------------------------------------------------------------


class _CancellingDiscTreeGUI(DummyGUI):
    """GUI that returns ``None`` from ``show_disc_tree`` to simulate
    the user dismissing the dialog via Cancel / Esc."""

    def show_disc_tree(self, *_args, **_kwargs):
        return None


def test_open_manual_disc_picker_marks_cancellation():
    """The bug Section 7 surfaced: cancelling the disc-tree dialog
    inside ``_open_manual_disc_picker`` left SM at INIT.  Now it
    flips to FAILED + was_cancelled."""
    engine = RipperEngine(_engine_cfg())
    gui = _CancellingDiscTreeGUI()
    controller = RipperController(engine, gui)

    selected_ids, selected_size = controller._open_manual_disc_picker(
        disc_titles=[],
        is_tv=False,
    )
    assert selected_ids is None
    assert selected_size is None
    assert controller.sm.was_cancelled is True
    assert controller.sm.state is SessionState.FAILED


def test_disc_tree_cancel_logs_correct_messages():
    """End-to-end through ``_open_manual_disc_picker``: log line is
    "Cancelled.", the cancellation event is recorded, and the
    SM-cancel flag is set.  Combined this makes
    ``write_session_summary`` emit "Cancelled by user." instead of
    "All discs completed successfully."

    This is the v1-blocker scenario from the smoke bot's Section 7
    cancel reproduction — the post-loop summary lands on the right
    message because of the SM marking."""
    engine = RipperEngine(_engine_cfg())
    gui = _CancellingDiscTreeGUI()
    controller = RipperController(engine, gui)

    controller._open_manual_disc_picker([], is_tv=False)
    controller.sm.complete()  # what _run_disc_inner does post-loop
    controller.write_session_summary()
    summary = _summary_lines(gui)

    assert any("Cancelled by user" in line for line in summary), (
        f"expected 'Cancelled by user' in summary, got: {summary}"
    )
    assert not any(
        "completed successfully" in line for line in summary
    ), (
        f"summary still claims success — the SM-leak bug is back: {summary}"
    )


# ---------------------------------------------------------------------------
# Property test — every cancel reason produces a non-success summary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "user_cancelled_movie_setup",
        "user_cancelled_tv_review",
        "user_cancelled_disc_tree",
        "user_declined_uhd_warning",
        "user_declined_space_warning",
        "user_cancelled_setup",
        # Edge cases that should still flag as cancelled:
        "",                # empty reason
        "x" * 200,         # very long reason
        "weird/chars\\here",
    ],
)
def test_every_cancel_reason_produces_cancelled_summary(reason):
    """No matter what reason string we feed to ``_state_cancelled``,
    the summary must say "Cancelled by user."  The reason is
    metadata; the user-visible summary is the same."""
    controller, _, gui = _make_controller()
    controller._state_cancelled(reason)
    controller.sm.complete()  # post-loop call from _run_disc_inner
    controller.write_session_summary()
    summary = _summary_lines(gui)
    assert any("Cancelled by user" in line for line in summary)
    assert not any(
        "completed successfully" in line for line in summary
    )


# ---------------------------------------------------------------------------
# Mixed flows — cancel followed by additional operations
# ---------------------------------------------------------------------------


def test_cancel_then_post_loop_complete_keeps_cancel_signal():
    """Mirrors the exact ``_run_disc_inner`` sequence: cancel
    inside the loop → break → post-loop ``sm.complete()`` →
    ``write_session_summary``.  The cancel signal must survive
    the complete() call (no-op when FAILED)."""
    controller, _, gui = _make_controller()

    controller._state_cancelled("user_cancelled_movie_setup")
    controller.sm.complete()  # no-op
    controller.write_session_summary()

    summary = _summary_lines(gui)
    assert any("Cancelled by user" in line for line in summary)
    assert controller.sm.is_cancelled() is True
    assert controller.sm.state is SessionState.FAILED


def test_real_failure_then_cancel_keeps_failure_classification():
    """Edge case: a real engine failure happens, THEN the user hits
    cancel on a follow-up prompt.  The cancel marks
    was_cancelled=True, which wins for summary purposes — the user
    bailed out, even if there was also a real error."""
    controller, _, gui = _make_controller()
    controller._state_fail("makemkvcon_exited_1")
    # User then dismisses a follow-up dialog.
    controller._state_cancelled("user_cancelled_after_error")
    controller.write_session_summary()
    summary = _summary_lines(gui)
    # Cancel takes precedence — we don't want to surface a generic
    # "Session failed" when the user is the one who said stop.
    assert any("Cancelled by user" in line for line in summary)
