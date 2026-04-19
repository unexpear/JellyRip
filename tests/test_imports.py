"""Import smoke tests to guard module boundary regressions."""
import threading
import unittest.mock

import pytest


class _FakeTkBase:
    pass


def test_imports():
    import config  # noqa: F401
    import engine.ripper_engine  # noqa: F401
    import controller.controller  # noqa: F401


def test_gui_import():
    """GUI import must not require a live display.

    main_window.py imports tkinter at module level; patch Tk so this test
    passes on headless CI without a display server.
    """
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window  # noqa: F401


def test_ui_settings_summarize_profile_returns_human_text():
    from transcode.profiles import normalize_profile_data
    from ui.settings import summarize_profile

    summary = summarize_profile(normalize_profile_data({}))

    assert "Video:" in summary
    assert "Audio:" in summary


def test_ui_dialogs_ask_yes_no_wraps_messagebox(monkeypatch):
    import ui.dialogs as dialogs

    prompt = unittest.mock.Mock(return_value=False)
    monkeypatch.setattr(dialogs.messagebox, "askyesno", prompt)

    result = dialogs.ask_yes_no("Title", "Body", parent=None, icon="warning")

    assert result is False
    prompt.assert_called_once_with("Title", "Body", parent=None, icon="warning")


def test_gui_import_exposes_make_rip_folder_name():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window

    assert callable(main_window.make_rip_folder_name)


def test_run_on_main_executes_directly_on_main_thread():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)

    result = gui._run_on_main(lambda: "ok")

    assert result == "ok"


def test_ask_duplicate_resolution_uses_modal_fallback_on_main_thread():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._ask_duplicate_resolution_modal = unittest.mock.Mock(return_value="retry")

    result = gui.ask_duplicate_resolution("dup?")

    assert result == "retry"
    gui._ask_duplicate_resolution_modal.assert_called_once()


def test_ask_space_override_uses_modal_fallback_on_main_thread():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._ask_space_override_modal = unittest.mock.Mock(return_value=True)

    result = gui.ask_space_override(10.0, 5.0)

    assert result is True
    gui._ask_space_override_modal.assert_called_once_with(10.0, 5.0)


def test_ask_input_uses_modal_popup_on_main_thread():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._input_lock = threading.Lock()
    gui.append_log = unittest.mock.Mock()
    gui._ask_input_modal = unittest.mock.Mock(return_value="Movie Name")

    result = gui.ask_input("Title", "Exact title:", default_value="default")

    assert result == "Movie Name"
    gui._ask_input_modal.assert_called_once_with(
        "Title",
        "Exact title:",
        default_value="default",
    )
    gui.append_log.assert_called_once()


def test_ask_yesno_uses_modal_popup_on_main_thread():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._ask_yesno_modal = unittest.mock.Mock(return_value=True)

    result = gui.ask_yesno("Proceed?")

    assert result is True
    gui._ask_yesno_modal.assert_called_once_with("Proceed?")


def test_parse_expert_profile_value_converts_supported_types():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    assert JellyRipperGUI._parse_expert_profile_value(
        "audio.downmix",
        "yes",
        bool,
    ) is True
    assert JellyRipperGUI._parse_expert_profile_value(
        "constraints.skip_if_below_gb",
        "4.5",
        (int, float, type(None)),
    ) == 4.5
    assert JellyRipperGUI._parse_expert_profile_value(
        "video.crf",
        "",
        (int, type(None)),
    ) is None


def test_parse_expert_profile_value_rejects_invalid_input():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    with pytest.raises(ValueError):
        JellyRipperGUI._parse_expert_profile_value("video.crf", "abc", int)


def test_collect_expert_profile_data_returns_typed_profile():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

    base_profile = normalize_profile_data({})
    expert_vars = {}
    for section_name, values in base_profile.items():
        expert_vars[section_name] = {}
        for key, value in values.items():
            expert_vars[section_name][key] = _Var(
                JellyRipperGUI._format_expert_profile_value(value)
            )

    expert_vars["video"]["crf"] = _Var("24")
    expert_vars["audio"]["downmix"] = _Var("true")
    expert_vars["constraints"]["skip_if_below_gb"] = _Var("4.5")

    gui = object.__new__(JellyRipperGUI)
    profile_data = gui._collect_expert_profile_data(
        base_profile,
        expert_vars,
        "Balanced (Recommended)",
    )

    assert profile_data["video"]["crf"] == 24
    assert profile_data["audio"]["downmix"] is True
    assert profile_data["constraints"]["skip_if_below_gb"] == 4.5


def test_load_expert_profile_snapshot_returns_selected_profile(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    cinema_profile = normalize_profile_data({})
    cinema_profile["video"]["crf"] = 18
    loader.add_profile("Cinema", cinema_profile)

    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    snapshot = gui._load_expert_profile_snapshot("Cinema")

    assert snapshot["name"] == "Cinema"
    assert "Cinema" in snapshot["names"]
    assert snapshot["default_name"] == "Balanced (Recommended)"
    assert snapshot["data"]["video"]["crf"] == 18


def test_expert_profile_form_is_dirty_detects_unsaved_changes():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    profile_data = normalize_profile_data({})
    expert_vars = {}
    for section_name, values in profile_data.items():
        expert_vars[section_name] = {}
        for key, value in values.items():
            expert_vars[section_name][key] = _Var(
                JellyRipperGUI._format_expert_profile_value(value)
            )

    gui = object.__new__(JellyRipperGUI)

    assert gui._expert_profile_form_is_dirty(profile_data, expert_vars) is False

    expert_vars["video"]["crf"].set("27")

    assert gui._expert_profile_form_is_dirty(profile_data, expert_vars) is True


def test_populate_expert_profile_vars_handles_bool_var_wrappers():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    profile_data = normalize_profile_data({})
    profile_data["audio"]["downmix"] = True

    expert_vars = {
        "audio": {
            "downmix": JellyRipperGUI._make_expert_var_handle(
                _Var(False),
                "bool",
            )
        }
    }

    gui = object.__new__(JellyRipperGUI)
    gui._populate_expert_profile_vars(expert_vars, profile_data)

    assert expert_vars["audio"]["downmix"]["var"].get() is True


def test_summarize_expert_profile_uses_human_readable_description():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    profile_data = normalize_profile_data({})
    profile_data["video"]["codec"] = "h264"
    profile_data["video"]["crf"] = 20

    gui = object.__new__(JellyRipperGUI)
    summary = gui._summarize_expert_profile(profile_data)

    assert "Video:" in summary
    assert "CRF 20" in summary
    assert "Metadata:" in summary


def test_resolve_transcode_backend_path_uses_detected_fallback(monkeypatch):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI
    from config import ResolvedTool

    gui = object.__new__(JellyRipperGUI)
    gui.cfg = {
        "ffmpeg_path": r"C:\Broken\ffmpeg.exe",
        "opt_allow_path_tool_resolution": False,
    }
    gui._allow_path_tool_resolution = lambda: False

    monkeypatch.setattr(
        main_window,
        "resolve_ffmpeg",
        lambda _path, *, allow_path_lookup=False: ResolvedTool(
            path="",
            source="",
            error="Configured FFmpeg executable failed validation: bad build",
            suggestion_path=r"C:\Bundled\ffmpeg.exe",
            suggestion_source="bundled",
        ),
    )

    path, status = gui._resolve_transcode_backend_path("ffmpeg")

    assert path == r"C:\Bundled\ffmpeg.exe"
    assert "Configured FFmpeg executable failed validation" in status
    assert "Using FFmpeg (bundled): C:\\Bundled\\ffmpeg.exe" in status


def test_confirm_profile_hdr_metadata_save_respects_user_choice(monkeypatch):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    profile_data = normalize_profile_data({})
    profile_data["video"]["extra_video_params"] = "hdr-opt=1:colorprim=bt2020"

    gui = object.__new__(JellyRipperGUI)
    prompt = unittest.mock.Mock(return_value=False)
    monkeypatch.setattr(main_window, "ask_yes_no", prompt)

    result = gui._confirm_profile_hdr_metadata_save(profile_data, parent=None)

    assert result is False
    prompt.assert_called_once()


def test_confirm_discard_dirty_expert_changes_respects_user_choice(monkeypatch):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import normalize_profile_data

    class _Var:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    profile_data = normalize_profile_data({})
    expert_vars = {"video": {"crf": _Var("27")}}

    gui = object.__new__(JellyRipperGUI)
    prompt = unittest.mock.Mock(return_value=False)
    monkeypatch.setattr(main_window, "ask_yes_no", prompt)

    result = gui._confirm_discard_dirty_expert_changes(
        profile_data,
        expert_vars,
        "Discard unsaved Expert profile edits and close Settings?",
        parent=None,
    )

    assert result is False
    prompt.assert_called_once()


def test_save_expert_profile_data_updates_loader(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    profile_data = normalize_profile_data({})
    profile_data["video"]["crf"] = 19

    saved_name = gui._save_expert_profile_data(
        "Balanced (Recommended)",
        profile_data,
    )

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))

    assert saved_name == "Balanced (Recommended)"
    assert reloaded.get_profile(saved_name).to_dict()["video"]["crf"] == 19


def test_persist_settings_and_profile_saves_profile_before_config(tmp_path, monkeypatch):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader

    gui = object.__new__(JellyRipperGUI)
    calls = []
    gui._get_transcode_profile_loader = unittest.mock.Mock(
        return_value=ProfileLoader(str(tmp_path / "profiles.json"))
    )

    gui._save_expert_profile_data = unittest.mock.Mock(
        side_effect=lambda name, data: calls.append(("profile", name, data)) or name
    )
    monkeypatch.setattr(
        main_window,
        "save_config",
        lambda cfg: calls.append(("config", dict(cfg))),
    )

    saved_name = gui._persist_settings_and_profile(
        {"temp_folder": "C:/Temp"},
        expert_profile_name="Balanced (Recommended)",
        expert_profile_data={"video": {"crf": 20}},
    )

    assert saved_name == "Balanced (Recommended)"
    assert calls[0][0] == "profile"
    assert calls[1][0] == "config"


def test_persist_settings_and_profile_rolls_back_profile_on_config_failure(
    tmp_path,
    monkeypatch,
):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    gui = object.__new__(JellyRipperGUI)
    gui.controller = unittest.mock.Mock()
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    updated_profile = normalize_profile_data({})
    updated_profile["video"]["crf"] = 19

    monkeypatch.setattr(
        main_window,
        "save_config",
        unittest.mock.Mock(side_effect=RuntimeError("config failed")),
    )

    with pytest.raises(RuntimeError, match="config failed"):
        gui._persist_settings_and_profile(
            {"temp_folder": "C:/Temp"},
            expert_profile_name="Balanced (Recommended)",
            expert_profile_data=updated_profile,
        )

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))
    assert reloaded.get_profile("Balanced (Recommended)").to_dict()["video"]["crf"] == 22


def test_create_expert_profile_adds_named_profile(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    created_name = gui._create_expert_profile("Cinema")

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))

    assert created_name == "Cinema"
    assert "Cinema" in reloaded.profiles


def test_duplicate_expert_profile_copies_profile_data(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    source_profile = normalize_profile_data({})
    source_profile["video"]["crf"] = 17
    loader.add_profile("Cinema", source_profile)

    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    duplicated_name = gui._duplicate_expert_profile("Cinema", "Cinema Copy")

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))

    assert duplicated_name == "Cinema Copy"
    assert reloaded.get_profile("Cinema Copy").to_dict()["video"]["crf"] == 17


def test_delete_expert_profile_removes_profile_and_returns_next_name(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    loader.add_profile("Cinema", normalize_profile_data({}))
    loader.set_default("Cinema")

    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    next_name = gui._delete_expert_profile("Cinema")

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))

    assert next_name == "Balanced (Recommended)"
    assert "Cinema" not in reloaded.profiles
    assert reloaded.default == "Balanced (Recommended)"


def test_set_default_expert_profile_updates_loader(tmp_path):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    from transcode.profiles import ProfileLoader, normalize_profile_data

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    cinema_profile = normalize_profile_data({})
    loader.add_profile("Cinema", cinema_profile)

    gui = object.__new__(JellyRipperGUI)
    gui._get_transcode_profile_loader = unittest.mock.Mock(return_value=loader)

    default_name = gui._set_default_expert_profile("Cinema")

    reloaded = ProfileLoader(str(tmp_path / "profiles.json"))

    assert default_name == "Cinema"
    assert reloaded.default == "Cinema"


def test_confirm_input_preserves_empty_string():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    class _Var:
        def get(self):
            return "   "

    gui = object.__new__(JellyRipperGUI)
    gui._input_active = True
    gui.input_var = _Var()
    gui._input_event = threading.Event()
    gui._input_result = object()

    gui._confirm_input()

    assert gui._input_result == ""
    assert gui._input_event.is_set()


def test_on_close_destroys_window_without_force_exit(monkeypatch):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        import gui.main_window as main_window
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui.engine = unittest.mock.Mock()
    gui.rip_thread = None
    gui.destroy = unittest.mock.Mock()

    monkeypatch.setattr(
        main_window.messagebox,
        "askokcancel",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        main_window.os,
        "_exit",
        unittest.mock.Mock(side_effect=AssertionError("os._exit should not run")),
    )

    gui.on_close()

    gui.engine.abort.assert_called_once_with()
    gui.destroy.assert_called_once_with()
    main_window.os._exit.assert_not_called()


def test_disable_buttons_keeps_transcode_prep_available():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    class _FakeButton:
        def __init__(self):
            self.state = None

        def config(self, **kwargs):
            self.state = kwargs.get("state")

    gui = object.__new__(JellyRipperGUI)
    gui.mode_buttons = {
        "t": _FakeButton(),
        "m": _FakeButton(),
        "d": _FakeButton(),
        "i": _FakeButton(),
        "scan": _FakeButton(),
    }
    gui.settings_btn = _FakeButton()
    gui.update_btn = _FakeButton()
    gui.abort_btn = _FakeButton()

    gui.disable_buttons()

    assert gui.mode_buttons["t"].state == "disabled"
    assert gui.mode_buttons["m"].state == "disabled"
    assert gui.mode_buttons["d"].state == "disabled"
    assert gui.mode_buttons["i"].state == "disabled"
    assert gui.mode_buttons["scan"].state == "normal"
    assert gui.settings_btn.state == "disabled"
    assert gui.update_btn.state == "disabled"
    assert gui.abort_btn.state == "normal"


def test_pick_movie_mode_yes_uses_smart_rip():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._run_on_main = lambda fn: True
    gui.controller = unittest.mock.Mock()

    result = gui._pick_movie_mode()

    assert result is gui.controller.run_smart_rip


def test_pick_movie_mode_no_uses_manual_movie_flow():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._run_on_main = lambda fn: False
    gui.controller = unittest.mock.Mock()

    result = gui._pick_movie_mode()

    assert result is gui.controller.run_movie_disc


def test_pick_movie_mode_cancel_stops_before_scan():
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._run_on_main = lambda fn: None
    gui.controller = unittest.mock.Mock()

    result = gui._pick_movie_mode()

    assert result is None
    gui.controller.log.assert_called_once_with(
        "Movie mode prompt cancelled before scan."
    )
