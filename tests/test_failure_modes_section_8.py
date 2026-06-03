"""Section 8 — failure-mode regression tests.

Pins the app's defenses against three real-world environment
failures the smoke bot could not exercise live without destroying
test data:

1. **Unloadable theme** — themes render from color tokens at runtime,
   so the old "corrupt .qss file on disk" failure can't happen for
   built-ins.  The modern equivalents are an unknown theme id (e.g. a
   saved custom theme the user deleted) or a custom theme whose JSON is
   corrupt.  ``load_theme`` must surface a clear ``FileNotFoundError``
   listing the available themes — never crash startup before the
   window appears.

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
# (1) Unloadable theme — unknown id / deleted custom / corrupt custom JSON
# --------------------------------------------------------------------------


def test_unknown_theme_raises_friendly_filenotfound():
    """Themes render from color tokens at runtime, so the old "corrupt
    .qss file" failure can't happen for built-ins.  The modern
    equivalent is a theme id that resolves to nothing (e.g. a saved
    custom theme the user deleted).  ``load_theme`` must surface a
    friendly ``FileNotFoundError`` listing the available themes —
    never crash startup before the window appears."""
    app = _FakeApp()
    with pytest.raises(FileNotFoundError) as excinfo:
        theme_module.load_theme(app, "no_such_theme")

    msg = str(excinfo.value)
    assert "no_such_theme" in msg, "error names the missing theme"
    assert "dark_github" in msg, (
        "error lists available themes so the user can switch without "
        "going to the docs"
    )
    assert app.last_stylesheet is None, (
        "no stylesheet applied on failure — caller falls back to default"
    )


def test_corrupt_custom_theme_json_degrades_gracefully(tmp_path, monkeypatch):
    """A custom theme whose JSON file is corrupt must not crash the
    loader: ``custom_themes.get_custom`` returns ``None`` for
    unparseable JSON, so ``load_theme`` degrades to the same friendly
    ``FileNotFoundError`` as an unknown theme — no stylesheet applied."""
    from gui_qt import custom_themes

    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "custom_broken.json").write_bytes(
        b"\xff\xd8\xff\xe0 not valid json"
    )
    monkeypatch.setattr(custom_themes, "themes_dir", lambda: themes_dir)

    app = _FakeApp()
    with pytest.raises(FileNotFoundError):
        theme_module.load_theme(app, "custom_broken")
    assert app.last_stylesheet is None


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
