from typing import Dict, Any

def profile_summary_readable(profile: Dict[str, Any]) -> str:
    """
    Returns a human-readable summary of the recommended profile for non-technical users.
    """
    video = profile["video"]
    audio = profile["audio"]
    subs = profile["subtitles"]
    output = profile["output"]

    # Video
    codec_map = {"h265": "H.265 (smaller files, good quality)", "h264": "H.264 (compatible)", "copy": "No change (original)"}
    codec_str = codec_map.get(video["codec"], video["codec"]) 
    if video["codec"] == "copy":
        video_str = f"Keep original video (no quality loss)"
    else:
        crf = video.get("crf", 22)
        video_str = f"Convert video to {codec_str}, balanced quality (CRF {crf}), hardware acceleration if available"

    # Audio
    if audio["mode"] == "copy":
        if audio["tracks"] == "main":
            audio_str = "Keep only the main audio track (original quality)"
        else:
            audio_str = "Keep all audio tracks (original quality)"
    else:
        audio_str = f"Convert audio to {audio['mode'].upper()}"

    # Subtitles
    if subs["mode"] == "all":
        subs_str = "Keep all subtitles as selectable tracks"
    elif subs["mode"] == "forced":
        subs_str = "Keep only forced/essential subtitles"
    elif subs["mode"] == "none":
        subs_str = "No subtitles will be kept"
    else:
        subs_str = f"Keep subtitles: {subs['mode']}"
    if subs.get("burn", False):
        subs_str += " (burned into video)"

    # Container
    container_map = {"mkv": "MKV (best for compatibility and features)", "mp4": "MP4 (widely supported)"}
    container_str = container_map.get(output["container"], output["container"]).capitalize()

    return (
        f"Video: {video_str}\n"
        f"Audio: {audio_str}\n"
        f"Subtitles: {subs_str}\n"
        f"Container: {container_str}"
    )
