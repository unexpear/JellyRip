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

    def run_next(self):
        if not self.jobs:
            return None
        job = self.jobs.pop(0)
        ret, log_path = self.engine.run_job(job)
        if ret == 0:
            self.completed.append((job, log_path))
        else:
            self.failed.append((job, log_path))
        return ret, log_path

    def run_all(self):
        results = []
        while self.jobs:
            results.append(self.run_next())
        return results
