"""Session result normalization helpers."""


def normalize_session_result(abort, failed_titles, files, valid_files):
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
