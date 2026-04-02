"""Engine layer implementation."""

import glob
import json
import os
import queue as queue_module
import shutil
import subprocess
import sys as _sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Suppress black CMD flash on Windows for every subprocess we spawn.
_POPEN_FLAGS = {"creationflags": 0x08000000} if _sys.platform == "win32" else {}

from shared.runtime import RIP_ATTEMPT_FLAGS

from config import resolve_ffprobe, resolve_makemkvcon
from utils.helpers import clean_name
from utils.parsing import (
    parse_cli_args,
    parse_duration_to_seconds,
    parse_size_to_bytes,
    safe_int,
)
from utils.scoring import score_title


class RipperEngine:
    def __init__(self, cfg):
        """
        LAYER 1 — Engine

        Pure logic layer. No UI calls, no tkinter, no user interaction.

        Owns everything that touches the disc, the filesystem, and MakeMKV:
          - Disc scanning and title scoring
          - Ripping via makemkvcon subprocess
          - File analysis via ffprobe
          - Atomic file moves and metadata writes
          - Disk space checks and partial file cleanup

        All public methods accept on_log and on_progress callbacks so the
        controller can route output to the UI without this layer knowing
        anything about tkinter.

        Threading model: abort_event is a threading.Event checked throughout
        all long-running operations. Set it to stop everything cleanly.
        """
        self.cfg             = cfg
        self.abort_event     = threading.Event()
        self.current_process = None
        self._abort_lock     = threading.Lock()
        self.last_move_error = ""
        self.last_title_file_map = {}
        self.last_degraded_titles: list = []
        self._ffprobe_cache = {}
        self._last_scan_total_bytes = None
        self._last_scan_timestamp = 0.0
        self._last_scan_target = None

    @staticmethod
    def _io_path(path):
        """Return a Windows long-path form for file I/O when needed."""
        if _sys.platform != "win32" or not path:
            return path
        p = os.path.abspath(str(path))
        if p.startswith("\\\\?\\"):
            return p
        if p.startswith("\\\\"):
            return "\\\\?\\UNC\\" + p.lstrip("\\")
        return "\\\\?\\" + p

    @property
    def abort_flag(self):
        return self.abort_event.is_set()

    def abort(self):
        """Set abort flag and terminate active MakeMKV process if running."""
        with self._abort_lock:
            if self.abort_event.is_set():
                return
            self.abort_event.set()
        proc = self.current_process
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                self.current_process = None

    def reset_abort(self):
        """Clear abort state before starting a new operation."""
        self.abort_event.clear()

    def unique_path(self, path):
        # Best-effort unique destination naming to avoid collisions.
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 2
        while os.path.exists(new_path := f"{base} - {counter}{ext}"):
            counter += 1
        return new_path

    def validate_tools(self):
        """Validate configured MakeMKV and ffprobe paths."""
        makemkvcon = resolve_makemkvcon(
            os.path.normpath(self.cfg["makemkvcon_path"])
        )
        ffprobe, ffprobe_source = resolve_ffprobe(
            os.path.normpath(self.cfg["ffprobe_path"])
        )
        if not os.path.exists(makemkvcon):
            return False, (
                f"MakeMKV not found at:\n{makemkvcon}"
                f"\n\nPlease check Settings."
            )
        if not os.path.exists(ffprobe):
            return False, (
                f"ffprobe not found."
                f"\n\nDownload ffmpeg from https://ffmpeg.org and point"
                f"\nSettings \u2192 Paths \u2192 ffprobe folder to its bin directory."
            )
        self._ffprobe_source = ffprobe_source
        return True, ""

    def get_disc_target(self):
        """Return MakeMKV disc selector for the configured drive index."""
        return f"disc:{self.cfg.get('opt_drive_index', 0)}"

    def cleanup_partial_files(self, temp_root, on_log):
        """Remove stale `.partial` files left by interrupted move/rip operations."""
        if not self.cfg.get("opt_clean_partials_startup", True):
            return
        if not os.path.isdir(temp_root):
            return
        for root_dir, dirs, files in os.walk(temp_root):
            for f in files:
                if f.endswith(".partial"):
                    full = os.path.join(root_dir, f)
                    try:
                        os.remove(full)
                        on_log(
                            f"Cleaned up leftover partial file: {f}"
                        )
                    except Exception as e:
                        on_log(
                            f"Warning: could not remove {f}: {e}"
                        )

    def find_old_temp_folders(self, temp_root):
        """Enumerate temp rip folders with aggregate file count and size metadata."""
        if not os.path.isdir(temp_root):
            return []
        folders = []
        for name in os.listdir(temp_root):
            full = os.path.join(temp_root, name)
            if os.path.isdir(full) and (
                name.startswith("Disc_") or
                name.startswith("TEMP_") or
                name.startswith("Unattended_")
            ):
                # Single pass: count MKVs and calculate size together
                mkv_count = 0
                total_size = 0
                try:
                    for dp, dn, fns in os.walk(full):
                        for f in fns:
                            if f.endswith(".mkv"):
                                mkv_count += 1
                            try:
                                total_size += os.path.getsize(
                                    os.path.join(dp, f)
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
                folders.append((full, name, mkv_count, total_size))
        folders.sort(key=lambda x: x[1])
        return folders

    def find_resumable_sessions(self, temp_root):
        """Find temp sessions with saved workflow metadata that can be resumed."""
        resumable = []
        if not os.path.isdir(temp_root):
            return resumable
        for name in os.listdir(temp_root):
            full = os.path.join(temp_root, name)
            if not os.path.isdir(full):
                continue
            meta = self.read_temp_metadata(full)
            if meta and meta.get("phase") not in {"complete", "organized"}:
                # Count MKV files efficiently: one pass
                mkv_count = 0
                try:
                    for dp, dn, fns in os.walk(full):
                        mkv_count += sum(
                            1 for f in fns if f.endswith(".mkv")
                        )
                except Exception:
                    pass
                resumable.append((full, name, meta, mkv_count))
        return resumable

    def _atomic_write_json(self, path, data):
        """Write JSON atomically using temp file + os.replace."""
        tmp = path + ".tmp"
        io_tmp = self._io_path(tmp)
        io_path = self._io_path(path)
        try:
            with open(io_tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(io_tmp, io_path)
        except Exception as e:
            print(f"Warning: failed atomic JSON write for {path}: {e}")
            if os.path.exists(io_tmp):
                try:
                    os.remove(io_tmp)
                except Exception as cleanup_err:
                    print(
                        "Warning: failed to remove temporary JSON file "
                        f"{tmp}: {cleanup_err}"
                    )

    def write_temp_metadata(self, rip_path, title, disc_number,
                            season=None, year=None, media_type=None,
                            selected_titles=None, episode_names=None,
                            episode_numbers=None, dest_folder=None,
                            completed_titles=None, phase="ripping"):
        """Create initial metadata file for a rip temp folder."""
        meta = {
            "title":            title,
            "year":             year,
            "media_type":       media_type,
            "season":           season,
            "selected_titles":  list(selected_titles or []),
            "episode_names":    list(episode_names or []),
            "episode_numbers":  list(episode_numbers or []),
            "completed_titles": list(completed_titles or []),
            "phase":            phase,
            "dest_folder":      dest_folder,
            "disc_number":      disc_number,
            "timestamp":        datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "file_count":       0,
            "status":           "ripping",
        }
        self._atomic_write_json(
            os.path.join(rip_path, "_rip_meta.json"), meta
        )

    def update_temp_metadata(self, rip_path, status=None, **updates):
        """Refresh metadata counters/status for a temp session folder."""
        meta_path = os.path.join(rip_path, "_rip_meta.json")
        io_meta_path = self._io_path(meta_path)
        try:
            with open(io_meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            # Count MKV files: single pass instead of glob
            file_count = 0
            try:
                for dp, dn, fns in os.walk(rip_path):
                    file_count += sum(
                        1 for f in fns if f.endswith(".mkv")
                    )
            except Exception:
                pass
            meta["file_count"] = file_count
            if status:
                meta["status"] = status
            for key, value in updates.items():
                meta[key] = value
            self._atomic_write_json(meta_path, meta)
        except Exception as e:
            print(f"Warning: failed to update session metadata {meta_path}: {e}")

    def read_temp_metadata(self, rip_path):
        """Read metadata for a temp session folder, returning None on failure."""
        meta_path = os.path.join(rip_path, "_rip_meta.json")
        try:
            with open(self._io_path(meta_path), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def scan_disc(self, on_log, on_progress):
        """
        Scan disc and return list of title dicts sorted by score.

        Parses both TINFO (title info) and SINFO (stream info) from
        makemkvcon output. Stores duration_seconds at parse time so
        score_title() has numeric data to work with.

        Returns list sorted best-first, or None on abort/error.
        """
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        global_args = parse_cli_args(
            self.cfg.get("opt_makemkv_global_args", ""),
            on_log,
            "MakeMKV global args"
        )
        info_args = parse_cli_args(
            self.cfg.get("opt_makemkv_info_args", ""),
            on_log,
            "MakeMKV info args"
        )
        on_log(f"Scanning disc ({disc_target})...")
        titles      = {}
        title_count = 0
        try:
            proc = subprocess.Popen(
                [makemkvcon] + global_args +
                ["-r", "info", disc_target] + info_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **_POPEN_FLAGS
            )
            for line in iter(proc.stdout.readline, ""):
                if self.abort_event.is_set():
                    proc.kill()
                    return None
                line = line.strip()
                if not line:
                    continue
                if line.startswith("TINFO:"):
                    parts = line[6:].split(",", 3)
                    if len(parts) < 4:
                        continue
                    try:
                        tid  = int(parts[0])
                        attr = int(parts[1])
                        val  = parts[3].strip().strip('"')
                    except (ValueError, IndexError):
                        continue
                    if tid not in titles:
                        titles[tid] = {
                            "id":               tid,
                            "name":             f"Title {tid+1}",
                            "duration":         "",
                            "duration_seconds": 0,
                            "size":             "",
                            "size_bytes":       0,
                            "chapters":         0,
                            "_invalid":         False,
                            "streams":          {},
                        }
                        title_count += 1
                        on_progress(
                            min(5 + title_count, 90)
                        )
                    if attr == 2:
                        titles[tid]["name"] = val
                    elif attr == 9:
                        titles[tid]["duration"] = val
                        dur_seconds = parse_duration_to_seconds(val)
                        titles[tid]["duration_seconds"] = dur_seconds
                        if val and dur_seconds <= 0:
                            titles[tid]["_invalid"] = True
                    elif attr == 8:
                        titles[tid]["chapters"] = safe_int(val)
                    elif attr == 11:
                        size_bytes = parse_size_to_bytes(val)
                        titles[tid]["size_bytes"] = size_bytes
                        if val and size_bytes <= 0:
                            titles[tid]["_invalid"] = True
                        if size_bytes > 0:
                            gb = size_bytes / (1024**3)
                            titles[tid]["size"] = f"{gb:.2f} GB"
                        else:
                            titles[tid]["size"] = val
                elif line.startswith("SINFO:"):
                    parts = line[6:].split(",", 4)
                    if len(parts) < 5:
                        continue
                    try:
                        tid  = int(parts[0])
                        sid  = int(parts[1])
                        attr = int(parts[2])
                        val  = parts[4].strip().strip('"')
                    except (ValueError, IndexError):
                        continue
                    if tid not in titles:
                        continue
                    streams = titles[tid]["streams"]
                    if sid not in streams:
                        streams[sid] = {}
                    stream = streams[sid]
                    if attr == 1:
                        stream["type"] = val
                    elif attr == 2:
                        stream["codec"] = val
                    elif attr == 3:
                        stream["lang"] = val
                    elif attr == 4:
                        stream["channels"] = val
                    elif attr == 21:
                        stream["lang_name"] = val
            proc.wait()
        except Exception as e:
            on_log(f"Error scanning disc: {e}")
            return None

        result = []
        for tid in sorted(titles.keys()):
            t = titles[tid]
            if not isinstance(t.get("size_bytes"), (int, float)):
                t["size_bytes"] = 0
                t["_invalid"] = True
            if not isinstance(t.get("duration_seconds"), (int, float)):
                t["duration_seconds"] = 0
                t["_invalid"] = True
            t["chapters"] = safe_int(t.get("chapters", 0))
            audio_tracks    = []
            subtitle_tracks = []
            for sid in sorted(t["streams"].keys()):
                s     = t["streams"][sid]
                stype = s.get("type", "")
                if stype == "Audio":
                    audio_tracks.append({
                        "id":        sid,
                        "codec":     s.get("codec", ""),
                        "lang":      s.get("lang", ""),
                        "lang_name": s.get("lang_name", ""),
                        "channels":  s.get("channels", ""),
                    })
                elif stype == "Subtitles":
                    subtitle_tracks.append({
                        "id":        sid,
                        "lang":      s.get("lang", ""),
                        "lang_name": s.get("lang_name", ""),
                    })
            t["audio_tracks"]    = audio_tracks
            t["subtitle_tracks"] = subtitle_tracks
            del t["streams"]
            result.append(t)

        # Sort by score descending — best candidate first.
        # Keep scores out of title dicts to avoid mutating shared objects.
        scored = [(t, score_title(t, result)) for t in result]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        result = [t for t, _score in scored]

        # Log scores for debugging edge cases and bad discs
        # On large discs: show top 20 + always include selected title.
        log_all = len(scored) <= 50
        on_log(
            "Title scores:"
            if log_all else
            f"Title scores (top 20 of {len(scored)} shown, + selected):"
        )
        # Collect titles to log: all or top 20 + best if not in top 20
        titles_to_log = scored if log_all else scored[:20]
        if not log_all and scored and scored[0] not in titles_to_log:
            titles_to_log = titles_to_log + [scored[0]]

        for t, score in titles_to_log:
            raw_name = str(t.get("name", "") or "").strip()
            projected_name = clean_name(raw_name) if raw_name else ""
            if not projected_name:
                projected_name = f"Title_{safe_int(t.get('id', 0)) + 1:02d}"
            on_log(
                f"  Title {t['id']+1}: score={score:.3f} | "
                f"{t['duration']} {t['size']} | "
                f"chap={safe_int(t.get('chapters', 0))} "
                f"aud={len(t.get('audio_tracks', []))} "
                f"sub={len(t.get('subtitle_tracks', []))} | "
                f"projected='{projected_name}'"
            )
        if scored:
            best_title = scored[0][0]
            best_raw_name = str(best_title.get("name", "") or "").strip()
            best_projected_name = clean_name(best_raw_name) if best_raw_name else ""
            if not best_projected_name:
                best_projected_name = f"Title_{safe_int(best_title.get('id', 0)) + 1:02d}"
            on_log(
                f"BEST: Title {scored[0][0]['id']+1} "
                f"(score={scored[0][1]:.3f}) "
                f"projected='{best_projected_name}'"
            )

            if len(scored) > 1:
                diff = scored[0][1] - scored[1][1]
                if diff < 0.05:
                    on_log(
                        "WARNING: Top titles are very close — "
                        "possible ambiguity."
                    )

        self._last_scan_total_bytes = sum(
            max(0, int(t.get("size_bytes", 0) or 0)) for t in result
        )
        self._last_scan_timestamp = time.time()
        self._last_scan_target = disc_target

        on_progress(100)
        on_log(f"Disc scan complete. Found {len(result)} title(s).")
        return result

    def get_disc_size(self, on_log, prefer_cached=False):
        """
        Lightweight disc size query used only by dump/multi-disc modes.
        TV/Movie disc flows use size_bytes from scan_disc() instead,
        avoiding a second full pass over the disc.
        """
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        if prefer_cached:
            scan_age = time.time() - float(self._last_scan_timestamp or 0.0)
            if (
                self._last_scan_target == disc_target
                and self._last_scan_total_bytes
                and scan_age < 300
            ):
                on_log("Using cached disc size from recent scan.")
                return int(self._last_scan_total_bytes)
        global_args = parse_cli_args(
            self.cfg.get("opt_makemkv_global_args", ""),
            on_log,
            "MakeMKV global args"
        )
        info_args = parse_cli_args(
            self.cfg.get("opt_makemkv_info_args", ""),
            on_log,
            "MakeMKV info args"
        )
        total_bytes = 0
        try:
            proc = subprocess.Popen(
                [makemkvcon] + global_args +
                ["-r", "info", disc_target] + info_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **_POPEN_FLAGS
            )
            for line in iter(proc.stdout.readline, ""):
                if self.abort_event.is_set():
                    proc.kill()
                    return None
                if line.startswith("TINFO:"):
                    parts = line[6:].split(",", 3)
                    if len(parts) >= 4 and parts[1] == "11":
                        try:
                            size_str = parts[3].strip().strip('"')
                            total_bytes += parse_size_to_bytes(size_str)
                        except IndexError:
                            pass
            proc.wait()
        except Exception as e:
            on_log(f"Warning: could not read disc size: {e}")
            return None
        if total_bytes > 0:
            self._last_scan_total_bytes = int(total_bytes)
            self._last_scan_timestamp = time.time()
            self._last_scan_target = disc_target
            return total_bytes
        return None

    def check_disk_space(self, path, required_bytes, on_log):
        hard_floor = int(
            self.cfg.get("opt_hard_block_gb", 20)
        ) * (1024**3)
        try:
            if not os.path.exists(path):
                on_log(f"Warning: disk-space path does not exist: {path}")
                return "ok", 0, required_bytes
            free = shutil.disk_usage(path).free
            on_log(
                f"Disk space — "
                f"Required: {required_bytes / (1024**3):.1f} GB  "
                f"Free: {free / (1024**3):.1f} GB"
            )
            if free < hard_floor:
                return "block", free, required_bytes
            if free < required_bytes:
                return "warn", free, required_bytes
            return "ok", free, required_bytes
        except Exception as e:
            on_log(f"Warning: could not check disk space: {e}")
            return "ok", 0, required_bytes

    def _snapshot_mkv_files(self, rip_path):
        return set(
            glob.glob(
                os.path.join(rip_path, "**", "*.mkv"),
                recursive=True
            )
        )

    def _purge_rip_target_files(self, rip_path, on_log):
        """Ensure each rip starts fresh; never resume prior file fragments."""
        removed = 0
        for pattern in ("**/*.mkv", "**/*.partial"):
            for f in glob.glob(
                os.path.join(rip_path, pattern), recursive=True
            ):
                try:
                    os.remove(f)
                    removed += 1
                except Exception:
                    pass
        if removed:
            on_log(
                f"Removed {removed} pre-existing file(s) from rip target "
                "to avoid file-level resume."
            )

    def wipe_session_outputs(self, rip_path, on_log):
        """Delete ripped outputs for a session while preserving metadata."""
        removed = 0
        for pattern in ("**/*.mkv", "**/*.partial"):
            for f in glob.glob(
                os.path.join(rip_path, pattern), recursive=True
            ):
                try:
                    os.remove(f)
                    removed += 1
                except Exception:
                    pass
        on_log(
            f"Cleared {removed} session output file(s); preserved metadata "
            "for workflow resume."
        )

    def _clean_new_mkv_files(self, rip_path, before_set, on_log):
        """
        Delete only MKV files created since before_set snapshot.
        Preserves successfully ripped titles from prior attempts in
        a multi-title session.
        """
        if not self.cfg.get("opt_clean_mkv_before_retry", True):
            return
        after_set = self._snapshot_mkv_files(rip_path)
        new_files = after_set - before_set
        for f in new_files:
            try:
                os.remove(f)
                on_log(
                    f"Removed partial MKV before retry: "
                    f"{os.path.basename(f)}"
                )
            except Exception:
                pass
        # Also remove transient partial files from failed attempts.
        for f in glob.glob(
            os.path.join(rip_path, "**", "*.partial"),
            recursive=True
        ):
            try:
                os.remove(f)
                on_log(
                    f"Removed transient partial before retry: "
                    f"{os.path.basename(f)}"
                )
            except Exception:
                pass

    def _log_forced_failure_with_outputs(self, rip_path, before_set, on_log):
        """Log when a failed MakeMKV run still created output files."""
        after_set = self._snapshot_mkv_files(rip_path)
        new_files = after_set - before_set
        if not new_files:
            return
        on_log(
            "MakeMKV failed with non-zero exit code; forcing failure "
            f"regardless of output ({len(new_files)} new file(s))."
        )

    def _stdout_reader(self, pipe, q):
        """Feed subprocess stdout into a queue. Runs in a daemon thread."""
        try:
            for line in iter(pipe.readline, ""):
                q.put(line)
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _run_rip_process(self, cmd, on_progress, on_log):
        """
        Run a single MakeMKV rip subprocess with reliable cross-platform
        stdout handling.

        Uses a dedicated reader thread that feeds lines into a queue, then
        reads from that queue with a 1-second timeout. This approach:
          - Avoids blocking readline() on Windows where select() doesn't
            work on pipes
          - Keeps abort checks responsive regardless of MakeMKV output rate

        Returns True on rc==0, False otherwise.
        """
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **_POPEN_FLAGS
        )
        self.current_process = proc

        line_queue    = queue_module.Queue()
        reader        = threading.Thread(
            target=self._stdout_reader,
            args=(proc.stdout, line_queue),
            daemon=True
        )
        reader.start()

        last_pct        = -1
        last_output     = time.time()
        rip_start       = time.time()
        stall_detection = self.cfg.get("opt_stall_detection", True)
        stall_timeout   = int(
            self.cfg.get("opt_stall_timeout_seconds", 120)
        )
        stall_warned = False

        while True:
            if self.abort_event.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                on_log("Rip aborted.")
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                self.current_process = None
                return False

            try:
                line = line_queue.get(timeout=1.0)
            except queue_module.Empty:
                if proc.poll() is not None:
                    break
                if stall_detection:
                    if (not stall_warned and
                            time.time() - last_output > stall_timeout):
                        on_log(
                            f"No output for {stall_timeout}s — "
                            "process may be reading difficult sectors; waiting."
                        )
                        stall_warned = True
                continue

            last_output = time.time()
            stall_warned = False
            line = line.strip()
            if not line:
                continue

            if line.startswith("PRGV:"):
                parts = line[5:].split(",")
                if len(parts) >= 2:
                    try:
                        current = int(parts[0])
                        total   = int(parts[1])
                        if total > 0 and current > 0:
                            pct = min(
                                int(current / total * 100), 100
                            )
                            on_progress(pct)
                            if pct != last_pct:
                                last_pct = pct
                                elapsed  = time.time() - rip_start
                                rate     = (
                                    current / elapsed
                                    if elapsed > 0 else 0
                                )
                                remain   = (
                                    int((total - current) / rate)
                                    if rate > 0 else 0
                                )
                                mins, secs = divmod(remain, 60)
                                eta = (
                                    f"~{mins}m {secs:02d}s remaining"
                                    if remain > 0 else ""
                                )
                                on_log(f"Ripping: {pct}%  {eta}")
                    except ValueError:
                        pass
            elif line.startswith("PRGT:"):
                parts = line[5:].split(",")
                if len(parts) >= 3:
                    on_log(f"Task: {parts[2].strip()}")
            elif line.startswith("PRGC:"):
                parts = line[5:].split(",")
                if len(parts) >= 3:
                    on_log(parts[2].strip())
            elif line.startswith("MSG:"):
                parts = line[4:].split(",", 4)
                if len(parts) >= 5:
                    msg = parts[4].strip().strip('"')
                    if msg:
                        on_log(msg)
                        # Log all messages but don't treat them as failures.
                        # MakeMKV tolerates recoverable errors (read errors,
                        # parsing issues, etc) and continues. Trust the
                        # return code, not the message content.

        try:
            proc.wait(timeout=30)
        except Exception:
            pass
        try:
            rc = proc.returncode
            if rc is None:
                rc = 1
        except Exception:
            rc = 1
        on_log(f"MakeMKV exit code: {rc}")
        self.current_process = None

        try:
            reader.join(timeout=1)
        except Exception:
            pass

        try:
            while True:
                line = line_queue.get_nowait()
                line = line.strip()
                if line.startswith("MSG:"):
                    parts = line[4:].split(",", 4)
                    if len(parts) >= 5:
                        msg = parts[4].strip().strip('"')
                        if msg:
                            on_log(msg)
                            # Log all messages. Don't use them for failure
                            # detection — trust the return code only.
        except queue_module.Empty:
            pass

        return rc == 0

    def _run_preview_process(self, cmd, preview_seconds, on_log):
        """Run a disposable preview rip with a hard time limit and no retries."""
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **_POPEN_FLAGS
        )
        self.current_process = proc

        line_queue = queue_module.Queue()
        reader = threading.Thread(
            target=self._stdout_reader,
            args=(proc.stdout, line_queue),
            daemon=True
        )
        reader.start()

        start = time.time()
        timed_out = False

        while True:
            if self.abort_event.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                self.current_process = None
                return False

            if time.time() - start >= preview_seconds and proc.poll() is None:
                timed_out = True
                on_log(
                    f"Preview sample reached {preview_seconds}s; stopping rip."
                )
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                except Exception:
                    pass
                break

            try:
                line = line_queue.get(timeout=0.5)
            except queue_module.Empty:
                if proc.poll() is not None:
                    break
                continue

            line = line.strip()
            if not line:
                continue

            if line.startswith("PRGT:"):
                parts = line[5:].split(",")
                if len(parts) >= 3:
                    on_log(f"Preview task: {parts[2].strip()}")
            elif line.startswith("MSG:"):
                parts = line[4:].split(",", 4)
                if len(parts) >= 5:
                    msg = parts[4].strip().strip('"')
                    if msg:
                        on_log(msg)

        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        self.current_process = None

        try:
            reader.join(timeout=1)
        except Exception:
            pass

        return timed_out or proc.returncode == 0

    def rip_preview_title(self, rip_path, title_id, preview_seconds, on_log):
        """Rip a short disposable preview clip for a single title."""
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        global_args = parse_cli_args(
            self.cfg.get("opt_makemkv_global_args", ""),
            on_log,
            "MakeMKV global args"
        )
        rip_args = parse_cli_args(
            self.cfg.get("opt_makemkv_rip_args", ""),
            on_log,
            "MakeMKV rip args"
        )
        os.makedirs(rip_path, exist_ok=True)
        self._purge_rip_target_files(rip_path, on_log)
        cmd = (
            [makemkvcon] + global_args +
            ["mkv", disc_target, str(title_id), rip_path] +
            RIP_ATTEMPT_FLAGS[0] + rip_args
        )
        return self._run_preview_process(cmd, preview_seconds, on_log)

    def _get_rip_attempts(self):
        """Resolve retry strategy flags based on config toggles."""
        count = int(self.cfg.get("opt_retry_attempts", 3))
        if not self.cfg.get("opt_auto_retry", True):
            count = 1
        return RIP_ATTEMPT_FLAGS[
            :max(1, min(count, len(RIP_ATTEMPT_FLAGS)))
        ]

    def rip_all_titles(self, rip_path, on_progress, on_log):
        """Rip all disc titles with retry flags and stall-aware process handling."""
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        global_args = parse_cli_args(
            self.cfg.get("opt_makemkv_global_args", ""),
            on_log,
            "MakeMKV global args"
        )
        rip_args = parse_cli_args(
            self.cfg.get("opt_makemkv_rip_args", ""),
            on_log,
            "MakeMKV rip args"
        )
        os.makedirs(rip_path, exist_ok=True)
        self._purge_rip_target_files(rip_path, on_log)
        attempts = self._get_rip_attempts()
        before   = self._snapshot_mkv_files(rip_path)

        for attempt_num, flags in enumerate(attempts, start=1):
            if self.abort_event.is_set():
                return False
            if attempt_num > 1:
                self._clean_new_mkv_files(rip_path, before, on_log)
                before = self._snapshot_mkv_files(rip_path)
            on_log(
                f"Rip attempt {attempt_num}/{len(attempts)} "
                f"(flags: {' '.join(flags)})"
            )
            cmd = (
                [makemkvcon] + global_args +
                ["mkv", disc_target, "all", rip_path] +
                flags + rip_args
            )
            success = self._run_rip_process(
                cmd, on_progress, on_log
            )
            if self.abort_event.is_set():
                return False
            if success:
                return True
            self._log_forced_failure_with_outputs(
                rip_path, before, on_log
            )
            on_log(f"Attempt {attempt_num} failed.")
            if attempt_num < len(attempts):
                on_log("Retrying with different settings...")

        on_log("All rip attempts failed.")
        return False

    def rip_selected_titles(self, rip_path, title_ids,
                            on_progress, on_log):
        """Rip selected title IDs with per-title retries and aggregated progress."""
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        global_args = parse_cli_args(
            self.cfg.get("opt_makemkv_global_args", ""),
            on_log,
            "MakeMKV global args"
        )
        rip_args = parse_cli_args(
            self.cfg.get("opt_makemkv_rip_args", ""),
            on_log,
            "MakeMKV rip args"
        )
        os.makedirs(rip_path, exist_ok=True)
        self._purge_rip_target_files(rip_path, on_log)
        on_log(
            f"Ripping {len(title_ids)} selected title(s) "
            f"to: {rip_path}"
        )
        attempts      = self._get_rip_attempts()
        failed_titles = []
        self.last_title_file_map = {}
        self.last_degraded_titles = []

        for idx, tid in enumerate(title_ids):
            if self.abort_event.is_set():
                on_log("Rip aborted.")
                return False, failed_titles

            on_log(
                f"Ripping title {tid+1} "
                f"({idx+1}/{len(title_ids)})..."
            )
            title_success = False
            before        = self._snapshot_mkv_files(rip_path)

            for attempt_num, flags in enumerate(attempts, start=1):
                if self.abort_event.is_set():
                    return False, failed_titles
                if attempt_num > 1:
                    self._clean_new_mkv_files(
                        rip_path, before, on_log
                    )
                    before = self._snapshot_mkv_files(rip_path)
                    on_log(
                        f"Retry attempt {attempt_num}/{len(attempts)}"
                        f" for title {tid+1} "
                        f"(flags: {' '.join(flags)})"
                    )
                cmd = (
                    [makemkvcon] + global_args +
                    ["mkv", disc_target, str(tid), rip_path] +
                    flags + rip_args
                )

                def scaled_progress(pct, _idx=idx):
                    overall = (
                        (_idx + pct / 100) / len(title_ids)
                    ) * 100
                    on_progress(int(overall))

                success = self._run_rip_process(
                    cmd, scaled_progress, on_log
                )
                if self.abort_event.is_set():
                    return False, failed_titles
                after = self._snapshot_mkv_files(rip_path)
                new_files = sorted(after - before)
                if success:
                    if new_files:
                        self.last_title_file_map[int(tid)] = list(new_files)
                    title_success = True
                    break
                if new_files:
                    # MakeMKV exited non-zero but produced output.
                    # Downstream stabilization and ffprobe will validate
                    # the actual file — classify as degraded here.
                    on_log(
                        f"Warning: MakeMKV reported errors for title "
                        f"{tid+1} but produced {len(new_files)} "
                        f"output file(s) — treating as degraded success."
                    )
                    self.last_title_file_map[int(tid)] = list(new_files)
                    self.last_degraded_titles.append(int(tid) + 1)
                    title_success = True
                    break
                on_log(
                    f"Attempt {attempt_num} failed "
                    f"for title {tid+1}."
                )
                if attempt_num < len(attempts):
                    on_log("Retrying with different settings...")

            if not title_success:
                on_log(
                    f"All attempts failed for title {tid+1}. "
                    f"Skipping."
                )
                failed_titles.append(tid + 1)

        on_progress(100)
        # Return True only when no abort AND every selected title succeeded.
        # Callers also run _normalize_rip_result (file-presence + ffprobe check)
        # as the authoritative gate, so this accurately reflects title-level success.
        all_ok = not self.abort_event.is_set() and not bool(failed_titles)
        return all_ok, failed_titles

    def analyze_files(self, mkv_files, on_log):
        """
        Analyze MKV files using ffprobe to get duration.
        Runs in parallel using ThreadPoolExecutor with automatic
        worker scaling (min(32, cpu_count+4)).

        Each worker kills its ffprobe process immediately on abort,
        preventing zombie processes. Results are collected in completion
        order, not submission order.

        Returns list of (filepath, duration_seconds, size_mb) tuples,
        sorted longest-first with unknowns appended at the end.
        """
        ffprobe = resolve_ffprobe(
            os.path.normpath(self.cfg["ffprobe_path"])
        )[0]
        abort   = self.abort_event
        results = []
        total   = len(mkv_files)

        def analyze_one(f):
            if abort.is_set():
                return None
            try:
                dur, mb = self._probe_file_duration_and_size(
                    f, ffprobe=ffprobe, honor_abort=True
                )
                return (f, dur, mb)
            except Exception:
                try:
                    mb = os.path.getsize(f) // (1024**2)
                except Exception:
                    mb = 0
                return (f, -1, mb)

        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(analyze_one, f) for f in mkv_files
            ]
            for i, future in enumerate(as_completed(futures), 1):
                if abort.is_set():
                    on_log("Analysis aborted.")
                    return []
                try:
                    res = future.result()
                except Exception:
                    res = None
                if res is not None:
                    results.append(res)
                    on_log(
                        f"Analyzed {i}/{total}: "
                        f"{os.path.basename(res[0])}"
                    )

        known   = [x for x in results if x[1] > 0]
        unknown = [x for x in results if x[1] <= 0]
        known.sort(key=lambda x: x[1], reverse=True)
        return known + unknown

    def _probe_file_duration_and_size(self, path, ffprobe=None, honor_abort=False):
        """Return (duration_seconds, size_mb) with metadata cache by mtime/size."""
        stat = os.stat(path)
        cache_key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
        cached = self._ffprobe_cache.get(cache_key)
        if cached is not None:
            return cached

        ffprobe_exe = ffprobe or resolve_ffprobe(
            os.path.normpath(self.cfg["ffprobe_path"])
        )[0]
        mb = stat.st_size // (1024**2)
        dur = -1.0
        proc = subprocess.Popen(
            [ffprobe_exe, "-v", "error", "-show_entries",
             "format=duration", "-of", "json", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_POPEN_FLAGS
        )
        while proc.poll() is None:
            if honor_abort and self.abort_event.is_set():
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
                return -1, mb
            time.sleep(0.05)
        out, _ = proc.communicate()
        try:
            data = json.loads(out)
            dur = float(data.get("format", {}).get("duration", -1) or -1)
        except Exception:
            dur = -1.0

        result = (dur, mb)
        self._ffprobe_cache[cache_key] = result
        return result

    def copy_with_abort(self, src, dst, buf_size=8 * 1024 * 1024):
        """Stream-copy a file while honoring abort requests between chunks."""
        use_fsync = self.cfg.get("opt_fsync", True)
        try:
            with open(self._io_path(src), "rb") as fsrc, open(self._io_path(dst), "wb") as fdst:
                while True:
                    if self.abort_event.is_set():
                        return False
                    chunk = fsrc.read(buf_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                fdst.flush()
                if use_fsync:
                    os.fsync(fdst.fileno())
            return True
        except Exception as e:
            self.last_move_error = f"Copy failed: {e}"
            return False

    def _quick_ffprobe_ok(self, path, on_log):
        """Fast container integrity check: ffprobe must return duration > 0."""
        try:
            ffprobe = resolve_ffprobe(
                os.path.normpath(self.cfg["ffprobe_path"])
            )[0]
            duration, _mb = self._probe_file_duration_and_size(
                path, ffprobe=ffprobe, honor_abort=False
            )
            if duration <= 0:
                on_log(
                    "ERROR: ffprobe duration invalid for "
                    f"{os.path.basename(path)}"
                )
                return False
            return True
        except Exception as e:
            on_log(
                "ERROR: ffprobe integrity check failed for "
                f"{os.path.basename(path)}: {e}"
            )
            return False

    def move_file_atomic(self, source, final_path, on_log):
        """
        Move a file safely using copy+rename (atomic move).
        Preserves timestamps via shutil.copystat.
        Falls back to direct shutil.move if opt_atomic_move is off.
        Cleans up .partial file on abort or failure.
        REQUIRES: Source must be fully written (verified by move start check).
        """
        self.last_move_error = ""
        io_source = self._io_path(source)

        if not os.path.exists(io_source):
            on_log(f"Missing file: {source}")
            self.last_move_error = "Move failed — source file is missing."
            return False

        # Verify source has stopped growing before accepting move.
        try:
            size_before = os.path.getsize(io_source)
            time.sleep(1.0)
            size_after = os.path.getsize(io_source)
            if size_before != size_after:
                on_log(
                    f"ERROR: Source file still growing before move "
                    f"({size_before} -> {size_after} bytes). "
                    f"Stabilization failed."
                )
                self.last_move_error = (
                    "Move failed — source file incomplete. "
                    "Stabilization did not complete successfully."
                )
                return False
        except Exception as e:
            on_log(f"ERROR checking source stability: {e}")
            return False

        if os.path.exists(final_path):
            final_path = self.unique_path(final_path)
            on_log(
                f"Destination exists. Using unique path: {final_path}"
            )

        verify_retries = max(
            1, int(self.cfg.get("opt_move_verify_retries", 5))
        )

        def wait_for_size_match(src_size, dst_path):
            last_size = -1
            for _ in range(verify_retries):
                if os.path.exists(dst_path):
                    last_size = os.path.getsize(dst_path)
                    if last_size == src_size:
                        return True, last_size
                if self.abort_event.is_set():
                    break
                time.sleep(1.0)
            return False, last_size

        if not self.cfg.get("opt_atomic_move", True):
            try:
                io_final_path = self._io_path(final_path)
                src_size = os.path.getsize(io_source)
                shutil.move(io_source, io_final_path)
                if not os.path.exists(io_final_path):
                    on_log("ERROR: destination missing after move.")
                    self.last_move_error = (
                        "Move failed — destination file missing after move."
                    )
                    return False
                size_ok, dst_size = wait_for_size_match(
                    src_size, io_final_path
                )
                if not size_ok:
                    on_log(
                        "ERROR: destination size mismatch after move "
                        f"(src={src_size} bytes, dst={dst_size} bytes) "
                        f"after {verify_retries} verification check(s)."
                    )
                    self.last_move_error = (
                        "Move failed — network write mismatch. "
                        "Destination size did not match source."
                    )
                    return False
                if not self._quick_ffprobe_ok(io_final_path, on_log):
                    self.last_move_error = (
                        "Move failed — destination file failed integrity "
                        "probe (ffprobe)."
                    )
                    return False
                return True
            except Exception as e:
                on_log(f"ERROR moving file: {e}")
                return False

        temp_dest = final_path + ".partial"
        io_temp_dest = self._io_path(temp_dest)
        io_final_path = self._io_path(final_path)
        try:
            ok = self.copy_with_abort(source, temp_dest)
            if not ok or self.abort_event.is_set():
                if os.path.exists(io_temp_dest):
                    try:
                        os.remove(io_temp_dest)
                    except Exception:
                        pass
                on_log("Move aborted — partial file removed.")
                self.last_move_error = "Move failed — operation aborted."
                return False
            try:
                shutil.copystat(io_source, io_temp_dest)
            except Exception:
                pass
            if os.path.exists(io_final_path):
                new_final = self.unique_path(final_path)
                on_log(
                    "Destination appeared during move; "
                    f"using unique path: {new_final}"
                )
                final_path = new_final
                io_final_path = self._io_path(final_path)
            try:
                os.replace(io_temp_dest, io_final_path)
            except OSError:
                # Cross-volume fallback when atomic rename is unavailable.
                shutil.move(io_temp_dest, io_final_path)
            if os.path.exists(io_final_path):
                src_size = os.path.getsize(io_source)
                size_ok, dst_size = wait_for_size_match(
                    src_size, io_final_path
                )
                if not size_ok:
                    on_log(
                        "ERROR: destination size mismatch after move "
                        f"(src={src_size} bytes, dst={dst_size} bytes). "
                        f"after {verify_retries} verification check(s). "
                        "Source file retained."
                    )
                    self.last_move_error = (
                        "Move failed — network write mismatch. "
                        "Destination size did not match source."
                    )
                    return False
                if not self._quick_ffprobe_ok(io_final_path, on_log):
                    self.last_move_error = (
                        "Move failed — destination file failed integrity "
                        "probe (ffprobe)."
                    )
                    return False
                os.remove(io_source)
            else:
                on_log("ERROR: destination missing after move.")
                self.last_move_error = (
                    "Move failed — destination file missing after move."
                )
                return False
            return True
        except Exception as e:
            if os.path.exists(io_temp_dest):
                try:
                    os.remove(io_temp_dest)
                except Exception:
                    pass
            on_log(f"ERROR moving file: {e}")
            self.last_move_error = f"Move failed — {e}"
            return False

    def move_files(self, titles_list, main_indices, episode_numbers,
                   real_names, extra_indices, is_tv, title, dest_folder,
                   extras_folder, season, year, extra_counter,
                   on_progress, on_log):
        """Move selected main/extras files into final library structure.

        extra_indices: None = keep all non-main as extras,
                       []   = keep no extras,
                       [i]  = keep only those absolute indices as extras.
        """
        _main_set    = set(main_indices)
        _extras_list = (
            [i for i in range(len(titles_list)) if i not in _main_set]
            if extra_indices is None
            else list(extra_indices)
        )
        total_to_move = len(main_indices) + len(_extras_list)
        moved = 0
        moved_paths = []

        selected_size = sum(
            os.path.getsize(titles_list[i][0]) for i in main_indices
        )
        if _extras_list:
            selected_size += sum(
                os.path.getsize(titles_list[i][0]) for i in _extras_list
            )

        if self.cfg.get("opt_check_dest_space", True):
            on_log("Checking destination drive space...")
            try:
                status, free, required = self.check_disk_space(
                    dest_folder, selected_size, on_log
                )
                if status == "block":
                    on_log(
                        f"ERROR: Critically low space on destination "
                        f"({free / (1024**3):.1f} GB free). "
                        f"Cannot proceed."
                    )
                    return False, extra_counter, moved_paths
            except Exception as e:
                on_log(
                    f"Warning: could not check destination space: {e}"
                )

        try:
            for idx, i in enumerate(main_indices):
                if self.abort_event.is_set():
                    on_log("Move aborted by user.")
                    return False, extra_counter, moved_paths

                source = titles_list[i][0]
                if is_tv:
                    ep_num  = episode_numbers[idx]
                    ep_name = clean_name(
                        real_names[idx] if idx < len(real_names)
                        else f"Episode {ep_num:02d}"
                    )
                    name = (
                        f"{clean_name(title)} - "
                        f"S{season:02d}E{ep_num:02d} - {ep_name}.mkv"
                    )
                else:
                    name = f"{clean_name(title)} ({year}).mkv"

                final_path = self.unique_path(
                    os.path.join(dest_folder, name)
                )
                on_log(f"Moving: {os.path.basename(source)}")
                on_log(f"    To: {final_path}")
                ok = self.move_file_atomic(source, final_path, on_log)
                if not ok:
                    return False, extra_counter, moved_paths

                moved += 1
                moved_paths.append(final_path)
                on_progress(int(moved / total_to_move * 100))
                on_log(f"Done: {os.path.basename(final_path)}")

            for i in _extras_list:
                if self.abort_event.is_set():
                    on_log("Move aborted by user.")
                    return False, extra_counter, moved_paths
                old_file, dur, mb = titles_list[i]
                if is_tv:
                    name = (
                        f"{clean_name(title)} - "
                        f"S{season:02d}E00 - "
                        f"Ex{extra_counter}.mkv"
                    )
                else:
                    name = (
                        f"{clean_name(title)} ({year}) "
                        f"- Ex{extra_counter}.mkv"
                    )
                final_path = self.unique_path(
                    os.path.join(extras_folder, name)
                )
                extra_counter += 1
                on_log(
                    f"Moving extra: "
                    f"{os.path.basename(old_file)}"
                )
                ok = self.move_file_atomic(
                    old_file, final_path, on_log
                )
                if not ok:
                    return False, extra_counter, moved_paths
                moved += 1
                moved_paths.append(final_path)
                on_progress(
                    int(moved / total_to_move * 100)
                )
                on_log(
                    f"Done: {os.path.basename(final_path)}"
                )

            on_log(f"All files moved. {moved} file(s) total.")
            return True, extra_counter, moved_paths

        except Exception as e:
            on_log(f"ERROR during move: {e}")
            on_log(
                "Check temp folder — "
                "some files may not have moved."
            )
            return False, extra_counter, moved_paths

    def write_session_log(self, log_file, start_time,
                          session_log, on_log):
        """Append session logs to disk with rollover for oversized log files."""
        if not log_file:
            on_log("No log file configured — session log not saved.")
            return
        try:
            # Ensure log file has .txt extension
            if not log_file.lower().endswith(('.txt', '.log')):
                log_file = log_file + '.txt'
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(self._io_path(log_dir), exist_ok=True)
            max_size = 5 * 1024**3
            io_log_file = self._io_path(log_file)
            if (os.path.exists(io_log_file) and
                    os.path.getsize(io_log_file) >= max_size):
                with open(io_log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                start_date = lines[0][:10] if lines else "unknown"
                end_date   = lines[-1][:10] if lines else "unknown"
                old_name = (
                    f"rip_log_{start_date}_to_{end_date}.txt"
                )
                shutil.move(
                    io_log_file, self._io_path(os.path.join(log_dir, old_name))
                )
            with open(io_log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(
                    f"Session: "
                    f"{start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                f.write(f"{'='*60}\n")
                for line in session_log:
                    f.write(line + "\n")
                f.write(f"{'='*60}\n")
            on_log(f"Session log written to: {log_file}")
        except Exception as e:
            on_log(f"Warning: could not write log: {e}")


# ==========================================
# LAYER 2 — CONTROLLER
# ==========================================


__all__ = ["RipperEngine"]
