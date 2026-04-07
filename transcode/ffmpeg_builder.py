from typing import Dict, Any, List
from .profiles import TranscodeProfile

class FFmpegBuilder:
    def __init__(self, profile: TranscodeProfile, input_path: str, output_path: str, metadata: Dict[str, Any] = None):
        self.profile = profile
        self.input_path = input_path
        self.output_path = output_path
        self.metadata = metadata or {}

    def build_command(self) -> List[str]:
        """
        Build ffmpeg command based on profile:
        - Prefer remux/copy if possible (video: copy, audio: copy, subtitles: copy)
        - Always preserve all metadata and chapters (-map_metadata 0 -map_chapters 0)
        - Only transcode when necessary
        """
        video = self.profile.get('video', 'codec')
        mode = self.profile.get('video', 'mode')
        crf = self.profile.get('video', 'crf')
        preset = self.profile.get('video', 'preset')
        hw_accel = self.profile.get('video', 'hw_accel')
        audio_mode = self.profile.get('audio', 'mode')
        audio_language = self.profile.get('audio', 'language')
        audio_tracks = self.profile.get('audio', 'tracks')
        audio_downmix = self.profile.get('audio', 'downmix', False)
        container = self.profile.get('output', 'container')
        sub_mode = self.profile.get('subtitles', 'mode')
        sub_burn = self.profile.get('subtitles', 'burn', False)
        sub_language = self.profile.get('subtitles', 'language')
        sub_soft_preferred = self.profile.get('subtitles', 'soft_preferred', True)
        # Remux/copy mode: all streams copied, preserve metadata and chapters
        if video == 'copy' and audio_mode == 'copy' and not sub_burn:
            cmd = [
                'ffmpeg', '-i', self.input_path,
                '-map', '0',  # map all streams
                '-c', 'copy',
                '-map_metadata', '0',
                '-map_chapters', '0',
                '-disposition:s:0', 'default',
                self.output_path
            ]
            return cmd
        # Transcode mode (video or audio or subtitle needs processing)
        cmd = ['ffmpeg', '-i', self.input_path]
        # Hardware acceleration (auto, nvenc, qsv, or CPU)
        if hw_accel and hw_accel.startswith('nvenc'):
            vcodec = f'h264_nvenc' if video == 'h264' else f'hevc_nvenc'
        elif hw_accel and hw_accel.startswith('qsv'):
            vcodec = f'h264_qsv' if video == 'h264' else f'hevc_qsv'
        elif hw_accel and hw_accel == 'auto_prefer':
            vcodec = f'hevc_nvenc' if video == 'h265' else f'h264_nvenc'
        elif video == 'h264':
            vcodec = 'libx264'
        elif video == 'h265':
            vcodec = 'libx265'
        else:
            vcodec = video  # fallback to user value
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
        # Downmix to stereo if requested (for compatibility)
        if audio_downmix:
            cmd += ['-ac', '2']
        # Audio language selection (if specified)
        if audio_language:
            cmd += ['-map', f'0:a:m:language:{audio_language}']
        elif audio_tracks == 'main':
            cmd += ['-map', '0:a:0']
        elif audio_tracks == 'all':
            cmd += ['-map', '0:a']
        # Subtitles
        if sub_mode == 'none':
            cmd += ['-sn']  # disable all subtitles
        elif sub_burn:
            # Burn-in first matching subtitle stream (language if specified)
            if sub_language:
                cmd += ['-filter_complex', f'[0:s:m:language:{sub_language}]scale=iw:ih[sub];[0:v][sub]overlay']
            else:
                cmd += ['-filter_complex', '[0:s:0]scale=iw:ih[sub];[0:v][sub]overlay']
            cmd += ['-c:s', 'mov_text']  # fallback for container
        else:
            # Prefer soft subs (copy if possible)
            cmd += ['-c:s', 'copy']
            if sub_language:
                cmd += ['-map', f'0:s:m:language:{sub_language}']
            elif sub_mode == 'forced':
                cmd += ['-map', '0:s:m:forced']
        # Metadata and chapters
        cmd += ['-map_metadata', '0']
        cmd += ['-map_chapters', '0']
        # Disposition
        cmd += ['-disposition:s:0', 'default']
        # Output
        cmd += [self.output_path]
        return cmd
