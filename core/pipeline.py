import os
from typing import Optional, Dict, Any
from .profiles import TranscodeProfile, ProfileLoader, ProfileValidationError

class TranscodeJob:
    def __init__(self, input_path: str, output_path: str, profile: TranscodeProfile, metadata: Optional[Dict[str, Any]] = None):
        self.input_path = input_path
        self.output_path = output_path
        self.profile = profile
        self.metadata = metadata or {}
        self.skip_reason = None

    def should_skip(self, file_info: Dict[str, Any]) -> bool:
        """
        file_info: {
            'size_gb': float,
            'video_codec': str,
            'bitrate': Optional[int],
        }
        """
        constraints = self.profile.get('constraints', 'skip_if_below_gb', None)
        if constraints is not None and file_info.get('size_gb', 0) < constraints:
            self.skip_reason = f"File size {file_info.get('size_gb', 0):.2f}GB < {constraints}GB"
            return True
        if self.profile.get('constraints', 'skip_if_codec_matches', False):
            target_codec = self.profile.get('video', 'codec', None)
            if target_codec and file_info.get('video_codec', None) == target_codec:
                self.skip_reason = f"Video codec already {target_codec}"
                return True
        # Optionally: efficient bitrate check (placeholder, can be expanded)
        # if file_info.get('bitrate', 0) < some_threshold:
        #     self.skip_reason = "Bitrate already efficient"
        #     return True
        return False

class PipelineController:
    def __init__(self, profile_loader: ProfileLoader):
        self.profile_loader = profile_loader
        self.queue = []  # List of TranscodeJob

    def add_job(self, input_path: str, output_path: str, profile_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, file_info: Optional[Dict[str, Any]] = None):
        profile = self.profile_loader.get_profile(profile_name)
        # Output naming/collision avoidance
        overwrite = profile.get('output', 'overwrite', False)
        auto_increment = profile.get('output', 'auto_increment', True)
        base, ext = os.path.splitext(output_path)
        candidate = output_path
        idx = 1
        while os.path.exists(candidate):
            if overwrite:
                break
            if auto_increment:
                candidate = f"{base}_{idx}{ext}"
                idx += 1
            else:
                raise FileExistsError(f"Output file exists and overwrite/auto_increment are disabled: {candidate}")
        job = TranscodeJob(input_path, candidate, profile, metadata)
        if file_info and job.should_skip(file_info):
            print(f"Skipping job: {job.skip_reason}")
            return False
        self.queue.append(job)
        return True

    def get_queue(self):
        return self.queue
