"""Parsing utilities implementation."""

import os
import re
import shlex

from shared.runtime import (  # pyright: ignore[reportMissingImports]
    _duration_debug_warn,
    _safe_int_debug_warn,
)

# Whitelist of MakeMKV flags that are allowed in user-configurable args.
# This prevents command injection via opt_makemkv_global_args, opt_makemkv_info_args, opt_makemkv_rip_args.
_ALLOWED_MAKEMKV_FLAGS = {
    "--cache", "--noscan", "--directio", "--minlength", "--help", "--version",
}


def parse_episode_names(name_input):
    if not name_input:
        return []

    if '",' in name_input or name_input.count('"') >= 2:
        return [
            x.strip().strip('"')
            for x in re.split(r'",\s*', name_input)
        ]
    return [x.strip() for x in name_input.split(",")]


def _normalize_title_part(s):
    """Collapse internal whitespace and strip surrounding whitespace/quotes."""
    s = s.strip().strip('"')
    s = re.sub(r'\s+', ' ', s)
    return s


def parse_ordered_titles(name_input):
    """Parse ordered title lists for multi-disc dump naming.

    Accepts comma-separated values by default, and also accepts a
    spaced-hyphen separator like "Title A - Title B - Title C".

    Case is preserved but whitespace is normalized: leading/trailing spaces
    are stripped, internal runs of spaces are collapsed to one, and any
    number of spaces around the ' - ' separator are accepted.
    """
    if not name_input:
        return []

    text = str(name_input).strip()
    if not text:
        return []

    if '","' in text or text.count('"') >= 2:
        parts = [
            _normalize_title_part(x)
            for x in re.split(r'",\s*', text)
        ]
        return [p for p in parts if p]

    # Prefer comma lists. If no comma is present, allow spaced hyphen
    # delimiters so users can enter: "Toony - Herb - Jeckel".
    # Accept any amount of whitespace around the dash (\s*-\s* guarded by
    # requiring at least one whitespace on at least one side), so that
    # "Title 1  -  Title 2" and "Title 1 - Title 2" both split correctly
    # while "Spider-Man" (no surrounding whitespace) is kept intact.
    if "," in text:
        raw_parts = text.split(",")
    elif re.search(r"\s+-\s*|\s*-\s+", text):
        raw_parts = re.split(r"\s+-\s*|\s*-\s+", text)
    else:
        raw_parts = [text]

    parts = [_normalize_title_part(x) for x in raw_parts]
    return [p for p in parts if p]


def parse_duration_to_seconds(s):
    """
    Convert MakeMKV duration string to integer seconds.
    Handles H:MM:SS and M:SS formats. Returns 0 on any parse failure.

    MakeMKV reports duration from playlist metadata, not actual playback.
    Relative comparisons between titles on the same disc are reliable.
    Absolute values should not be treated as ground truth.
    """
    try:
        s = str(s).strip()
        if not s or ":" not in s:
            _duration_debug_warn(s)
            return 0
        # Accept HH:MM:SS, H:MM:SS, M:SS, and fractional seconds like
        # 00:45:12.000 or 1:23:45.678 from some MakeMKV builds.
        raw_parts = s.split(":")
        try:
            parts = [float(p) for p in raw_parts]
        except ValueError:
            _duration_debug_warn(s)
            return 0
        if len(parts) == 3:
            h, m, sec = parts
        elif len(parts) == 2:
            h, m, sec = 0.0, parts[0], parts[1]
        else:
            _duration_debug_warn(s)
            return 0
        return int(h * 3600 + m * 60 + sec)
    except Exception:
        _duration_debug_warn(s)
        return 0


def safe_int(val):
    """
    Safely convert any value to integer.
    MakeMKV sometimes returns malformed data (e.g., chapter field
    contains '3.7 GB'). This extracts just the numeric part.
    Returns 0 on any parse failure.
    """
    try:
        # Strip whitespace and convert to string
        s = str(val).strip()
        if not s:
            return 0
        if "/" in s:
            # Ambiguous formats like "1/12" are not safe integer fields.
            _safe_int_debug_warn(val)
            return 0
        # Try direct int conversion first
        try:
            return int(s)
        except ValueError:
            # If that fails, try to extract just the numeric part
            # This handles cases like "3.7 GB" → extract 3
            match = re.search(r'-?\d+(?:\.\d+)?', s)
            if match:
                return int(float(match.group()))
            _safe_int_debug_warn(val)
            return 0
    except Exception:
        _safe_int_debug_warn(val)
        return 0


def parse_size_to_bytes(val):
    """Parse MakeMKV size values into integer bytes."""
    try:
        s = str(val).strip()
        if not s:
            return 0
        if s.isdigit():
            return int(s)

        # Accept variants like "3.7GB", "3,7 GB", "3.7 GiB", and values
        # with leading or trailing text (e.g. "Size: 3.7 GB").
        match = re.search(
            r'([\d.,]+)\s*([KMGTPE]?i?B)', s, re.IGNORECASE
        )
        if not match:
            return 0

        raw = match.group(1).strip().replace(" ", "")

        # Handle clear thousands-grouped forms early.
        if raw.count(",") > 1 and "." not in raw:
            raw = raw.replace(",", "")
        if raw.count(".") > 1 and "," not in raw:
            raw = raw.replace(".", "")

        if "," in raw and "." in raw:
            # Keep the last separator as decimal; strip the other as thousands.
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            # Disambiguate single comma: thousands group vs decimal separator.
            if raw.count(",") == 1:
                left, right = raw.split(",", 1)
                if left.isdigit() and right.isdigit() and len(right) == 3:
                    # Example: 5,000 -> 5000
                    raw = left + right
                elif len(right) <= 2:
                    # Ambiguous locale case (e.g. "1,23 GB") is treated as
                    # decimal-comma intentionally: 1.23 GB.
                    # Example: 3,7 -> 3.7
                    raw = raw.replace(",", ".")
                else:
                    raw = raw.replace(",", "")
            else:
                raw = raw.replace(",", "")
        elif raw.count(".") > 1:
            # Collapse thousands separators in dot-formatted strings.
            head, tail = raw.rsplit(".", 1)
            raw = head.replace(".", "") + "." + tail

        number = float(raw)
        # Handle both SI (decimal) and IEC (binary) units explicitly so
        # "3.7 GB" and "3.7 GiB" map to correct byte counts.
        unit = match.group(2).upper()
        multipliers = {
            "B":   1,
            "KB":  1000,       "KIB": 1024,
            "MB":  1000**2,    "MIB": 1024**2,
            "GB":  1000**3,    "GIB": 1024**3,
            "TB":  1000**4,    "TIB": 1024**4,
            "PB":  1000**5,    "PIB": 1024**5,
            "EB":  1000**6,    "EIB": 1024**6,
        }
        multiplier = multipliers.get(unit)
        if multiplier is None:
            return 0
        return int(number * multiplier)
    except Exception:
        return 0


def parse_cli_args(raw, on_log=None, label="args"):
    """Parse a CLI argument string into argv tokens, restricted to whitelisted flags.

    To prevent command injection attacks, only MakeMKV flags in the whitelist are allowed.
    Flag values (e.g., --cache=1024) are OK; tokens starting with unknown flags are dropped.
    """
    s = (raw or "").strip()
    if not s:
        return []
    try:
        tokens = shlex.split(s, posix=(os.name != "nt"))
    except Exception:
        if on_log:
            on_log(
                f"Warning: could not parse {label}; "
                f"falling back to simple split."
            )
        tokens = s.split()

    filtered = []
    dropped = []
    for tok in tokens:
        low = tok.lower()
        # Remove unsupported MakeMKV profile tokens
        if low.startswith(("+sel:", "-sel:")):
            dropped.append(tok)
            continue
        # Whitelist check: allow flag if it matches or starts with allowed flag + "="
        is_allowed = False
        for allowed in _ALLOWED_MAKEMKV_FLAGS:
            if low == allowed or low.startswith(allowed + "="):
                is_allowed = True
                break
        if not is_allowed:
            dropped.append(tok)
            continue
        filtered.append(tok)

    if dropped and on_log:
        on_log(
            f"Warning: removed disallowed token(s) in {label}: "
            + ", ".join(dropped)
        )

    return filtered



__all__ = ["parse_cli_args", "parse_duration_to_seconds", "parse_episode_names", "parse_ordered_titles", "parse_size_to_bytes", "safe_int"]
