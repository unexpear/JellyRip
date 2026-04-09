import copy
import json
import os
from typing import Any, Dict, Optional

PROFILE_SCHEMA = {
    # Video stream selection and encoding options
    "video": {
        "codec": str,  # Target codec (e.g., h264, h265, copy)
        "mode": str,  # crf, bitrate, copy
        "crf": (int, type(None)),
        "bitrate": (int, type(None)),
        "preset": (str, type(None)),
        "hw_accel": str,  # auto_prefer, cpu, nvenc, qsv, etc.
        # Advanced: add 'stream_index' or 'select' for multi-video support if needed
    },
    # Audio stream selection and encoding options
    "audio": {
        "mode": str,  # copy, aac, ac3
        "language": (str, type(None)),  # Preferred language (e.g., 'eng')
        "tracks": (str, type(None)),  # all, main, language, etc.
        # Advanced: add 'downmix' (bool/str) for stereo compatibility if needed
    },
    # Subtitle stream selection and handling
    "subtitles": {
        "mode": str,  # all, forced, language, none
        "burn": bool,  # Burn-in if required for compatibility
        "language": (str, type(None)),  # Preferred language
        # Advanced: add 'soft_preferred' (bool) to prefer soft subs
    },
    # Output container and naming
    "output": {
        "container": str,  # mkv, mp4, etc.
        "naming": str,  # Output naming pattern
        "overwrite": bool,  # Overwrite existing files
        "auto_increment": bool,  # Auto-increment to avoid collisions
    },
    # Constraints for skipping unnecessary jobs
    "constraints": {
        "skip_if_below_gb": (int, float, type(None)),
        "skip_if_codec_matches": bool,
    },
    # Metadata preservation and advanced options
    "metadata": {
        "preserve": (bool, type(None)),  # Preserve all metadata if True
        # Advanced: add 'chapters' (bool) to preserve chapters
    }
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
        },
        "audio": {
            "mode": "copy",
            "language": None,
            "tracks": "all",
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
    }


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
