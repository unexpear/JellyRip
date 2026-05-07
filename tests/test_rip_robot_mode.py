"""Pin that every MakeMKV rip command includes ``-r`` (robot mode).

**Why this test exists:** the smoke bot caught a class of bug
2026-05-04 where the rip command in ``engine/rip_ops.py`` was
missing ``-r``.  Without it, MakeMKV emits human-readable text
instead of ``PRGV:`` / ``PRGT:`` / ``PRGC:`` / ``MSG:`` lines, and
``RipperEngine._run_rip_process`` silently drops every line that
doesn't start with one of those four prefixes.

The user-visible symptom: rip looks "hung" — no progress bar
updates, no "Ripping: X%" log lines — even though MakeMKV is
happily writing bytes to disk.  The reader's stall watchdog
doesn't fire either, because the reader IS receiving lines (just
ignoring them), so ``last_output`` keeps resetting.

Bytes flow correctly to disk regardless; this is a pure
visibility regression.  But it makes the app feel broken on every
rip path, so we pin it.

This test is intentionally a static / source-level check rather
than a behavior test against the live engine.  Behavior tests
would need a fake makemkvcon, drive state, and the full retry
loop machinery — too expensive for what's a simple "is the flag
in the command" guarantee.  Static AST inspection catches the
regression with zero runtime cost.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_REPO_ROOT = Path(__file__).resolve().parent.parent
_RIP_OPS = _REPO_ROOT / "engine" / "rip_ops.py"


def _rip_op_cmd_assignments() -> list[tuple[str, str]]:
    """Walk ``engine/rip_ops.py`` and return every ``cmd = (...)``
    assignment whose RHS string mentions ``"mkv"`` (the makemkvcon
    rip subcommand — distinct from ``"info"`` for scan).

    Returns a list of ``(function_name, source_text)`` so failures
    can pinpoint exactly which rip path is missing ``-r``.
    """
    text = _RIP_OPS.read_text(encoding="utf-8")
    tree = ast.parse(text)

    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # Walk inside the function body for ``cmd = (...)``
        # assignments.  ``ast.walk`` recurses into nested blocks
        # (``for``/``if``), which is what we want — the
        # ``rip_selected_titles`` cmd lives inside a nested loop.
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Assign):
                continue
            if not (
                len(sub.targets) == 1
                and isinstance(sub.targets[0], ast.Name)
                and sub.targets[0].id == "cmd"
            ):
                continue
            # Reconstruct the literal source for the assignment
            # so the failure message can show what was wrong.
            try:
                source_chunk = ast.get_source_segment(text, sub)
            except Exception:
                source_chunk = "<source segment unavailable>"
            if source_chunk and '"mkv"' in source_chunk:
                out.append((node.name, source_chunk))
    return out


def test_rip_ops_has_at_least_three_mkv_cmd_assignments():
    """Sanity check: there should be three rip cmd builders —
    ``rip_preview_title``, ``rip_all_titles``, and
    ``rip_selected_titles``.  If any of those go missing entirely
    it's also a problem (different from the ``-r`` regression but
    worth flagging here so it doesn't slip past)."""
    assignments = _rip_op_cmd_assignments()
    fn_names = {fn for fn, _ in assignments}
    assert {
        "rip_preview_title",
        "rip_all_titles",
        "rip_selected_titles",
    }.issubset(fn_names), (
        f"expected cmd builders for the three rip paths; "
        f"found in: {sorted(fn_names)}"
    )


def test_every_rip_cmd_includes_robot_flag():
    """Every ``cmd = (...)`` block that builds a makemkvcon ``mkv``
    invocation must place ``"-r"`` somewhere before ``"mkv"`` in
    the argv list.

    This is what gets MakeMKV to emit ``PRGV:`` progress lines
    that ``_run_rip_process`` parses.  Without it, the rip looks
    hung because all output is silently dropped.
    """
    assignments = _rip_op_cmd_assignments()
    assert assignments, "no rip cmd assignments found at all"

    failures: list[str] = []
    for fn_name, source_chunk in assignments:
        # Robust check: the source chunk must contain ``"-r"``
        # AND that ``"-r"`` must precede the ``"mkv"`` literal in
        # the source text.  Order in the argv list mirrors
        # textual order in the source — an out-of-order ``-r``
        # would be a real regression we want to catch.
        if '"-r"' not in source_chunk:
            failures.append(
                f"  in {fn_name}(): missing '-r' flag\n"
                f"  cmd source:\n    {source_chunk!r}"
            )
            continue
        r_idx = source_chunk.index('"-r"')
        mkv_idx = source_chunk.index('"mkv"')
        if r_idx > mkv_idx:
            failures.append(
                f"  in {fn_name}(): '-r' appears AFTER 'mkv' — "
                f"order matters; '-r' must come first\n"
                f"  cmd source:\n    {source_chunk!r}"
            )

    if failures:
        msg = (
            "rip cmd(s) missing '-r' (robot mode) flag — without "
            "it MakeMKV emits human-readable text instead of the "
            "PRGV/PRGT/PRGC/MSG lines our parser handles, so the "
            "rip looks 'hung' even though bytes are writing fine.\n\n"
            + "\n\n".join(failures)
            + "\n\nFix: insert '-r' between global_args and "
            "['mkv', ...] in each rip cmd builder in "
            "engine/rip_ops.py.  See "
            "tests/test_rip_robot_mode.py docstring for context."
        )
        pytest.fail(msg)


def test_scan_paths_already_use_robot_flag():
    """Sibling guard: the scan paths already correctly include
    ``-r`` (this is what made the scan part of the smoke pass
    work while the rip part appeared hung).  Pinned here so a
    future refactor that drops ``-r`` from scan also surfaces
    immediately — same class of bug, just on the other path."""
    scan_ops = (_REPO_ROOT / "engine" / "scan_ops.py").read_text(encoding="utf-8")
    # The single rip-time scan in scan_ops.py.
    assert re.search(
        r'\["-r",\s*"info"', scan_ops
    ), "engine/scan_ops.py:scan_disc lost its '-r' before 'info' flag"

    ripper_engine = (
        _REPO_ROOT / "engine" / "ripper_engine.py"
    ).read_text(encoding="utf-8")
    # Three info-mode invocations in ripper_engine.py — drive
    # probe, deep probe, post-rip probe.  Each must keep '-r'.
    info_with_r_count = len(
        re.findall(r'\["-r",\s*"info"', ripper_engine)
    )
    assert info_with_r_count >= 3, (
        f"engine/ripper_engine.py should have at least 3 "
        f'["-r", "info"...] invocations; found {info_with_r_count}.'
    )
