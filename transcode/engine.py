# Transcode module
# Provides: ProfileLoader, TranscodeProfile, ProfileValidationError


import subprocess
import os
import time
from .ffmpeg_builder import FFmpegBuilder
from .profiles import TranscodeProfile
class TranscodeEngine:
	def __init__(self, log_dir: str = "logs"):
		self.log_dir = log_dir
		os.makedirs(self.log_dir, exist_ok=True)

	def run_job(self, job, dry_run=False):
		"""
		job: TranscodeJob (from core/pipeline.py)
		Logs: full command, all output, errors, and job metadata for every job.
		"""
		builder = FFmpegBuilder(job.profile, job.input_path, job.output_path, job.metadata)
		cmd = builder.build_command()
		timestamp = time.strftime("%Y%m%d_%H%M%S")
		log_path = os.path.join(self.log_dir, f"transcode_{timestamp}.txt")
		if dry_run:
			print("[DRY RUN] Command:", " ".join(cmd))
			return cmd
		try:
			with open(log_path, "w", encoding="utf-8") as logf:
				logf.write("COMMAND: " + " ".join(cmd) + "\n")
				logf.write(f"INPUT: {job.input_path}\nOUTPUT: {job.output_path}\nPROFILE: {getattr(job.profile, 'name', '')}\n")
				logf.write(f"METADATA: {repr(getattr(job, 'metadata', {}))}\n\n")
				logf.flush()
				proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
				for line in proc.stdout:
					logf.write(line)
					logf.flush()
				proc.wait()
				logf.write(f"\nExit code: {proc.returncode}\n")
				logf.flush()
			return proc.returncode, log_path
		except Exception as e:
			with open(log_path, "a", encoding="utf-8") as logf:
				logf.write(f"\nERROR: {repr(e)}\n")
			return -1, log_path
