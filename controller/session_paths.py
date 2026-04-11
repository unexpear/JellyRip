from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable, Mapping


PathOverrides = dict[str, str]


def init_session_paths(
    cfg: Mapping[str, object],
    overrides: Mapping[str, str] | None = None,
) -> PathOverrides:
    session_paths: PathOverrides = {
        "temp": os.path.normpath(str(cfg.get("temp_folder", "") or "")),
        "movies": os.path.normpath(str(cfg.get("movies_folder", "") or "")),
        "tv": os.path.normpath(str(cfg.get("tv_folder", "") or "")),
    }
    if overrides:
        key_map = {
            "temp_folder": "temp",
            "movies_folder": "movies",
            "tv_folder": "tv",
        }
        for key, value in overrides.items():
            session_key = key_map.get(key)
            if session_key and value:
                session_paths[session_key] = os.path.normpath(value)
    return session_paths


def get_session_path(session_paths: PathOverrides | None, key: str) -> str:
    if not session_paths:
        raise RuntimeError("session_paths not initialized")
    return session_paths[key]


def log_session_paths(
    session_paths: PathOverrides | None,
    *,
    version: str,
    log_fn: Callable[[str], None],
) -> None:
    if not session_paths:
        return
    log_fn(f"=== JellyRip v{version} - session start ===")
    log_fn(f"Temp:   {session_paths.get('temp')}")
    log_fn(f"Movies: {session_paths.get('movies')}")
    log_fn(f"TV:     {session_paths.get('tv')}")
    log_fn("=================")


def validate_session_paths(
    temp: str | None,
    movies: str | None = None,
    tv: str | None = None,
) -> str | None:
    def _norm(path: str) -> str:
        return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))

    def _is_writable(path: str) -> bool:
        if not os.access(path, os.W_OK):
            return False

        probe = os.path.join(path, f".jellyrip_probe_{os.getpid()}")
        result = [False]

        def _probe() -> None:
            try:
                with open(probe, "w", encoding="utf-8") as handle:
                    handle.write("")
                os.remove(probe)
                result[0] = True
            except OSError:
                pass

        thread = threading.Thread(target=_probe, daemon=True)
        thread.start()
        thread.join(timeout=8.0)
        return result[0]

    system_path_re = re.compile(
        r"^[A-Za-z]:\\(Windows|Program Files|Program Files \(x86\))(\\|$)",
        re.IGNORECASE,
    )

    temp_n = _norm(temp) if temp else None
    movies_n = _norm(movies) if movies else None
    tv_n = _norm(tv) if tv else None

    if temp_n and movies_n and temp_n == movies_n:
        return "Temp and Movies folder cannot be the same"
    if temp_n and tv_n and temp_n == tv_n:
        return "Temp and TV folder cannot be the same"

    for path in [item for item in [temp_n, movies_n, tv_n] if item]:
        if system_path_re.match(path):
            return f"Blocked system path: {path}"

        if os.path.exists(path) and not _is_writable(path):
            return f"Path not writable: {path}"

    return None


def ensure_session_paths(session_paths: PathOverrides | None) -> None:
    if not session_paths:
        raise RuntimeError(
            "session_paths not initialized - "
            "call _init_session_paths() first"
        )
