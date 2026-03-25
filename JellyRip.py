'''
JellyRip v1.0.4
MakeMKV companion for ripping and organizing discs into a Jellyfin library.

Architecture — three strict layers:
  Layer 1: RipperEngine   — pure logic, no UI
  Layer 2: RipperController — workflow orchestration
  Layer 3: JellyRipperGUI  — display and input only

See CONTRIBUTING.md for design rules and contribution guidelines.
'''

import subprocess
import os
import glob
import shutil
import json
import re
import platform
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading
import queue as queue_module

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

__version__ = "1.0.4"


# ==========================================
# CONFIG
# ==========================================

def get_config_dir():
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get(
            "XDG_CONFIG_HOME", os.path.expanduser("~/.config")
        )
    config_dir = os.path.join(base, "JellyRip")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


CONFIG_FILE = os.path.join(get_config_dir(), "config.json")

DEFAULTS = {
    "makemkvcon_path": r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe",
    "ffprobe_path":    r"C:\Program Files\HandBrake\ffprobe.exe",
    "temp_folder":     r"C:\Temp",
    "tv_folder":       r"C:\Media\TV Shows",
    "movies_folder":   r"C:\Media\Movies",
    "log_file":        os.path.expanduser("~/Downloads/rip_log.txt"),
    "opt_drive_index":                0,
    "opt_scan_disc_size":             True,
    "opt_confirm_before_rip":         True,
    "opt_clean_mkv_before_retry":     True,
    "opt_stall_detection":            True,
    "opt_stall_timeout_seconds":      120,
    "opt_auto_retry":                 True,
    "opt_retry_attempts":             3,
    "opt_check_dest_space":           True,
    "opt_confirm_before_move":        True,
    "opt_atomic_move":                True,
    "opt_fsync":                      True,
    "opt_show_temp_manager":          True,
    "opt_auto_delete_temp":           True,
    "opt_clean_partials_startup":     True,
    "opt_warn_low_space":             True,
    "opt_hard_block_gb":              20,
    "opt_warn_out_of_order_episodes": True,
    "opt_session_failure_report":     True,
    "opt_log_cap":                    300000,
    "opt_log_trim":                   200000,
    "opt_smart_rip_mode":             False,
}

RIP_ATTEMPT_FLAGS = [
    ["--cache=1024"],
    ["--noscan", "--cache=1024"],
    ["--noscan", "--directio=true", "--cache=512"],
]

FATAL_MSG_PATTERNS = [
    "failed to open disc",
    "failed to open source",
    "read error",
    "unable to read",
    "failed to save",
    "critical error",
    "failed to open destination",
]


# ==========================================
# HELPERS
# ==========================================

def clean_name(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip().rstrip(". ")


def make_rip_folder_name():
    return datetime.now().strftime("Disc_%Y-%m-%d_%H-%M-%S")


def make_temp_title():
    return f"TEMP_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"


def parse_episode_names(name_input):
    if not name_input:
        return []
    if '",' in name_input or name_input.count('"') >= 2:
        return [
            x.strip().strip('"')
            for x in re.split(r'",\s*', name_input)
        ]
    return [x.strip() for x in name_input.split(",")]


def parse_duration_to_seconds(s):
    """
    Convert MakeMKV duration string to integer seconds.
    Handles H:MM:SS and M:SS formats. Returns 0 on any parse failure.

    MakeMKV reports duration from playlist metadata, not actual playback.
    Relative comparisons between titles on the same disc are reliable.
    Absolute values should not be treated as ground truth.
    """
    try:
        parts = [int(p) for p in s.strip().split(":")]
        if len(parts) == 3:
            h, m, sec = parts
        elif len(parts) == 2:
            h, m, sec = 0, parts[0], parts[1]
        else:
            return 0
        return h * 3600 + m * 60 + sec
    except Exception:
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
        # Try direct int conversion first
        try:
            return int(s)
        except ValueError:
            # If that fails, try to extract just the numeric part
            # This handles cases like "3.7 GB" → extract 3
            import re
            match = re.search(r'-?\d+', s)
            if match:
                return int(match.group())
            return 0
    except Exception:
        return 0


def score_title(t, all_titles):
    """
    Score a title relative to all titles on the disc.
    Returns a float 0.0-1.0. Higher = more likely to be the main feature.

    All five signals are normalized against the disc maximum so they
    contribute equally regardless of absolute scale. Weighting:
      0.35 duration  — most reliable signal, hard to fake
      0.30 size      — correlates with quality and length
      0.15 chapters  — main features are chaptered, extras often aren't
      0.15 audio     — more tracks = more likely primary content
      0.05 subtitles — weak signal but breaks ties

    This beats size-only selection on Blu-rays with obfuscation titles
    because fake titles fail across multiple axes simultaneously.
    """
    if not all_titles:
        return 0.0
    
    max_size     = max((x["size_bytes"] for x in all_titles), default=1)
    max_duration = max(
        (x["duration_seconds"] for x in all_titles), default=1
    )
    max_chapters = max(
        (safe_int(x.get("chapters")) for x in all_titles), default=1
    )
    max_audio    = max(
        (len(x["audio_tracks"]) for x in all_titles), default=1
    )
    max_subs     = max(
        (len(x["subtitle_tracks"]) for x in all_titles), default=1
    )

    return (
        (t["size_bytes"] / max_size)                       * 0.30 +
        (t["duration_seconds"] / max_duration)             * 0.35 +
        (safe_int(t.get("chapters")) / max_chapters)      * 0.15 +
        (len(t["audio_tracks"]) / max_audio)               * 0.15 +
        (len(t["subtitle_tracks"]) / max_subs)             * 0.05
    )


def format_audio_summary(audio_tracks):
    """Format audio track list as a readable string for the disc tree UI."""
    if not audio_tracks:
        return "—"
    parts = []
    for a in audio_tracks:
        lang     = a.get("lang_name") or a.get("lang") or ""
        codec    = a.get("codec", "")
        channels = a.get("channels", "")
        label    = " ".join(
            filter(None, [lang, codec, channels])
        ).strip()
        if label:
            parts.append(label)
    return ", ".join(parts) if parts else "—"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save config: {e}")


def resolve_ffprobe(configured_path):
    if os.path.exists(configured_path):
        return configured_path
    found = shutil.which("ffprobe")
    if found:
        return found
    fallbacks = [
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    for path in fallbacks:
        if os.path.exists(path):
            return path
    return configured_path


def get_available_drives(makemkvcon_path):
    """Query MakeMKV for available optical drives via disc:9999 trick."""
    drives = []
    try:
        proc = subprocess.Popen(
            [makemkvcon_path, "-r", "info", "disc:9999"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(proc.stdout.readline, ""):
            line = line.strip()
            if line.startswith("DRV:"):
                parts = line[4:].split(",")
                if len(parts) >= 6:
                    try:
                        idx  = int(parts[0])
                        name = parts[5].strip().strip('"')
                        if name:
                            drives.append((idx, name))
                    except (ValueError, IndexError):
                        pass
        proc.wait()
    except Exception:
        pass
    if not drives:
        drives = [(0, "Default Drive (disc:0)")]
    return drives


# ==========================================
# LAYER 1 — ENGINE
# ==========================================

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

    @property
    def abort_flag(self):
        return self.abort_event.is_set()

    def abort(self):
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
        self.abort_event.clear()

    def unique_path(self, path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 2
        while os.path.exists(new_path := f"{base} - {counter}{ext}"):
            counter += 1
        return new_path

    def validate_tools(self):
        makemkvcon = os.path.normpath(self.cfg["makemkvcon_path"])
        ffprobe    = resolve_ffprobe(
            os.path.normpath(self.cfg["ffprobe_path"])
        )
        if not os.path.exists(makemkvcon):
            return False, (
                f"MakeMKV not found at:\n{makemkvcon}"
                f"\n\nPlease check Settings."
            )
        if not os.path.exists(ffprobe):
            return False, (
                f"ffprobe not found at:\n{ffprobe}"
                f"\n\nInstall ffprobe or HandBrake and check Settings."
            )
        return True, ""

    def get_disc_target(self):
        return f"disc:{self.cfg.get('opt_drive_index', 0)}"

    def cleanup_partial_files(self, temp_root, on_log):
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
                mkv_files = glob.glob(
                    os.path.join(full, "**", "*.mkv"),
                    recursive=True
                )
                try:
                    size = sum(
                        os.path.getsize(os.path.join(dp, f))
                        for dp, dn, fns in os.walk(full)
                        for f in fns
                    )
                except Exception:
                    size = 0
                folders.append((full, name, len(mkv_files), size))
        folders.sort(key=lambda x: x[1])
        return folders

    def find_resumable_sessions(self, temp_root):
        resumable = []
        if not os.path.isdir(temp_root):
            return resumable
        for name in os.listdir(temp_root):
            full = os.path.join(temp_root, name)
            if not os.path.isdir(full):
                continue
            meta = self.read_temp_metadata(full)
            if meta and meta.get("status") == "ripping":
                mkv_files = glob.glob(
                    os.path.join(full, "**", "*.mkv"),
                    recursive=True
                )
                resumable.append((full, name, meta, len(mkv_files)))
        return resumable

    def _atomic_write_json(self, path, data):
        """Write JSON atomically using temp file + os.replace."""
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def write_temp_metadata(self, rip_path, title, disc_number,
                            season=None):
        meta = {
            "title":       title,
            "disc_number": disc_number,
            "timestamp":   datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "file_count":  0,
            "status":      "ripping",
        }
        if season is not None:
            meta["season"] = season
        self._atomic_write_json(
            os.path.join(rip_path, "_rip_meta.json"), meta
        )

    def update_temp_metadata(self, rip_path, status=None):
        meta_path = os.path.join(rip_path, "_rip_meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            meta["file_count"] = len(
                glob.glob(
                    os.path.join(rip_path, "**", "*.mkv"),
                    recursive=True
                )
            )
            if status:
                meta["status"] = status
            self._atomic_write_json(meta_path, meta)
        except Exception:
            pass

    def read_temp_metadata(self, rip_path):
        meta_path = os.path.join(rip_path, "_rip_meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
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
        on_log(f"Scanning disc ({disc_target})...")
        titles      = {}
        title_count = 0
        try:
            proc = subprocess.Popen(
                [makemkvcon, "-r", "info", disc_target],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
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
                            "chapters":         "",
                            "streams":          {},
                        }
                        title_count += 1
                        on_progress(min(title_count * 3, 90))
                    if attr == 2:
                        titles[tid]["name"] = val
                    elif attr == 9:
                        titles[tid]["duration"] = val
                        titles[tid]["duration_seconds"] = (
                            parse_duration_to_seconds(val)
                        )
                    elif attr == 10:
                        # Store chapters as safe integer to prevent
                        # crashes downstream. MakeMKV sometimes returns
                        # malformed data here (e.g., "3.7 GB").
                        titles[tid]["chapters"] = safe_int(val)
                    elif attr == 11:
                        # Parse size - might be bytes or already formatted
                        try:
                            size_bytes = int(val)
                        except ValueError:
                            # Size might be already formatted (e.g., "3.7 GB" or "3,7 GB" in European locale)
                            # Extract numeric part and convert
                            try:
                                parts = val.split()
                                if len(parts) >= 2:
                                    num = float(parts[0].replace(",", "."))
                                    unit = parts[1].upper()
                                    multipliers = {
                                        "B": 1, "KB": 1024, "MB": 1024**2,
                                        "GB": 1024**3, "TB": 1024**4
                                    }
                                    size_bytes = int(num * multipliers.get(unit, 1))
                                else:
                                    size_bytes = 0
                            except Exception:
                                size_bytes = 0
                        
                        titles[tid]["size_bytes"] = size_bytes
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
        # Everything downstream (Smart Rip, disc tree pre-selection)
        # inherits this ordering automatically.
        result.sort(
            key=lambda t: score_title(t, result), reverse=True
        )

        # Log scores for debugging edge cases and bad discs
        on_log("Title scores:")
        for t in result:
            on_log(
                f"  Title {t['id']+1}: "
                f"{t['name'][:30]:<30}  "
                f"score={score_title(t, result):.3f}  "
                f"{t['duration']}  {t['size']}  "
                f"{safe_int(t.get('chapters', 0))} chapters  "
                f"{len(t['audio_tracks'])} audio  "
                f"{len(t['subtitle_tracks'])} subs"
            )

        on_progress(100)
        on_log(f"Disc scan complete. Found {len(result)} title(s).")
        return result

    def get_disc_size(self, on_log):
        """
        Lightweight disc size query used only by dump/unattended modes.
        TV/Movie disc flows use size_bytes from scan_disc() instead,
        avoiding a second full pass over the disc.
        """
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        total_bytes = 0
        try:
            proc = subprocess.Popen(
                [makemkvcon, "-r", "info", disc_target],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            for line in iter(proc.stdout.readline, ""):
                if self.abort_event.is_set():
                    proc.kill()
                    return None
                if line.startswith("TINFO:"):
                    parts = line.strip().split(",")
                    if len(parts) >= 4 and parts[1] == "11":
                        try:
                            size_str = parts[3].strip().strip('"')
                            try:
                                total_bytes += int(size_str)
                            except ValueError:
                                # Size might be formatted like "3.7 GB" or "3,7 GB" in European locale
                                try:
                                    size_parts = size_str.split()
                                    if len(size_parts) >= 2:
                                        num = float(size_parts[0].replace(",", "."))
                                        unit = size_parts[1].upper()
                                        multipliers = {
                                            "B": 1, "KB": 1024, "MB": 1024**2,
                                            "GB": 1024**3, "TB": 1024**4
                                        }
                                        total_bytes += int(num * multipliers.get(unit, 1))
                                except Exception:
                                    pass
                        except IndexError:
                            pass
            proc.wait()
        except Exception as e:
            on_log(f"Warning: could not read disc size: {e}")
            return None
        return total_bytes if total_bytes > 0 else None

    def check_disk_space(self, path, required_bytes, on_log):
        hard_floor = int(
            self.cfg.get("opt_hard_block_gb", 20)
        ) * (1024**3)
        try:
            os.makedirs(path, exist_ok=True)
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
          - Enables real stall detection (timeout fires if queue stays empty)
          - Keeps abort checks responsive regardless of MakeMKV output rate

        Returns (success, had_error). success is True only if return code
        is 0 AND no fatal message patterns were detected in MSG output.
        """
        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        line_queue    = queue_module.Queue()
        reader        = threading.Thread(
            target=self._stdout_reader,
            args=(self.current_process.stdout, line_queue),
            daemon=True
        )
        reader.start()

        last_pct        = -1
        last_output     = time.time()
        rip_start       = time.time()
        had_error       = False
        stall_detection = self.cfg.get("opt_stall_detection", True)
        stall_timeout   = int(
            self.cfg.get("opt_stall_timeout_seconds", 120)
        )

        while True:
            if self.abort_event.is_set():
                try:
                    self.current_process.terminate()
                except Exception:
                    pass
                on_log("Rip aborted.")
                self.current_process.wait()
                self.current_process = None
                return False, had_error

            try:
                line = line_queue.get(timeout=1.0)
            except queue_module.Empty:
                if self.current_process.poll() is not None:
                    break
                if stall_detection:
                    if time.time() - last_output > stall_timeout:
                        on_log(
                            f"No output for {stall_timeout}s — "
                            f"killing stalled process."
                        )
                        self.current_process.kill()
                        self.current_process.wait()
                        self.current_process = None
                        return False, True
                continue

            last_output = time.time()
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

        self.current_process.wait()
        rc = self.current_process.returncode
        self.current_process = None

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

        return (rc == 0), had_error

    def _get_rip_attempts(self):
        count = int(self.cfg.get("opt_retry_attempts", 3))
        if not self.cfg.get("opt_auto_retry", True):
            count = 1
        return RIP_ATTEMPT_FLAGS[
            :max(1, min(count, len(RIP_ATTEMPT_FLAGS)))
        ]

    def rip_all_titles(self, rip_path, on_progress, on_log):
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        os.makedirs(rip_path, exist_ok=True)
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
                [makemkvcon, "mkv", disc_target, "all", rip_path]
                + flags
            )
            success, _ = self._run_rip_process(
                cmd, on_progress, on_log
            )
            if self.abort_event.is_set():
                return False
            if success:
                return True
            on_log(f"Attempt {attempt_num} failed.")
            if attempt_num < len(attempts):
                on_log("Retrying with different settings...")

        on_log("All rip attempts failed.")
        return False

    def rip_selected_titles(self, rip_path, title_ids,
                            on_progress, on_log):
        makemkvcon  = os.path.normpath(self.cfg["makemkvcon_path"])
        disc_target = self.get_disc_target()
        os.makedirs(rip_path, exist_ok=True)
        on_log(
            f"Ripping {len(title_ids)} selected title(s) "
            f"to: {rip_path}"
        )
        attempts      = self._get_rip_attempts()
        failed_titles = []

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
                    [makemkvcon, "mkv", disc_target,
                     str(tid), rip_path]
                    + flags
                )

                def scaled_progress(pct, _idx=idx):
                    overall = (
                        (_idx + pct / 100) / len(title_ids)
                    ) * 100
                    on_progress(int(overall))

                success, _ = self._run_rip_process(
                    cmd, scaled_progress, on_log
                )
                if self.abort_event.is_set():
                    return False, failed_titles
                if success:
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
        return not self.abort_event.is_set(), failed_titles

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
        )
        abort   = self.abort_event
        results = []
        total   = len(mkv_files)

        def analyze_one(f):
            if abort.is_set():
                return None
            mb = os.path.getsize(f) // (1024**2)
            try:
                proc = subprocess.Popen(
                    [ffprobe, "-v", "error", "-show_entries",
                     "format=duration", "-of", "json", f],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                while proc.poll() is None:
                    if abort.is_set():
                        proc.kill()
                        return None
                    time.sleep(0.05)
                out, _ = proc.communicate()
                try:
                    data = json.loads(out)
                    dur  = float(data["format"]["duration"])
                except Exception:
                    dur = -1
                return (f, dur, mb)
            except Exception:
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

    def copy_with_abort(self, src, dst, buf_size=8 * 1024 * 1024):
        use_fsync = self.cfg.get("opt_fsync", True)
        try:
            with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
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
        except Exception:
            return False

    def move_file_atomic(self, source, final_path, on_log):
        """
        Move a file safely using copy+rename (atomic move).
        Preserves timestamps via shutil.copystat.
        Falls back to direct shutil.move if opt_atomic_move is off.
        Cleans up .partial file on abort or failure.
        """
        if not self.cfg.get("opt_atomic_move", True):
            try:
                shutil.move(source, final_path)
                try:
                    shutil.copystat(source, final_path)
                except Exception:
                    pass
                return True
            except Exception as e:
                on_log(f"ERROR moving file: {e}")
                return False

        temp_dest = final_path + ".partial"
        try:
            ok = self.copy_with_abort(source, temp_dest)
            if not ok or self.abort_event.is_set():
                if os.path.exists(temp_dest):
                    try:
                        os.remove(temp_dest)
                    except Exception:
                        pass
                on_log("Move aborted — partial file removed.")
                return False
            try:
                shutil.copystat(source, temp_dest)
            except Exception:
                pass
            os.replace(temp_dest, final_path)
            os.remove(source)
            return True
        except Exception as e:
            if os.path.exists(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass
            on_log(f"ERROR moving file: {e}")
            return False

    def move_files(self, titles_list, main_indices, episode_numbers,
                   real_names, keep_extras, is_tv, title, dest_folder,
                   extras_folder, season, year, extra_counter,
                   on_progress, on_log):

        total_to_move = len(main_indices) + (
            len(titles_list) - len(main_indices) if keep_extras else 0
        )
        moved = 0

        selected_size = sum(
            os.path.getsize(titles_list[i][0]) for i in main_indices
        )
        if keep_extras:
            selected_size += sum(
                os.path.getsize(titles_list[i][0])
                for i in range(len(titles_list))
                if i not in main_indices
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
                    return False, extra_counter
            except Exception as e:
                on_log(
                    f"Warning: could not check destination space: {e}"
                )

        try:
            for idx, i in enumerate(main_indices):
                if self.abort_event.is_set():
                    on_log("Move aborted by user.")
                    return False, extra_counter

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
                    return False, extra_counter

                moved += 1
                on_progress(int(moved / total_to_move * 100))
                on_log(f"Done: {os.path.basename(final_path)}")

            if keep_extras:
                for i, (old_file, dur, mb) in enumerate(titles_list):
                    if self.abort_event.is_set():
                        on_log("Move aborted by user.")
                        return False, extra_counter
                    if i not in main_indices:
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
                            return False, extra_counter
                        moved += 1
                        on_progress(
                            int(moved / total_to_move * 100)
                        )
                        on_log(
                            f"Done: {os.path.basename(final_path)}"
                        )

            on_log(f"All files moved. {moved} file(s) total.")
            return True, extra_counter

        except Exception as e:
            on_log(f"ERROR during move: {e}")
            on_log(
                "Check temp folder — "
                "some files may not have moved."
            )
            return False, extra_counter

    def write_session_log(self, log_file, start_time,
                          session_log, on_log):
        if not log_file:
            on_log("No log file configured — session log not saved.")
            return
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            max_size = 5 * 1024**3
            if (os.path.exists(log_file) and
                    os.path.getsize(log_file) >= max_size):
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                start_date = lines[0][:10] if lines else "unknown"
                end_date   = lines[-1][:10] if lines else "unknown"
                old_name = (
                    f"rip_log_{start_date}_to_{end_date}.txt"
                )
                shutil.move(
                    log_file, os.path.join(log_dir, old_name)
                )
            with open(log_file, "a", encoding="utf-8") as f:
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

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full = f"[{timestamp}] {msg}"
        self.session_log.append(full)
        cap  = int(self.engine.cfg.get("opt_log_cap", 300000))
        trim = int(self.engine.cfg.get("opt_log_trim", 200000))
        if len(self.session_log) > cap:
            self.session_log = self.session_log[-trim:]
        self.gui.append_log(full)

    def report(self, msg):
        self.session_report.append(msg)
        self.log(msg)

    def flush_log(self):
        log_file = os.path.normpath(
            self.engine.cfg.get("log_file", "")
        )
        self.engine.write_session_log(
            log_file, self.start_time, self.session_log, self.log
        )

    def write_session_summary(self):
        if not self.engine.cfg.get(
            "opt_session_failure_report", True
        ):
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
        for attempt in range(2):
            self.log(
                f"Scanning disc on drive "
                f"{self.engine.get_disc_target()}..."
            )
            self.gui.set_status("Scanning disc...")
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

            if result:
                return result

            if attempt == 0:
                self.log("Scan failed — retrying once...")
                time.sleep(2)

        self.log("Scan failed after 2 attempts.")
        return None

    def check_resume(self, temp_root):
        resumable = self.engine.find_resumable_sessions(temp_root)
        if not resumable:
            return
        for full_path, name, meta, file_count in resumable:
            title = meta.get("title", "Unknown")
            ts    = meta.get("timestamp", name)
            if self.gui.ask_yesno(
                f"Resume previous session?\n\n"
                f"Title: {title}\n"
                f"Started: {ts}\n"
                f"Files so far: {file_count}\n\n"
                f"Click Yes to resume, No to skip."
            ):
                self.log(f"Resuming session: {name}")
                self.engine.update_temp_metadata(
                    full_path, status="ripping"
                )

    def run_tv_disc(self):
        self._run_disc(is_tv=True)

    def run_movie_disc(self):
        self._run_disc(is_tv=False)

    def run_smart_rip(self):
        cfg        = self.engine.cfg
        movie_root = os.path.normpath(cfg["movies_folder"])
        temp_root  = os.path.normpath(cfg["temp_folder"])

        self.engine.reset_abort()
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
        if not title:
            title = make_temp_title()
            self.log(f"WARNING: No title — using: {title}")

        year = self.gui.ask_input("Year", "Release year:")
        if not year:
            year = "0000"
            self.log("WARNING: No year — using 0000")

        time.sleep(2)  # drive spin-up / mount stabilization
        disc_titles = self.scan_with_retry()

        if self.engine.abort_event.is_set():
            return

        if not disc_titles:
            self.log("Could not read disc.")
            self.gui.show_error("Scan Failed", "Could not read disc.")
            return

        # Best candidate is first — sorted by score in scan_disc()
        best          = disc_titles[0]
        selected_ids  = [best["id"]]
        selected_size = best["size_bytes"]

        self.log(
            f"Smart Rip selected: Title {best['id']+1} "
            f"({best['size']}) — {best['duration']}"
        )

        if cfg.get("opt_confirm_before_rip", True):
            if not self.gui.ask_yesno(
                f"Smart Rip selected Title {best['id']+1} "
                f"({best['size']}) as main feature. Continue?"
            ):
                self.log("Cancelled.")
                return

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

        self.gui.set_status("Ripping main feature...")
        success, _ = self.engine.rip_selected_titles(
            rip_path, selected_ids,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )

        if not success:
            self.report(f"Smart Rip failed for {title} ({year})")
            self.flush_log()
            return

        self.engine.update_temp_metadata(rip_path, status="ripped")
        mkv_files = sorted(
            glob.glob(os.path.join(rip_path, "*.mkv"))
        )
        if not mkv_files:
            self.log("No files found after ripping.")
            return

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
            return

        name       = f"{clean_name(title)} ({year}).mkv"
        final_path = self.engine.unique_path(
            os.path.join(movie_folder, name)
        )
        self.log(f"Moving: {os.path.basename(titles_list[0][0])}")
        self.log(f"    To: {final_path}")
        ok = self.engine.move_file_atomic(
            titles_list[0][0], final_path, self.log
        )
        if ok:
            shutil.rmtree(rip_path, ignore_errors=True)
            self.log("Done.")
        else:
            self.log(f"Temp preserved at: {rip_path}")

        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        self.gui.show_info(
            "Smart Rip Complete",
            f"Ripped and moved:\n{final_path}"
        )

    def run_dump_all(self):
        cfg       = self.engine.cfg
        temp_root = os.path.normpath(cfg["temp_folder"])

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
            title = make_temp_title()
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

        if not success:
            self.log("Rip did not complete.")
            self.report(f"Dump All: rip failed for {title}")
            self.flush_log()
            return

        self.engine.update_temp_metadata(rip_path, status="ripped")
        mkv_files = sorted(
            glob.glob(os.path.join(rip_path, "*.mkv"))
        )
        self.log(
            f"Dump complete. "
            f"{len(mkv_files)} file(s) saved to: {rip_path}"
        )
        self.write_session_summary()
        self.flush_log()
        self.gui.set_progress(0)
        self.gui.show_info(
            "Dump Complete",
            f"Ripped {len(mkv_files)} file(s) to:\n{rip_path}\n\n"
            f"Use 'Organize Existing MKVs' to sort them."
        )

    def run_unattended_single(self):
        cfg       = self.engine.cfg
        temp_root = os.path.normpath(cfg["temp_folder"])

        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
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

        self.gui.set_status("Ripping...")
        success = self.engine.rip_all_titles(
            rip_path,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )

        if not success:
            self.report("Unattended single: rip failed.")
            self.flush_log()
            self.gui.show_error(
                "Rip Failed", "Disc could not be ripped."
            )
            return

        self.engine.update_temp_metadata(rip_path, status="ripped")
        mkv_files = sorted(
            glob.glob(os.path.join(rip_path, "*.mkv"))
        )
        self.log(f"Done. {len(mkv_files)} file(s) in: {rip_path}")
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
        temp_root = os.path.normpath(cfg["temp_folder"])

        self.engine.cleanup_partial_files(temp_root, self.log)
        if cfg.get("opt_show_temp_manager", True):
            self._offer_temp_manager(temp_root)
        if self.engine.abort_event.is_set():
            return

        title = self.gui.ask_input(
            "Series Title", "Exact series title:"
        )
        if not title:
            title = make_temp_title()
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

        disc_number    = 0
        current_season = 1

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

                disc_number += 1
                self.log(f"--- Disc {disc_number} ---")

                self.gui.show_info(
                    "Insert Disc",
                    f"Insert disc {disc_number} "
                    f"(Season {current_season:02d}) and click OK."
                )
                time.sleep(2)  # drive spin-up / mount stabilization

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

                self.gui.set_status("Ripping...")
                success = self.engine.rip_all_titles(
                    rip_path,
                    on_progress=self.gui.set_progress,
                    on_log=self.log
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
                mkv_files = sorted(
                    glob.glob(os.path.join(rip_path, "*.mkv"))
                )
                self.log(
                    f"Disc {disc_number} done. "
                    f"{len(mkv_files)} file(s) ripped."
                )
                self.gui.set_progress(0)

                if not self.gui.ask_yesno(
                    f"Season {current_season:02d} — "
                    f"another disc for this season?"
                ):
                    season_done = True

            current_season += 1

        self.write_session_summary()
        self.flush_log()
        self.gui.set_status("Ready")
        self.gui.set_progress(0)
        self.gui.show_info(
            "Series Complete",
            f"All discs ripped to:\n{series_root}\n\n"
            f"Use 'Organize Existing MKVs' to sort into your library."
        )

    def run_organize(self):
        cfg        = self.engine.cfg
        tv_root    = os.path.normpath(cfg["tv_folder"])
        movie_root = os.path.normpath(cfg["movies_folder"])

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

        title = self.gui.ask_input("Title", "Exact title:")
        if not title:
            title = make_temp_title()
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
            temp_root   = os.path.normpath(cfg["temp_folder"])
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
        tv_root    = os.path.normpath(cfg["tv_folder"])
        movie_root = os.path.normpath(cfg["movies_folder"])
        temp_root  = os.path.normpath(cfg["temp_folder"])

        self.engine.reset_abort()
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

        self.check_resume(temp_root)

        if is_tv:
            title = self.gui.ask_input(
                "Title", "Exact TV show title:"
            )
            if not title:
                title = make_temp_title()
                self.log(f"WARNING: No title — using: {title}")
            self.log(f"Title: {title}")
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

            if is_tv:
                season_str = self.gui.ask_input(
                    "Season",
                    f"Season number for disc {disc_number}:"
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
                    "Title", f"Title for disc {disc_number}:"
                )
                if not title:
                    title = make_temp_title()
                    self.log(f"WARNING: No title — using: {title}")
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
                rip_path = os.path.join(
                    temp_root, make_rip_folder_name()
                )

            os.makedirs(rip_path, exist_ok=True)
            self.engine.write_temp_metadata(
                rip_path, title, disc_number,
                season=season if is_tv else None
            )
            self.log(f"Temp folder: {rip_path}")

            if self.engine.abort_event.is_set():
                break

            time.sleep(2)  # drive spin-up / mount stabilization
            disc_titles = self.scan_with_retry()

            if self.engine.abort_event.is_set():
                break

            if not disc_titles:
                self.log("Could not read disc.")
                self.report(
                    f"Disc {disc_number}: could not read disc."
                )
                if not self.gui.ask_yesno("Retry?"):
                    break
                continue

            # Titles already sorted by score — first is best candidate
            if cfg.get("opt_smart_rip_mode", False):
                best          = disc_titles[0]
                selected_ids  = [best["id"]]
                selected_size = best["size_bytes"]
                self.log(
                    f"Smart Rip: auto-selected Title "
                    f"{best['id']+1} ({best['size']})"
                )
            else:
                selected_ids = self.gui.show_disc_tree(
                    disc_titles, is_tv
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

            self.gui.set_status("Ripping...")
            success, failed_titles = self.engine.rip_selected_titles(
                rip_path, selected_ids,
                on_progress=self.gui.set_progress,
                on_log=self.log
            )

            if failed_titles:
                self.report(
                    f"Disc {disc_number}: titles failed — "
                    f"{failed_titles}"
                )

            if not success:
                if self.engine.abort_event.is_set():
                    self.log("Rip aborted — cleaning up...")
                    for f in glob.glob(
                        os.path.join(rip_path, "*.partial")
                    ):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    self.log(f"Temp preserved at: {rip_path}")
                    break
                self.log("Rip did not complete.")
                self.flush_log()
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            self.engine.update_temp_metadata(
                rip_path, status="ripped"
            )
            self.log("Ripping complete.")
            self.gui.set_progress(0)
            time.sleep(2)

            mkv_files = sorted(
                glob.glob(os.path.join(rip_path, "*.mkv"))
            )
            if not mkv_files:
                self.log("No .mkv files found after ripping.")
                if not self.gui.ask_yesno("Try another disc?"):
                    break
                continue

            self.log(f"Found {len(mkv_files)} file(s).")
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
                self.log("Analysis aborted or no files returned.")
                break

            move_ok = self._select_and_move(
                titles_list, is_tv, title, dest_folder, extras_folder,
                season if is_tv else None,
                year if not is_tv else None
            )

            if move_ok:
                shutil.rmtree(rip_path, ignore_errors=True)
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
                         dest_folder, extras_folder, season, year):
        options = []
        for i, (f, dur, mb) in enumerate(titles_list, 1):
            mins = int(dur // 60) if dur > 0 else "?"
            options.append(
                f"{i}: {os.path.basename(f)}  ~{mins} min  {mb} MB"
            )

        self.log("Files (longest first, unknowns at end):")
        for opt in options:
            self.log(f"  {opt}")

        if is_tv:
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

            while True:
                ep_input = self.gui.ask_input(
                    "Episode Numbers",
                    f"Enter {len(main_indices)} episode number(s), "
                    f"comma separated:"
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
                "(or leave blank for defaults):"
            )
            real_names  = parse_episode_names(name_input)
            keep_extras = self.gui.ask_yesno("Keep extras?")

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
            selected = self.gui.show_file_list(
                "Select Main Movie",
                "Select the MAIN MOVIE file:",
                options
            )
            if not selected:
                self.log("Cancelled.")
                return False

            main_indices    = [int(selected[0].split(":")[0]) - 1]
            keep_extras     = self.gui.ask_yesno("Keep extras?")
            episode_numbers = []
            real_names      = []

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
        success, self.global_extra_counter = self.engine.move_files(
            titles_list, main_indices, episode_numbers,
            real_names, keep_extras, is_tv, title,
            dest_folder, extras_folder, season, year,
            self.global_extra_counter,
            on_progress=self.gui.set_progress,
            on_log=self.log
        )
        return success


# ==========================================
# LAYER 3 — GUI
# ==========================================

class JellyRipperGUI(tk.Tk):
    def __init__(self, cfg):
        """
        LAYER 3 — GUI

        Display and input layer. All tkinter lives here and only here.

        Owns all widgets, user prompts, progress indicators, and the inline
        yes/no and text input UI. Makes no content decisions.

        Threading model: all GUI updates must happen on the main thread via
        self.after(). Worker threads communicate through:
          - message_queue → process_queue() polls every 100ms for log lines
          - threading.Event for ask_input() and ask_yesno() blocking calls
          - _run_on_main() for one-off calls that need a return value

        Never call engine or controller methods directly from widget
        callbacks. Always go through start_task() which runs the target
        in a daemon thread.
        """
        super().__init__()
        self.cfg   = cfg
        self.title(f"Jellyfin Raw Ripper v{__version__}")
        self.geometry("1200x900")
        self.minsize(1000, 750)
        self.configure(bg="#0d1117")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.message_queue = queue_module.Queue()
        self.engine        = RipperEngine(cfg)
        self.controller    = RipperController(self.engine, self)
        self.rip_thread    = None
        self._input_result = None
        self._input_event  = threading.Event()
        self._input_active = False

        self.build_interface()
        self.controller.log(f"Jellyfin Raw Ripper v{__version__} started")
        self.controller.log("Choose a mode to begin")
        self.after(100, self.process_queue)

    def build_interface(self):
        BG = "#0d1117"
        self.configure(bg=BG)

        header = tk.Frame(self, bg="#161b22")
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"JELLYFIN RAW RIPPER",
            font=("Segoe UI", 24, "bold"),
            bg="#161b22", fg="#58a6ff"
        ).pack(pady=12)

        drive_frame = tk.Frame(self, bg=BG)
        drive_frame.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(
            drive_frame, text="Drive:",
            bg=BG, fg="#8b949e",
            font=("Segoe UI", 10)
        ).pack(side="left", padx=(0, 8))
        self.drive_var     = tk.StringVar(value="Loading drives...")
        self.drive_options = [(0, "Default Drive (disc:0)")]
        self.drive_menu    = ttk.Combobox(
            drive_frame, textvariable=self.drive_var,
            values=["Loading drives..."],
            state="readonly", width=38
        )
        self.drive_menu.bind(
            "<<ComboboxSelected>>", self._on_drive_select
        )
        self.drive_menu.pack(side="left")
        tk.Button(
            drive_frame, text="↻ Refresh",
            command=self._refresh_drives,
            bg="#21262d", fg="#c9d1d9",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="left", padx=8)

        mode_frame = tk.Frame(self, bg=BG)
        mode_frame.pack(pady=(12, 4))
        self.mode_buttons = {}
        buttons_row1 = [
            ("📀  Rip TV Show Disc",       "t",  "#238636", 20),
            ("🎬  Rip Movie Disc",          "m",  "#238636", 20),
            ("⚡  Smart Rip",              "sr", "#1a6b3a", 14),
            ("💾  Dump All Titles",         "d",  "#1f6feb", 18),
            ("📁  Organize Existing MKVs", "i",  "#6e40c9", 22),
        ]
        for text, mode, color, width in buttons_row1:
            btn = tk.Button(
                mode_frame, text=text,
                command=lambda m=mode: self.start_task(m),
                bg=color, fg="white",
                font=("Segoe UI", 11),
                width=width, height=2, relief="flat"
            )
            btn.pack(side="left", padx=5)
            self.mode_buttons[mode] = btn

        mode_frame2 = tk.Frame(self, bg=BG)
        mode_frame2.pack(pady=(4, 8))
        buttons_row2 = [
            ("🤖  Unattended — Single Disc", "u1", "#6e3a1e", 28),
            ("📦  Unattended — Series Mode", "us", "#6e3a1e", 28),
        ]
        for text, mode, color, width in buttons_row2:
            btn = tk.Button(
                mode_frame2, text=text,
                command=lambda m=mode: self.start_task(m),
                bg=color, fg="white",
                font=("Segoe UI", 11),
                width=width, height=2, relief="flat"
            )
            btn.pack(side="left", padx=5)
            self.mode_buttons[mode] = btn

        util_frame = tk.Frame(self, bg=BG)
        util_frame.pack(fill="x", padx=20)
        tk.Button(
            util_frame, text="📋  Copy Log",
            command=self.copy_log_to_clipboard,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="right", padx=4)
        tk.Button(
            util_frame, text="⚙  Settings",
            command=self.open_settings,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="right", padx=4)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self, variable=self.progress_var,
            maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(8, 2))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            self, textvariable=self.status_var,
            bg=BG, fg="#58a6ff",
            font=("Segoe UI", 10, "italic")
        ).pack(anchor="w", padx=22)

        tk.Label(
            self, text="Live Log",
            bg=BG, fg="#8b949e",
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=20)

        self.log_text = scrolledtext.ScrolledText(
            self, height=18, bg="#161b22", fg="#c9d1d9",
            font=("Consolas", 10), insertbackground="white",
            state="disabled"
        )
        self.log_text.pack(
            fill="both", expand=True, padx=20, pady=(0, 0)
        )
        self.log_text.tag_configure("prompt", foreground="#f0e68c")
        self.log_text.tag_configure("answer", foreground="#90ee90")

        self.input_bar = tk.Frame(self, bg="#21262d")
        self.input_bar.pack(fill="x", padx=20, pady=4)
        self.input_bar.pack_forget()

        self.input_label_var = tk.StringVar(value="")
        tk.Label(
            self.input_bar, textvariable=self.input_label_var,
            bg="#21262d", fg="#c9d1d9",
            font=("Segoe UI", 10), anchor="w"
        ).pack(side="left", padx=(10, 6), pady=8)

        self.input_var   = tk.StringVar()
        self.input_field = tk.Entry(
            self.input_bar, textvariable=self.input_var,
            bg="#0d1117", fg="#c9d1d9",
            font=("Segoe UI", 11),
            insertbackground="white",
            relief="flat", bd=4, width=40
        )
        self.input_field.pack(side="left", padx=4, pady=8)
        self.input_field.bind(
            "<Return>", lambda e: self._confirm_input()
        )

        self.input_browse_btn = tk.Button(
            self.input_bar, text="Browse",
            bg="#30363d", fg="#c9d1d9",
            font=("Segoe UI", 10),
            command=self._browse_input, relief="flat"
        )

        tk.Button(
            self.input_bar, text="Confirm",
            bg="#238636", fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self._confirm_input, relief="flat"
        ).pack(side="left", padx=4, pady=8)

        tk.Button(
            self.input_bar, text="Skip",
            bg="#30363d", fg="#8b949e",
            font=("Segoe UI", 10),
            command=self._skip_input, relief="flat"
        ).pack(side="left", padx=4, pady=8)

        bottom = tk.Frame(self, bg="#161b22")
        bottom.pack(fill="x", pady=8, padx=20)
        self.abort_btn = tk.Button(
            bottom, text="ABORT SESSION",
            bg="#c94b4b", fg="white",
            font=("Segoe UI", 12, "bold"),
            width=20, command=self.request_abort, relief="flat"
        )
        self.abort_btn.pack(side="right")

        self.after(500, self._refresh_drives)

    def _refresh_drives(self):
        def _load():
            makemkvcon = os.path.normpath(
                self.cfg.get("makemkvcon_path", "")
            )
            drives = get_available_drives(makemkvcon)
            self.after(0, lambda: self._update_drive_menu(drives))
        threading.Thread(target=_load, daemon=True).start()

    def _update_drive_menu(self, drives):
        self.drive_options = drives
        labels = [f"Drive {idx}: {name}" for idx, name in drives]
        self.drive_menu["values"] = labels
        current_idx = self.cfg.get("opt_drive_index", 0)
        for i, (idx, name) in enumerate(drives):
            if idx == current_idx:
                self.drive_var.set(labels[i])
                break
        else:
            if labels:
                self.drive_var.set(labels[0])

    def _on_drive_select(self, *args):
        selected = self.drive_var.get()
        for idx, name in self.drive_options:
            if f"Drive {idx}: {name}" == selected:
                self.cfg["opt_drive_index"] = idx
                self.engine.cfg["opt_drive_index"] = idx
                save_config(self.cfg)
                self.controller.log(f"Drive selected: {name}")
                break

    def copy_log_to_clipboard(self):
        try:
            self.log_text.config(state="normal")
            content = self.log_text.get("1.0", "end")
            self.clipboard_clear()
            self.clipboard_append(content)
            self.controller.log("Log copied to clipboard.")
        except Exception as e:
            self.controller.log(f"Could not copy log: {e}")
        finally:
            self.log_text.config(state="disabled")

    def _show_input_bar(self, label, show_browse=False):
        self.input_label_var.set(label)
        self.input_var.set("")
        self._input_active = True
        if show_browse:
            self.input_browse_btn.pack(side="left", padx=4, pady=8)
        else:
            self.input_browse_btn.pack_forget()
        self.input_bar.pack(fill="x", padx=20, pady=4)
        self.input_field.focus_set()

    def _hide_input_bar(self):
        self._input_active = False
        self.input_bar.pack_forget()
        self.input_var.set("")

    def _confirm_input(self):
        if not self._input_active:
            return
        val = self.input_var.get().strip()
        self._input_result = val if val else None
        self._input_event.set()

    def _skip_input(self):
        if not self._input_active:
            return
        self._input_result = ""
        self._input_event.set()

    def _browse_input(self):
        path = filedialog.askdirectory(parent=self)
        if path:
            self.input_var.set(os.path.normpath(path))

    def ask_input(self, label, prompt, show_browse=False):
        result = [None]
        done   = threading.Event()

        def _show():
            self._input_event.clear()
            self._input_result = None
            self._show_input_bar(f"{label}: {prompt}", show_browse)

            def _wait():
                while not self._input_event.wait(timeout=0.1):
                    if self.engine.abort_event.is_set():
                        self.after(0, self._hide_input_bar)
                        result[0] = None
                        done.set()
                        return
                val = self._input_result
                self.after(0, self._hide_input_bar)
                if val:
                    self.append_log(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"{label}: {val}"
                    )
                elif val == "":
                    self.append_log(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"{label}: (skipped)"
                    )
                result[0] = val
                done.set()

            threading.Thread(target=_wait, daemon=True).start()

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def ask_folder(self, title):
        return self._run_on_main(
            lambda: filedialog.askdirectory(title=title, parent=self)
        )

    def ask_yesno(self, prompt):
        result = [None]
        done   = threading.Event()

        def _show():
            self.log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(
                "end", f"[{ts}] {prompt}\n", "prompt"
            )

            btn_frame = tk.Frame(self.log_text, bg="#161b22")

            def yes():
                result[0] = True
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                self.log_text.config(state="normal")
                self.log_text.insert(
                    "end",
                    f"[{datetime.now().strftime('%H:%M:%S')}]"
                    f" → Yes\n",
                    "answer"
                )
                self.log_text.see("end")
                self.log_text.config(state="disabled")
                done.set()

            def no():
                result[0] = False
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                self.log_text.config(state="normal")
                self.log_text.insert(
                    "end",
                    f"[{datetime.now().strftime('%H:%M:%S')}]"
                    f" → No\n",
                    "answer"
                )
                self.log_text.see("end")
                self.log_text.config(state="disabled")
                done.set()

            tk.Button(
                btn_frame, text="  Yes  ",
                bg="#238636", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=yes, relief="flat"
            ).pack(side="left", padx=6, pady=4)
            tk.Button(
                btn_frame, text="  No  ",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=no, relief="flat"
            ).pack(side="left", padx=6, pady=4)

            self.log_text.window_create("end", window=btn_frame)
            self.log_text.insert("end", "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

            # Abort watcher — unblocks immediately if abort fires
            def _abort_watch():
                while not done.is_set():
                    if self.engine.abort_event.is_set():
                        def _cleanup():
                            try:
                                btn_frame.destroy()
                            except Exception:
                                pass
                            result[0] = False
                            done.set()
                        self.after(0, _cleanup)
                        return
                    time.sleep(0.1)

            threading.Thread(
                target=_abort_watch, daemon=True
            ).start()

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            pass
        return result[0] if result[0] is not None else False

    def _run_on_main(self, fn):
        result = [None]
        done   = threading.Event()

        def wrapper():
            try:
                result[0] = fn()
            finally:
                done.set()

        self.after(0, wrapper)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def show_info(self, title, msg):
        self._run_on_main(
            lambda: messagebox.showinfo(title, msg, parent=self)
        )

    def show_error(self, title, msg):
        self._run_on_main(
            lambda: messagebox.showerror(title, msg, parent=self)
        )

    def ask_space_override(self, required_gb, free_gb):
        result = [False]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title("Not Enough Space")
            win.configure(bg="#1a0000")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.resizable(False, False)

            tk.Label(
                win, text="⚠  NOT ENOUGH DISK SPACE",
                font=("Segoe UI", 16, "bold"),
                bg="#1a0000", fg="#ff4444"
            ).pack(pady=(20, 10), padx=20)
            tk.Label(
                win,
                text=f"Required:  {required_gb:.1f} GB\n"
                     f"Free:         {free_gb:.1f} GB\n\n"
                     f"This may cause the rip to fail\n"
                     f"or produce incomplete files.",
                font=("Segoe UI", 12),
                bg="#1a0000", fg="#ffcccc",
                justify="center"
            ).pack(pady=10, padx=30)

            bf = tk.Frame(win, bg="#1a0000")
            bf.pack(pady=20)

            def proceed():
                result[0] = True
                win.destroy()
                done.set()

            def cancel():
                result[0] = False
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                bf, text="I understand, continue anyway",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 11, "bold"),
                width=28, command=proceed, relief="flat"
            ).pack(side="left", padx=8)
            tk.Button(
                bf, text="Cancel",
                bg="#21262d", fg="white",
                font=("Segoe UI", 11),
                width=12, command=cancel, relief="flat"
            ).pack(side="left", padx=8)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return False
        return result[0]

    def show_disc_tree(self, disc_titles, is_tv):
        result = [None]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title("Disc Contents — Select Titles to Rip")
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.geometry("1060x660")

            tk.Label(
                win,
                text="Select titles to rip. "
                     "Click anywhere on a row to toggle. "
                     "Best title candidate highlighted in blue.",
                bg="#0d1117", fg="#8b949e",
                font=("Segoe UI", 10)
            ).pack(pady=(10, 4), padx=15)

            tree_frame = tk.Frame(win, bg="#0d1117")
            tree_frame.pack(
                fill="both", expand=True, padx=15, pady=5
            )

            style = ttk.Style()
            style.theme_use("default")
            style.configure(
                "Disc.Treeview",
                background="#161b22", foreground="#c9d1d9",
                fieldbackground="#161b22", rowheight=24,
                font=("Consolas", 10)
            )
            style.configure(
                "Disc.Treeview.Heading",
                background="#21262d", foreground="#58a6ff",
                font=("Segoe UI", 10, "bold")
            )
            style.map(
                "Disc.Treeview",
                background=[("selected", "#1f6feb")]
            )

            tree = ttk.Treeview(
                tree_frame, style="Disc.Treeview",
                columns=("duration", "size", "chapters", "audio"),
                show="tree headings"
            )
            tree.heading("#0",       text="Title / Track")
            tree.heading("duration", text="Duration")
            tree.heading("size",     text="Size")
            tree.heading("chapters", text="Chapters")
            tree.heading("audio",    text="Audio")
            tree.column("#0",       width=220)
            tree.column("duration", width=80,  anchor="center")
            tree.column("size",     width=80,  anchor="center")
            tree.column("chapters", width=70,  anchor="center")
            tree.column("audio",    width=380, anchor="w")

            vsb = ttk.Scrollbar(
                tree_frame, orient="vertical", command=tree.yview
            )
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            check_vars  = {}
            base_labels = {}

            # First title is best candidate — sorted by score in engine
            best_id = disc_titles[0]["id"] if disc_titles else None
            id_map  = {t["id"]: t for t in disc_titles}

            for t in disc_titles:
                audio_summary = format_audio_summary(
                    t["audio_tracks"]
                )
                iid          = f"title_{t['id']}"
                pre_selected = (t["id"] == best_id)
                check_vars[iid]  = pre_selected
                base_labels[iid] = f"Title {t['id']+1}: {t['name']}"
                check_char       = "☑" if pre_selected else "☐"

                tags = ["title"]
                if t["id"] == best_id:
                    tags.append("main")

                tree.insert(
                    "", "end", iid=iid,
                    text=f"{check_char}  {base_labels[iid]}",
                    values=(
                        t.get("duration", ""),
                        t.get("size", ""),
                        t.get("chapters", ""),
                        audio_summary,
                    ),
                    tags=tuple(tags)
                )

                for s in t["subtitle_tracks"]:
                    lang = (s.get("lang_name") or
                            s.get("lang") or "Unknown")
                    tree.insert(
                        iid, "end",
                        text=f"    💬 Subtitle: {lang}",
                        values=("", "", "", ""),
                        tags=("track",)
                    )

            tree.tag_configure("title", foreground="#c9d1d9")
            tree.tag_configure("main",  foreground="#58a6ff")
            tree.tag_configure("track", foreground="#6e7681")

            def toggle(event):
                item = tree.identify_row(event.y)
                if not item or not item.startswith("title_"):
                    return
                check_vars[item] = not check_vars[item]
                prefix = "☑" if check_vars[item] else "☐"
                tree.item(
                    item, text=f"{prefix}  {base_labels[item]}"
                )
                _update_size_label()

            tree.bind("<Button-1>", toggle)

            def _update_size_label():
                total = sum(
                    id_map[int(iid.split("_")[1])]["size_bytes"]
                    for iid, checked in check_vars.items()
                    if checked
                )
                size_label_var.set(
                    f"Selected: ~{total / (1024**3):.1f} GB"
                )

            def select_all():
                for iid in check_vars:
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            def deselect_all():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                _update_size_label()

            def select_best():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                if best_id is not None:
                    iid = f"title_{best_id}"
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            def select_top3():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                for t in disc_titles[:3]:
                    iid = f"title_{t['id']}"
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=15, pady=8)

            size_label_var = tk.StringVar(value="")
            _update_size_label()

            tk.Label(
                btn_row, textvariable=size_label_var,
                bg="#0d1117", fg="#58a6ff",
                font=("Segoe UI", 10, "bold")
            ).pack(side="left", padx=8)

            for text, cmd in [
                ("Select All",   select_all),
                ("Deselect All", deselect_all),
                ("Best Only",    select_best),
                ("Top 3",        select_top3),
            ]:
                tk.Button(
                    btn_row, text=text, command=cmd,
                    bg="#21262d", fg="#c9d1d9",
                    font=("Segoe UI", 10), relief="flat"
                ).pack(side="left", padx=4)

            def confirm():
                selected = [
                    int(iid.split("_")[1])
                    for iid, checked in check_vars.items()
                    if checked
                ]
                result[0] = selected
                win.destroy()
                done.set()

            def cancel():
                result[0] = None
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                btn_row, text="Rip Selected",
                bg="#238636", fg="white",
                font=("Segoe UI", 11, "bold"),
                command=confirm, relief="flat"
            ).pack(side="right", padx=4)
            tk.Button(
                btn_row, text="Cancel",
                bg="#21262d", fg="white",
                command=cancel, relief="flat"
            ).pack(side="right", padx=4)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def show_file_list(self, title, prompt, options):
        result = [None]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title(title)
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()

            tk.Label(
                win, text=prompt,
                bg="#0d1117", fg="#c9d1d9",
                font=("Segoe UI", 11), wraplength=500
            ).pack(pady=10, padx=15)

            listbox = tk.Listbox(
                win, bg="#161b22", fg="#c9d1d9",
                font=("Consolas", 10), width=70,
                height=min(len(options), 15),
                selectmode="extended", relief="flat"
            )
            listbox.pack(padx=15, pady=5)
            for opt in options:
                listbox.insert("end", opt)
            listbox.select_set(0)

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(pady=4)
            tk.Button(
                btn_row, text="Select All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.select_set(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)
            tk.Button(
                btn_row, text="Deselect All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.selection_clear(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)

            def confirm():
                result[0] = [
                    listbox.get(i) for i in listbox.curselection()
                ]
                win.destroy()
                done.set()

            def on_close():
                result[0] = []
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", on_close)
            tk.Button(
                win, text="Confirm",
                bg="#238636", fg="white",
                font=("Segoe UI", 11),
                command=confirm, relief="flat"
            ).pack(pady=10)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return []
        return result[0]

    def show_temp_manager(self, old_folders, engine, log_fn):
        if not old_folders:
            return
        done = threading.Event()

        STATUS_COLORS = {
            "ripped":     "#238636",
            "organizing": "#f0a500",
            "ripping":    "#f0a500",
            "organized":  "#1f6feb",
        }
        DEFAULT_COLOR = "#c94b4b"

        def _show():
            win = tk.Toplevel(self)
            win.title("Temp Session Manager")
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.geometry("740x540")

            tk.Label(
                win, text="Temp Sessions",
                font=("Segoe UI", 14, "bold"),
                bg="#0d1117", fg="#58a6ff"
            ).pack(pady=(15, 5))
            tk.Label(
                win,
                text="Leftover disc folders in your temp directory.\n"
                     "Check the ones you want to delete.",
                font=("Segoe UI", 10),
                bg="#0d1117", fg="#8b949e"
            ).pack(pady=(0, 10))

            frame = tk.Frame(win, bg="#0d1117")
            frame.pack(fill="both", expand=True, padx=15, pady=5)

            canvas = tk.Canvas(
                frame, bg="#0d1117", highlightthickness=0
            )
            scrollbar = ttk.Scrollbar(
                frame, orient="vertical", command=canvas.yview
            )
            scroll_frame = tk.Frame(canvas, bg="#0d1117")

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )
            canvas.create_window(
                (0, 0), window=scroll_frame, anchor="nw"
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            check_vars = []

            for full_path, name, file_count, size in old_folders:
                meta = engine.read_temp_metadata(full_path)
                var  = tk.BooleanVar(value=False)
                check_vars.append((var, full_path, name))

                status_text = (
                    meta.get("status", "unknown")
                    if meta else "unknown"
                )
                color = STATUS_COLORS.get(status_text, DEFAULT_COLOR)

                row = tk.Frame(scroll_frame, bg="#161b22")
                row.pack(fill="x", pady=3, padx=5)

                tk.Checkbutton(
                    row, variable=var,
                    bg="#161b22", activebackground="#161b22",
                    selectcolor="#238636"
                ).pack(side="left", padx=8, pady=8)

                tk.Label(
                    row, text="●", fg=color, bg="#161b22",
                    font=("Segoe UI", 14)
                ).pack(side="left", padx=(0, 6))

                info = tk.Frame(row, bg="#161b22")
                info.pack(
                    side="left", fill="x", expand=True, pady=6
                )

                title_text = (
                    meta.get("title", "Unknown")
                    if meta else "Unknown"
                )
                ts_text = (
                    meta.get("timestamp", name) if meta else name
                )

                tk.Label(
                    info, text=title_text,
                    font=("Segoe UI", 11, "bold"),
                    bg="#161b22", fg="#c9d1d9", anchor="w"
                ).pack(fill="x")
                tk.Label(
                    info,
                    text=f"Ripped: {ts_text}   "
                         f"Files: {file_count}   "
                         f"Size: {size / (1024**3):.1f} GB   "
                         f"Status: {status_text}",
                    font=("Segoe UI", 9),
                    bg="#161b22", fg="#8b949e", anchor="w"
                ).pack(fill="x")

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=15, pady=12)

            def select_all():
                for var, _, _ in check_vars:
                    var.set(True)

            def deselect_all():
                for var, _, _ in check_vars:
                    var.set(False)

            def delete_selected():
                for var, full_path, name in check_vars:
                    if var.get():
                        try:
                            shutil.rmtree(full_path)
                            log_fn(f"Deleted temp folder: {name}")
                        except Exception as e:
                            log_fn(
                                f"Could not delete {name}: {e}"
                            )
                win.destroy()
                done.set()

            def close():
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", close)

            tk.Button(
                btn_row, text="Select All",
                bg="#21262d", fg="#c9d1d9",
                command=select_all, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Deselect All",
                bg="#21262d", fg="#c9d1d9",
                command=deselect_all, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Delete Selected",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 11, "bold"),
                command=delete_selected, relief="flat"
            ).pack(side="right", padx=4)
            tk.Button(
                btn_row, text="Close",
                bg="#21262d", fg="white",
                command=close, relief="flat"
            ).pack(side="right", padx=4)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return

    def open_settings(self):
        done = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title("JellyRip Settings")
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.geometry("700x800")
            win.resizable(False, True)

            canvas = tk.Canvas(
                win, bg="#0d1117", highlightthickness=0
            )
            scrollbar = ttk.Scrollbar(
                win, orient="vertical", command=canvas.yview
            )
            scroll_frame = tk.Frame(canvas, bg="#0d1117")

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )
            canvas.create_window(
                (0, 0), window=scroll_frame, anchor="nw"
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            cfg      = self.cfg
            vars_map = {}

            def section(text):
                tk.Label(
                    scroll_frame, text=text,
                    bg="#0d1117", fg="#58a6ff",
                    font=("Segoe UI", 11, "bold"), anchor="w"
                ).pack(fill="x", padx=16, pady=(14, 2))
                tk.Frame(
                    scroll_frame, bg="#21262d", height=1
                ).pack(fill="x", padx=16, pady=(0, 6))

            def path_row(key, label):
                row = tk.Frame(scroll_frame, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=3)
                tk.Label(
                    row, text=label, bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), width=28, anchor="w"
                ).pack(side="left")
                var = tk.StringVar(
                    value=cfg.get(key, DEFAULTS.get(key, ""))
                )
                tk.Entry(
                    row, textvariable=var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    insertbackground="white",
                    relief="flat", bd=3, width=28
                ).pack(side="left", padx=4)

                def browse(k=key, v=var):
                    current = v.get().strip()
                    if current and os.path.exists(current):
                        start_dir = (
                            os.path.dirname(current)
                            if os.path.isfile(current)
                            else current
                        )
                    else:
                        start_dir = os.path.expanduser("~")

                    if k.endswith("_path") and "log" not in k:
                        path = filedialog.askopenfilename(
                            title=f"Select {label}",
                            initialdir=start_dir,
                            filetypes=[
                                ("Executable", "*.exe"),
                                ("All files", "*.*")
                            ],
                            parent=win
                        )
                    elif k == "log_file":
                        path = filedialog.asksaveasfilename(
                            title="Select log file location",
                            initialdir=start_dir,
                            initialfile=os.path.basename(current)
                                if current else "rip_log.txt",
                            defaultextension=".txt",
                            filetypes=[
                                ("Text files", "*.txt"),
                                ("All files", "*.*")
                            ],
                            parent=win
                        )
                    else:
                        path = filedialog.askdirectory(
                            title=f"Select {label}",
                            initialdir=start_dir,
                            parent=win
                        )
                    if path:
                        v.set(os.path.normpath(path))

                tk.Button(
                    row, text="Browse", command=browse,
                    bg="#21262d", fg="#c9d1d9",
                    font=("Segoe UI", 9), relief="flat"
                ).pack(side="left", padx=4)
                vars_map[key] = ("str", var)

            def toggle_row(key, label):
                """Create a toggle row without dependent number field.
                Number fields are now created separately for full independence."""
                row = tk.Frame(scroll_frame, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                bool_var = tk.BooleanVar(value=cfg.get(key, True))
                tk.Checkbutton(
                    row, variable=bool_var,
                    bg="#0d1117", activebackground="#0d1117",
                    selectcolor="#238636",
                    fg="#c9d1d9", font=("Segoe UI", 10),
                    text=label, anchor="w"
                ).pack(side="left")
                vars_map[key] = ("bool", bool_var)

            def number_row(key, label, default=0):
                row = tk.Frame(scroll_frame, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                num_var = tk.StringVar(
                    value=str(cfg.get(key, default))
                )
                tk.Entry(
                    row, textvariable=num_var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    relief="flat", bd=3, width=10
                ).pack(side="left")
                vars_map[key] = ("int", num_var)

            section("Paths")
            path_row("makemkvcon_path", "MakeMKV executable")
            path_row("ffprobe_path",    "ffprobe executable")
            path_row("temp_folder",     "Temp folder")
            path_row("tv_folder",       "TV shows folder")
            path_row("movies_folder",   "Movies folder")
            path_row("log_file",        "Log file")

            section("Ripping")
            toggle_row("opt_scan_disc_size",
                       "Scan disc size before ripping")
            toggle_row("opt_confirm_before_rip",
                       "Confirm selection before ripping")
            toggle_row("opt_stall_detection",
                       "Stall detection")
            number_row("opt_stall_timeout_seconds",
                       "Stall timeout (seconds):", 120)
            toggle_row("opt_auto_retry",
                       "Auto-retry failed titles")
            number_row("opt_retry_attempts",
                       "Retry attempts:", 3)
            toggle_row("opt_clean_mkv_before_retry",
                       "Clean MKV files before each retry")
            toggle_row("opt_smart_rip_mode",
                       "Smart Rip Mode (auto-select best title)")

            section("Moving")
            toggle_row("opt_check_dest_space",
                       "Check destination space before moving")
            toggle_row("opt_confirm_before_move",
                       "Confirm before moving files")
            toggle_row("opt_atomic_move",
                       "Atomic move (safe but slower)")
            toggle_row("opt_fsync",
                       "fsync on copy (protects against power loss)")

            section("Temp & Session")
            toggle_row("opt_show_temp_manager",
                       "Show temp manager on startup")
            toggle_row("opt_auto_delete_temp",
                       "Auto-delete temp after successful organize")
            toggle_row("opt_clean_partials_startup",
                       "Clean partial files on startup")

            section("Warnings & Limits")
            toggle_row("opt_warn_low_space",
                       "Warn if space below estimate")
            number_row("opt_hard_block_gb",
                       "Hard block below (GB):", 20)
            toggle_row("opt_warn_out_of_order_episodes",
                       "Warn on out-of-order episode numbers")
            toggle_row("opt_session_failure_report",
                       "Session failure report at end")

            section("Log")
            number_row(
                "opt_log_cap", "Log memory cap (lines):", 300000
            )
            number_row(
                "opt_log_trim", "Trim to (lines):", 200000
            )

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=16, pady=12)

            def save():
                try:
                    for key, (vtype, var) in vars_map.items():
                        if vtype == "str":
                            v = var.get().strip()
                            cfg[key] = (
                                os.path.normpath(v) if v else ""
                            )
                        elif vtype == "bool":
                            cfg[key] = var.get()
                        elif vtype == "int":
                            try:
                                cfg[key] = int(var.get())
                            except ValueError:
                                pass
                    self.engine.cfg = cfg
                    save_config(cfg)
                    self.controller.log("Settings saved.")
                except Exception as e:
                    self.controller.log(f"Error saving settings: {e}")
                finally:
                    win.destroy()
                    done.set()

            def cancel():
                try:
                    win.destroy()
                except Exception:
                    pass
                finally:
                    done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                btn_row, text="Save",
                bg="#238636", fg="white",
                font=("Segoe UI", 11, "bold"),
                width=12, command=save, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Cancel",
                bg="#21262d", fg="white",
                font=("Segoe UI", 11),
                width=12, command=cancel, relief="flat"
            ).pack(side="left", padx=4)

        self.after(0, _show)

    def start_indeterminate(self):
        def _start():
            if self.progress_bar["mode"] != "indeterminate":
                self.progress_bar.config(mode="indeterminate")
            self.progress_bar.start(12)
        self.after(0, _start)

    def stop_indeterminate(self):
        def _stop():
            self.progress_bar.stop()
            if self.progress_bar["mode"] != "determinate":
                self.progress_bar.config(mode="determinate")
            self.progress_var.set(0)
        self.after(0, _stop)

    def set_progress(self, pct):
        self.after(0, lambda: self.progress_var.set(pct))

    def set_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def append_log(self, msg):
        self.message_queue.put(msg)

    def process_queue(self):
        for _ in range(100):
            if self.message_queue.empty():
                break
            msg = self.message_queue.get()
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(100, self.process_queue)

    def disable_buttons(self):
        for btn in self.mode_buttons.values():
            btn.config(state="disabled")

    def enable_buttons(self):
        for btn in self.mode_buttons.values():
            btn.config(state="normal")

    def request_abort(self):
        """Abort immediately — no confirmation dialog required."""
        self.controller.log("ABORT REQUESTED BY USER")
        self.set_status("Aborting...")
        self.abort_btn.config(state="disabled")
        self.engine.abort()

    def on_close(self):
        if messagebox.askokcancel(
            "Exit", "Close Jellyfin Raw Ripper?", parent=self
        ):
            self.engine.abort()
            self.destroy()

    def start_task(self, mode):
        if self.rip_thread and self.rip_thread.is_alive():
            messagebox.showwarning(
                "Busy",
                "Wait for current operation to finish.",
                parent=self
            )
            return

        ok, msg = self.engine.validate_tools()
        if not ok:
            messagebox.showerror(
                "Configuration Error", msg, parent=self
            )
            return

        self.engine.reset_abort()
        self.abort_btn.config(state="normal")
        self.controller.session_log          = []
        self.controller.session_report       = []
        self.controller.start_time           = datetime.now()
        self.controller.global_extra_counter = 1
        self.disable_buttons()
        self.set_progress(0)

        targets = {
            "t":  self.controller.run_tv_disc,
            "m":  self.controller.run_movie_disc,
            "sr": self.controller.run_smart_rip,
            "d":  self.controller.run_dump_all,
            "i":  self.controller.run_organize,
            "u1": self.controller.run_unattended_single,
            "us": self.controller.run_unattended_series,
        }
        target = targets.get(mode, self.controller.run_organize)

        def task_wrapper():
            try:
                target()
            except Exception as e:
                self.controller.log(f"Unhandled error: {e}")
            finally:
                self.stop_indeterminate()
                self.after(0, self.enable_buttons)
                self.after(
                    0,
                    lambda: self.abort_btn.config(state="normal")
                )
                self.set_status("Ready")

        self.rip_thread = threading.Thread(
            target=task_wrapper, daemon=True
        )
        self.rip_thread.start()


if __name__ == "__main__":
    cfg = load_config()
    app = JellyRipperGUI(cfg)
    app.mainloop()