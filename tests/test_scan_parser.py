"""Tests for engine.scan_ops.scan_disc — the makemkvcon scan parser.

Seam: monkeypatch `subprocess.Popen` in `engine.scan_ops` to return a fake
process whose stdout pipe yields canned makemkvcon scan output. Unlike the
rip parser, scan_disc reads stdout *synchronously* in the main thread (no
queue, no reader thread), so these tests run without timeout waits.

Covered (per memory/test-coverage.md §3 corrected scope):
- Clean scan — CINFO+TINFO+SINFO sequence → titles list with correct fields,
  on_progress fires per new title, engine.last_drive_info populated.
- TINFO with invalid duration / size → title marked _invalid → excluded.
- Title sorting by descending duration.
- MSG with LibreDrive / UHD hints → drive_info reflects them.
- Non-zero exit → returns None, error logged.
- Abort mid-scan → returns None, proc.kill() called.
- Malformed CINFO / TINFO → silently skipped (no crash).
- SINFO before its parent TINFO → silently skipped (tid-not-in-titles guard).
- Empty stdout → returns []; if titles existed but all were invalid, also [].
- Exception during scan → returns None (caught and logged).
"""

from __future__ import annotations

from typing import Any

from engine.ripper_engine import RipperEngine
from engine.scan_ops import _parse_drive_info, scan_disc

from tests.test_behavior_guards import _engine_cfg


# --------------------------------------------------------------------------
# Fake subprocess plumbing.
# --------------------------------------------------------------------------


class _FakeStdout:
    def __init__(self, lines: list[str]):
        self._lines = iter(line if line.endswith("\n") else line + "\n"
                           for line in lines)
        self.closed = False

    def readline(self) -> str:
        if self.closed:
            return ""
        try:
            return next(self._lines)
        except StopIteration:
            return ""

    def close(self) -> None:
        self.closed = True


class _FakeProc:
    def __init__(self, lines: list[str], returncode: int = 0):
        self.stdout = _FakeStdout(lines)
        self.returncode = returncode
        self.kill_called = False
        self.wait_called = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_called = True
        return self.returncode

    def kill(self) -> None:
        self.kill_called = True
        self.stdout.close()


def _patch_popen(monkeypatch, lines: list[str], returncode: int = 0) -> _FakeProc:
    fake = _FakeProc(lines, returncode=returncode)
    monkeypatch.setattr(
        "engine.scan_ops.subprocess.Popen",
        lambda *args, **kwargs: fake,
    )
    return fake


def _make_engine(**cfg_overrides: Any) -> RipperEngine:
    return RipperEngine(_engine_cfg(**cfg_overrides))


# --------------------------------------------------------------------------
# scan_disc — happy path
# --------------------------------------------------------------------------


def test_clean_scan_returns_titles_with_parsed_fields(monkeypatch):
    """One title with name, duration, chapters, and size populated; verify
    the returned title dict matches what each TINFO attr was supposed to set."""
    lines = [
        'CINFO:2,0,"Test Movie"',
        'CINFO:32,0,"VOLUME_ID_42"',
        'TINFO:0,2,0,"title_t00.mkv"',
        'TINFO:0,9,0,"1:30:00"',          # duration → 5400 seconds
        'TINFO:0,8,0,"12"',                # chapters
        'TINFO:0,11,0,"5368709120"',       # size → 5.00 GB
        'SINFO:0,0,6,0,"V_MPEG4/ISO/AVC"', # video stream codec
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    progress: list[int] = []
    logs: list[str] = []
    titles = scan_disc(engine, logs.append, progress.append)

    assert titles is not None
    assert len(titles) == 1
    t = titles[0]
    assert t["id"] == 0
    assert t["name"] == "title_t00.mkv"
    assert t["duration"] == "1:30:00"
    assert t["duration_seconds"] == 5400
    assert t["chapters"] == 12
    assert t["size_bytes"] == 5368709120
    assert "GB" in t["size"]
    assert t["streams"][0][6] == "V_MPEG4/ISO/AVC"
    assert t["_invalid"] is False
    # First TINFO line for a title bumps progress.
    assert progress  # at least one call


def test_clean_scan_sorts_titles_by_descending_duration(monkeypatch):
    """The function returns valid_titles sorted by -duration_seconds."""
    lines = [
        # Title 0: 1 hour
        'TINFO:0,9,0,"1:00:00"',
        'TINFO:0,11,0,"1000000000"',
        # Title 1: 2 hours
        'TINFO:1,9,0,"2:00:00"',
        'TINFO:1,11,0,"2000000000"',
        # Title 2: 30 minutes
        'TINFO:2,9,0,"0:30:00"',
        'TINFO:2,11,0,"500000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles is not None
    assert [t["id"] for t in titles] == [1, 0, 2]


def test_progress_increments_per_new_title_and_caps_at_90(monkeypatch):
    """on_progress is called with min(5 + title_count, 90) on each new TINFO."""
    # Spawn 100 distinct title ids — enough to exercise the cap.
    lines = []
    for tid in range(100):
        lines.append(f'TINFO:{tid},9,0,"0:01:00"')
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    progress: list[int] = []
    scan_disc(engine, lambda _m: None, progress.append)

    assert progress[0] == 6              # 5 + 1
    assert progress[-1] == 90            # cap
    assert max(progress) == 90
    assert all(p >= 6 for p in progress)


# --------------------------------------------------------------------------
# scan_disc — invalid / malformed inputs
# --------------------------------------------------------------------------


def test_tinfo_with_invalid_duration_marks_title_invalid_and_excludes_it(monkeypatch):
    """`val and dur_seconds <= 0` → _invalid=True. Empty val keeps duration 0
    but does NOT mark invalid (must have a non-empty val)."""
    lines = [
        'TINFO:0,9,0,"not-a-duration"',  # val present, parse → 0 → invalid
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles == []  # excluded by valid_titles filter


def test_tinfo_with_invalid_size_marks_title_invalid(monkeypatch):
    lines = [
        'TINFO:0,9,0,"1:30:00"',     # valid duration
        'TINFO:0,11,0,"garbage"',     # bad size → invalid
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles == []


def test_malformed_cinfo_is_silently_skipped(monkeypatch):
    """Parser splits CINFO body with maxsplit=2 (3 parts required).
    `CINFO:2` → 1 part → skipped. `CINFO:not-an-int,0,"x"` → ValueError
    on `int(parts[0])` → continue. Both must not crash."""
    lines = [
        'CINFO:2',                       # too few fields
        'CINFO:not-an-int,0,"foo"',      # ValueError on int parse
        'CINFO:2,0,"Real Title"',        # valid — proves parser still works after
        'TINFO:0,9,0,"1:00:00"',
        'TINFO:0,11,0,"1000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    logs: list[str] = []
    titles = scan_disc(engine, logs.append, lambda _p: None)

    assert titles is not None
    assert len(titles) == 1
    # The malformed lines did not leak as logs — the parser silently skipped.
    assert "CINFO:2" not in logs
    assert "CINFO:not-an-int,0,\"foo\"" not in logs


def test_malformed_tinfo_is_silently_skipped(monkeypatch):
    """TINFO needs 4 parts after splitting body with maxsplit=3."""
    lines = [
        'TINFO:0,9',                          # 2 parts — too few
        'TINFO:not-an-int,9,0,"1:00:00"',     # ValueError
        # Valid title afterwards proves parser recovered.
        'TINFO:0,9,0,"1:00:00"',
        'TINFO:0,11,0,"1000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles is not None
    assert len(titles) == 1
    assert titles[0]["id"] == 0


def test_sinfo_before_its_parent_tinfo_is_silently_skipped(monkeypatch):
    """SINFO has a `if tid not in titles: continue` guard — orphan SINFO
    must not crash and must not invent a title."""
    lines = [
        'SINFO:5,0,6,0,"V_MPEG4"',      # title 5 doesn't exist yet
        'TINFO:0,9,0,"1:00:00"',         # only title 0 actually defined
        'TINFO:0,11,0,"1000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles is not None
    assert [t["id"] for t in titles] == [0]
    # Orphan SINFO did not fabricate title 5 in the output.
    assert all(t["id"] != 5 for t in titles)


# --------------------------------------------------------------------------
# scan_disc — drive info via MSG → engine.last_drive_info
# --------------------------------------------------------------------------


def test_msg_with_libredrive_enabled_marks_drive_enabled(monkeypatch):
    lines = [
        'MSG:1005,0,1,"LibreDrive mode is enabled.","LibreDrive mode is enabled."',
        'TINFO:0,9,0,"1:00:00"',
        'TINFO:0,11,0,"1000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    scan_disc(engine, lambda _m: None, lambda _p: None)

    assert engine.last_drive_info["libre_drive"] == "enabled"


def test_msg_with_uhd_hint_marks_disc_type_uhd(monkeypatch):
    """When LibreDrive is *not* enabled but the disc is UHD, uhd_friendly
    must be False (per the post-loop heuristic)."""
    lines = [
        'MSG:1005,0,1,"This is an Ultra HD disc.","UHD detected"',
        'TINFO:0,9,0,"2:00:00"',
        'TINFO:0,11,0,"50000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    scan_disc(engine, lambda _m: None, lambda _p: None)

    assert engine.last_drive_info["disc_type"] == "UHD"
    assert engine.last_drive_info["uhd_friendly"] is False


def test_msg_with_too_few_fields_is_silently_skipped(monkeypatch):
    """MSG split with maxsplit=4 needs 5 parts. `MSG:1` has zero commas →
    1 part → silently skipped, must not crash, must not appear in drive info."""
    lines = [
        'MSG:1',                                              # too few
        'MSG:1005,0,1,"benign","benign"',                     # valid
        'TINFO:0,9,0,"1:00:00"',
        'TINFO:0,11,0,"1000000000"',
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles is not None
    assert len(titles) == 1


# --------------------------------------------------------------------------
# scan_disc — abort, non-zero exit, exception handling
# --------------------------------------------------------------------------


def test_abort_set_before_run_returns_none_and_kills_proc(monkeypatch):
    """Pre-set abort: the very first line read triggers the abort branch."""
    fake = _patch_popen(monkeypatch, ['CINFO:2,0,"Movie"'], returncode=0)
    engine = _make_engine()
    engine.abort_event.set()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles is None
    assert fake.kill_called is True


def test_non_zero_exit_returns_none_and_logs_failure(monkeypatch):
    _patch_popen(monkeypatch, ['CINFO:2,0,"Movie"'], returncode=42)
    engine = _make_engine()

    logs: list[str] = []
    titles = scan_disc(engine, logs.append, lambda _p: None)

    assert titles is None
    assert any("exit code 42" in m for m in logs)


def test_exception_during_scan_returns_none_and_is_swallowed(monkeypatch):
    """Anything raised inside the try block — including from Popen itself —
    must be caught: scan_disc returns None and logs `Scan failed: ...`."""
    def explode(*_args, **_kwargs):
        raise OSError("simulated subprocess.Popen failure")

    monkeypatch.setattr("engine.scan_ops.subprocess.Popen", explode)
    engine = _make_engine()

    logs: list[str] = []
    titles = scan_disc(engine, logs.append, lambda _p: None)

    assert titles is None
    assert any("Scan failed:" in m for m in logs)


# --------------------------------------------------------------------------
# scan_disc — empty / degenerate output
# --------------------------------------------------------------------------


def test_empty_scan_returns_empty_list(monkeypatch):
    """No titles, but rc=0: returns [] (not None). Note: in this case
    `titles` is empty, so the all-invalid diag warning does NOT fire."""
    _patch_popen(monkeypatch, [], returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles == []


def test_scan_with_only_invalid_titles_returns_empty_list(monkeypatch):
    """`titles` is non-empty but all are flagged _invalid → valid_titles
    is empty list. The function returns [] (not None) and emits a
    diag_record warning (we don't assert on diagnostics here, just the
    return shape)."""
    lines = [
        'TINFO:0,9,0,"not-a-duration"',  # title 0 invalid
        'TINFO:1,9,0,"also-bad"',         # title 1 invalid
    ]
    _patch_popen(monkeypatch, lines, returncode=0)
    engine = _make_engine()

    titles = scan_disc(engine, lambda _m: None, lambda _p: None)

    assert titles == []


# --------------------------------------------------------------------------
# _parse_drive_info — the helper called after the scan loop.
# Exercised indirectly above; these add direct unit coverage for branches
# that need many MSG variants.
# --------------------------------------------------------------------------


def test_parse_drive_info_libredrive_states():
    """Tri-state classifier — order matters: enabled/active is checked first,
    then possible/not-yet, then the unavailable synonyms. Test phrases must
    not contain "enabled" or "active" substrings unless that's the target
    state, because the first matching branch wins."""
    assert _parse_drive_info(
        ["LibreDrive mode is enabled."]
    )["libre_drive"] == "enabled"
    # "possible" alone must NOT contain "active" — the first branch matches
    # "active" anywhere in the line and wins. (Pins a real ordering quirk:
    # a phrase like "possible but not yet active" classifies as "enabled".)
    assert _parse_drive_info(
        ["LibreDrive support is possible — firmware patch may be needed."]
    )["libre_drive"] == "possible"
    assert _parse_drive_info(
        ["LibreDrive is not available on this drive."]
    )["libre_drive"] == "unavailable"
    # No LibreDrive mention → tri-state stays None.
    assert _parse_drive_info(["completely unrelated message"])["libre_drive"] is None


def test_parse_drive_info_active_wins_over_possible_when_both_appear():
    """Documents the ordering quirk: "active" / "enabled" check runs before
    "possible" / "not yet", so a phrase containing both classifies as
    "enabled". If the upstream classifier is ever rewritten to be more
    specific (e.g., only `... is enabled` rather than the substring),
    this test will fail and force a deliberate decision."""
    info = _parse_drive_info(["LibreDrive: possible but not yet active."])
    assert info["libre_drive"] == "enabled"


def test_parse_drive_info_uhd_with_libredrive_is_friendly():
    info = _parse_drive_info([
        "Detected Ultra HD disc.",
        "LibreDrive mode is enabled.",
    ])
    assert info["disc_type"] == "UHD"
    assert info["libre_drive"] == "enabled"
    assert info["uhd_friendly"] is True


def test_parse_drive_info_uhd_without_libredrive_is_unfriendly():
    info = _parse_drive_info(["Detected Ultra HD disc."])
    assert info["disc_type"] == "UHD"
    assert info["uhd_friendly"] is False


def test_parse_drive_info_bluray_does_not_overwrite_uhd():
    """Once disc_type is set to UHD, a later Blu-ray-mentioning MSG must
    not downgrade it (the elif checks `if info["disc_type"] is None`)."""
    info = _parse_drive_info([
        "Ultra HD disc detected.",
        "BDMV folder structure found.",
    ])
    assert info["disc_type"] == "UHD"
