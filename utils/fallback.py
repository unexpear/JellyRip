"""Centralized fallback decision policy."""


def handle_fallback(controller, reason, fallback_fn):
    controller.log(f"WARNING: {reason}")

    strict_mode = bool(controller.engine.cfg.get("opt_strict_mode", False))
    if strict_mode:
        controller.log("Strict mode enabled — aborting.")
        controller._record_fallback_event(reason, accepted=False, strict=True)
        return None

    if not controller.gui.ask_yesno(f"{reason}\n\nUse fallback?"):
        controller.log("User declined fallback.")
        controller._record_fallback_event(reason, accepted=False, strict=False)
        return None

    controller.log("Fallback accepted — executing.")
    controller._record_fallback_event(reason, accepted=True, strict=False)
    return fallback_fn()
