import os
import shutil
import subprocess
import tempfile
import time
from .ffmpeg_builder import FFmpegBuilder
from .handbrake_builder import HandBrakeBuilder


FFMPEG_SOURCE_MODE_SAFE_COPY = "safe_copy"
FFMPEG_SOURCE_MODE_FAST_DIRECT = "fast_direct"


def normalize_ffmpeg_source_mode(value: str | None) -> str:
	token = str(value or "").strip().lower()
	if token in {FFMPEG_SOURCE_MODE_FAST_DIRECT, "fast", "direct", "read_original"}:
		return FFMPEG_SOURCE_MODE_FAST_DIRECT
	return FFMPEG_SOURCE_MODE_SAFE_COPY


def describe_ffmpeg_source_mode(value: str | None) -> str:
	mode = normalize_ffmpeg_source_mode(value)
	if mode == FFMPEG_SOURCE_MODE_FAST_DIRECT:
		return (
			"Reads the original MKV directly and still writes a separate output file. "
			"Faster and lighter on free space, but FFmpeg works against the original path during the transcode."
		)
	return (
		"Copies the source MKV to a temporary working file before the transcode starts. "
		"Safest for the original file, but it needs extra free space roughly equal to the source size."
	)


class TranscodeEngine:
	def __init__(
		self,
		log_dir: str = "logs",
		ffmpeg_exe: str = "ffmpeg",
		handbrake_exe: str = "HandBrakeCLI",
		ffmpeg_source_mode: str = FFMPEG_SOURCE_MODE_SAFE_COPY,
	):
		self.log_dir = log_dir
		self.ffmpeg_exe = ffmpeg_exe or "ffmpeg"
		self.handbrake_exe = handbrake_exe or "HandBrakeCLI"
		self.ffmpeg_source_mode = normalize_ffmpeg_source_mode(
			ffmpeg_source_mode
		)
		os.makedirs(self.log_dir, exist_ok=True)

	def _build_command(self, job, *, input_path: str | None = None):
		effective_input_path = input_path or job.input_path
		backend = getattr(job, "backend", "ffmpeg")
		if backend == "handbrake":
			builder = HandBrakeBuilder(
				effective_input_path,
				job.output_path,
				getattr(job, "backend_options", {}).get("preset", "Fast 1080p30"),
				getattr(job, "metadata", {}),
				executable_path=self.handbrake_exe,
			)
			return builder.build_command()

		if getattr(job, "profile", None) is None:
			raise ValueError("FFmpeg transcode jobs require a profile.")
		builder = FFmpegBuilder(
			job.profile,
			effective_input_path,
			job.output_path,
			job.metadata,
			executable_path=self.ffmpeg_exe,
		)
		return builder.build_command()

	def _stage_ffmpeg_input_copy(self, job, logf):
		source_path = os.path.normpath(str(getattr(job, "input_path", "") or ""))
		if not source_path:
			raise ValueError("FFmpeg transcode jobs require an input path.")
		if not os.path.isfile(source_path):
			raise FileNotFoundError(f"FFmpeg source file was not found: {source_path}")

		output_parent = os.path.dirname(os.path.normpath(str(getattr(job, "output_path", "") or "")))
		if output_parent:
			os.makedirs(output_parent, exist_ok=True)
		staging_root = output_parent if output_parent else tempfile.gettempdir()
		staging_dir = tempfile.mkdtemp(prefix="JellyRipFFmpeg_", dir=staging_root)
		staged_input_path = os.path.join(staging_dir, os.path.basename(source_path))
		logf.write(f"ORIGINAL_INPUT: {source_path}\n")
		logf.write(f"STAGING_DIR: {staging_dir}\n")
		logf.flush()
		shutil.copy2(source_path, staged_input_path)
		logf.write(f"WORKING_INPUT: {staged_input_path}\n")
		logf.flush()
		return staged_input_path, staging_dir

	def _resolve_ffmpeg_source_mode(self, job) -> str:
		metadata = getattr(job, "metadata", {})
		if isinstance(metadata, dict):
			return normalize_ffmpeg_source_mode(
				metadata.get("ffmpeg_source_mode") or self.ffmpeg_source_mode
			)
		return self.ffmpeg_source_mode

	def run_job(self, job, dry_run=False):
		"""
		job: TranscodeJob (from core/pipeline.py)
		Logs: full command, all output, errors, and job metadata for every job.
		"""
		timestamp = time.strftime("%Y%m%d_%H%M%S")
		log_path = os.path.join(self.log_dir, f"transcode_{timestamp}.txt")
		working_input_path = None
		staging_dir = None
		if dry_run:
			cmd = self._build_command(job)
			print("[DRY RUN] Command:", " ".join(cmd))
			return cmd
		try:
			with open(log_path, "w", encoding="utf-8") as logf:
				backend = getattr(job, "backend", "ffmpeg")
				if backend == "ffmpeg":
					ffmpeg_source_mode = self._resolve_ffmpeg_source_mode(job)
					logf.write(f"FFMPEG_SOURCE_MODE: {ffmpeg_source_mode}\n")
					logf.write(
						f"FFMPEG_SOURCE_MODE_DESC: {describe_ffmpeg_source_mode(ffmpeg_source_mode)}\n"
					)
					if ffmpeg_source_mode == FFMPEG_SOURCE_MODE_SAFE_COPY:
						working_input_path, staging_dir = self._stage_ffmpeg_input_copy(job, logf)
					else:
						working_input_path = job.input_path
						logf.write(f"INPUT: {job.input_path}\n")
						logf.write(f"WORKING_INPUT: {job.input_path}\n")
						logf.flush()
				else:
					logf.write(f"INPUT: {job.input_path}\n")
				cmd = self._build_command(job, input_path=working_input_path)
				logf.write(f"BACKEND: {getattr(job, 'backend', 'ffmpeg')}\n")
				logf.write("COMMAND: " + " ".join(cmd) + "\n")
				logf.write(
					f"OUTPUT: {job.output_path}\n"
					f"PROFILE: {getattr(job.profile, 'name', '')}\n"
				)
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
		finally:
			if staging_dir:
				shutil.rmtree(staging_dir, ignore_errors=True)
