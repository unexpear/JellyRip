from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, Protocol

from utils.session_result import normalize_session_result


AnalyzedFile = tuple[str, float, float]
AnalyzedFiles = list[AnalyzedFile]
SizeValidationStatus = Literal["pass", "warn", "hard_fail"]


LogFn = Callable[[str], None]
ReportFn = Callable[[str], None]


class AnalyzeFilesFn(Protocol):
    def __call__(
        self,
        files: Sequence[str],
        log_fn: LogFn,
    ) -> AnalyzedFiles | None: ...


class RetryEngineLike(Protocol):
    def cleanup_partial_files(self, rip_path: str, log_fn: LogFn) -> None: ...

    def rip_selected_titles(
        self,
        rip_path: str,
        selected_ids: Sequence[int],
        *,
        on_progress: Callable[[float], None],
        on_log: LogFn,
    ) -> tuple[bool, list[Any]]: ...

    def update_temp_metadata(self, rip_path: str, **metadata: Any) -> None: ...


class RetryGuiLike(Protocol):
    def set_status(self, status: str) -> None: ...

    def set_progress(self, value: float) -> None: ...


class RetryContextLike(Protocol):
    engine: RetryEngineLike
    gui: RetryGuiLike

    def log(self, msg: str) -> None: ...

    def report(self, msg: str) -> None: ...

    def _safe_glob(
        self,
        pattern: str,
        recursive: bool = False,
        timeout: float = 8.0,
        context: str = "glob",
    ) -> list[str]: ...

    def _warn_degraded_rips(self) -> None: ...

    def _normalize_rip_result(
        self,
        rip_path: str,
        success: bool,
        failed_titles: Sequence[Any] | None,
        pre_existing_files: frozenset[str] | None = None,
    ) -> tuple[bool, list[str]]: ...

    def _log_ripped_file_sizes(self, mkv_files: Sequence[str]) -> None: ...

    def _stabilize_ripped_files(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None = None,
    ) -> tuple[bool, bool]: ...

    def _log_expected_vs_actual_summary(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None,
    ) -> None: ...

    def _verify_expected_sizes(
        self,
        mkv_files: Sequence[str],
        expected_size_by_title: Mapping[int, int] | None,
    ) -> tuple[SizeValidationStatus, str]: ...


def _sum_file_sizes(
    files: Sequence[str],
    *,
    log_fn: LogFn,
) -> int:
    total = 0
    for path in files:
        try:
            total += os.path.getsize(path)
        except Exception as exc:
            log_fn(f"os.path.getsize failed: {exc}")
    return total


def compute_size_validation_status(
    actual_bytes: int,
    expected_bytes: int,
    *,
    hard_fail_ratio_pct: float,
    expected_size_ratio_pct: float,
) -> tuple[SizeValidationStatus, str, float]:
    if expected_bytes <= 0:
        return "pass", "no_expected_size", 1.0

    hard_ratio = max(0.10, min(0.95, float(hard_fail_ratio_pct) / 100.0))
    warn_ratio = max(hard_ratio, min(0.99, float(expected_size_ratio_pct) / 100.0))
    ratio = actual_bytes / expected_bytes if expected_bytes > 0 else 0.0

    if ratio < hard_ratio:
        return (
            "hard_fail",
            f"size too small: {ratio * 100:.1f}% of expected "
            f"(< {hard_ratio * 100:.0f}% hard floor)",
            ratio,
        )
    if ratio < warn_ratio:
        return (
            "warn",
            f"size below preferred threshold: {ratio * 100:.1f}% "
            f"(< {warn_ratio * 100:.0f}%)",
            ratio,
        )
    return "pass", f"size OK ({ratio * 100:.1f}%)", ratio


def verify_expected_sizes(
    mkv_files: Sequence[str],
    expected_size_by_title: Mapping[int, int] | None,
    *,
    safe_mode: bool,
    hard_fail_ratio_pct: float,
    expected_size_ratio_pct: float,
    log_fn: LogFn,
) -> tuple[SizeValidationStatus, str]:
    if not safe_mode:
        return "pass", "safe_mode_disabled"
    if not expected_size_by_title:
        return "pass", "no_expected_size"

    expected_total = sum(int(value or 0) for value in expected_size_by_title.values())
    actual_total = _sum_file_sizes(mkv_files, log_fn=log_fn)
    status, reason, ratio = compute_size_validation_status(
        actual_total,
        expected_total,
        hard_fail_ratio_pct=hard_fail_ratio_pct,
        expected_size_ratio_pct=expected_size_ratio_pct,
    )
    log_fn(
        "Size sanity (aggregate): expected "
        f"{expected_total / (1024**3):.2f} GB, actual "
        f"{actual_total / (1024**3):.2f} GB "
        f"({ratio * 100:.1f}%)"
    )
    if status == "hard_fail":
        log_fn(f"ERROR: {reason}")
    elif status == "warn":
        log_fn(f"WARNING: {reason}")
    return status, reason


def log_expected_vs_actual_summary(
    mkv_files: Sequence[str],
    expected_size_by_title: Mapping[int, int] | None,
    *,
    log_fn: LogFn,
) -> None:
    if not expected_size_by_title:
        return

    expected_total = sum(int(value or 0) for value in expected_size_by_title.values())
    if expected_total <= 0:
        return

    actual_total = _sum_file_sizes(mkv_files, log_fn=log_fn)
    pct = (actual_total / expected_total) * 100
    log_fn(
        "Expected total size: "
        f"{expected_total / (1024**3):.2f} GB | "
        f"Actual total size: {actual_total / (1024**3):.2f} GB "
        f"({pct:.1f}%)"
    )


def verify_container_integrity(
    mkv_files: Sequence[str],
    *,
    analyzed: AnalyzedFiles | None = None,
    analyze_files: AnalyzeFilesFn | None = None,
    expected_durations: Mapping[str, float] | None = None,
    expected_sizes: Mapping[str, int] | None = None,
    title_file_map: Mapping[int, Sequence[str]] | None = None,
    strict: bool,
    log_fn: LogFn,
    report_fn: ReportFn,
) -> bool:
    size_floor = 200 * 1024 * 1024
    short_title_seconds = 600

    if not mkv_files:
        return False

    log_fn("Container integrity check (ffprobe)...")
    analyzed_list: AnalyzedFiles = analyzed
    if analyzed_list is None:
        analyzed_list = analyze_files(mkv_files, log_fn) if analyze_files else None
    analyzed_list = analyzed_list or []

    if len(analyzed_list) != len(mkv_files):
        log_fn(
            "ERROR: Container integrity check incomplete "
            f"({len(analyzed_list)}/{len(mkv_files)} files analyzed)."
        )
        return False

    bad = [os.path.basename(path) for path, duration, _mb in analyzed_list if duration <= 0]
    if bad:
        log_fn(
            "ERROR: Container integrity check failed for: "
            + ", ".join(bad)
        )
        return False

    if not (expected_durations or expected_sizes):
        return True

    analyzed_lookup = {
        path: (duration, int(size_mb * 1024 * 1024))
        for path, duration, size_mb in analyzed_list
    }

    groups: list[tuple[int | str | None, list[str]]]
    if title_file_map:
        groups = [
            (title_id, [path for path in paths if path in analyzed_lookup])
            for title_id, paths in title_file_map.items()
        ]
        covered = {path for _, paths in groups for path in paths}
        for path in analyzed_lookup:
            if path not in covered:
                groups.append((None, [path]))
    else:
        groups = [(None, [path]) for path in mkv_files]

    warned_tids: set[int | str] = set()
    strict_fail = False

    for title_id, files in groups:
        if not files:
            continue
        if title_id is not None and title_id in warned_tids:
            continue

        total_duration = sum(
            analyzed_lookup[path][0] for path in files if path in analyzed_lookup
        )
        total_bytes = sum(
            analyzed_lookup[path][1] for path in files if path in analyzed_lookup
        )
        label = (
            os.path.basename(files[0])
            if len(files) == 1
            else f"Title {title_id} ({len(files)} files)"
            if title_id is not None
            else os.path.basename(files[0])
        )

        expected_duration = sum(
            (expected_durations or {}).get(path, 0) for path in files
        ) or None
        raw_expected_size = sum(
            (expected_sizes or {}).get(path, 0) for path in files
        )
        expected_size = raw_expected_size if raw_expected_size >= size_floor else None

        if not expected_duration or expected_duration <= 0:
            continue

        duration_ratio = total_duration / expected_duration if total_duration > 0 else 0.0
        size_ratio = total_bytes / expected_size if expected_size else None

        is_short = expected_duration < short_title_seconds
        severe_threshold = 0.4 if is_short else 0.5
        likely_threshold = 0.6 if is_short else 0.75
        minor_threshold = 0.85 if is_short else 0.9

        if duration_ratio >= minor_threshold:
            continue

        if title_id is not None:
            warned_tids.add(title_id)

        if duration_ratio < severe_threshold:
            if size_ratio is not None and size_ratio < severe_threshold:
                assert expected_size is not None
                report_fn(
                    f"TRUNCATION ERROR: {label} - "
                    f"duration {total_duration / 60:.1f} min "
                    f"(expected ~{expected_duration / 60:.1f} min, "
                    f"{duration_ratio * 100:.0f}%) AND "
                    f"size {total_bytes // (1024**2)} MB "
                    f"(expected ~{int(expected_size) // (1024**2)} MB, "
                    f"{size_ratio * 100:.0f}%) - "
                    f"both signals indicate corrupt/incomplete rip"
                )
                if strict:
                    strict_fail = True
            else:
                report_fn(
                    f"WARNING: Severe duration mismatch - {label}: "
                    f"actual {total_duration / 60:.1f} min, "
                    f"expected ~{expected_duration / 60:.1f} min "
                    f"({duration_ratio * 100:.0f}%) - possible truncation"
                )
                if strict:
                    strict_fail = True
        elif duration_ratio < likely_threshold:
            report_fn(
                f"WARNING: Likely truncation - {label}: "
                f"actual {total_duration / 60:.1f} min, "
                f"expected ~{expected_duration / 60:.1f} min "
                f"({duration_ratio * 100:.0f}%)"
                + (
                    f"; size also low ({size_ratio * 100:.0f}%)"
                    if (size_ratio is not None and size_ratio < likely_threshold)
                    else ""
                )
            )
            if strict:
                strict_fail = True
        else:
            report_fn(
                f"WARNING: Minor duration mismatch - {label}: "
                f"actual {total_duration / 60:.1f} min, "
                f"expected ~{expected_duration / 60:.1f} min "
                f"({duration_ratio * 100:.0f}%)"
            )

    if strict_fail:
        log_fn("ERROR: Strict mode - truncation warning escalated to failure.")
        return False

    return True


def normalize_rip_result(
    rip_path: str,
    success: bool,
    failed_titles: Sequence[Any] | None,
    *,
    pre_existing_files: frozenset[str] | None = None,
    safe_glob: Callable[..., list[str]],
    quick_ffprobe_ok: Callable[[str, LogFn], bool],
    abort_flag: bool,
    log_fn: LogFn,
) -> tuple[bool, list[str]]:
    excluded = frozenset(pre_existing_files or [])
    mkv_files = sorted(
        path for path in safe_glob(
            os.path.join(rip_path, "**", "*.mkv"),
            recursive=True,
            context="Enumerating rip outputs",
        )
        if path not in excluded
    )

    valid_files = [
        path for path in mkv_files
        if quick_ffprobe_ok(path, log_fn)
    ]

    if abort_flag:
        log_fn("Rip aborted - treating session as failure.")
    if failed_titles:
        log_fn(f"Titles failed: {failed_titles}")
    if not mkv_files:
        log_fn("No MKV files produced - treating as failure.")

    log_fn(
        "Failure gate: "
        f"abort={abort_flag}, "
        f"failed_titles={len(failed_titles or [])}, "
        f"files={len(mkv_files)}, valid={len(valid_files)}"
    )

    normalized = normalize_session_result(
        abort_flag,
        failed_titles,
        mkv_files,
        valid_files,
    )

    if len(valid_files) != len(mkv_files):
        log_fn("One or more MKV files are invalid - treating as failure.")
    if not normalized:
        return False, mkv_files

    return bool(success), mkv_files


def retry_rip_once_after_size_failure(
    context: RetryContextLike,
    rip_path: str,
    selected_ids: Sequence[int],
    expected_size_by_title: Mapping[int, int] | None,
) -> bool:
    context.log("Safe Mode: size sanity failed - retrying rip once automatically.")
    context.engine.cleanup_partial_files(rip_path, context.log)
    for pattern in ("**/*.mkv", "**/*.partial"):
        for path in context._safe_glob(
            os.path.join(rip_path, pattern),
            recursive=True,
            context="Cleaning retry artifacts",
        ):
            try:
                os.remove(path)
            except Exception as exc:
                context.log(f"os.remove failed: {exc}")

    context.gui.set_status("Ripping... (this may take 20-60 min)")
    pre_rip_mkvs = frozenset(
        context._safe_glob(
            os.path.join(rip_path, "**", "*.mkv"),
            recursive=True,
            context="Snapshotting pre-rip MKVs",
        )
    )
    success, failed_titles = context.engine.rip_selected_titles(
        rip_path,
        selected_ids,
        on_progress=context.gui.set_progress,
        on_log=context.log,
    )
    context._warn_degraded_rips()
    if failed_titles:
        context.report(f"Retry: titles failed - {failed_titles}")
    success, mkv_files = context._normalize_rip_result(
        rip_path,
        success,
        failed_titles,
        pre_rip_mkvs,
    )
    if not success:
        return False

    context.engine.update_temp_metadata(rip_path, status="ripped")
    context._log_ripped_file_sizes(mkv_files)
    stabilized, timed_out = context._stabilize_ripped_files(
        mkv_files,
        expected_size_by_title,
    )
    if not stabilized:
        if timed_out:
            context.log("Retry stabilization failed: timed out.")
        return False

    context._log_expected_vs_actual_summary(
        mkv_files,
        expected_size_by_title,
    )
    status, _reason = context._verify_expected_sizes(
        mkv_files,
        expected_size_by_title,
    )
    return status == "pass"
