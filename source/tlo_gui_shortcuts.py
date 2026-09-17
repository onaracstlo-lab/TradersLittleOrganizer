"""Shared Tkinter keyboard shortcuts used by all TLO GUI applications."""

from __future__ import annotations

__version__ = "v472"

import tkinter as tk
from tkinter import ttk


def configure_centered_ttk_button_text(style: ttk.Style) -> None:
    """Center ttk button/menubutton labels horizontally and vertically.

    ``anchor`` centers the label element within the available button area;
    ``justify`` centers every line of a multi-line button label.  Keeping this
    in the shared GUI helper makes the Inventory and Search applications use
    the same alignment rule regardless of the active Tk theme.
    """
    if style is None:
        return
    for style_name in ("TButton", "TMenubutton"):
        try:
            style.configure(style_name, anchor="center", justify="center")
        except (AttributeError, tk.TclError):
            continue



def bounded_initial_window_size(
    requested_width: int,
    requested_height: int,
    screen_width: int,
    screen_height: int,
    *,
    horizontal_margin: int = 48,
    vertical_margin: int = 96,
) -> tuple[int, int]:
    """Return a first-open client size that stays inside the current screen.

    Margins leave room for ordinary window-manager borders plus a taskbar/dock.
    The helper is intentionally independent of Tk so startup-fit behavior can be
    regression-tested without opening a GUI.
    """
    requested_width = max(1, int(requested_width))
    requested_height = max(1, int(requested_height))
    screen_width = max(1, int(screen_width))
    screen_height = max(1, int(screen_height))
    horizontal_margin = max(0, int(horizontal_margin))
    vertical_margin = max(0, int(vertical_margin))

    available_width = max(1, screen_width - horizontal_margin)
    available_height = max(1, screen_height - vertical_margin)
    return min(requested_width, available_width), min(requested_height, available_height)

def _select_all_entry(event) -> str:
    """Select the complete contents of an Entry/ttk Entry/Combobox."""
    widget = event.widget
    try:
        widget.selection_range(0, tk.END)
        widget.icursor(tk.END)
    except (AttributeError, tk.TclError):
        return ""
    return "break"


def _select_all_text(event) -> str:
    """Select all content in a Text/ScrolledText, including disabled viewers."""
    widget = event.widget
    try:
        widget.tag_remove("sel", "1.0", "end")
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
        widget.see("insert")
    except (AttributeError, tk.TclError):
        return ""
    return "break"


def install_global_ctrl_a(root) -> None:
    """Make Ctrl+A select all in every TLO text-entry or text-view widget.

    Tk/ttk platform defaults are inconsistent for Ctrl+A, especially for ttk
    Entry and Combobox widgets.  Class bindings make the behavior apply to
    widgets created later in dialogs as well as widgets already on screen.
    Text includes ScrolledText's underlying widget, so the main console and
    read-only text viewers get the same select-all behavior.
    """
    if root is None:
        return
    for class_name in ("Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"):
        try:
            root.bind_class(class_name, "<Control-a>", _select_all_entry, add="+")
            root.bind_class(class_name, "<Control-A>", _select_all_entry, add="+")
        except (AttributeError, tk.TclError):
            continue
    try:
        root.bind_class("Text", "<Control-a>", _select_all_text, add="+")
        root.bind_class("Text", "<Control-A>", _select_all_text, add="+")
    except (AttributeError, tk.TclError):
        pass
