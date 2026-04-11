from __future__ import annotations

import os
import re
from collections.abc import Callable


LogFn = Callable[[str], None]

_RE_SXXEYY = re.compile(
    r"S(\d{1,3})((?:E\d{1,3})+)",
    re.IGNORECASE,
)
_RE_NXNN = re.compile(r"(\d{1,2})x(\d{1,2})")
_RE_EPISODE_N = re.compile(r"[Ee]pisode\s+(\d{1,4})")
_RE_E_SPLIT = re.compile(r"E(\d{1,3})", re.IGNORECASE)


def get_next_episode(existing: set[int]) -> int:
    if not existing:
        return 1
    for episode in range(1, max(existing) + 2):
        if episode not in existing:
            return episode
    return max(existing) + 1


def episodes_from_filename(fname: str, season: int) -> set[int]:
    match = _RE_SXXEYY.search(fname)
    if match:
        if int(match.group(1)) != season:
            return set()
        return {int(number) for number in _RE_E_SPLIT.findall(match.group(2))}

    match = _RE_NXNN.search(fname)
    if match:
        if int(match.group(1)) != season:
            return set()
        return {int(match.group(2))}

    match = _RE_EPISODE_N.search(fname)
    if match:
        return {int(match.group(1))}

    return set()


def scan_episode_files(folder: str | None, season: int) -> set[int]:
    found: set[int] = set()
    if not folder or not os.path.isdir(folder):
        return found
    try:
        for fname in os.listdir(folder):
            found |= episodes_from_filename(fname, season)
    except OSError:
        pass
    return found


def scan_library_folder(
    show_root: str | None,
    *,
    log_fn: LogFn | None = None,
) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    if not show_root or not os.path.isdir(show_root):
        return result

    season_pat = re.compile(r"Season\s+(\d{1,3})", re.IGNORECASE)
    specials_pat = re.compile(r"^Specials?$", re.IGNORECASE)

    try:
        for entry in os.listdir(show_root):
            season_dir = os.path.join(show_root, entry)
            if not os.path.isdir(season_dir):
                continue

            match = season_pat.match(entry)
            if match:
                season_num = int(match.group(1))
            elif specials_pat.match(entry):
                season_num = 0
            else:
                continue

            episodes = scan_episode_files(season_dir, season_num)
            result[season_num] = sorted(episodes)
            if season_num == 0 and log_fn:
                log_fn(
                    f"Specials/Season 00 detected: {season_dir} "
                    f"({len(episodes)} item(s))"
                )
    except OSError:
        pass

    return result


def scan_highest_episode(dest_folder: str | None, season: int) -> int:
    episodes = scan_episode_files(dest_folder, season)
    return max(episodes) if episodes else 0
