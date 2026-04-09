from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Literal, TextIO, TypedDict


ScanStatus = Literal["RAW DISC", "RAW RIP", "OK", "WEIRD"]
SortMode = Literal[
    "size_desc",
    "size_asc",
    "name_asc",
    "name_desc",
    "modified_desc",
    "modified_asc",
    "duration_desc",
    "duration_asc",
    "bad_names",
]
ProgressCallback = Callable[[int, int], None]

SORT_MODE_LABELS: dict[SortMode, str] = {
    "size_desc": "Largest to Smallest",
    "size_asc": "Smallest to Largest",
    "name_asc": "Alphabetical (A-Z)",
    "name_desc": "Alphabetical (Z-A)",
    "modified_desc": "Newest First",
    "modified_asc": "Oldest First",
    "duration_desc": "Longest Runtime",
    "duration_asc": "Shortest Runtime",
    "bad_names": "Bad/Weird Names",
}

LEGACY_MODE_MAP: dict[int, SortMode] = {
    1: "size_desc",
    2: "bad_names",
    3: "name_asc",
    4: "size_asc",
    5: "name_desc",
    6: "modified_desc",
    7: "modified_asc",
    8: "duration_desc",
    9: "duration_asc",
}


class FolderScanEntry(TypedDict):
    name: str
    path: str
    relative_path: str
    size: int
    size_str: str
    is_dir: bool
    bad_name: bool
    parent: str | None
    status: ScanStatus
    modified_ts: float
    modified_str: str
    duration_seconds: float | None
    duration_str: str


def get_sort_mode_label(mode: int | str) -> str:
    return SORT_MODE_LABELS[_normalize_mode(mode)]


def classify_entry(entry: FolderScanEntry) -> ScanStatus:
    name = entry["name"].lower()

    if entry["is_dir"]:
        try:
            contents = os.listdir(entry["path"])
        except OSError:
            contents = []

        if "BDMV" in contents or "VIDEO_TS" in contents:
            return "RAW DISC"

        if sum(1 for item in contents if item.lower().endswith(".mkv")) >= 2:
            return "RAW RIP"

    if "(" in name and ")" in name:
        return "OK"

    return "WEIRD"


def _normalize_mode(mode: int | str) -> SortMode:
    if isinstance(mode, int):
        return LEGACY_MODE_MAP.get(mode, "name_asc")

    normalized = str(mode or "").strip().lower().replace("-", "_")
    aliases: dict[str, SortMode] = {
        "largest": "size_desc",
        "largest_first": "size_desc",
        "smallest": "size_asc",
        "smallest_first": "size_asc",
        "alpha": "name_asc",
        "alphabetical": "name_asc",
        "az": "name_asc",
        "za": "name_desc",
        "newest": "modified_desc",
        "oldest": "modified_asc",
        "longest": "duration_desc",
        "shortest": "duration_asc",
        "weird": "bad_names",
        "bad": "bad_names",
    }
    if normalized in SORT_MODE_LABELS:
        return normalized  # type: ignore[return-value]
    return aliases.get(normalized, "name_asc")


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024**4:
        return f"{size_bytes / (1024**4):.2f} TB"
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    if size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def _format_duration(duration_seconds: float | None) -> str:
    if duration_seconds is None or duration_seconds <= 0:
        return "n/a"
    total_seconds = int(round(duration_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_timestamp(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "n/a"


def _report_progress(
    progress_cb: ProgressCallback | None,
    current: int,
    total: int,
) -> None:
    if progress_cb is None:
        return
    try:
        progress_cb(current, total)
    except Exception:
        pass


def _build_entry(
    *,
    root_folder: str,
    name: str,
    path: str,
    size: int,
    is_dir: bool,
    parent: str | None,
    modified_ts: float,
) -> FolderScanEntry:
    relative_path = os.path.relpath(path, root_folder)
    entry: FolderScanEntry = {
        "name": name,
        "path": path,
        "relative_path": relative_path,
        "size": size,
        "size_str": _format_size(size),
        "is_dir": is_dir,
        "bad_name": _is_bad_name(name),
        "parent": parent,
        "status": "WEIRD",
        "modified_ts": modified_ts,
        "modified_str": _format_timestamp(modified_ts),
        "duration_seconds": None,
        "duration_str": "n/a",
    }
    entry["status"] = classify_entry(entry)
    return entry


def _resolve_ffprobe_exe(ffprobe_exe: str | None) -> str | None:
    normalized = str(ffprobe_exe or "").strip()
    if normalized and os.path.isfile(normalized):
        return normalized
    if normalized and os.path.isdir(normalized):
        for candidate in (
            os.path.join(normalized, "ffprobe.exe"),
            os.path.join(normalized, "bin", "ffprobe.exe"),
        ):
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("ffprobe")


def _probe_duration_seconds(path: str, ffprobe_exe: str) -> float | None:
    creationflags = 0x08000000 if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            creationflags=creationflags,
        )
    except Exception:
        return None

    if proc.returncode != 0:
        return None
    try:
        value = float((proc.stdout or "").strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _apply_duration_metadata(
    entries: list[FolderScanEntry],
    ffprobe_exe: str | None,
    log: Callable[[str], None],
) -> None:
    if not ffprobe_exe:
        log("Duration sort requested but ffprobe was not found; using size/name fallback.")
        return

    file_entries = [entry for entry in entries if not entry["is_dir"]]
    if not file_entries:
        return

    max_workers = min(8, max(1, (os.cpu_count() or 4)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_probe_duration_seconds, entry["path"], ffprobe_exe): entry
            for entry in file_entries
        }
        for future in as_completed(future_map):
            entry = future_map[future]
            try:
                duration = future.result()
            except Exception:
                duration = None
            entry["duration_seconds"] = duration
            entry["duration_str"] = _format_duration(duration)


def _sort_entries(entries: list[FolderScanEntry], mode: SortMode) -> list[FolderScanEntry]:
    if mode == "bad_names":
        filtered = [entry for entry in entries if entry["bad_name"]]
        filtered.sort(
            key=lambda entry: (
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return filtered

    if mode == "size_desc":
        entries.sort(
            key=lambda entry: (
                -entry["size"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "size_asc":
        entries.sort(
            key=lambda entry: (
                entry["size"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "name_asc":
        entries.sort(
            key=lambda entry: (
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "name_desc":
        entries.sort(
            key=lambda entry: (
                entry["name"].lower(),
                entry["relative_path"].lower(),
            ),
            reverse=True,
        )
        return entries

    if mode == "modified_desc":
        entries.sort(
            key=lambda entry: (
                -entry["modified_ts"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "modified_asc":
        entries.sort(
            key=lambda entry: (
                entry["modified_ts"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "duration_desc":
        entries.sort(
            key=lambda entry: (
                entry["duration_seconds"] is None,
                -(entry["duration_seconds"] or 0.0),
                -entry["size"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    if mode == "duration_asc":
        entries.sort(
            key=lambda entry: (
                entry["duration_seconds"] is None,
                entry["duration_seconds"] or 0.0,
                -entry["size"],
                entry["name"].lower(),
                entry["relative_path"].lower(),
            )
        )
        return entries

    return entries


def scan_folder(
    folder: str,
    mode: int | str = 1,
    min_size_mb: int = 0,
    progress_cb: ProgressCallback | None = None,
    log_path: str | None = None,
    recursive: bool = True,
    include_dirs: bool = True,
    ffprobe_exe: str | None = None,
) -> list[FolderScanEntry]:
    """
    Scan a folder and return MKV-oriented entries with sorting/filtering.

    The legacy integer modes remain supported:
      1: largest to smallest
      2: bad/weird names only
      3: alphabetical

    New string or integer modes can additionally sort by:
      - size ascending
      - name descending
      - modified time newest/oldest
      - runtime longest/shortest (via ffprobe when available)
    """

    sort_mode = _normalize_mode(mode)
    root_folder = os.path.normpath(folder)
    logf: TextIO | None = None
    progress_count = 0

    def log(msg: str) -> None:
        if logf is not None:
            logf.write(f"{msg}\n")

    def _scan_dir(
        current_folder: str,
        parent: str | None = None,
    ) -> list[FolderScanEntry]:
        nonlocal progress_count
        local_entries: list[FolderScanEntry] = []

        try:
            all_entries = sorted(
                os.scandir(current_folder),
                key=lambda entry: entry.name.lower(),
            )
        except OSError as exc:
            log(f"Failed to scan {current_folder}: {exc}")
            return local_entries

        for entry in all_entries:
            try:
                is_file = entry.is_file(follow_symlinks=False)
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue

            if is_file and entry.name.lower().endswith(".mkv"):
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    log(f"Failed to stat file {entry.path}: {exc}")
                    continue

                entry_dict = _build_entry(
                    root_folder=root_folder,
                    name=entry.name,
                    path=entry.path,
                    size=stat.st_size,
                    is_dir=False,
                    parent=parent,
                    modified_ts=stat.st_mtime,
                )
                local_entries.append(entry_dict)
                log(
                    "Scanned MKV: "
                    f"{entry_dict['relative_path']} | "
                    f"Size: {entry_dict['size_str']} | "
                    f"Bad: {entry_dict['bad_name']}"
                )
                progress_count += 1
                _report_progress(progress_cb, progress_count, 0)
                continue

            if not is_dir:
                continue

            next_parent = entry.path
            sub_entries = _scan_dir(entry.path, parent=next_parent) if recursive else []
            if include_dirs and sub_entries:
                dir_size = _get_dir_size(entry.path)
                try:
                    stat = entry.stat(follow_symlinks=False)
                    modified_ts = stat.st_mtime
                except OSError:
                    modified_ts = 0.0
                entry_dict = _build_entry(
                    root_folder=root_folder,
                    name=entry.name,
                    path=entry.path,
                    size=dir_size,
                    is_dir=True,
                    parent=parent,
                    modified_ts=modified_ts,
                )
                local_entries.append(entry_dict)
                log(
                    "Scanned directory: "
                    f"{entry_dict['relative_path']} | "
                    f"Size: {entry_dict['size_str']} | "
                    f"Status: {entry_dict['status']}"
                )
                progress_count += 1
                _report_progress(progress_cb, progress_count, 0)

            local_entries.extend(sub_entries)

        return local_entries

    if log_path:
        try:
            logf = open(log_path, "w", encoding="utf-8")
            log(f"Folder scan started: {root_folder}")
            log(
                "Options: "
                f"sort={sort_mode}, recursive={recursive}, include_dirs={include_dirs}"
            )
        except OSError:
            logf = None

    try:
        entries = _scan_dir(root_folder)
        if min_size_mb > 0:
            min_size_bytes = min_size_mb * 1024 * 1024
            entries = [entry for entry in entries if entry["size"] >= min_size_bytes]

        if sort_mode in {"duration_desc", "duration_asc"}:
            _apply_duration_metadata(entries, _resolve_ffprobe_exe(ffprobe_exe), log)

        entries = _sort_entries(entries, sort_mode)
        total = len(entries)
        _report_progress(progress_cb, total, total)
        log(f"Scan complete. {total} entries.")
        return entries
    finally:
        if logf is not None:
            logf.close()


def _get_dir_size(path: str) -> int:
    total = 0
    visited: set[str] = set()
    for root, dirs, files in os.walk(path, followlinks=False):
        real_root = os.path.realpath(root)
        if real_root in visited:
            continue

        visited.add(real_root)
        dirs[:] = [
            directory
            for directory in dirs
            if not os.path.islink(os.path.join(root, directory))
        ]
        for filename in files:
            if not filename.lower().endswith(".mkv"):
                continue
            file_path = os.path.join(root, filename)
            try:
                if not os.path.islink(file_path):
                    total += os.path.getsize(file_path)
            except OSError:
                pass

    return total


def _is_bad_name(name: str) -> bool:
    if len(name) < 6:
        return True
    if not re.search(r"\b(19|20)\d{2}\b", name):
        return True
    if re.search(r"[^\w .\-()\[\]]", name):
        return True
    return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan MKV folders for transcode prep.")
    parser.add_argument("folder", help="Folder to scan")
    parser.add_argument(
        "--mode",
        default="size_desc",
        help=(
            "Sort mode: size_desc, size_asc, name_asc, name_desc, "
            "modified_desc, modified_asc, duration_desc, duration_asc, bad_names"
        ),
    )
    parser.add_argument("--min-size-mb", type=int, default=0, help="Minimum size in MB")
    parser.add_argument("--ffprobe", default="", help="Optional ffprobe executable path")
    parser.add_argument(
        "--include-dirs",
        action="store_true",
        help="Include directory summary entries in addition to MKV files",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only scan the selected folder, not subfolders",
    )
    args = parser.parse_args()

    results = scan_folder(
        args.folder,
        mode=args.mode,
        min_size_mb=args.min_size_mb,
        recursive=not args.no_recursive,
        include_dirs=args.include_dirs,
        ffprobe_exe=args.ffprobe or None,
    )
    for entry in results:
        print(
            f"{entry['size_str']:>12}  "
            f"{entry['duration_str']:>8}  "
            f"{entry['modified_str']}  "
            f"{entry['relative_path']}"
        )
