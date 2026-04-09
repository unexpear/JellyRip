from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Literal, TextIO, TypedDict


ScanStatus = Literal["RAW DISC", "RAW RIP", "OK", "WEIRD"]
ProgressCallback = Callable[[int, int], None]


class FolderScanEntry(TypedDict):
    name: str
    path: str
    size: int
    size_str: str
    is_dir: bool
    bad_name: bool
    parent: str | None
    status: ScanStatus


def classify_entry(entry: FolderScanEntry) -> ScanStatus:
    name = entry["name"].lower()
    path = entry["path"]

    if entry["is_dir"]:
        try:
            contents = os.listdir(path)
        except OSError:
            contents = []

        if "BDMV" in contents or "VIDEO_TS" in contents:
            return "RAW DISC"

        if sum(1 for item in contents if item.lower().endswith(".mkv")) >= 2:
            return "RAW RIP"

    if "(" in name and ")" in name:
        return "OK"

    return "WEIRD"


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
    name: str,
    path: str,
    size: int,
    is_dir: bool,
    parent: str | None,
) -> FolderScanEntry:
    entry: FolderScanEntry = {
        "name": name,
        "path": path,
        "size": size,
        "size_str": _format_size(size),
        "is_dir": is_dir,
        "bad_name": _is_bad_name(name),
        "parent": parent,
        "status": "WEIRD",
    }
    entry["status"] = classify_entry(entry)
    return entry


def scan_folder(
    folder: str,
    mode: int = 1,
    min_size_mb: int = 0,
    progress_cb: ProgressCallback | None = None,
    log_path: str | None = None,
) -> list[FolderScanEntry]:
    """
    Scan a folder and return a list of movie files/folders with sorting/filtering.
    Modes:
      1: Largest to smallest (by size)
      2: Bad names (missing year, weird patterns)
      3: Alphabetical (default fallback)
    """

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
            all_entries = list(os.scandir(current_folder))
        except OSError as exc:
            log(f"Failed to scan {current_folder}: {exc}")
            return local_entries

        for entry in all_entries:
            if entry.is_file() and entry.name.lower().endswith(".mkv"):
                try:
                    size_bytes = entry.stat().st_size
                except OSError as exc:
                    log(f"Failed to stat file {entry.path}: {exc}")
                    continue

                entry_dict = _build_entry(
                    name=entry.name,
                    path=entry.path,
                    size=size_bytes,
                    is_dir=False,
                    parent=parent,
                )
                local_entries.append(entry_dict)
                log(
                    "Scanned: "
                    f"{entry.name} | Size: {entry_dict['size_str']} | "
                    f"Dir: False | Bad: {entry_dict['bad_name']} | Parent: {parent}"
                )
                progress_count += 1
                _report_progress(progress_cb, progress_count, 0)
            elif entry.is_dir():
                sub_entries = _scan_dir(entry.path, parent=entry.path)
                if not sub_entries:
                    continue

                dir_size = _get_dir_size(entry.path)
                entry_dict = _build_entry(
                    name=entry.name,
                    path=entry.path,
                    size=dir_size,
                    is_dir=True,
                    parent=parent,
                )
                local_entries.append(entry_dict)
                local_entries.extend(sub_entries)
                log(
                    "Scanned: "
                    f"{entry.name} | Size: {entry_dict['size_str']} | "
                    f"Dir: True | Bad: {entry_dict['bad_name']} | Parent: {parent}"
                )
                progress_count += 1
                _report_progress(progress_cb, progress_count, 0)

        return local_entries

    if log_path:
        try:
            logf = open(log_path, "w", encoding="utf-8")
            log(f"Folder scan started: {folder}")
        except OSError:
            logf = None

    try:
        entries = _scan_dir(folder)
        total = len(entries)
        _report_progress(progress_cb, total, total)
        log(f"Scan complete. {total} entries.")
    finally:
        if logf is not None:
            logf.close()

    if min_size_mb > 0:
        min_size_bytes = min_size_mb * 1024 * 1024
        entries = [entry for entry in entries if entry["size"] >= min_size_bytes]

    if mode == 1:
        entries.sort(key=lambda entry: -entry["size"])
    elif mode == 2:
        entries = [entry for entry in entries if entry["bad_name"]]
    else:
        entries.sort(key=lambda entry: entry["name"].lower())

    return entries


def _get_dir_size(path: str) -> int:
    total = 0
    visited: set[str] = set()
    for root, dirs, files in os.walk(path, followlinks=False):
        real_root = os.path.realpath(root)
        if real_root in visited:
            continue

        visited.add(real_root)
        dirs[:] = [directory for directory in dirs if not os.path.islink(os.path.join(root, directory))]
        for filename in files:
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

    parser = argparse.ArgumentParser(description="Scan and sort movie folders.")
    parser.add_argument("folder", help="Folder to scan")
    parser.add_argument("--mode", type=int, default=1, help="1=largest, 2=bad names, 3=alpha")
    parser.add_argument("--min-size-mb", type=int, default=0, help="Minimum size in MB")
    args = parser.parse_args()

    results = scan_folder(args.folder, args.mode, args.min_size_mb)
    for entry in results:
        print(
            f"{'[DIR]' if entry['is_dir'] else '[FILE]'} "
            f"{entry['name']:<50} {entry['size_str']:>12}  {entry['status']}"
        )
