import copy
import json
import os
from typing import Any, Dict, Optional

_VIDEO_CODEC_LABELS = {
    "copy": "copy",
    "h264": "H.264",
    "h265": "H.265",
}
_HW_ACCEL_LABELS = {
    "cpu": "CPU",
    "auto_prefer": "auto GPU/CPU",
    "nvenc": "NVENC",
    "qsv": "Intel QSV",
    "amf": "AMD AMF",
}
_CHANNEL_LABELS = {
    1: "mono",
    2: "stereo",
    6: "5.1",
    8: "7.1",
}

PROFILE_SCHEMA = {
    # Video stream selection and encoding options
    "video": {
        "codec": str,                       # Target codec: h265, h264, copy
        "mode": str,                        # crf, bitrate, copy
        "crf": (int, type(None)),
        "bitrate": (int, type(None)),       # kbps, used when mode=bitrate
        "preset": (str, type(None)),        # ultrafast … veryslow
        "hw_accel": str,                    # cpu, auto_prefer, nvenc, qsv, amf
        "tune": (str, type(None)),          # film, animation, grain, fastdecode, zerolatency
        "video_profile": (str, type(None)), # main, main10, high, high10, baseline
        "pix_fmt": (str, type(None)),       # yuv420p, yuv420p10le, yuv444p10le …
        "keyint": (int, type(None)),        # keyframe interval in frames (GOP size)
        "bframes": (int, type(None)),       # max B-frames (0–16)
        "refs": (int, type(None)),          # reference frames (1–16)
        "extra_video_params": (str, type(None)),  # x265-params / x264-opts raw string
    },
    # Audio stream selection and encoding options
    "audio": {
        "mode": str,                        # copy, aac, ac3, eac3, mp3, opus, flac
        "language": (str, type(None)),      # preferred language tag (e.g. 'eng')
        "tracks": (str, type(None)),        # all, main, language
        "bitrate": (int, type(None)),       # kbps, used when mode != copy
        "channels": (int, type(None)),      # 1=mono, 2=stereo, 6=5.1, 8=7.1
        "sample_rate": (int, type(None)),   # Hz: 44100, 48000, 96000
        "downmix": bool,                    # force stereo output (-ac 2)
    },
    # Subtitle stream selection and handling
    "subtitles": {
        "mode": str,                        # all, forced, language, none
        "burn": bool,                       # burn-in (hard sub)
        "language": (str, type(None)),      # preferred language tag
    },
    # Output container and naming
    "output": {
        "container": str,                   # mkv, mp4, mov
        "naming": str,                      # naming pattern
        "overwrite": bool,
        "auto_increment": bool,
    },
    # Constraints for skipping unnecessary jobs
    "constraints": {
        "skip_if_below_gb": (int, float, type(None)),
        "skip_if_codec_matches": bool,
    },
    # Metadata preservation
    "metadata": {
        "preserve": (bool, type(None)),
    },
    # Raw FFmpeg pass-through arguments
    "advanced": {
        "extra_output_args": (str, type(None)),  # appended before output path
    },
}

class ProfileValidationError(Exception):
    pass


def _default_profile_data() -> Dict[str, Any]:
    return {
        "video": {
            "codec": "h265",
            "mode": "crf",
            "crf": 22,
            "bitrate": None,
            "preset": "medium",
            "hw_accel": "auto_prefer",
            "tune": None,
            "video_profile": None,
            "pix_fmt": None,
            "keyint": None,
            "bframes": None,
            "refs": None,
            "extra_video_params": None,
        },
        "audio": {
            "mode": "copy",
            "language": None,
            "tracks": "all",
            "bitrate": None,
            "channels": None,
            "sample_rate": None,
            "downmix": False,
        },
        "subtitles": {
            "mode": "all",
            "burn": False,
            "language": None,
        },
        "output": {
            "container": "mkv",
            "naming": "{title}_{profile}",
            "overwrite": False,
            "auto_increment": True,
        },
        "constraints": {
            "skip_if_below_gb": 7,
            "skip_if_codec_matches": True,
        },
        "metadata": {
            "preserve": True,
        },
        "advanced": {
            "extra_output_args": None,
        },
    }


def normalize_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Public wrapper around _normalize_profile_data for use by other modules."""
    return _normalize_profile_data(data)


def _normalize_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = copy.deepcopy(_default_profile_data())
    for section, section_value in data.items():
        if isinstance(section_value, dict) and isinstance(normalized.get(section), dict):
            normalized[section].update(section_value)
        else:
            normalized[section] = section_value
    return normalized

class TranscodeProfile:
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data
        self.validate()

    def validate(self):
        # Basic schema validation
        for section, schema in PROFILE_SCHEMA.items():
            if section not in self.data:
                raise ProfileValidationError(f"Missing section: {section}")
            for key, typ in schema.items():
                if key not in self.data[section]:
                    raise ProfileValidationError(f"Missing key: {section}.{key}")
                val = self.data[section][key]
                if isinstance(typ, tuple):
                    if not any(isinstance(val, t) for t in typ):
                        raise ProfileValidationError(f"{section}.{key} wrong type: {type(val)}")
                else:
                    if not isinstance(val, typ):
                        raise ProfileValidationError(f"{section}.{key} wrong type: {type(val)}")

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def to_dict(self):
        return self.data

class ProfileLoader:
    def __init__(self, path: str):
        self.path = path
        self.profiles: Dict[str, TranscodeProfile] = {}
        self.default: Optional[str] = None
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self._create_default()
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.profiles = {}
        for name, data in raw.get("transcode_profiles", {}).items():
            self.profiles[name] = TranscodeProfile(
                name,
                _normalize_profile_data(data),
            )
        self.default = raw.get("default_profile", "Balanced (Recommended)")

    def save(self):
        out = {
            "transcode_profiles": {name: p.to_dict() for name, p in self.profiles.items()},
            "default_profile": self.default
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    def _create_default(self):
        default_profile = _default_profile_data()
        out = {
            "transcode_profiles": {"Balanced (Recommended)": default_profile},
            "default_profile": "Balanced (Recommended)"
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    def get_profile(self, name: Optional[str] = None) -> TranscodeProfile:
        if name is None:
            name = self.default
        if name is None:
            raise ProfileValidationError("No default profile set and no name provided.")
        return self.profiles[name]

    def add_profile(self, name: str, data: Dict[str, Any]):
        self.profiles[name] = TranscodeProfile(name, data)
        self.save()

    def delete_profile(self, name: str):
        if name in self.profiles:
            del self.profiles[name]
            if self.default == name:
                self.default = next(iter(self.profiles), None)
            self.save()

    def duplicate_profile(self, name: str, new_name: str):
        if name in self.profiles:
            data = self.profiles[name].to_dict().copy()
            self.add_profile(new_name, data)

    def set_default(self, name: str):
        if name in self.profiles:
            self.default = name
            self.save()


def describe_profile(profile: "TranscodeProfile | Dict[str, Any]") -> str:
    if isinstance(profile, TranscodeProfile):
        data = profile.to_dict()
    else:
        data = profile
    normalized = normalize_profile_data(dict(data))

    video = normalized.get("video", {})
    audio = normalized.get("audio", {})
    subtitles = normalized.get("subtitles", {})
    constraints = normalized.get("constraints", {})
    metadata = normalized.get("metadata", {})

    video_codec = str(video.get("codec") or "copy").strip().lower()
    video_label = _VIDEO_CODEC_LABELS.get(video_codec, video_codec.upper() or "copy")
    if video_codec == "copy" or str(video.get("mode") or "").strip().lower() == "copy":
        video_summary = "Video: copy"
    else:
        quality_parts: list[str] = [video_label]
        mode = str(video.get("mode") or "").strip().lower()
        if mode == "crf" and video.get("crf") is not None:
            quality_parts.append(f"CRF {video['crf']}")
        elif mode == "bitrate" and video.get("bitrate") is not None:
            quality_parts.append(f"{video['bitrate']} kbps")
        preset = str(video.get("preset") or "").strip()
        if preset:
            quality_parts.append(f"{preset} preset")
        hw_accel = str(video.get("hw_accel") or "cpu").strip().lower()
        quality_parts.append(_HW_ACCEL_LABELS.get(hw_accel, hw_accel.upper() or "CPU"))
        video_summary = "Video: " + ", ".join(quality_parts)

    audio_mode = str(audio.get("mode") or "copy").strip().lower()
    track_scope = str(audio.get("tracks") or "all").strip().lower()
    if track_scope == "language":
        language = str(audio.get("language") or "").strip()
        track_summary = f"{language or 'language-matched'} tracks"
    elif track_scope == "main":
        track_summary = "main track"
    else:
        track_summary = "all tracks"
    if audio_mode == "copy":
        audio_summary = f"Audio: copy {track_summary}"
    else:
        audio_parts: list[str] = [audio_mode.upper()]
        if audio.get("bitrate") is not None:
            audio_parts.append(f"{audio['bitrate']} kbps")
        channels = audio.get("channels")
        if isinstance(channels, int) and channels > 0:
            audio_parts.append(_CHANNEL_LABELS.get(channels, f"{channels}ch"))
        audio_summary = f"Audio: {' '.join(audio_parts)} from {track_summary}"

    subtitle_mode = str(subtitles.get("mode") or "none").strip().lower()
    subtitle_language = str(subtitles.get("language") or "").strip()
    burn = bool(subtitles.get("burn"))
    if subtitle_mode == "none":
        subtitle_summary = "Subtitles: none"
    elif subtitle_mode == "language":
        subtitle_summary = (
            f"Subtitles: {'burn' if burn else 'copy'} "
            f"{subtitle_language or 'language-matched'}"
        )
    else:
        subtitle_summary = (
            f"Subtitles: {'burn' if burn else 'copy'} {subtitle_mode}"
        )

    skip_parts: list[str] = []
    skip_if_below_gb = constraints.get("skip_if_below_gb")
    if isinstance(skip_if_below_gb, (int, float)):
        if float(skip_if_below_gb).is_integer():
            skip_value = str(int(skip_if_below_gb))
        else:
            skip_value = str(skip_if_below_gb)
        skip_parts.append(f"under {skip_value} GB")
    if constraints.get("skip_if_codec_matches") and video_codec != "copy":
        skip_parts.append(f"already {video_label}")
    skip_summary = (
        f"Skip: {', '.join(skip_parts)}"
        if skip_parts else
        "Skip: none"
    )

    metadata_summary = (
        "Metadata: preserve"
        if metadata.get("preserve", True) else
        "Metadata: drop"
    )

    return " | ".join(
        [
            video_summary,
            audio_summary,
            subtitle_summary,
            skip_summary,
            metadata_summary,
        ]
    )
