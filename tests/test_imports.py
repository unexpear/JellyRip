"""Import smoke tests to guard module boundary regressions."""
import unittest.mock


def test_imports():
    import config  # noqa: F401
    import engine.ripper_engine  # noqa: F401
    import controller.controller  # noqa: F401


def test_gui_import():
    """GUI import must not require a live display.

    main_window.py imports tkinter at module level; patch Tk so this test
    passes on headless CI without a display server.
    """
    with unittest.mock.patch("tkinter.Tk"):
        import gui.main_window  # noqa: F401


def test_gui_import_exposes_make_rip_folder_name():
    with unittest.mock.patch("tkinter.Tk"):
        import gui.main_window as main_window

    assert callable(main_window.make_rip_folder_name)


def test_run_on_main_executes_directly_on_main_thread():
    with unittest.mock.patch("tkinter.Tk"):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)

    result = gui._run_on_main(lambda: "ok")

    assert result == "ok"


def test_ask_duplicate_resolution_uses_modal_fallback_on_main_thread():
    with unittest.mock.patch("tkinter.Tk"):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._ask_duplicate_resolution_modal = unittest.mock.Mock(return_value="retry")

    result = gui.ask_duplicate_resolution("dup?")

    assert result == "retry"
    gui._ask_duplicate_resolution_modal.assert_called_once()


def test_ask_space_override_uses_modal_fallback_on_main_thread():
    with unittest.mock.patch("tkinter.Tk"):
        from gui.main_window import JellyRipperGUI

    gui = object.__new__(JellyRipperGUI)
    gui._ask_space_override_modal = unittest.mock.Mock(return_value=True)

    result = gui.ask_space_override(10.0, 5.0)

    assert result is True
    gui._ask_space_override_modal.assert_called_once_with(10.0, 5.0)
