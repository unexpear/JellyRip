
"""Controller layer implementation."""
# pyright: reportUnusedImport=false, reportUnusedVariable=false
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from config import AppConfig
from controller.legacy_compat import LegacyControllerMixin
from controller.naming import build_fallback_title as _build_fallback_title
from controller.naming import build_movie_folder_name, build_tv_folder_name, parse_metadata_id
from controller.session import SessionHelpers
from shared.event import Event
from utils.fallback import handle_fallback
from utils.helpers import clean_name, make_rip_folder_name, make_temp_title
from utils.parsing import parse_episode_names, parse_ordered_titles, safe_int
from utils.scoring import choose_best_title
from utils.state_machine import SessionState, SessionStateMachine


DiscTitle = dict[str, Any]
DiscTitles = list[DiscTitle]
AnalyzedFile = tuple[str, float, float]
AnalyzedFiles = list[AnalyzedFile]
ExpectedSizeMap = dict[int, int]
build_fallback_title = _build_fallback_title


def _normalize_title_file_map(raw_value: Any) -> dict[int, list[str]]:
    normalized: dict[int, list[str]] = {}
    if not isinstance(raw_value, Mapping):
        return normalized
    raw_map = cast(Mapping[object, object], raw_value)
    for raw_tid, raw_files in raw_map.items():
        if not isinstance(raw_tid, (int, str)):
            continue
        if not isinstance(raw_files, Sequence) or isinstance(raw_files, (str, bytes)):
            continue
        file_list = [str(path) for path in cast(Sequence[object], raw_files)]
        normalized[int(raw_tid)] = file_list
    return normalized


@dataclass
class Progress:
    percent: float = 0.0
    eta: str = ""
    speed: str = ""


@dataclass
class QueuedJob:
    id: str
    job: Any  # Should be Job, but avoid circular import
    name: str
    config: Optional[AppConfig] = None
    status: str = "pending"
    result: Any = None  # Should be Result
    logs: List[str] = field(default_factory=lambda: [])
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: Progress = field(default_factory=Progress)


class JobQueue:
    def __init__(self) -> None:
        self.jobs: List[QueuedJob] = []
        self.running: bool = False

    def add_job(self, job: Any, config: Optional[AppConfig] = None) -> str:
        name: str = getattr(job, "source", None) or "Job"
        qjob = QueuedJob(
            id=str(uuid.uuid4()),
            job=job,
            name=name,
            config=config,
            logs=[]
        )
        self.jobs.append(qjob)
        return qjob.id

    def start(self, controller: "RipperController") -> None:
        if self.running:
            return
        self.running = True
        threading.Thread(target=lambda: controller.worker(), daemon=True).start()


class RipperController(LegacyControllerMixin):
    def __init__(self, engine: Any, ui: Any) -> None:
        self.queue: JobQueue = JobQueue()
        self.engine: Any = engine
        self.ui: Any = ui
        self.gui: Any = ui
        self.session_log: List[str] = []
        self.start_time: datetime = datetime.now()
        self.global_extra_counter: int = 1
        self.session_report: List[str] = []
        self._preview_lock = threading.Lock()
        self._wiped_session_paths: set[str] = set()
        self.session_paths: Optional[Dict[str, str]] = None
        self.session_helpers = SessionHelpers(ui, self)
        self.sm = SessionStateMachine(
            debug=bool(self.engine.cfg.get("opt_debug_state", False)),
            logger=self.log,
        )

    def extract_progress(self, log_line: str) -> Optional[float]:
        match = re.search(r'(\d{1,3}(?:\.\d+)?)\s*%', log_line)
        if match:
            pct = float(match.group(1))
            if 0 <= pct <= 100:
                return pct
        return None

    def run_now(self, job: Any) -> Any:
        """Bypass queue, run a single job immediately."""
        return self.engine.run_job(job)

    def emit(self, event: Event) -> None:
        if not self.ui:
            return
        if hasattr(self.ui, "handle_event"):
            self.ui.handle_event(event)
        # else: do nothing (no fallback to direct UI calls)

    def worker(self) -> None:
        for qjob in self.queue.jobs:
            if qjob.status != "pending":
                continue
            qjob.status = "running"
            qjob.started_at = datetime.now()
            self.emit(Event("log", qjob.id, {"message": "Running"}))
            try:
                logs: List[str] = []
                last_emit: float = 0.0
                for engine_event in self.engine.run_job_streaming(qjob.job):
                    if engine_event.type == "log":
                        logs.append(str(engine_event.data))
                        percent = self.extract_progress(str(engine_event.data))
                        if percent is not None:
                            qjob.progress.percent = percent
                            now = time.time()
                            if now - last_emit > 0.2:
                                self.emit(Event("progress", qjob.id, {"percent": percent}))
                                last_emit = now
                        self.emit(Event("log", qjob.id, {"message": str(engine_event.data)}))
                    elif engine_event.type == "done":
                        qjob.result = engine_event.data
                        qjob.logs = logs
                        qjob.status = "done" if getattr(engine_event.data, "success", False) else "failed"
                        self.emit(Event("done", qjob.id, {"result": engine_event.data}))
                if not qjob.status or qjob.status == "running":
                    qjob.status = "done"
            except Exception as e:
                qjob.status = "failed"
                self.emit(Event("error", qjob.id, {"error": str(e)}))
            finally:
                qjob.finished_at = datetime.now()
        self.queue.running = False

    def log(self, message: str) -> None:
        self.session_helpers.log(message)
    def _stabilize_file(self, path: str, timeout_seconds: int, min_stable_polls: int) -> tuple[bool, bool]:
        """Wait for file to be stable: N equal reads AND 3+ seconds of no growth.

        Stability = file size stopped changing. Size alone is NOT a stability
        signal — extras and short titles are legitimately small. Size validation
        is a separate post-stabilization concern.
        """
        start = time.time()
        try:
            prev = os.path.getsize(path)
        except Exception as e:
            self.log(
                f"WARNING: Could not read file during stabilization "
                f"({os.path.basename(path)}): {e}"
            )
            return False, False

        stable_polls = 0
        stable_start_time = None  # Track when current stability streak began

        while time.time() - start < timeout_seconds:
            if self.engine.abort_event.is_set():
                return False, False
            time.sleep(1.0)
            try:
                cur = os.path.getsize(path)
            except Exception as e:
                self.log(
                    f"WARNING: File disappeared or became unreadable during "
                    f"stabilization ({os.path.basename(path)}): {e}"
                )
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
                    except Exception as e:
                        self.log(
                            f"WARNING: Could not re-check stabilized file "
                            f"({os.path.basename(path)}): {e}"
                        )
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
        return False, True  # timed out


    # CRITICAL:
    # All size threshold decisions for ripped files MUST go through this
    # function. Do not duplicate or inline this logic elsewhere.
    @staticmethod
    def _compute_file_min_size(expected_bytes: int, floor_bytes: int) -> int:
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

    def _stabilize_ripped_files(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None = None,
    ) -> tuple[bool, bool]:
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
                tid: int | None = self._title_id_from_filename(f)
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

    def run_tv_disc(self) -> None:
        """Run manual TV-disc workflow."""
        self._run_disc(is_tv=True)

    def run_movie_disc(self) -> None:
        """Run manual movie-disc workflow."""
        self._run_disc(is_tv=False)


    def run_smart_rip(self) -> None:
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

        self.log("Flow: Smart Rip session initialized -> collecting disc metadata.")

        self.gui.show_info(
            "Smart Rip",
            "Insert disc and click OK.\n\n"
            "Smart Rip will automatically select the main feature."
        )

        if self.engine.abort_event.is_set():
            return

        title = self.gui.ask_input("Title", "Movie title:")
        if self.engine.abort_event.is_set():
            return
        auto_title_pending = not bool(title)
        if auto_title_pending:
            self.log(
                "WARNING: No title entered — will use fallback naming "
                "mode after scan."
            )

        year = self.gui.ask_input("Year", "Release year:")
        if self.engine.abort_event.is_set():
            return
        if not year:
            year = "0000"
            self.log("WARNING: No year — using 0000")

        metadata_id = self.gui.ask_input(
            "Metadata ID",
            "Optional: TMDB/IMDB/TVDB ID for Jellyfin matching\n"
            "(e.g. tmdb:12345  or  tt1234567  or  tvdb:79168):"
        )
        if self.engine.abort_event.is_set():
            return
        if metadata_id:
            self.log(f"Metadata ID: {parse_metadata_id(metadata_id)}")

        if self.engine.abort_event.is_set():
            return

        time.sleep(2)  # drive spin-up / mount stabilization
        disc_titles: DiscTitles | None = self.scan_with_retry()

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
        best_seconds = safe_int(best.get("duration_seconds", 0))
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

        best_id = safe_int(best.get("id", -1))
        selected_ids: list[int] = [best_id]
        selected_size = safe_int(best.get("size_bytes", 0))
        expected_size_by_title: ExpectedSizeMap = {
            int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
            for t in disc_titles
            if int(t.get("id", -1)) in selected_ids
        }

        self.log(
            f"Smart Rip selected: Title {best_id + 1} "
                f"(score={smart_score:.3f}) "
                f"{best['duration']} {best['size']}"
        )

        if cfg.get("opt_confirm_before_rip", True):
            if not self.gui.ask_yesno(
                f"Smart Rip selected Title {best_id + 1} "
                    f"(score={smart_score:.3f}) "
                    f"{best['duration']} {best['size']} as main feature. "
                    f"Continue?"
            ):
                self.log("Cancelled.")
                return

        if self.gui.ask_yesno("Keep all extras from this disc?"):
            selected_ids = [int(t["id"]) for t in disc_titles]
            selected_size = sum(
                int(t.get("size_bytes", 0) or 0) for t in disc_titles
            )
            expected_size_by_title = {
                int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
                for t in disc_titles
                if int(t.get("id", -1)) in selected_ids
            }
            self.log(
                f"Extras enabled — ripping all {len(selected_ids)} titles."
            )
        else:
            _extra_disc = [
                t for t in disc_titles if t["id"] != best["id"]
            ]
            if _extra_disc:
                _eopts = [
                    f"Title {t['id']+1}:  "
                    f"{t.get('name', '') or 'Untitled'}  "
                    f"({t.get('duration', '')}  {t.get('size', '')})"
                    for t in _extra_disc
                ]
                _chosen = self.gui.show_extras_picker(
                    "Select Extras",
                    "All extras are selected. "
                    "Deselect any you don't want:",
                    _eopts,
                )
                if _chosen:
                    chosen_indices = [int(i) for i in _chosen]
                    _extra_ids: list[int] = [
                        int(_extra_disc[i]["id"]) for i in chosen_indices
                    ]
                    selected_ids = [best_id] + _extra_ids
                    selected_size = sum(
                        int(t.get("size_bytes", 0) or 0) for t in disc_titles
                        if t["id"] in selected_ids
                    )
                    expected_size_by_title = {
                        int(t.get("id", -1)):
                        int(t.get("size_bytes", 0) or 0)
                        for t in disc_titles
                        if int(t.get("id", -1)) in selected_ids
                    }
                    self.log(
                        f"Extras selected — ripping"
                        f" {len(selected_ids)} titles"
                        f" ({len(_extra_ids)} extras)."
                    )

        movie_folder  = os.path.join(
            movie_root,
            build_movie_folder_name(clean_name(title), year, metadata_id),
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
            if len(selected_ids) > 1 else
            "Ripping main feature..."
        )
        self.gui.set_status(status_msg)
        _pre_rip_mkvs = frozenset(
            self._safe_glob(
                os.path.join(rip_path, "**", "*.mkv"),
                recursive=True,
                context="Snapshotting pre-rip MKVs",
            )
        )
        from engine.ripper_engine import Job
        job = Job(
            source=','.join(str(tid) for tid in selected_ids),
            output=rip_path,
            profile="default"
        )
        result = self.engine.run_job(job)
        success = result.success
        failed_titles = result.errors
        self._warn_degraded_rips()
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, failed_titles, _pre_rip_mkvs
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
            titles_list: AnalyzedFiles = self.engine.analyze_files(
                mkv_files, self.log
            ) or []
        finally:
            self.gui.stop_indeterminate()
            self.gui.set_progress(0)

        if not titles_list:
            self._state_fail("analysis_failed")
            return
        assert titles_list is not None

        # Build expected-duration and expected-size maps for integrity warnings.
        # Maps filepath → expected value using disc scan data + rip tracking.
        _dur_by_id = {
            int(t.get("id", -1)): float(t.get("duration_seconds", 0) or 0)
            for t in disc_titles
        }
        _size_by_id = {
            int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
            for t in disc_titles
        }
        _expected_durations: dict[str, float] = {}
        _expected_sizes: dict[str, int] = {}
        title_file_map = _normalize_title_file_map(self.engine.last_title_file_map)
        for tid, files in title_file_map.items():
            exp_dur = _dur_by_id.get(int(tid), 0)
            exp_size = _size_by_id.get(int(tid), 0)
            for fp in files:
                if exp_dur > 0:
                    _expected_durations[str(fp)] = exp_dur
                if exp_size > 0:
                    _expected_sizes[str(fp)] = exp_size

        # Container integrity uses the already-analyzed data — no extra ffprobe.
        if not self._verify_container_integrity(
            mkv_files,
            analyzed=titles_list,
            expected_durations=_expected_durations or None,
            expected_sizes=_expected_sizes or None,
            title_file_map=title_file_map or None,
        ):
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
        if len(selected_ids) > 1:
            mapped = self._map_title_ids_to_analyzed_indices(
                titles_list, [best_id]
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
                    target_size = safe_int(best.get("size_bytes", 0))
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
            extra_indices=None if len(selected_ids) > 1 else [],
            is_tv=False,
            title=title, dest_folder=movie_folder,
            extras_folder=extras_folder,
            season=0, year=year,
            extra_counter=1,
            on_progress=lambda percent: self.emit(Event("progress", "", {"percent": percent})),  # type: ignore[reportUnknownLambdaType]
            on_log=lambda message: self.emit(Event("log", "", {"message": message})),  # type: ignore[reportUnknownLambdaType]
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
            "Dump multiple discs in one session?\n\n"
            "Yes = multi-disc with auto swap detection\n"
            "No = single-disc dump"
        )
        if multi_disc:
            self.log("Multi-disc dump mode: you will be asked for custom disc names and batch folder name.")
            self._run_dump_all_multi(temp_root)
            return

        self.log("Single-disc dump mode: you will be asked for a disc name.")
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

        if self.engine.abort_event.is_set():
            return

        time.sleep(2)  # drive spin-up / mount stabilization

        title = self.gui.ask_input(
            "Disc Name", 
            "Name for this disc (used in folder name).\n"
            "Skip for auto-generated name (timestamp)."
        )
        if not title:
            title = self._fallback_title_from_mode()
            self.log(f"Using auto-generated disc name: {title}")

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
        _pre_rip_mkvs = frozenset(
            self._safe_glob(
                os.path.join(rip_path, "**", "*.mkv"),
                recursive=True,
                context="Snapshotting pre-rip MKVs",
            )
        )
        from engine.ripper_engine import Job
        job = Job(
            source="all",
            output=rip_path,
            profile="default"
        )
        result = self.engine.run_job(job)
        success = result.success
        success, mkv_files = self._normalize_rip_result(
            rip_path, success, [], _pre_rip_mkvs
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

    def _disc_present(self) -> bool:
        """Best-effort check: True when a readable disc appears present."""
        result: list[int | None] = [None]
        cfg = getattr(self.engine, "cfg", {}) or {}
        # 45 s default: slow/encrypted discs can take 20-40 s to spin up and
        # produce the first TINFO line.  12 s was too short and caused every
        # probe to time out, leaving freshly inserted discs "never detected".
        probe_timeout = max(
            5,
            int(cfg.get("opt_disc_presence_probe_seconds", 45))
        )

        def _discard_log(_message: str) -> None:
            return None

        def _probe() -> None:
            try:
                result[0] = self.engine.get_disc_size(
                    _discard_log,
                    prefer_cached=False,
                    timeout_seconds=probe_timeout,
                )
            except Exception:
                result[0] = None

        try:
            t = threading.Thread(target=_probe, daemon=True)
            t.start()
            checks = int((probe_timeout + 1) * 10)
            for _ in range(max(10, checks)):
                if self.engine.abort_event.is_set():
                    return False
                if not t.is_alive():
                    break
                time.sleep(0.1)
            if t.is_alive():
                return False
            return result[0] is not None
        except Exception:
            return False

    def _wait_for_disc_state(
        self,
        want_present: bool,
        timeout_seconds: int | None = 300,
    ) -> bool:
        state_text = "inserted" if want_present else "removed"
        start    = time.time()
        last_log = 0
        self.log(f"Waiting for disc to be {state_text}...")
        while True:
            if self.engine.abort_event.is_set():
                return False
            if self._disc_present() == want_present:
                return True
            elapsed = int(time.time() - start)
            if timeout_seconds is None:
                self.gui.set_status(
                    f"Waiting for disc to be {state_text}..."
                )
            else:
                remaining = int(timeout_seconds - (time.time() - start))
                if remaining <= 0:
                    return False
                self.gui.set_status(
                    f"Waiting for disc to be {state_text} "
                    f"({max(0, remaining)}s)..."
                )
            # Log a heartbeat every ~10 s so the user sees activity.
            if elapsed - last_log >= 10:
                if timeout_seconds is None:
                    self.log(
                        f"Still waiting for disc to be {state_text}..."
                    )
                else:
                    remaining = int(timeout_seconds - (time.time() - start))
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

    def _build_disc_fingerprint(self) -> str | None:
        """Build a disc fingerprint using the standard scan retry path."""
        titles: DiscTitles | None = self.scan_with_retry()
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

    def _resolve_duplicate_dump_disc(
        self,
        disc_number: int,
        total: int,
        per_disc_titles: list[str],
    ) -> str:
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

    def _wait_for_new_unique_disc(
        self,
        seen_fingerprints: set[str],
        disc_number: int,
        total: int,
    ) -> str | None:
        """
        Wait for physical swap and ensure inserted disc is unique in this
        multi-disc batch session.
        """
        if disc_number == 1:
            self.log(
                f"Insert disc {disc_number}/{total} when ready..."
            )
            time.sleep(2)  # drive spin-up / mount stabilization
        else:
            swap_timeout = None
            if self.engine.cfg.get("opt_disc_swap_timeout_enabled", False):
                try:
                    swap_timeout = max(
                        1,
                        int(self.engine.cfg.get(
                            "opt_disc_swap_timeout_seconds", 300
                        ))
                    )
                except Exception:
                    swap_timeout = 300
            self.gui.show_info(
                "Swap Disc",
                f"Disc {disc_number - 1}/{total} completed successfully.\n\n"
                f"Remove it, insert disc {disc_number}/{total}, then click OK."
            )
            self.log(
                "Swap disc now: remove current disc and insert "
                f"disc {disc_number}/{total}."
            )

            # After explicit user acknowledgment, allow pre-swapped insertion
            # to proceed immediately only when a readable disc is already
            # present, avoiding empty-drive scans that add noise and delay.
            if self._disc_present():
                quick_fp = self._build_disc_fingerprint()
                if quick_fp and quick_fp not in seen_fingerprints:
                    seen_fingerprints.add(quick_fp)
                    self.log("Detected new disc already inserted.")
                    return quick_fp

            self.log("Waiting for disc removal...")
            removed = self._wait_for_disc_state(
                want_present=False,
                timeout_seconds=swap_timeout
            )
            if not removed:
                if swap_timeout is None:
                    self.report(f"Disc {disc_number}: stopped while waiting for removal.")
                else:
                    self.report(f"Disc {disc_number}: timed out waiting for removal.")
                return None
            self.log("Disc removal detected.")

            self.log("Waiting for next disc insertion...")
            inserted = self._wait_for_disc_state(
                want_present=True,
                timeout_seconds=swap_timeout
            )
            if not inserted:
                if swap_timeout is None:
                    self.report(f"Disc {disc_number}: stopped while waiting for insertion.")
                else:
                    self.report(f"Disc {disc_number}: timed out waiting for insertion.")
                return None
            self.log("New disc insertion detected.")

        time.sleep(2)  # settle before reading fingerprint
        fingerprint = self._build_disc_fingerprint()
        if not fingerprint:
            self.report(
                f"Disc {disc_number}: could not read disc fingerprint."
            )
            decision = self.gui.ask_duplicate_resolution(
                "Could not verify this disc automatically.\n\n"
                "Choose how to continue:",
                retry_text="Retry Scan",
                bypass_text="Advance Anyway",
                stop_text="Stop",
            )
            if decision == "bypass":
                self.log(
                    "Manual advance selected for unverified disc. "
                    "Proceeding without fingerprint check."
                )
                return "manual-advance"
            if decision == "stop":
                self.report(
                    f"Disc {disc_number}: stopped after unverified disc prompt."
                )
            return None

        if fingerprint in seen_fingerprints:
            self.log(
                "Duplicate disc detected (already dumped in this session)."
            )
            return "duplicate"

        seen_fingerprints.add(fingerprint)
        return fingerprint

    def _collect_dump_all_multi_setup(self) -> tuple[int, list[str], str] | None:
        """Collect multi-disc batch setup with a review/edit loop."""
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
                "Custom Disc Names",
                "Optional: custom names for each disc in order\n"
                "(comma or ' - ' separated).\n"
                "Example: Movie A, Movie B, Movie C\n\n"
                "Skip if you want auto-generated names (timestamp)."
            )
            if per_disc_titles_input is None:
                return None
            per_disc_titles = parse_ordered_titles(per_disc_titles_input)

            batch_title = self.gui.ask_input(
                "Batch Folder Name",
                "Optional: name for the batch folder (contains all discs).\n"
                "Skip for auto-generated name (timestamp)."
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
                "Review multi-disc setup:\n\n"
                f"Disc count: {total}\n"
                f"Batch name: {batch_title}\n"
                f"Custom disc titles: {len(per_disc_titles)}\n"
                f"Preview: {titles_preview}\n\n"
                "Continue with these settings?\n"
                "No = go back and edit"
            ):
                return total, per_disc_titles, batch_title

            self.log("Setup edit requested — re-enter multi-disc settings.")

    def _run_dump_all_multi(self, temp_root: str) -> None:
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
            self.log("Multi-disc dump cancelled during setup.")
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
        self.log(f"Multi-disc dump batch root: {batch_root}")
        self.log(f"Planned discs: {total}")

        seen_fingerprints: set[str] = set()
        disc_number = 1
        verify_failures_for_slot = 0
        while disc_number <= total:
            if self.engine.abort_event.is_set():
                self.log("Multi-disc dump aborted.")
                break

            fingerprint = self._wait_for_new_unique_disc(
                seen_fingerprints, disc_number, total
            )
            if fingerprint is None:
                if self.engine.abort_event.is_set():
                    self.log("Multi-disc dump aborted.")
                    break
                verify_failures_for_slot += 1
                if verify_failures_for_slot < 3:
                    self.log(
                        "Could not verify a new disc for this slot. "
                        f"Retrying automatically ({verify_failures_for_slot}/3)."
                    )
                    continue
                self.report(
                    f"Disc {disc_number}: verification failed after 3 attempts."
                )
                self.log("Cancelled multi-disc dump.")
                break

            verify_failures_for_slot = 0

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

            if fingerprint == "manual-advance":
                self.report(
                    f"Disc {disc_number}: manual advance used without fingerprint verification."
                )

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
                f"--- Disc {disc_number}/{total}: '{disc_title}' ---"
            )
            if (disc_number - 1) < len(per_disc_titles):
                self.log(f"Using custom disc name.")
            else:
                self.log(f"Using auto-generated disc name.")

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
            _pre_rip_mkvs = frozenset(
                self._safe_glob(
                    os.path.join(rip_path, "**", "*.mkv"),
                    recursive=True,
                    context="Snapshotting pre-rip MKVs",
                )
            )
            from engine.ripper_engine import Job
            job = Job(
                source="all",
                output=rip_path,
                profile="default"
            )
            result = self.engine.run_job(job)
            success = result.success
            success, mkv_files = self._normalize_rip_result(
                rip_path, success, [], _pre_rip_mkvs
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
                    "Stopping multi-disc dump to prevent partial files."
                )
                break
            if not self._verify_container_integrity(mkv_files):
                self.report(
                    f"Dump disc {disc_number} failed ffprobe integrity check"
                )
                self.gui.show_error(
                    "Rip Failed",
                    "Container integrity check failed (ffprobe).\n\n"
                    "Stopping multi-disc dump to prevent corrupt files."
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
                "Multi-Disc Dump Stopped",
                f"Session stopped. Files saved so far in:\n{batch_root}"
            )
            return
        self.gui.show_info(
            "Multi-Disc Dump Complete",
            f"Batch output:\n{batch_root}\n\n"
            f"Use 'Organize Existing MKVs' to sort them."
        )

    def run_organize(self) -> None:
        cfg = self.engine.cfg

        if callable(getattr(self.gui, "ask_directory", None)):
            self.log("Opening folder picker — Organize source folder")
            folder_path = self.gui.ask_directory(
                "Organize",
                "Choose folder with raw .mkv files",
                initialdir=self.engine.cfg.get("temp_folder", ""),
            )
            self.log(
                "Folder picker result — Organize source folder: "
                f"{folder_path if folder_path else '<cancelled>'}"
            )
        else:
            folder_path = self.gui.ask_input(
                "Organize",
                "Enter path to folder with raw .mkv files:",
            )
        if not folder_path:
            self.log("Folder selection cancelled — aborting organize.")
            return

        recursive = self.gui.ask_yesno("Scan subfolders too?")
        if recursive:
            mkv_files = sorted(self._safe_glob(
                os.path.join(folder_path, "**", "*.mkv"),
                recursive=True,
                context="Scanning organize source recursively",
            ))
        else:
            mkv_files = sorted(
                self._safe_glob(
                    os.path.join(folder_path, "*.mkv"),
                    recursive=False,
                    context="Scanning organize source",
                )
            )

        if not mkv_files:
            self.log("No .mkv files found.")
            return

        self.log(f"Found {len(mkv_files)} files in: {folder_path}")

        while True:
            media_type = self.gui.ask_input(
                "Media Type", "TV or Movie? Enter t or m:"
            )
            if not media_type:
                self.log("Cancelled.")
                return

            media_type = media_type.strip().lower()
            if media_type in {"t", "tv", "m", "movie"}:
                break

            self.log("Invalid media type. Enter 't' for TV or 'm' for Movie.")

        is_tv = media_type in {"t", "tv"}

        path_fields: list[tuple[str, str]] = [
            ("tv_folder", "TV Folder"),
            ("temp_folder", "Temp Folder"),
        ] if is_tv else [
            ("movies_folder", "Movies Folder"),
            ("temp_folder", "Temp Folder"),
        ]
        path_overrides: dict[str, str] | None = self._prompt_run_path_overrides(path_fields)
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

        metadata_input = self.gui.ask_input(
            "Metadata ID",
            "Optional: TMDB/IMDB/TVDB ID for Jellyfin matching\n"
            "(e.g. tmdb:12345  or  tt1234567  or  tvdb:79168):"
        )
        metadata_id = str(metadata_input or "")
        if metadata_id:
            self.log(f"Metadata ID: {parse_metadata_id(metadata_id)}")

        year = "0000"
        if is_tv:
            season_input = self.gui.ask_input(
                "Season", "Season number:"
            )
            season_str = str(season_input or "")
            season = int(season_str) if (
                season_str and season_str.isdigit()
            ) else 0
            if season == 0:
                self.log("WARNING: No season number — using 00")
            season_folder = os.path.join(
                tv_root,
                build_tv_folder_name(clean_name(title), metadata_id),
                f"Season {season:02d}",
            )
            extras_folder = os.path.join(season_folder, "Extras")
            os.makedirs(season_folder, exist_ok=True)
            os.makedirs(extras_folder, exist_ok=True)
            dest_folder = season_folder
            self.log(f"Season folder: {season_folder}")
        else:
            year_input = self.gui.ask_input("Year", "Release year:")
            year = str(year_input or "")
            if not year:
                year = "0000"
                self.log("WARNING: No year — using 0000")
            movie_folder = os.path.join(
                movie_root,
                build_movie_folder_name(clean_name(title), year, metadata_id),
            )
            extras_folder = os.path.join(movie_folder, "Extras")
            os.makedirs(movie_folder, exist_ok=True)
            os.makedirs(extras_folder, exist_ok=True)
            dest_folder = movie_folder
            self.log(f"Movie folder: {movie_folder}")

        self.gui.set_status("Analyzing files...")
        self.gui.start_indeterminate()
        try:
            titles_list: AnalyzedFiles = self.engine.analyze_files(
                mkv_files, self.log
            ) or []
        finally:
            self.gui.stop_indeterminate()
            self.gui.set_progress(0)

        if not titles_list:
            self.log("No files to process.")
            return

        move_ok = self._select_and_move(
            titles_list,
            is_tv,
            title,
            dest_folder,
            extras_folder,
            0,
            year,
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

    def _offer_temp_manager(self, temp_root: str) -> None:
        old_folders = self.engine.find_old_temp_folders(temp_root)
        if not old_folders:
            return
        self.gui.show_temp_manager(
            old_folders, self.engine, self.log
        )

    def _ask_extras_selection(
        self,
        titles_list: AnalyzedFiles,
        main_indices: list[int],
    ) -> tuple[list[int] | None, list[int] | None]:
        """Prompt user to select which non-main titles to keep as extras.

        When opt_extras_folder_mode is "split", shows two pickers so the
        user can assign titles to the Extras folder and the bonus folder
        separately.

        Returns:
            (extra_indices, bonus_indices) tuple.
            extra_indices: None (keep all), [] (none), or [idx ...].
            bonus_indices: None when mode is "single" (caller ignores),
                           or [] / [idx ...] when "split".
        """
        _main_set = set(main_indices)
        _non_main = [
            i for i in range(len(titles_list)) if i not in _main_set
        ]
        if not _non_main:
            return [], None

        split_mode = (
            self.engine.cfg.get("opt_extras_folder_mode", "single") == "split"
        )

        if not split_mode:
            # --- single-folder mode (original behaviour) ---
            if self.gui.ask_yesno("Keep all extras?"):
                return None, None
            opts = [
                f"{os.path.basename(titles_list[i][0])}  "
                f"({int(titles_list[i][1] / 60)}min  "
                f"{titles_list[i][2]:.0f} MB)"
                for i in _non_main
            ]
            chosen = self.gui.show_extras_picker(
                "Select Extras",
                "All extras are selected. Deselect any you don't want:",
                opts,
            )
            if chosen is None:
                return [], None
            return [_non_main[c] for c in chosen], None

        # --- split mode: two pickers ---
        bonus_name = self.engine.cfg.get(
            "opt_bonus_folder_name", "featurettes"
        ).title()

        opts = [
            f"{os.path.basename(titles_list[i][0])}  "
            f"({int(titles_list[i][1] / 60)}min  "
            f"{titles_list[i][2]:.0f} MB)"
            for i in _non_main
        ]

        # Picker 1 — Extras folder
        extras_chosen = self.gui.show_extras_picker(
            "Select Extras",
            "Select titles to put in the Extras folder.\n"
            "(Deselect any you don't want as extras.)",
            opts,
        )
        if extras_chosen is None:
            return [], []
        extras_abs: list[int] = (
            [_non_main[c] for c in extras_chosen]
            if extras_chosen else []
        )

        # Remaining non-main titles not claimed as extras
        extras_set = set(extras_abs)
        remaining = [i for i in _non_main if i not in extras_set]

        bonus_abs: list[int] = []
        if remaining:
            remaining_opts = [
                f"{os.path.basename(titles_list[i][0])}  "
                f"({int(titles_list[i][1] / 60)}min  "
                f"{titles_list[i][2]:.0f} MB)"
                for i in remaining
            ]
            bonus_chosen = self.gui.show_extras_picker(
                f"Select {bonus_name}",
                f"Select titles to put in the {bonus_name} folder.\n"
                f"(Deselect any you don't want.)",
                remaining_opts,
            )
            if bonus_chosen is None:
                return extras_abs, []
            if bonus_chosen:
                bonus_abs = [remaining[c] for c in bonus_chosen]

        return extras_abs, bonus_abs

    def _run_disc(self, is_tv: bool) -> None:
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
        tv_root: str = self.get_path("tv")
        movie_root: str = self.get_path("movies")
        temp_root: str = self.get_path("temp")

        self.engine.reset_abort()
        self._reset_state_machine()
        self._wiped_session_paths.clear()
        self.global_extra_counter = 1
        self.session_report       = []
        disc_number = 0
        season = 0
        year = "0000"
        title = ""
        metadata_id: str | None = None
        mid: str | None = None
        library_root: str | None = None
        library_state: dict[int, list[int]] = {}
        series_root: str = temp_root
        dest_folder = ""
        extras_folder = ""
        rip_path = ""

        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            return

        self.log(
            "Flow: session initialized -> waiting for disc + metadata input."
        )

        # Resume-from-old-session is intentionally disabled. We still keep
        # writing per-run JSON metadata for logs/debug context, but new runs
        # always start fresh instead of offering chained resume prompts.
        resume_meta: dict[str, Any] = {}
        resume_path: str | None = None

        if is_tv:
            # -------------------------------------------------------
            # "Attach to existing show folder" mode
            # When the user already has season folders on disk (from
            # a previous session or another tool), they can point
            # JellyRip at the show root and it will infer title,
            # detect what episodes exist, and pick up exactly where
            # the library left off — including filling gaps.
            # -------------------------------------------------------
            if not resume_meta and self.gui.ask_yesno(
                "Continue an existing show folder?\n\n"
                "Choose YES to point to a show folder that already has "
                "season/episode files.  JellyRip will detect what's "
                "already there and suggest the next episode(s).\n\n"
                "Choose NO to start a new folder from scratch."
            ):
                if callable(getattr(self.gui, "ask_directory", None)):
                    chosen_input = self.gui.ask_directory(
                        "Library Folder",
                        "Choose existing show folder",
                        initialdir=tv_root,
                    )
                else:
                    chosen_input = self.gui.ask_input(
                        "Library Folder",
                        "Enter path to existing show folder (e.g. TV/Breaking Bad):",
                    )
                chosen = str(chosen_input).strip() if chosen_input else None
                if chosen and os.path.isdir(chosen):
                    library_root = os.path.normpath(chosen)
                    # Guard: if the user accidentally selected a Season folder
                    # (e.g. "Season 01") instead of the show root, auto-correct
                    # to its parent so season_folder is computed correctly later.
                    if re.match(r"^Season\s+\d{1,3}$",
                                os.path.basename(library_root),
                                re.IGNORECASE):
                        parent = os.path.dirname(library_root)
                        self.log(
                            f"Selected folder looks like a Season folder; "
                            f"auto-correcting library root to parent: {parent}"
                        )
                        library_root = parent
                    library_state = self._scan_library_folder(library_root)
                    if library_state:
                        season_summary = "  ".join(
                            f"S{s:02d}:{len(e)}ep"
                            for s, e in sorted(library_state.items())
                        )
                        self.log(
                            f"Library detected at: {library_root}\n"
                            f"  Seasons: {season_summary}"
                        )
                    else:
                        self.log(
                            f"No season folders found in {library_root} — "
                            f"will create them as needed."
                        )
                else:
                    self.log("No folder selected — starting fresh.")
                    library_root = None

            title_input = self.gui.ask_input(
                "Title", "Exact TV show title:",
                default_value=(
                    os.path.basename(library_root)
                    if library_root
                    else resume_meta.get("title", "")
                )
            )
            title = str(title_input or "")
            if not title:
                title = self._fallback_title_from_mode()
                self.log(f"WARNING: No title — using: {title}")
            self.log(f"Title: {title}")

            metadata_input = self.gui.ask_input(
                "Metadata ID",
                "Optional: TMDB/IMDB/TVDB ID for Jellyfin matching\n"
                "(e.g. tmdb:12345  or  tt1234567  or  tvdb:79168):"
            )
            metadata_id = str(metadata_input or "")
            if metadata_id:
                self.log(f"Metadata ID: {parse_metadata_id(metadata_id)}")

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

            active_resume: dict[str, Any] | None = None
            if resume_meta and safe_int(
                resume_meta.get("disc_number", 0)
            ) == disc_number:
                active_resume = resume_meta

            auto_title_pending = False
            selected_ids: list[int] = []
            selected_size = 0

            if is_tv:
                # Build the season prompt — when in library mode, show
                # the user which seasons already exist and default to the
                # season most likely to need more episodes (incomplete
                # season with the highest number, or the next one after
                # the highest complete season).
                season_hint = ""
                default_season = str(
                    active_resume.get("season", "")
                    if active_resume else ""
                )
                if library_state:
                    season_hint = " (detected: " + ", ".join(
                        f"S{s:02d}:{len(e)}ep"
                        for s, e in sorted(library_state.items())
                    ) + ")"
                    if not default_season:
                        # Suggest the highest season present (most likely
                        # to be the one still being collected).
                        default_season = str(max(library_state.keys()))

                season_input = self.gui.ask_input(
                    "Season",
                    f"Season number for disc {disc_number}:{season_hint}",
                    default_value=default_season,
                )
                season_str = str(season_input or "")
                season = int(season_str) if (
                    season_str and season_str.isdigit()
                ) else 0
                if season == 0:
                    self.log("WARNING: No season number — using 00")

                season_temp: str = os.path.join(
                    series_root, f"Season {season:02d}"
                )
                os.makedirs(season_temp, exist_ok=True)

                # Destination: use existing library root when provided,
                # otherwise build the standard path under tv_root.
                if library_root:
                    season_folder = os.path.join(
                        library_root, f"Season {season:02d}"
                    )
                else:
                    season_folder = os.path.join(
                        tv_root,
                        build_tv_folder_name(clean_name(title), metadata_id or ""),
                        f"Season {season:02d}",
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
                title_input = self.gui.ask_input(
                    "Title", f"Title for disc {disc_number}:",
                    default_value=(active_resume or {}).get("title", "")
                )
                title = str(title_input or "")
                if not title:
                    auto_title_pending = True
                    title = make_temp_title()
                    self.log(
                        "WARNING: No title entered — using fallback naming "
                        "mode after scan when possible."
                    )
                year_input = self.gui.ask_input(
                    "Year", "Release year:",
                    default_value=str(
                        (active_resume or {}).get("year", year)
                    )
                )
                year = str(year_input or "")
                if not year:
                    year = "0000"
                    self.log("WARNING: No year — using 0000")
                mid_input = self.gui.ask_input(
                    "Metadata ID",
                    "Optional: TMDB/IMDB/TVDB ID for Jellyfin matching\n"
                    "(e.g. tmdb:12345  or  tt1234567  or  tvdb:79168):"
                )
                mid = str(mid_input or "")
                if mid:
                    self.log(f"Metadata ID: {parse_metadata_id(mid)}")
                movie_folder = os.path.join(
                    movie_root,
                    build_movie_folder_name(clean_name(title), year, mid or ""),
                )
                extras_folder = os.path.join(movie_folder, "Extras")
                os.makedirs(movie_folder, exist_ok=True)
                os.makedirs(extras_folder, exist_ok=True)
                dest_folder = movie_folder
                self.log(f"Movie folder: {movie_folder}")
                # Always create a new rip folder — even on resume — so that
                # _purge_rip_target_files never deletes the previously ripped
                # files that are still sitting in the old resume folder.
                rip_path = os.path.join(temp_root, make_rip_folder_name())
                if active_resume and resume_path:
                    # Mark the old session folder as superseded so it is not
                    # offered for resume again in subsequent sessions.
                    self.engine.update_temp_metadata(
                        resume_path, phase="organized"
                    )

            os.makedirs(rip_path, exist_ok=True)
            # rip_path is always a new folder (even on resume), so always
            # write fresh metadata rather than trying to update a file that
            # does not exist yet.
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
            disc_titles: DiscTitles | None = self.scan_with_retry()

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
                        movie_root,
                        build_movie_folder_name(
                            clean_name(title), year, mid or "",
                        ),
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
                selected_ids: list[int] = restored_selected_ids
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
                            selected_ids_raw = self.gui.show_disc_tree(
                                disc_titles, is_tv, self.preview_title
                            )
                            if selected_ids_raw is None:
                                self.log("Cancelled.")
                                break
                            selected_ids = [int(item) for item in selected_ids_raw]
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
                        best_id = safe_int(best.get("id", -1))
                        selected_ids = [best_id]
                        selected_size = safe_int(best.get("size_bytes", 0))
                        self.log(
                            f"Smart Rip: auto-selected Title "
                            f"{best_id + 1} "
                            f"(score={smart_score:.3f}) "
                            f"{best['duration']} {best['size']}"
                        )
                else:
                    best_id = safe_int(best.get("id", -1))
                    selected_ids = [best_id]
                    selected_size = safe_int(best.get("size_bytes", 0))
                    self.log(
                        f"Smart Rip: auto-selected Title "
                        f"{best_id + 1} "
                        f"(score={smart_score:.3f}) "
                        f"{best['duration']} {best['size']}"
                    )
            elif not restored_selected_ids:
                selected_ids_raw = self.gui.show_disc_tree(
                    disc_titles, is_tv, self.preview_title
                )
                if selected_ids_raw is None:
                    self.log("Cancelled.")
                    break
                selected_ids = [int(item) for item in selected_ids_raw]
                if not selected_ids:
                    self.log("No titles selected.")
                    if not self.gui.ask_yesno("Try again?"):
                        break
                    continue
                selected_size = sum(
                    t["size_bytes"] for t in disc_titles
                    if t["id"] in selected_ids
                )

            expected_size_by_title: ExpectedSizeMap = {
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
            _pre_rip_mkvs = frozenset(
                self._safe_glob(
                    os.path.join(rip_path, "**", "*.mkv"),
                    recursive=True,
                    context="Snapshotting pre-rip MKVs",
                )
            )
            from engine.ripper_engine import Job
            job = Job(
                source=','.join(str(tid) for tid in selected_ids),
                output=rip_path,
                profile="default"
            )
            result = self.engine.run_job(job)
            success = result.success
            failed_titles = result.errors
            self._warn_degraded_rips()

            if failed_titles:
                self.report(
                    f"Disc {disc_number}: titles failed — "
                    f"{failed_titles}"
                )

            success, mkv_files = self._normalize_rip_result(
                rip_path, success, failed_titles, _pre_rip_mkvs
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
                titles_list: AnalyzedFiles = self.engine.analyze_files(
                    mkv_files, self.log
                ) or []
                self.log(f"Analysis completed: {len(titles_list)} title(s) found.")
            except Exception as e:
                self.log(f"ERROR during analysis: {e}")
                titles_list = []
            finally:
                self.gui.stop_indeterminate()
                self.gui.set_progress(0)

            if not titles_list:
                self.log("Analysis aborted or no files returned.")
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            # Integrity check uses pre-analyzed data — no extra ffprobe pass.
            # Build expected-duration/size maps from disc scan + rip tracking.
            _dur_by_id_d = {
                int(t.get("id", -1)): float(t.get("duration_seconds", 0) or 0)
                for t in disc_titles
            }
            _size_by_id_d = {
                int(t.get("id", -1)): int(t.get("size_bytes", 0) or 0)
                for t in disc_titles
            }
            _exp_dur_d: dict[str, float] = {}
            _exp_size_d: dict[str, int] = {}
            title_file_map = _normalize_title_file_map(self.engine.last_title_file_map)
            for _tid, _files in title_file_map.items():
                _ed = _dur_by_id_d.get(int(_tid), 0)
                _es = _size_by_id_d.get(int(_tid), 0)
                for _fp in _files:
                    if _ed > 0:
                        _exp_dur_d[_fp] = _ed
                    if _es > 0:
                        _exp_size_d[_fp] = _es

            if not self._verify_container_integrity(
                mkv_files,
                analyzed=titles_list,
                expected_durations=_exp_dur_d or None,
                expected_sizes=_exp_size_d or None,
                title_file_map=title_file_map or None,
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
                titles_list,
                is_tv,
                title,
                dest_folder,
                extras_folder,
                season if is_tv else 0,
                year if not is_tv else "0000",
                expected_size_by_title=expected_size_by_title,
                session_rip_path=rip_path,
                session_meta=active_resume,
                selected_title_ids=selected_ids,
            )

            if move_ok:
                shutil.rmtree(rip_path, ignore_errors=True)
                if os.path.exists(rip_path):
                    self.log(f"Warning: could not delete {rip_path}")
                # Also remove the original resume folder if it differs from
                # the fresh rip folder (it was superseded by this session).
                if (active_resume and resume_path
                        and os.path.normpath(resume_path) !=
                            os.path.normpath(rip_path)
                        and os.path.isdir(resume_path)):
                    shutil.rmtree(resume_path, ignore_errors=True)
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

        # Mark session as completed so write_session_summary uses the
        # correct code path (warnings list vs clean success).
        # sm.complete() is a no-op if the session already failed.
        self.sm.complete()
        self.write_session_summary()
        self.gui.set_status("Ready")
        self.gui.set_progress(0)
        self.gui.show_info("Done", "Session complete!")

    def _select_and_move(
        self,
        titles_list: AnalyzedFiles,
        is_tv: bool,
        title: str,
        dest_folder: str,
        extras_folder: str,
        season: int,
        year: str,
        expected_size_by_title: ExpectedSizeMap | None = None,
        session_rip_path: str | None = None,
        session_meta: dict[str, Any] | None = None,
        selected_title_ids: list[int] | None = None,
    ) -> bool:
        options: list[str] = []
        for i, (f, dur, mb) in enumerate(titles_list, 1):
            mins = int(dur // 60) if dur > 0 else "?"
            options.append(
                f"{i}: {os.path.basename(f)}  ~{mins} min  {mb} MB"
            )

        restored_main_indices = self._map_title_ids_to_analyzed_indices(
            titles_list,
            list(selected_title_ids or []),
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
                    int(str(s).split(":")[0]) - 1 for s in selected
                ]

            default_episode_numbers: list[int] = []
            if session_meta:
                default_episode_numbers = session_meta.get(
                    "episode_numbers", []
                ) or []

            # Auto-detect episode offset from existing files in the
            # destination season folder.  Uses gap-fill logic so a
            # missing disc (e.g. S01E03 absent) is suggested first
            # rather than simply appending after the highest number.
            if (
                not default_episode_numbers
                and dest_folder
            ):
                existing_eps = self._scan_episode_files(dest_folder, season)
                if existing_eps:
                    next_ep = self.get_next_episode(existing_eps)
                    suggested = list(
                        range(next_ep, next_ep + len(main_indices))
                    )
                    default_episode_numbers = suggested
                    gap_fill = next_ep <= max(existing_eps)
                    verb = "gap-filling from" if gap_fill else "continuing from"
                    self.log(
                        f"Detected {len(existing_eps)} existing episode(s) in "
                        f"Season {season:02d} — {verb} "
                        f"episode(s) {suggested[0]}â€“{suggested[-1]}."
                    )

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

                # Duplicate-episode guard: check whether any of the
                # chosen episode numbers already exist as files in the
                # destination folder.  This prevents silent overwrites
                # when pointing at an existing library.
                if dest_folder:
                    existing_eps = self._scan_episode_files(
                        dest_folder, season
                    )
                    colliding = [
                        ep for ep in episode_numbers
                        if ep in existing_eps
                    ]
                    if colliding:
                        collision_str = ", ".join(
                            f"E{ep:02d}" for ep in sorted(colliding)
                        )
                        self.log(
                            f"WARNING: Episode(s) {collision_str} already "
                            f"exist in Season {season:02d}. "
                            f"Existing files will NOT be overwritten "
                            f"(unique_path will rename)."
                        )
                        if not self.gui.ask_yesno(
                            f"Episode(s) {collision_str} already exist in "
                            f"this season folder.\n\n"
                            f"Continue anyway? "
                            f"(Files will be renamed, not overwritten.)"
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
            real_names    = parse_episode_names(name_input)
            extra_indices, bonus_indices = self._ask_extras_selection(
                titles_list, main_indices
            )

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
                + (f" - {real_names[idx]}" if idx < len(real_names) and real_names[idx] else "")
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

                main_indices = [int(str(selected[0]).split(":")[0]) - 1]
            extra_indices, bonus_indices = self._ask_extras_selection(
                titles_list, main_indices
            )
            episode_numbers: list[int] = []
            real_names: list[str] = []

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
        bonus_folder: str | None = None
        if bonus_indices:
            bonus_name = self.engine.cfg.get(
                "opt_bonus_folder_name", "featurettes"
            )
            parent = os.path.dirname(extras_folder)
            bonus_folder = os.path.join(parent, bonus_name)
            os.makedirs(bonus_folder, exist_ok=True)
        success, self.global_extra_counter, moved_paths = self.engine.move_files(
            titles_list, main_indices, episode_numbers,
            real_names, extra_indices, is_tv, title,
            dest_folder, extras_folder, season, year,
            self.global_extra_counter,
            on_progress=lambda percent: self.emit(Event("progress", "", {"percent": percent})),  # type: ignore[arg-type]
            on_log=lambda message: self.emit(Event("log", "", {"message": message})),  # type: ignore[arg-type]
            bonus_indices=bonus_indices,
            bonus_folder=bonus_folder,
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
