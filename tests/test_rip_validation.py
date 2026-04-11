from __future__ import annotations

import glob
from pathlib import Path
from typing import Any, Sequence

from controller.rip_validation import (
    compute_size_validation_status,
    normalize_rip_result,
    retry_rip_once_after_size_failure,
    verify_expected_sizes,
)


def test_compute_size_validation_status_uses_configured_thresholds():
    status, _reason, ratio = compute_size_validation_status(
        39,
        100,
        hard_fail_ratio_pct=40,
        expected_size_ratio_pct=70,
    )
    assert status == "hard_fail"
    assert ratio == 0.39

    status, _reason, ratio = compute_size_validation_status(
        50,
        100,
        hard_fail_ratio_pct=40,
        expected_size_ratio_pct=70,
    )
    assert status == "warn"
    assert ratio == 0.5

    status, _reason, ratio = compute_size_validation_status(
        80,
        100,
        hard_fail_ratio_pct=40,
        expected_size_ratio_pct=70,
    )
    assert status == "pass"
    assert ratio == 0.8


def test_verify_expected_sizes_reports_warning(tmp_path):
    target = tmp_path / "output.mkv"
    target.write_bytes(b"x" * 60)
    messages: list[str] = []

    status, reason = verify_expected_sizes(
        [str(target)],
        {0: 100},
        safe_mode=True,
        hard_fail_ratio_pct=40,
        expected_size_ratio_pct=70,
        log_fn=messages.append,
    )

    assert status == "warn"
    assert "below preferred threshold" in reason
    assert any("Size sanity (aggregate)" in line for line in messages)
    assert any("WARNING:" in line for line in messages)


def test_normalize_rip_result_ignores_preexisting_files(tmp_path):
    old_file = tmp_path / "old.mkv"
    new_file = tmp_path / "new.mkv"
    old_file.write_text("old")
    new_file.write_text("new")
    messages: list[str] = []

    success, mkv_files = normalize_rip_result(
        str(tmp_path),
        True,
        [],
        pre_existing_files=frozenset({str(old_file)}),
        safe_glob=lambda pattern, **kwargs: glob.glob(
            pattern,
            recursive=bool(kwargs.get("recursive", False)),
        ),
        quick_ffprobe_ok=lambda path, _log_fn: Path(path).name == "new.mkv",
        abort_flag=False,
        log_fn=messages.append,
    )

    assert success is True
    assert mkv_files == [str(new_file)]
    assert any("Failure gate" in line for line in messages)


class _FakeRetryEngine:
    def __init__(self, rip_path: Path) -> None:
        self._rip_path = rip_path
        self.cleanup_calls: list[str] = []
        self.metadata_updates: list[tuple[str, dict[str, Any]]] = []
        self.rip_calls: list[tuple[str, list[int]]] = []

    def cleanup_partial_files(self, rip_path: str, _log_fn) -> None:
        self.cleanup_calls.append(rip_path)

    def rip_selected_titles(
        self,
        rip_path: str,
        selected_ids: Sequence[int],
        *,
        on_progress,
        on_log,
    ) -> tuple[bool, list[Any]]:
        self.rip_calls.append((rip_path, list(selected_ids)))
        Path(rip_path, "fresh.mkv").write_text("fresh")
        on_progress(50.0)
        on_log("retry rip invoked")
        return True, []

    def update_temp_metadata(self, rip_path: str, **metadata: Any) -> None:
        self.metadata_updates.append((rip_path, metadata))


class _FakeRetryGui:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.progress_values: list[float] = []

    def set_status(self, status: str) -> None:
        self.statuses.append(status)

    def set_progress(self, value: float) -> None:
        self.progress_values.append(value)


class _FakeRetryContext:
    def __init__(self, rip_path: Path) -> None:
        self.engine = _FakeRetryEngine(rip_path)
        self.gui = _FakeRetryGui()
        self.messages: list[str] = []
        self.reports: list[str] = []
        self.warned = False
        self.logged_sizes: list[list[str]] = []
        self.stabilized: list[tuple[list[str], dict[int, int] | None]] = []
        self.summaries: list[tuple[list[str], dict[int, int] | None]] = []
        self.verified: list[tuple[list[str], dict[int, int] | None]] = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)

    def report(self, msg: str) -> None:
        self.reports.append(msg)

    def _safe_glob(
        self,
        pattern: str,
        recursive: bool = False,
        timeout: float = 8.0,
        context: str = "glob",
    ) -> list[str]:
        _ = timeout, context
        return glob.glob(pattern, recursive=recursive)

    def _warn_degraded_rips(self) -> None:
        self.warned = True

    def _normalize_rip_result(
        self,
        rip_path: str,
        success: bool,
        failed_titles: Sequence[Any] | None,
        pre_existing_files: frozenset[str] | None = None,
    ) -> tuple[bool, list[str]]:
        return normalize_rip_result(
            rip_path,
            success,
            failed_titles,
            pre_existing_files=pre_existing_files,
            safe_glob=self._safe_glob,
            quick_ffprobe_ok=lambda path, _log_fn: Path(path).name == "fresh.mkv",
            abort_flag=False,
            log_fn=self.log,
        )

    def _log_ripped_file_sizes(self, mkv_files: Sequence[str]) -> None:
        self.logged_sizes.append(list(mkv_files))

    def _stabilize_ripped_files(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: dict[int, int] | None = None,
    ) -> tuple[bool, bool]:
        self.stabilized.append((list(mkv_files), expected_size_by_title))
        return True, False

    def _log_expected_vs_actual_summary(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: dict[int, int] | None,
    ) -> None:
        self.summaries.append((list(mkv_files), expected_size_by_title))

    def _verify_expected_sizes(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: dict[int, int] | None,
    ) -> tuple[str, str]:
        self.verified.append((list(mkv_files), expected_size_by_title))
        return "pass", "size OK"


def test_retry_rip_once_after_size_failure_retries_and_revalidates(tmp_path):
    stale_mkv = tmp_path / "stale.mkv"
    stale_partial = tmp_path / "stale.partial"
    stale_mkv.write_text("old")
    stale_partial.write_text("old")
    context = _FakeRetryContext(tmp_path)

    result = retry_rip_once_after_size_failure(
        context,
        str(tmp_path),
        [1, 2],
        {1: 1000},
    )

    assert result is True
    assert stale_mkv.exists() is False
    assert stale_partial.exists() is False
    assert (tmp_path / "fresh.mkv").exists() is True
    assert context.engine.cleanup_calls == [str(tmp_path)]
    assert context.engine.rip_calls == [(str(tmp_path), [1, 2])]
    assert context.engine.metadata_updates == [
        (str(tmp_path), {"status": "ripped"})
    ]
    assert context.gui.statuses == ["Ripping... (this may take 20-60 min)"]
    assert context.gui.progress_values == [50.0]
    assert context.warned is True
    assert len(context.logged_sizes) == 1
    assert len(context.stabilized) == 1
    assert len(context.summaries) == 1
    assert len(context.verified) == 1
