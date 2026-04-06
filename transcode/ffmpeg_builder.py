from typing import Dict, Any, List
from .profiles import TranscodeProfile

class FFmpegBuilder:
    def __init__(self, profile: TranscodeProfile, input_path: str, output_path: str, metadata: Dict[str, Any] = None):
        self.profile = profile
        self.input_path = input_path
        self.output_path = output_path
        self.metadata = metadata or {}

    def build_command(self) -> List[str]:
        video = self.profile.get('video', 'codec')
        mode = self.profile.get('video', 'mode')
        crf = self.profile.get('video', 'crf')
        preset = self.profile.get('video', 'preset')
        hw_accel = self.profile.get('video', 'hw_accel')
        audio_mode = self.profile.get('audio', 'mode')
        container = self.profile.get('output', 'container')
        # Remux mode
        if video == 'copy':
            cmd = [
                'ffmpeg', '-i', self.input_path,
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-c:s', 'copy',
                self.output_path
            ]
            return cmd
        # Transcode mode
        cmd = ['ffmpeg', '-i', self.input_path]
        # Hardware acceleration
        if hw_accel and hw_accel.startswith('nvenc'):
            vcodec = f'h264_nvenc' if video == 'h264' else f'hevc_nvenc'
        elif hw_accel and hw_accel.startswith('qsv'):
            vcodec = f'h264_qsv' if video == 'h264' else f'hevc_qsv'
        else:
            vcodec = f'libx264' if video == 'h264' else f'libx265'
        cmd += ['-c:v', vcodec]
        if mode == 'crf' and crf is not None:
            cmd += ['-crf', str(crf)]
        if preset:
            cmd += ['-preset', preset]
        # Audio
        if audio_mode == 'copy':
            cmd += ['-c:a', 'copy']
        elif audio_mode == 'aac':
            cmd += ['-c:a', 'aac']
        elif audio_mode == 'ac3':
            cmd += ['-c:a', 'ac3']
        # Subtitles
        cmd += ['-c:s', 'copy']
        # Output
        cmd += [self.output_path]
        return cmd
