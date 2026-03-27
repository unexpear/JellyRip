"""Naming helpers for workflow-level title and preview naming behavior."""

from datetime import datetime


def normalize_naming_mode(mode_value):
    """Normalize configured naming mode including backward-compatible aliases."""
    mode = (mode_value or "timestamp").strip().lower()
    if mode in {"auto-title", "disc-title"}:
        return "disc-title"
    if mode in {"auto-title+timestamp", "disc-title+timestamp"}:
        return "disc-title+timestamp"
    return "timestamp"


def resolve_naming_mode(cfg):
    """Resolve naming mode from config with fallback for legacy key names."""
    mode_value = cfg.get("opt_naming_mode", cfg.get("opt_fallback_title_mode", "timestamp"))
    return normalize_naming_mode(mode_value)


def build_fallback_title(cfg, make_temp_title_fn, clean_name_fn,
                         choose_best_title_fn, disc_titles=None):
    """Build fallback title string based on the active naming mode."""
    mode = resolve_naming_mode(cfg)
    timestamp_title = make_temp_title_fn()

    if mode == "timestamp":
        return timestamp_title

    best = None
    if disc_titles:
        best, _ = choose_best_title_fn(disc_titles, require_valid=True)
        if not best:
            best, _ = choose_best_title_fn(disc_titles)

    if not best:
        return timestamp_title

    raw = clean_name_fn(best.get("name", "").strip())
    if not raw or raw.lower().startswith("title "):
        raw = f"Disc_Title_{best.get('id', 0) + 1}"

    if mode == "disc-title+timestamp":
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return clean_name_fn(f"{raw}_{ts}")

    return raw


def build_naming_preview_text(mode_label_value, sample_title, sample_suffix):
    """Build a human-readable naming preview example for settings UI."""
    mode = normalize_naming_mode(mode_label_value)
    if mode == "disc-title":
        return f"Example: {sample_title} [{sample_title}]"
    if mode == "disc-title+timestamp":
        return f"Example: {sample_title} [{sample_title}_{sample_suffix}]"
    return f"Example: {sample_title} [{sample_suffix}]"
