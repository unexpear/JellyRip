"""Main entrypoint for the split package layout."""

from JellyRip import JellyRipperGUI, load_config  # pyright: ignore[reportMissingImports]


def main():
    cfg = load_config()
    app = JellyRipperGUI(cfg)
    app.mainloop()


if __name__ == "__main__":
    main()
