"""Session state machine for enforcing pipeline transitions."""

from collections.abc import Callable
from enum import Enum, auto


class SessionState(Enum):
    INIT = auto()
    SCANNED = auto()
    RIPPED = auto()
    STABILIZED = auto()
    VALIDATED = auto()
    MOVED = auto()
    COMPLETED = auto()
    FAILED = auto()


class SessionStateMachine:
    def __init__(self, debug: bool = False, logger: Callable[[str], None] | None = None):
        self.state = SessionState.INIT
        self.debug = bool(debug)
        self.logger = logger
        # Tracks the most recent fail/cancel reason so callers
        # introspecting the SM can distinguish a true error from a
        # user cancellation.  Reset on transition + reset.
        self.fail_reason: str | None = None
        # Set by ``cancel()``.  ``write_session_summary`` reads this
        # to emit "Cancelled by user" instead of "Session failed" or
        # the misleading "All discs completed successfully" (the
        # latter was the v1-blocker the smoke bot caught 2026-05-04).
        self.was_cancelled: bool = False
        self.allowed: dict[SessionState, list[SessionState]] = {
            SessionState.INIT: [SessionState.SCANNED, SessionState.FAILED],
            SessionState.SCANNED: [SessionState.RIPPED, SessionState.FAILED],
            SessionState.RIPPED: [SessionState.STABILIZED, SessionState.FAILED],
            SessionState.STABILIZED: [SessionState.VALIDATED, SessionState.FAILED],
            SessionState.VALIDATED: [SessionState.MOVED, SessionState.FAILED],
            SessionState.MOVED: [SessionState.COMPLETED, SessionState.FAILED],
        }

    def _emit(self, message: str) -> None:
        if self.debug and self.logger:
            self.logger(message)

    def transition(self, new_state: SessionState) -> None:
        if self.state == SessionState.FAILED:
            return

        if new_state not in self.allowed.get(self.state, []):
            raise RuntimeError(
                f"Invalid transition: {self.state.name} -> {new_state.name}"
            )

        self._emit(f"[STATE] {self.state.name} -> {new_state.name}")
        self.state = new_state

    def fail(self, reason: str | None = None) -> None:
        """Transition to FAILED for a real error.

        Note: this does NOT set ``was_cancelled``.  Callers who want
        to mark a user-driven cancellation should use ``cancel()``
        instead so the summary can distinguish "rip failed" from
        "user bailed at a dialog".
        """
        if self.debug and reason:
            self._emit(f"[STATE] FAIL: {reason}")
        self.state = SessionState.FAILED
        self.fail_reason = reason

    def cancel(self, reason: str | None = None) -> None:
        """Transition to FAILED to mark a user cancellation.

        Behaviorally identical to ``fail()`` — the SM still ends in
        FAILED so any downstream check that gates on
        ``state != FAILED`` keeps working — but the ``was_cancelled``
        flag lets the session-summary writer emit "Cancelled by user"
        rather than "Session failed" or the misleading
        "All discs completed successfully".

        Pinned by ``tests/test_controller_cancel_class.py`` (added
        2026-05-04) — the smoke bot caught the SM-leak class where
        cancel-return paths in ``_run_disc_inner`` left the SM at
        INIT, ``sm.complete()`` then forced it to COMPLETED, and the
        summary falsely claimed success.
        """
        self._emit(f"[STATE] CANCEL: {reason or 'user_cancelled'}")
        self.state = SessionState.FAILED
        self.fail_reason = reason or "user_cancelled"
        self.was_cancelled = True

    def complete(self) -> None:
        """Force COMPLETED if not already failed.

        Used by flows (e.g. _run_disc) that don't track every intermediate
        state transition but still need write_session_summary to take the
        correct code path at the end of a successful session.
        """
        if self.state != SessionState.FAILED:
            self._emit(f"[STATE] {self.state.name} -> COMPLETED (forced)")
            self.state = SessionState.COMPLETED

    def is_success(self) -> bool:
        return self.state == SessionState.COMPLETED

    def is_cancelled(self) -> bool:
        """True iff the session ended in a user cancellation
        (``cancel()`` was called) rather than a true failure or
        clean completion.  ``write_session_summary`` reads this to
        pick the right summary message."""
        return self.was_cancelled
