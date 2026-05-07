"""Regression test for the v1-blocker the smoke bot caught
2026-05-04 (after the ``-r`` fix had already landed).

**The bug:** ``RipperEngine.run_job`` defined its own ``on_log`` and
``on_progress`` callbacks that swallowed every log line into a local
list and dropped every progress event entirely.  When
``_run_disc_inner`` called ``run_job(job)``, the controller's
``self.log`` (live GUI log) and ``self.gui.set_progress`` (progress
bar) were **never invoked** for the duration of the rip — typically
17–40 minutes of total silence in the UI even though MakeMKV was
emitting progress fine.

The smoke bot found it because:
1. The ``-r`` fix (2026-05-04 morning) made MakeMKV emit
   ``PRGV:`` / ``PRGT:`` lines as expected.
2. But the rebuilt ``.exe`` STILL showed zero progress in the live
   log on a real-disc rip.
3. Tracing the controller flow showed ``_run_disc_inner`` calls
   ``engine.run_job(job)`` — not the directly-callable
   ``rip_selected_titles``.  ``run_job`` was the swallowing wrapper.

**The fix:** ``run_job`` now accepts optional ``on_log`` /
``on_progress`` keyword args and forwards them to the underlying
rip operation.  When omitted, behavior is the legacy "capture into
``Result.outputs``, drop progress" — preserves test compatibility
where loggers aren't available.

Pinned by these tests so a future refactor can't silently
re-introduce the swallowing wrapper.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.ripper_engine import Job, Result, RipperEngine

from tests.test_behavior_guards import _engine_cfg


def _engine() -> RipperEngine:
    return RipperEngine(_engine_cfg())


def test_run_job_forwards_on_log_to_rip_all_titles(monkeypatch):
    """``run_job(job, on_log=...)`` must invoke the supplied logger
    for every ``on_log`` call from ``rip_all_titles``."""
    captured: list[str] = []

    def fake_rip_all(rip_path, on_progress, on_log):
        on_log("Rip attempt 1/3 (flags: --cache=1024)")
        on_log("Ripping: 25%")
        on_log("Ripping: 50%")
        on_log("MakeMKV exit code: 0")
        return True

    eng = _engine()
    monkeypatch.setattr(eng, "rip_all_titles", fake_rip_all)

    result = eng.run_job(
        Job(source="all", output="/tmp/x", profile="default"),
        on_log=captured.append,
    )

    assert result.success is True
    # Every log line the rip path emitted reached the supplied logger.
    assert "Rip attempt 1/3 (flags: --cache=1024)" in captured
    assert "Ripping: 25%" in captured
    assert "Ripping: 50%" in captured
    assert "MakeMKV exit code: 0" in captured


def test_run_job_forwards_on_log_to_rip_selected_titles(monkeypatch):
    """Same contract for the ``rip_selected_titles`` path — which
    is what ``_run_disc_inner`` actually exercises (selected-title
    rip from the disc-tree dialog)."""
    captured: list[str] = []

    def fake_rip_selected(rip_path, title_ids, on_progress, on_log):
        _n = len(title_ids)
        _noun = "title" if _n == 1 else "titles"
        on_log(f"Ripping {_n} selected {_noun} to: {rip_path}")
        on_log("Ripping title 1 (1/1)...")
        on_log("Ripping: 33%  ~12m 30s remaining")
        on_log("MakeMKV exit code: 0")
        return True, []

    eng = _engine()
    monkeypatch.setattr(eng, "rip_selected_titles", fake_rip_selected)

    result = eng.run_job(
        Job(source="0", output="/tmp/x", profile="default"),
        on_log=captured.append,
    )

    assert result.success is True
    assert any("Ripping 1 selected title" in line for line in captured)
    assert any("Ripping title 1 (1/1)" in line for line in captured)
    assert any("Ripping: 33%" in line for line in captured)


def test_run_job_forwards_on_progress(monkeypatch):
    """The progress bar setter must receive every PRGV-derived
    pct value.  Pre-fix, ``run_job`` hardwired
    ``on_progress=lambda _p: None``, so the bar never moved during
    a rip."""
    progress_values: list[int] = []

    def fake_rip_selected(rip_path, title_ids, on_progress, on_log):
        # Simulate PRGV-driven progress events from MakeMKV.
        for pct in (0, 25, 50, 75, 100):
            on_progress(pct)
        return True, []

    eng = _engine()
    monkeypatch.setattr(eng, "rip_selected_titles", fake_rip_selected)

    eng.run_job(
        Job(source="0", output="/tmp/x", profile="default"),
        on_progress=progress_values.append,
    )

    assert progress_values == [0, 25, 50, 75, 100]


def test_run_job_without_callbacks_falls_back_to_outputs_capture(monkeypatch):
    """Default behavior (no callbacks supplied) keeps the legacy
    contract: ``on_log`` lines land in ``Result.outputs``, progress
    is silently dropped.  Useful for tests / scripts that don't
    have a live UI."""
    def fake_rip_selected(rip_path, title_ids, on_progress, on_log):
        on_log("Ripping title 1 (1/1)...")
        on_log("MakeMKV exit code: 0")
        # progress events with no listener — must not raise
        on_progress(50)
        return True, []

    eng = _engine()
    monkeypatch.setattr(eng, "rip_selected_titles", fake_rip_selected)

    result = eng.run_job(
        Job(source="0", output="/tmp/x", profile="default"),
    )

    assert result.success is True
    # Captured into the Result for callers that didn't supply on_log.
    assert any("Ripping title 1 (1/1)" in line for line in result.outputs)
    assert any("MakeMKV exit code: 0" in line for line in result.outputs)


def test_run_job_on_log_also_captures_into_outputs(monkeypatch):
    """Belt-and-suspenders: when on_log IS supplied, lines still
    also land in Result.outputs.  This means a caller that wants
    both the live stream AND the post-mortem record gets them
    without a second callback layer."""
    live_lines: list[str] = []

    def fake_rip_selected(rip_path, title_ids, on_progress, on_log):
        on_log("Ripping title 1 (1/1)...")
        return True, []

    eng = _engine()
    monkeypatch.setattr(eng, "rip_selected_titles", fake_rip_selected)

    result = eng.run_job(
        Job(source="0", output="/tmp/x", profile="default"),
        on_log=live_lines.append,
    )

    assert "Ripping title 1 (1/1)..." in live_lines
    assert any("Ripping title 1 (1/1)" in line for line in result.outputs)


def test_run_job_no_title_ids_short_circuits():
    """Defensive: empty title-ID source returns failure without
    invoking the rip.  Pinned because this path predates the
    callback fix and shouldn't regress."""
    eng = _engine()
    result = eng.run_job(
        Job(source="", output="/tmp/x", profile="default"),
    )
    assert result.success is False
    assert "no-title-ids" in result.errors


def test_run_job_all_calls_rip_all_titles_path(monkeypatch):
    """Sanity: ``source='all'`` routes to ``rip_all_titles``,
    not ``rip_selected_titles``.  Pinned because the dispatch is
    the only thing distinguishing the two job shapes; a refactor
    that crossed wires would silently rip wrong titles."""
    calls: list[str] = []

    def fake_all(rip_path, on_progress, on_log):
        calls.append("rip_all_titles")
        return True

    def fake_selected(rip_path, title_ids, on_progress, on_log):
        calls.append("rip_selected_titles")
        return True, []

    eng = _engine()
    monkeypatch.setattr(eng, "rip_all_titles", fake_all)
    monkeypatch.setattr(eng, "rip_selected_titles", fake_selected)

    eng.run_job(Job(source="all", output="/tmp/x", profile="default"))
    assert calls == ["rip_all_titles"]
