"""Update helpers for checking GitHub releases and downloading assets."""

import hashlib
import json
import shutil
import subprocess
import sys as _sys
import urllib.error
import urllib.request

# Resolve PowerShell executable once at import time; fall back to the
# well-known absolute path when powershell.exe is not on PATH.
_ps_exe = (
    shutil.which("powershell")
    or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
)

# Suppress black CMD flash on Windows.
_POPEN_FLAGS = {"creationflags": 0x08000000} if _sys.platform == "win32" else {}


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


def download_asset(url, destination_path, progress_callback=None, timeout=15,
                   abort_event=None):
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
                if abort_event and abort_event.is_set():
                    raise InterruptedError("Download aborted by user")
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)
                written += len(chunk)
                if progress_callback:
                    progress_callback(written, total)


def sha256_file(path):
    """Return lowercase SHA256 hex for the given file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def get_authenticode_signature(path):
    """Get Authenticode signature details via PowerShell on Windows."""
    # Pass the path as a PS variable to avoid any injection via string formatting.
    # -LiteralPath treats the value as a literal string (no wildcards, no PS expansion).
    ps = (
        "param([string]$p); "
        "$sig = Get-AuthenticodeSignature -LiteralPath $p; "
        "$out = [PSCustomObject]@{"
        "Status = [string]$sig.Status; "
        "StatusMessage = [string]$sig.StatusMessage; "
        "Thumbprint = [string]($sig.SignerCertificate.Thumbprint); "
        "Subject = [string]($sig.SignerCertificate.Subject)"
        "}; "
        "$out | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        [_ps_exe, "-NoProfile", "-Command", ps, "-p", path],
        capture_output=True,
        text=True,
        timeout=15,
        **_POPEN_FLAGS
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "signature query failed")
    data = json.loads(proc.stdout.strip() or "{}")
    return {
        "status": str(data.get("Status") or "").strip(),
        "status_message": str(data.get("StatusMessage") or "").strip(),
        "thumbprint": str(data.get("Thumbprint") or "").strip().upper(),
        "subject": str(data.get("Subject") or "").strip(),
    }


def verify_downloaded_update(
    path,
    *,
    require_signature=True,
    required_thumbprint="",
):
    """Validate downloaded update package before launch."""
    if not require_signature:
        return True, "Signature verification is disabled by configuration."

    pin = (required_thumbprint or "").strip().upper().replace(" ", "")
    if not pin:
        return (
            False,
            "Signature verification requires a pinned signer thumbprint, "
            "but none is configured.",
        )

    try:
        sig = get_authenticode_signature(path)
    except Exception as e:
        return False, f"Could not verify Authenticode signature: {e}"

    if sig.get("status") != "Valid":
        msg = sig.get("status_message") or "Unsigned or invalid signature"
        return False, f"Signature validation failed: {msg}"

    got = (sig.get("thumbprint") or "").strip().upper().replace(" ", "")
    if pin and got != pin:
        return (
            False,
            "Signer certificate thumbprint mismatch. "
            f"Expected {pin}, got {got or '<none>'}."
        )

    return True, (
        "Authenticode signature is valid"
        + (f" (subject: {sig.get('subject')})" if sig.get("subject") else "")
    )


__all__ = [
    "download_asset",
    "fetch_latest_release",
    "get_authenticode_signature",
    "is_newer_version",
    "sha256_file",
    "verify_downloaded_update",
]
