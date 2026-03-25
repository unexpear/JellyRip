"""Compatibility entrypoint that forwards to src/JellyRip.py."""

from src.JellyRip import *  # noqa: F401,F403


if __name__ == "__main__":
    cfg = load_config()
    app = JellyRipperGUI(cfg)
    app.mainloop()
