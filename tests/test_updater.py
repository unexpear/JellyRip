"""Tests for update verification and download safeguards."""

from pathlib import Path

import pytest

from utils import updater


class _FakeResponse:
    def __init__(self, chunks, total="0"):
        self._chunks = list(chunks)
        self.headers = {"Content-Length": total}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _size):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_verify_downloaded_update_valid_signature(monkeypatch):
    monkeypatch.setattr(
        updater,
        "get_authenticode_signature",
        lambda _path: {
            "status": "Valid",
            "status_message": "",
            "thumbprint": "ABCDEF",
            "subject": "CN=Signer",
        },
    )

    ok, msg = updater.verify_downloaded_update(
        "dummy.exe",
        require_signature=True,
        required_thumbprint="ABCDEF",
    )

    assert ok is True
    assert (
        "valid" in msg.lower()
        or "validated" in msg.lower()
        or "passed" in msg.lower()
        or "verified" in msg.lower()
    )


def test_download_asset_detects_stall(monkeypatch, tmp_path):
    chunks = [b"a", b"b", b"c", b""]
    monkeypatch.setattr(
        updater.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(chunks, total="3"),
    )

    tick = {"t": 0.0}

    def fake_time():
        # Advance quickly so each chunk lands in a new timeout window.
        tick["t"] += 61.0
        return tick["t"]

    monkeypatch.setattr(updater.time, "time", fake_time)

    out_file = Path(tmp_path) / "update.bin"

    with pytest.raises(TimeoutError):
        updater.download_asset(
            "https://example.invalid/update.bin",
            str(out_file),
            timeout=1,
            max_total_seconds=0,
            stall_window_seconds=60,
            min_window_bytes=1024,
        )
