"""Import smoke tests to guard module boundary regressions."""


def test_imports():
    import config  # noqa: F401
    import engine.ripper_engine  # noqa: F401
    import controller.controller  # noqa: F401
    import gui.main_window  # noqa: F401
