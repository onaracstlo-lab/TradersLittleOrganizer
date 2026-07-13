__version__ = "v335"
# TLO-GI package version: v335
__version_summary__ = 'Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.'
# TLO-GI version summary: Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.

"""Native-Windows-only drag-and-drop helpers for the TLO Tk GUI.

Tk itself has no built-in file-drop support.  TLO release builds for native
Windows are expected to include tkinterdnd2/TkDND via PyInstaller.  WSL and
regular Linux deliberately do not try to enable this feature.
"""

import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import unquote, urlparse


DND_FILES = "DND_Files"


@dataclass(frozen=True)
class DragDropStatus:
    enabled: bool
    reason: str = ""
    provider: str = ""


def is_windows_platform() -> bool:
    """Return True only for native Windows-style Python runtimes."""
    return os.name == "nt" or sys.platform.startswith(("win32", "cygwin", "msys"))


def is_drag_drop_platform() -> bool:
    """Search Path drag/drop is intentionally limited to native Windows."""
    return is_windows_platform()


def create_tk_root(tk_module):
    """Create the Tk root.

    On native Windows, use tkinterdnd2 because release builds are expected to
    bundle TkDND support.  On WSL/Linux/macOS, create a normal Tk root and do
    not enable Search Path drag/drop.
    """
    if is_drag_drop_platform():
        from tkinterdnd2 import TkinterDnD  # type: ignore

        return TkinterDnD.Tk(), "tkinterdnd2"
    return tk_module.Tk(), ""


def _file_uri_to_path(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme.lower() != "file":
        return value
    netloc = unquote(parsed.netloc or "")
    path = unquote(parsed.path or "")
    if netloc:
        return "\\\\" + netloc + path.replace("/", "\\")
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    return path.replace("/", "\\")


def normalize_dropped_path(value: str) -> str:
    """Normalize one dropped file/folder value for native Windows."""
    path = (value or "").strip()
    if not path:
        return ""
    path = _file_uri_to_path(path)
    if re.match(r"^[A-Za-z]:/", path):
        path = path.replace("/", "\\")
    return os.path.normpath(path)


def split_dropped_paths(widget, data: str) -> list[str]:
    """Split a TkDND payload into normalized path strings."""
    raw = data or ""
    try:
        parts = list(widget.tk.splitlist(raw))
    except Exception:
        parts = [raw]
    paths = [normalize_dropped_path(part) for part in parts]
    return [path for path in paths if path]


def _first_folder_from_drop(widget, data: str) -> Optional[str]:
    for path in split_dropped_paths(widget, data):
        if os.path.isdir(path):
            return path
        if os.path.isfile(path):
            parent = os.path.dirname(path)
            if parent and os.path.isdir(parent):
                return parent
    paths = split_dropped_paths(widget, data)
    return paths[0] if paths else None


def enable_folder_path_drop(
    entry_widget,
    string_var,
    *,
    field_label: str = "Path",
    on_error: Optional[Callable[[str], None]] = None,
) -> DragDropStatus:
    """Enable native-Windows folder drops on a path entry.

    On WSL, Linux, and other non-Windows platforms, no drag/drop registration is
    attempted.  On native Windows, tkinterdnd2/TkDND is assumed to be bundled in
    the release app.  Dropping a folder replaces the path value; dropping a file
    uses its containing folder when available.
    """
    if not is_drag_drop_platform():
        return DragDropStatus(False, "Folder drag/drop is available only in native Windows.")

    clean_label = str(field_label or "Path").strip() or "Path"

    def handle_data(data: str) -> None:
        folder = _first_folder_from_drop(entry_widget, data)
        if not folder:
            if on_error:
                on_error(f"Drop a folder onto the {clean_label} field.")
            return
        string_var.set(folder)
        try:
            entry_widget.icursor("end")
            entry_widget.focus_set()
        except Exception:
            pass

    entry_widget.drop_target_register(DND_FILES)
    entry_widget.dnd_bind("<<Drop>>", lambda event: handle_data(getattr(event, "data", "")))
    return DragDropStatus(True, provider="tkinterdnd2")


def enable_search_path_folder_drop(
    entry_widget,
    string_var,
    *,
    on_error: Optional[Callable[[str], None]] = None,
) -> DragDropStatus:
    """Enable native-Windows folder drops on the Search Path entry."""
    return enable_folder_path_drop(
        entry_widget,
        string_var,
        field_label="Search Path",
        on_error=on_error,
    )


def enable_tagging_path_folder_drop(
    entry_widget,
    string_var,
    *,
    on_error: Optional[Callable[[str], None]] = None,
) -> DragDropStatus:
    """Enable native-Windows folder drops on the Tagger window Tagging Path entry."""
    return enable_folder_path_drop(
        entry_widget,
        string_var,
        field_label="Tagging Path",
        on_error=on_error,
    )
