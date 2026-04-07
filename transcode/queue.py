from typing import List
from .engine import TranscodeEngine

class TranscodeQueue:
    def __init__(self, log_dir: str = "logs"):
        self.engine = TranscodeEngine(log_dir=log_dir)
        self.jobs = []
        self.completed = []
        self.failed = []

    def add_job(self, job):
        self.jobs.append(job)

    def run_next(self, feedback_cb=None):
        if not self.jobs:
            return None
        job = self.jobs.pop(0)
        if feedback_cb:
            feedback_cb(f"Starting job: {getattr(job, 'input_path', job)}")
        ret, log_path = self.engine.run_job(job)
        if ret == 0:
            self.completed.append((job, log_path))
            if feedback_cb:
                feedback_cb(f"Completed: {getattr(job, 'output_path', job)}")
        else:
            self.failed.append((job, log_path))
            if feedback_cb:
                feedback_cb(f"FAILED: {getattr(job, 'input_path', job)} (see {log_path})")
        return ret, log_path

    def run_all(self, feedback_cb=None):
        results = []
        total = len(self.jobs)
        count = 0
        while self.jobs:
            count += 1
            if feedback_cb:
                feedback_cb(f"Processing job {count} of {total}")
            results.append(self.run_next(feedback_cb=feedback_cb))
        if feedback_cb:
            feedback_cb(f"Batch complete. Success: {len(self.completed)}, Failed: {len(self.failed)}")
        return results
