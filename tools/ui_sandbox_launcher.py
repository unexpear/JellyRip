"""UI sandbox launcher for testing flows without tools or hardware."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gui.main_window as main_window
from config import ResolvedTool, load_startup_config
from gui.main_window import JellyRipperGUI
from main import _prepare_startup_environment, _set_windows_app_user_model_id
from utils.classifier import ClassifiedTitle, classify_titles
from utils.helpers import MakeMKVDriveInfo

_FAKE_TOOL_ROOT = Path(r"C:\JellyRipUIFake")
_FAKE_SAVED_CONFIG: dict[str, object] = {}


def _fake_tool(filename: str, source: str = "ui sandbox") -> ResolvedTool:
    return ResolvedTool(path=str(_FAKE_TOOL_ROOT / filename), source=source)


def _fake_validator(_path: str) -> tuple[bool, str]:
    return True, ""


def _fake_save_config(cfg: dict[str, object]) -> None:
    _FAKE_SAVED_CONFIG.clear()
    _FAKE_SAVED_CONFIG.update(cfg)


def _fake_drives() -> list[MakeMKVDriveInfo]:
    return [
        MakeMKVDriveInfo(
            index=0,
            state_code=2,
            flags_code=999,
            disc_type_code=1,
            drive_name="Sandbox Blu-ray Drive",
            disc_name="OVER THE HEDGE",
            device_path="disc:0",
        ),
        MakeMKVDriveInfo(
            index=1,
            state_code=0,
            flags_code=999,
            disc_type_code=0,
            drive_name="Sandbox DVD Drive",
            disc_name="",
            device_path="disc:1",
        ),
    ]


class FakeEngine:
    def __init__(self, cfg: dict[str, object]) -> None:
        self.cfg = cfg
        self.abort_event = threading.Event()
        self.current_process = None
        self.last_classification: list[ClassifiedTitle] = []
        self.last_available_drives = _fake_drives()
        self.last_selected_drive_probe = self.last_available_drives[0]
        self.last_drive_info = {
            "disc_type": "Blu-ray",
            "libre_drive": "enabled",
        }
        self._resolved_makemkvcon = str(_FAKE_TOOL_ROOT / "makemkvcon64.exe")
        self._makemkvcon_source = "ui sandbox"
        self._resolved_ffprobe = str(_FAKE_TOOL_ROOT / "ffprobe.exe")
        self._ffprobe_source = "ui sandbox"

    def validate_tools(self) -> tuple[bool, str]:
        return True, ""

    def reset_abort(self) -> None:
        self.abort_event.clear()

    def abort(self) -> None:
        self.abort_event.set()


def _install_sandbox_patches() -> None:
    main_window.RipperEngine = FakeEngine
    main_window.resolve_makemkvcon = lambda *_args, **_kwargs: _fake_tool(
        "makemkvcon64.exe"
    )
    main_window.resolve_ffprobe = lambda *_args, **_kwargs: _fake_tool(
        "ffprobe.exe"
    )
    main_window.resolve_ffmpeg = lambda *_args, **_kwargs: _fake_tool(
        "ffmpeg.exe"
    )
    main_window.resolve_handbrake = lambda *_args, **_kwargs: _fake_tool(
        "HandBrakeCLI.exe"
    )
    main_window.validate_makemkvcon = _fake_validator
    main_window.validate_ffprobe = _fake_validator
    main_window.validate_ffmpeg = _fake_validator
    main_window.validate_handbrake = _fake_validator
    main_window.save_config = _fake_save_config
    main_window.handbrake_gui_installed = lambda: False
    main_window.get_available_drives = lambda *_args, **_kwargs: _fake_drives()


class FakeJellyRipperGUI(JellyRipperGUI):
    def __init__(self, cfg: dict[str, object], startup_context=None) -> None:
        super().__init__(cfg, startup_context=startup_context)
        self.title(f"{self.title()} [UI Sandbox]")
        self._refresh_drives()
        self.controller.log("UI sandbox mode enabled.")
        self.controller.log(
            "No hardware probes, no MakeMKV or ffprobe calls, no updates, "
            "and no config writes will run from this launcher."
        )
        self.set_status("UI Sandbox Ready")

    def _refresh_drives(self) -> None:
        self._update_drive_menu(_fake_drives())
        self.controller.log("Sandbox drives loaded.")

    def _open_path_in_explorer(self, path) -> None:
        normalized = os.path.normpath(str(path))
        self.controller.log(f"UI sandbox: open path suppressed: {normalized}")
        self.show_info(
            "Sandbox",
            f"Explorer launch is disabled in UI sandbox mode.\n\nRequested path:\n{normalized}",
        )

    def _reveal_path_in_explorer(self, path) -> None:
        normalized = os.path.normpath(str(path))
        self.controller.log(f"UI sandbox: reveal path suppressed: {normalized}")
        self.show_info(
            "Sandbox",
            f"Explorer reveal is disabled in UI sandbox mode.\n\nRequested path:\n{normalized}",
        )

    def _browse_folder_in_explorer(self) -> None:
        self.show_info(
            "Sandbox",
            "Browse is disabled in UI sandbox mode.\n\n"
            "Use the dialog flows and prompts without launching Explorer.",
        )

    def check_for_updates(self) -> None:
        available = self._run_on_main(
            lambda: messagebox.askyesno(
                "Sandbox Update Check",
                "Simulate a new update being available?",
                parent=self,
            )
        )
        if available:
            self.show_info(
                "Sandbox Updates",
                "Fake update available:\n\n"
                "Version: v1.0.99-sandbox\n"
                "Channel: stable\n"
                "Result: no download or installer launch was performed.",
            )
        else:
            self.show_info(
                "Sandbox Updates",
                "Fake update check complete.\n\nYou are already up to date.",
            )

    def start_task(self, mode):
        if self.rip_thread and self.rip_thread.is_alive():
            messagebox.showwarning(
                "Busy",
                "Wait for the current sandbox flow to finish.",
                parent=self,
            )
            return

        flows = {
            "t": ("TV flow", self._run_fake_tv_flow),
            "m": ("Movie flow", self._run_fake_movie_flow),
            "d": ("Dump flow", self._run_fake_dump_flow),
            "i": ("Organize flow", self._run_fake_organize_flow),
            "scan": ("Prep flow", self._run_fake_prep_flow),
        }
        flow_name, flow_fn = flows.get(mode, ("Organize flow", self._run_fake_organize_flow))

        self.engine.reset_abort()
        self.disable_buttons()
        self.abort_btn.config(text="ABORT SESSION", state="normal")
        self.set_progress(0)
        self.set_status(f"Sandbox: {flow_name}")
        self.controller.log(f"Starting sandbox {flow_name.lower()}.")

        def _worker():
            try:
                flow_fn()
            except Exception as exc:
                self.controller.log(f"Sandbox flow crashed: {exc}")
                self.show_error("Sandbox Error", str(exc))
            finally:
                self.after(0, self._finish_fake_task)

        self.rip_thread = threading.Thread(target=_worker, daemon=True)
        self.rip_thread.start()

    def _finish_fake_task(self) -> None:
        if self.engine.abort_event.is_set():
            self.controller.log("Sandbox flow aborted.")
            self.set_status("Sandbox Aborted")
        else:
            self.set_status("UI Sandbox Ready")
            self.set_progress(100)
        self.abort_btn.config(text="ABORT SESSION", state="disabled")
        self.enable_buttons()
        self.rip_thread = None

    def _set_fake_step(self, percent: float, message: str) -> None:
        self.controller.log(message)
        self.after(0, lambda: self.set_progress(percent))
        self.after(0, lambda: self.set_status(message))

    def _preview_title(self, title_id: int) -> None:
        self.controller.log(
            f"Sandbox preview requested for title {title_id + 1}."
        )

    def _sample_movie_titles(self) -> list[dict[str, object]]:
        return [
            {
                "id": 0,
                "name": "Main Feature",
                "duration": "1:23:00",
                "duration_seconds": 4980,
                "size": "24.1 GB",
                "size_bytes": 24_100_000_000,
                "chapters": 18,
                "audio_tracks": [{"lang": "eng"}, {"lang": "spa"}],
                "subtitle_tracks": [{"lang_name": "English"}],
            },
            {
                "id": 1,
                "name": "Main Feature Duplicate",
                "duration": "1:22:35",
                "duration_seconds": 4955,
                "size": "23.8 GB",
                "size_bytes": 23_800_000_000,
                "chapters": 18,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [{"lang_name": "English"}],
            },
            {
                "id": 2,
                "name": "Behind The Scenes",
                "duration": "0:11:00",
                "duration_seconds": 660,
                "size": "1.2 GB",
                "size_bytes": 1_200_000_000,
                "chapters": 4,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [],
            },
            {
                "id": 3,
                "name": "Deleted Scenes",
                "duration": "0:08:30",
                "duration_seconds": 510,
                "size": "820 MB",
                "size_bytes": 820_000_000,
                "chapters": 3,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [],
            },
        ]

    def _sample_tv_titles(self) -> list[dict[str, object]]:
        return [
            {
                "id": 0,
                "name": "Episode 1",
                "duration": "0:43:00",
                "duration_seconds": 2580,
                "size": "7.4 GB",
                "size_bytes": 7_400_000_000,
                "chapters": 12,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [{"lang_name": "English"}],
            },
            {
                "id": 1,
                "name": "Episode 2",
                "duration": "0:42:10",
                "duration_seconds": 2530,
                "size": "7.2 GB",
                "size_bytes": 7_200_000_000,
                "chapters": 12,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [{"lang_name": "English"}],
            },
            {
                "id": 2,
                "name": "Episode 3",
                "duration": "0:42:40",
                "duration_seconds": 2560,
                "size": "7.3 GB",
                "size_bytes": 7_300_000_000,
                "chapters": 12,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [{"lang_name": "English"}],
            },
            {
                "id": 3,
                "name": "Bonus Featurette",
                "duration": "0:06:00",
                "duration_seconds": 360,
                "size": "480 MB",
                "size_bytes": 480_000_000,
                "chapters": 2,
                "audio_tracks": [{"lang": "eng"}],
                "subtitle_tracks": [],
            },
        ]

    def _classified(self, titles: list[dict[str, object]]) -> list[ClassifiedTitle]:
        classified = classify_titles(titles)
        self.engine.last_classification = classified
        return classified

    def _show_fake_summary(self, title: str, lines: list[str]) -> None:
        self.show_info(title, "\n".join(lines))

    def _build_extras_map(
        self,
        classified: list[ClassifiedTitle],
        assignments: dict[int, str],
    ) -> dict[str, list[str]]:
        title_names = {ct.title_id: ct.display_name for ct in classified}
        extras_map: dict[str, list[str]] = {}
        for title_id, category in assignments.items():
            extras_map.setdefault(category, []).append(
                title_names.get(title_id, f"Title {title_id + 1}")
            )
        return extras_map

    def _run_fake_movie_flow(self) -> None:
        choice = self._run_on_main(
            lambda: messagebox.askyesnocancel(
                "Movie Mode",
                "Use Smart Rip for this movie disc?\n\n"
                "Yes = auto-pick main feature\n"
                "No = manual title selection\n"
                "Cancel = stop",
                parent=self,
            )
        )
        if choice is None:
            self.controller.log("Sandbox movie flow cancelled at mode prompt.")
            return
        if choice:
            self._run_fake_smart_movie_flow()
            return
        self._run_fake_manual_movie_flow()

    def _run_fake_smart_movie_flow(self) -> None:
        titles = self._sample_movie_titles()
        classified = self._classified(titles)

        self._set_fake_step(10, "Sandbox: scan results ready.")
        media_type = self.show_scan_results_step(
            classified,
            {"disc_type": "Blu-ray", "libre_drive": "enabled"},
        )
        if media_type is None:
            self.controller.log("Sandbox smart movie flow cancelled after scan.")
            return

        if media_type == "tv":
            setup = self.ask_tv_setup(
                default_title="Planet Earth",
                default_season="1",
                default_metadata_provider="TMDB",
                default_metadata_id="1396",
            )
            if setup is None:
                self.controller.log("Sandbox smart flow cancelled in TV setup.")
                return
            base_folder = os.path.join(
                str(self.cfg.get("tv_folder", "TV")),
                setup.title,
                f"Season {setup.season:02d}",
            )
            main_label = f"{setup.title} - Season {setup.season:02d}"
        else:
            setup = self.ask_movie_setup(
                default_title="OVER THE HEDGE",
                default_year="2006",
                default_metadata_provider="TMDB",
                default_metadata_id="7518",
            )
            if setup is None:
                self.controller.log("Sandbox smart flow cancelled in movie setup.")
                return
            base_folder = os.path.join(
                str(self.cfg.get("movies_folder", "Movies")),
                f"{setup.title} ({setup.year})",
            )
            main_label = f"{setup.title} ({setup.year})"

        self._set_fake_step(35, "Sandbox: content mapping.")
        selection = self.show_content_mapping_step(classified)
        if selection is None:
            self.controller.log("Sandbox smart flow cancelled in content mapping.")
            return

        extras_map: dict[str, list[str]] = {}
        if selection.extra_title_ids:
            extra_titles = [
                ct for ct in classified if ct.title_id in selection.extra_title_ids
            ]
            self._set_fake_step(55, "Sandbox: extras classification.")
            extras_assignment = self.show_extras_classification_step(extra_titles)
            if extras_assignment is None:
                self.controller.log(
                    "Sandbox smart flow cancelled in extras classification."
                )
                return
            extras_map = self._build_extras_map(
                classified,
                extras_assignment.assignments,
            )

        self._set_fake_step(75, "Sandbox: output plan preview.")
        confirmed = self.show_output_plan_step(base_folder, main_label, extras_map)
        if not confirmed:
            self.controller.log("Sandbox smart flow cancelled at output plan.")
            return

        self._set_fake_step(100, "Sandbox smart movie flow complete.")
        self._show_fake_summary(
            "Sandbox Smart Movie Flow",
            [
                f"Media type: {media_type}",
                f"Main output: {main_label}",
                f"Base folder: {base_folder}",
                f"Selected mains: {selection.main_title_ids}",
                f"Selected extras: {selection.extra_title_ids}",
                "Result: no rip was started.",
            ],
        )

    def _run_fake_manual_movie_flow(self) -> None:
        self._set_fake_step(10, "Sandbox: manual movie setup.")
        setup = self.ask_movie_setup(
            default_title="OVER THE HEDGE",
            default_year="2006",
            default_metadata_provider="TMDB",
            default_metadata_id="7518",
        )
        if setup is None:
            self.controller.log("Sandbox manual movie flow cancelled in setup.")
            return

        titles = self._sample_movie_titles()
        self._classified(titles)
        self._set_fake_step(45, "Sandbox: manual movie title picker.")
        selected = self.show_disc_tree(
            titles,
            is_tv=False,
            preview_callback=self._preview_title,
        )
        if selected is None:
            self.controller.log("Sandbox manual movie flow cancelled in picker.")
            return

        proceed = self.ask_yesno(
            "Proceed with the sandbox manual movie flow using the selected titles?"
        )
        if not proceed:
            self.controller.log("Sandbox manual movie flow stopped before summary.")
            return

        self._set_fake_step(100, "Sandbox manual movie flow complete.")
        self._show_fake_summary(
            "Sandbox Manual Movie Flow",
            [
                f"Title: {setup.title} ({setup.year})",
                f"Edition: {setup.edition or '(none)'}",
                f"Metadata: {setup.metadata_provider} {setup.metadata_id or '(lookup)'}",
                f"Selected title ids: {selected}",
                "Result: no rip was started.",
            ],
        )

    def _run_fake_tv_flow(self) -> None:
        self._set_fake_step(10, "Sandbox: TV setup.")
        continuing = self.ask_yesno(
            "Simulate continuing an existing TV show folder?"
        )
        if continuing:
            self.controller.log("Sandbox: existing TV folder chosen.")

        setup = self.ask_tv_setup(
            default_title="Planet Earth",
            default_season="1",
            default_metadata_provider="TMDB",
            default_metadata_id="1396",
        )
        if setup is None:
            self.controller.log("Sandbox TV flow cancelled in setup.")
            return

        titles = self._sample_tv_titles()
        self._classified(titles)
        self._set_fake_step(50, "Sandbox: TV title picker.")
        selected = self.show_disc_tree(
            titles,
            is_tv=True,
            preview_callback=self._preview_title,
        )
        if selected is None:
            self.controller.log("Sandbox TV flow cancelled in picker.")
            return

        proceed = self.ask_yesno(
            "Proceed with the sandbox TV flow using the selected titles?"
        )
        if not proceed:
            self.controller.log("Sandbox TV flow stopped before summary.")
            return

        self._set_fake_step(100, "Sandbox TV flow complete.")
        self._show_fake_summary(
            "Sandbox TV Flow",
            [
                f"Series: {setup.title}",
                f"Season: {setup.season}",
                f"Episode mapping: {setup.episode_mapping}",
                f"Selected title ids: {selected}",
                "Result: no rip was started.",
            ],
        )

    def _run_fake_dump_flow(self) -> None:
        self._set_fake_step(15, "Sandbox: dump setup.")
        setup = self.ask_dump_setup(
            default_multi_disc=True,
            default_disc_name="DISC_A",
            default_disc_count="3",
            default_custom_disc_names="DISC_A, DISC_B, DISC_C",
            default_batch_title="Planet Earth Complete Set",
        )
        if setup is None:
            self.controller.log("Sandbox dump flow cancelled in setup.")
            return

        options = [
            "DISC_A - Main disc",
            "DISC_B - Bonus disc",
            "DISC_C - Extras disc",
        ]
        self._set_fake_step(55, "Sandbox: dump review list.")
        selected = self.show_file_list(
            "Sandbox Dump Review",
            "Choose which fake discs stay in this batch plan.",
            options,
        )
        if selected is None:
            self.controller.log("Sandbox dump flow cancelled in review list.")
            return

        self._set_fake_step(100, "Sandbox dump flow complete.")
        self._show_fake_summary(
            "Sandbox Dump Flow",
            [
                f"Multi-disc: {setup.multi_disc}",
                f"Disc count: {setup.disc_count}",
                f"Batch title: {setup.batch_title or '(none)'}",
                f"Reviewed items: {selected}",
                "Result: no scan or dump was started.",
            ],
        )

    def _run_fake_organize_flow(self) -> None:
        self._set_fake_step(10, "Sandbox: organize prompts.")
        library_title = self.ask_input(
            "Library Title",
            "Enter a fake title to organize into Jellyfin",
            default_value="OVER THE HEDGE",
        )
        if library_title is None:
            self.controller.log("Sandbox organize flow cancelled at title input.")
            return

        is_tv = self.ask_yesno("Treat these fake MKVs as TV episodes?")
        options = [
            "Disc_01\\Main Feature.mkv",
            "Disc_01\\Behind The Scenes.mkv",
            "Disc_01\\Deleted Scenes.mkv",
        ]
        self._set_fake_step(55, "Sandbox: organize file picker.")
        selected = self.show_file_list(
            "Sandbox Organize",
            "Choose fake MKVs to move into the target library structure.",
            options,
        )
        if selected is None:
            self.controller.log("Sandbox organize flow cancelled in file list.")
            return

        self._set_fake_step(100, "Sandbox organize flow complete.")
        self._show_fake_summary(
            "Sandbox Organize Flow",
            [
                f"Library title: {library_title or '(skipped)'}",
                f"Media type: {'TV' if is_tv else 'Movie'}",
                f"Selected files: {selected}",
                "Result: no files were moved.",
            ],
        )

    def _run_fake_prep_flow(self) -> None:
        self._set_fake_step(20, "Sandbox: prep scan results.")
        selected = self.show_file_list(
            "Sandbox Prep Queue",
            "Choose fake MKVs to send into a transcode queue.",
            [
                "Movies\\OVER THE HEDGE (2006)\\OVER THE HEDGE.mkv",
                "TV\\Planet Earth\\Season 01\\Planet Earth - s01e01.mkv",
                "TV\\Planet Earth\\Season 01\\Planet Earth - s01e02.mkv",
            ],
        )
        if selected is None:
            self.controller.log("Sandbox prep flow cancelled in queue picker.")
            return

        recommend = self.ask_yesno(
            "Simulate recommendation mode instead of queue building?"
        )
        self._set_fake_step(100, "Sandbox prep flow complete.")
        self._show_fake_summary(
            "Sandbox Prep Flow",
            [
                f"Mode: {'Recommendation' if recommend else 'Queue build'}",
                f"Selected entries: {selected}",
                "Result: no scan, ffprobe, ffmpeg, or HandBrake run occurred.",
            ],
        )


def main() -> None:
    _prepare_startup_environment()
    _set_windows_app_user_model_id()
    _install_sandbox_patches()
    startup = load_startup_config()
    app = FakeJellyRipperGUI(
        startup.config,
        startup_context={
            "issues": [],
            "open_settings": False,
        },
    )
    app.mainloop()


if __name__ == "__main__":
    main()
