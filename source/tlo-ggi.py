"""Tkinter GUI for configuring and running TLO Inventory, Add Shows, and Tag workflows."""

__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import argparse
import io
import os
import queue
import signal
import sys
from console_output_lib import console_emit
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, scrolledtext, ttk

from inventory_parser_lib import Config


class _InventoryStartCancelled(Exception):
    pass
from tlo_options import (
    GUI_CHECKBOX_OPTIONS,
    add_options_to_parser,
    apply_lookup_dependency,
    parse_bool,
    parse_compliant_artist_mode,
)
from tlo_path_inputs import normalize_platform_input_path, resolve_current_storage_volume, resolve_tlo_home as resolve_inventory_tlo_home
from logging_lib import delete_logs_for_tokens
from tlo_bootlist_volume_policy import normalize_volume_action, volume_display_name
from tlo_main_lib import run_inventory
from tlo_tag_lib import TAGGER_TITLE, default_tagging_path, resolve_tlo_home, run_tagger
from tlo_version import BUNDLE_BUILD, DISPLAY_VERSION, versioned_title

# Keep the standalone Tagger dialog intentionally compact. The prior layout
# used an 82-character path field and a 110-character output pane; v298 halves
# those character widths so the dialog occupies about half as much horizontal
# screen space while preserving normal resize behavior.
TAGGER_PATH_ENTRY_WIDTH = 41
TAGGER_OUTPUT_TEXT_WIDTH = 55
TAGGER_MODE_WRAP_PIXELS = 520
TAGGER_DISPLAY_VERSION = versioned_title("TLO Tagger GUI")

from tlo_inventory_update import (
    UPDATER_DISPLAY_VERSION,
    UPDATER_TITLE,
    delete_new_keep_old,
    duplicate_work_items,
    ensure_updater_directories,
    open_paths,
    prepare_updater_config,
    process_duplicate_folder,
    process_new_shows,
    review_paths_for_duplicate,
    updater_delete_script_path,
)
from tlo_dragdrop import create_tk_root, enable_search_path_folder_drop
from tlo_runtime_control import (
    clear_cancel_request,
    request_cancel,
    request_cancel_and_terminate_active_executor,
    terminate_all_children,
    flush_standard_streams,
    request_pause,
    clear_pause,
    is_pause_requested,
)


WINDOW_TITLE = versioned_title("TLO Inventory GUI")


def _format_elapsed_time(seconds):
    try:
        total_seconds = max(0, int(round(float(seconds))))
    except Exception:
        total_seconds = 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


HELP_TEXT = (
    "tlo-ggi.py\n\n"
    "GUI fields and their command-line forms:\n"
    "  TLOHome          --TLOHome DIR\n"
    "  Search Path      --search-path STRING\n"
    "  Tag Path         --tag-path STRING   (tagger only)\n"
    "  Slam             -$slam STRING   (only valid with --search-path)\n"
    "  Compliant        --compliant\n"
    "  Compliant Artist --compliant-artist-mode master|as-is\n"
    "  Tag in Place     --tag-during-inventory\n"
    "  Tag Copy        --tag-copy-during-inventory\n  Destination     --tag-copy-destination DIR\n  Rename Compliantly --rename-compliantly\n  Convert shn     --convert-shn\n"
    "  etreeDB          --etree-lookup\n"
    "  setlist.fm       --setlistfm-lookup\n"
    "  Performance Mode --performance-mode gentle|balanced|fast|extreme\n"
    "  Max Workers      --max-workers N\n"
    "  Silent          --silent   (command-line only; no GUI control)\n"
    "  Debug           --debug [BOOL]   (command-line only; no GUI control)\n"
    "  Current Storage --current-storage-volume STRING   (updater field default; overrides TLOCurrentStorage)\n\n"
    "Argument details:\n"
    "  --TLOHome DIR        Fully qualified existing writable directory path. Defaults from the TLOHome environment variable when present.\n"
    "  --search-path STRING  Override toBeInventoried.txt and process a single search path. May be quoted or unquoted; may begin with [Volume] before the path.\n"
    "                        In the native Windows GUI, drag a folder from File Explorer onto the Search Path field to fill it in.\n"
    "  --tag-path STRING     Optional fully qualified tagger input path. Used only by the Tag workflow; inventory and updater do not use it.\n"
    "  -$slam STRING        Artist override paired with --search-path. Invalid by itself.\n"
    "  --silent             Suppress all console output.\n"
    "  --compliant          Use the simplified compliant Phase 2/3 parsing rules.\n"
    "  --compliant-artist-mode master|as-is  Set compliant artist handling without prompting.\n"
    "  --tag-during-inventory Tag in place during inventory-time tagging; mutually exclusive with --tag-copy-during-inventory.\n"
    "  --tag-copy-during-inventory Copy each music folder before tagging and tag the copy instead of the original.\n  --tag-copy-destination DIR Destination parent directory for Tag Copy. The GUI asks when Tag Copy is selected.\n  --rename-compliantly Rename using the resolved Show Name. With no tag/copy mode in Full Inventory, rename the original folder in place without tagging.\n  --convert-shn        Convert .shn/.shnf files to .flac during Tag or inventory-time tagging, deleting originals only after successful conversion.\n"
    "  --etree-lookup        Enable the GUI etreeDB / eTreeDB venue-location lookup option after artist and yyyy-mm-dd date are identified.\n"
    "  --setlistfm-lookup         If eTreeDB has no usable result, look up venue/location from setlist.fm. Requires --etree-lookup on the command line.\n"
    "  --debug [BOOL]      Command-line only. With no value, enables debug output; also accepts true/false, yes/no, y/n, 1/0. No Debug checkbox is shown in the GUI.\n"
    "  --current-storage-volume STRING  Prepopulate the Add Shows (incremental) Current Backup/Storage Drive and Volume field. Overrides TLOCurrentStorage.\n"
    "\n"
    "GUI buttons:\n"
    "  Tag               Open the TLO Tagger window; displayed at the far left and uses TLOHome/readyForXfer unless --tag-path is supplied. The tagger window has its own Quit button that stops tagging and closes only that window.\n"
    "  Add Shows (incremental)  Open the updater workflow for readyForXfer/staged/dups processing; displayed immediately to the right of Tag.\n"
    "  Quit              Close the GUI. If a run is still active, active workers are stopped and active search-path logs are removed before exit; displayed in the middle.\n"
    "  Inventory (full)  Run the full inventory job and capture console output in the embedded window; displayed as a two-line button in the right-side inventory group.\n"
    "  Pause             Pause traversal between directory operations; displayed in the right-side inventory group.\n"
    "  Resume            Resume a paused traversal; displayed in the right-side inventory group.\n"
    "  ☰ > Help          Opens the upper-right hamburger menu, then Help > About or Help > FAQ.\n"
)


def _default_max_workers_for_mode(mode):
    mode_value = str(mode or "gentle").strip().lower()
    cpu_count = os.cpu_count() or 1
    if mode_value == "gentle":
        return 1
    if mode_value == "balanced":
        return max(1, min(2, cpu_count))
    if mode_value == "fast":
        return max(1, cpu_count)
    if mode_value == "extreme":
        # 0 means "use the mode default"; for extreme that means no
        # performance-mode worker cap in the inventory runner.
        return 0
    return 1


class _QueueWriter(io.TextIOBase):
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(s)
        return len(s)

    def flush(self):
        return None



def _parse_gui_command_line(argv=None):
    """Parse GUI launcher arguments. --myTLO is accepted but intentionally not shown in the GUI."""
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="tlo-ggi.py",
        description="Launch the TLO Inventory GUI.",
        add_help=True,
    )
    parser.add_argument("--TLOHome", dest="TLOHome", default="", help="TLOHome directory. Defaults from the TLOHome environment variable when present.")
    parser.add_argument("--myTLO", dest="myTLO", default="", help=argparse.SUPPRESS)
    parser.add_argument("--tag-path", dest="tagPath", default="", help="Optional fully qualified tagger input path. Tagger-only; inventory/updater ignore it.")
    parser.add_argument("-$slam", "--$slam", dest="search_path_slam_override", default="", help="Artist override paired with --search-path.")
    parser.add_argument("--$copy", dest="search_path_copy_override", default="", help="Per-search-path Tag Copy destination. Only valid with --search-path.")
    parser.add_argument("--$copy-delete", dest="search_path_copy_delete_override", default="", help="Per-search-path Tag Copy and Delete destination. Only valid with --search-path.")
    parser.add_argument("--debug", dest="debug", nargs="?", const=True, default=False, type=parse_bool, metavar="BOOL", help="Command-line only. Enable debug output; optional BOOL accepts true/false, yes/no, y/n, 1/0. This is the only toggle that accepts an optional BOOL for backwards compatibility.")
    add_options_to_parser(parser, fields=(
        "search_path_override",
        "silent",
        "compliant",
        "compliant_artist_mode",
        "tag_during_inventory",
        "tag_copy_during_inventory",
        "tag_copy_destination",
        "tag_copy_and_delete_path",
        "rename_compliantly",
        "convert_shn",
        "etree_lookup",
        "setlistfm_lookup",
        "performance_mode",
        "max_workers",
        "current_storage_volume",
    ))
    args = parser.parse_args(argv_list)
    if getattr(args, "search_path_slam_override", "") and not getattr(args, "search_path_override", ""):
        parser.error("--$slam is only valid with --search-path")
    if getattr(args, "search_path_copy_override", "") and not getattr(args, "search_path_override", ""):
        parser.error("--$copy is only valid with --search-path")
    if getattr(args, "search_path_copy_delete_override", "") and not getattr(args, "search_path_override", ""):
        parser.error("--$copy-delete is only valid with --search-path")
    if getattr(args, "search_path_copy_override", "") and getattr(args, "search_path_copy_delete_override", ""):
        parser.error("--$copy and --$copy-delete are mutually exclusive for a single --search-path")
    if hasattr(args, "max_workers") and int(getattr(args, "max_workers", 0) or 0) < 0:
        parser.error("--max-workers must be an integer >= 0")
    try:
        apply_lookup_dependency(vars(args), mode="strict")
    except ValueError as exc:
        parser.error(str(exc))
    return args

class App:
    def __init__(self, root, cli_args=None):
        self.root = root
        self.cli_args = cli_args or _parse_gui_command_line([])
        self.root.title(WINDOW_TITLE)
        self.queue = queue.Queue()
        self.worker = None
        self.current_config = None
        self.full_inventory_active = False
        self.active_updater_window = None
        self.active_tagger_window = None
        self.tag_button = None
        self.add_shows_button = None
        self.inventory_button = None
        self.pause_button = None
        self.resume_button = None
        self.hamburger_button = None
        self.hamburger_menu = None
        self.help_menu = None
        self._previous_sigint_handler = None
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self._install_sigint_handler()
        self.root.after(100, self._drain)

    def _configure_gui_fonts(self):
        base_font = tkfont.nametofont("TkDefaultFont")
        try:
            target_size = int(base_font.cget("size")) + 2
        except Exception:
            target_size = 12
        self.gui_font_size = target_size
        for font_name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                tkfont.nametofont(font_name).configure(size=target_size)
            except tk.TclError:
                pass
        style = ttk.Style(self.root)
        for style_name in (
            "TLabel",
            "TButton",
            "TEntry",
            "TCombobox",
            "TCheckbutton",
            "TFrame",
        ):
            try:
                style.configure(style_name, font=("", target_size))
            except tk.TclError:
                pass
        style.configure(
            "Large.TCheckbutton",
            font=("", target_size),
            padding=(2, 4, 10, 4),
            indicatorsize=target_size + 4,
        )
        self.main_font = tkfont.Font(size=target_size, weight="bold")
        self.title_font = tkfont.Font(size=target_size, weight="bold")
        try:
            style.configure("Main.TLabel", font=self.main_font)
            style.configure("Main.TButton", font=self.main_font, padding=(8, 7))
            style.configure("Main.TEntry", font=self.main_font)
            style.configure("Main.TCombobox", font=self.main_font)
            style.configure("Main.Large.TCheckbutton", font=self.main_font, padding=(2, 4, 10, 4), indicatorsize=target_size + 4)
        except tk.TclError:
            pass

    def _build(self):
        self._configure_gui_fonts()
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=0)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=1)

        resolved_tlo_home_default = (
            (getattr(self.cli_args, "myTLO", "") or "").strip()
            or (getattr(self.cli_args, "TLOHome", "") or "").strip()
            or os.environ.get("TLOHome", "")
        )
        performance_mode_default = (getattr(self.cli_args, "performance_mode", "balanced") or "balanced").strip().lower()
        cli_max_workers = int(getattr(self.cli_args, "max_workers", 0) or 0)
        cli_max_workers_supplied = bool(hasattr(self.cli_args, "max_workers"))
        initial_max_workers = (
            cli_max_workers
            if cli_max_workers_supplied and cli_max_workers > 0
            else _default_max_workers_for_mode(performance_mode_default)
        )
        self._max_workers_auto_default = not (cli_max_workers_supplied and cli_max_workers > 0)
        self._setting_max_workers_programmatically = False
        defaults = {
            "TLOHome": resolved_tlo_home_default,
            "search_path_override": (getattr(self.cli_args, "search_path_override", "") or "").strip(),
            "search_path_slam_override": (getattr(self.cli_args, "search_path_slam_override", "") or "").strip(),
            "tag_copy_and_delete_path": (getattr(self.cli_args, "tag_copy_and_delete_path", "") or "").strip(),
            "performance_mode": performance_mode_default,
            "max_workers": str(initial_max_workers),
        }
        self.vars = {key: tk.StringVar(value=value) for key, value in defaults.items()}
        self.vars["performance_mode"].trace_add("write", self._sync_max_workers_to_performance_mode)
        self.vars["max_workers"].trace_add("write", self._mark_max_workers_manual)

        row = 0
        ttk.Label(frm, text="Traders Little Organizer™ Inventory App", font=self.title_font).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4)
        )
        self.hamburger_button = ttk.Menubutton(
            frm,
            text="☰",
            style="Main.TButton",
        )
        self.hamburger_menu = tk.Menu(self.hamburger_button, tearoff=False)
        self.help_menu = tk.Menu(self.hamburger_menu, tearoff=False)
        self.help_menu.add_command(label="About", command=self._show_about_from_menu)
        self.help_menu.add_command(label="FAQ", command=self._show_faq_from_menu)
        self.hamburger_menu.add_cascade(label="Help", menu=self.help_menu)
        self.hamburger_button.configure(menu=self.hamburger_menu)
        self.hamburger_button.grid(row=row, column=2, sticky="e", padx=6, pady=(0, 4))
        row += 1

        ttk.Label(frm, text="TLOHome", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(2, 3))
        ttk.Entry(frm, textvariable=self.vars["TLOHome"], width=92, style="Main.TEntry").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(2, 3)
        )
        row += 1

        ttk.Label(frm, text="Search Path", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 1))
        self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=92, style="Main.TEntry")
        self.search_path_entry.grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(4, 1)
        )
        self.search_path_drop_status = self._enable_search_path_drag_drop()
        row += 1
        search_path_note = "(optional/override; may start with [Volume])"
        if getattr(self, "search_path_drop_status", None) and self.search_path_drop_status.enabled:
            search_path_note += " - drag a folder here from File Explorer"
        ttk.Label(frm, text=search_path_note, style="Main.TLabel").grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 6), pady=(0, 4))
        row += 1

        ttk.Label(frm, text="Slam", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 1))
        ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=92, style="Main.TEntry").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(4, 1)
        )
        row += 1
        ttk.Label(frm, text="(optional/override)", style="Main.TLabel").grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 6), pady=(0, 6))
        row += 1

        ttk.Label(frm, text="Tag Copy/Delete Original\n-- Destination Path", style="Main.TLabel", justify="left").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 1))
        ttk.Entry(frm, textvariable=self.vars["tag_copy_and_delete_path"], width=92, style="Main.TEntry").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(4, 1)
        )
        row += 1
        ttk.Label(frm, text="(optional; existing full destination directory; inventory uses copied/moved destination)", style="Main.TLabel").grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 6), pady=(0, 6))
        row += 1

        ttk.Label(frm, text="Performance Mode", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 3))
        self.performance_combo = ttk.Combobox(
            frm,
            textvariable=self.vars["performance_mode"],
            values=("gentle", "balanced", "fast", "extreme"),
            state="readonly",
            width=18,
            style="Main.TCombobox",
        )
        self.performance_combo.grid(row=row, column=1, sticky="w", padx=(12, 6), pady=(4, 3))
        row += 1

        ttk.Label(frm, text="Max Workers", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 3))
        ttk.Entry(frm, textvariable=self.vars["max_workers"], width=12, style="Main.TEntry").grid(
            row=row, column=1, sticky="w", padx=(12, 6), pady=(4, 3)
        )
        row += 1

        self.bool_vars = {
            option.config_field: tk.BooleanVar(value=bool(getattr(self.cli_args, option.config_field, option.default)))
            for option in GUI_CHECKBOX_OPTIONS
        }
        checkbox_frame = ttk.Frame(frm)
        checkbox_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=0, pady=(4, 4))
        checkbox_frame.columnconfigure(0, weight=0)
        checkbox_frame.columnconfigure(1, weight=0)
        checkbox_frame.columnconfigure(2, weight=0)
        for option in GUI_CHECKBOX_OPTIONS:
            checkbox_command = None
            if option.config_field in {"tag_during_inventory", "tag_copy_during_inventory"}:
                checkbox_command = (lambda field=option.config_field: self._tag_mode_clicked(field))
            ttk.Checkbutton(
                checkbox_frame,
                text=option.gui_label,
                variable=self.bool_vars[option.config_field],
                command=checkbox_command,
                style="Main.Large.TCheckbutton",
            ).grid(
                row=option.gui_row,
                column=option.gui_col,
                sticky="w",
                padx=(4, 34 if option.gui_col in (0, 1) else 4),
                pady=(3, 3),
            )
        self._lookup_dependency_syncing = False
        self.bool_vars["setlistfm_lookup"].trace_add("write", self._reapply_lookup_dependency)
        self.bool_vars["etree_lookup"].trace_add("write", self._reapply_lookup_dependency)
        self._tag_mode_syncing = False
        self._reapply_lookup_dependency()
        self._reapply_tag_mode_exclusivity()
        row += 1

        button_frame = ttk.Frame(frm)
        button_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        main_button_style = "Main.TButton"
        left_button_group = ttk.Frame(button_frame)
        left_button_group.grid(row=0, column=0, sticky="w")
        self.tag_button = ttk.Button(
            left_button_group,
            text="Tag\n ",
            command=self._open_tagger,
            style=main_button_style,
        )
        self.tag_button.grid(row=0, column=0, padx=4, sticky="w")
        self.add_shows_button = ttk.Button(
            left_button_group,
            text="Add Shows\n(incremental)",
            command=self._open_add_to_inventory,
            style=main_button_style,
        )
        self.add_shows_button.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Button(
            button_frame,
            text="Quit\n ",
            command=self._on_quit,
            style=main_button_style,
        ).grid(row=0, column=1, padx=4)

        inventory_group = ttk.Frame(button_frame)
        inventory_group.grid(row=0, column=2, sticky="e")
        self.inventory_button = ttk.Button(
            inventory_group,
            text="Inventory\n(full)",
            command=self._start,
            style=main_button_style,
        )
        self.inventory_button.grid(row=0, column=0, padx=4)
        self.pause_button = ttk.Button(
            inventory_group,
            text="Pause\n ",
            command=self._pause_inventory,
            style=main_button_style,
        )
        self.pause_button.grid(row=0, column=1, padx=4)
        self.resume_button = ttk.Button(
            inventory_group,
            text="Resume\n ",
            command=self._resume_inventory,
            style=main_button_style,
        )
        self.resume_button.grid(row=0, column=2, padx=4)
        row += 1

        self.output = scrolledtext.ScrolledText(frm, width=96, height=21, font=tkfont.nametofont("TkFixedFont"))
        self.output.grid(row=row, column=0, columnspan=3, sticky="nsew")
        frm.rowconfigure(row, weight=1)
        self._update_main_action_states()

    def _enable_search_path_drag_drop(self):
        return enable_search_path_folder_drop(
            self.search_path_entry,
            self.vars["search_path_override"],
            on_error=lambda msg: messagebox.showwarning("tlo-ggi", msg, parent=self.root),
        )

    def _run_after_menu_closes(self, callback):
        """Run a hamburger-menu action after Tk has dismissed the posted menu."""
        try:
            self.root.after_idle(callback)
        except tk.TclError:
            callback()

    def _show_about_from_menu(self):
        self._run_after_menu_closes(self._show_about)

    def _show_faq_from_menu(self):
        self._run_after_menu_closes(self._show_faq)

    def _show_about(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("About TLO"))
        dialog.transient(self.root)
        dialog.resizable(False, False)

        about_text = (
            "Traders Little Organizer(TM) - TLO\n"
            f"V1.0Build{BUNDLE_BUILD}\n"
            "TLO is developed by Jay Scarano\n"
            "using ChatGPT and Anthropic/Claude\n"
            "Contact me at: onaracs.tlo of g.mail"
        )
        frame = ttk.Frame(dialog, padding=14)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text=about_text, justify="left", style="Main.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=(0, 12))
        ttk.Button(frame, text="OK", command=dialog.destroy, style="Main.TButton").grid(row=1, column=0, sticky="e", padx=4)
        try:
            dialog.grab_set()
            dialog.focus_force()
        except tk.TclError:
            pass

    def _resolve_faq_path(self):
        tlo_home_value = self.vars.get("TLOHome").get() if hasattr(self, "vars") and "TLOHome" in self.vars else ""
        tlo_home = resolve_inventory_tlo_home(tlo_home_value, getattr(self.cli_args, "myTLO", ""))
        return os.path.join(tlo_home, "TLO-FAQ.txt")

    def _show_faq(self):
        try:
            faq_path = self._resolve_faq_path()
        except Exception as exc:
            messagebox.showerror("TLO FAQ", str(exc), parent=self.root)
            return
        if not os.path.isfile(faq_path):
            messagebox.showerror("TLO FAQ", f"FAQ file not found: {faq_path}", parent=self.root)
            return
        try:
            with open(faq_path, "r", encoding="utf-8") as handle:
                faq_text = handle.read()
        except Exception as exc:
            messagebox.showerror("TLO FAQ", f"Unable to read FAQ file: {exc}", parent=self.root)
            return

        window = tk.Toplevel(self.root)
        window.title(versioned_title("TLO FAQ"))
        window.transient(self.root)
        window.geometry("720x420")
        frame = ttk.Frame(window, padding=8)
        frame.grid(sticky="nsew")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text_widget = scrolledtext.ScrolledText(frame, width=84, height=20, font=tkfont.nametofont("TkFixedFont"), wrap="word")
        text_widget.grid(row=0, column=0, sticky="nsew")
        text_widget.insert("1.0", faq_text)
        text_widget.configure(state="disabled")
        ttk.Button(frame, text="Close", command=window.destroy, style="Main.TButton").grid(row=1, column=0, sticky="e", pady=(8, 0))
        try:
            window.focus_force()
        except tk.TclError:
            pass


    def _worker_is_alive(self):
        return bool(self.worker and self.worker.is_alive())

    def _inventory_is_running(self):
        # Use an explicit GUI workflow flag in addition to thread state.
        # The thread can be between creation/startup/teardown while the run must
        # still be treated as active for mutual-exclusion and pause/resume logic.
        return bool(self.full_inventory_active or self._worker_is_alive())

    def _update_main_action_states(self):
        inventory_active = self._inventory_is_running()
        updater_open = self._updater_is_open()
        tagger_open = self._tagger_is_open()
        try:
            if self.tag_button is not None:
                self.tag_button.configure(state=("disabled" if inventory_active or updater_open or tagger_open else "normal"))
            if self.add_shows_button is not None:
                self.add_shows_button.configure(state=("disabled" if inventory_active or tagger_open else "normal"))
            if self.inventory_button is not None:
                self.inventory_button.configure(state=("disabled" if updater_open or tagger_open or inventory_active else "normal"))
            if self.pause_button is not None:
                self.pause_button.configure(state=("normal" if inventory_active else "disabled"))
            if self.resume_button is not None:
                self.resume_button.configure(state=("normal" if inventory_active else "disabled"))
        except tk.TclError:
            pass

    def _updater_is_open(self):
        updater = getattr(self, "active_updater_window", None)
        if updater is None:
            return False
        window = getattr(updater, "window", None)
        if window is None:
            self.active_updater_window = None
            return False
        try:
            exists = bool(window.winfo_exists())
        except tk.TclError:
            exists = False
        if not exists:
            self.active_updater_window = None
        return exists

    def _tagger_is_open(self):
        tagger = getattr(self, "active_tagger_window", None)
        if tagger is None:
            return False
        window = getattr(tagger, "window", None)
        if window is None:
            self.active_tagger_window = None
            return False
        try:
            exists = bool(window.winfo_exists())
        except tk.TclError:
            exists = False
        if not exists:
            self.active_tagger_window = None
        return exists

    def _focus_active_tagger(self):
        tagger = getattr(self, "active_tagger_window", None)
        window = getattr(tagger, "window", None) if tagger is not None else None
        if window is None:
            return
        try:
            window.deiconify()
            window.lift()
            window.focus_force()
        except tk.TclError:
            pass

    def _focus_active_updater(self):
        updater = getattr(self, "active_updater_window", None)
        window = getattr(updater, "window", None) if updater is not None else None
        if window is None:
            return
        try:
            window.deiconify()
            window.lift()
            window.focus_force()
        except tk.TclError:
            pass

    def _open_tagger(self):
        if self._inventory_is_running():
            messagebox.showwarning(
                "tlo-ggi",
                "Full Inventory is already running. Tag cannot be opened until the full inventory run finishes.",
                parent=self.root,
            )
            return
        if self._updater_is_open():
            messagebox.showwarning(
                "tlo-ggi",
                "Add Shows is open. Tag cannot be opened while Add Shows is open.",
                parent=self.root,
            )
            self._focus_active_updater()
            return
        if self._tagger_is_open():
            self._focus_active_tagger()
            return
        try:
            resolved_home = resolve_tlo_home(
                tlo_home=self.vars["TLOHome"].get().strip(),
                my_tlo=(getattr(self.cli_args, "myTLO", "") or "").strip(),
            )
            tag_path = default_tagging_path(
                tlo_home=resolved_home,
                tag_path=(getattr(self.cli_args, "tagPath", "") or "").strip(),
            )
        except _InventoryStartCancelled:
            return
        except Exception as exc:
            messagebox.showerror("tlo-ggi", str(exc), parent=self.root)
            return
        tag_in_place = bool(self.bool_vars["tag_during_inventory"].get())
        tag_copy = bool(self.bool_vars["tag_copy_during_inventory"].get())
        tag_copy_and_delete_path = self.vars["tag_copy_and_delete_path"].get().strip()
        rename_compliantly = bool(self.bool_vars["rename_compliantly"].get())
        TaggerWindow(
            self,
            tlo_home=resolved_home,
            tag_path=tag_path,
            compliant=bool(self.bool_vars["compliant"].get()),
            etree_lookup=bool(self.bool_vars["etree_lookup"].get()),
            debug=bool(getattr(self.cli_args, "debug", False)),
            tag_in_place=tag_in_place,
            tag_copy=tag_copy,
            tag_copy_destination=str(getattr(self.cli_args, "tag_copy_destination", "") or ""),
            rename_compliantly=rename_compliantly,
            convert_shn=bool(self.bool_vars["convert_shn"].get()),
        )

    def _open_add_to_inventory(self):
        if self._tagger_is_open():
            messagebox.showwarning(
                "tlo-ggi",
                "Tag is open. Add Shows cannot be opened while Tag is open.",
                parent=self.root,
            )
            self._focus_active_tagger()
            return
        if self._inventory_is_running():
            messagebox.showwarning(
                "tlo-ggi",
                "Full Inventory is already running. Add Shows cannot be opened until the full inventory run finishes.",
                parent=self.root,
            )
            return
        if self._updater_is_open():
            self._focus_active_updater()
            return
        try:
            config = self._build_config(for_add_shows=True)
            prepare_updater_config(config)
            ensure_updater_directories(config.TLOHome)
        except _InventoryStartCancelled:
            return
        except Exception as exc:
            messagebox.showerror("tlo-ggi", str(exc), parent=self.root)
            return
        script_path = updater_delete_script_path(config.TLOHome)
        if os.path.exists(script_path):
            self._show_backup_alert(config, script_path)
            return
        AddToInventoryWindow(self, config)

    def _show_backup_alert(self, config, script_path):
        alert = tk.Toplevel(self.root)
        alert.title(versioned_title("TLO Backup Alert"))
        alert.transient(self.root)
        alert.grab_set()
        ttk.Label(
            alert,
            text="TLOHome/deleteBackupFolders already exists. Continue or abort?",
            padding=12,
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        def continue_clicked():
            try:
                alert.grab_release()
            except tk.TclError:
                pass
            alert.destroy()
            if self._inventory_is_running():
                messagebox.showwarning(
                    "tlo-ggi",
                    "Full Inventory is already running. Add Shows cannot be opened until the full inventory run finishes.",
                    parent=self.root,
                )
                return
            if self._updater_is_open():
                self._focus_active_updater()
                return
            AddToInventoryWindow(self, config)

        def abort_clicked():
            try:
                alert.grab_release()
            except tk.TclError:
                pass
            alert.destroy()
            # Abort only cancels the Add Shows (incremental) launch.
            # The main tlo-ggi application remains open.
            try:
                self.root.focus_force()
            except tk.TclError:
                pass

        ttk.Button(alert, text="Continue", command=continue_clicked).grid(row=1, column=0, padx=8, pady=(0, 10))
        ttk.Button(alert, text="Abort", command=abort_clicked).grid(row=1, column=1, padx=8, pady=(0, 10))
        alert.protocol("WM_DELETE_WINDOW", abort_clicked)
        alert.wait_visibility()
        alert.focus_force()



    def _install_sigint_handler(self):
        try:
            self._previous_sigint_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self._handle_sigint)
        except (ValueError, AttributeError):
            self._previous_sigint_handler = None

    def _mark_max_workers_manual(self, *_args):
        if not getattr(self, "_setting_max_workers_programmatically", False):
            self._max_workers_auto_default = False

    def _sync_max_workers_to_performance_mode(self, *_args):
        if not getattr(self, "_max_workers_auto_default", False):
            return
        mode = (self.vars["performance_mode"].get() or "balanced").strip().lower()
        self._setting_max_workers_programmatically = True
        try:
            self.vars["max_workers"].set(str(_default_max_workers_for_mode(mode)))
        finally:
            self._setting_max_workers_programmatically = False

    def _reapply_lookup_dependency(self, *_args):
        if getattr(self, "_lookup_dependency_syncing", False):
            return
        values = {key: bool(var.get()) for key, var in self.bool_vars.items()}
        apply_lookup_dependency(values, mode="auto")
        self._lookup_dependency_syncing = True
        try:
            for key in ("etree_lookup", "setlistfm_lookup"):
                if key in self.bool_vars and bool(self.bool_vars[key].get()) != bool(values.get(key, False)):
                    self.bool_vars[key].set(bool(values.get(key, False)))
        finally:
            self._lookup_dependency_syncing = False

    def _tag_mode_clicked(self, field: str):
        if getattr(self, "_tag_mode_syncing", False):
            return
        self._tag_mode_syncing = True
        try:
            if field == "tag_during_inventory" and bool(self.bool_vars["tag_during_inventory"].get()):
                self.bool_vars["tag_copy_during_inventory"].set(False)
            elif field == "tag_copy_during_inventory" and bool(self.bool_vars["tag_copy_during_inventory"].get()):
                self.bool_vars["tag_during_inventory"].set(False)
        finally:
            self._tag_mode_syncing = False

    def _reapply_tag_mode_exclusivity(self, *_args):
        if bool(self.bool_vars["tag_during_inventory"].get()) and bool(self.bool_vars["tag_copy_during_inventory"].get()):
            self.bool_vars["tag_copy_during_inventory"].set(False)


    def _cleanup_active_logs(self):
        if self.current_config is None:
            return []
        return delete_logs_for_tokens(
            self.current_config.TLOHome,
            getattr(self.current_config, "active_log_tokens", []),
        )

    def _run_on_gui_thread(self, func, *args, **kwargs):
        """Run a GUI callback on the Tk thread and return its result.

        Inventory preparation now runs inside the inventory worker so the main
        window can gray out buttons, show startup output, and respond to Quit
        immediately.  Any Tk prompt needed by that worker must be marshaled
        back to the GUI thread; direct Tk calls from the worker can hang or
        crash on some platforms.
        """
        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)

        done = threading.Event()
        result = {}

        def invoke():
            try:
                result["value"] = func(*args, **kwargs)
            except BaseException as exc:  # propagate back to worker thread
                result["error"] = exc
            finally:
                done.set()

        try:
            self.root.after(0, invoke)
        except tk.TclError as exc:
            raise RuntimeError("GUI closed before the inventory prompt could be shown.") from exc

        done.wait()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _ask_existing_volume_action_threadsafe(self, *args):
        return self._run_on_gui_thread(self._ask_existing_volume_action, *args)

    def _cancel_active_inventory_and_clean_logs(self):
        if self.current_config is not None:
            self.current_config.cancel_requested = True
        terminated = request_cancel_and_terminate_active_executor()
        deleted = self._cleanup_active_logs()
        try:
            self.queue.put(
                f"Inventory cancelled; terminated active worker process(es): {terminated}; "
                f"deleted active log file(s): {len(deleted)}\n"
            )
        except Exception:
            pass
        return deleted

    def _force_exit_after_child_cleanup(self, code: int = 130):
        terminate_all_children()
        flush_standard_streams()
        os._exit(code)

    def _handle_sigint(self, _signum, _frame):
        self._cancel_active_inventory_and_clean_logs()
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass
        self._force_exit_after_child_cleanup(130)

    def _on_quit(self):
        inventory_complete = bool(getattr(self.current_config, "inventory_complete", False))
        scanning_complete = bool(getattr(self.current_config, "inventory_scanning_complete", False))
        worker_alive = bool(self.worker and self.worker.is_alive())

        if worker_alive and not inventory_complete and scanning_complete:
            force_exit = messagebox.askyesno(
                "tlo-ggi",
                "Cleanup, aggregation, or output generation is still running. Force exit now?",
                default=messagebox.NO,
            )
            if not force_exit:
                return

        if worker_alive and not inventory_complete and not scanning_complete:
            messagebox.showinfo(
                "tlo-ggi",
                "Inventory is stopping. It will take a moment to clean up before exiting.",
                parent=self.root,
            )
            self._cancel_active_inventory_and_clean_logs()
            try:
                self.root.quit()
                self.root.destroy()
            except tk.TclError:
                pass
            self._force_exit_after_child_cleanup(130)

        if worker_alive and not inventory_complete and scanning_complete:
            if self.current_config is not None:
                self.current_config.cancel_requested = True
            try:
                self.root.quit()
                self.root.destroy()
            except tk.TclError:
                pass
            self._force_exit_after_child_cleanup(130)

        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    def _prompt_compliant_artist_mode(self):
        if not self.bool_vars["compliant"].get():
            return "master"
        supplied = (getattr(self.cli_args, "compliant_artist_mode", "") or "").strip()
        if supplied:
            return parse_compliant_artist_mode(supplied)
        answer = messagebox.askyesnocancel(
            "tlo-ggi",
            "Compliant inventory artist names:\n\nYes = Master artist name from the artist DB\nNo = As-Is String1 with no artist DB lookup",
            default=messagebox.YES,
            parent=self.root,
        )
        if answer is None:
            return ""
        return "master" if answer else "as-is"

    def _is_valid_copy_destination(self, value: str) -> bool:
        try:
            normalized = normalize_platform_input_path(str(value or "").strip())
        except Exception:
            return False
        return bool(normalized and os.path.isabs(normalized) and os.path.isdir(normalized))

    def _confirm_tag_copy_destination(self, initial_value=None) -> str:
        result = {"destination": ""}
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("Tag Copy"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(
            dialog,
            text=(
                "Tag Copy copies each music folder before tagging.\n"
                "This can use a large amount of disk space. Choose a destination parent folder."
            ),
            justify="left",
            padding=12,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(dialog, text="Destination of Copies", padding=(12, 4)).grid(row=1, column=0, sticky="w")
        if initial_value is None:
            initial_value = getattr(self.cli_args, "tag_copy_destination", "")
        initial = str(initial_value or "").strip()
        dest_var = tk.StringVar(value=normalize_platform_input_path(initial) if initial else "")
        entry = ttk.Entry(dialog, textvariable=dest_var, width=70)
        entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(4, 12), pady=4)
        ok_button = ttk.Button(dialog, text="OK")

        def close_abort():
            result["destination"] = ""
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def close_ok():
            normalized = normalize_platform_input_path(dest_var.get().strip())
            if not self._is_valid_copy_destination(normalized):
                return
            result["destination"] = os.path.normpath(normalized)
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def refresh_ok(*_args):
            ok_button.configure(state=("normal" if self._is_valid_copy_destination(dest_var.get()) else "disabled"))

        dest_var.trace_add("write", refresh_ok)
        ttk.Button(dialog, text="Quit", command=close_abort).grid(row=2, column=1, padx=8, pady=(8, 12), sticky="e")
        ok_button.configure(command=close_ok)
        ok_button.grid(row=2, column=2, padx=(0, 12), pady=(8, 12), sticky="w")
        refresh_ok()
        dialog.protocol("WM_DELETE_WINDOW", close_abort)
        dialog.wait_visibility()
        entry.focus_force()
        dialog.wait_window()
        return result["destination"]


    def _build_config(self, *, for_add_shows=False):
        tlo_home = resolve_inventory_tlo_home(
            tlo_home=self.vars["TLOHome"].get().strip(),
            my_tlo=(getattr(self.cli_args, "myTLO", "") or "").strip(),
            error_type=ValueError,
        )
        silent = bool(getattr(self.cli_args, "silent", False))
        performance_mode = (self.vars["performance_mode"].get() or "balanced").strip().lower()
        if performance_mode not in {"gentle", "balanced", "fast", "extreme"}:
            raise ValueError("Performance Mode must be gentle, balanced, fast, or extreme")
        max_workers_text = self.vars["max_workers"].get().strip()
        max_workers = 0 if not max_workers_text else int(max_workers_text)
        if max_workers < 0:
            raise ValueError("Max Workers must be blank, 0, or a positive integer")
        compliant_artist_mode = self._prompt_compliant_artist_mode()
        if not compliant_artist_mode:
            raise ValueError("Compliant artist selection cancelled")
        rename_compliantly = bool(self.bool_vars["rename_compliantly"].get())
        tag_copy_and_delete_path = self.vars["tag_copy_and_delete_path"].get().strip()
        if tag_copy_and_delete_path:
            normalized_copy_delete = normalize_platform_input_path(tag_copy_and_delete_path.strip().strip('"').strip("'"))
            if not os.path.isabs(normalized_copy_delete) or not os.path.isdir(normalized_copy_delete):
                raise ValueError("Tag Copy and Delete Path must be an existing fully qualified directory path")
            tag_copy_and_delete_path = os.path.normpath(normalized_copy_delete)
        if for_add_shows:
            # Add Shows can rename the readyForXfer folder in place, but it is
            # not an inventory-time tagging workflow and intentionally ignores
            # the main-window Tag in Place / Tag Copy selections.
            tag_in_place = False
            tag_copy = False
        else:
            tag_in_place = bool(self.bool_vars["tag_during_inventory"].get())
            tag_copy = bool(self.bool_vars["tag_copy_during_inventory"].get())
            if tag_in_place and tag_copy:
                raise ValueError("Tag in Place and Tag Copy are mutually exclusive")
        tag_copy_destination = ""
        if tag_copy:
            tag_copy_destination = self._confirm_tag_copy_destination()
            if not tag_copy_destination:
                raise _InventoryStartCancelled()
        config = Config(
            debug=bool(getattr(self.cli_args, "debug", False)),
            silent=silent,
            TLOHome=tlo_home,
            search_path_override=self.vars["search_path_override"].get().strip(),
            search_path_slam_override=self.vars["search_path_slam_override"].get().strip(),
            search_path_copy_override=(getattr(self.cli_args, "search_path_copy_override", "") or "").strip(),
            search_path_copy_delete_override=(getattr(self.cli_args, "search_path_copy_delete_override", "") or "").strip(),
            compliant=self.bool_vars["compliant"].get(),
            compliant_artist_mode=compliant_artist_mode,
            tag_during_inventory=tag_in_place,
            tag_copy_during_inventory=tag_copy,
            tag_copy_destination=tag_copy_destination,
            tag_copy_and_delete_path=tag_copy_and_delete_path,
            rename_compliantly=rename_compliantly,
            convert_shn=self.bool_vars["convert_shn"].get(),
            etree_lookup=self.bool_vars["etree_lookup"].get(),
            setlistfm_lookup=self.bool_vars["setlistfm_lookup"].get(),
            performance_mode=performance_mode,
            max_workers=max_workers,
        )
        config.current_volume_label = resolve_current_storage_volume(getattr(self.cli_args, "current_storage_volume", None))
        config.capacity_alert_callback = self._show_copy_capacity_alert_threadsafe
        apply_lookup_dependency(vars(config), mode="auto")
        return config

    def _pause_inventory(self):
        if not self._inventory_is_running():
            return
        if is_pause_requested(self.current_config):
            self.queue.put("Inventory is already paused.\n")
            return
        request_pause()
        self.queue.put("Inventory paused. Click Resume to continue.\n")

    def _resume_inventory(self):
        if not self._inventory_is_running():
            return
        if not is_pause_requested(self.current_config):
            self.queue.put("Inventory is not paused.\n")
            return
        clear_pause()
        self.queue.put("Inventory resumed.\n")

    def _finish_inventory_thread(self):
        # The GUI thread may run this callback while the worker thread is still
        # unwinding from a startup failure, such as a copy-destination capacity
        # error.  Clear both the explicit inventory-active flag and the worker
        # reference before recomputing button states so the main actions are
        # restored immediately after the alert is dismissed.
        self.full_inventory_active = False
        self.worker = None
        self._update_main_action_states()


    def _ask_existing_volume_action(self, *args):
        """Ask how to handle existing group-log collisions.

        v208 passes a list of collision dictionaries and expects a mapping of
        item_index -> action.  Older callback signatures are also accepted so
        tests or stale callers do not break abruptly.
        """
        if len(args) == 1 and isinstance(args[0], list):
            collisions = list(args[0])
            if not collisions:
                return {}
            if len(collisions) == 1:
                item = collisions[0]
                action = self._ask_single_existing_path_action(item)
                return {item.get("item_index", 0): action}
            return self._ask_multiple_existing_path_actions(collisions)

        # Legacy path: volume, existing_count, queued_count or volume, path,
        # existing_count, queued_count.  Present only Skip/Re-inventory.
        if len(args) >= 4:
            volume_label, path_name, row_count, path_count = args[:4]
        else:
            volume_label = args[0] if len(args) > 0 else ""
            path_name = ""
            row_count = args[1] if len(args) > 1 else 0
            path_count = args[2] if len(args) > 2 else 1
        item = {
            "item_index": 0,
            "volume": volume_label,
            "path": path_name,
            "related_count": row_count,
            "related_group_paths": [],
        }
        return self._ask_single_existing_path_action(item)

    def _ask_single_existing_path_action(self, item):
        result = {"action": "reinventory"}
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("Existing TLO Inventory"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        volume_label = item.get("volume", "")
        path_name = item.get("path", "")
        related_count = item.get("related_count", 0)
        related_paths = [p for p in item.get("related_group_paths", []) if p]
        detail = ""
        if related_paths:
            shown = "\n".join(f"  {p}" for p in related_paths[:5])
            if len(related_paths) > 5:
                shown += f"\n  ... {len(related_paths) - 5} more"
            detail = f"\n\nRelated prior group-log path(s):\n{shown}"
        label_text = (
            f"Search path [{volume_label}] {path_name} overlaps {related_count} existing group log entry/entries.\n\n"
            "Skip aborts inventory for this path.\n"
            "Re-inventory scans this path now and replaces prior output for this path/subtree."
            f"{detail}"
        )
        ttk.Label(dialog, text=label_text, padding=12, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")

        def choose(action):
            result["action"] = normalize_volume_action(action)
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        ttk.Button(dialog, text="Skip", command=lambda: choose("skip")).grid(row=1, column=0, padx=8, pady=(0, 12))
        ttk.Button(dialog, text="Re-inventory", command=lambda: choose("re-inventory")).grid(row=1, column=1, padx=8, pady=(0, 12))
        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("re-inventory"))
        dialog.wait_visibility()
        dialog.focus_force()
        dialog.wait_window()
        return result["action"]

    def _ask_multiple_existing_path_actions(self, collisions):
        result = {item.get("item_index", idx): "reinventory" for idx, item in enumerate(collisions)}
        variables = {}
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("Existing TLO Inventory"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)
        ttk.Label(
            dialog,
            text="Some queued search paths overlap existing group logs. Choose Skip or Re-inventory for each path.",
            padding=12,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        for row, item in enumerate(collisions, start=1):
            key = item.get("item_index", row - 1)
            var = tk.StringVar(value="reinventory")
            variables[key] = var
            volume_label = item.get("volume", "")
            path_name = item.get("path", "")
            related_count = item.get("related_count", 0)
            ttk.Label(dialog, text=f"[{volume_label}] {path_name}\n{related_count} related group-log entry/entries", justify="left").grid(row=row, column=0, sticky="w", padx=12, pady=4)
            ttk.Radiobutton(dialog, text="Skip", variable=var, value="skip").grid(row=row, column=1, sticky="w", padx=8, pady=4)
            ttk.Radiobutton(dialog, text="Re-inventory", variable=var, value="reinventory").grid(row=row, column=2, sticky="w", padx=8, pady=4)

        def choose():
            for key, var in variables.items():
                result[key] = normalize_volume_action(var.get())
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        ttk.Button(dialog, text="Continue", command=choose).grid(row=len(collisions) + 1, column=0, columnspan=3, pady=(8, 12))
        dialog.protocol("WM_DELETE_WINDOW", choose)
        dialog.wait_visibility()
        dialog.focus_force()
        dialog.wait_window()
        return result

    def _show_copy_capacity_alert_threadsafe(self, message):
        done = threading.Event()

        def show():
            try:
                messagebox.showerror("TLO copy destination capacity", str(message), parent=self.root)
            finally:
                done.set()

        try:
            self.root.after(0, show)
            done.wait()
        except Exception:
            done.set()

    def _start(self):
        if self._tagger_is_open():
            messagebox.showwarning(
                "tlo-ggi",
                "Tag is open. Full Inventory cannot be started while Tag is open.",
                parent=self.root,
            )
            self._focus_active_tagger()
            return
        if self._inventory_is_running():
            messagebox.showinfo("tlo-ggi", "Full Inventory is already running.", parent=self.root)
            return
        if self._updater_is_open():
            messagebox.showwarning(
                "tlo-ggi",
                "Add Shows is open. Full Inventory cannot be started while Add Shows is open.",
                parent=self.root,
            )
            self._focus_active_updater()
            return
        try:
            config = self._build_config()
            config.volume_action_callback = self._ask_existing_volume_action_threadsafe
        except _InventoryStartCancelled:
            return
        except Exception as exc:
            messagebox.showerror("tlo-ggi", str(exc), parent=self.root)
            return
        clear_cancel_request()
        clear_pause()
        config.cancel_requested = False
        self.output.delete("1.0", tk.END)
        self.current_config = config
        self.full_inventory_active = True
        self._update_main_action_states()
        self.queue.put("Inventory request accepted; preparing inventory roots.\n")

        def target():
            old_out, old_err = sys.stdout, sys.stderr
            writer = _QueueWriter(self.queue)
            sys.stdout = writer
            sys.stderr = writer
            try:
                run_inventory(config)
            except Exception as exc:
                self.queue.put(f"ERROR: {exc}\n")
            finally:
                sys.stdout = old_out
                sys.stderr = old_err
                try:
                    self.root.after(0, self._finish_inventory_thread)
                except tk.TclError:
                    self.full_inventory_active = False
                    self.worker = None

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _drain(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self.output.insert(tk.END, msg)
                self.output.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)



class TaggerWindow:
    def __init__(
        self,
        parent_app,
        tlo_home,
        tag_path,
        compliant=False,
        etree_lookup=False,
        debug=False,
        tag_in_place=True,
        tag_copy=False,
        tag_copy_destination="",
        rename_compliantly=False,
        convert_shn=False,
    ):
        self.parent_app = parent_app
        self.tlo_home = tlo_home
        self.compliant = bool(compliant)
        self.etree_lookup = bool(etree_lookup)
        self.debug = bool(debug)
        self.tag_copy_destination = str(tag_copy_destination or "")
        self.tag_copy = bool(tag_copy)
        self.tag_in_place = bool(tag_in_place) and not self.tag_copy
        if not self.tag_in_place and not self.tag_copy:
            self.tag_in_place = True
        self.rename_compliantly = bool(rename_compliantly)
        self.convert_shn = bool(convert_shn)
        self.queue = queue.Queue()
        self.worker = None
        self._processing = False
        self._closed = False
        self._tag_cancel_requested = False
        self._tag_start_monotonic = None
        self.window = tk.Toplevel(parent_app.root)
        parent_app.active_tagger_window = self
        parent_app._update_main_action_states()
        self.window.title(TAGGER_DISPLAY_VERSION)
        self.window.protocol("WM_DELETE_WINDOW", self._request_exit)
        self.path_var = tk.StringVar(value=tag_path or "")
        self._build()
        self.window.after(100, self._drain)

    def _build(self):
        frm = ttk.Frame(self.window, padding=10)
        frm.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        title_font = getattr(self.parent_app, "title_font", None) or tkfont.Font(size=12, weight="bold")
        ttk.Label(frm, text=TAGGER_TITLE, font=title_font).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2)
        )
        tag_mode_label = "Tag Copy" if self.tag_copy else "Tag in Place"
        ttk.Label(
            frm,
            text=(
                f"Mode: {'Compliant' if self.compliant else 'Non-compliant'} | "
                f"eTreeDB title fallback: {'on' if self.etree_lookup else 'off'} | "
                f"Tag mode: {tag_mode_label} | "
                f"Rename Compliantly: {'on' if self.rename_compliantly else 'off'} | "
                f"Convert shn: {'on' if self.convert_shn else 'off'}"
            ),
            wraplength=TAGGER_MODE_WRAP_PIXELS,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(frm, text="Tagging Path:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frm, textvariable=self.path_var, width=TAGGER_PATH_ENTRY_WIDTH).grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)

        buttons = ttk.Frame(frm)
        buttons.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 6))
        self.tag_run_button = ttk.Button(buttons, text="Tag", command=self._start_tagging)
        self.tag_run_button.grid(row=0, column=0, padx=(0, 6))
        self.exit_button = ttk.Button(buttons, text="Quit", command=self._request_exit)
        self.exit_button.grid(row=0, column=1, padx=6)

        self.output = scrolledtext.ScrolledText(frm, width=TAGGER_OUTPUT_TEXT_WIDTH, height=28, font=tkfont.nametofont("TkFixedFont"))
        self.output.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        frm.rowconfigure(4, weight=1)

    def _set_processing_controls(self, enabled):
        tag_state = "normal" if enabled else "disabled"
        tag_button = getattr(self, "tag_run_button", None)
        if tag_button is not None:
            try:
                tag_button.configure(state=tag_state)
            except tk.TclError:
                pass
        # Quit must remain available while tagging is running so the user can
        # stop the tagger window without closing the main Inventory GUI.
        exit_button = getattr(self, "exit_button", None)
        if exit_button is not None:
            try:
                exit_button.configure(state="normal")
            except tk.TclError:
                pass

    def _start_tagging(self):
        if self._processing:
            messagebox.showinfo("TLO Tagger", "Tagging is already running.", parent=self.window)
            return
        tag_path = self.path_var.get().strip()
        tag_copy = bool(self.tag_copy)
        tag_copy_destination = ""
        if tag_copy:
            tag_copy_destination = self.parent_app._confirm_tag_copy_destination(self.tag_copy_destination)
            if not tag_copy_destination:
                return
            self.tag_copy_destination = tag_copy_destination
        self.output.delete("1.0", tk.END)
        self._tag_cancel_requested = False
        self._tag_start_monotonic = time.monotonic()
        self._processing = True
        self._set_processing_controls(False)
        self.parent_app._update_main_action_states()

        def worker():
            try:
                run_tagger(
                    tlo_home=self.tlo_home,
                    compliant=self.compliant,
                    tag_path=tag_path,
                    etree_lookup=self.etree_lookup,
                    debug=self.debug,
                    tag_in_place=bool(self.tag_in_place),
                    tag_copy=tag_copy,
                    tag_copy_destination=tag_copy_destination,
                    rename_compliantly=bool(self.rename_compliantly),
                    convert_shn=self.convert_shn,
                    emit=self.queue.put,
                )
                error = None
            except Exception as exc:
                error = exc
            try:
                self.parent_app.root.after(0, lambda: self._finish_tagging(error))
            except tk.TclError:
                pass

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _finish_tagging(self, error):
        elapsed_text = None
        if self._tag_start_monotonic is not None:
            elapsed_text = _format_elapsed_time(time.monotonic() - self._tag_start_monotonic)
        self._tag_start_monotonic = None
        self._processing = False
        self.worker = None
        if self._closed:
            if getattr(self.parent_app, "active_tagger_window", None) is self:
                self.parent_app.active_tagger_window = None
            self.parent_app._update_main_action_states()
            return
        self._set_processing_controls(True)
        self.parent_app._update_main_action_states()
        if error is not None:
            self.queue.put(f"ERROR: {error}\n")
        if elapsed_text is not None:
            self.queue.put(f"Elapsed time: {elapsed_text}\n")
        if error is not None:
            messagebox.showerror("TLO Tagger", str(error), parent=self.window)

    def _request_exit(self):
        if self._processing:
            self._tag_cancel_requested = True
            request_cancel()
            try:
                self.queue.put("Tagger quit requested; stopping active tagging work.\n")
            except Exception:
                pass
            # Close the tagger window immediately, but keep the main GUI's
            # conflicting actions disabled until the worker observes the cancel
            # request and exits. This prevents a new inventory/tag run from
            # clearing the cancel flag before the old tagger has stopped.
            self._destroy_tagger_window(release_main=False)
            return
        self._destroy_tagger_window()

    def _destroy_tagger_window(self, release_main=True):
        self._closed = True
        if release_main and getattr(self.parent_app, "active_tagger_window", None) is self:
            self.parent_app.active_tagger_window = None
        try:
            self.parent_app._update_main_action_states()
        except Exception:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _drain(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                self.output.insert(tk.END, msg)
                self.output.see(tk.END)
        except queue.Empty:
            pass
        try:
            self.window.after(100, self._drain)
        except tk.TclError:
            pass


class AddToInventoryWindow:
    def __init__(self, parent_app, config):
        self.parent_app = parent_app
        self.config = config
        self.child_windows = []
        self._processing = False
        self._processing_thread = None
        self._close_after_processing = False
        self._finish_notice_shown = False
        self.window = tk.Toplevel(parent_app.root)
        parent_app.active_updater_window = self
        parent_app._update_main_action_states()
        self.window.title(UPDATER_DISPLAY_VERSION)
        self.window.protocol("WM_DELETE_WINDOW", self._request_exit)
        self._build()

    def _build(self):
        frm = ttk.Frame(self.window, padding=10)
        frm.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        title_font = getattr(self.parent_app, "title_font", None) or tkfont.Font(size=12, weight="bold")
        ttk.Label(frm, text=UPDATER_TITLE, font=title_font).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.volume_var = tk.StringVar(value=getattr(self.config, "current_volume_label", "") or "")
        self.check_dups_var = tk.BooleanVar(value=True)

        ttk.Label(frm, text="Current Backup/Storage Drive and Volume").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frm, textvariable=self.volume_var, width=56).grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Checkbutton(frm, text="Check for Duplicates", variable=self.check_dups_var).grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 1))
        ttk.Label(
            frm,
            text=(
                f"Mode: {'Compliant' if bool(getattr(self.config, 'compliant', False)) else 'Non-compliant'} | "
                f"Rename Compliantly: {'on' if bool(getattr(self.config, 'rename_compliantly', False)) else 'off'}"
            ),
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(1, 8))

        buttons = ttk.Frame(frm)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.process_new_button = ttk.Button(buttons, text="Process New Shows", command=self._process_new_shows)
        self.process_new_button.grid(row=0, column=0, padx=(0, 6))
        self.process_dups_button = ttk.Button(buttons, text="Process Potential\nDuplicate/Upgrades", command=self._process_duplicates)
        self.process_dups_button.grid(row=0, column=1, padx=6)
        self.exit_button = ttk.Button(buttons, text="Exit", command=self._request_exit)
        self.exit_button.grid(row=0, column=2, padx=6)

    def _refresh_config(self):
        self.config.current_volume_label = self.volume_var.get().strip()
        return self.config

    def _set_processing_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        for button_name in ("process_new_button", "process_dups_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                try:
                    button.configure(state=state)
                except tk.TclError:
                    pass

    def _start_background_task(self, task_name, worker_func, done_func):
        if self._processing:
            messagebox.showinfo("TLO Inventory Updater", "Processing is already running.", parent=self.window)
            return False
        self._processing = True
        self._close_after_processing = False
        self._finish_notice_shown = False
        self._set_processing_controls(False)

        def run_task():
            try:
                result = worker_func()
                error = None
            except Exception as exc:
                result = None
                error = exc
            try:
                self.parent_app.root.after(0, lambda: self._finish_background_task(task_name, result, error, done_func))
            except tk.TclError:
                pass

        self._processing_thread = threading.Thread(target=run_task, daemon=True)
        self._processing_thread.start()
        return True

    def _finish_background_task(self, task_name, result, error, done_func):
        self._processing = False
        self._processing_thread = None
        self._set_processing_controls(True)
        should_close = bool(self._close_after_processing)
        self._close_after_processing = False

        if error is not None:
            if not should_close:
                messagebox.showerror("TLO Inventory Updater", str(error), parent=self.window)
            else:
                messagebox.showerror("TLO Inventory Updater", f"{task_name} did not complete: {error}", parent=self.window)
                self._destroy_updater_window()
            return

        if should_close:
            self._destroy_updater_window()
            return

        done_func(result)

    def _bootlist_path(self):
        return os.path.join(self.config.TLOHome, "bootlist.csv")

    def _confirm_first_add_shows_run(self, current_volume):
        if os.path.exists(self._bootlist_path()):
            return True
        if not current_volume:
            messagebox.showwarning(
                "TLO Inventory Updater",
                (
                    "No existing bootlist.csv was found. Add Shows can create a new bootlist "
                    "from readyForXfer, but this is normally used after a full inventory. "
                    "Enter the Current Backup/Storage Drive and Volume before continuing."
                ),
                parent=self.window,
            )
            return False
        return messagebox.askokcancel(
            "TLO Inventory Updater",
            (
                "No existing bootlist.csv was found. Add Shows can create a new bootlist "
                "from readyForXfer, but this is normally used after a full inventory. "
                "Continue with Add Shows as the first inventory output?"
            ),
            parent=self.window,
        )

    def _process_new_shows(self):
        self._refresh_config()
        current_volume = self.volume_var.get().strip()
        check_duplicates = bool(self.check_dups_var.get())
        if not self._confirm_first_add_shows_run(current_volume):
            return

        def worker():
            return process_new_shows(
                self.config,
                current_volume=current_volume,
                check_duplicates=check_duplicates,
            )

        self._start_background_task("Process New Shows", worker, self._show_process_new_result)

    def _show_process_new_result(self, result):
        processed = int(result.get("processed", 0) or 0)
        duplicates = int(result.get("duplicates", 0) or 0)
        errors = int(result.get("errors", 0) or 0)
        staged = int(result.get("staged", 0) or 0)
        if processed <= 0:
            messagebox.showinfo("TLO Inventory Updater", "There are no shows to process.", parent=self.window)
        elif errors > 0:
            messagebox.showwarning(
                "TLO Inventory Updater",
                f"Processing complete. {staged} staged, {duplicates} potential duplicate shows identified, {errors} folder error(s).",
                parent=self.window,
            )
        elif duplicates > 0:
            messagebox.showinfo(
                "TLO Inventory Updater",
                f"Processing complete. {duplicates} potential duplicate shows identified",
                parent=self.window,
            )
        else:
            messagebox.showinfo("TLO Inventory Updater", "Processing complete.", parent=self.window)

    def _process_duplicates(self):
        self._refresh_config()

        def worker():
            return duplicate_work_items(self.config)

        self._start_background_task("Process Potential Duplicate/Upgrades", worker, self._show_duplicate_work_items)

    def _show_duplicate_work_items(self, items):
        if not items:
            messagebox.showinfo("TLO Inventory Updater", "There are no potential duplicate/upgrade folders to process.", parent=self.window)
            return
        self._duplicate_batch_active = True
        self._duplicate_batch_reported_complete = False
        for item in items:
            child = DuplicateHandlerWindow(self, item)
            self.child_windows.append(child)

    def _remove_child(self, child, completed_action=False):
        self.child_windows = [item for item in self.child_windows if item is not child]
        if completed_action and getattr(self, "_duplicate_batch_active", False):
            self._maybe_report_duplicate_batch_complete()

    def _maybe_report_duplicate_batch_complete(self):
        if self.child_windows or getattr(self, "_duplicate_batch_reported_complete", False):
            return
        try:
            remaining = duplicate_work_items(self.config)
        except Exception:
            remaining = []
        if remaining:
            return
        self._duplicate_batch_reported_complete = True
        self._duplicate_batch_active = False
        messagebox.showinfo("TLO Inventory Updater", "Processing complete.", parent=self.window)
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
        except tk.TclError:
            pass

    def _request_exit(self):
        if self._processing:
            self._close_after_processing = True
            if not self._finish_notice_shown:
                self._finish_notice_shown = True
                messagebox.showinfo(
                    "TLO Inventory Updater",
                    "Processing is still running. The updater will finish the current task before closing.",
                    parent=self.window,
                )
            return
        self._destroy_updater_window()

    def _destroy_updater_window(self):
        for child in list(self.child_windows):
            child.close_no_action()
        if getattr(self.parent_app, "active_updater_window", None) is self:
            self.parent_app.active_updater_window = None
        try:
            self.parent_app._update_main_action_states()
        except Exception:
            pass
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    # Backwards-compatible alias for older internal call sites/tests.
    def _exit(self):
        self._request_exit()


class DuplicateHandlerWindow:
    def __init__(self, updater_window, item):
        self.updater_window = updater_window
        self.config = updater_window.config
        self.item = item
        self.matches = list(item.get("matches") or [])
        self.window = tk.Toplevel(updater_window.window)
        self.window.title(versioned_title("TLO Handle Duplicates"))
        self.window.protocol("WM_DELETE_WINDOW", self.close_no_action)
        self._build()

    def _build(self):
        frm = ttk.Frame(self.window, padding=10)
        frm.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        title_font = getattr(self.updater_window.parent_app, "title_font", None) or tkfont.Font(size=12, weight="bold")
        show_name = str(self.item.get("show_name") or "")
        ttk.Label(frm, text=f"New Folder: {show_name}", font=title_font).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(frm, text=f"New Folder: {show_name}").grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.listbox = tk.Listbox(frm, selectmode=tk.EXTENDED, width=100, height=min(12, max(4, len(self.matches))))
        self.listbox.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        frm.rowconfigure(2, weight=1)
        for row in self.matches:
            show = row.get("Show", "")
            volume_path = row.get("VolumePath", "")
            display = f"{show}    {volume_path}" if volume_path else show
            self.listbox.insert(tk.END, display)

        buttons = ttk.Frame(frm)
        buttons.grid(row=3, column=0, sticky="w")
        ttk.Button(buttons, text="Review Selected Txt Files", command=self._review_selected_txt_files).grid(row=0, column=0, padx=(0, 6), pady=3)
        ttk.Button(buttons, text="Process Folders (Delete/Move)", command=self._process_folders).grid(row=0, column=1, padx=6, pady=3)
        ttk.Button(buttons, text="Delete New / Keep Old", command=self._delete_new_keep_old).grid(row=0, column=2, padx=6, pady=3)
        ttk.Button(buttons, text="Quit", command=self.close_no_action).grid(row=0, column=3, padx=6, pady=3)
        note_font = tkfont.Font(size=max(8, getattr(self.updater_window.parent_app, "gui_font_size", 10) - 2), weight="bold")
        ttk.Label(buttons, text="Keep all when none selected", font=note_font).grid(row=1, column=1, sticky="n", padx=6, pady=(0, 0))

    def _selected_rows(self):
        indices = list(self.listbox.curselection())
        return [self.matches[index] for index in indices]

    def _rows_for_review(self):
        selected = self._selected_rows()
        return selected if selected else list(self.matches)

    def _open_text_review_window(self, path_name):
        review = tk.Toplevel(self.window)
        review.title(versioned_title(f"TLO Txt Review - {os.path.basename(path_name)}"))
        review.columnconfigure(0, weight=1)
        review.rowconfigure(1, weight=1)
        ttk.Label(review, text=path_name, padding=(8, 8, 8, 4)).grid(row=0, column=0, sticky="w")
        viewer = scrolledtext.ScrolledText(review, width=110, height=34, font=tkfont.nametofont("TkFixedFont"))
        viewer.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        try:
            with open(path_name, "r", encoding="utf-8", errors="replace") as infile:
                text = infile.read()
        except Exception as exc:
            text = f"Unable to read file: {exc}"
        viewer.insert("1.0", text)
        viewer.configure(state="disabled")
        ttk.Button(review, text="Close", command=review.destroy).grid(row=2, column=0, sticky="e", padx=8, pady=(0, 8))

    def _review_selected_txt_files(self):
        try:
            paths = review_paths_for_duplicate(self.config, self.item, self._rows_for_review())
        except Exception as exc:
            messagebox.showerror("TLO Handle Duplicates", str(exc), parent=self.window)
            return
        existing = []
        seen = set()
        for path_name in paths:
            if not path_name or not os.path.isfile(path_name):
                continue
            key = os.path.normcase(os.path.normpath(path_name))
            if key in seen:
                continue
            seen.add(key)
            existing.append(path_name)
        if not existing:
            messagebox.showinfo("TLO Handle Duplicates", "No txt files were found to review.", parent=self.window)
            return
        for path_name in existing:
            self._open_text_review_window(path_name)

    def _process_folders(self):
        try:
            process_duplicate_folder(
                self.config,
                self.item,
                self._selected_rows(),
                current_volume=self.updater_window.volume_var.get().strip(),
            )
        except Exception as exc:
            messagebox.showerror("TLO Handle Duplicates", str(exc), parent=self.window)
            return
        self.close_no_action(completed_action=True)

    def _delete_new_keep_old(self):
        try:
            delete_new_keep_old(self.item)
        except Exception as exc:
            messagebox.showerror("TLO Handle Duplicates", str(exc), parent=self.window)
            return
        self.close_no_action(completed_action=True)

    def close_no_action(self, completed_action=False):
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.updater_window._remove_child(self, completed_action=completed_action)


def main() -> int:
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        console_emit(HELP_TEXT)
        return 0
    cli_args = _parse_gui_command_line(sys.argv[1:])
    root, _drop_provider = create_tk_root(tk)
    app = App(root, cli_args=cli_args)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app._cancel_active_inventory_and_clean_logs()
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
