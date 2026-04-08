"""Centralized fallback decision policy."""

from collections.abc import Callable
from typing import Any, Protocol


class FallbackController(Protocol):
    gui: Any
    engine: Any

    def log(self, message: str) -> None: ...
    def _record_fallback_event(self, reason: str, accepted: bool, strict: bool) -> None: ...


def handle_fallback(controller: FallbackController, reason: str, fallback_fn: Callable[[], object]) -> object | None:
    record_event = getattr(controller, "_record_fallback_event")
    controller.log(f"WARNING: {reason}")

    strict_mode = bool(controller.engine.cfg.get("opt_strict_mode", False))
    if strict_mode:
        controller.log("Strict mode enabled — aborting.")
        record_event(reason, accepted=False, strict=True)
        return None

    if not controller.gui.ask_yesno(f"{reason}\n\nUse fallback?"):
        controller.log("User declined fallback.")
        record_event(reason, accepted=False, strict=False)
        return None

    controller.log("Fallback accepted — executing.")
    record_event(reason, accepted=True, strict=False)
    return fallback_fn()
