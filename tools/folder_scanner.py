import os
import re
from typing import List, Tuple, Dict, Optional, Callable

def scan_folder(
    folder: str,
    mode: int = 1,
    min_size_mb: int = 0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    log_path: Optional[str] = None
) -> List[Dict]:
    """
    Scan a folder and return a list of movie files/folders with sorting/filtering.
    Modes:
      1: Largest to smallest (by size)
      2: Bad names (missing year, weird patterns)
      3: Alphabetical (default fallback)
    """

    def _format_size(size_bytes):
        if size_bytes >= 1024 ** 4:
            return f"{size_bytes / (1024 ** 4):.2f} TB"
        elif size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
        elif size_bytes >= 1024 ** 2:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes} bytes"

    logf = None
    def log(msg):
        if logf:
            logf.write(msg + "\n")


    entries = []
    progress_count = [0]

    def _scan_dir(current_folder, parent=None):
        local_entries = []
        mkv_found_in_dir = False
        try:
            all_entries = list(os.scandir(current_folder))
        except Exception as e:
            if logf:
                logf.write(f"Failed to scan {current_folder}: {e}\n")
            return local_entries
        for entry in all_entries:
            if entry.is_file() and entry.name.lower().endswith('.mkv'):
                size_bytes = entry.stat().st_size
                name = entry.name
                entry_dict = {
                    "name": name,
                    "path": entry.path,
                    "size": size_bytes,
                    "size_str": _format_size(size_bytes),
                    "is_dir": False,
                    "bad_name": _is_bad_name(name),
                    "parent": parent,
                }
                local_entries.append(entry_dict)
                mkv_found_in_dir = True
                log(f"Scanned: {name} | Size: {_format_size(size_bytes)} | Dir: False | Bad: {_is_bad_name(name)} | Parent: {parent}")
                progress_count[0] += 1
                if progress_cb:
                    try:
                        progress_cb(progress_count[0], 0)
                    except Exception:
                        pass
            elif entry.is_dir():
                sub_entries = _scan_dir(entry.path, parent=entry.path)
                # Only add the directory if it contains mkv files
                if sub_entries:
                    dir_size = _get_dir_size(entry.path)
                    entry_dict = {
                        "name": entry.name,
                        "path": entry.path,
                        "size": dir_size,
                        "size_str": _format_size(dir_size),
                        "is_dir": True,
                        "bad_name": _is_bad_name(entry.name),
                        "parent": parent,
                    }
                    local_entries.append(entry_dict)
                    local_entries.extend(sub_entries)
                    log(f"Scanned: {entry.name} | Size: {_format_size(dir_size)} | Dir: True | Bad: {_is_bad_name(entry.name)} | Parent: {parent}")
                    progress_count[0] += 1
                    if progress_cb:
                        try:
                            progress_cb(progress_count[0], 0)
                        except Exception:
                            pass
        return local_entries

    entries = _scan_dir(folder, parent=None)
    total = len(entries)
    # Final progress update with total
    if progress_cb:
        try:
            progress_cb(total, total)
        except Exception:
            pass

    if log_path:
        try:
            logf = open(log_path, "w", encoding="utf-8")
            logf.write(f"Folder scan started: {folder}\n")
        except Exception:
            logf = None

    # Progress callback is not granular in recursive mode, but can be called at end
    if progress_cb:
        progress_cb(total, total)
    if logf:
        logf.write(f"Scan complete. {len(entries)} entries.\n")
        logf.close()
    # Filter by min size
    if min_size_mb > 0:
        min_size_bytes = min_size_mb * 1024 * 1024
        entries = [e for e in entries if e["size"] >= min_size_bytes]
    # Sorting
    if mode == 1:
        entries.sort(key=lambda e: -e["size"])
    elif mode == 2:
        entries = [e for e in entries if e["bad_name"]]
    else:
        entries.sort(key=lambda e: e["name"].lower())
    return entries

def _get_dir_size(path: str) -> int:
    total = 0
    visited = set()
    for root, dirs, files in os.walk(path, followlinks=False):
        real_root = os.path.realpath(root)
        if real_root in visited:
            # Already visited this directory (symlink/junction loop)
            continue
        visited.add(real_root)
        # Remove symlinked dirs from traversal
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for f in files:
            fp = os.path.join(root, f)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except Exception:
                pass
    return total

def _is_bad_name(name: str) -> bool:
    # Bad if missing year (YYYY), or has weird chars, or too short
    if len(name) < 6:
        return True
    if not re.search(r"\\b(19|20)\\d{2}\\b", name):
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
        print(f"{'[DIR]' if entry['is_dir'] else '[FILE]'} {entry['name']:<50} {entry['size_str']:>12}{'  BAD' if entry['bad_name'] else ''}")
