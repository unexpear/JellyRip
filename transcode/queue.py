from .engine import (
    FFMPEG_SOURCE_MODE_SAFE_COPY,
    TranscodeEngine,
    normalize_ffmpeg_source_mode,
)


def _safe_progress_event(progress_cb, payload):
    if not callable(progress_cb):
        return
    try:
        progress_cb(payload)
    except Exception:
        return


def _job_percent_from_event(job, event) -> float | None:
    if not isinstance(event, dict):
        return None
    raw_percent = event.get("percent")
    if not isinstance(raw_percent, (int, float)):
        return None
    percent = max(0.0, min(100.0, float(raw_percent)))
    backend = str(getattr(job, "backend", "ffmpeg") or "ffmpeg").strip().lower()
    if backend != "ffmpeg":
        return percent

    metadata = getattr(job, "metadata", {})
    source_mode = normalize_ffmpeg_source_mode(
        metadata.get("ffmpeg_source_mode") if isinstance(metadata, dict) else None
    )
    copy_weight = 25.0 if source_mode == FFMPEG_SOURCE_MODE_SAFE_COPY else 0.0
    encode_weight = 100.0 - copy_weight
    phase = str(event.get("phase", "") or "").strip().lower()

    if phase == "copy":
        if copy_weight <= 0:
            return percent
        return (percent / 100.0) * copy_weight
    if phase == "encode":
        return copy_weight + ((percent / 100.0) * encode_weight)
    if phase in {"prepare", "launch"}:
        return copy_weight if copy_weight > 0 else 0.0
    return percent


class TranscodeQueue:
    def __init__(
        self,
        log_dir: str = "logs",
        ffmpeg_exe: str = "ffmpeg",
        ffprobe_exe: str = "",
        handbrake_exe: str = "HandBrakeCLI",
        ffmpeg_source_mode: str = FFMPEG_SOURCE_MODE_SAFE_COPY,
        temp_root: str | None = None,
    ):
        self.engine = TranscodeEngine(
            log_dir=log_dir,
            ffmpeg_exe=ffmpeg_exe,
            ffprobe_exe=ffprobe_exe,
            handbrake_exe=handbrake_exe,
            ffmpeg_source_mode=ffmpeg_source_mode,
            temp_root=temp_root,
        )
        self.jobs = []
        self.completed = []
        self.failed = []

    def add_job(self, job):
        self.jobs.append(job)

    def run_next(self, feedback_cb=None, progress_cb=None):
        if not self.jobs:
            return None
        total_jobs = len(self.jobs) + len(self.completed) + len(self.failed)
        job = self.jobs.pop(0)
        current_index = len(self.completed) + len(self.failed) + 1
        if feedback_cb:
            feedback_cb(f"Starting job: {getattr(job, 'input_path', job)}")

        def _engine_progress(event):
            payload = dict(event or {})
            payload.setdefault("job_index", current_index)
            payload.setdefault("job_total", total_jobs)
            payload.setdefault("input_path", getattr(job, "input_path", ""))
            payload.setdefault("output_path", getattr(job, "output_path", ""))
            job_percent = _job_percent_from_event(job, payload)
            if job_percent is not None and total_jobs > 0:
                payload["job_percent"] = job_percent
                payload["overall_percent"] = (
                    ((current_index - 1) + (job_percent / 100.0)) / total_jobs
                ) * 100.0
            _safe_progress_event(progress_cb, payload)

        ret, log_path = self.engine.run_job(
            job,
            feedback_cb=feedback_cb,
            progress_cb=_engine_progress,
        )
        if ret == 0:
            self.completed.append((job, log_path))
            if feedback_cb:
                feedback_cb(f"Completed: {getattr(job, 'output_path', job)}")
        else:
            self.failed.append((job, log_path))
            if feedback_cb:
                feedback_cb(f"FAILED: {getattr(job, 'input_path', job)} (see {log_path})")

        final_percent = (
            ((current_index - 1) + 1.0) / total_jobs
        ) * 100.0 if total_jobs > 0 else 100.0
        _safe_progress_event(
            progress_cb,
            {
                "phase": "complete" if ret == 0 else "failed",
                "percent": 100.0,
                "job_percent": 100.0,
                "overall_percent": final_percent,
                "job_index": current_index,
                "job_total": total_jobs,
                "input_path": getattr(job, "input_path", ""),
                "output_path": getattr(job, "output_path", ""),
                "message": (
                    f"Completed: {getattr(job, 'output_path', job)}"
                    if ret == 0
                    else f"FAILED: {getattr(job, 'input_path', job)}"
                ),
            },
        )
        return ret, log_path

    def run_all(self, feedback_cb=None, progress_cb=None):
        results = []
        total = len(self.jobs)
        count = 0
        while self.jobs:
            count += 1
            if feedback_cb:
                feedback_cb(f"Processing job {count} of {total}")
            results.append(self.run_next(feedback_cb=feedback_cb, progress_cb=progress_cb))
        if feedback_cb:
            feedback_cb(f"Batch complete. Success: {len(self.completed)}, Failed: {len(self.failed)}")
        return results
