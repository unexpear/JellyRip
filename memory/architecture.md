# JellyRip — Architecture pointers

Authoritative docs (read these first):
- `docs/architecture.md` — overall architecture overview
- `docs/repository-layout.md` — why directories are split the way they are
- `FEATURE_MAP.md` — "where does feature X live"

## Quick "where does X live" map

| Concern | Module(s) |
|---|---|
| Disc scan + title scoring | `engine/ripper_engine.py` (`scan_disc`, `score_title`) |
| Rip orchestration | `controller/controller.py` → `engine/rip_ops.py`, `engine/ripper_engine.py` |
| ffprobe validation | `engine/ripper_engine.py` (`_quick_ffprobe_ok`, `_probe_file_duration_and_size`, `analyze_files`) |
| Tool path resolution | `config.py` (`resolve_ffprobe`), `engine/ripper_engine.py` (`validate_tools`) |
| Temp/session folder naming | `utils/helpers.py` (`make_rip_folder_name`) |
| Resumable session discovery | `engine/ripper_engine.py` (`find_old_temp_folders`, `find_resumable_sessions`) |
| Library scan (attach to existing show) | `controller/controller.py` (`_scan_library_folder`, `_scan_episode_files`) |
| Settings dialog | `gui/main_window.py` (settings tab) |
| Settings defaults / validation | `config.py`, `controller/controller.py` |
| Update check / download | `gui/update_ui.py` (`check_for_updates`, `launch_downloaded_update`); core in `utils/updater.py` |
| Folder picker dialogs | `gui/main_window.py` (`ask_directory`, `ask_input`) |
| Transcode queue + engines | `transcode/queue.py`, `transcode/queue_builder.py`, `transcode/engine.py` |
| Transcode planning | `transcode/planner.py`, `transcode/profiles.py`, `transcode/recommendations.py` |
| Process safety (Windows) | `shared/windows_exec.py` |
| Pub/sub events | `shared/event.py` |
| Session state machine | `utils/state_machine.py` |

## Layering rules of thumb
- `gui/` and `ui/` should not import `engine/` directly — go through `controller/`.
- `controller/` is the orchestration boundary; pure-logic modules in `transcode/`, `utils/`, `engine/` should remain importable without a UI.
- `shared/` is leaf-level — must not import from `controller/`, `engine/`, `gui/`, `ui/`.
