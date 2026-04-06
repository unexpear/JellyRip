import os
from .profiles import ProfileLoader, TranscodeProfile, ProfileValidationError

# Example usage for integration/testing
if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "transcode_profiles.json")
    loader = ProfileLoader(config_path)
    print("Loaded profiles:", list(loader.profiles.keys()))
    default = loader.get_profile()
    print("Default profile:", default.name)
    print(default.to_dict())
