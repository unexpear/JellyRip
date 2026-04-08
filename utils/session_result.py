"""Session result normalization helpers."""

from collections.abc import Sequence
from typing import Any


# CRITICAL:
# This function defines ALL success criteria for rip sessions.
# Do not replicate this logic elsewhere.
def normalize_session_result(
    abort: bool,
    failed_titles: Sequence[Any] | None,
    files: Sequence[str],
    valid_files: Sequence[str],
) -> bool:
    """Return deterministic all-or-nothing session success state."""
    if abort:
        return False
    if failed_titles:
        return False
    if not files:
        return False
    if len(valid_files) != len(files):
        return False
    return True


__all__ = ["normalize_session_result"]
