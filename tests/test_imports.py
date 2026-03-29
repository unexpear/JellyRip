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
