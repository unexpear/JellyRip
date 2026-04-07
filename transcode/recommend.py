import subprocess
import json
import os
from typing import Dict, Any

def analyze_media(input_path: str) -> Dict[str, Any]:
    """
    Uses ffprobe to extract media info for recommendation logic.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=size,duration:stream=index,codec_type,codec_name,channels,bit_rate,language,tags',
        '-of', 'json',
        input_path
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    info = json.loads(proc.stdout)
    # Parse info
    result = {
        'size_gb': float(info['format'].get('size', 0)) / (1024 ** 3),
        'duration': float(info['format'].get('duration', 0)),
        'video': [],
        'audio': [],
        'subtitle': []
    }
    for stream in info.get('streams', []):
        if stream['codec_type'] == 'video':
            result['video'].append(stream)
        elif stream['codec_type'] == 'audio':
            result['audio'].append(stream)
        elif stream['codec_type'] == 'subtitle':
            result['subtitle'].append(stream)
    return result

def recommend_profile_from_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a recommended profile dict based on media analysis.
    """
    # Video
    video = meta['video'][0] if meta['video'] else {}
    codec = video.get('codec_name', '')
    size_gb = meta.get('size_gb', 0)
    # Recommend remux if already h265 and <7GB
    if codec == 'hevc' and size_gb < 7:
        video_codec = 'copy'
        crf = None
        preset = None
        hw_accel = 'auto_prefer'
    else:
        video_codec = 'h265'
        crf = 22
        preset = 'medium'
        hw_accel = 'auto_prefer'
    # Audio
    audio_tracks = meta['audio']
    if len(audio_tracks) > 2:
        audio_mode = 'copy'
        audio_tracks_sel = 'main'
    else:
        audio_mode = 'copy'
        audio_tracks_sel = 'all'
    # Subs
    subtitle_tracks = meta['subtitle']
    if len(subtitle_tracks) > 3:
        subs_mode = 'forced'
    else:
        subs_mode = 'all'
    # Build profile
    profile = {
        "video": {
            "codec": video_codec,
            "mode": "crf" if video_codec != 'copy' else 'copy',
            "crf": crf,
            "bitrate": None,
            "preset": preset,
            "hw_accel": hw_accel
        },
        "audio": {
            "mode": audio_mode,
            "language": None,
            "tracks": audio_tracks_sel
        },
        "subtitles": {
            "mode": subs_mode,
            "burn": False,
            "language": None
        },
        "output": {
            "container": "mkv",
            "naming": "{title}_recommended",
            "overwrite": False,
            "auto_increment": True
        },
        "constraints": {
            "skip_if_below_gb": 7,
            "skip_if_codec_matches": True
        }
    }
    return profile
