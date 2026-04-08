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
        if self.debug and reason:
            self._emit(f"[STATE] FAIL: {reason}")
        self.state = SessionState.FAILED

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
