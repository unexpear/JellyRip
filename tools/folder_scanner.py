import os
import re
from typing import List, Tuple, Dict, Optional

def scan_folder(
    folder: str,
    mode: int = 1,
    min_size_mb: int = 0
) -> List[Dict]:
    """
    Scan a folder and return a list of movie files/folders with sorting/filtering.
    Modes:
      1: Largest to smallest (by size)
      2: Bad names (missing year, weird patterns)
      3: Alphabetical (default fallback)
    """
    entries = []
    for entry in os.scandir(folder):
        if entry.is_file() or entry.is_dir():
            size = entry.stat().st_size if entry.is_file() else _get_dir_size(entry.path)
            name = entry.name
            entries.append({
                "name": name,
                "path": entry.path,
                "size": size,
                "is_dir": entry.is_dir(),
                "bad_name": _is_bad_name(name),
            })
    # Filter by min size
    if min_size_mb > 0:
        entries = [e for e in entries if e["size"] >= min_size_mb * 1024 * 1024]
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
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
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
        size_mb = entry["size"] / (1024*1024)
        print(f"{'[DIR]' if entry['is_dir'] else '[FILE]'} {entry['name']:<50} {size_mb:8.2f} MB{'  BAD' if entry['bad_name'] else ''}")
