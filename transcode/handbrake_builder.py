from typing import Any, Dict, List


class HandBrakeBuilder:
    def __init__(
        self,
        input_path: str,
        output_path: str,
        preset: str,
        metadata: Dict[str, Any] | None = None,
        executable_path: str = "HandBrakeCLI",
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.preset = preset or "Fast 1080p30"
        self.metadata = metadata or {}
        self.executable_path = executable_path or "HandBrakeCLI"

    def build_command(self) -> List[str]:
        cmd = [
            self.executable_path,
            "-i",
            self.input_path,
            "-o",
            self.output_path,
            "--preset",
            self.preset,
            "--format",
            "av_mkv",
            "--markers",
            "--all-audio",
            "--all-subtitles",
        ]
        if self.metadata.get("optimize_for_web"):
            cmd.append("--optimize")
        return cmd
