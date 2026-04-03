"""Naming helpers for workflow-level title and preview naming behavior."""

import re
from datetime import datetime


def normalize_naming_mode(mode_value):
    """Normalize configured naming mode including backward-compatible aliases."""
    mode = (mode_value or "timestamp").strip().lower()
    if mode in {"auto-title", "disc-title"}:
        return "disc-title"
    if mode in {"auto-title+timestamp", "disc-title+timestamp"}:
        return "disc-title+timestamp"
    return "timestamp"


def parse_metadata_id(raw):
    """Parse a user-entered metadata provider ID into a Jellyfin tag.

    Accepts formats like:
        tmdbid-12345, tmdb-12345, tmdb:12345, 12345 (assumed tmdb)
        imdbid-tt1234567, imdb-tt1234567, tt1234567
        tvdbid-79168, tvdb-79168, tvdb:79168

    Returns a string like ``[tmdbid-12345]`` or ``""`` if input is empty/invalid.
    """
    if not raw:
        return ""
    raw = raw.strip().strip("[]")
    if not raw:
        return ""

    # Already in Jellyfin format: tmdbid-NNN / imdbid-ttNNN / tvdbid-NNN
    m = re.match(r"^(tmdbid|imdbid|tvdbid)-(\S+)$", raw, re.IGNORECASE)
    if m:
        return f"[{m.group(1).lower()}-{m.group(2)}]"

    # Shorthand: tmdb-NNN / imdb-ttNNN / tvdb-NNN or with colon
    m = re.match(r"^(tmdb|imdb|tvdb)[:\-](\S+)$", raw, re.IGNORECASE)
    if m:
        return f"[{m.group(1).lower()}id-{m.group(2)}]"

    # Bare IMDb ID: tt followed by digits
    m = re.match(r"^(tt\d+)$", raw, re.IGNORECASE)
    if m:
        return f"[imdbid-{m.group(1)}]"

    # Bare integer: assume TMDB (most common)
    m = re.match(r"^(\d+)$", raw)
    if m:
        return f"[tmdbid-{m.group(1)}]"

    return ""


def build_movie_folder_name(title_clean, year, metadata_id=""):
    """Build a Jellyfin-compatible movie folder name.

    ``title_clean`` must already be passed through ``clean_name()``.
    ``metadata_id`` is the raw user input (parsed by ``parse_metadata_id``).
    """
    tag = parse_metadata_id(metadata_id)
    base = f"{title_clean} ({year})"
    if tag:
        base = f"{base} {tag}"
    return base


def build_tv_folder_name(title_clean, metadata_id=""):
    """Build a Jellyfin-compatible TV series folder name.

    ``title_clean`` must already be passed through ``clean_name()``.
    """
    tag = parse_metadata_id(metadata_id)
    if tag:
        return f"{title_clean} {tag}"
    return title_clean


def resolve_naming_mode(cfg):
    """Resolve naming mode from config with fallback for legacy key names."""
    mode_value = cfg.get("opt_naming_mode", cfg.get("opt_fallback_title_mode", "timestamp"))
    return normalize_naming_mode(mode_value)


def build_fallback_title(cfg, make_temp_title_fn, clean_name_fn,
                         choose_best_title_fn, disc_titles=None,
                         disc_name=None):
    """Build fallback title string based on the active naming mode.

    ``disc_name`` is the CINFO disc title from MakeMKV — preferred over
    per-title TINFO names when available and non-generic.
    """
    mode = resolve_naming_mode(cfg)
    timestamp_title = make_temp_title_fn()

    if mode == "timestamp":
        return timestamp_title

    # Prefer CINFO disc name (disc-level) over TINFO title name
    if disc_name:
        raw = clean_name_fn(disc_name.strip())
        low = raw.lower() if raw else ""
        is_generic = (low.startswith("title ") or low.startswith("title_")
                      or low.startswith("disc") or not low)
        if not is_generic:
            if mode == "disc-title+timestamp":
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                return clean_name_fn(f"{raw}_{ts}")
            return raw

    # Fall back to best title from TINFO
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
