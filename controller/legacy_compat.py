"""Compatibility helpers restored from the pre-refactor controller."""

import glob
import json
import os
import re
import shutil
import subprocess
import sys as _sys
import threading
import time
from datetime import datetime
from typing import Any, Literal, Mapping, Protocol, Sequence, cast

from shared.runtime import __version__
from utils.helpers import clean_name, make_temp_title
from utils.media import select_largest_file
from utils.session_result import normalize_session_result
from utils.state_machine import SessionState, SessionStateMachine
from utils.scoring import choose_best_title


DiscTitle = dict[str, Any]
DiscTitles = list[DiscTitle]
AnalyzedFile = tuple[str, float, float]
AnalyzedFiles = list[AnalyzedFile]
PathOverrides = dict[str, str]
PathField = tuple[str, str]
SessionMeta = Mapping[str, Any]
SizeValidationStatus = Literal["pass", "warn", "hard_fail"]


class _SessionHelpersLike(Protocol):
    def log(self, msg: str) -> None: ...
    def report(self, msg: str) -> None: ...
    def flush_log(self) -> None: ...
    def write_session_summary(self) -> None: ...
    def scan_with_retry(self) -> DiscTitles | None: ...
    def check_resume(self, temp_root: str, media_type: str | None = None) -> Any: ...


class LegacyControllerMixin:
    engine: Any
    gui: Any
    session_helpers: _SessionHelpersLike
    session_paths: PathOverrides | None
    _preview_lock: threading.Lock
    _wiped_session_paths: set[str]
    session_report: list[str]
    sm: SessionStateMachine

    def log(self, message: str) -> None: ...
    def _stabilize_ripped_files(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None = None,
    ) -> tuple[bool, bool]: ...

    def report(self, msg: str) -> None:
        return self.session_helpers.report(msg)

    def _warn_degraded_rips(self) -> None:
        """Add session warnings for any degraded titles from the last rip."""
        for tid in self.engine.last_degraded_titles:
            self.report(
                f"Title {tid}: MakeMKV read errors but output produced "
                f"(degraded rip — validated downstream by ffprobe)"
            )

    def _reset_state_machine(self) -> None:
        self.sm = SessionStateMachine(
            debug=bool(self.engine.cfg.get("opt_debug_state", False)),
            logger=self.log,
        )

    def _state_transition(self, new_state: SessionState) -> None:
        self.sm.transition(new_state)
        if self.engine.cfg.get("opt_debug_state_json", False):
            self.log(
                "STATE_JSON: " + json.dumps(
                    {
                        "event": "transition",
                        "state": self.sm.state.name,
                        "time": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            )

    def _state_fail(self, reason: str) -> None:
        self.sm.fail(reason)
        if self.engine.cfg.get("opt_debug_state_json", False):
            self.log(
                "STATE_JSON: " + json.dumps(
                    {
                        "event": "fail",
                        "reason": reason,
                        "state": self.sm.state.name,
                        "time": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            )

    def _record_fallback_event(
        self,
        reason: str,
        accepted: bool,
        strict: bool,
    ) -> None:
        if not self.engine.cfg.get("opt_debug_state_json", False):
            return
        self.log(
            "STATE_JSON: " + json.dumps(
                {
                    "event": "fallback",
                    "reason": reason,
                    "accepted": bool(accepted),
                    "strict": bool(strict),
                    "time": datetime.now().isoformat(timespec="seconds"),
                }
            )
        )

    def flush_log(self) -> None:
        return self.session_helpers.flush_log()

    def write_session_summary(self) -> None:
        return self.session_helpers.write_session_summary()

    def scan_with_retry(self) -> DiscTitles | None:
        return self.session_helpers.scan_with_retry()

    def check_resume(self, temp_root: str, media_type: str | None = None) -> Any:
        return self.session_helpers.check_resume(temp_root, media_type)

    def _init_session_paths(self, overrides: Mapping[str, str] | None = None) -> None:
        """Initialize per-run path state from defaults plus optional overrides."""
        cfg = self.engine.cfg
        self.session_paths = {
            "temp": os.path.normpath(cfg.get("temp_folder", "")),
            "movies": os.path.normpath(cfg.get("movies_folder", "")),
            "tv": os.path.normpath(cfg.get("tv_folder", "")),
        }
        if overrides:
            key_map = {
                "temp_folder": "temp",
                "movies_folder": "movies",
                "tv_folder": "tv",
            }
            for k, v in overrides.items():
                session_key = key_map.get(k)
                if session_key and v:
                    self.session_paths[session_key] = os.path.normpath(v)

    def get_path(self, key: str) -> str:
        if not self.session_paths:
            raise RuntimeError("session_paths not initialized")
        return self.session_paths[key]

    def _log_session_paths(self) -> None:
        if not self.session_paths:
            return
        self.log(f"=== JellyRip v{__version__} — session start ===")
        self.log(f"Temp:   {self.session_paths.get('temp')}")
        self.log(f"Movies: {self.session_paths.get('movies')}")
        self.log(f"TV:     {self.session_paths.get('tv')}")
        self.log("=================")

    def _validate_paths(
        self,
        temp: str | None,
        movies: str | None = None,
        tv: str | None = None,
    ) -> str | None:
        def _norm(p: str) -> str:
            return os.path.normcase(os.path.abspath(os.path.normpath(str(p))))

        def _is_writable(path: str) -> bool:
            # Fast pre-check keeps behavior explicit and testable on all OSes.
            if not os.access(path, os.W_OK):
                return False
            # Write a probe file in a daemon thread — on a slow/offline network
            # share, open() and os.remove() can block for 60-120 s.
            probe = os.path.join(path, f".jellyrip_probe_{os.getpid()}")
            _result = [False]

            def _probe() -> None:
                try:
                    with open(probe, "w") as f:
                        f.write("")
                    os.remove(probe)
                    _result[0] = True
                except OSError:
                    pass

            t = threading.Thread(target=_probe, daemon=True)
            t.start()
            t.join(timeout=8.0)
            return _result[0]

        _SYSTEM_PATH_RE = re.compile(
            r'^[A-Za-z]:\\(Windows|Program Files|Program Files \(x86\))(\\|$)',
            re.IGNORECASE,
        )

        temp_n = _norm(temp) if temp else None
        movies_n = _norm(movies) if movies else None
        tv_n = _norm(tv) if tv else None

        if temp_n and movies_n and temp_n == movies_n:
            return "Temp and Movies folder cannot be the same"
        if temp_n and tv_n and temp_n == tv_n:
            return "Temp and TV folder cannot be the same"

        for p in [x for x in [temp_n, movies_n, tv_n] if x]:
            if _SYSTEM_PATH_RE.match(p):
                return f"Blocked system path: {p}"

            if os.path.exists(p) and not _is_writable(p):
                return f"Path not writable: {p}"

        return None

    def _prompt_run_path_overrides(
        self,
        path_fields: Sequence[PathField],
    ) -> PathOverrides | None:
        """Optionally override folder paths for this run only.

        path_fields: list of tuples (config_key, human_label).
        Returns dict of resolved paths, or None if aborted.
        """
        resolved = {
            key: os.path.normpath(self.engine.cfg.get(key, ""))
            for key, _label in path_fields
        }

        if not path_fields:
            return resolved

        if not self.gui.ask_yesno(
            "Use custom folders for this run?\n\n"
            "Yes = browse/select per-mode paths\n"
            "No = use saved defaults"
        ):
            return resolved

        self.log("Custom run-folder override selected — collecting paths.")

        for key, label in path_fields:
            default_path = resolved[key]
            used_picker = callable(getattr(self.gui, "ask_directory", None))

            if used_picker:
                self.log(
                    f"Opening folder picker — {label} (default: {default_path})"
                )
                chosen = self.gui.ask_directory(
                    f"{label} (Run Override)",
                    "Choose folder (Cancel = keep default)",
                    initialdir=default_path,
                )
                if chosen is None:
                    resolved[key] = default_path
                    self.log(
                        f"Folder picker closed/cancelled — {label}: using default {default_path}"
                    )
                    continue
                self.log(f"Folder picker result — {label}: {chosen}")
                chosen = os.path.normpath(str(chosen).strip())
                if os.path.isdir(chosen):
                    resolved[key] = chosen
                    self.log(f"Run override — {label}: {chosen}")
                    continue
                try:
                    os.makedirs(chosen, exist_ok=True)
                    resolved[key] = chosen
                    self.log(f"Run override — {label}: {chosen}")
                    continue
                except Exception as e:
                    self.log(
                        f"Could not create folder '{chosen}': {e}"
                    )
                    resolved[key] = default_path
                    self.log(
                        f"Falling back to default {label}: {default_path}"
                    )
                    continue

            while True:
                entered = self.gui.ask_input(
                    f"{label} (Run Override)",
                    "Enter folder path (Skip = keep default):",
                    default_value=default_path,
                )
                if entered is None:
                    resolved[key] = default_path
                    self.log(
                        f"Run override cancelled — {label}: using default {default_path}"
                    )
                    break

                chosen = default_path if entered == "" else str(entered).strip()
                if not chosen:
                    chosen = default_path
                chosen = os.path.normpath(chosen)

                if os.path.isdir(chosen):
                    resolved[key] = chosen
                    self.log(f"Run override — {label}: {chosen}")
                    break

                if self.gui.ask_yesno(
                    f"Folder does not exist:\n{chosen}\n\nCreate it?"
                ):
                    try:
                        os.makedirs(chosen, exist_ok=True)
                        resolved[key] = chosen
                        self.log(f"Run override — {label}: {chosen}")
                        break
                    except Exception as e:
                        self.log(
                            f"Could not create folder '{chosen}': {e}"
                        )
                else:
                    self.log(
                        f"Re-enter {label} or click Skip to keep default."
                    )

        error = self._validate_paths(
            resolved.get("temp_folder"),
            movies=resolved.get("movies_folder"),
            tv=resolved.get("tv_folder"),
        )
        if error:
            self.log(f"ERROR: {error}")
            self.gui.show_error("Invalid Run Paths", error)
            return None

        self.log("Custom folders set, continuing...")

        return resolved

    def _restore_selected_titles(
        self,
        disc_titles: DiscTitles,
        resume_meta: SessionMeta,
    ) -> list[int] | None:
        """Return saved selected title ids if they still exist on this disc."""
        saved_raw = resume_meta.get("selected_titles")
        saved: list[int] = []
        if isinstance(saved_raw, Sequence) and not isinstance(saved_raw, (str, bytes)):
            for raw_tid in cast(Sequence[object], saved_raw):
                if isinstance(raw_tid, (int, str)):
                    saved.append(int(raw_tid))
        if not saved:
            return None
        valid_ids = {int(t.get("id", -1)) for t in disc_titles}
        restored = [tid for tid in saved if tid in valid_ids]
        return restored or None

    def _map_title_ids_to_analyzed_indices(
        self,
        titles_list: AnalyzedFiles,
        title_ids: Sequence[int] | None,
    ) -> list[int]:
        """Map MakeMKV title ids to analyze_files indices.

        Primary: explicit engine tracking from rip_selected_titles.
        Fallback: filename parsing tags for legacy compatibility.
        """
        wanted = {int(tid) for tid in (title_ids or [])}
        if not wanted:
            return []
        tracked_obj = getattr(self.engine, "last_title_file_map", {}) or {}
        tracked_map: Mapping[object, object]
        if isinstance(tracked_obj, Mapping):
            tracked_map = cast(Mapping[object, object], tracked_obj)
        else:
            tracked_map = {}
        tracked_lookup: dict[str, int] = {}
        for raw_tid, raw_files in tracked_map.items():
            if not isinstance(raw_tid, (int, str)):
                continue
            tid = int(raw_tid)
            if tid not in wanted:
                continue
            file_list: list[str] = []
            if isinstance(raw_files, Sequence) and not isinstance(raw_files, (str, bytes)):
                file_list = [str(path) for path in cast(Sequence[object], raw_files)]
            for path in file_list:
                tracked_lookup[os.path.normcase(os.path.abspath(path))] = tid
        mapped: list[int] = []
        for idx, (path, _dur, _mb) in enumerate(titles_list):
            norm = os.path.normcase(os.path.abspath(path))
            title_id = tracked_lookup.get(norm)
            if title_id is None:
                title_id = self._title_id_from_filename(path)
            if title_id in wanted:
                mapped.append(idx)
        return mapped

    def _fallback_title_from_mode(self, disc_titles: DiscTitles | None = None) -> str:
        """Build fallback title string based on configured naming mode."""
        from controller import controller as controller_module

        disc_name = self.engine.last_disc_info.get("title")
        title: str = controller_module.build_fallback_title(
            self.engine.cfg,
            make_temp_title,
            clean_name,
            choose_best_title,
            disc_titles=disc_titles,
            disc_name=disc_name,
        )
        self.log(f"Auto-title fallback used: '{title}'")
        return title

    def _log_ripped_file_sizes(self, mkv_files: Sequence[str]) -> None:
        """Log final sizes for newly ripped files so anomalies stand out."""
        for f in sorted(mkv_files):
            try:
                size_gb = os.path.getsize(f) / (1024**3)
                self.log(
                    f"Ripped file: {os.path.basename(f)} — {size_gb:.2f} GB"
                )
            except Exception as e:
                self.log(
                    f"Ripped file: {os.path.basename(f)} — size unavailable ({e})"
                )

    def _title_id_from_filename(self, path: str) -> int | None:
        name = os.path.basename(path)
        m = re.search(r'title_t(\d+)', name, re.IGNORECASE)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _size_validation_status(
        self,
        actual_bytes: int,
        expected_bytes: int,
    ) -> tuple[SizeValidationStatus, str, float]:
        """Return (status, reason, ratio): status in {pass,warn,hard_fail}."""
        if expected_bytes <= 0:
            return "pass", "no_expected_size", 1.0

        hard_ratio = max(
            0.10,
            min(0.95, float(self.engine.cfg.get("opt_hard_fail_ratio_pct", 40)) / 100.0)
        )
        warn_ratio = max(
            hard_ratio,
            min(0.99, float(self.engine.cfg.get("opt_expected_size_ratio_pct", 70)) / 100.0)
        )
        ratio = actual_bytes / expected_bytes if expected_bytes > 0 else 0.0

        if ratio < hard_ratio:
            return (
                "hard_fail",
                f"size too small: {ratio * 100:.1f}% of expected "
                f"(< {hard_ratio * 100:.0f}% hard floor)",
                ratio,
            )
        if ratio < warn_ratio:
            return (
                "warn",
                f"size below preferred threshold: {ratio * 100:.1f}% "
                f"(< {warn_ratio * 100:.0f}%)",
                ratio,
            )
        return "pass", f"size OK ({ratio * 100:.1f}%)", ratio

    def _verify_expected_sizes(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None,
    ) -> tuple[SizeValidationStatus, str]:
        """Aggregate expected-vs-actual validation with hard/warn thresholds."""
        if not self.engine.cfg.get("opt_safe_mode", True):
            return "pass", "safe_mode_disabled"
        if not expected_size_by_title:
            return "pass", "no_expected_size"

        expected_total = sum(int(v or 0) for v in expected_size_by_title.values())
        actual_total = 0
        for f in mkv_files:
            try:
                actual_total += os.path.getsize(f)
            except Exception as e:
                self.log(f"os.path.getsize failed: {e}")

        status, reason, ratio = self._size_validation_status(
            actual_total, expected_total
        )
        self.log(
            "Size sanity (aggregate): expected "
            f"{expected_total / (1024**3):.2f} GB, actual "
            f"{actual_total / (1024**3):.2f} GB "
            f"({ratio * 100:.1f}%)"
        )
        if status == "hard_fail":
            self.log(f"ERROR: {reason}")
        elif status == "warn":
            self.log(f"WARNING: {reason}")
        return status, reason

    def _log_expected_vs_actual_summary(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None,
    ) -> None:
        """Log concise total expected vs actual output size summary."""
        if not expected_size_by_title:
            return

        expected_total = sum(
            int(v or 0) for v in expected_size_by_title.values()
        )
        if expected_total <= 0:
            return

        actual_total = 0
        for f in mkv_files:
            try:
                actual_total += os.path.getsize(f)
            except Exception as e:
                self.log(f"os.path.getsize failed: {e}")

        pct = (actual_total / expected_total) * 100
        self.log(
            "Expected total size: "
            f"{expected_total / (1024**3):.2f} GB | "
            f"Actual total size: {actual_total / (1024**3):.2f} GB "
            f"({pct:.1f}%)"
        )

    def _ensure_session_paths(self) -> None:
        """Hard guard: raises if session_paths has not been initialized."""
        if not self.session_paths:
            raise RuntimeError(
                "session_paths not initialized — "
                "call _init_session_paths() first"
            )

    def _verify_container_integrity(
        self,
        mkv_files: Sequence[str],
        analyzed: AnalyzedFiles | None = None,
        expected_durations: Mapping[str, float] | None = None,
        expected_sizes: Mapping[str, int] | None = None,
        title_file_map: Mapping[int, Sequence[str]] | None = None,
    ) -> bool:
        """Require ffprobe-readable container with duration > 0 for each file.

        Accepts an optional pre-analyzed list (from a prior analyze_files call)
        to avoid running ffprobe twice in the same pipeline step.

        When expected_durations (filepath → seconds) and/or expected_sizes
        (filepath → bytes) are provided, performs tiered duration sanity checks.
        Comparison is done at the title-group level (sum of all files per title)
        when title_file_map (title_id → [paths]) is supplied, preventing false
        per-file warnings on seamless/multi-part titles.

        Tiers:
          < 50%  → severe warning (TRUNCATION ERROR when BOTH dur AND size agree)
          50â€“75% → likely truncation warning
          75â€“90% → minor mismatch warning
          â‰¥ 90%  → normal variance, no warning

        Expected size values below 200 MB are treated as unreliable disc scan
        metadata and excluded from size-based escalation.

        Short titles (expected < 600 s) use widened tiers to avoid false
        positives from disc timing inaccuracies.

        In strict mode (opt_strict_mode), any tier below "minor" (< 75%)
        escalates to a hard failure.
        """
        _SIZE_FLOOR = 200 * 1024 * 1024   # 200 MB — below this, size is noise
        _SHORT_TITLE = 600                  # < 600 s — widen tiers

        if not mkv_files:
            return False
        self.log("Container integrity check (ffprobe)...")
        analyzed_list: AnalyzedFiles = (
            analyzed if analyzed is not None
            else self.engine.analyze_files(mkv_files, self.log) or []
        )
        if len(analyzed_list) != len(mkv_files):
            self.log(
                "ERROR: Container integrity check incomplete "
                f"({len(analyzed_list)}/{len(mkv_files)} files analyzed)."
            )
            return False
        bad = [os.path.basename(f) for f, dur, _mb in analyzed_list if dur <= 0]
        if bad:
            self.log(
                "ERROR: Container integrity check failed for: "
                + ", ".join(bad)
            )
            return False

        if not (expected_durations or expected_sizes):
            return True

        strict = bool(self.engine.cfg.get("opt_strict_mode", False))
        strict_fail = False

        # Build a lookup: filepath → (dur, size_bytes) from analyzed results.
        analyzed_lookup = {
            f: (dur, int(mb * 1024 * 1024))
            for f, dur, mb in analyzed_list
        }

        # Build groups: each group is a list of file paths belonging to one
        # logical title. When title_file_map is absent, treat each file as
        # its own group.
        groups: list[tuple[int | str | None, list[str]]]
        if title_file_map:
            groups = [
                (tid, [fp for fp in files if fp in analyzed_lookup])
                for tid, files in title_file_map.items()
            ]
            # Files not covered by any title group get individual treatment.
            covered = {fp for _, files in groups for fp in files}
            for fp in analyzed_lookup:
                if fp not in covered:
                    groups.append((None, [fp]))
        else:
            groups = [(None, [fp]) for fp in mkv_files]

        warned_tids: set[int | str] = set()

        for tid, files in groups:
            if not files:
                continue
            if tid is not None and tid in warned_tids:
                continue

            # Aggregate duration and size across the group.
            total_dur = sum(analyzed_lookup[fp][0] for fp in files if fp in analyzed_lookup)
            total_bytes = sum(analyzed_lookup[fp][1] for fp in files if fp in analyzed_lookup)
            label = (
                os.path.basename(files[0])
                if len(files) == 1
                else f"Title {tid} ({len(files)} files)"
                if tid is not None
                else os.path.basename(files[0])
            )

            # Aggregate expectations across group files.
            exp_dur = sum(
                (expected_durations or {}).get(fp, 0) for fp in files
            ) or None
            raw_exp_size = sum(
                (expected_sizes or {}).get(fp, 0) for fp in files
            )
            # Clamp unreliable disc-scan size metadata.
            exp_size = raw_exp_size if raw_exp_size >= _SIZE_FLOOR else None

            if not exp_dur or exp_dur <= 0:
                continue

            dur_ratio = total_dur / exp_dur if total_dur > 0 else 0.0
            size_ratio = total_bytes / exp_size if exp_size else None

            # Widen tiers for short titles.
            is_short = exp_dur < _SHORT_TITLE
            t_severe  = 0.4 if is_short else 0.5
            t_likely  = 0.6 if is_short else 0.75
            t_minor   = 0.85 if is_short else 0.9

            if dur_ratio >= t_minor:
                continue  # normal variance

            if tid is not None:
                warned_tids.add(tid)

            if dur_ratio < t_severe:
                if size_ratio is not None and size_ratio < t_severe:
                    assert exp_size is not None
                    self.report(
                        f"TRUNCATION ERROR: {label} — "
                        f"duration {total_dur / 60:.1f} min "
                        f"(expected ~{exp_dur / 60:.1f} min, "
                        f"{dur_ratio * 100:.0f}%) AND "
                        f"size {total_bytes // (1024**2)} MB "
                        f"(expected ~{int(exp_size) // (1024**2)} MB, "
                        f"{size_ratio * 100:.0f}%) — "
                        f"both signals indicate corrupt/incomplete rip"
                    )
                    if strict:
                        strict_fail = True
                else:
                    self.report(
                        f"WARNING: Severe duration mismatch — {label}: "
                        f"actual {total_dur / 60:.1f} min, "
                        f"expected ~{exp_dur / 60:.1f} min "
                        f"({dur_ratio * 100:.0f}%) — possible truncation"
                    )
                    if strict:
                        strict_fail = True
            elif dur_ratio < t_likely:
                self.report(
                    f"WARNING: Likely truncation — {label}: "
                    f"actual {total_dur / 60:.1f} min, "
                    f"expected ~{exp_dur / 60:.1f} min "
                    f"({dur_ratio * 100:.0f}%)"
                    + (
                        f"; size also low ({size_ratio * 100:.0f}%)"
                        if (size_ratio is not None and size_ratio < t_likely)
                        else ""
                    )
                )
                if strict:
                    strict_fail = True
            else:
                self.report(
                    f"WARNING: Minor duration mismatch — {label}: "
                    f"actual {total_dur / 60:.1f} min, "
                    f"expected ~{exp_dur / 60:.1f} min "
                    f"({dur_ratio * 100:.0f}%)"
                )

        if strict_fail:
            self.log(
                "ERROR: Strict mode — truncation warning escalated to failure."
            )
            return False

        return True

    def _normalize_rip_result(
        self,
        rip_path: str,
        success: bool,
        failed_titles: Sequence[Any] | None,
        pre_existing_files: frozenset[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Collapse rip outcomes into one all-or-nothing success state.

        pre_existing_files: optional frozenset of MKV paths that existed in
        rip_path before this rip started.  Files in this set are excluded from
        the validity check so a leftover invalid partial from a prior session
        cannot cause the current rip to fail.
        """
        _excluded = frozenset(pre_existing_files or [])
        mkv_files = sorted(
            f for f in self._safe_glob(
                os.path.join(rip_path, "**", "*.mkv"),
                recursive=True,
                context="Enumerating rip outputs",
            )
            if f not in _excluded
        )

        valid_files = [
            f for f in mkv_files
            if self.engine._quick_ffprobe_ok(f, self.log)
        ]

        if self.engine.abort_flag:
            self.log("Rip aborted — treating session as failure.")
        if failed_titles:
            self.log(f"Titles failed: {failed_titles}")
        if not mkv_files:
            self.log("No MKV files produced — treating as failure.")

        self.log(
            "Failure gate: "
            f"abort={self.engine.abort_flag}, "
            f"failed_titles={len(failed_titles or [])}, "
            f"files={len(mkv_files)}, valid={len(valid_files)}"
        )

        normalized = normalize_session_result(
            self.engine.abort_flag,
            failed_titles,
            mkv_files,
            valid_files,
        )

        if len(valid_files) != len(mkv_files):
            self.log("One or more MKV files are invalid — treating as failure.")
        if not normalized:
            return False, mkv_files

        return bool(success), mkv_files

    # ------------------------------------------------------------------
    # Library-scanning helpers (used by "attach to existing show" mode)
    # ------------------------------------------------------------------

    # SxxEyy with optional chained episodes: S01E01, S01E01E02, S01E01E02E03 â€¦
    # Captured groups: season, first episode, then zero or more extra E-tokens.
    _RE_SxxEyy = re.compile(
        r"S(\d{1,3})((?:E\d{1,3})+)",
        re.IGNORECASE,
    )
    # 1x01 / Nx01 — season Ã— episode
    _RE_NxNN = re.compile(r"(\d{1,2})x(\d{1,2})")
    # "Episode N" — no season token; useful when file is already inside a
    # Season folder (the folder itself encodes the season).
    _RE_EPISODE_N = re.compile(r"[Ee]pisode\s+(\d{1,4})")
    # Splits the E-token block into individual episode numbers.
    _RE_E_SPLIT = re.compile(r"E(\d{1,3})", re.IGNORECASE)

    @staticmethod
    def get_next_episode(existing: set[int]) -> int:
        """Return the lowest episode number not yet in *existing*.

        Fills gaps before appending, so a library missing E03 returns 3
        rather than max+1.  Returns 1 when *existing* is empty.
        """
        if not existing:
            return 1
        for i in range(1, max(existing) + 2):
            if i not in existing:
                return i
        return max(existing) + 1  # unreachable but satisfies type checkers

    def _episodes_from_filename(self, fname: str, season: int) -> set[int]:
        """Extract every episode number encoded in *fname* for *season*.

        Handles:
          - ``S01E01``           → {1}
          - ``S01E01E02``        → {1, 2}   (multi-episode file)
          - ``S01E01E02E03``     → {1, 2, 3}
          - ``1x01``             → {1}
          - ``Episode 4``        → {4}

        Returns an empty set when the filename does not match any pattern
        or the season token does not match *season*.
        """
        # --- SxxEyy (with optional chained episodes) ---
        m = self._RE_SxxEyy.search(fname)
        if m:
            if int(m.group(1)) != season:
                # Season token present but wrong season — do not fall through.
                return set()
            return {int(n) for n in self._RE_E_SPLIT.findall(m.group(2))}

        # --- Nx01 format ---
        m = self._RE_NxNN.search(fname)
        if m:
            if int(m.group(1)) != season:
                return set()
            return {int(m.group(2))}

        # --- "Episode N" (no season token) ---
        m = self._RE_EPISODE_N.search(fname)
        if m:
            return {int(m.group(1))}

        return set()

    def _scan_episode_files(self, folder: str, season: int) -> set[int]:
        """Return the set of episode numbers found in *folder* for *season*.

        Multi-episode files (e.g. ``S01E01E02.mkv``) contribute all their
        episode numbers so gap detection is never fooled into thinking an
        episode is missing when it is part of a combined file.
        Season 00 is supported (Jellyfin treats it as Specials).
        Only reads the directory listing — no ffprobe or file I/O.
        """
        found: set[int] = set()
        if not folder or not os.path.isdir(folder):
            return found
        try:
            for fname in os.listdir(folder):
                found |= self._episodes_from_filename(fname, season)
        except OSError:
            pass
        return found

    def _scan_library_folder(self, show_root: str) -> dict[int, list[int]]:
        """Scan *show_root* for existing season folders and their episodes.

        Returns a dict mapping season number (int) to a sorted list of
        episode numbers already present on disk.  Season 00 ("Specials")
        is included and logged.  Only reads directory listings — no file I/O.

        Example::

            {0: [1, 2], 1: [1, 2, 3], 2: [1, 2]}
        """
        result: dict[int, list[int]] = {}
        if not show_root or not os.path.isdir(show_root):
            return result
        # "Season 00", "Season 1", "Specials" (mapped to season 0) are all valid.
        season_pat = re.compile(r"Season\s+(\d{1,3})", re.IGNORECASE)
        specials_pat = re.compile(r"^Specials?$", re.IGNORECASE)
        try:
            for entry in os.listdir(show_root):
                season_dir = os.path.join(show_root, entry)
                if not os.path.isdir(season_dir):
                    continue
                m = season_pat.match(entry)
                if m:
                    season_num = int(m.group(1))
                elif specials_pat.match(entry):
                    season_num = 0
                else:
                    continue
                eps = self._scan_episode_files(season_dir, season_num)
                result[season_num] = sorted(eps)
                if season_num == 0:
                    self.log(
                        f"Specials/Season 00 detected: {season_dir} "
                        f"({len(eps)} item(s))"
                    )
        except OSError:
            pass
        return result

    def _scan_highest_episode(self, dest_folder: str, season: int) -> int:
        """Return the highest episode number already present in *dest_folder*
        for *season*, or 0 if none are found.

        Kept for backward compatibility; internally delegates to
        :meth:`_scan_episode_files`.
        """
        eps = self._scan_episode_files(dest_folder, season)
        return max(eps) if eps else 0

    def _mark_session_failed(self, rip_path: str, **metadata: Any) -> None:
        """Wipe session outputs and persist a single failed session state."""
        self.log("Session failed — wiping outputs.")
        self.engine.update_temp_metadata(
            rip_path,
            status="failed",
            phase="failed",
            **metadata,
        )
        if rip_path not in self._wiped_session_paths:
            self.engine.wipe_session_outputs(rip_path, self.log)
            self._wiped_session_paths.add(rip_path)

    def _safe_glob(
        self,
        pattern: str,
        recursive: bool = False,
        timeout: float = 8.0,
        context: str = "glob",
    ) -> list[str]:
        """Run glob with timeout so slow/offline shares do not block flow."""
        matches: list[str] = []
        err: list[Exception | None] = [None]

        def _scan() -> None:
            try:
                matches.extend(glob.glob(pattern, recursive=recursive))
            except Exception as e:
                err[0] = e

        t = threading.Thread(target=_scan, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            self.log(f"WARNING: {context} timed out; continuing.")
            return []
        if err[0] is not None:
            self.log(f"WARNING: {context} failed: {err[0]}")
            return []
        return matches

    def preview_title(self, title_id: int) -> None:
        """Rip a short preview clip for one title and open it in VLC."""
        temp_root = (
            self.get_path("temp")
            if self.session_paths and "temp" in self.session_paths
            else self.engine.cfg["temp_folder"]
        )
        preview_dir = os.path.join(
            temp_root, "preview"
        )

        try:
            shutil.rmtree(preview_dir, ignore_errors=True)
            os.makedirs(preview_dir, exist_ok=True)
        except Exception as e:
            self.log(f"Preview setup failed: {e}")
            return

        def run_preview() -> None:
            lock_acquired = False
            try:
                if not self._preview_lock.acquire(blocking=False):
                    self.log("Preview already running. Wait for it to finish.")
                    return
                lock_acquired = True

                if self.engine.abort_event.is_set():
                    self.log("Preview skipped: abort requested.")
                    return
                self.log(f"Preview: starting Title {title_id + 1} for 40s...")
                self.gui.set_status(
                    f"Previewing Title {title_id + 1}... (40s sample)"
                )
                preview_ok = self.engine.rip_preview_title(
                    preview_dir, title_id, 40, self.log
                )

                # MakeMKV may create output in nested paths and can finish
                # metadata flush shortly after process stop. Poll briefly.
                files = []
                for _ in range(8):
                    files = self._safe_glob(
                        os.path.join(preview_dir, "**", "*.mkv"),
                        recursive=True,
                        context="Scanning preview outputs",
                    )
                    if files:
                        break
                    time.sleep(0.25)
                if not files:
                    if not preview_ok:
                        self.log("Preview failed: rip process did not complete.")
                    else:
                        self.log("Preview failed: no preview file found.")
                    return

                latest = select_largest_file(files)
                if not latest:
                    self.log("Preview failed: preview file selection returned nothing.")
                    return
                try:
                    size_mb = os.path.getsize(latest) / (1024**2)
                except Exception:
                    size_mb = 0.0
                analyzed = self.engine.analyze_files([latest], self.log)
                duration = int(analyzed[0][1]) if analyzed else 0
                mm = duration // 60
                ss = duration % 60
                self.log(
                    f"Preview candidate: {os.path.basename(latest)} | "
                    f"{size_mb:.0f} MB | {mm:02d}:{ss:02d}"
                )
                vlc = shutil.which("vlc")
                if not vlc:
                    for candidate in [
                        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                    ]:
                        if os.path.isfile(candidate):
                            vlc = candidate
                            break
                if vlc:
                    if _sys.platform == "win32":
                        subprocess.Popen(
                            [vlc, latest],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=0x08000000,
                        )
                    else:
                        subprocess.Popen(
                            [vlc, latest],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    self.log(
                        f"Preview opened in VLC: {os.path.basename(latest)}"
                    )
                else:
                    self.log(
                        f"VLC not found; opening in default player: {os.path.basename(latest)}"
                    )
                    os.startfile(latest)
            except Exception as e:
                self.log(f"Preview open failed: {e}")
            finally:
                # Only clear abort if no rip is running — otherwise
                # preview cleanup would cancel a real abort request.
                rip = getattr(self.gui, "rip_thread", None)
                if not (rip and rip.is_alive()):
                    self.engine.reset_abort()
                self.gui.set_status("Ready")
                if lock_acquired:
                    self._preview_lock.release()

        threading.Thread(target=run_preview, daemon=True).start()

    def _retry_rip_once_after_size_failure(
        self,
        rip_path: str,
        selected_ids: Sequence[int],
        expected_size_by_title: Mapping[int, int] | None,
    ) -> bool:
        """Retry rip once after size sanity failure and re-run checks."""
        self.log(
            "Safe Mode: size sanity failed — retrying rip once automatically."
        )
        self.engine.cleanup_partial_files(rip_path, self.log)
        for pattern in ("**/*.mkv", "**/*.partial"):
            for f in self._safe_glob(
                os.path.join(rip_path, pattern),
                recursive=True,
                context="Cleaning retry artifacts",
            ):
                try:
                    os.remove(f)
                except Exception as e:
                    self.log(f"os.remove failed: {e}")

        self.gui.set_status("Ripping... (this may take 20-60 min)")
        _pre_rip_mkvs = frozenset(
            self._safe_glob(
                os.path.join(rip_path, "**", "*.mkv"),
                recursive=True,
                context="Snapshotting pre-rip MKVs",
            )
        )
        success, failed_titles = self.engine.rip_selected_titles(
            rip_path, selected_ids,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        self._warn_degraded_rips()
        if failed_titles:
            self.report(
                f"Retry: titles failed — {failed_titles}"
            )
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, failed_titles, _pre_rip_mkvs
        )
        if not success:
            return False

        self.engine.update_temp_metadata(rip_path, status="ripped")

        self._log_ripped_file_sizes(mkv_files)
        stabilized, timed_out = self._stabilize_ripped_files(
            mkv_files, expected_size_by_title
        )
        if not stabilized:
            if timed_out:
                self.log("Retry stabilization failed: timed out.")
            return False
        self._log_expected_vs_actual_summary(
            mkv_files, expected_size_by_title
        )
        status, _reason = self._verify_expected_sizes(mkv_files, expected_size_by_title)
        return status == "pass"

