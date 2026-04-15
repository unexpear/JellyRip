"""Compatibility no-op diagnostics layer for the non-AI workspace."""

from __future__ import annotations

import json
import tempfile
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional


GuiLogFn = Callable[[str], None]


@dataclass
class DiagnosticEvent:
    timestamp: str
    level: str
    category: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    process_capture: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessCapture:
    command: list[str]
    start_time: str
    working_directory: str
    end_time: str = ""
    duration_seconds: float = 0.0
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    stall_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiagnosticsManager:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        gui_log_fn: GuiLogFn | None = None,
        session_dir: str | None = None,
        ring_buffer_size: int = 200,
    ) -> None:
        self._config = dict(config or {})
        self._gui_log_fn = gui_log_fn
        self._session_dir = str(session_dir or "")
        self._context: dict[str, Any] = {}
        self._events: deque[DiagnosticEvent] = deque(
            maxlen=max(1, int(ring_buffer_size))
        )
        self._mode = "off"

    def set_session_dir(self, session_dir: str) -> None:
        self._session_dir = str(session_dir or "")

    def update_context(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if value is not None:
                self._context[str(key)] = value

    def set_config(self, config: dict[str, Any]) -> None:
        self._config = dict(config or {})
        self._mode = "off"

    def set_mode(self, mode: str) -> None:
        _ = mode
        self._mode = "off"

    def get_status(self) -> dict[str, Any]:
        return {
            "state": "off",
            "mode": "off",
            "calls_made": 0,
            "calls_max": 0,
            "cloud": "disabled",
            "local": "disabled",
        }

    def test_backends(self) -> dict[str, str]:
        return {"cloud": "disabled", "local": "disabled"}

    def record(
        self,
        level: str,
        category: str,
        summary: str,
        details: dict[str, Any] | None = None,
        process_capture: ProcessCapture | dict[str, Any] | None = None,
    ) -> DiagnosticEvent:
        capture_data: dict[str, Any] | None
        if isinstance(process_capture, ProcessCapture):
            capture_data = process_capture.to_dict()
        elif isinstance(process_capture, dict):
            capture_data = dict(process_capture)
        else:
            capture_data = None

        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            level=str(level or "info"),
            category=str(category or "general"),
            summary=str(summary or ""),
            details=dict(details or {}),
            process_capture=capture_data,
        )
        self._events.append(event)
        return event

    def record_exception(
        self,
        exc: Exception,
        context: str = "",
        category: str = "error",
    ) -> DiagnosticEvent:
        label = str(context or "").strip()
        summary = str(exc)
        if label:
            summary = f"{label}: {summary}"
        return self.record(
            "error",
            category,
            summary,
            details={
                "exception_type": type(exc).__name__,
                "exception": str(exc),
                "context": label,
            },
        )

    def record_process(
        self,
        capture: ProcessCapture,
        success: bool,
        category: str = "process",
    ) -> DiagnosticEvent:
        return self.record(
            "info" if success else "warning",
            category,
            (
                "Process completed successfully"
                if success
                else "Process finished with errors"
            ),
            details={"success": bool(success)},
            process_capture=capture,
        )

    def dump_ring_buffer(self, path: Optional[str] = None) -> str:
        target = str(path or "").strip()
        if not target:
            base_dir = (
                Path(self._session_dir)
                if self._session_dir
                else Path(tempfile.gettempdir())
            )
            target = str(base_dir / "session.diagnostics.json")

        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": self._mode,
            "context": dict(self._context),
            "events": [event.to_dict() for event in self._events],
        }
        target_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return str(target_path)

    def generate_session_summary(self) -> Optional[str]:
        return None


_DIAGNOSTICS_MANAGER: DiagnosticsManager | None = None


def init_diagnostics(
    config: dict[str, Any] | None = None,
    gui_log_fn: GuiLogFn | None = None,
    session_dir: str | None = None,
) -> DiagnosticsManager:
    global _DIAGNOSTICS_MANAGER
    _DIAGNOSTICS_MANAGER = DiagnosticsManager(
        config=config,
        gui_log_fn=gui_log_fn,
        session_dir=session_dir,
    )
    return _DIAGNOSTICS_MANAGER


def get_diagnostics() -> Optional[DiagnosticsManager]:
    return _DIAGNOSTICS_MANAGER


def diag_record(
    level: str,
    category: str,
    summary: str,
    details: dict[str, Any] | None = None,
    process_capture: ProcessCapture | dict[str, Any] | None = None,
) -> Optional[DiagnosticEvent]:
    mgr = get_diagnostics()
    if mgr is None:
        return None
    try:
        return mgr.record(level, category, summary, details, process_capture)
    except Exception:
        return None


def diag_exception(
    exc: Exception,
    context: str = "",
    category: str = "error",
) -> Optional[DiagnosticEvent]:
    mgr = get_diagnostics()
    if mgr is None:
        return None
    try:
        return mgr.record_exception(exc, context=context, category=category)
    except Exception:
        return None


def diag_process(
    capture: ProcessCapture,
    success: bool,
    category: str = "process",
) -> Optional[DiagnosticEvent]:
    mgr = get_diagnostics()
    if mgr is None:
        return None
    try:
        return mgr.record_process(capture, success=success, category=category)
    except Exception:
        return None
