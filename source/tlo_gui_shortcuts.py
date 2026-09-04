"""Shared Tkinter keyboard shortcuts used by all TLO GUI applications."""

from __future__ import annotations

__version__ = "v433"

import tkinter as tk


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
