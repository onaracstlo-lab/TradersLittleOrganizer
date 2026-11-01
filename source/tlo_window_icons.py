"""Apply the matching TLO application artwork to a running Tk window.

An executable's PE/.app icon does not set Tk's live title-bar/task-switcher
icon.  Use bundled artwork at runtime; setting the root's default iconphoto
also covers Toplevel windows created later in the application.
"""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from pathlib import Path
import sys
import tkinter as tk


_ICON_NAMES = {
    "main": "tlo-main-icon",
    "search": "tlo-search-icon",
}


def _icon_file(stem: str, suffix: str) -> Path | None:
    """Locate checked-in artwork both in source and in frozen PyInstaller apps."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = base / "icons" / f"{stem}.{suffix}"
    return candidate if candidate.is_file() else None


def install_window_icon(window: tk.Misc, application: str) -> bool:
    """Set Tk's default child-window icon and Windows native icon when available.

    The executable remains usable if an icon cannot be decoded by a platform's
    Tk implementation; missing runtime assets are separately checked in CI.
    """
    stem = _ICON_NAMES[application]
    installed = False
    png = _icon_file(stem, "png")
    if png is not None:
        try:
            photo = tk.PhotoImage(master=window, file=str(png))
            window.iconphoto(True, photo)
            # Tk retains the Tcl image, but keep the Python reference as well.
            window._tlo_window_icon_photo = photo
            installed = True
        except (tk.TclError, OSError):
            pass

    if sys.platform == "win32":
        ico = _icon_file(stem, "ico")
        if ico is not None:
            try:
                window.iconbitmap(str(ico))
                installed = True
            except (tk.TclError, OSError):
                pass
    return installed
