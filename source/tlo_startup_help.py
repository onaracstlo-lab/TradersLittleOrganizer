"""Copyable, actionable TLOHome setup help shared by GUI and CLI startup."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import sys

SETUP_TITLE = "TLO Setup Required - Home Folder Missing"
SETUP_HEADING = "TLO can't start - TLOHome is not set."
INSTALLATION_URL = "https://traderslittleorganizer.com"


def missing_tlo_home_message(app_name: str = "tlo-main") -> str:
    """Give complete, copyable examples, using the executable actually started."""
    executable = str(app_name or "tlo-main").strip()
    if executable.lower().endswith(".exe"):
        executable = executable[:-4]
    if executable not in {
        "tlo-main", "tlo-search", "tlo-tag", "tlo-gi",
        "tlo-research", "tlo-reverse", "tlo-deleteDupes", "setlistFM",
    }:
        executable = "tlo-main"
    windows_command = (
        f'"C:\\.tlo\\apps\\Windows\\{executable}.exe" --TLOHome "C:\\.tlo"'
    )
    linux_command = (
        f'"/mnt/c/.tlo/apps/Linux/{executable}" --TLOHome "/mnt/c/.tlo"'
    )
    return (
        f"{SETUP_HEADING}\n\n"
        "TLOHome tells TLO where to find its settings, databases, and other files. "
        "It is normally the folder where you installed or unzipped TLO.\n\n"
        "How to fix it (choose one method):\n\n"
        "1. Windows command line - enter this complete command:\n"
        f"   {windows_command}\n\n"
        "2. Windows shortcut - right-click your TLO shortcut, choose Properties. "
        "Keep the existing app path in Target and add --TLOHome at the end. "
        "For example, the completed Target field can be:\n"
        f"   {windows_command}\n"
        "   Click OK, then start TLO using the shortcut.\n\n"
        "3. Linux or WSL - for an installation under /mnt/c/.tlo, run:\n"
        f"   {linux_command}\n\n"
        "4. Environment variable - set TLOHome to your TLO folder "
        "and restart TLO.\n\n"
        "These paths are examples. Use the actual folder where you unzipped TLO.\n\n"
        "Installation and Quick Start instructions:\n"
        f"{INSTALLATION_URL}"
    )


def show_missing_tlo_home_dialog(app_name: str = "tlo-main") -> None:
    """Present readable, selectable text and a Copy Instructions button.

    CLI callers should print missing_tlo_home_message() instead. The caller
    can catch an unavailable display and print the same instructions to stderr.
    """
    import tkinter as tk
    from tkinter import ttk

    from tlo_window_icons import install_window_icon

    root = tk.Tk()
    try:
        root.title(SETUP_TITLE)
        install_window_icon(root, "search" if app_name == "tlo-search" else "main")
        root.minsize(610, 380)
        root.geometry("820x570")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        header = ttk.Label(root, text=SETUP_HEADING, font=("TkDefaultFont", 13, "bold"))
        header.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        reading_area = ttk.Frame(root)
        reading_area.grid(row=1, column=0, sticky="nsew", padx=16)
        reading_area.columnconfigure(0, weight=1)
        reading_area.rowconfigure(0, weight=1)
        text = tk.Text(reading_area, wrap="word", padx=12, pady=10,
                       relief="sunken", borderwidth=1)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(reading_area, orient="vertical", command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        text.insert("1.0", missing_tlo_home_message(app_name).split("\n\n", 1)[1])
        text.configure(state="disabled")  # text remains selectable with mouse/Ctrl+C
        buttons = ttk.Frame(root)
        buttons.grid(row=2, column=0, sticky="e", padx=16, pady=(10, 16))

        def copy_instructions() -> None:
            root.clipboard_clear()
            root.clipboard_append(missing_tlo_home_message(app_name))
            root.update_idletasks()

        ttk.Button(buttons, text="Copy Instructions", command=copy_instructions).pack(side="left", padx=(0, 12))
        def open_setup_guide() -> None:
            import webbrowser
            webbrowser.open(INSTALLATION_URL)

        ttk.Button(buttons, text="Open Setup Guide", command=open_setup_guide).pack(side="left", padx=(0, 12))
        ttk.Button(buttons, text="Close", command=root.destroy).pack(side="left")
        root.bind("<Escape>", lambda _event: root.destroy())
        root.mainloop()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def report_missing_tlo_home(app_name: str = "tlo-main") -> int:
    """GUI setup instructions if possible; otherwise print them to stderr."""
    try:
        show_missing_tlo_home_dialog(app_name)
    except Exception:  # noqa: BLE001 - lack of display must not hide recovery instructions
        print(missing_tlo_home_message(app_name), file=sys.stderr)
    return 2
