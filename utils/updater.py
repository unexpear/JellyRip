"""Update helpers for checking GitHub releases and downloading assets."""

import json
import urllib.error
import urllib.request


def _normalize_version(value):
    token = str(value or "").strip().lower()
    if token.startswith("v"):
        token = token[1:]
    parts = []
    for piece in token.split("."):
        try:
            parts.append(int(piece))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(current_version, latest_version):
    """Return True when latest_version is newer than current_version."""
    return _normalize_version(latest_version) > _normalize_version(current_version)


def fetch_latest_release(repo="unexpear/JellyRip", timeout=8):
    """Fetch latest GitHub release metadata for the given repo."""
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "JellyRip-Updater",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    assets = payload.get("assets") or []
    preferred = ["JellyRipInstaller.exe", "JellyRip.exe"]
    chosen_asset = None
    for name in preferred:
        chosen_asset = next((a for a in assets if a.get("name") == name), None)
        if chosen_asset:
            break
    if chosen_asset is None and assets:
        chosen_asset = assets[0]

    tag = str(payload.get("tag_name") or "").strip()
    normalized = tag[1:] if tag.lower().startswith("v") else tag

    return {
        "tag": tag,
        "version": normalized,
        "html_url": payload.get("html_url") or "",
        "asset_name": (chosen_asset or {}).get("name") or "",
        "asset_url": (chosen_asset or {}).get("browser_download_url") or "",
    }


def download_asset(url, destination_path, progress_callback=None, timeout=15):
    """Download a release asset to destination_path."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "JellyRip-Updater"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        written = 0
        with open(destination_path, "wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                written += len(chunk)
                if progress_callback:
                    progress_callback(written, total)


__all__ = [
    "download_asset",
    "fetch_latest_release",
    "is_newer_version",
]
