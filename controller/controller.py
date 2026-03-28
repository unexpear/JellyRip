"""Controller layer implementation."""

from shared.runtime import *

from utils.helpers import clean_name, make_rip_folder_name, make_temp_title
from utils.fallback import handle_fallback
from utils.media import select_largest_file
from utils.parsing import parse_episode_names, parse_ordered_titles, safe_int
from utils.scoring import choose_best_title
from utils.session_result import normalize_session_result
from utils.state_machine import SessionState, SessionStateMachine


class RipperController:
    def __init__(self, engine, gui):
        """
        LAYER 2 — Controller

        Workflow orchestration layer. Calls engine methods and GUI methods
        but owns neither. No tkinter widgets, no subprocess calls.

        Owns the session flow for each ripping mode:
          - Temp folder management and resume detection
          - scan_with_retry() — single choke point for all disc scanning
          - Disc loop (insert → scan → select → rip → analyze → move)
          - Session logging and failure reporting

        Design rule: every scan goes through scan_with_retry(). Never call
        engine.scan_disc() directly from a run_* method.

        The 2-second settle delay (time.sleep(2)) after disc insertion is
        intentional hardware timing and must stay outside scan_with_retry().
        """
        self.engine = engine
        self.gui    = gui
        self.session_log          = []
        self.start_time           = datetime.now()
        self.global_extra_counter = 1
        self.session_report       = []
        self._preview_lock        = threading.Lock()
        self._wiped_session_paths = set()
        self.session_paths = None
        self.sm = SessionStateMachine(
            debug=bool(self.engine.cfg.get("opt_debug_state", False)),
            logger=self.log,
        )

    def log(self, msg):
        """Record a timestamped log line and forward it to the GUI queue."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full = f"[{timestamp}] {msg}"
        self.session_log.append(full)
        cap  = int(self.engine.cfg.get("opt_log_cap_lines", 300000))
        trim = int(self.engine.cfg.get("opt_log_trim_lines", 200000))
        if len(self.session_log) > cap:
            self.session_log = self.session_log[-trim:]
        self.gui.append_log(full)

    def report(self, msg):
        """Track a warning/failure event and emit it to the live log."""
        self.session_report.append(msg)
        self.log(msg)

    def _warn_degraded_rips(self):
        """Add session warnings for any degraded titles from the last rip."""
        for tid in self.engine.last_degraded_titles:
            self.report(
                f"Title {tid}: MakeMKV read errors but output produced "
                f"(degraded rip — validated downstream by ffprobe)"
            )

    def _reset_state_machine(self):
        self.sm = SessionStateMachine(
            debug=bool(self.engine.cfg.get("opt_debug_state", False)),
            logger=self.log,
        )

    def _state_transition(self, new_state):
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

    def _state_fail(self, reason):
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

    def _record_fallback_event(self, reason, accepted, strict):
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

    def flush_log(self):
        """Persist current session log buffer to configured log file."""
        log_file = os.path.normpath(
            self.engine.cfg.get("log_file", "")
        )
        # Ensure .txt extension if missing
        if log_file and not log_file.lower().endswith(('.txt', '.log')):
            log_file = log_file + '.txt'
        self.engine.write_session_log(
            log_file, self.start_time, self.session_log, self.log
        )

    def write_session_summary(self):
        if not self.engine.cfg.get(
            "opt_session_failure_report", True
        ):
            return
        if getattr(self, "sm", None) is not None:
            if self.sm.state == SessionState.COMPLETED:
                if self.session_report:
                    self.log("Session summary: Completed with warnings.")
                    self.log("=" * 44)
                    self.log("SESSION SUMMARY — WARNINGS")
                    self.log("=" * 44)
                    for line in self.session_report:
                        self.log(f"  {line}")
                    self.log("=" * 44)
                else:
                    self.log(
                        "Session summary: All discs completed successfully."
                    )
                return
            if self.sm.state == SessionState.FAILED and not self.session_report:
                self.log("Session summary: Session failed.")
                return
        if not self.session_report:
            self.log(
                "Session summary: All discs completed successfully."
            )
            return
        self.log("=" * 44)
        self.log("SESSION SUMMARY — FAILURES/WARNINGS")
        self.log("=" * 44)
        for line in self.session_report:
            self.log(f"  {line}")
        self.log("=" * 44)

    def scan_with_retry(self):
        """
        Single choke point for all disc scanning.
        Wraps engine.scan_disc() with UI state management and one
        automatic retry. All run_* methods must use this — never
        call engine.scan_disc() directly.
        """
        for attempt in range(3):
            self.log(
                f"Scanning disc on drive "
                f"{self.engine.get_disc_target()}..."
            )
            self.gui.set_status("Scanning... (time varies by disc)")
            self.gui.start_indeterminate()
            try:
                result = self.engine.scan_disc(
                    self.log, self.gui.set_progress
                )
            finally:
                self.gui.stop_indeterminate()
                self.gui.set_progress(0)

            if self.engine.abort_event.is_set():
                self.log("Scan aborted.")
                return None

            if result is None:
                if attempt < 2:
                    self.log("Scan failed — retrying...")
                    time.sleep(2 + attempt)
                continue

            if result is not None:
                # Return even if empty (e.g., bad disc structure).
                # Handle empty result at call site.
                return result

        self.log("Scan failed after 3 attempts.")
        return None

    def check_resume(self, temp_root, media_type=None):
        """Offer workflow-level resume using saved session metadata."""
        resumable = self.engine.find_resumable_sessions(temp_root)
        if not resumable:
            return None
        for full_path, name, meta, file_count in resumable:
            if media_type and meta.get("media_type") not in {None, media_type}:
                continue
            title = meta.get("title", "Unknown")
            ts    = meta.get("timestamp", name)
            phase = meta.get("phase", meta.get("status", "unknown"))
            if self.gui.ask_yesno(
                f"Resume previous session?\n\n"
                f"Title: {title}\n"
                f"Started: {ts}\n"
                f"Phase: {phase}\n"
                f"Files so far: {file_count}\n\n"
                "This reloads saved workflow metadata only. Any partial "
                "rip files will be replaced by a fresh rip."
            ):
                self.log(f"Resuming session: {name}")
                return {
                    "path": full_path,
                    "name": name,
                    "meta": meta,
                }
        return None

    def _parse_int_or_default(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def _init_session_paths(self, overrides=None):
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

    def get_path(self, key):
        if not self.session_paths:
            raise RuntimeError("session_paths not initialized")
        return self.session_paths[key]

    def _log_session_paths(self):
        if not self.session_paths:
            return
        self.log("=== RUN PATHS ===")
        self.log(f"Temp:   {self.session_paths.get('temp')}")
        self.log(f"Movies: {self.session_paths.get('movies')}")
        self.log(f"TV:     {self.session_paths.get('tv')}")
        self.log("=================")

    def _validate_paths(self, temp, movies=None, tv=None):
        def _norm(p):
            return os.path.normcase(os.path.abspath(os.path.normpath(str(p))))

        temp_n = _norm(temp) if temp else None
        movies_n = _norm(movies) if movies else None
        tv_n = _norm(tv) if tv else None

        if temp_n and movies_n and temp_n == movies_n:
            return "Temp and Movies folder cannot be the same"
        if temp_n and tv_n and temp_n == tv_n:
            return "Temp and TV folder cannot be the same"

        blocked = [
            _norm(r"C:\Windows"),
            _norm(r"C:\Program Files"),
            _norm(r"C:\Program Files (x86)"),
        ]

        for p in [x for x in [temp_n, movies_n, tv_n] if x]:
            for b in blocked:
                if p == b or p.startswith(b + os.sep):
                    return f"Blocked system path: {p}"

            if os.path.exists(p) and (not os.access(p, os.W_OK)):
                return f"Path not writable: {p}"

        return None

    def _prompt_run_path_overrides(self, path_fields):
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

        for key, label in path_fields:
            default_path = resolved[key]
            while True:
                entered = self.gui.ask_input(
                    f"{label} (Run Override)",
                    "Select folder path (Skip = keep default):",
                    show_browse=True,
                    default_value=default_path,
                )
                if entered is None:
                    return None

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

        return resolved

    def _restore_selected_titles(self, disc_titles, resume_meta):
        """Return saved selected title ids if they still exist on this disc."""
        saved = resume_meta.get("selected_titles") or []
        if not saved:
            return None
        valid_ids = {int(t.get("id", -1)) for t in disc_titles}
        restored = [int(tid) for tid in saved if int(tid) in valid_ids]
        return restored or None

    def _map_title_ids_to_analyzed_indices(self, titles_list, title_ids):
        """Map MakeMKV title ids to analyze_files indices.

        Primary: explicit engine tracking from rip_selected_titles.
        Fallback: filename parsing tags for legacy compatibility.
        """
        wanted = {int(tid) for tid in (title_ids or [])}
        if not wanted:
            return []
        tracked = getattr(self.engine, "last_title_file_map", {}) or {}
        tracked_lookup = {}
        for tid, files in tracked.items():
            if int(tid) not in wanted:
                continue
            for p in files or []:
                tracked_lookup[os.path.normcase(os.path.abspath(p))] = int(tid)
        mapped = []
        for idx, (path, _dur, _mb) in enumerate(titles_list):
            norm = os.path.normcase(os.path.abspath(path))
            title_id = tracked_lookup.get(norm)
            if title_id is None:
                title_id = self._title_id_from_filename(path)
            if title_id in wanted:
                mapped.append(idx)
        return mapped

    def _fallback_title_from_mode(self, disc_titles=None):
        """Build fallback title string based on configured naming mode."""
        return build_fallback_title(
            self.engine.cfg,
            make_temp_title,
            clean_name,
            choose_best_title,
            disc_titles=disc_titles,
        )

    def _log_ripped_file_sizes(self, mkv_files):
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

    def _title_id_from_filename(self, path):
        name = os.path.basename(path)
        m = re.search(r'title_t(\d+)', name, re.IGNORECASE)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _size_validation_status(self, actual_bytes, expected_bytes):
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

    def _verify_expected_sizes(self, mkv_files, expected_size_by_title):
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
            except Exception:
                pass

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

    def _log_expected_vs_actual_summary(self, mkv_files,
                                        expected_size_by_title):
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
            except Exception:
                pass

        pct = (actual_total / expected_total) * 100
        self.log(
            "Expected total size: "
            f"{expected_total / (1024**3):.2f} GB | "
            f"Actual total size: {actual_total / (1024**3):.2f} GB "
            f"({pct:.1f}%)"
        )

    def _ensure_session_paths(self):
        """Hard guard: raises if session_paths has not been initialized."""
        if not self.session_paths:
            raise RuntimeError(
                "session_paths not initialized — "
                "call _init_session_paths() first"
            )

    def _verify_container_integrity(self, mkv_files, analyzed=None):
        """Require ffprobe-readable container with duration > 0 for each file.

        Accepts an optional pre-analyzed list (from a prior analyze_files call)
        to avoid running ffprobe twice in the same pipeline step.
        """
        if not mkv_files:
            return False
        self.log("Container integrity check (ffprobe)...")
        if analyzed is None:
            analyzed = self.engine.analyze_files(mkv_files, self.log)
        if len(analyzed) != len(mkv_files):
            self.log(
                "ERROR: Container integrity check incomplete "
                f"({len(analyzed)}/{len(mkv_files)} files analyzed)."
            )
            return False
        bad = [os.path.basename(f) for f, dur, _mb in analyzed if dur <= 0]
        if bad:
            self.log(
                "ERROR: Container integrity check failed for: "
                + ", ".join(bad)
            )
            return False
        return True

    def _normalize_rip_result(self, rip_path, success, failed_titles):
        """Collapse rip outcomes into one all-or-nothing success state."""
        mkv_files = sorted(glob.glob(os.path.join(rip_path, "*.mkv")))

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

    def _mark_session_failed(self, rip_path, **metadata):
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

    def preview_title(self, title_id):
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

        def run_preview():
            try:
                if not self._preview_lock.acquire(blocking=False):
                    self.log("Preview already running. Wait for it to finish.")
                    return

                self.log(f"Preview: starting Title {title_id + 1} for 40s...")
                self.gui.set_status(
                    f"Previewing Title {title_id + 1}... (40s sample)"
                )
                self.engine.reset_abort()
                preview_ok = self.engine.rip_preview_title(
                    preview_dir, title_id, 40, self.log
                )

                # MakeMKV may create output in nested paths and can finish
                # metadata flush shortly after process stop. Poll briefly.
                files = []
                for _ in range(8):
                    files = glob.glob(
                        os.path.join(preview_dir, "**", "*.mkv"),
                        recursive=True,
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
                if vlc:
                    subprocess.Popen([vlc, latest])
                    self.log(
                        f"Preview opened in VLC: {os.path.basename(latest)}"
                    )
                else:
                    self.log(
                        "Preview ready, but VLC was not found in PATH. "
                        f"File: {latest}"
                    )
            except Exception as e:
                self.log(f"Preview open failed: {e}")
            finally:
                self.engine.reset_abort()
                self.gui.set_status("Ready")
                if self._preview_lock.locked():
                    self._preview_lock.release()

        threading.Thread(target=run_preview, daemon=True).start()

    def _retry_rip_once_after_size_failure(self, rip_path, selected_ids,
                                           expected_size_by_title):
        """Retry rip once after size sanity failure and re-run checks."""
        self.log(
            "Safe Mode: size sanity failed — retrying rip once automatically."
        )
        self.engine.cleanup_partial_files(rip_path, self.log)
        for pattern in ("**/*.mkv", "**/*.partial"):
            for f in glob.glob(
                os.path.join(rip_path, pattern), recursive=True
            ):
                try:
                    os.remove(f)
                except Exception:
                    pass

        self.gui.set_status("Ripping... (this may take 20-60 min)")
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
            rip_path, success, failed_titles
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

    def _stabilize_file(self, path, timeout_seconds, min_stable_polls):
        """Wait for file to be stable: N equal reads AND 3+ seconds of no growth.

        Stability = file size stopped changing. Size alone is NOT a stability
        signal — extras and short titles are legitimately small. Size validation
        is a separate post-stabilization concern.
        """
        start = time.time()
        try:
            prev = os.path.getsize(path)
        except Exception:
            return False, False

        stable_polls = 0
        stable_start_time = None  # Track when current stability streak began

        while time.time() - start < timeout_seconds:
            if self.engine.abort_event.is_set():
                return False, False
            time.sleep(1.0)
            try:
                cur = os.path.getsize(path)
            except Exception:
                return False, False

            prev_mb = prev / (1024**2)
            cur_mb = cur / (1024**2)
            if cur == prev:
                if stable_start_time is None:
                    stable_start_time = time.time()
                stable_polls += 1
                stable_duration = time.time() - stable_start_time
                self.log(
                    f"Stabilizing: {prev_mb:.0f} MB -> {cur_mb:.0f} MB — "
                    f"stable ({stable_polls}/{min_stable_polls}, "
                    f"{stable_duration:.1f}s duration)"
                )
                # Require BOTH: min poll count AND 3+ seconds of stability
                if stable_polls >= min_stable_polls and stable_duration >= 3.0:
                    # Final re-check catches late flush after brief pause.
                    time.sleep(1.0)
                    try:
                        post = os.path.getsize(path)
                    except Exception:
                        return False, False
                    if post == cur:
                        return True, False
                    self.log(
                        f"Stabilizing: {cur / (1024**2):.0f} MB -> "
                        f"{post / (1024**2):.0f} MB — resumed growth"
                    )
                    stable_polls = 0
                    stable_start_time = None
                    prev = post
                    continue
            else:
                stable_polls = 0
                stable_start_time = None
                self.log(
                    f"Stabilizing: {prev_mb:.0f} MB -> {cur_mb:.0f} MB — still growing"
                )
            prev = cur

        self.log(
            f"WARNING: File stabilization timed out after {timeout_seconds}s: "
            f"{os.path.basename(path)}"
        )
        return False, True

    # CRITICAL:
    # All size threshold decisions for ripped files MUST go through this
    # function. Do not duplicate or inline this logic elsewhere.
    @staticmethod
    def _compute_file_min_size(expected_bytes, floor_bytes):
        """Return the minimum acceptable size for a ripped file.

        If expected_bytes comes from disc metadata and is credibly large
        (> 100 MB), trust it: accept down to 50% of that figure.
        This lets 0.47 GB extras pass while still catching truncated rips.

        The result is capped at expected_bytes itself to guard against
        inflated playlist sizes (e.g. fake 20 GB title) producing a
        threshold higher than the real file could ever satisfy.

        If expected is zero, missing, or suspiciously small (bad parse /
        corrupt metadata), fall back to the global floor from settings.
        """
        _100_MB = 100 * 1024 * 1024
        if expected_bytes > _100_MB:
            return min(int(expected_bytes * 0.5), expected_bytes)
        return floor_bytes

    def _stabilize_ripped_files(self, mkv_files, expected_size_by_title=None):
        """Optionally wait for ripped files to stabilize before analysis/move.

        Stabilization = file stopped changing size. The minimum-size floor is
        NOT checked here; a small file (extra, short feature) is stable the
        moment it stops writing. Size validation lives in _verify_expected_sizes.
        """
        cfg = self.engine.cfg
        if not cfg.get("opt_file_stabilization", True):
            return True, False

        base_timeout = max(
            1, int(cfg.get("opt_stabilize_timeout_seconds", 60))
        )
        default_polls = max(
            3, int(cfg.get("opt_stabilize_required_polls", 4))
        )
        min_size_floor = max(
            0, int(cfg.get("opt_min_rip_size_gb", 1) * (1024**3))
        )

        for f in sorted(mkv_files):
            if self.engine.abort_event.is_set():
                return False, False

            current_size = os.path.getsize(f)
            expected = 0
            if expected_size_by_title:
                tid = self._title_id_from_filename(f)
                if tid is not None:
                    expected = int(expected_size_by_title.get(tid, 0) or 0)
            # Use expected size (from disc scan) for timeout budget when
            # available; otherwise use current on-disk size. Both are capped.
            size_for_timeout = max(expected, current_size)
            size_gb = size_for_timeout / (1024**3)
            # Cap timeout: don't scale unboundedly with size.
            timeout = max(base_timeout, min(300, int(size_gb * 5)))
            polls = default_polls if size_gb >= 5 else max(3, default_polls - 1)

            ok, timed_out = self._stabilize_file(f, timeout, polls)
            if not ok:
                return False, timed_out

            # Post-stabilization size advisory: log when file is below the
            # effective threshold but do NOT fail — extras are legitimately
            # small. Strict size validation uses ratio checks in
            # _verify_expected_sizes after all files are stable.
            try:
                final_size = os.path.getsize(f)
            except Exception:
                final_size = 0
            effective_floor = self._compute_file_min_size(expected, min_size_floor)
            if effective_floor > 0 and final_size < effective_floor:
                detail = (
                    f"expected {expected / (1024**3):.2f} GB"
                    f" → threshold {effective_floor / (1024**3):.2f} GB"
                    if expected > 0 else
                    f"advisory floor {effective_floor / (1024**2):.0f} MB"
                    f" — normal for extras/short titles"
                )
                self.log(
                    f"INFO: {os.path.basename(f)}: "
                    f"{final_size / (1024**2):.0f} MB "
                    f"(below threshold — {detail})"
                )

        return True, False

    def run_tv_disc(self):
        """Run manual TV-disc workflow."""
        self._run_disc(is_tv=True)

    def run_movie_disc(self):
        """Run manual movie-disc workflow."""
        self._run_disc(is_tv=False)

    def run_smart_rip(self):
        """Auto-select and rip the highest-scoring main movie title."""
        cfg        = self.engine.cfg
        path_overrides = self._prompt_run_path_overrides([
            ("movies_folder", "Movies Folder"),
            ("temp_folder", "Temp Folder"),
        ])
        if path_overrides is None:
            self.log("Cancelled before rip (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._log_session_paths()
        movie_root = self.get_path("movies")
        temp_root = self.get_path("temp")

        self._reset_state_machine()
        self.engine.reset_abort()
        self._wiped_session_paths.clear()
        self.session_report = []
        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            return

        self.gui.show_info(
            "Smart Rip",
            "Insert disc and click OK.\n\n"
            "Smart Rip will automatically select the main feature."
        )

        title = self.gui.ask_input("Title", "Movie title:")
        auto_title_pending = not bool(title)
        if auto_title_pending:
            self.log(
                "WARNING: No title entered — will use fallback naming "
                "mode after scan."
            )

        year = self.gui.ask_input("Year", "Release year:")
        if not year:
            year = "0000"
            self.log("WARNING: No year — using 0000")

        time.sleep(2)  # drive spin-up / mount stabilization
        disc_titles = self.scan_with_retry()

        if self.engine.abort_event.is_set():
            return

        if disc_titles is None:
            self._state_fail("scan_failed")
            self.log("Could not read disc.")
            self.gui.show_error(
                "Scan Failed",
                "Disc scan failed after retry.\n\n"
                "Try cleaning the disc and retrying."
            )
            return
        if disc_titles == []:
            self.log("Scan completed but no titles were found on this disc.")
            self._state_fail("scan_no_titles")
            self.gui.show_error(
                "No Titles Found",
                "Disc was readable, but no rip-able titles were found.\n\n"
                "This can happen with unsupported or empty media."
            )
            return
        self._state_transition(SessionState.SCANNED)

        if auto_title_pending:
            title = self._fallback_title_from_mode(disc_titles)
            self.log(f"Auto title used: {title}")

        best, smart_score = choose_best_title(
            disc_titles, require_valid=True
        )
        if not best:
            self.log("Could not select a valid title for Smart Rip.")
            return

        low_conf = float(cfg.get("opt_smart_low_confidence_threshold", 0.45))
        if smart_score < low_conf:
            self.log(
                f"WARNING: Low-confidence Smart Rip selection "
                f"(score={smart_score:.3f} < {low_conf:.2f})."
            )
            if not self.gui.ask_yesno(
                f"Smart Rip confidence is low ({smart_score:.3f}).\n\n"
                "Disc structure may be ambiguous or damaged.\n"
                "Continue with this auto-selected title?"
            ):
                self.log("Cancelled due to low-confidence Smart Rip score.")
                return

        # Guardrail: movie discs where the "best" title is very short
        # are often extras/featurettes, not the main feature.
        min_minutes = max(1, int(cfg.get("opt_smart_min_minutes", 20)))
        best_seconds = int(best.get("duration_seconds", 0) or 0)
        if best_seconds > 0 and best_seconds < min_minutes * 60:
            mins = best_seconds / 60
            self.log(
                f"WARNING: Smart Rip best title is only {mins:.1f} min "
                f"(< {min_minutes} min threshold)."
            )
            if not self.gui.ask_yesno(
                f"Smart Rip warning: best title is only {mins:.1f} min.\n\n"
                f"This is often an extra, not the main movie.\n"
                f"Continue anyway?"
            ):
                self.log("Cancelled due to Smart Rip short-title warning.")
                return

        selected_ids  = [best["id"]]
        selected_size = best.get("size_bytes", 0)
        expected_size_by_title = {
            int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
            for t in disc_titles
            if int(t.get("id", -1)) in selected_ids
        }

        self.log(
            f"Smart Rip selected: Title {best['id']+1} "
                f"(score={smart_score:.3f}) "
                f"{best['duration']} {best['size']}"
        )

        if cfg.get("opt_confirm_before_rip", True):
            if not self.gui.ask_yesno(
                f"Smart Rip selected Title {best['id']+1} "
                    f"(score={smart_score:.3f}) "
                    f"{best['duration']} {best['size']} as main feature. "
                    f"Continue?"
            ):
                self.log("Cancelled.")
                return

        keep_extras = self.gui.ask_yesno("Keep extras from this disc?")
        if keep_extras:
            selected_ids  = [t["id"] for t in disc_titles]
            selected_size = sum(
                t.get("size_bytes", 0) for t in disc_titles
            )
            expected_size_by_title = {
                int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
                for t in disc_titles
                if int(t.get("id", -1)) in selected_ids
            }
            self.log(
                f"Extras enabled — ripping all "
                f"{len(selected_ids)} titles."
            )

        movie_folder  = os.path.join(
            movie_root, f"{clean_name(title)} ({year})"
        )
        extras_folder = os.path.join(movie_folder, "Extras")
        os.makedirs(movie_folder, exist_ok=True)
        os.makedirs(extras_folder, exist_ok=True)

        if selected_size > 0 and cfg.get("opt_scan_disc_size", True):
            status, free, required = self.engine.check_disk_space(
                temp_root, selected_size, self.log
            )
            if status == "block":
                self.gui.show_error(
                    "Critically Low Space",
                    f"Only {free / (1024**3):.1f} GB free.\n"
                    f"Minimum: "
                    f"{cfg.get('opt_hard_block_gb', 20)} GB."
                )
                return
            elif (status == "warn" and
                  cfg.get("opt_warn_low_space", True)):
                if not self.gui.ask_space_override(
                    required / (1024**3), free / (1024**3)
                ):
                    return

        rip_path = os.path.join(temp_root, make_rip_folder_name())
        os.makedirs(rip_path, exist_ok=True)
        self.engine.write_temp_metadata(rip_path, title, 1)

        status_msg = (
            "Ripping all titles..."
            if keep_extras else
            "Ripping main feature..."
        )
        self.gui.set_status("Ripping... (this may take 20-60 min)")
        success, failed_titles = self.engine.rip_selected_titles(
            rip_path, selected_ids,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        self._warn_degraded_rips()
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, failed_titles
        )

        if not success:
            self._state_fail("rip_failed")
            self.report(f"Smart Rip failed for {title} ({year})")
            self._mark_session_failed(
                rip_path,
                title=title,
                year=year,
                media_type="movie",
                selected_titles=list(selected_ids),
                dest_folder=movie_folder,
                failed_titles=list(failed_titles),
            )
            self.flush_log()
            return
        self._state_transition(SessionState.RIPPED)

        self.engine.update_temp_metadata(rip_path, status="ripped")

        self._log_ripped_file_sizes(mkv_files)
        stabilized, timed_out = self._stabilize_ripped_files(
            mkv_files, expected_size_by_title
        )
        if not stabilized:
            self._state_fail("stabilization_failed")
            self.log("File stabilization check failed after rip.")
            self.report(
                f"Smart Rip stabilization failed for {title} ({year})"
            )
            self._mark_session_failed(
                rip_path,
                title=title,
                year=year,
                media_type="movie",
                selected_titles=list(selected_ids),
                dest_folder=movie_folder,
            )
            self.gui.show_error(
                "Rip Failed",
                (
                    "Ripped file(s) did not stabilize in time.\n\n"
                    if timed_out else
                    "Ripped file(s) failed stabilization checks.\n\n"
                ) +
                "Move is blocked to prevent partial file corruption."
            )
            return
        self._state_transition(SessionState.STABILIZED)
        self._log_expected_vs_actual_summary(
            mkv_files, expected_size_by_title
        )
        size_status, size_reason = self._verify_expected_sizes(
            mkv_files, expected_size_by_title
        )
        if size_status == "hard_fail":
            self.log("ERROR: Size sanity check failed after rip.")
            retried_ok = self._retry_rip_once_after_size_failure(
                rip_path, selected_ids, expected_size_by_title
            )
            if not retried_ok:
                self._state_fail("size_validation_failed")
                self.report(
                    f"Smart Rip failed size sanity check for {title} ({year})"
                )
                self._mark_session_failed(
                    rip_path,
                    title=title,
                    year=year,
                    media_type="movie",
                    selected_titles=list(selected_ids),
                    dest_folder=movie_folder,
                )
                self.flush_log()
                self.gui.show_error(
                    "Rip Failed",
                    "Rip incomplete — file too small.\n\n"
                    "Automatic retry was attempted once and still failed."
                )
                return
        elif size_status == "warn":
            if not self.gui.ask_yesno(
                "Rip size is below preferred threshold.\n\n"
                f"{size_reason}\n\n"
                "Continue anyway?"
            ):
                self._state_fail("size_warning_declined")
                self.log("Cancelled due to size warning threshold.")
                return
            self.report(
                f"USER OVERRIDE — Smart Rip size warning for {title} ({year})"
            )

        # Analyze files once; reuse the result for both integrity check and
        # the title-picker/move step. This avoids running ffprobe twice.
        self.gui.set_status("Analyzing...")
        self.gui.start_indeterminate()
        try:
            titles_list = self.engine.analyze_files(
                mkv_files, self.log
            )
        finally:
            self.gui.stop_indeterminate()
            self.gui.set_progress(0)

        if not titles_list:
            self._state_fail("analysis_failed")
            return

        # Container integrity uses the already-analyzed data — no extra ffprobe.
        if not self._verify_container_integrity(mkv_files, analyzed=titles_list):
            self._state_fail("pre_move_integrity_failed")
            self.report(
                f"Smart Rip ffprobe integrity check failed for {title} ({year})"
            )
            self._mark_session_failed(
                rip_path,
                title=title,
                year=year,
                media_type="movie",
                selected_titles=list(selected_ids),
                dest_folder=movie_folder,
            )
            self.gui.show_error(
                "Rip Failed",
                "Container integrity check failed (ffprobe).\n\n"
                "Move is blocked to prevent corrupt files in library."
            )
            return
        self._state_transition(SessionState.VALIDATED)

        # Map analyzed files back to MakeMKV title ids when possible.
        # Primary path uses explicit tracking captured during rip.
        # This avoids assuming analyze_files sort order matches smart score.
        main_indices = [0]
        if keep_extras:
            mapped = self._map_title_ids_to_analyzed_indices(
                titles_list, [best.get("id")]
            )
            if mapped:
                # Multi-file title safe: pick the largest mapped file.
                chosen_idx = max(
                    mapped,
                    key=lambda i: int(titles_list[i][2] * (1024**2)),
                )
                main_indices = [chosen_idx]
            else:
                def _closest_size_fallback():
                    target_size = int(best.get("size_bytes", 0) or 0)
                    if target_size > 0 and titles_list:
                        idx = min(
                            range(len(titles_list)),
                            key=lambda i: abs(
                                int(titles_list[i][2] * (1024**2)) - target_size
                            )
                        )
                        self.log(
                            "Warning: smart title id mapping failed; using "
                            "closest-size analyzed file as main."
                        )
                        return [idx]
                    idx = max(
                        range(len(titles_list)),
                        key=lambda i: int(titles_list[i][2] * (1024**2)),
                    )
                    self.log(
                        "Warning: could not map smart-selected title id to "
                        "analyzed files; falling back to largest file."
                    )
                    return [idx]

                resolved = handle_fallback(
                    self,
                    "Title mapping failed",
                    _closest_size_fallback,
                )
                if resolved is None:
                    self._state_fail("title_mapping_failed")
                    self.report(
                        f"Smart Rip mapping failed for {title} ({year})"
                    )
                    self.gui.show_error(
                        "Mapping Failed",
                        "Could not map ripped files back to selected title."
                    )
                    self.write_session_summary()
                    self.flush_log()
                    self.gui.set_progress(0)
                    return
                main_indices = resolved
        self.gui.set_status("Moving files...")
        ok, _, moved_paths = self.engine.move_files(
            titles_list, main_indices,
            episode_numbers=[], real_names=[],
            keep_extras=keep_extras,
            is_tv=False,
            title=title, dest_folder=movie_folder,
            extras_folder=extras_folder,
            season=0, year=year,
            extra_counter=1,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        if ok:
            post_status, post_reason = self._verify_expected_sizes(
                moved_paths, expected_size_by_title
            )
            if post_status == "hard_fail":
                self._state_fail("post_move_size_validation_failed")
                self.report(
                    f"Smart Rip post-move validation failed for {title} ({year})"
                )
                self.gui.show_error(
                    "Post-Move Validation Failed",
                    f"Moved file(s) failed size validation:\n{post_reason}\n\n"
                    "Source temp files were already moved. Re-check output manually."
                )
                ok = False
            elif post_status == "warn":
                self.report(
                    f"USER OVERRIDE — Smart Rip post-move size warning for {title} ({year})"
                )
            if ok and (not self._verify_container_integrity(moved_paths)):
                self.report(
                    f"Smart Rip post-move ffprobe check failed for {title} ({year})"
                )
                self.gui.show_error(
                    "Post-Move Validation Failed",
                    "Moved file(s) failed container integrity check (ffprobe)."
                )
                self._state_fail("post_move_integrity_failed")
                ok = False
        if ok:
            self._state_transition(SessionState.MOVED)
        if ok:
            shutil.rmtree(rip_path, ignore_errors=True)
            if os.path.exists(rip_path):
                self.log(f"Warning: could not delete {rip_path}")
        else:
            if self.sm.state != SessionState.FAILED:
                self._state_fail("move_failed")
            self.report(
                f"Smart Rip move failed for {title} ({year})"
            )
            self.log(f"Temp preserved at: {rip_path}")

        if ok:
            self._state_transition(SessionState.COMPLETED)

        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        if ok:
            self.gui.show_info(
                "Smart Rip Complete",
                f"Files moved to:\n{movie_folder}"
            )
        else:
            self.gui.show_error(
                "Smart Rip Failed",
                "Move did not complete successfully.\n\n"
                f"Temp preserved at:\n{rip_path}"
            )

    def run_dump_all(self):
        """Rip all titles to temp storage for later organization."""
        cfg       = self.engine.cfg
        path_overrides = self._prompt_run_path_overrides([
            ("temp_folder", "Temp Folder"),
        ])
        if path_overrides is None:
            self.log("Cancelled before dump (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._log_session_paths()
        temp_root = self.get_path("temp")

        multi_disc = self.gui.ask_yesno(
            "Dump multiple discs in one unattended session?\n\n"
            "Yes = multi-disc with auto swap detection\n"
            "No = single-disc dump"
        )
        if multi_disc:
            self._run_dump_all_multi(temp_root)
            return

        if cfg.get("opt_show_temp_manager", True):
            self.gui.show_temp_manager(
                self.engine.find_old_temp_folders(temp_root),
                self.engine, self.log
            )
        if self.engine.abort_event.is_set():
            return

        self.gui.show_info(
            "Insert Disc", "Insert disc and click OK when ready."
        )
        time.sleep(2)  # drive spin-up / mount stabilization

        title = self.gui.ask_input(
            "Title", "Exact title (used for folder name):"
        )
        if not title:
            title = self._fallback_title_from_mode()
            self.log(f"WARNING: No title — using: {title}")

        rip_path = os.path.join(temp_root, make_rip_folder_name())
        os.makedirs(rip_path, exist_ok=True)
        self.engine.write_temp_metadata(rip_path, title, 1)

        if cfg.get("opt_scan_disc_size", True):
            self.gui.set_status("Scanning disc size...")
            self.gui.start_indeterminate()
            try:
                disc_size = self.engine.get_disc_size(self.log)
            finally:
                self.gui.stop_indeterminate()
                self.gui.set_progress(0)

            if self.engine.abort_event.is_set():
                return

            if disc_size:
                status, free, required = self.engine.check_disk_space(
                    temp_root, disc_size, self.log
                )
                if status == "block":
                    self.gui.show_error(
                        "Critically Low Space",
                        f"Only {free / (1024**3):.1f} GB free.\n"
                        f"Minimum: "
                        f"{cfg.get('opt_hard_block_gb', 20)} GB."
                    )
                    return
                elif (status == "warn" and
                      cfg.get("opt_warn_low_space", True)):
                    if not self.gui.ask_space_override(
                        required / (1024**3), free / (1024**3)
                    ):
                        self.log("Cancelled: not enough space.")
                        return

        self.gui.set_status("Ripping all titles...")
        success = self.engine.rip_all_titles(
            rip_path,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, []
        )

        if not success:
            self.log("Rip did not complete.")
            self.report(f"Dump All: rip failed for {title}")
            self.flush_log()
            return

        self.engine.update_temp_metadata(rip_path, status="ripped")
        self.log(
            f"Dump complete. "
            f"{len(mkv_files)} file(s) saved to: {rip_path}"
        )
        self._log_ripped_file_sizes(mkv_files)
        stabilized, timed_out = self._stabilize_ripped_files(mkv_files)
        if not stabilized:
            self.log("File stabilization check failed after rip.")
            self.report("Manual dump failed stabilization check")
            self.gui.show_error(
                "Rip Failed",
                (
                    "Ripped file(s) did not stabilize in time.\n\n"
                    if timed_out else
                    "Ripped file(s) failed stabilization checks.\n\n"
                ) +
                "Move is blocked to prevent partial file corruption."
            )
            return
        if not self._verify_container_integrity(mkv_files):
            self.report("Manual dump failed ffprobe integrity check")
            self.gui.show_error(
                "Rip Failed",
                "Container integrity check failed (ffprobe)."
            )
            return
        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        self.gui.show_info(
            "Dump Complete",
            f"Ripped {len(mkv_files)} file(s) to:\n{rip_path}\n\n"
            f"Use 'Organize Existing MKVs' to sort them."
        )

    def _disc_present(self):
        """Best-effort check: True when a readable disc appears present."""
        try:
            first = self.engine.get_disc_size(lambda _m: None)
            if first is None:
                return False
            time.sleep(0.5)
            second = self.engine.get_disc_size(lambda _m: None)
            return second is not None
        except Exception:
            return False

    def _wait_for_disc_state(self, want_present, timeout_seconds=300):
        state_text = "inserted" if want_present else "removed"
        start    = time.time()
        last_log = 0
        self.log(f"Waiting for disc to be {state_text}...")
        while time.time() - start < timeout_seconds:
            if self.engine.abort_event.is_set():
                return False
            if self._disc_present() == want_present:
                return True
            remaining = int(timeout_seconds - (time.time() - start))
            self.gui.set_status(
                f"Waiting for disc to be {state_text} "
                f"({max(0, remaining)}s)..."
            )
            # Log a heartbeat every ~10 s so the user sees activity.
            elapsed = int(time.time() - start)
            if elapsed - last_log >= 10:
                self.log(
                    f"Still waiting for disc to be {state_text} "
                    f"({max(0, remaining)}s remaining)..."
                )
                last_log = elapsed
            # Split sleep into short intervals so abort is responsive.
            for _ in range(20):
                if self.engine.abort_event.is_set():
                    return False
                time.sleep(0.1)
        return False

    def _build_disc_fingerprint(self):
        """Build a disc fingerprint using the standard scan retry path."""
        titles = self.scan_with_retry()
        if not titles:
            return None
        parts = [str(len(titles))]
        sorted_titles = sorted(
            titles,
            key=lambda t: (
                t.get("duration_seconds", 0)
                if isinstance(t.get("duration_seconds"), (int, float))
                else 0,
                t.get("size_bytes", 0)
                if isinstance(t.get("size_bytes"), (int, float))
                else 0,
            ),
            reverse=True,
        )
        total_size = sum(
            int(t.get("size_bytes", 0) or 0) for t in sorted_titles
        )
        total_duration = sum(
            int(t.get("duration_seconds", 0) or 0) for t in sorted_titles
        )
        parts.append(f"sum:{total_duration}:{total_size}")
        # Use up to 50 entries to reduce collisions on large-but-similar discs.
        for t in sorted_titles[:50]:
            parts.append(
                f"{t.get('duration_seconds', 0)}:"
                f"{t.get('size_bytes', 0)}:"
                f"{safe_int(t.get('chapters', 0))}:"
                f"{len(t.get('audio_tracks', []))}:"
                f"{len(t.get('subtitle_tracks', []))}"
            )
        return "|".join(parts)

    def _resolve_duplicate_dump_disc(self, disc_number, total,
                                     per_disc_titles):
        """Resolve duplicate-disc detection with an easy custom-title override."""
        disc_label = (
            per_disc_titles[disc_number - 1]
            if disc_number - 1 < len(per_disc_titles)
            else ""
        )
        if disc_label:
            if self.gui.ask_yesno(
                "This disc looks like a duplicate from earlier in this "
                f"session, but slot {disc_number}/{total} has custom title:\n"
                f"\"{disc_label}\"\n\n"
                "Continue anyway with this disc?"
            ):
                self.log(
                    "Duplicate check override accepted for labeled disc: "
                    f"{disc_label}"
                )
                return "bypass"

        return self.gui.ask_duplicate_resolution(
            "This disc looks like a duplicate from earlier in this "
            "session.",
            "Swap and Retry",
            "Not a Dup",
            "Stop"
        )

    def _wait_for_new_unique_disc(self, seen_fingerprints,
                                  disc_number, total):
        """
        Wait for physical swap and ensure inserted disc is unique in this
        unattended batch session.
        """
        if disc_number == 1:
            self.gui.show_info(
                "Insert Disc",
                f"Insert disc {disc_number}/{total} and click OK."
            )
            time.sleep(2)  # drive spin-up / mount stabilization
        else:
            self.gui.show_info(
                "Swap Disc",
                "Remove current disc (tray open/close), then insert the "
                f"next disc ({disc_number}/{total}) and click OK."
            )

            self.log("Waiting for disc removal...")
            removed = self._wait_for_disc_state(
                want_present=False,
                timeout_seconds=300
            )
            if not removed:
                self.report(
                    f"Disc {disc_number}: timed out waiting for removal."
                )
                return None
            self.log("Disc removal detected.")

            self.log("Waiting for next disc insertion...")
            inserted = self._wait_for_disc_state(
                want_present=True,
                timeout_seconds=300
            )
            if not inserted:
                self.report(
                    f"Disc {disc_number}: timed out waiting for insertion."
                )
                return None
            self.log("New disc insertion detected.")

        time.sleep(2)  # settle before reading fingerprint
        fingerprint = self._build_disc_fingerprint()
        if not fingerprint:
            self.report(
                f"Disc {disc_number}: could not read disc fingerprint."
            )
            return None

        if fingerprint in seen_fingerprints:
            self.log(
                "Duplicate disc detected (already dumped in this session)."
            )
            return "duplicate"

        seen_fingerprints.add(fingerprint)
        return fingerprint

    def _collect_dump_all_multi_setup(self):
        """Collect unattended batch setup with a review/edit loop."""
        while True:
            total_str = self.gui.ask_input(
                "Disc Count", "How many discs do you want to dump?"
            )
            if total_str is None:
                return None
            total = int(total_str) if (
                total_str and total_str.isdigit()
            ) else 1
            total = max(1, total)

            per_disc_titles_input = self.gui.ask_input(
                "Disc Titles (Optional)",
                "Optional titles in order (comma or ' - ' separated),\n"
                "e.g. Toony, Herb, Jeckel"
            )
            if per_disc_titles_input is None:
                return None
            per_disc_titles = parse_ordered_titles(per_disc_titles_input)

            batch_title = self.gui.ask_input(
                "Batch Name",
                "Optional batch name for temp folder (blank = timestamp):"
            )
            if batch_title is None:
                return None
            if not batch_title:
                batch_title = self._fallback_title_from_mode()

            titles_preview = (
                ", ".join(per_disc_titles[:3]) +
                ("..." if len(per_disc_titles) > 3 else "")
                if per_disc_titles else "(none)"
            )
            if self.gui.ask_yesno(
                "Review unattended setup:\n\n"
                f"Disc count: {total}\n"
                f"Batch name: {batch_title}\n"
                f"Custom disc titles: {len(per_disc_titles)}\n"
                f"Preview: {titles_preview}\n\n"
                "Continue with these settings?\n"
                "No = go back and edit"
            ):
                return total, per_disc_titles, batch_title

            self.log("Setup edit requested — re-enter unattended settings.")

    def _run_dump_all_multi(self, temp_root):
        cfg = self.engine.cfg

        self.engine.reset_abort()
        self.session_report = []
        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            return

        setup = self._collect_dump_all_multi_setup()
        if setup is None:
            self.log("Unattended dump cancelled during setup.")
            return
        total, per_disc_titles, batch_title = setup
        if per_disc_titles:
            self.log(
                f"Using custom disc titles for first "
                f"{len(per_disc_titles)} disc(s)."
            )

        batch_root = os.path.join(
            temp_root,
            f"DumpBatch_{clean_name(batch_title)}_{make_rip_folder_name()}"
        )
        os.makedirs(batch_root, exist_ok=True)
        self.log(f"Unattended dump batch root: {batch_root}")
        self.log(f"Planned discs: {total}")

        seen_fingerprints = set()
        disc_number = 1
        while disc_number <= total:
            if self.engine.abort_event.is_set():
                self.log("Unattended dump aborted.")
                break

            fingerprint = self._wait_for_new_unique_disc(
                seen_fingerprints, disc_number, total
            )
            if fingerprint is None:
                if self.gui.ask_yesno(
                    "Could not verify a new disc. Try again for this slot?"
                ):
                    continue
                self.log("Cancelled unattended dump.")
                break

            if fingerprint == "duplicate":
                duplicate_action = self._resolve_duplicate_dump_disc(
                    disc_number,
                    total,
                    per_disc_titles,
                )
                if duplicate_action == "retry":
                    continue
                if duplicate_action == "bypass":
                    self.log(
                        "Manual duplicate bypass selected; proceeding "
                        "with this disc."
                    )
                else:
                    self.report(
                        f"Disc {disc_number}: duplicate disc not accepted."
                    )
                    break

            safe_marker = f"disc_{disc_number:02d}"
            rip_path = os.path.join(
                batch_root, f"Disc_{disc_number:02d}_{safe_marker}"
            )
            os.makedirs(rip_path, exist_ok=True)
            disc_title = (
                per_disc_titles[disc_number - 1]
                if disc_number - 1 < len(per_disc_titles)
                else f"Dump {disc_number:02d}"
            )
            self.engine.write_temp_metadata(
                rip_path,
                disc_title,
                disc_number
            )
            self.log(
                f"--- Dump disc {disc_number}/{total}: {disc_title} ---"
            )

            if cfg.get("opt_scan_disc_size", True):
                self.gui.set_status("Scanning disc size...")
                self.gui.start_indeterminate()
                try:
                    disc_size = self.engine.get_disc_size(self.log)
                finally:
                    self.gui.stop_indeterminate()
                    self.gui.set_progress(0)

                if self.engine.abort_event.is_set():
                    break

                if disc_size:
                    status, free, required = self.engine.check_disk_space(
                        temp_root, disc_size, self.log
                    )
                    if status == "block":
                        self.gui.show_error(
                            "Critically Low Space",
                            f"Only {free / (1024**3):.1f} GB free.\n"
                            f"Minimum: "
                            f"{cfg.get('opt_hard_block_gb', 20)} GB."
                        )
                        self.report(
                            f"Dump disc {disc_number}: blocked by low space."
                        )
                        break
                    elif (status == "warn" and
                          cfg.get("opt_warn_low_space", True)):
                        if not self.gui.ask_space_override(
                            required / (1024**3), free / (1024**3)
                        ):
                            self.report(
                                f"Dump disc {disc_number}: cancelled for space."
                            )
                            break

            self.gui.set_status("Ripping... (this may take 20-60 min)")
            success = self.engine.rip_all_titles(
                rip_path,
                on_progress=self.gui.set_progress,
                on_log=self.log
            )
            success, mkv_files = self._normalize_rip_result(
                rip_path, success, []
            )

            if not success:
                self.report(
                    f"Dump disc {disc_number}: rip failed."
                )
                self.flush_log()
                if disc_number < total and self.gui.ask_yesno(
                    "This disc failed. Continue with next disc?"
                ):
                    disc_number += 1
                    continue
                break

            self.engine.update_temp_metadata(rip_path, status="ripped")
            self.log(
                f"Dump disc {disc_number} complete. "
                f"{len(mkv_files)} file(s) saved to: {rip_path}"
            )
            self._log_ripped_file_sizes(mkv_files)
            stabilized, timed_out = self._stabilize_ripped_files(mkv_files)
            if not stabilized:
                self.log("File stabilization check failed after rip.")
                self.report(
                    f"Dump disc {disc_number} failed stabilization check"
                )
                self.gui.show_error(
                    "Rip Failed",
                    (
                        f"Disc {disc_number} did not stabilize in time.\n\n"
                        if timed_out else
                        f"Disc {disc_number} failed stabilization checks.\n\n"
                    ) +
                    "Stopping unattended dump to prevent partial files."
                )
                break
            if not self._verify_container_integrity(mkv_files):
                self.report(
                    f"Dump disc {disc_number} failed ffprobe integrity check"
                )
                self.gui.show_error(
                    "Rip Failed",
                    "Container integrity check failed (ffprobe).\n\n"
                    "Stopping unattended dump to prevent corrupt files."
                )
                break
            self.gui.set_progress(0)
            disc_number += 1

        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        self.gui.set_status("Ready")
        if self.engine.abort_event.is_set():
            self.gui.show_info(
                "Unattended Dump Stopped",
                f"Session stopped. Files saved so far in:\n{batch_root}"
            )
            return
        self.gui.show_info(
            "Unattended Dump Complete",
            f"Batch output:\n{batch_root}\n\n"
            f"Use 'Organize Existing MKVs' to sort them."
        )

    def _prepare_unattended_session(self, temp_root, mode_label):
        """Initialize unattended mode state and optionally show temp manager."""
        self.engine.reset_abort()
        self.session_report = []
        self.log(f"{mode_label} started.")
        self.engine.cleanup_partial_files(temp_root, self.log)
        if self.engine.cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            self.log(f"{mode_label} cancelled.")
            return False
        return True

    def run_unattended_single(self):
        cfg       = self.engine.cfg
        path_overrides = self._prompt_run_path_overrides([
            ("temp_folder", "Temp Folder"),
        ])
        if path_overrides is None:
            self.log("Cancelled before unattended single (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._log_session_paths()
        temp_root = self.get_path("temp")

        if not self._prepare_unattended_session(
            temp_root, "Unattended single-disc mode"
        ):
            return

        self.gui.show_info(
            "Unattended — Single Disc",
            "Insert disc and click OK. "
            "Everything will be ripped automatically."
        )
        time.sleep(2)  # drive spin-up / mount stabilization

        rip_path = os.path.join(
            temp_root, f"Unattended_{make_rip_folder_name()}"
        )
        os.makedirs(rip_path, exist_ok=True)
        self.engine.write_temp_metadata(rip_path, "Unattended", 1)
        self.log(f"Unattended single disc — temp: {rip_path}")

        if cfg.get("opt_scan_disc_size", True):
            self.gui.set_status("Scanning disc size...")
            self.gui.start_indeterminate()
            try:
                disc_size = self.engine.get_disc_size(self.log)
            finally:
                self.gui.stop_indeterminate()
                self.gui.set_progress(0)

            if self.engine.abort_event.is_set():
                return

            if disc_size:
                status, free, required = self.engine.check_disk_space(
                    temp_root, disc_size, self.log
                )
                if status == "block":
                    self.gui.show_error(
                        "Critically Low Space",
                        f"Only {free / (1024**3):.1f} GB free.\n"
                        f"Minimum: "
                        f"{cfg.get('opt_hard_block_gb', 20)} GB."
                    )
                    return
                elif (status == "warn" and
                      cfg.get("opt_warn_low_space", True)):
                    if not self.gui.ask_space_override(
                        required / (1024**3), free / (1024**3)
                    ):
                        return

        self.gui.set_status("Ripping... (this may take 20-60 min)")
        success = self.engine.rip_all_titles(
            rip_path,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, []
        )

        if not success:
            self.report("Unattended single: rip failed.")
            self.flush_log()
            self.gui.show_error(
                "Rip Failed", "Disc could not be ripped."
            )
            return

        self.engine.update_temp_metadata(rip_path, status="ripped")
        self.log(f"Done. {len(mkv_files)} file(s) in: {rip_path}")
        self._log_ripped_file_sizes(mkv_files)
        stabilized, timed_out = self._stabilize_ripped_files(mkv_files)
        if not stabilized:
            self.log("File stabilization check failed after rip.")
            self.report("Unattended current-disc rip failed stabilization check")
            self.gui.show_error(
                "Rip Failed",
                (
                    "Ripped file(s) did not stabilize in time.\n\n"
                    if timed_out else
                    "Ripped file(s) failed stabilization checks.\n\n"
                ) +
                "Move is blocked to prevent partial file corruption."
            )
            return
        if not self._verify_container_integrity(mkv_files):
            self.report("Unattended current-disc ffprobe integrity check failed")
            self.gui.show_error(
                "Rip Failed",
                "Container integrity check failed (ffprobe)."
            )
            return
        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        self.gui.show_info(
            "Unattended Complete",
            f"Ripped {len(mkv_files)} file(s) to:\n{rip_path}\n\n"
            f"Use 'Organize Existing MKVs' to sort them."
        )

    def run_unattended_series(self):
        cfg       = self.engine.cfg
        path_overrides = self._prompt_run_path_overrides([
            ("temp_folder", "Temp Folder"),
        ])
        if path_overrides is None:
            self.log("Cancelled before unattended series (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._log_session_paths()
        temp_root = self.get_path("temp")

        if not self._prepare_unattended_session(
            temp_root, "Unattended series mode"
        ):
            return

        title = self.gui.ask_input(
            "Series Title", "Exact series title:"
        )
        if not title:
            title = self._fallback_title_from_mode()
            self.log(f"WARNING: No title — using: {title}")

        num_seasons_str = self.gui.ask_input(
            "Seasons", "How many seasons are you ripping?"
        )
        num_seasons = int(num_seasons_str) if (
            num_seasons_str and num_seasons_str.isdigit()
        ) else 1

        eps_per_season = {}
        for s in range(1, num_seasons + 1):
            eps_str = self.gui.ask_input(
                f"Season {s:02d} Episodes",
                f"How many episodes in Season {s:02d}?"
            )
            eps_per_season[s] = int(eps_str) if (
                eps_str and eps_str.isdigit()
            ) else 0

        self.log(f"Series: {title}")
        self.log(f"Seasons: {num_seasons}")
        for s, eps in eps_per_season.items():
            self.log(f"  Season {s:02d}: {eps} episodes")

        series_root = os.path.join(temp_root, clean_name(title))
        os.makedirs(series_root, exist_ok=True)

        disc_number       = 0
        current_season    = 1
        seen_fingerprints = set()
        stop_requested    = False

        while current_season <= num_seasons:
            if self.engine.abort_event.is_set():
                self.log("Session aborted.")
                break

            season_folder = os.path.join(
                series_root, f"Season {current_season:02d}"
            )
            os.makedirs(season_folder, exist_ok=True)
            self.log(f"--- Season {current_season:02d} ---")

            season_done = False
            while not season_done:
                if self.engine.abort_event.is_set():
                    break

                next_disc_number = disc_number + 1
                self.log(f"--- Disc {next_disc_number} ---")

                self.gui.show_info(
                    "Insert Disc",
                    f"Insert disc {next_disc_number} "
                    f"(Season {current_season:02d}) and click OK."
                )
                time.sleep(2)  # drive spin-up / mount stabilization

                fingerprint = self._build_disc_fingerprint()
                if not fingerprint:
                    self.report(
                        f"{title} S{current_season:02d} "
                        f"Disc {next_disc_number}: could not read disc "
                        f"fingerprint."
                    )
                    action = self.gui.ask_duplicate_resolution(
                        f"{title} — Season {current_season:02d}, "
                        f"Disc {next_disc_number}: could not verify this "
                        "disc fingerprint.",
                        "Retry Disc",
                        "Proceed Anyway",
                        "Stop"
                    )
                    if action == "retry":
                        continue
                    if action == "stop":
                        stop_requested = True
                        break
                    self.log(
                        "Fingerprint check bypassed manually; proceeding."
                    )
                elif fingerprint in seen_fingerprints:
                    duplicate_action = self.gui.ask_duplicate_resolution(
                        f"{title} — Season {current_season:02d}, "
                        f"Disc {next_disc_number}: this disc looks like a "
                        "duplicate from earlier in this session.",
                        "Swap and Retry",
                        "Not a Dup",
                        "Stop"
                    )
                    if duplicate_action == "retry":
                        continue
                    if duplicate_action == "stop":
                        self.report(
                            f"{title} S{current_season:02d} "
                            f"Disc {next_disc_number}: duplicate not accepted."
                        )
                        stop_requested = True
                        break
                    self.log(
                        "Manual duplicate bypass selected; proceeding "
                        "with this disc."
                    )
                else:
                    seen_fingerprints.add(fingerprint)

                disc_number = next_disc_number

                rip_path = os.path.join(
                    season_folder, make_rip_folder_name()
                )
                os.makedirs(rip_path, exist_ok=True)
                self.engine.write_temp_metadata(
                    rip_path, title, disc_number,
                    season=current_season
                )

                if cfg.get("opt_scan_disc_size", True):
                    self.gui.set_status("Scanning disc size...")
                    self.gui.start_indeterminate()
                    try:
                        disc_size = self.engine.get_disc_size(
                            self.log
                        )
                    finally:
                        self.gui.stop_indeterminate()
                        self.gui.set_progress(0)

                    if self.engine.abort_event.is_set():
                        break

                    if disc_size:
                        status, free, required = (
                            self.engine.check_disk_space(
                                temp_root, disc_size, self.log
                            )
                        )
                        if status == "block":
                            self.gui.show_error(
                                "Critically Low Space",
                                f"Only {free/(1024**3):.1f} GB "
                                f"free.\nMinimum: "
                                f"{cfg.get('opt_hard_block_gb',20)}"
                                f" GB."
                            )
                            break
                        elif (status == "warn" and
                              cfg.get("opt_warn_low_space", True)):
                            if not self.gui.ask_space_override(
                                required / (1024**3),
                                free / (1024**3)
                            ):
                                break

                self.gui.set_status("Ripping... (this may take 20-60 min)")
                success = self.engine.rip_all_titles(
                    rip_path,
                    on_progress=self.gui.set_progress,
                    on_log=self.log
                )
                success, mkv_files = self._normalize_rip_result(
                    rip_path, success, []
                )

                if not success:
                    if self.engine.abort_event.is_set():
                        break
                    self.report(
                        f"{title} S{current_season:02d} "
                        f"Disc {disc_number}: rip failed."
                    )
                    if not self.gui.ask_yesno(
                        f"Disc {disc_number} failed. "
                        f"Try another disc?"
                    ):
                        season_done = True
                    continue

                self.engine.update_temp_metadata(
                    rip_path, status="ripped"
                )
                self.log(
                    f"Disc {disc_number} done. "
                    f"{len(mkv_files)} file(s) ripped."
                )
                self._log_ripped_file_sizes(mkv_files)
                stabilized, timed_out = self._stabilize_ripped_files(
                    mkv_files
                )
                if not stabilized:
                    self.log("File stabilization check failed after rip.")
                    self.report(
                        f"{title} S{current_season:02d} Disc {disc_number}: "
                        "failed stabilization check"
                    )
                    self.gui.show_error(
                        "Rip Failed",
                        (
                            f"Disc {disc_number} did not stabilize in time.\n\n"
                            if timed_out else
                            f"Disc {disc_number} failed stabilization checks.\n\n"
                        ) +
                        "Stopping unattended series to prevent partial files."
                    )
                    stop_requested = True
                    break
                if not self._verify_container_integrity(mkv_files):
                    self.report(
                        f"{title} S{current_season:02d} Disc {disc_number}: "
                        "failed ffprobe integrity check"
                    )
                    self.gui.show_error(
                        "Rip Failed",
                        "Container integrity check failed (ffprobe).\n\n"
                        "Stopping unattended series to prevent corrupt files."
                    )
                    stop_requested = True
                    break
                self.gui.set_progress(0)

                if not self.gui.ask_yesno(
                    f"Season {current_season:02d} — "
                    f"another disc for this season?"
                ):
                    season_done = True

            if stop_requested:
                self.log("Unattended series stopped by user decision.")
                break

            current_season += 1

        self.write_session_summary()
        self.flush_log()
        self.gui.set_status("Ready")
        self.gui.set_progress(0)
        if self.engine.abort_event.is_set() or stop_requested:
            self.gui.show_info(
                "Series Stopped",
                "Unattended series mode was stopped before completion."
            )
            return
        self.gui.show_info(
            "Series Complete",
            f"All discs ripped to:\n{series_root}\n\n"
            f"Use 'Organize Existing MKVs' to sort into your library."
        )

    def run_organize(self):
        cfg = self.engine.cfg

        folder_path = self.gui.ask_folder(
            "Select folder with raw .mkv files"
        )
        if not folder_path:
            self.log("Cancelled.")
            return

        recursive = self.gui.ask_yesno("Scan subfolders too?")
        if recursive:
            mkv_files = sorted(glob.glob(
                os.path.join(folder_path, "**", "*.mkv"),
                recursive=True
            ))
        else:
            mkv_files = sorted(
                glob.glob(os.path.join(folder_path, "*.mkv"))
            )

        if not mkv_files:
            self.log("No .mkv files found.")
            return

        self.log(f"Found {len(mkv_files)} files in: {folder_path}")

        media_type = self.gui.ask_input(
            "Media Type", "TV or Movie? Enter t or m:"
        )
        if not media_type:
            self.log("Cancelled.")
            return
        is_tv = media_type.strip().lower() == "t"

        path_fields = [
            ("tv_folder", "TV Folder"),
            ("temp_folder", "Temp Folder"),
        ] if is_tv else [
            ("movies_folder", "Movies Folder"),
            ("temp_folder", "Temp Folder"),
        ]
        path_overrides = self._prompt_run_path_overrides(path_fields)
        if path_overrides is None:
            self.log("Cancelled before organize (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._ensure_session_paths()
        self._log_session_paths()
        # Always derive all folder roots from session_paths — never from cfg
        # directly — so run-time path overrides are always honored.
        tv_root    = self.get_path("tv")
        movie_root = self.get_path("movies")
        temp_root  = self.get_path("temp")

        title = self.gui.ask_input("Title", "Exact title:")
        if not title:
            title = self._fallback_title_from_mode()
            self.log(f"WARNING: No title — using: {title}")
        self.log(f"Title: {title}")

        if is_tv:
            season_str = self.gui.ask_input(
                "Season", "Season number:"
            )
            season = int(season_str) if (
                season_str and season_str.isdigit()
            ) else 0
            if season == 0:
                self.log("WARNING: No season number — using 00")
            season_folder = os.path.join(
                tv_root, clean_name(title), f"Season {season:02d}"
            )
            extras_folder = os.path.join(season_folder, "Extras")
            os.makedirs(season_folder, exist_ok=True)
            os.makedirs(extras_folder, exist_ok=True)
            dest_folder = season_folder
            self.log(f"Season folder: {season_folder}")
        else:
            year = self.gui.ask_input("Year", "Release year:")
            if not year:
                year = "0000"
                self.log("WARNING: No year — using 0000")
            movie_folder = os.path.join(
                movie_root, f"{clean_name(title)} ({year})"
            )
            extras_folder = os.path.join(movie_folder, "Extras")
            os.makedirs(movie_folder, exist_ok=True)
            os.makedirs(extras_folder, exist_ok=True)
            dest_folder = movie_folder
            self.log(f"Movie folder: {movie_folder}")

        self.gui.set_status("Analyzing files...")
        self.gui.start_indeterminate()
        try:
            titles_list = self.engine.analyze_files(
                mkv_files, self.log
            )
        finally:
            self.gui.stop_indeterminate()
            self.gui.set_progress(0)

        if not titles_list:
            self.log("No files to process.")
            return

        move_ok = self._select_and_move(
            titles_list, is_tv, title, dest_folder, extras_folder,
            season if is_tv else None,
            year if not is_tv else None
        )

        if move_ok:
            norm_folder = os.path.normpath(folder_path)
            if (cfg.get("opt_auto_delete_temp", True) and
                    norm_folder.startswith(temp_root)):
                try:
                    shutil.rmtree(norm_folder)
                    self.log(
                        f"Auto-deleted temp folder: "
                        f"{os.path.basename(folder_path)}"
                    )
                except Exception as e:
                    self.log(
                        f"Warning: could not delete temp: {e}"
                    )
        elif self.engine.abort_event.is_set():
            self.log(
                "Move stopped before completion — "
                "some files may not have moved."
            )

        self.write_session_summary()
        self.flush_log()
        self.gui.show_info("Done", "Organize complete!")

    def _offer_temp_manager(self, temp_root):
        old_folders = self.engine.find_old_temp_folders(temp_root)
        if not old_folders:
            return
        self.gui.show_temp_manager(
            old_folders, self.engine, self.log
        )

    def _run_disc(self, is_tv):
        cfg        = self.engine.cfg
        path_fields = [
            ("tv_folder", "TV Folder"),
            ("temp_folder", "Temp Folder"),
        ] if is_tv else [
            ("movies_folder", "Movies Folder"),
            ("temp_folder", "Temp Folder"),
        ]
        path_overrides = self._prompt_run_path_overrides(path_fields)
        if path_overrides is None:
            self.log("Cancelled before disc rip (path override step).")
            return
        self._init_session_paths(path_overrides)
        self._log_session_paths()
        tv_root = self.get_path("tv")
        movie_root = self.get_path("movies")
        temp_root = self.get_path("temp")

        self.engine.reset_abort()
        self._wiped_session_paths.clear()
        self.global_extra_counter = 1
        self.session_report       = []
        disc_number = 0
        season      = 0
        year        = "0000"

        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            return

        resume_session = self.check_resume(
            temp_root, media_type="tv" if is_tv else "movie"
        )
        resume_meta = resume_session["meta"] if resume_session else {}
        resume_path = resume_session["path"] if resume_session else None
        if resume_meta:
            disc_number = max(
                0,
                self._parse_int_or_default(
                    resume_meta.get("disc_number", 1), 1
                ) - 1
            )
            year = str(resume_meta.get("year") or year)

        if is_tv:
            title = self.gui.ask_input(
                "Title", "Exact TV show title:",
                default_value=resume_meta.get("title", "")
            )
            if not title:
                title = self._fallback_title_from_mode()
                self.log(f"WARNING: No title — using: {title}")
            self.log(f"Title: {title}")
            if resume_path:
                series_root = os.path.dirname(
                    os.path.dirname(resume_path)
                )
            else:
                series_root = os.path.join(temp_root, clean_name(title))
            os.makedirs(series_root, exist_ok=True)

        while True:
            if self.engine.abort_event.is_set():
                self.log("Session aborted.")
                break

            disc_number += 1
            self.log(f"--- Disc {disc_number} ---")

            self.gui.show_info(
                "Insert Disc",
                f"Insert disc {disc_number} "
                f"and click OK when ready."
            )

            active_resume = None
            if resume_meta and self._parse_int_or_default(
                resume_meta.get("disc_number", 0), 0
            ) == disc_number:
                active_resume = resume_meta

            auto_title_pending = False

            if is_tv:
                season_str = self.gui.ask_input(
                    "Season",
                    f"Season number for disc {disc_number}:",
                    default_value=str(
                        active_resume.get("season", "")
                        if active_resume else ""
                    )
                )
                season = int(season_str) if (
                    season_str and season_str.isdigit()
                ) else 0
                if season == 0:
                    self.log("WARNING: No season number — using 00")

                season_temp = os.path.join(
                    series_root, f"Season {season:02d}"
                )
                os.makedirs(season_temp, exist_ok=True)

                season_folder = os.path.join(
                    tv_root, clean_name(title),
                    f"Season {season:02d}"
                )
                extras_folder = os.path.join(season_folder, "Extras")
                os.makedirs(season_folder, exist_ok=True)
                os.makedirs(extras_folder, exist_ok=True)
                dest_folder = season_folder
                self.log(f"Season folder: {season_folder}")
                rip_path = os.path.join(
                    season_temp, make_rip_folder_name()
                )

            else:
                title = self.gui.ask_input(
                    "Title", f"Title for disc {disc_number}:",
                    default_value=(active_resume or {}).get("title", "")
                )
                if not title:
                    auto_title_pending = True
                    title = make_temp_title()
                    self.log(
                        "WARNING: No title entered — using fallback naming "
                        "mode after scan when possible."
                    )
                year = self.gui.ask_input(
                    "Year", "Release year:",
                    default_value=str(
                        (active_resume or {}).get("year", year)
                    )
                )
                if not year:
                    year = "0000"
                    self.log("WARNING: No year — using 0000")
                movie_folder = os.path.join(
                    movie_root, f"{clean_name(title)} ({year})"
                )
                extras_folder = os.path.join(movie_folder, "Extras")
                os.makedirs(movie_folder, exist_ok=True)
                os.makedirs(extras_folder, exist_ok=True)
                dest_folder = movie_folder
                self.log(f"Movie folder: {movie_folder}")
                if active_resume and resume_path:
                    rip_path = resume_path
                else:
                    rip_path = os.path.join(
                        temp_root, make_rip_folder_name()
                    )

            os.makedirs(rip_path, exist_ok=True)
            if active_resume and resume_path:
                self.engine.update_temp_metadata(
                    rip_path,
                    status="ripping",
                    title=title,
                    year=year if not is_tv else None,
                    media_type="tv" if is_tv else "movie",
                    season=season if is_tv else None,
                    dest_folder=dest_folder,
                    phase="setup",
                    disc_number=disc_number,
                )
            else:
                self.engine.write_temp_metadata(
                    rip_path, title, disc_number,
                    season=season if is_tv else None,
                    year=year if not is_tv else None,
                    media_type="tv" if is_tv else "movie",
                    dest_folder=dest_folder,
                    phase="setup"
                )
            self.log(f"Temp folder: {rip_path}")

            if self.engine.abort_event.is_set():
                break

            time.sleep(2)  # drive spin-up / mount stabilization
            disc_titles = self.scan_with_retry()

            if self.engine.abort_event.is_set():
                break

            if disc_titles is None:
                self.log("Could not read disc.")
                self.report(
                    f"Disc {disc_number}: could not read disc."
                )
                self.gui.show_error(
                    "Scan Failed",
                    "Disc scan failed after retry.\n\n"
                    "Try cleaning the disc and retrying."
                )
                if not self.gui.ask_yesno("Retry?"):
                    break
                continue
            if disc_titles == []:
                self.log("Disc readable but no titles found.")
                self.report(
                    f"Disc {disc_number}: readable disc with no titles."
                )
                self.gui.show_error(
                    "No Titles Found",
                    "Disc was readable, but no rip-able titles were found.\n\n"
                    "Try another disc."
                )
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            if (not is_tv) and auto_title_pending:
                auto_title = self._fallback_title_from_mode(disc_titles)
                if auto_title and auto_title != title:
                    title = auto_title
                    movie_folder = os.path.join(
                        movie_root, f"{clean_name(title)} ({year})"
                    )
                    extras_folder = os.path.join(movie_folder, "Extras")
                    os.makedirs(movie_folder, exist_ok=True)
                    os.makedirs(extras_folder, exist_ok=True)
                    dest_folder = movie_folder
                    self.log(f"Auto title used: {title}")
                    self.log(f"Movie folder: {movie_folder}")
                    self.engine.update_temp_metadata(
                        rip_path,
                        title=title,
                        year=year,
                        dest_folder=dest_folder,
                    )

            restored_selected_ids = (
                self._restore_selected_titles(disc_titles, active_resume)
                if active_resume else None
            )

            if restored_selected_ids:
                selected_ids = restored_selected_ids
                selected_size = sum(
                    t["size_bytes"] for t in disc_titles
                    if t["id"] in selected_ids
                )
                self.log(
                    "Restored selected titles from session metadata: "
                    + ", ".join(str(tid + 1) for tid in selected_ids)
                )

            # Select best by score, not incoming list position.
            if not restored_selected_ids and cfg.get("opt_smart_rip_mode", False):
                selected_ids = None
                selected_size = 0
                best, smart_score = choose_best_title(
                    disc_titles, require_valid=True
                )
                if not best:
                    self.log("Could not select a valid Smart Rip title.")
                    if not self.gui.ask_yesno("Try again?"):
                        break
                    continue
                low_conf = float(cfg.get("opt_smart_low_confidence_threshold", 0.45))
                if smart_score < low_conf:
                    self.log(
                        f"WARNING: Low-confidence Smart Rip selection "
                        f"(score={smart_score:.3f} < {low_conf:.2f})."
                    )
                    if not self.gui.ask_yesno(
                        f"Smart Rip confidence is low ({smart_score:.3f}).\n\n"
                        "Disc structure may be ambiguous or damaged.\n"
                        "Use this auto-selected title?"
                    ):
                        if self.gui.ask_yesno(
                            "Open manual title picker with Preview buttons?"
                        ):
                            selected_ids = self.gui.show_disc_tree(
                                disc_titles, is_tv, self.preview_title
                            )
                            if selected_ids is None:
                                self.log("Cancelled.")
                                break
                            if not selected_ids:
                                self.log("No titles selected.")
                                if not self.gui.ask_yesno("Try again?"):
                                    break
                                continue
                            selected_size = sum(
                                t["size_bytes"] for t in disc_titles
                                if t["id"] in selected_ids
                            )
                            self.log(
                                "Ambiguous Smart Rip: switched to manual "
                                "selection with preview."
                            )
                        else:
                            if not self.gui.ask_yesno("Try again?"):
                                break
                            continue
                    else:
                        selected_ids  = [best["id"]]
                        selected_size = best.get("size_bytes", 0)
                        self.log(
                            f"Smart Rip: auto-selected Title "
                            f"{best['id']+1} "
                            f"(score={smart_score:.3f}) "
                            f"{best['duration']} {best['size']}"
                        )
                else:
                    selected_ids  = [best["id"]]
                    selected_size = best.get("size_bytes", 0)
                    self.log(
                        f"Smart Rip: auto-selected Title "
                        f"{best['id']+1} "
                        f"(score={smart_score:.3f}) "
                        f"{best['duration']} {best['size']}"
                    )
            elif not restored_selected_ids:
                selected_ids = self.gui.show_disc_tree(
                    disc_titles, is_tv, self.preview_title
                )
                if selected_ids is None:
                    self.log("Cancelled.")
                    break
                if not selected_ids:
                    self.log("No titles selected.")
                    if not self.gui.ask_yesno("Try again?"):
                        break
                    continue
                selected_size = sum(
                    t["size_bytes"] for t in disc_titles
                    if t["id"] in selected_ids
                )

            expected_size_by_title = {
                int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
                for t in disc_titles
                if int(t.get("id", -1)) in selected_ids
            }
            self.engine.update_temp_metadata(
                rip_path,
                status="ripping",
                title=title,
                year=year if not is_tv else None,
                media_type="tv" if is_tv else "movie",
                season=season if is_tv else None,
                selected_titles=list(selected_ids),
                dest_folder=dest_folder,
                phase="ripping",
                completed_titles=[],
            )

            if cfg.get("opt_confirm_before_rip", True):
                if not self.gui.ask_yesno(
                    f"Rip {len(selected_ids)} title(s) — "
                    f"~{selected_size / (1024**3):.1f} GB. Continue?"
                ):
                    self.log("Rip cancelled by user.")
                    if not self.gui.ask_yesno("Try again?"):
                        break
                    continue

            self.log(
                f"Selected {len(selected_ids)} title(s) — "
                f"~{selected_size / (1024**3):.1f} GB"
            )

            if (selected_size > 0 and
                    cfg.get("opt_scan_disc_size", True)):
                status, free, required = self.engine.check_disk_space(
                    temp_root, selected_size, self.log
                )
                if status == "block":
                    self.gui.show_error(
                        "Critically Low Space",
                        f"Only {free / (1024**3):.1f} GB free.\n"
                        f"Minimum: "
                        f"{cfg.get('opt_hard_block_gb', 20)} GB."
                    )
                    break
                elif (status == "warn" and
                      cfg.get("opt_warn_low_space", True)):
                    if not self.gui.ask_space_override(
                        required / (1024**3), free / (1024**3)
                    ):
                        self.log("Cancelled: not enough space.")
                        break

            self.gui.set_status("Ripping... (this may take 20-60 min)")
            success, failed_titles = self.engine.rip_selected_titles(
                rip_path, selected_ids,
                on_progress=self.gui.set_progress,
                on_log=self.log
            )
            self._warn_degraded_rips()

            if failed_titles:
                self.report(
                    f"Disc {disc_number}: titles failed — "
                    f"{failed_titles}"
                )

            success, mkv_files = self._normalize_rip_result(
                rip_path, success, failed_titles
            )

            if not success:
                self._mark_session_failed(
                    rip_path,
                    title=title,
                    year=year if not is_tv else None,
                    media_type="tv" if is_tv else "movie",
                    season=season if is_tv else None,
                    selected_titles=list(selected_ids),
                    dest_folder=dest_folder,
                    failed_titles=list(failed_titles),
                )
                if self.engine.abort_event.is_set():
                    break
                self.log("Rip did not complete.")
                self.flush_log()
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            self.engine.update_temp_metadata(
                rip_path, status="ripped", phase="analyzing"
            )
            self.log("Ripping complete.")
            self.gui.set_progress(0)
            time.sleep(2)

            self.log(f"Found {len(mkv_files)} file(s).")
            self._log_ripped_file_sizes(mkv_files)
            stabilized, timed_out = self._stabilize_ripped_files(
                mkv_files, expected_size_by_title
            )
            if not stabilized:
                self.log("File stabilization check failed after rip.")
                self.report(
                    f"Disc {disc_number}: failed stabilization check"
                )
                self._mark_session_failed(
                    rip_path,
                    title=title,
                    year=year if not is_tv else None,
                    media_type="tv" if is_tv else "movie",
                    season=season if is_tv else None,
                    selected_titles=list(selected_ids),
                    dest_folder=dest_folder,
                )
                self.gui.show_error(
                    "Rip Failed",
                    (
                        "Ripped file(s) did not stabilize in time.\n\n"
                        if timed_out else
                        "Ripped file(s) failed stabilization checks.\n\n"
                    ) +
                    "Move is blocked to prevent partial file corruption."
                )
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue
            self._log_expected_vs_actual_summary(
                mkv_files, expected_size_by_title
            )
            size_status, size_reason = self._verify_expected_sizes(
                mkv_files, expected_size_by_title
            )
            if size_status == "hard_fail":
                self.log("ERROR: Size sanity check failed after rip.")
                retried_ok = self._retry_rip_once_after_size_failure(
                    rip_path, selected_ids, expected_size_by_title
                )
                if not retried_ok:
                    self.report(
                        f"Disc {disc_number}: failed size sanity check"
                    )
                    self._mark_session_failed(
                        rip_path,
                        title=title,
                        year=year if not is_tv else None,
                        media_type="tv" if is_tv else "movie",
                        season=season if is_tv else None,
                        selected_titles=list(selected_ids),
                        dest_folder=dest_folder,
                    )
                    self.gui.show_error(
                        "Rip Failed",
                        "Rip incomplete — file too small.\n\n"
                        "Automatic retry was attempted once and still failed."
                    )
                    if not self.gui.ask_yesno("Try another disc?"):
                        break
                    continue
            elif size_status == "warn":
                if not self.gui.ask_yesno(
                    "Rip size is below preferred threshold.\n\n"
                    f"{size_reason}\n\n"
                    "Continue anyway?"
                ):
                    if not self.gui.ask_yesno("Try another disc?"):
                        break
                    continue
                self.report(
                    f"USER OVERRIDE — Disc {disc_number} size warning"
                )

            # Analyze files once; reuse for both integrity check and move step.
            self.gui.set_status("Analyzing files...")
            self.gui.start_indeterminate()
            try:
                titles_list = self.engine.analyze_files(
                    mkv_files, self.log
                )
                self.log(f"Analysis completed: {len(titles_list)} title(s) found.")
            except Exception as e:
                self.log(f"ERROR during analysis: {e}")
                titles_list = None
            finally:
                self.gui.stop_indeterminate()
                self.gui.set_progress(0)

            if not titles_list:
                self.log("Analysis aborted or no files returned.")
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            # Integrity check uses pre-analyzed data — no extra ffprobe pass.
            if not self._verify_container_integrity(
                mkv_files, analyzed=titles_list
            ):
                self.report(
                    f"Disc {disc_number}: ffprobe integrity check failed"
                )
                self._mark_session_failed(
                    rip_path,
                    title=title,
                    year=year if not is_tv else None,
                    media_type="tv" if is_tv else "movie",
                    season=season if is_tv else None,
                    selected_titles=list(selected_ids),
                    dest_folder=dest_folder,
                )
                self.gui.show_error(
                    "Rip Failed",
                    "Container integrity check failed (ffprobe).\n\n"
                    "Try another disc."
                )
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            move_ok = self._select_and_move(
                titles_list, is_tv, title, dest_folder, extras_folder,
                season if is_tv else None,
                year if not is_tv else None,
                expected_size_by_title=expected_size_by_title,
                session_rip_path=rip_path,
                session_meta=active_resume,
                selected_title_ids=selected_ids,
            )

            if move_ok:
                shutil.rmtree(rip_path, ignore_errors=True)
                if os.path.exists(rip_path):
                    self.log(f"Warning: could not delete {rip_path}")
                self.log("Temp folder cleaned up.")
                if cfg.get("opt_show_temp_manager", True):
                    self._offer_temp_manager(temp_root)
            else:
                if self.engine.abort_event.is_set():
                    self.log(
                        "Move stopped before completion — "
                        "some files may not have moved."
                    )
                self.log(f"Temp folder preserved at: {rip_path}")

            self.flush_log()

            if not self.gui.ask_yesno("Another disc in this set?"):
                break

        self.write_session_summary()
        self.gui.set_status("Ready")
        self.gui.set_progress(0)
        self.gui.show_info("Done", "Session complete!")

    def _select_and_move(self, titles_list, is_tv, title,
                         dest_folder, extras_folder, season, year,
                         expected_size_by_title=None, session_rip_path=None,
                         session_meta=None, selected_title_ids=None):
        options = []
        for i, (f, dur, mb) in enumerate(titles_list, 1):
            mins = int(dur // 60) if dur > 0 else "?"
            options.append(
                f"{i}: {os.path.basename(f)}  ~{mins} min  {mb} MB"
            )

        restored_main_indices = self._map_title_ids_to_analyzed_indices(
            titles_list, selected_title_ids
        )

        self.log("Files (longest first, unknowns at end):")
        for opt in options:
            self.log(f"  {opt}")

        if is_tv:
            if restored_main_indices:
                main_indices = restored_main_indices
                self.log(
                    "Restored episode file selection from session metadata."
                )
            else:
                selected = self.gui.show_file_list(
                    "Select Main Episodes",
                    "Select MAIN EPISODE files:",
                    options
                )
                if not selected:
                    self.log("Cancelled.")
                    return False

                main_indices = [
                    int(s.split(":")[0]) - 1 for s in selected
                ]

            default_episode_numbers = []
            if session_meta:
                default_episode_numbers = session_meta.get(
                    "episode_numbers", []
                ) or []
            default_episode_input = ", ".join(
                str(x) for x in default_episode_numbers
            )

            while True:
                ep_input = self.gui.ask_input(
                    "Episode Numbers",
                    f"Enter {len(main_indices)} episode number(s), "
                    f"comma separated:",
                    default_value=default_episode_input
                )
                if not ep_input:
                    self.log("Cancelled.")
                    return False

                episode_numbers = [
                    int(x.strip()) for x in ep_input.split(",")
                    if x.strip().isdigit()
                ]

                if len(episode_numbers) != len(main_indices):
                    self.log(
                        f"Need {len(main_indices)} numbers, "
                        f"got {len(episode_numbers)}. "
                        f"Please re-enter."
                    )
                    continue

                if len(set(episode_numbers)) != len(episode_numbers):
                    self.log(
                        "Duplicate episode numbers. Please re-enter."
                    )
                    continue

                if episode_numbers != sorted(episode_numbers):
                    if self.engine.cfg.get(
                        "opt_warn_out_of_order_episodes", True
                    ):
                        if not self.gui.ask_yesno(
                            f"Episode numbers not in order: "
                            f"{episode_numbers} — continue anyway?"
                        ):
                            continue

                break

            name_input = self.gui.ask_input(
                "Episode Names",
                "Paste episode names comma separated "
                "(or leave blank for defaults):",
                default_value=", ".join(
                    session_meta.get("episode_names", [])
                ) if session_meta else ""
            )
            real_names  = parse_episode_names(name_input)
            keep_extras = self.gui.ask_yesno("Keep extras?")

            if session_rip_path:
                self.engine.update_temp_metadata(
                    session_rip_path,
                    season=season,
                    episode_names=list(real_names),
                    episode_numbers=list(episode_numbers),
                    phase="moving",
                )

            preview_lines = [
                f"  {os.path.basename(titles_list[i][0])}  ->  "
                f"S{season:02d}E{episode_numbers[idx]:02d}"
                for idx, i in enumerate(main_indices)
            ]
            self.log("Move preview:")
            for line in preview_lines:
                self.log(line)

            if self.engine.cfg.get("opt_confirm_before_move", True):
                if not self.gui.ask_yesno(
                    "Confirm — move these files?"
                ):
                    self.log("Cancelled by user.")
                    return False

        else:
            if restored_main_indices:
                main_indices = [restored_main_indices[0]]
                self.log(
                    "Restored main movie selection from session metadata."
                )
            else:
                selected = self.gui.show_file_list(
                    "Select Main Movie",
                    "Select the MAIN MOVIE file:",
                    options
                )
                if not selected:
                    self.log("Cancelled.")
                    return False

                main_indices = [int(selected[0].split(":")[0]) - 1]
            keep_extras     = self.gui.ask_yesno("Keep extras?")
            episode_numbers = []
            real_names      = []

            if session_rip_path:
                self.engine.update_temp_metadata(
                    session_rip_path,
                    phase="moving",
                )

            self.log(
                f"Main movie: "
                f"{os.path.basename(titles_list[main_indices[0]][0])}"
            )

            if self.engine.cfg.get("opt_confirm_before_move", True):
                if not self.gui.ask_yesno(
                    "Confirm — move this file?"
                ):
                    self.log("Cancelled by user.")
                    return False

        self.gui.set_status("Moving files...")
        success, self.global_extra_counter, moved_paths = self.engine.move_files(
            titles_list, main_indices, episode_numbers,
            real_names, keep_extras, is_tv, title,
            dest_folder, extras_folder, season, year,
            self.global_extra_counter,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        if success and moved_paths and expected_size_by_title:
            post_status, post_reason = self._verify_expected_sizes(
                moved_paths, expected_size_by_title
            )
            if post_status == "hard_fail":
                self.report("Post-move size validation hard failure")
                self.gui.show_error(
                    "Post-Move Validation Failed",
                    post_reason
                )
                success = False
            elif post_status == "warn":
                self.report("USER OVERRIDE — post-move size warning")
        if success and moved_paths and (not self._verify_container_integrity(moved_paths)):
            self.report("Post-move ffprobe integrity check failed")
            self.gui.show_error(
                "Post-Move Validation Failed",
                "Moved file(s) failed container integrity check (ffprobe)."
            )
            success = False
        if not success:
            reason = self.engine.last_move_error.strip()
            self.report("Move failed")
            if reason:
                self.gui.show_error("Move Failed", reason)
        elif session_rip_path:
            self.engine.update_temp_metadata(
                session_rip_path,
                status="organized",
                phase="complete",
                completed_titles=list(selected_title_ids or []),
                episode_names=list(real_names),
                episode_numbers=list(episode_numbers),
            )
        return success


# ==========================================
# LAYER 3 — GUI
# ==========================================


__all__ = ["RipperController"]
