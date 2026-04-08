import subprocess
import sys
from utils.parsing import parse_cli_args, parse_duration_to_seconds, parse_size_to_bytes, safe_int

def scan_disc(engine, on_log, on_progress):
    makemkvcon  = engine._get_makemkvcon()
    disc_target = engine.get_disc_target()
    global_args = parse_cli_args(
        engine.cfg.get("opt_makemkv_global_args", ""),
        on_log,
        "MakeMKV global args"
    )
    info_args = parse_cli_args(
        engine.cfg.get("opt_makemkv_info_args", ""),
        on_log,
        "MakeMKV info args"
    )
    minlength = int(engine.cfg.get("opt_minlength_seconds", 0) or 0)
    minlength_args = [f"--minlength={minlength}"] if minlength > 0 else []

    on_log(f"Scanning disc ({disc_target})...")
    disc_info   = {}
    titles      = {}
    title_count = 0
    try:
        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = 0x08000000
        proc = subprocess.Popen(
            [makemkvcon] + global_args +
            ["-r", "info", disc_target] + minlength_args + info_args,
            **popen_kwargs
        )
        valid_titles = []
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ""):
                if engine.abort_event.is_set():
                    proc.kill()
                    return None
                line = line.strip()
                if not line:
                    continue
                if line.startswith("CINFO:"):
                    parts = line[6:].split(",", 2)
                    if len(parts) < 3:
                        continue
                    try:
                        attr = int(parts[0])
                        val  = parts[2].strip().strip('"')
                    except (ValueError, IndexError):
                        continue
                    if attr == 2:
                        disc_info["title"] = val
                    elif attr == 28:
                        disc_info["lang_code"] = val
                    elif attr == 29:
                        disc_info["lang_name"] = val
                    elif attr == 32:
                        disc_info["volume_id"] = val
                elif line.startswith("TINFO:"):
                    parts = line[6:].split(",", 3)
                    if len(parts) < 4:
                        continue
                    try:
                        tid  = int(parts[0])
                        attr = int(parts[1])
                        val  = parts[3].strip().strip('"')
                    except (ValueError, IndexError):
                        continue
                    if tid not in titles:
                        titles[tid] = {
                            "id":               tid,
                            "name":             f"Title {tid+1}",
                            "duration":         "",
                            "duration_seconds": 0,
                            "size":             "",
                            "size_bytes":       0,
                            "chapters":         0,
                            "_invalid":         False,
                            "streams":          {},
                        }
                        title_count += 1
                        on_progress(
                            min(5 + title_count, 90)
                        )
                    if attr == 2:
                        titles[tid]["name"] = val
                    elif attr == 9:
                        titles[tid]["duration"] = val
                        dur_seconds = parse_duration_to_seconds(val)
                        titles[tid]["duration_seconds"] = dur_seconds
                        if val and dur_seconds <= 0:
                            titles[tid]["_invalid"] = True
                    elif attr == 8:
                        titles[tid]["chapters"] = safe_int(val)
                    elif attr == 11:
                        size_bytes = parse_size_to_bytes(val)
                        titles[tid]["size_bytes"] = size_bytes
                        if val and size_bytes <= 0:
                            titles[tid]["_invalid"] = True
                        if size_bytes > 0:
                            gb = size_bytes / (1024**3)
                            titles[tid]["size"] = f"{gb:.2f} GB"
                        else:
                            titles[tid]["size"] = val
                elif line.startswith("SINFO:"):
                    parts = line[6:].split(",", 4)
                    if len(parts) < 5:
                        continue
                    try:
                        tid  = int(parts[0])
                        stid = int(parts[1])
                        attr = int(parts[2])
                        val  = parts[4].strip().strip('"')
                    except (ValueError, IndexError):
                        continue
                    if tid not in titles:
                        continue
                    streams = titles[tid]["streams"]
                    if stid not in streams:
                        streams[stid] = {}
                    streams[stid][attr] = val
            proc.wait()
            if proc.returncode != 0:
                on_log(f"MakeMKV scan failed (exit code {proc.returncode})")
                return None
            # Filter and sort titles
            valid_titles = [t for t in titles.values() if not t["_invalid"]]
            valid_titles.sort(key=lambda t: -t["duration_seconds"])
        return valid_titles
        return valid_titles
    except Exception as e:
        on_log(f"Scan failed: {e}")
        return None
