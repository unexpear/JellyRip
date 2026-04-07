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
        # Remux mode (best practice: preserve all streams, metadata, and disposition)
        if video == 'copy':
            cmd = [
                'ffmpeg', '-i', self.input_path,
                '-map', '0',  # map all streams
                '-c', 'copy',
                '-map_metadata', '0',
                '-disposition:s:0', 'default',
                self.output_path
            ]
            return cmd
        # Transcode mode
        cmd = ['ffmpeg', '-i', self.input_path]
        # Hardware acceleration (auto, nvenc, qsv, or CPU)
        if hw_accel and hw_accel.startswith('nvenc'):
            vcodec = f'h264_nvenc' if video == 'h264' else f'hevc_nvenc'
        elif hw_accel and hw_accel.startswith('qsv'):
            vcodec = f'h264_qsv' if video == 'h264' else f'hevc_qsv'
        elif hw_accel and hw_accel == 'auto_prefer':
            # Try hardware, fallback to CPU (let ffmpeg auto-select)
            vcodec = f'hevc_nvenc' if video == 'h265' else f'h264_nvenc'
        else:
            vcodec = f'libx264' if video == 'h264' else f'libx265'
        cmd += ['-map', '0']  # map all streams
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
        # Metadata and disposition
        cmd += ['-map_metadata', '0']
        cmd += ['-disposition:s:0', 'default']
        # Output
        cmd += [self.output_path]
        return cmd
