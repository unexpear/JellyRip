from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from controller.session import SessionHelpers
from shared.runtime import DEFAULTS


class _Callbacks:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def append_log(self, msg: str) -> None:
        self.messages.append(msg)


class _Engine:
    def __init__(self, cfg: dict[str, object]) -> None:
        self.cfg = cfg
        self.writes: list[tuple[str, datetime, list[str]]] = []

    def write_session_log(
        self,
        log_file: str,
        start_time: datetime,
        session_log: list[str],
        on_log,
    ) -> None:
        self.writes.append((log_file, start_time, list(session_log)))


def _helpers(cfg: dict[str, object]) -> tuple[SessionHelpers, _Engine]:
    engine = _Engine(cfg)
    controller = SimpleNamespace(
        engine=engine,
        start_time=datetime(2026, 4, 30, 10, 0, 0),
        session_log=["line one"],
        session_report=[],
    )
    return SessionHelpers(_Callbacks(), controller), engine


def test_save_logs_default_is_enabled() -> None:
    assert DEFAULTS["opt_save_logs"] is True


def test_settings_exposes_save_logs_toggle() -> None:
    """Phase 3h note: pre-2026-05-04 this test asserted the toggle
    text appeared in ``gui/main_window.py``'s tkinter settings
    dialog.  That dialog was retired alongside the rest of
    ``gui/``.  The PySide6 settings dialog ships only the
    Appearance tab today (see ``gui_qt/settings/tab_appearance.py``);
    the Logs / Everyday tab with this toggle is pending — see
    ``docs/handoffs/phase-3d-port-settings-tabs.md``.

    For now we pin the contract that matters at the cfg layer:
    the ``opt_save_logs`` key exists in DEFAULTS with the right
    default.  When the Logs / Everyday tab lands, this test will
    grow a widget-level assertion against it.
    """
    assert "opt_save_logs" in DEFAULTS
    assert DEFAULTS["opt_save_logs"] is True


def test_flush_log_writes_when_log_saving_enabled() -> None:
    helpers, engine = _helpers(
        {"opt_save_logs": True, "log_file": r"C:\Logs\session-log"}
    )

    helpers.flush_log()

    assert len(engine.writes) == 1
    assert engine.writes[0][0] == r"C:\Logs\session-log.txt"


def test_flush_log_skips_disk_write_when_log_saving_disabled() -> None:
    helpers, engine = _helpers(
        {"opt_save_logs": False, "log_file": r"C:\Logs\session-log"}
    )

    helpers.flush_log()

    assert engine.writes == []
