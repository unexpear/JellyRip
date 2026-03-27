"""Main entrypoint for the split package layout."""

from config import load_config
from gui.main_window import JellyRipperGUI


def main():
    cfg = load_config()
    app = JellyRipperGUI(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
