"""Shared modal dialog helpers.

Phase 3h (2026-05-04) — ``ask_yes_no`` is no longer reachable on the
shipping (PySide6) UI path; the Qt shell uses
``gui_qt.dialogs.ask.ask_yesno``. The function is kept here only so
external tools / scripts that imported ``from ui.dialogs import
ask_yes_no`` don't break — the tkinter import was moved inside the
function body so that importing this module no longer requires
tkinter to be present.

``friendly_error`` is a pure-string helper with no GUI coupling and
is the live function in this module on the Qt path.
"""

from __future__ import annotations


def ask_yes_no(title: str, message: str, *, parent=None, icon: str | None = None) -> bool:
    """Tkinter-side yes/no dialog (legacy callers only).

    Lazy-imports ``tkinter.messagebox`` so that consumers of
    ``friendly_error`` don't pull tkinter at module-load time. On a
    Qt-only build (no tkinter installed) this raises ``ImportError``
    when actually called — but no live code path on the Qt UI calls
    it. New code should use ``gui_qt.dialogs.ask.ask_yesno``.
    """
    from tkinter import messagebox  # lazy — tkinter is retired

    kwargs = {"parent": parent}
    if icon:
        kwargs["icon"] = icon
    return bool(messagebox.askyesno(title, message, **kwargs))


def friendly_error(base_message: str, exception: BaseException | None = None) -> str:
    """Build a user-facing error dialog body with recovery guidance.

    Closes Finding #8 in
    `docs/ux-copy-and-accessibility-plan.md` — WCAG 3.3.3 (Error
    Suggestion) wants error messages to identify *both* what failed
    *and* what the user can try next. The prior pattern was
    `f"Could not save expert profile:\\n{exc}"` — raw-dumps the
    exception text into the dialog body, which is scary, redundant
    with the developer-facing log line, and gives the user no
    recovery path.

    This helper takes a base message describing what failed and
    optionally the exception. It returns a formatted dialog body
    with the base message followed by a targeted recovery suggestion
    for known exception types. **The raw exception text is NOT
    included in the returned message** — callers should already be
    logging the exception separately via `controller.log()` for
    the developer-facing log file path.

    Recovery guidance for unknown exception types points the user at
    the session log for technical detail, since that's where the
    raw exception text lives.

    Args:
        base_message: The user-facing description of what failed.
            Should be a complete sentence ending with a period
            (e.g. ``"Could not save the transcode profile."``).
            May include path or context info on additional lines
            (e.g. ``"Could not open path:\\nC:/foo"``) — the
            recovery text appends after a blank line.
        exception: The caught exception, if any. Type-dispatched to
            map to recovery text. May be ``None``, in which case
            only the base message is returned.

    Returns:
        A formatted multi-line string suitable for messagebox body.
    """
    parts = [base_message.rstrip()]
    if exception is not None:
        recovery = _recovery_text_for(exception)
        if recovery:
            parts.append("")  # blank line separator
            parts.append(recovery)
    return "\n".join(parts)


def _recovery_text_for(exception: BaseException) -> str:
    """Map exception type and OS errno to user-facing recovery text.

    The mapping is deliberately conservative — broad categories that
    most users can act on, not exhaustive technical detail. Unknown
    types fall through to a generic "see session log" hint.
    """
    if isinstance(exception, PermissionError):
        return (
            "Permission denied. Check that the file or folder isn't "
            "open in another program, and that you have write access "
            "to the destination."
        )
    if isinstance(exception, FileNotFoundError):
        return (
            "Path not found. Check the location, or create it manually "
            "and try again."
        )
    if isinstance(exception, IsADirectoryError):
        return (
            "Expected a file but found a folder at this path. Pick a "
            "different name, or remove the existing folder first."
        )
    if isinstance(exception, NotADirectoryError):
        return (
            "Expected a folder but found a file at this path. Pick a "
            "different location."
        )
    # NB: TimeoutError and ConnectionError are subclasses of OSError
    # in Python 3.11+, so we must check the more-specific types first.
    # Without this ordering, a TimeoutError would match the OSError
    # branch and produce a generic filesystem-error message.
    if isinstance(exception, (TimeoutError, ConnectionError)):
        return (
            "A network or connection error occurred. Check your "
            "network and try again."
        )
    if isinstance(exception, OSError):
        errno = getattr(exception, "errno", None)
        # ENOSPC = 28 — out of disk space
        if errno == 28:
            return (
                "Out of disk space on the destination drive. Free up "
                "space and try again."
            )
        # ENOTEMPTY = 39 (Linux) / 41 (Windows in some cases) — directory not empty
        if errno in (39, 41, 17):
            return (
                "The destination folder isn't empty. Either pick a "
                "different path, or empty the existing folder first."
            )
        # EACCES = 13 — usually surfaces as PermissionError but can leak as OSError
        if errno == 13:
            return (
                "Permission denied. Check that the file isn't open in "
                "another program, and that you have write access."
            )
        # Generic OSError fallback — point at the session log for the
        # actual errno detail rather than dumping it into the user
        # dialog.
        return (
            "A filesystem error occurred. Check the session log for "
            "technical details, or try a different path."
        )
    if isinstance(exception, ValueError):
        return (
            "Invalid value. Check the session log for details."
        )
    # Final fallback: anything we don't have a tailored hint for.
    # The session log carries the raw exception text for the
    # developer-facing path; users only see the generic recovery
    # hint here.
    return (
        "Something went wrong. Check the session log for technical "
        "details."
    )
              