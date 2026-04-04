"""Runtime hook to point tkinter at bundled Tcl/Tk assets."""

import os
import sys
from pathlib import Path


def _set_tk_env():
    if sys.platform != "win32":
        return

    root = Path(getattr(sys, "_MEIPASS", ""))
    tcl_dir = root / "_tcl_data"
    tk_dir = root / "_tk_data"
    if (tcl_dir / "init.tcl").is_file() and tk_dir.is_dir():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))


_set_tk_env()