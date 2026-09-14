__version__ = "v465"

"""Native-Windows-only drag-and-drop helpers for the TLO Tk GUI.

Tk itself has no built-in file-drop support.  TLO release builds for native
Windows are expected to include tkinterdnd2/TkDND via PyInstaller.  WSL and
regular Linux deliberately do not try to enable this feature.
"""

from tlo_diagnostics import debug_suppressed_exception
import os
import re
import sys
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import unquote, urlparse


DND_FILES = "DND_Files"
_VALID_DROP_ACTIONS = {"copy", "move", "link", "ask", "private"}


def _accepted_drop_action(event) -> str:
    """Return the TkDND action that the drop target actually performed."""
    action = str(getattr(event, "action", "") or "").strip().lower()
    return action if action in _VALID_DROP_ACTIONS else "copy"


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


def _search_path_values_from_drop(widget, data: str) -> list[str]:
    """Return every dropped Search Path value in payload order.

    Folders are preserved.  A .txt file is preserved so it can act as an
    inventory-control file.  Other files retain the legacy behavior of using
    their containing folder.  If existence cannot be confirmed (for example a
    transient/network path), keep the normalized dropped value and let normal
    Search Path validation report any problem later.
    """
    values = []
    for path in split_dropped_paths(widget, data):
        if os.path.isdir(path):
            values.append(path)
            continue
        if os.path.isfile(path):
            if path.lower().endswith(".txt"):
                values.append(path)
                continue
            parent = os.path.dirname(path)
            values.append(parent if parent else path)
            continue
        values.append(path)
    return values


def _format_search_path_drop_value(path: str) -> str:
    """Format one dropped path for the semicolon-delimited Search Path field."""
    value = str(path or "").strip()
    if ";" in value:
        return f'"{value}"'
    return value


def _append_search_path_drop_values(existing: str, values: list[str]) -> str:
    """Append dropped Search Path values, inserting semicolon delimiters."""
    additions = [_format_search_path_drop_value(value) for value in values if str(value or "").strip()]
    if not additions:
        return str(existing or "")

    current = str(existing or "").strip()
    joined = ";".join(additions)
    if not current:
        return joined
    if current.endswith(";"):
        return current + joined
    return current + ";" + joined


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

    def handle_drop(event):
        folder = _first_folder_from_drop(entry_widget, getattr(event, "data", ""))
        if not folder:
            if on_error:
                on_error(f"Drop a folder onto the {clean_label} field.")
            return "refuse_drop"
        string_var.set(folder)
        try:
            entry_widget.icursor("end")
            entry_widget.focus_set()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)
        return _accepted_drop_action(event)

    entry_widget.drop_target_register(DND_FILES)
    entry_widget.dnd_bind("<<Drop:DND_Files>>", handle_drop)
    return DragDropStatus(True, provider="tkinterdnd2")


def enable_search_path_folder_drop(
    entry_widget,
    string_var,
    *,
    on_error: Optional[Callable[[str], None]] = None,
) -> DragDropStatus:
    """Enable native-Windows Search Path drops.

    Every dropped folder is used directly. A dropped .txt file is preserved so
    it can be processed as an inventory-control file; other dropped files retain
    the legacy behavior of using their containing folder. Multiple values in one
    drop are separated with semicolons, and later drops append to the existing
    Search Path value instead of replacing it.
    """
    if not is_drag_drop_platform():
        return DragDropStatus(False, "Folder drag/drop is available only in native Windows.")

    def handle_drop(event):
        # TkDND delivers DND_Files as a raw Tcl list in event.data.  splitlist()
        # must see the complete payload so one Explorer drag can contribute every
        # selected item, including braced paths containing spaces.
        values = _search_path_values_from_drop(entry_widget, getattr(event, "data", ""))
        if not values:
            if on_error:
                on_error("Drop one or more folders or .txt control files onto the Path(s) field.")
            return "refuse_drop"
        current = string_var.get() if hasattr(string_var, "get") else ""
        string_var.set(_append_search_path_drop_values(current, values))
        try:
            entry_widget.icursor("end")
            entry_widget.focus_set()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)
        # TkDND requires Drop callbacks to return the action performed.  Returning
        # None causes the target to report a refused drop after we update the field.
        return _accepted_drop_action(event)

    entry_widget.drop_target_register(DND_FILES)
    entry_widget.dnd_bind("<<Drop:DND_Files>>", handle_drop)
    return DragDropStatus(True, provider="tkinterdnd2")


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
