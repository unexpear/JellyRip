from typing import Any, Dict
from .profiles import ProfileValidationError

class TranscodeProfile:
    """
    Represents a validated transcode profile. (Re-exported for clarity)
    """
    def __init__(self, name: str, data: Dict[str, Any]):
        from .profiles import TranscodeProfile as _TranscodeProfile
        # Use the validated implementation from profiles.py
        self._profile = _TranscodeProfile(name, data)
        self.name = self._profile.name
        self.data = self._profile.data
        self.get = self._profile.get
        self.to_dict = self._profile.to_dict

    def validate(self):
        self._profile.validate()
