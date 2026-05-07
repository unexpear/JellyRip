"""Section 8 — failure-mode regression tests.

Pins the app's defenses against three real-world environment
failures the smoke bot could not exercise live without destroying
test data:

1. **Corrupt QSS theme file** — non-UTF-8 binary content masquerading
   as a ``.qss`` file (e.g. someone copied a JPEG over the theme).
   The loader must surface a clear ``FileNotFoundError`` rather than
   propagating ``UnicodeDecodeError`` — that distinction is what
   keeps ``gui_qt/app.py`` from crashing on startup before the
   window appears.  An invalid-but-utf8 QSS (bad syntax) is NOT
   tested here — Qt's ``setStyleSheet`` swallows parse errors and
   degrades to default styling, which is acceptable behavior.

2. **Locked / permission-denied QSS file** — same outcome required
   as (1): friendly ``FileNotFoundError`` with available themes
   listed, no startup crash.  Simulated by making the file
   unreadable and patching ``Path.read_text`` to raise
   ``PermissionError``.  Direct chmod tests don't work reliably on
   Windows.

3. **Disk-space block** — ``check_disk_space`` returns ``"block"``
   when free is below the hard floor, ``"warn"`` when between hard
   floor and required, and ``"ok"`` otherwise.  Already covered
   exhaustively in ``test_disk_space_pre_checks.py``; this file
   adds one *integration* pin: ``shutil.disk_usage`` raising
   ``OSError`` (offline network share, vanished mount point) must
   degrade to ``"ok"`` rather than crashing the workflow.  Pre-rip
   crashes are worse than missing the warning.

A fourth finding (the ``validate_tools`` orphan-call gap) is
**fixed** as of 2026-05-04 evening: the launcher now calls
``engine.validate_tools()`` before every disc-touching workflow
and surfaces the friendly "MakeMKV not found.  Please check
Settings." dialog instead of the cryptic ``[Errno 2]`` log line.
Behavior pinned in
``tests/test_pyside6_workflow_launchers.py`` (the section under
"Tool-path pre-flight").  This file's last test inverts to a
guard: callers list must include the launcher.

Behavior-first.  No real ``QApplication``, no real disk, no real
binaries.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gui_qt import theme as theme_module


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


class _FakeApp:
    """Captures the QSS that would have been pushed to QApplication."""

    def __init__(self) -> None:
        self.last_stylesheet: str | None = None

    def setStyleSheet(self, qss: str) -> None:  # noqa: N802 (Qt convention)
        self.last_stylesheet = qss


# --------------------------------------------------------------------------
# (1) Corrupt QSS — binary content
# --------------------------------------------------------------------------


def test_corrupt_qss_binary_content_raises_friendly_filenotfound(
    tmp_path, monkeypatch,
):
    """A non-empty file with non-UTF-8 binary content must NOT
    propagate ``UnicodeDecodeError`` — that would crash startup
    before the main window appears.  Loader normalizes to
    ``FileNotFoundError`` with the available-themes hint so the
    caller in ``gui_qt/app.py`` can fall back cleanly."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    # Write JPEG-like bytes — invalid UTF-8.
    (fake_qss_dir / "broken.qss").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
    (fake_qss_dir / "good.qss").write_text(
        "QPushButton { color: #58a6ff; }",
        encoding="utf-8",
    )
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    app = _FakeApp()
    with pytest.raises(FileNotFoundError) as excinfo:
        theme_module.load_theme(app, "broken")

    msg = str(excinfo.value)
    assert "broken" in msg, "error message names the broken theme"
    assert "good" in msg, (
        "error message lists available themes so the user can "
        "switch to one without going to the docs"
    )
    assert app.last_stylesheet is None, (
        "no stylesheet should be applied on failure — caller falls "
        "back to default look"
    )


def test_corrupt_qss_chains_original_exception_for_diagnostics(
    tmp_path, monkeypatch,
):
    """``raise FileNotFoundError(...) from exc`` chains the
    underlying ``UnicodeDecodeError`` so debug logging /
    ``diag_exception`` can still capture root cause without
    surfacing it to the user."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    (fake_qss_dir / "broken.qss").write_bytes(b"\xff\xfe\x00\x00")
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    with pytest.raises(FileNotFoundError) as excinfo:
        theme_module.load_theme(_FakeApp(), "broken")

    cause = excinfo.value.__cause__
    assert cause is not None, "must chain underlying exception via 'from'"
    assert isinstance(cause, (UnicodeDecodeError, OSError))


# --------------------------------------------------------------------------
# (2) Locked / permission-denied QSS
# --------------------------------------------------------------------------


def test_locked_qss_permission_denied_raises_friendly_filenotfound(
    tmp_path, monkeypatch,
):
    """An unreadable .qss (locked by another process, NTFS ACL deny,
    network share off-line) must NOT propagate ``PermissionError``.
    Same normalization as (1)."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    qss_path = fake_qss_dir / "locked.qss"
    qss_path.write_text("/* placeholder */", encoding="utf-8")
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    # Simulate the read failure by patching Path.read_text — chmod
    # is unreliable on Windows for tests.
    real_read_text = Path.read_text

    def fake_read_text(self, *args, **kwargs):
        if self == qss_path:
            raise PermissionError(
                f"[Errno 13] Permission denied: {qss_path}"
            )
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    app = _FakeApp()
    with pytest.raises(FileNotFoundError) as excinfo:
        theme_module.load_theme(app, "locked")

    msg = str(excinfo.value)
    assert "locked" in msg
    assert "could not be read" in msg.lower() or "PermissionError" in msg


# --------------------------------------------------------------------------
# (3) Disk space — graceful degradation when shutil.disk_usage fails
# --------------------------------------------------------------------------


def test_check_disk_space_offline_share_degrades_to_ok(monkeypatch, tmp_path):
    """``shutil.disk_usage`` raising ``OSError`` (e.g. offline
    network share) must NOT crash the workflow.  ``check_disk_space``
    swallows the error, logs a warning, and returns ``"ok"`` so the
    rip can proceed.

    Rationale: a missing pre-flight warning is a worse-case nuisance
    (rip might fail mid-way with a real ENOSPC).  An uncaught
    exception is a workflow-blocking crash.  Trade-off favors
    proceeding."""
    from engine.ripper_engine import RipperEngine
    import shutil

    cfg = {
        "opt_hard_block_gb": 20,
        "opt_warn_low_space": True,
    }
    engine = RipperEngine(cfg)

    def fake_disk_usage(_path):
        raise OSError("[WinError 53] The network path was not found")

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    log_lines: list[str] = []

    status, free, required = engine.check_disk_space(
        str(tmp_path), 50 * (1024**3), log_lines.append, timeout=2.0,
    )

    assert status == "ok", (
        "OSError from disk_usage must degrade to 'ok' — never block "
        "the rip on a broken pre-check"
    )
    assert free == 0
    assert required == 50 * (1024**3)
    assert any("could not check disk space" in line for line in log_lines)


def test_check_disk_space_block_when_below_hard_floor(monkeypatch, tmp_path):
    """``free < hard_floor`` (default 20 GB) returns ``"block"`` so
    the controller can refuse the rip and show a clear error.  Pinned
    here because Section 8 specifically asks how the workflow
    handles 'disk full' — and the answer is: pre-check blocks it."""
    from engine.ripper_engine import RipperEngine
    import shutil

    cfg = {"opt_hard_block_gb": 20}
    engine = RipperEngine(cfg)

    class FakeUsage:
        free = 5 * (1024**3)  # 5 GB free, below 20 GB hard floor

    monkeypatch.setattr(shutil, "disk_usage", lambda _p: FakeUsage)

    log_lines: list[str] = []
    status, free, required = engine.check_disk_space(
        str(tmp_path), 30 * (1024**3), log_lines.append,
    )

    assert status == "block"
    assert free == 5 * (1024**3)
    assert required == 30 * (1024**3)


# --------------------------------------------------------------------------
# (4) Documentation pin — validate_tools() orphan-call gap
# --------------------------------------------------------------------------


def test_validate_tools_is_wired_into_workflow_launcher():
    """``RipperEngine.validate_tools()`` is called from a workflow
    entry point.  As of 2026-05-04 evening, the
    ``WorkflowLauncher`` runs the pre-flight on every disc-touching
    workflow click and surfaces the friendly error dialog instead
    of the cryptic ``[Errno 2]`` the user used to see.

    This test pins the wiring at the *file* level — it doesn't
    drive the actual gate (full integration tests live in
    ``tests/test_pyside6_workflow_launchers.py`` under "Tool-path
    pre-flight").  Its job is to fail fast if a future refactor
    accidentally rips the gate out.

    The assertion intentionally allows multiple callers (e.g.
    Settings dialog might also call validate_tools to update its
    "tool found" indicator) — the only thing that matters is that
    at least one caller exists in the launcher path."""
    from engine.ripper_engine import RipperEngine
    import inspect

    assert hasattr(RipperEngine, "validate_tools")
    sig = inspect.signature(RipperEngine.validate_tools)
    assert list(sig.parameters) == ["self"], (
        "if signature changes, the launcher wiring needs review too"
    )

    # The launcher MUST call it (this is the contract being pinned).
    repo_root = Path(__file__).resolve().parent.parent
    launcher_path = repo_root / "gui_qt" / "workflow_launchers.py"
    launcher_text = launcher_path.read_text(encoding="utf-8")
    assert "validate_tools" in launcher_text, (
        "WorkflowLauncher no longer calls validate_tools — the "
        "orphan-call gap from Section 8 has regressed.  Re-wire it "
        "before the next release."
    )
