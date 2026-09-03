"""Tkinter GUI for configuring and running TLO Inventory, Add Shows, and Tag workflows."""

__version__ = "v426"

from tlo_diagnostics import debug_suppressed_exception
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import argparse
import io
import os
import queue
import signal
import shutil
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
    validate_compliant_rename_exclusivity,
)
from tlo_path_inputs import normalize_platform_input_path, resolve_current_storage_volume, resolve_tlo_home as resolve_inventory_tlo_home
from logging_lib import delete_logs_for_tokens
from tlo_bootlist_volume_policy import normalize_volume_action, volume_display_name
from tlo_main_lib import run_inventory
from tlo_tag_lib import TAGGER_TITLE, default_tagging_path, resolve_tlo_home, run_tagger
from tlo_version import BUNDLE_BUILD, DISPLAY_VERSION, PUBLIC_VERSION, versioned_title
from tlo_research_lib import research_logs
from tlo_reverse_copy_delete import prepare_reverse_selection, reverse_copy_delete_and_rename
from tlo_github_updates import (
    check_for_updates,
    is_auto_update_enabled,
    set_auto_update_enabled,
    should_auto_check,
)

# Keep the standalone Tagger dialog intentionally compact. The prior layout
# used an 82-character path field and a 110-character output pane; v298 halves
# those character widths so the dialog occupies about half as much horizontal
# screen space while preserving normal resize behavior.
TAGGER_PATH_ENTRY_WIDTH = 41
TAGGER_OUTPUT_TEXT_WIDTH = 55
TAGGER_MODE_WRAP_PIXELS = 520
TAGGER_DISPLAY_VERSION = versioned_title("TLO Tagger GUI")


def _start_activity_indicator(progress_bar) -> bool:
    """Start one indeterminate progress bar at the shared animation interval."""
    if progress_bar is None:
        return False
    progress_bar.start(ACTIVITY_INDICATOR_INTERVAL_MS)
    return True

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
from tlo_dragdrop import create_tk_root, enable_search_path_folder_drop, enable_tagging_path_folder_drop
from tlo_run_settings import append_run_settings
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
from tlo_ux import (
    ACTIVITY_INDICATOR_INTERVAL_MS,
    RunMonitor,
    RunIssue,
    PreviewResult,
    collect_current_log_issues,
    format_elapsed,
    format_preview,
    issue_group_counts,
    main_window_checkbox_values,
    merge_issues,
    open_path,
    operation_review_lines,
    preview_add_shows,
    preview_operation,
    validate_search_path,
    validate_tag_path,
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
    "  As-Is Artist Name --as-is-artist-name\n"
    "  Tag in Place     --tag-during-inventory\n"
    "  Tag Copy         --tag-copy-during-inventory\n  Destination      --tag-copy-destination DIR\n  Tag Copy/Delete Original --tag-copy-delete-original\n  Destination      --tag-copy-and-delete DIR   (command line only)\n  Rename Compliantly --rename-compliantly\n  Convert shn      --convert-shn\n"
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
    "  --compliant          Use the simplified compliant Phase 2/3 parsing rules. Mutually exclusive with --rename-compliantly.\n"
    "  --as-is-artist-name Preserve the artist name found in metadata instead of replacing a matched alias with the Artist DB master name.\n"
    "  --tag-during-inventory Tag in place during inventory-time tagging; mutually exclusive with Tag Copy and Tag Copy/Delete Original.\n"
    "  --tag-copy-during-inventory Copy each music folder before tagging and tag the copy instead of the original.\n  --tag-copy-destination DIR Destination parent directory for Tag Copy. The GUI asks after Inventory is started.\n  --tag-copy-delete-original Enable Tag Copy/Delete Original. In the GUI, starting Inventory opens the destination and deletion-warning window.\n  --tag-copy-and-delete DIR Supply the Tag Copy/Delete Original destination on the command line; this also enables the mode.\n  --rename-compliantly Rename using the resolved Show Name. Mutually exclusive with --compliant. With no tag/copy mode in Full Inventory, rename the original folder in place without tagging.\n  --convert-shn        Convert .shn/.shnf files to .flac during Tag or inventory-time tagging, deleting originals only after successful conversion.\n"
    "  --etree-lookup        Enable the GUI etreeDB / eTreeDB venue-location lookup option after artist and yyyy-mm-dd date are identified.\n"
    "  --setlistfm-lookup         If eTreeDB has no usable result, look up venue/location from setlist.fm. Requires --etree-lookup on the command line.\n"
    "  --debug [BOOL]      Command-line only. With no value, enables debug output; also accepts true/false, yes/no, y/n, 1/0. No Debug checkbox is shown in the GUI.\n"
    "  --current-storage-volume STRING  Prepopulate the Add Shows (incremental) Current Backup/Storage Drive and Volume field. Overrides TLOCurrentStorage.\n"
    "\n"
    "GUI buttons:\n"
    "  Tag               Open the TLO Tagger window; displayed at the far left and uses TLOHome/readyForXfer unless --tag-path is supplied. The tagger window has its own Quit button that stops tagging and closes only that window.\n"
    "  Add Shows (incremental)  Open the updater workflow for readyForXfer/staged/dups processing. The updater inherits all applicable main-window options, including Dry run, and validates the storage volume before processing.\n"
    "  Research          Search TLOHome comp/meta logs.\n"
    "  Reverse Copy/Delete + Rename  Restore folders moved by a logged combined Tag Copy/Delete Original + Rename Compliantly run to their exact original names and locations; audio tags are unchanged.\n"
    "  Quit              Close the GUI. If a run is still active, active workers are stopped and active search-path logs are removed before exit; displayed in the middle.\n"
    "  Inventory (full)  Validate the form and show Review Operation. When Dry run is checked, scan and report planned work without changing files; otherwise run the full inventory job.\n"
    "  Pause             Pause traversal between directory operations; displayed in the right-side inventory group.\n"
    "  Resume            Resume a paused traversal; displayed in the right-side inventory group.\n"
    "  ☰ > Donate        Shows Venmo and Check donation details.\n"
    "  ☰ > Help          Opens the upper-right hamburger menu, then Help > About or Help > FAQ.\n\n"
    "Run experience:\n"
    "  Inventory remains available so validation problems can be reported when it is clicked. Tag becomes available when its Tagging Path is valid.\n"
    "  Review Operation shows every main-window checkbox value in the same order for Inventory, Tag, and Add Shows, followed by action-specific details and whether original files may be changed. After Start is selected, the same lines are appended to TLOHome/logs/runSettings.log with the action, date, and time.\n"
    "  Dry run is controlled by the main-window checkbox and inherited by Inventory, Add Shows, and Tag. It is non-destructive. Inventory resolves the resulting show name for each show. When tagging applies, Inventory or Tag also lists each file and the Artist, Album, Track, and Title values that would be written.\n"
    "  Current Operation shows the live stage, current item, counts, warnings, errors, and elapsed time while a run is active.\n"
    "  Completion summaries provide View Issues, Open Output, and Open Logs actions. Issues are grouped by reason and may open the affected path.\n"
    "  Tag has no duplicated option checkboxes and reads current settings from the main window when Tag is clicked. Add Shows does the same and retains only its action-specific Check for Duplicates checkbox. Standalone Tag never copies or moves folders; verified SHN-to-FLAC conversion is the only case where it removes a source file.\n"
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


class PreviewWindow:
    """Run and display a non-destructive folder-level preview."""

    def __init__(self, parent, config, *, operation, tag_path="", preview_func=None):
        self.parent = parent
        self.config = config
        self.operation = operation
        self.tag_path = tag_path
        self.preview_func = preview_func
        self.cancelled = False
        self.window = tk.Toplevel(parent)
        self.window.title(versioned_title(f"{operation} Preview"))
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._close)
        self.status_var = tk.StringVar(value="Resolving show names and planned work. No files will be changed.")
        frame = ttk.Frame(self.window, padding=10)
        frame.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, textvariable=self.status_var, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.text = scrolledtext.ScrolledText(frame, width=100, height=30, font=tkfont.nametofont("TkFixedFont"), wrap="word")
        self.text.grid(row=1, column=0, sticky="nsew")
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, sticky="e", pady=(8, 0))
        self.close_button = ttk.Button(buttons, text="Cancel Preview", command=self._close)
        self.close_button.grid(row=0, column=0, padx=4)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        try:
            if self.preview_func is not None:
                result = self.preview_func(lambda: self.cancelled)
            else:
                result = preview_operation(
                    self.config,
                    operation=self.operation,
                    tag_path=self.tag_path,
                    cancel_check=lambda: self.cancelled,
                )
        except Exception as exc:
            result = PreviewResult(
                operation=self.operation,
                issues=[RunIssue("Preview error", str(exc).strip() or exc.__class__.__name__, severity="error", source="preview")],
            )
        try:
            self.window.after(0, lambda: self._finish(result))
        except tk.TclError:
            pass

    def _finish(self, result):
        if self.cancelled:
            return
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", format_preview(result))
        self.text.configure(state="disabled")
        if result.issues and any(issue.severity == "error" for issue in result.issues):
            self.status_var.set("Preview completed with input problems. No files were changed.")
        else:
            self.status_var.set("Preview complete. No files were changed.")
        self.close_button.configure(text="Close")

    def _close(self):
        self.cancelled = True
        try:
            self.window.destroy()
        except tk.TclError:
            pass


class IssuesWindow:
    """Present run issues by category with path and log-opening actions."""

    def __init__(self, parent, issues, *, tlo_home, title="Run Issues"):
        self.parent = parent
        self.issues = list(issues or [])
        self.tlo_home = tlo_home
        self.window = tk.Toplevel(parent)
        self.window.title(versioned_title(title))
        self.window.transient(parent)
        frame = ttk.Frame(self.window, padding=10)
        frame.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        counts = issue_group_counts(self.issues)
        summary = ", ".join(f"{name}: {count}" for name, count in counts.items()) or "No issues were recorded."
        ttk.Label(frame, text=summary, wraplength=950, justify="left").grid(row=0, column=0, sticky="ew", pady=(0, 8))
        columns = ("severity", "category", "message", "path")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        self.tree.heading("severity", text="Level")
        self.tree.heading("category", text="Category")
        self.tree.heading("message", text="Explanation")
        self.tree.heading("path", text="Path")
        self.tree.column("severity", width=80, stretch=False)
        self.tree.column("category", width=190, stretch=False)
        self.tree.column("message", width=540, stretch=True)
        self.tree.column("path", width=320, stretch=True)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        for index, issue in enumerate(self.issues):
            self.tree.insert("", "end", iid=str(index), values=(issue.severity.title(), issue.category, issue.message, issue.path))
        self.tree.bind("<Double-1>", lambda _event: self._open_selected())
        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Open Folder", command=self._open_selected).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Open Logs", command=self._open_logs).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Close", command=self.window.destroy).grid(row=0, column=2, padx=4)

    def _selected_issue(self):
        selected = self.tree.selection()
        if not selected:
            return None
        try:
            return self.issues[int(selected[0])]
        except Exception:
            return None

    def _open_selected(self):
        issue = self._selected_issue()
        if issue is None or not issue.path or not open_path(issue.path):
            messagebox.showinfo("TLO Issues", "Select an issue that contains an accessible path.", parent=self.window)

    def _open_logs(self):
        logs_path = os.path.join(self.tlo_home, "logs")
        if not open_path(logs_path):
            messagebox.showerror("TLO Issues", f"Unable to open logs directory: {logs_path}", parent=self.window)


def _show_operation_review(parent, *, title, lines, preview_callback=None):
    """Return True only when the user starts the reviewed operation."""
    result = {"start": False}
    dialog = tk.Toplevel(parent)
    dialog.title(versioned_title(title))
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(True, True)
    frame = ttk.Frame(dialog, padding=12)
    frame.grid(sticky="nsew")
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    ttk.Label(frame, text="Review the operation before it starts.", font=tkfont.nametofont("TkHeadingFont")).grid(row=0, column=0, sticky="w", pady=(0, 8))
    review_text = "\n".join(lines)
    ttk.Label(frame, text=review_text, justify="left", wraplength=780).grid(row=1, column=0, sticky="ew")
    if any(line.endswith("Yes") for line in lines if line.startswith("Original files may be changed:")):
        ttk.Label(
            frame,
            text="This operation can change original folders or audio files. Dry run is non-destructive.",
            justify="left",
            wraplength=780,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=3, column=0, sticky="e", pady=(14, 0))

    def close(start=False):
        result["start"] = bool(start)
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        dialog.destroy()

    if preview_callback is not None:
        ttk.Button(buttons, text="Preview Changes", command=lambda: preview_callback(dialog)).grid(row=0, column=0, padx=4)
    ttk.Button(buttons, text="Go Back", command=lambda: close(False)).grid(row=0, column=1, padx=4)
    ttk.Button(buttons, text="Start", command=lambda: close(True)).grid(row=0, column=2, padx=4)
    dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
    dialog.wait_visibility()
    dialog.focus_force()
    dialog.wait_window()
    return result["start"]


def _show_operation_review_and_log(
    parent,
    *,
    config,
    action,
    title,
    lines,
    preview_callback=None,
):
    """Show Review Operation and append the accepted settings before execution."""
    if not _show_operation_review(
        parent,
        title=title,
        lines=lines,
        preview_callback=preview_callback,
    ):
        return False
    try:
        append_run_settings(config.TLOHome, action, lines)
    except Exception as exc:
        messagebox.showerror(
            "TLO Run Settings Log",
            f"The operation was not started because its settings could not be written:\n{exc}",
            parent=parent,
        )
        return False
    return True


def _show_completion_dialog(parent, *, title, monitor, issues, tlo_home, primary_output=""):
    dialog = tk.Toplevel(parent)
    dialog.title(versioned_title(title))
    dialog.transient(parent)
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text=monitor.completion_text(), justify="left").grid(row=0, column=0, columnspan=4, sticky="w")
    buttons = ttk.Frame(frame)
    buttons.grid(row=1, column=0, columnspan=4, sticky="e", pady=(12, 0))

    def show_issues():
        IssuesWindow(dialog, issues, tlo_home=tlo_home)

    ttk.Button(buttons, text=f"View Issues ({len(issues)})", command=show_issues, state=("normal" if issues else "disabled")).grid(row=0, column=0, padx=4)
    if primary_output:
        ttk.Button(buttons, text="Open Output", command=lambda: open_path(primary_output)).grid(row=0, column=1, padx=4)
    ttk.Button(buttons, text="Open Logs", command=lambda: open_path(os.path.join(tlo_home, "logs"))).grid(row=0, column=2, padx=4)
    ttk.Button(buttons, text="Close", command=dialog.destroy).grid(row=0, column=3, padx=4)
    try:
        dialog.focus_force()
    except tk.TclError:
        pass


def _show_result_dialog(parent, *, title, summary, issues, tlo_home, primary_output=""):
    """Show a consistent completion summary for workflows without a RunMonitor."""
    dialog = tk.Toplevel(parent)
    dialog.title(versioned_title(title))
    dialog.transient(parent)
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text=str(summary or "Operation complete."), justify="left", wraplength=780).grid(
        row=0, column=0, columnspan=4, sticky="w"
    )
    buttons = ttk.Frame(frame)
    buttons.grid(row=1, column=0, columnspan=4, sticky="e", pady=(12, 0))

    def show_issues():
        IssuesWindow(dialog, issues, tlo_home=tlo_home)

    ttk.Button(
        buttons,
        text=f"View Issues ({len(issues)})",
        command=show_issues,
        state=("normal" if issues else "disabled"),
    ).grid(row=0, column=0, padx=4)
    if primary_output:
        ttk.Button(buttons, text="Open Output", command=lambda: open_path(primary_output)).grid(row=0, column=1, padx=4)
    ttk.Button(buttons, text="Open Logs", command=lambda: open_path(os.path.join(tlo_home, "logs"))).grid(row=0, column=2, padx=4)
    ttk.Button(buttons, text="Close", command=dialog.destroy).grid(row=0, column=3, padx=4)
    try:
        dialog.focus_force()
    except tk.TclError:
        pass



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
        "as_is_artist_name",
        "tag_during_inventory",
        "tag_copy_during_inventory",
        "tag_copy_destination",
        "tag_copy_and_delete_enabled",
        "tag_copy_and_delete_path",
        "rename_compliantly",
        "convert_shn",
        "artist_in_album",
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
        validate_compliant_rename_exclusivity(vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    legacy_artist_mode = str(getattr(args, "compliant_artist_mode", "") or "").strip().lower().replace("_", "-")
    if legacy_artist_mode:
        args.as_is_artist_name = legacy_artist_mode in {"as-is", "asis", "as is", "raw"}
    if str(getattr(args, "tag_copy_and_delete_path", "") or "").strip():
        args.tag_copy_and_delete_enabled = True
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
        self.inventory_monitor = None
        self.inventory_issues = []
        self._inventory_exit_code = None
        self._form_valid = True
        self._validation_after_id = None
        self.active_updater_window = None
        self.active_tagger_window = None
        self.tag_button = None
        self.add_shows_button = None
        self.inventory_button = None
        self.research_button = None
        self.reverse_copy_delete_button = None
        self.active_reverse_window = None
        self.pause_button = None
        self.resume_button = None
        self.progress_bar = None
        self.hamburger_button = None
        self.hamburger_menu = None
        self.donate_menu = None
        self.venmo_menu = None
        self.check_menu = None
        self.help_menu = None
        self.auto_update_var = tk.BooleanVar(value=False)
        self._update_check_thread = None
        self._previous_sigint_handler = None
        self._tag_copy_destination = os.path.normpath(
            normalize_platform_input_path(str(getattr(self.cli_args, "tag_copy_destination", "") or "").strip())
        ) if str(getattr(self.cli_args, "tag_copy_destination", "") or "").strip() else ""
        self._tag_copy_delete_destination = os.path.normpath(
            normalize_platform_input_path(str(getattr(self.cli_args, "tag_copy_and_delete_path", "") or "").strip())
        ) if str(getattr(self.cli_args, "tag_copy_and_delete_path", "") or "").strip() else ""
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)
        self._install_sigint_handler()
        self.root.after(100, self._drain)
        self.root.after(250, self._refresh_inline_validation)
        self.root.after(1000, self._refresh_elapsed_display)

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
            "search_path_override": (getattr(self.cli_args, "search_path_override", "") or "").strip(),
            "search_path_slam_override": (getattr(self.cli_args, "search_path_slam_override", "") or "").strip(),
            "performance_mode": performance_mode_default,
            "max_workers": str(initial_max_workers),
            "acceptable_corruption_percent": str(int(getattr(self.cli_args, "acceptable_corruption_percent", 100) or 0)),
        }
        self.vars = {key: tk.StringVar(value=value) for key, value in defaults.items()}
        self.option_status_var = tk.StringVar(value="Checking option combination...")
        self.progress_stage_var = tk.StringVar(value="Ready")
        self.progress_item_var = tk.StringVar(value="")
        self.progress_counts_var = tk.StringVar(value="")
        self.progress_elapsed_var = tk.StringVar(value="Elapsed: 0:00")
        self.vars["performance_mode"].trace_add("write", self._sync_max_workers_to_performance_mode)
        self.vars["max_workers"].trace_add("write", self._mark_max_workers_manual)
        for validation_field in ("search_path_override", "max_workers", "acceptable_corruption_percent"):
            self.vars[validation_field].trace_add("write", self._schedule_inline_validation)

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
        self.donate_menu = tk.Menu(self.hamburger_menu, tearoff=False)
        self.venmo_menu = tk.Menu(self.donate_menu, tearoff=False)
        self.check_menu = tk.Menu(self.donate_menu, tearoff=False)
        self.venmo_menu.add_command(label="@James-Scarano-3")
        self.check_menu.add_command(label="James Scarano")
        self.check_menu.add_command(label="49 Majestic Ave.")
        self.check_menu.add_command(label="Nashua, NH 03063")
        self.donate_menu.add_cascade(label="Venmo", menu=self.venmo_menu)
        self.donate_menu.add_cascade(label="Check", menu=self.check_menu)
        self.help_menu = tk.Menu(self.hamburger_menu, tearoff=False)
        self.help_menu.add_command(label="About", command=self._show_about_from_menu)
        self.help_menu.add_command(label="FAQ", command=self._show_faq_from_menu)
        self.hamburger_menu.add_command(label="Check for updates", command=self._check_for_updates_from_menu)
        self.hamburger_menu.add_checkbutton(label="Auto update", variable=self.auto_update_var, command=self._toggle_auto_update_from_menu)
        self.hamburger_menu.add_cascade(label="Donate", menu=self.donate_menu)
        self.hamburger_menu.add_separator()
        self.hamburger_menu.add_cascade(label="Help", menu=self.help_menu)
        self.hamburger_button.configure(menu=self.hamburger_menu)
        self.hamburger_button.grid(row=row, column=2, sticky="e", padx=6, pady=(0, 4))
        row += 1

        try:
            tlohome_display = self._resolve_gui_tlo_home(error_type=ValueError)
        except Exception:
            tlohome_display = self._cli_my_tlo_value() or self._cli_tlo_home_value() or os.environ.get("TLOHome", "") or "(not set)"
        ttk.Label(frm, text=f"TLOHome: {tlohome_display}", style="Main.TLabel").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 8)
        )
        row += 1

        ttk.Label(frm, text="Search Path", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 1))
        self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=92, style="Main.TEntry")
        self.search_path_entry.grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(4, 1)
        )
        self.search_path_drop_status = self._enable_search_path_drag_drop()
        row += 1
        search_path_note = "Optional override; may start with [Volume]."
        if getattr(self, "search_path_drop_status", None) and self.search_path_drop_status.enabled:
            search_path_note += " Drag a folder here from File Explorer."
        ttk.Label(frm, text=search_path_note, style="Main.TLabel").grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 6), pady=(0, 1))
        row += 1
        ttk.Label(frm, text="Slam", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 1))
        ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=92, style="Main.TEntry").grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(12, 6), pady=(4, 1)
        )
        row += 1
        ttk.Label(frm, text="(optional/override)", style="Main.TLabel").grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 6), pady=(0, 6))
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

        ttk.Label(frm, text="acceptable corruption %", style="Main.TLabel").grid(row=row, column=0, sticky="w", padx=6, pady=(4, 3))
        ttk.Entry(frm, textvariable=self.vars["acceptable_corruption_percent"], width=12, style="Main.TEntry").grid(
            row=row, column=1, sticky="w", padx=(12, 6), pady=(4, 3)
        )
        row += 1

        self.bool_vars = {
            option.config_field: tk.BooleanVar(value=bool(getattr(self.cli_args, option.config_field, option.default)))
            for option in GUI_CHECKBOX_OPTIONS
        }
        self.dry_run_var = tk.BooleanVar(value=False)
        checkbox_frame = ttk.Frame(frm)
        checkbox_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=0, pady=(4, 4))
        checkbox_frame.columnconfigure(0, weight=0)
        checkbox_frame.columnconfigure(1, weight=0)
        checkbox_frame.columnconfigure(2, weight=0)
        checkbox_frame.columnconfigure(3, weight=0)
        for option in GUI_CHECKBOX_OPTIONS:
            checkbox_command = None
            if option.config_field in {"tag_during_inventory", "tag_copy_during_inventory", "tag_copy_and_delete_enabled"}:
                checkbox_command = (lambda field=option.config_field: self._tag_mode_clicked(field))
            elif option.config_field in {"compliant", "rename_compliantly"}:
                checkbox_command = (lambda field=option.config_field: self._compliant_rename_clicked(field))
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
                padx=(4, 24 if option.gui_col in (0, 1, 2) else 4),
                pady=(3, 3),
            )
        self.dry_run_checkbox = ttk.Checkbutton(
            checkbox_frame,
            text="Dry run",
            variable=self.dry_run_var,
            style="Main.Large.TCheckbutton",
        )
        self.dry_run_checkbox.grid(row=2, column=3, sticky="w", padx=(4, 4), pady=(3, 3))
        self._lookup_dependency_syncing = False
        self.bool_vars["setlistfm_lookup"].trace_add("write", self._reapply_lookup_dependency)
        self.bool_vars["etree_lookup"].trace_add("write", self._reapply_lookup_dependency)
        self._tag_mode_syncing = False
        self._compliant_rename_syncing = False
        for option_var in self.bool_vars.values():
            option_var.trace_add("write", self._schedule_inline_validation)
        self._reapply_lookup_dependency()
        self._reapply_tag_mode_exclusivity()
        self._reapply_compliant_rename_exclusivity()
        row += 1
        ttk.Label(frm, textvariable=self.option_status_var, justify="left", wraplength=1000).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4)
        )
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
        self.research_button = ttk.Button(
            left_button_group,
            text="Research\n ",
            command=self._open_research,
            style=main_button_style,
        )
        self.research_button.grid(row=0, column=2, padx=4, sticky="w")
        self.reverse_copy_delete_button = ttk.Button(
            left_button_group,
            text="Reverse Copy/Delete\n+ Rename",
            command=self._open_reverse_copy_delete,
            style=main_button_style,
        )
        self.reverse_copy_delete_button.grid(row=0, column=3, padx=4, sticky="w")
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

        progress_frame = ttk.LabelFrame(frm, text="Current Operation", padding=6)
        progress_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 6))
        progress_frame.columnconfigure(1, weight=1)
        ttk.Label(progress_frame, textvariable=self.progress_stage_var).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(progress_frame, textvariable=self.progress_item_var, wraplength=720).grid(row=0, column=1, sticky="w")
        ttk.Label(progress_frame, textvariable=self.progress_elapsed_var).grid(row=0, column=2, sticky="e", padx=(12, 0))
        ttk.Label(progress_frame, textvariable=self.progress_counts_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))
        self.progress_bar = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        row += 1

        output_frame = ttk.Frame(frm)
        output_frame.grid(row=row, column=0, columnspan=3, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        self.output = tk.Text(output_frame, width=96, height=21, font=tkfont.nametofont("TkFixedFont"), wrap="none")
        output_vscroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.output.yview)
        output_hscroll = ttk.Scrollbar(output_frame, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=output_vscroll.set, xscrollcommand=output_hscroll.set)
        self.output.grid(row=0, column=0, sticky="nsew")
        output_vscroll.grid(row=0, column=1, sticky="ns")
        output_hscroll.grid(row=1, column=0, sticky="ew")
        frm.rowconfigure(row, weight=1)
        self._initialize_update_menu_state()
        self._update_main_action_states()

    def _enable_search_path_drag_drop(self):
        return enable_search_path_folder_drop(
            self.search_path_entry,
            self.vars["search_path_override"],
            on_error=lambda msg: messagebox.showwarning("tlo-ggi", msg, parent=self.root),
        )

    def _schedule_inline_validation(self, *_args):
        try:
            if self._validation_after_id is not None:
                self.root.after_cancel(self._validation_after_id)
            self._validation_after_id = self.root.after(180, self._refresh_inline_validation)
        except tk.TclError:
            pass

    def _refresh_inline_validation(self):
        self._validation_after_id = None
        try:
            tlo_home = self._resolve_gui_tlo_home(error_type=ValueError)
        except Exception as exc:
            tlo_home = self._cli_my_tlo_value() or self._cli_tlo_home_value() or os.environ.get("TLOHome", "")
            search_status = validate_search_path(self.vars["search_path_override"].get(), tlo_home)
            if not tlo_home:
                search_status = type(search_status)("error", str(exc))
        else:
            search_status = validate_search_path(self.vars["search_path_override"].get(), tlo_home)
        copy_delete_enabled = bool(self.bool_vars.get("tag_copy_and_delete_enabled", tk.BooleanVar(value=False)).get())
        max_workers_valid = True
        try:
            max_workers = int((self.vars["max_workers"].get() or "0").strip())
            if max_workers < 0:
                raise ValueError
        except Exception:
            max_workers_valid = False

        corruption_percent_valid = True
        try:
            corruption_percent = int((self.vars["acceptable_corruption_percent"].get() or "0").strip())
            if corruption_percent < 0 or corruption_percent > 100:
                raise ValueError
        except Exception:
            corruption_percent_valid = False

        option_messages = []
        if bool(self.bool_vars["tag_copy_during_inventory"].get()):
            option_messages.append("Tag Copy destination will be requested after Inventory is started.")
        if copy_delete_enabled:
            option_messages.append(
                "Tag Copy/Delete Original destination will be requested after Inventory is started; "
                "the original material will be removed after verified transfer."
            )
        if bool(self.bool_vars.get("convert_shn", tk.BooleanVar(value=False)).get()):
            option_messages.append("Verified SHN conversions remove the original SHN source.")
        if bool(self.bool_vars.get("rename_compliantly", tk.BooleanVar(value=False)).get()):
            option_messages.append("Rename Compliantly may rename original folders.")
        thorough = bool(self.bool_vars.get("thorough_setlist_matching", tk.BooleanVar(value=False)).get())
        setlistfm_enabled = bool(self.bool_vars.get("setlistfm_lookup", tk.BooleanVar(value=False)).get())
        setlistfm_upgrade = bool(self.bool_vars.get("setlistfm_upgrade", tk.BooleanVar(value=False)).get())
        if thorough:
            if setlistfm_enabled and not setlistfm_upgrade:
                option_messages.append(
                    "Thorough Setlist Matching may take substantially longer; setlist.fm evidence remains constrained "
                    "by the normal 600-ms / 1,400-call limits unless setlist.fm upgrade is enabled."
                )
            elif setlistfm_enabled and setlistfm_upgrade:
                option_messages.append(
                    "Thorough Setlist Matching will proactively compare local, eTreeDB, and setlist.fm candidates using upgraded setlist.fm access."
                )
            else:
                option_messages.append(
                    "Thorough Setlist Matching will compare additional local/eTreeDB candidates; setlist.fm evidence is unavailable unless setlist.fm is enabled."
                )
        if not option_messages:
            option_messages.append("Option combination is ready.")
        if not max_workers_valid:
            option_messages = ["Max Workers must be an integer of zero or greater."]
        if not corruption_percent_valid:
            option_messages = ["acceptable corruption % must be an integer from 0 through 100."]

        form_values_valid = bool(max_workers_valid and corruption_percent_valid)
        self.option_status_var.set(("Error: " if not form_values_valid else "Info: ") + " ".join(option_messages))
        self._form_valid = bool(search_status.valid and max_workers_valid)
        self._form_valid = bool(self._form_valid and corruption_percent_valid)
        self._update_main_action_states()

    def _refresh_elapsed_display(self):
        monitor = getattr(self, "inventory_monitor", None)
        if monitor is not None and self._inventory_is_running():
            monitor.snapshot.elapsed_seconds = time.monotonic() - monitor.started
            self.progress_elapsed_var.set(f"Elapsed: {format_elapsed(monitor.snapshot.elapsed_seconds)}")
        try:
            self.root.after(1000, self._refresh_elapsed_display)
        except tk.TclError:
            pass

    def _update_progress_display(self):
        monitor = getattr(self, "inventory_monitor", None)
        if monitor is None:
            self.progress_stage_var.set("Ready")
            self.progress_item_var.set("")
            self.progress_counts_var.set("")
            self.progress_elapsed_var.set("Elapsed: 0:00")
            return
        snap = monitor.snapshot
        self.progress_stage_var.set(snap.stage)
        self.progress_item_var.set(snap.current_item)
        self.progress_elapsed_var.set(f"Elapsed: {format_elapsed(snap.elapsed_seconds)}")
        self.progress_counts_var.set(
            f"Paths {snap.roots_completed}/{snap.roots_total or '?'} | "
            f"Music folders {snap.directories} | Shows {snap.show_groups} | "
            f"Warnings {snap.warnings} | Errors {snap.errors}"
        )

    def _review_inventory_operation(self, config, *, dry_run=False):
        lines = operation_review_lines(
            config,
            operation="Full Inventory",
            dry_run=dry_run,
            main_checkbox_source=self._current_main_checkbox_values(),
        )
        return _show_operation_review_and_log(
            self.root,
            config=config,
            action="Full Inventory Dry Run" if dry_run else "Full Inventory",
            title="Review Full Inventory Dry Run" if dry_run else "Review Full Inventory",
            lines=lines,
        )

    def _run_after_menu_closes(self, callback):
        """Run a hamburger-menu action after Tk has dismissed the posted menu."""
        try:
            self.root.after_idle(callback)
        except tk.TclError:
            callback()

    def _cli_tlo_home_value(self):
        """Return the non-GUI --TLOHome value; myTLO precedence is applied by the resolver."""
        return (getattr(self.cli_args, "TLOHome", "") or "").strip()

    def _cli_my_tlo_value(self):
        return (getattr(self.cli_args, "myTLO", "") or "").strip()

    def _resolve_gui_tlo_home(self, *, error_type=ValueError):
        return resolve_inventory_tlo_home(
            tlo_home=self._cli_tlo_home_value(),
            my_tlo=self._cli_my_tlo_value(),
            error_type=error_type,
        )

    def _show_about_from_menu(self):
        self._run_after_menu_closes(self._show_about)

    def _show_faq_from_menu(self):
        self._run_after_menu_closes(self._show_faq)

    def _resolve_update_tlo_home(self, *, require_existing=True):
        if require_existing:
            return self._resolve_gui_tlo_home(error_type=RuntimeError)
        resolved = self._cli_my_tlo_value() or self._cli_tlo_home_value() or os.environ.get("TLOHome", "")
        return os.path.normpath(resolved) if resolved else ""

    def _initialize_update_menu_state(self):
        try:
            tlo_home = self._resolve_update_tlo_home(require_existing=False)
            enabled = bool(tlo_home and is_auto_update_enabled(tlo_home))
            self.auto_update_var.set(enabled)
            if enabled:
                self.root.after(800, self._startup_auto_update_check)
        except Exception:
            self.auto_update_var.set(False)

    def _check_for_updates_from_menu(self):
        self._run_after_menu_closes(lambda: self._start_update_check(manual=True))

    def _toggle_auto_update_from_menu(self):
        self._run_after_menu_closes(self._toggle_auto_update)

    def _toggle_auto_update(self):
        enabled = bool(self.auto_update_var.get())
        try:
            tlo_home = self._resolve_update_tlo_home(require_existing=True)
            set_auto_update_enabled(tlo_home, enabled)
        except Exception as exc:
            self.auto_update_var.set(False)
            messagebox.showerror("TLO Auto update", str(exc), parent=self.root)
            return
        if enabled:
            messagebox.showinfo(
                "TLO Auto update",
                "Auto update is enabled. TLO will check GitHub at startup and download newer release ZIPs to your Downloads folder.",
                parent=self.root,
            )
            self._start_update_check(manual=False)

    def _startup_auto_update_check(self):
        try:
            tlo_home = self._resolve_update_tlo_home(require_existing=True)
            if is_auto_update_enabled(tlo_home):
                self.auto_update_var.set(True)
                if should_auto_check(tlo_home):
                    self._start_update_check(manual=False)
        except Exception:
            self.auto_update_var.set(False)

    def _start_update_check(self, *, manual):
        thread = getattr(self, "_update_check_thread", None)
        if thread is not None and thread.is_alive():
            if manual:
                messagebox.showinfo("TLO update check", "An update check is already running.", parent=self.root)
            return
        try:
            tlo_home = self._resolve_update_tlo_home(require_existing=False)
        except Exception:
            tlo_home = ""

        def worker():
            result = check_for_updates(tlo_home, manual=manual)
            try:
                self.root.after(0, lambda: self._finish_update_check(result, manual))
            except tk.TclError:
                pass

        if manual:
            self.queue.put("Checking GitHub for TLO updates...\n")
        self._update_check_thread = threading.Thread(target=worker, daemon=True)
        self._update_check_thread.start()

    def _finish_update_check(self, result, manual):
        if manual or result.status in {"downloaded", "already_downloaded", "no_asset", "error"}:
            icon = "error" if result.status == "error" else "info"
            if icon == "error":
                messagebox.showerror(result.title, result.message, parent=self.root)
            else:
                messagebox.showinfo(result.title, result.message, parent=self.root)
        try:
            if result.status in {"downloaded", "already_downloaded", "up_to_date"}:
                self.queue.put(result.title + "\n")
            elif result.status in {"error", "no_asset"}:
                self.queue.put(result.title + ": " + result.message.replace("\n", " ") + "\n")
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    def _show_about(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("About TLO"))
        dialog.transient(self.root)
        dialog.resizable(False, False)

        about_text = (
            "Traders Little Organizer™ - TLO\n"
            f"V{PUBLIC_VERSION}Build{BUNDLE_BUILD}\n"
            "TLO is developed by Jay Scarano\n"
            "using ChatGPT and Anthropic/Claude\n"
            "Contact me at: onaracs.tlo of gmail"
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
        tlo_home = self._resolve_gui_tlo_home()
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


    def _open_research(self):
        try:
            tlo_home = self._resolve_gui_tlo_home(error_type=ValueError)
        except Exception as exc:
            messagebox.showerror("TLO Research", str(exc), parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title("TLO Research"))
        dialog.transient(self.root)
        dialog.resizable(True, False)
        frame = ttk.Frame(dialog, padding=10)
        frame.grid(sticky="nsew")
        dialog.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        query_var = tk.StringVar(value="")
        ttk.Label(frame, text="Research", style="Main.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8)
        )
        entry = ttk.Entry(frame, textvariable=query_var, width=72, style="Main.TEntry")
        entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        ttk.Label(
            frame,
            text="Enter an artist followed by a date, a venue, or a date.",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=2, sticky="e")

        def run_query(_event=None):
            query_text = query_var.get().strip()
            if not query_text:
                messagebox.showwarning("TLO Research", "Enter a research string.", parent=dialog)
                return
            try:
                result = research_logs(tlo_home, query_text)
            except Exception as exc:
                messagebox.showerror("TLO Research", str(exc), parent=dialog)
                return
            self._show_research_results(query_text, result)

        search_button = ttk.Button(
            buttons,
            text="Search",
            command=run_query,
            style="Main.TButton",
            default="active",
        )
        search_button.grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Close", command=dialog.destroy, style="Main.TButton").grid(row=0, column=1, padx=4)

        def keep_search_live(_event=None):
            # Keep Search visually and behaviorally designated as the dialog's
            # default action whenever this Research window is active, even if a
            # different child widget currently owns keyboard focus.
            try:
                search_button.configure(default="active")
            except tk.TclError:
                pass

        # Return/Keypad-Enter at the Toplevel makes Search the live default
        # action for the entire Research dialog, not just for the entry widget.
        dialog.bind("<Return>", run_query)
        dialog.bind("<KP_Enter>", run_query)
        dialog.bind("<FocusIn>", keep_search_live, add="+")
        keep_search_live()
        try:
            entry.focus_set()
        except tk.TclError:
            pass

    def _show_research_results(self, query_text, result_text):
        window = tk.Toplevel(self.root)
        window.title(versioned_title("TLO Research Results"))
        window.geometry("980x620")
        frame = ttk.Frame(window, padding=8)
        frame.grid(sticky="nsew")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text=f"Research: {query_text}", style="Main.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        output = tk.Text(
            output_frame,
            width=110,
            height=32,
            font=tkfont.nametofont("TkFixedFont"),
            wrap="none",
        )
        vscroll = ttk.Scrollbar(output_frame, orient="vertical", command=output.yview)
        hscroll = ttk.Scrollbar(output_frame, orient="horizontal", command=output.xview)
        output.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        output.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        output.insert("1.0", result_text)
        output.mark_set("insert", "1.0")
        output.configure(state="disabled", exportselection=False)

        def select_all(_event=None):
            output.tag_remove("sel", "1.0", "end")
            output.tag_add("sel", "1.0", "end-1c")
            output.mark_set("insert", "1.0")
            output.see("1.0")
            return "break"

        def open_find(_event=None):
            existing = getattr(window, "_tlo_find_dialog", None)
            if existing is not None:
                try:
                    if existing.winfo_exists():
                        existing.deiconify()
                        existing.lift()
                        existing.focus_force()
                        return "break"
                except tk.TclError:
                    pass

            find_dialog = tk.Toplevel(window)
            window._tlo_find_dialog = find_dialog
            find_dialog.title(versioned_title("TLO Research Results Search"))
            find_dialog.transient(window)
            find_dialog.resizable(False, False)
            find_frame = ttk.Frame(find_dialog, padding=10)
            find_frame.grid(sticky="nsew")
            find_frame.columnconfigure(1, weight=1)

            search_var = tk.StringVar(value="")
            direction_var = tk.StringVar(value="forward")
            ttk.Label(find_frame, text="Search for:", style="Main.TLabel").grid(
                row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8)
            )
            search_entry = ttk.Entry(find_frame, textvariable=search_var, width=44, style="Main.TEntry")
            search_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=(0, 8))
            ttk.Radiobutton(
                find_frame, text="Forward", variable=direction_var, value="forward"
            ).grid(row=1, column=1, sticky="w")
            ttk.Radiobutton(
                find_frame, text="Backwards", variable=direction_var, value="backward"
            ).grid(row=1, column=2, sticky="w")
            status_var = tk.StringVar(value="")
            ttk.Label(find_frame, textvariable=status_var).grid(
                row=2, column=0, columnspan=3, sticky="w", pady=(6, 0)
            )
            find_buttons = ttk.Frame(find_frame)
            find_buttons.grid(row=3, column=0, columnspan=3, sticky="e", pady=(10, 0))

            def perform_find(_find_event=None):
                needle = search_var.get()
                if not needle:
                    status_var.set("Enter text to search for.")
                    try:
                        search_entry.focus_set()
                    except tk.TclError:
                        pass
                    return "break"

                direction = direction_var.get()
                try:
                    if output.tag_ranges("sel"):
                        anchor = output.index("sel.last" if direction == "forward" else "sel.first")
                    else:
                        anchor = output.index("insert")
                except tk.TclError:
                    anchor = "1.0" if direction == "forward" else "end-1c"

                count = tk.IntVar(master=find_dialog, value=0)
                if direction == "backward":
                    match = output.search(
                        needle, anchor, stopindex="1.0", backwards=True, nocase=True, count=count
                    )
                    if not match:
                        match = output.search(
                            needle, "end-1c", stopindex=anchor, backwards=True, nocase=True, count=count
                        )
                else:
                    match = output.search(
                        needle, anchor, stopindex="end-1c", nocase=True, count=count
                    )
                    if not match:
                        match = output.search(
                            needle, "1.0", stopindex=anchor, nocase=True, count=count
                        )

                if not match:
                    status_var.set("Not found.")
                    try:
                        find_dialog.bell()
                    except tk.TclError:
                        pass
                    return "break"

                match_len = max(1, int(count.get() or len(needle)))
                end_index = output.index(f"{match}+{match_len}c")
                output.tag_remove("sel", "1.0", "end")
                output.tag_add("sel", match, end_index)
                output.mark_set("insert", end_index if direction == "forward" else match)
                output.see(match)
                status_var.set("")
                return "break"

            find_search_button = ttk.Button(
                find_buttons, text="Search", command=perform_find, style="Main.TButton", default="active"
            )
            find_search_button.grid(row=0, column=0, padx=4)
            ttk.Button(
                find_buttons, text="Close", command=find_dialog.destroy, style="Main.TButton"
            ).grid(row=0, column=1, padx=4)
            find_dialog.bind("<Return>", perform_find)
            find_dialog.bind("<KP_Enter>", perform_find)
            find_dialog.protocol("WM_DELETE_WINDOW", find_dialog.destroy)
            try:
                search_entry.focus_set()
            except tk.TclError:
                pass
            return "break"

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Search", command=open_find, style="Main.TButton").grid(
            row=0, column=0, padx=4
        )
        ttk.Button(buttons, text="Close", command=window.destroy, style="Main.TButton").grid(
            row=0, column=1, padx=4
        )
        window.bind("<Control-a>", select_all)
        window.bind("<Control-A>", select_all)
        window.bind("<Control-f>", open_find)
        window.bind("<Control-F>", open_find)
        try:
            output.focus_set()
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
            reverse_open = self._reverse_copy_delete_is_open()
            if self.inventory_button is not None:
                self.inventory_button.configure(state=("disabled" if updater_open or tagger_open or inventory_active or reverse_open else "normal"))
            if self.reverse_copy_delete_button is not None:
                self.reverse_copy_delete_button.configure(state=("disabled" if inventory_active or updater_open or tagger_open or reverse_open else "normal"))
            if self.tag_button is not None and reverse_open:
                self.tag_button.configure(state="disabled")
            if self.add_shows_button is not None and reverse_open:
                self.add_shows_button.configure(state="disabled")
            if self.pause_button is not None:
                self.pause_button.configure(state=("normal" if inventory_active else "disabled"))
            if self.resume_button is not None:
                self.resume_button.configure(state=("normal" if inventory_active else "disabled"))
        except tk.TclError:
            pass

    def _reverse_copy_delete_is_open(self):
        window = getattr(self, "active_reverse_window", None)
        if window is None:
            return False
        try:
            exists = bool(window.winfo_exists())
        except tk.TclError:
            exists = False
        if not exists:
            self.active_reverse_window = None
        return exists

    def _open_reverse_copy_delete(self):
        if self._inventory_is_running() or self._updater_is_open() or self._tagger_is_open():
            messagebox.showwarning(
                "Reverse Copy/Delete + Rename",
                "Finish the active Inventory, Add Shows, or Tag operation before reversing folders.",
                parent=self.root,
            )
            return
        if self._reverse_copy_delete_is_open():
            try:
                self.active_reverse_window.lift()
                self.active_reverse_window.focus_force()
            except tk.TclError:
                pass
            return
        try:
            tlo_home = self._resolve_gui_tlo_home(error_type=ValueError)
        except Exception as exc:
            messagebox.showerror("Reverse Copy/Delete + Rename", str(exc), parent=self.root)
            return

        dialog = tk.Toplevel(self.root)
        self.active_reverse_window = dialog
        dialog.title(versioned_title("Reverse Copy/Delete + Rename"))
        dialog.transient(self.root)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        frame = ttk.Frame(dialog, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text=f"TLOHome: {tlo_home}", style="Main.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )
        ttk.Label(frame, text="Original Partition / Path").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        original_var = tk.StringVar(value="")
        original_entry = ttk.Entry(frame, textvariable=original_var, width=58)
        original_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(
            frame,
            text="Enter the current volume name, drive/root, or full original path such as D:\\somePath or /mnt/d/somePath.",
            justify="left",
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(frame, text="Copy/Delete Destination").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        moved_var = tk.StringVar(value=self._tag_copy_delete_destination or "")
        moved_entry = ttk.Entry(frame, textvariable=moved_var, width=58)
        moved_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Label(
            frame,
            text="Enter the location where the combined Copy/Delete + Rename operation placed the folders.",
            justify="left",
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 8))

        output = scrolledtext.ScrolledText(frame, width=92, height=15, wrap="none", state="disabled")
        output.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(4, 8))

        status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=status_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 6))
        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, sticky="e")
        reverse_button = ttk.Button(buttons, text="Reverse", style="Main.TButton")
        reverse_button.grid(row=0, column=0, padx=4)
        close_button = ttk.Button(buttons, text="Close", style="Main.TButton")
        close_button.grid(row=0, column=1, padx=4)

        q = queue.Queue()
        worker_state = {"thread": None}

        def append_output(text):
            try:
                output.configure(state="normal")
                output.insert("end", str(text).rstrip("\r\n") + "\n")
                output.see("end")
                output.configure(state="disabled")
            except tk.TclError:
                pass

        def set_running(running):
            state = "disabled" if running else "normal"
            try:
                original_entry.configure(state=state)
                moved_entry.configure(state=state)
                reverse_button.configure(state=state)
                close_button.configure(state=("disabled" if running else "normal"))
            except tk.TclError:
                pass

        def close_dialog():
            thread = worker_state.get("thread")
            if thread is not None and thread.is_alive():
                messagebox.showwarning(
                    "Reverse Copy/Delete + Rename",
                    "The reverse operation is still running.",
                    parent=dialog,
                )
                return
            try:
                dialog.destroy()
            finally:
                self.active_reverse_window = None
                self._update_main_action_states()

        def drain_queue():
            try:
                while True:
                    kind, payload = q.get_nowait()
                    if kind == "line":
                        append_output(payload)
                    elif kind == "done":
                        result = payload
                        worker_state["thread"] = None
                        set_running(False)
                        status_var.set(
                            f"Complete: restored={result.restored}, already restored={result.already_restored}, "
                            f"skipped={result.skipped_unmatched}, conflicts={result.conflicts}, errors={result.errors}"
                        )
                        messagebox.showinfo(
                            "Reverse Copy/Delete + Rename",
                            "Reverse operation complete.\n\n"
                            f"Restored: {result.restored}\n"
                            f"Already restored: {result.already_restored}\n"
                            f"Skipped unmatched: {result.skipped_unmatched}\n"
                            f"Conflicts: {result.conflicts}\n"
                            f"Errors: {result.errors}\n\n"
                            "Details were appended to TLOHome/logs/reverseCopyDelete.log.",
                            parent=dialog,
                        )
                    elif kind == "error":
                        worker_state["thread"] = None
                        set_running(False)
                        status_var.set("Reverse failed")
                        append_output(f"ERROR: {payload}")
                        messagebox.showerror("Reverse Copy/Delete + Rename", str(payload), parent=dialog)
            except queue.Empty:
                pass
            try:
                if dialog.winfo_exists():
                    dialog.after(120, drain_queue)
            except tk.TclError:
                pass

        def start_reverse():
            thread = worker_state.get("thread")
            if thread is not None and thread.is_alive():
                return
            original_text = original_var.get().strip()
            moved_text = moved_var.get().strip()
            try:
                selection = prepare_reverse_selection(
                    tlo_home=self._cli_tlo_home_value(),
                    my_tlo=self._cli_my_tlo_value(),
                    original_partition=original_text,
                    moved_to=moved_text,
                )
                original_root = selection.original_root
                moved_root = selection.moved_root
                records = list(selection.records)
            except Exception as exc:
                messagebox.showerror("Reverse Copy/Delete + Rename", str(exc), parent=dialog)
                return
            if not records:
                messagebox.showwarning(
                    "Reverse Copy/Delete + Rename",
                    "No successful combined Copy/Delete + Rename mappings could be identified for these inputs.",
                    parent=dialog,
                )
                return

            existing = sum(1 for item in records if os.path.isdir(item.current_path))
            summary = (
                f"Identified {os.path.basename(selection.log_path)} with {len(records)} logged folder mapping(s); "
                f"{existing} exact destination folder(s) currently exist.\n\n"
                f"Original partition/path: {original_root}\n"
                f"Copy/Delete destination: {moved_root}\n"
                f"Log evidence: {selection.evidence}\n\n"
                "TLO will restore each folder to its exact logged original name and location. "
                "Audio tags will not be changed. If the original path already exists, both folders are left untouched. "
                "Cross-partition restores are copied and verified before the moved copy is deleted.\n\n"
                "Continue?"
            )
            if not messagebox.askyesno("Reverse Copy/Delete + Rename", summary, parent=dialog):
                return

            try:
                append_run_settings(
                    tlo_home,
                    "Reverse Copy/Delete + Rename",
                    [
                        f"Original partition input: {original_text}",
                        f"Resolved original partition/path: {original_root}",
                        f"Copy/Delete destination: {moved_root}",
                        f"Selected success log: {selection.log_path}",
                        f"Matching logged mappings: {len(records)}",
                        "Internal audio tagging: unchanged",
                    ],
                )
            except Exception as exc:  # noqa: BLE001 - best-effort boundary
                debug_suppressed_exception(__name__, exc)
            append_output(f"Starting reverse for {len(records)} logged mapping(s).")
            status_var.set("Reversing folders...")
            set_running(True)
            self._update_main_action_states()

            def worker():
                try:
                    result = reverse_copy_delete_and_rename(
                        selection=selection,
                        emit=lambda line: q.put(("line", line)),
                    )
                    q.put(("done", result))
                except Exception as exc:
                    q.put(("error", exc))

            thread = threading.Thread(target=worker, name="tlo-reverse-copy-delete", daemon=True)
            worker_state["thread"] = thread
            thread.start()

        reverse_button.configure(command=start_reverse)
        close_button.configure(command=close_dialog)
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Return>", lambda _event: (start_reverse(), "break")[1])
        original_entry.focus_set()
        self._update_main_action_states()
        dialog.after(120, drain_queue)

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

    def _current_main_checkbox_values(self):
        values = {field: bool(var.get()) for field, var in self.bool_vars.items()}
        values["dry_run"] = bool(self.dry_run_var.get())
        return main_window_checkbox_values(values, dry_run=values["dry_run"])

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
                tlo_home=self._cli_tlo_home_value(),
                my_tlo=self._cli_my_tlo_value(),
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
        TaggerWindow(
            self,
            tlo_home=resolved_home,
            tag_path=tag_path,
            debug=bool(getattr(self.cli_args, "debug", False)),
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

    def _compliant_rename_clicked(self, field: str):
        if getattr(self, "_compliant_rename_syncing", False):
            return
        self._compliant_rename_syncing = True
        try:
            if bool(self.bool_vars[field].get()):
                other = "rename_compliantly" if field == "compliant" else "compliant"
                if other in self.bool_vars:
                    self.bool_vars[other].set(False)
        finally:
            self._compliant_rename_syncing = False
        self._schedule_inline_validation()

    def _reapply_compliant_rename_exclusivity(self, *_args):
        if not (bool(self.bool_vars.get("compliant").get()) and bool(self.bool_vars.get("rename_compliantly").get())):
            return
        self._compliant_rename_syncing = True
        try:
            # Startup command-line conflicts are rejected before the window is
            # built. This fallback protects direct programmatic construction.
            self.bool_vars["rename_compliantly"].set(False)
        finally:
            self._compliant_rename_syncing = False

    def _tag_mode_clicked(self, field: str):
        if getattr(self, "_tag_mode_syncing", False):
            return
        self._tag_mode_syncing = True
        try:
            if bool(self.bool_vars[field].get()):
                for other in ("tag_during_inventory", "tag_copy_during_inventory", "tag_copy_and_delete_enabled"):
                    if other != field and other in self.bool_vars:
                        self.bool_vars[other].set(False)
        finally:
            self._tag_mode_syncing = False

        self._schedule_inline_validation()

    def _reapply_tag_mode_exclusivity(self, *_args):
        enabled = [
            field for field in ("tag_during_inventory", "tag_copy_during_inventory", "tag_copy_and_delete_enabled")
            if field in self.bool_vars and bool(self.bool_vars[field].get())
        ]
        if len(enabled) <= 1:
            return
        keep = "tag_copy_and_delete_enabled" if "tag_copy_and_delete_enabled" in enabled else enabled[0]
        self._tag_mode_syncing = True
        try:
            for field in enabled:
                if field != keep:
                    self.bool_vars[field].set(False)
        finally:
            self._tag_mode_syncing = False


    def _cleanup_active_logs(self):
        if self.current_config is None:
            return []
        return delete_logs_for_tokens(
            self.current_config.TLOHome,
            getattr(self.current_config, "newly_allocated_log_tokens", []),
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
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)
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


    def _is_valid_copy_destination(self, value: str) -> bool:
        try:
            normalized = normalize_platform_input_path(str(value or "").strip())
        except Exception:
            return False
        return bool(normalized and os.path.isabs(normalized) and os.path.isdir(normalized))

    @staticmethod
    def _format_storage_bytes(value):
        size = float(max(0, int(value or 0)))
        for unit in ("bytes", "KB", "MB", "GB", "TB", "PB"):
            if size < 1024.0 or unit == "PB":
                return f"{int(size)} {unit}" if unit == "bytes" else f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{int(size)} bytes"

    def _destination_storage_status(self, value: str):
        normalized = normalize_platform_input_path(str(value or "").strip())
        if not self._is_valid_copy_destination(normalized):
            return False, "Enter an existing fully qualified destination directory.", ""
        try:
            free_bytes = shutil.disk_usage(normalized).free
        except OSError as exc:
            return False, f"Unable to check available storage: {exc}", ""
        return True, f"Valid destination - {self._format_storage_bytes(free_bytes)} available.", os.path.normpath(normalized)

    def _confirm_copy_destination(self, *, delete_original: bool, initial_value="") -> str:
        result = {"destination": ""}
        title = "Tag Copy/Delete Original" if delete_original else "Tag Copy"
        dialog = tk.Toplevel(self.root)
        dialog.title(versioned_title(title))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        if delete_original:
            message = (
                "WARNING: Tag Copy/Delete Original transfers each identified show to the selected destination "
                "and removes the original material.\n\n"
                "On the same partition, TLO renames/moves the folder without totaling or comparing file sizes. "
                "On a different partition, TLO checks required capacity, copies the folder, and verifies every "
                "file by size before deleting the original."
            )
        else:
            message = (
                "Tag Copy copies each identified show to the selected destination and tags the copy. "
                "The original material is retained.\n\n"
                "TLO checks required capacity before changes begin and verifies every copied file by size, "
                "including when the source and destination are on the same partition."
            )

        ttk.Label(
            dialog,
            text=message,
            justify="left",
            wraplength=720,
            padding=12,
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(dialog, text="Destination of Copies", padding=(12, 4)).grid(row=1, column=0, sticky="w")
        initial = str(initial_value or "").strip()
        dest_var = tk.StringVar(value=normalize_platform_input_path(initial) if initial else "")
        entry = ttk.Entry(dialog, textvariable=dest_var, width=72)
        entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(4, 12), pady=4)
        status_var = tk.StringVar(value="Enter an existing fully qualified destination directory.")
        ttk.Label(dialog, textvariable=status_var, justify="left", wraplength=650).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=(4, 12), pady=(0, 6)
        )
        ok_button = ttk.Button(dialog, text="OK")

        def close_abort():
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def refresh(*_args):
            valid, status_message, normalized = self._destination_storage_status(dest_var.get())
            status_var.set(status_message)
            ok_button.configure(state=("normal" if valid else "disabled"))
            result["candidate"] = normalized

        def close_ok():
            valid, status_message, normalized = self._destination_storage_status(dest_var.get())
            if not valid:
                status_var.set(status_message)
                return
            result["destination"] = normalized
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        dest_var.trace_add("write", refresh)
        ttk.Button(dialog, text="Cancel", command=close_abort).grid(row=3, column=1, padx=8, pady=(8, 12), sticky="e")
        ok_button.configure(command=close_ok)
        ok_button.grid(row=3, column=2, padx=(0, 12), pady=(8, 12), sticky="w")
        dialog.protocol("WM_DELETE_WINDOW", close_abort)
        refresh()
        dialog.wait_visibility()
        entry.focus_force()
        dialog.wait_window()
        return result["destination"]

    def _confirm_tag_copy_destination(self, initial_value=None) -> str:
        if initial_value is None:
            initial_value = self._tag_copy_destination or getattr(self.cli_args, "tag_copy_destination", "")
        return self._confirm_copy_destination(delete_original=False, initial_value=initial_value)

    def _confirm_tag_copy_delete_destination(self, initial_value="") -> str:
        return self._confirm_copy_destination(delete_original=True, initial_value=initial_value)


    def _build_config(self, *, for_add_shows=False):
        tlo_home = self._resolve_gui_tlo_home(error_type=ValueError)
        silent = bool(getattr(self.cli_args, "silent", False))
        performance_mode = (self.vars["performance_mode"].get() or "balanced").strip().lower()
        if performance_mode not in {"gentle", "balanced", "fast", "extreme"}:
            raise ValueError("Performance Mode must be gentle, balanced, fast, or extreme")
        max_workers_text = self.vars["max_workers"].get().strip()
        max_workers = 0 if not max_workers_text else int(max_workers_text)
        if max_workers < 0:
            raise ValueError("Max Workers must be blank, 0, or a positive integer")
        as_is_artist_name = bool(self.bool_vars["as_is_artist_name"].get())
        compliant_artist_mode = "as-is" if as_is_artist_name else "master"
        rename_compliantly = bool(self.bool_vars["rename_compliantly"].get())
        validate_compliant_rename_exclusivity({
            "compliant": bool(self.bool_vars["compliant"].get()),
            "rename_compliantly": rename_compliantly,
        })
        requested_copy_delete = bool(self.bool_vars["tag_copy_and_delete_enabled"].get())
        requested_tag_copy = bool(self.bool_vars["tag_copy_during_inventory"].get())
        copy_delete_enabled = requested_copy_delete and not for_add_shows
        tag_in_place = bool(self.bool_vars["tag_during_inventory"].get())
        tag_copy = requested_tag_copy
        if for_add_shows:
            # Add Shows stages accepted folders inside TLOHome and therefore does
            # not execute either inventory copy mode. Preserve the main-window
            # selections separately so the unified review dialog still reports
            # every main-window flag accurately.
            tag_copy = False
            copy_delete_enabled = False
        elif sum(bool(value) for value in (tag_in_place, tag_copy, copy_delete_enabled)) > 1:
            raise ValueError("Tag in Place, Tag Copy, and Tag Copy/Delete Original are mutually exclusive")

        tag_copy_destination = ""
        tag_copy_and_delete_path = ""
        if tag_copy:
            selected_destination = self._confirm_tag_copy_destination(self._tag_copy_destination)
            if not selected_destination:
                raise _InventoryStartCancelled()
            self._tag_copy_destination = selected_destination
            tag_copy_destination = selected_destination
        elif copy_delete_enabled:
            selected_destination = self._confirm_tag_copy_delete_destination(self._tag_copy_delete_destination)
            if not selected_destination:
                raise _InventoryStartCancelled()
            self._tag_copy_delete_destination = selected_destination
            tag_copy_and_delete_path = selected_destination
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
            as_is_artist_name=as_is_artist_name,
            tag_during_inventory=tag_in_place,
            tag_copy_during_inventory=tag_copy,
            tag_copy_destination=tag_copy_destination,
            tag_copy_and_delete_path=tag_copy_and_delete_path,
            rename_compliantly=rename_compliantly,
            convert_shn=self.bool_vars["convert_shn"].get(),
            artist_in_album=self.bool_vars["artist_in_album"].get(),
            etree_lookup=self.bool_vars["etree_lookup"].get(),
            setlistfm_lookup=self.bool_vars["setlistfm_lookup"].get(),
            setlistfm_upgrade=bool(getattr(self.bool_vars.get("setlistfm_upgrade"), "get", lambda: False)()),
            thorough_setlist_matching=bool(getattr(self.bool_vars.get("thorough_setlist_matching"), "get", lambda: False)()),
            acceptable_corruption_percent=int((getattr(self.vars.get("acceptable_corruption_percent"), "get", lambda: "100")() or "0").strip()),
            performance_mode=performance_mode,
            max_workers=max_workers,
        )
        config.current_volume_label = resolve_current_storage_volume(getattr(self.cli_args, "current_storage_volume", None))
        config.capacity_alert_callback = self._show_copy_capacity_alert_threadsafe
        config.main_window_tag_copy_selected = requested_tag_copy
        config.main_window_tag_copy_delete_selected = requested_copy_delete
        config.main_window_dry_run = bool(getattr(getattr(self, "dry_run_var", None), "get", lambda: False)())
        apply_lookup_dependency(vars(config), mode="auto")
        if config.setlistfm_lookup and config.setlistfm_upgrade:
            config.setlistfm_min_interval_seconds = 1.0 / 14.0
            config.setlistfm_max_calls = 0
            config.setlistfm_max_calls_per_day = 48000
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

    def _consume_inventory_queue(self):
        changed = False
        try:
            while True:
                msg = self.queue.get_nowait()
                self.output.insert(tk.END, msg)
                self.output.see(tk.END)
                if self.inventory_monitor is not None:
                    self.inventory_monitor.feed(msg)
                    changed = True
        except queue.Empty:
            pass
        if changed:
            self._update_progress_display()
        return changed

    def _finish_inventory_thread(self, exit_code=None):
        self.full_inventory_active = False
        self.worker = None
        self._inventory_exit_code = exit_code
        success = int(exit_code or 0) == 0
        self._consume_inventory_queue()
        if self.inventory_monitor is not None:
            self.inventory_monitor.finish(success=success)
            log_issues = collect_current_log_issues(
                getattr(self.current_config, "TLOHome", ""),
                getattr(self.current_config, "current_run_log_tokens", []),
            )
            self.inventory_issues = merge_issues(self.inventory_monitor.issues, log_issues)
        try:
            if self.progress_bar is not None:
                self.progress_bar.stop()
        except tk.TclError:
            pass
        self._update_progress_display()
        self._update_main_action_states()
        if self.inventory_monitor is not None and self.current_config is not None:
            _show_completion_dialog(
                self.root,
                title="Inventory Complete" if success else "Inventory Stopped",
                monitor=self.inventory_monitor,
                issues=self.inventory_issues,
                tlo_home=self.current_config.TLOHome,
                primary_output=os.path.join(self.current_config.TLOHome, "bootlist.csv") if success else "",
            )


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
            tlo_home = self._resolve_gui_tlo_home(error_type=ValueError)
            search_status = validate_search_path(self.vars["search_path_override"].get(), tlo_home)
            if not search_status.valid:
                raise ValueError(search_status.message)
            config = self._build_config()
            config.volume_action_callback = self._ask_existing_volume_action_threadsafe
        except _InventoryStartCancelled:
            return
        except Exception as exc:
            messagebox.showerror("tlo-ggi", str(exc), parent=self.root)
            return
        dry_run = bool(self.dry_run_var.get())
        if not self._review_inventory_operation(config, dry_run=dry_run):
            return
        if dry_run:
            PreviewWindow(self.root, config, operation="Full Inventory Dry Run")
            return
        clear_cancel_request()
        clear_pause()
        config.cancel_requested = False
        self.output.delete("1.0", tk.END)
        self.current_config = config
        self.inventory_monitor = RunMonitor("Full Inventory")
        self.inventory_issues = []
        self._inventory_exit_code = None
        self.full_inventory_active = True
        self._update_main_action_states()
        self._update_progress_display()
        try:
            _start_activity_indicator(self.progress_bar)
        except tk.TclError:
            pass
        self.queue.put("Inventory request accepted; preparing inventory roots.\n")

        def target():
            old_out, old_err = sys.stdout, sys.stderr
            writer = _QueueWriter(self.queue)
            sys.stdout = writer
            sys.stderr = writer
            exit_code = 1
            try:
                exit_code = run_inventory(config)
            except Exception as exc:
                self.queue.put(f"ERROR: {exc}\n")
                exit_code = 1
            finally:
                sys.stdout = old_out
                sys.stderr = old_err
                try:
                    self.root.after(0, lambda: self._finish_inventory_thread(exit_code))
                except tk.TclError:
                    self.full_inventory_active = False
                    self.worker = None

        self.worker = threading.Thread(target=target, daemon=True)
        self.worker.start()

    def _drain(self):
        self._consume_inventory_queue()
        self.root.after(100, self._drain)



class TaggerWindow:
    def __init__(
        self,
        parent_app,
        tlo_home,
        tag_path,
        debug=False,
    ):
        self.parent_app = parent_app
        self.tlo_home = tlo_home
        self.debug = bool(debug)
        self.queue = queue.Queue()
        self.worker = None
        self._processing = False
        self._closed = False
        self._tag_cancel_requested = False
        self.monitor = None
        self.issues = []
        self.window = tk.Toplevel(parent_app.root)
        parent_app.active_tagger_window = self
        parent_app._update_main_action_states()
        self.window.title(TAGGER_DISPLAY_VERSION)
        self.window.protocol("WM_DELETE_WINDOW", self._request_exit)
        self.path_var = tk.StringVar(value=tag_path or "")
        self.path_status_var = tk.StringVar(value="Checking Tagging Path...")
        self.stage_var = tk.StringVar(value="Ready")
        self.item_var = tk.StringVar(value="")
        self.counts_var = tk.StringVar(value="")
        self.elapsed_var = tk.StringVar(value="Elapsed: 0:00")
        self._build()
        self.path_var.trace_add("write", self._validate_controls)
        self._validate_controls()
        self.window.after(100, self._drain)
        self.window.after(1000, self._refresh_elapsed)

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
        ttk.Label(
            frm,
            text=(
                "Tags the selected path directly. It does not inventory, copy, move, or delete folders. "
                "When Convert SHN is selected, a source SHN is removed only after the FLAC conversion is verified."
            ),
            wraplength=TAGGER_MODE_WRAP_PIXELS,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(frm, text="Tagging Path:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.path_entry = ttk.Entry(frm, textvariable=self.path_var, width=TAGGER_PATH_ENTRY_WIDTH)
        self.path_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        self._enable_tagging_path_drag_drop()
        ttk.Label(frm, textvariable=self.path_status_var, wraplength=TAGGER_MODE_WRAP_PIXELS, justify="left").grid(
            row=3, column=1, columnspan=2, sticky="w", pady=(0, 6)
        )

        buttons = ttk.Frame(frm)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 6))
        self.tag_run_button = ttk.Button(buttons, text="Tag", command=self._start_tagging)
        self.tag_run_button.grid(row=0, column=0, padx=(0, 6))
        self.pause_button = ttk.Button(buttons, text="Pause", command=self._toggle_pause, state="disabled")
        self.pause_button.grid(row=0, column=1, padx=6)
        self.exit_button = ttk.Button(buttons, text="Quit", command=self._request_exit)
        self.exit_button.grid(row=0, column=2, padx=6)

        progress = ttk.LabelFrame(frm, text="Current Operation", padding=6)
        progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        progress.columnconfigure(1, weight=1)
        ttk.Label(progress, textvariable=self.stage_var).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(progress, textvariable=self.item_var, wraplength=430).grid(row=0, column=1, sticky="w")
        ttk.Label(progress, textvariable=self.elapsed_var).grid(row=0, column=2, sticky="e")
        ttk.Label(progress, textvariable=self.counts_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 0))
        self.progress_bar = ttk.Progressbar(progress, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))

        self.output = scrolledtext.ScrolledText(frm, width=TAGGER_OUTPUT_TEXT_WIDTH, height=22, font=tkfont.nametofont("TkFixedFont"))
        self.output.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        frm.rowconfigure(6, weight=1)

    def _enable_tagging_path_drag_drop(self):
        return enable_tagging_path_folder_drop(
            self.path_entry,
            self.path_var,
            on_error=lambda msg: messagebox.showwarning("TLO Tagger", msg, parent=self.window),
        )

    def _main_checkbox_values(self):
        getter = getattr(self.parent_app, "_current_main_checkbox_values", None)
        if callable(getter):
            return getter()
        bool_vars = getattr(self.parent_app, "bool_vars", {}) or {}
        values = {field: bool(var.get()) for field, var in bool_vars.items()}
        dry_var = getattr(self.parent_app, "dry_run_var", None)
        values["dry_run"] = bool(dry_var.get()) if dry_var is not None else False
        return main_window_checkbox_values(values, dry_run=values["dry_run"])

    def _current_dry_run(self):
        return bool(self._main_checkbox_values()["dry_run"])

    def _tag_config(self):
        values = self._main_checkbox_values()
        validate_compliant_rename_exclusivity(values)
        config = Config(
            debug=self.debug,
            silent=False,
            TLOHome=self.tlo_home,
            compliant=values["compliant"],
            compliant_artist_mode=("as-is" if values["as_is_artist_name"] else "master"),
            as_is_artist_name=values["as_is_artist_name"],
            # Standalone Tag always tags the selected path directly. The three
            # inventory tag-mode checkboxes are reported in the review dialog
            # but do not change standalone Tag's no-copy behavior.
            tag_during_inventory=True,
            tag_copy_during_inventory=False,
            tag_copy_destination="",
            tag_copy_and_delete_path="",
            etree_lookup=values["etree_lookup"],
            setlistfm_lookup=values["setlistfm_lookup"],
            setlistfm_upgrade=bool(values.get("setlistfm_upgrade", False)),
            thorough_setlist_matching=bool(values.get("thorough_setlist_matching", False)),
            rename_compliantly=values["rename_compliantly"],
            convert_shn=values["convert_shn"],
            artist_in_album=values["artist_in_album"],
        )
        if config.setlistfm_lookup and config.setlistfm_upgrade:
            config.setlistfm_min_interval_seconds = 1.0 / 14.0
            config.setlistfm_max_calls = 0
            config.setlistfm_max_calls_per_day = 48000
        config.main_window_tag_in_place_selected = values["tag_during_inventory"]
        config.main_window_tag_copy_selected = values["tag_copy_during_inventory"]
        config.main_window_tag_copy_delete_selected = values["tag_copy_and_delete_enabled"]
        config.main_window_dry_run = values["dry_run"]
        config.main_window_checkbox_values = dict(values)
        return config

    def _validate_controls(self, *_args):
        status = validate_tag_path(self.path_var.get())
        self.path_status_var.set(status.display)
        enabled = status.valid and not self._processing
        state = "normal" if enabled else "disabled"
        for widget in (getattr(self, "tag_run_button", None),):
            if widget is not None:
                try:
                    widget.configure(state=state)
                except tk.TclError:
                    pass

    def _set_processing_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in (self.tag_run_button, self.path_entry):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        self.pause_button.configure(state=("disabled" if enabled else "normal"))
        self.exit_button.configure(state="normal")
        if enabled:
            self._validate_controls()

    def _start_tagging(self):
        if self._processing:
            messagebox.showinfo("TLO Tagger", "Tagging is already running.", parent=self.window)
            return
        status = validate_tag_path(self.path_var.get())
        if not status.valid:
            messagebox.showerror("TLO Tagger", status.message, parent=self.window)
            return
        config = self._tag_config()
        dry_run = self._current_dry_run()
        config.main_window_dry_run = dry_run
        review_lines = operation_review_lines(
            config,
            operation="Tag",
            path_text=status.normalized,
            dry_run=dry_run,
            main_checkbox_source=config.main_window_checkbox_values,
        )
        if not _show_operation_review_and_log(
            self.window,
            config=config,
            action="Tag Dry Run" if dry_run else "Tag",
            title="Review Tag Dry Run" if dry_run else "Review Tagging",
            lines=review_lines,
        ):
            return
        if dry_run:
            PreviewWindow(self.window, config, operation="Tag Dry Run", tag_path=status.normalized)
            return
        clear_cancel_request()
        clear_pause()
        self.output.delete("1.0", tk.END)
        self._tag_cancel_requested = False
        self._processing = True
        self.monitor = RunMonitor("Tag")
        self.issues = []
        self._set_processing_controls(False)
        self.parent_app._update_main_action_states()
        self._update_progress_display()
        _start_activity_indicator(self.progress_bar)

        def worker():
            totals = None
            error = None
            try:
                totals = run_tagger(
                    tlo_home=self.tlo_home,
                    compliant=bool(config.compliant),
                    tag_path=status.normalized,
                    etree_lookup=bool(config.etree_lookup),
                    setlistfm_lookup=bool(config.setlistfm_lookup),
                    setlistfm_upgrade=bool(getattr(config, "setlistfm_upgrade", False)),
                    thorough_setlist_matching=bool(getattr(config, "thorough_setlist_matching", False)),
                    debug=self.debug,
                    rename_compliantly=bool(config.rename_compliantly),
                    convert_shn=bool(config.convert_shn),
                    artist_in_album=bool(config.artist_in_album),
                    as_is_artist_name=bool(config.as_is_artist_name),
                    emit=self.queue.put,
                )
            except Exception as exc:
                error = exc
            try:
                self.parent_app.root.after(0, lambda: self._finish_tagging(error, totals))
            except tk.TclError:
                pass

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _toggle_pause(self):
        if not self._processing:
            return
        if is_pause_requested():
            clear_pause()
            self.pause_button.configure(text="Pause")
            self.queue.put("Tagging resumed.\n")
        else:
            request_pause()
            self.pause_button.configure(text="Resume")
            self.queue.put("Tagging paused. The current file operation will finish first.\n")

    def _consume_queue(self):
        changed = False
        try:
            while True:
                msg = self.queue.get_nowait()
                self.output.insert(tk.END, msg)
                self.output.see(tk.END)
                if self.monitor is not None:
                    self.monitor.feed(msg)
                    changed = True
        except queue.Empty:
            pass
        if changed:
            self._update_progress_display()
        return changed

    def _finish_tagging(self, error, totals):
        self._processing = False
        self.worker = None
        clear_pause()
        if self._closed:
            if getattr(self.parent_app, "active_tagger_window", None) is self:
                self.parent_app.active_tagger_window = None
            self.parent_app._update_main_action_states()
            return
        self.progress_bar.stop()
        self.pause_button.configure(text="Pause")
        self._set_processing_controls(True)
        self.parent_app._update_main_action_states()
        if error is not None:
            self.queue.put(f"ERROR: {error}\n")
        self._consume_queue()
        success = error is None and not self._tag_cancel_requested
        if self.monitor is None:
            self.monitor = RunMonitor("Tag")
        if totals:
            self.monitor.snapshot.folders = int(totals.get("groups", 0))
            self.monitor.snapshot.tagged_files = int(totals.get("tagged", 0))
            self.monitor.snapshot.skipped_folders = int(totals.get("skipped", 0))
            self.monitor.snapshot.errors = max(self.monitor.snapshot.errors, int(totals.get("errors", 0)))
        self.monitor.finish(success=success)
        log_issues = collect_current_log_issues(self.tlo_home, ["T"], tagger=True)
        self.issues = merge_issues(self.monitor.issues, log_issues)
        self._update_progress_display()
        _show_completion_dialog(
            self.window,
            title="Tagging Complete" if success else "Tagging Stopped",
            monitor=self.monitor,
            issues=self.issues,
            tlo_home=self.tlo_home,
        )

    def _update_progress_display(self):
        if self.monitor is None:
            self.stage_var.set("Ready")
            self.item_var.set("")
            self.counts_var.set("")
            self.elapsed_var.set("Elapsed: 0:00")
            return
        snap = self.monitor.snapshot
        self.stage_var.set(snap.stage)
        self.item_var.set(snap.current_item)
        self.elapsed_var.set(f"Elapsed: {format_elapsed(snap.elapsed_seconds)}")
        self.counts_var.set(
            f"Folders {snap.folders} | Tagged files {snap.tagged_files} | "
            f"Skipped {snap.skipped_folders} | Warnings {snap.warnings} | Errors {snap.errors}"
        )

    def _refresh_elapsed(self):
        if self.monitor is not None and self._processing:
            self.monitor.snapshot.elapsed_seconds = time.monotonic() - self.monitor.started
            self._update_progress_display()
        try:
            self.window.after(1000, self._refresh_elapsed)
        except tk.TclError:
            pass

    def _request_exit(self):
        if self._processing:
            self._tag_cancel_requested = True
            request_cancel()
            clear_pause()
            try:
                self.queue.put("Tagger quit requested; stopping active tagging work.\n")
            except Exception as exc:  # noqa: BLE001 - best-effort boundary
                debug_suppressed_exception(__name__, exc)
            self._destroy_tagger_window(release_main=False)
            return
        self._destroy_tagger_window()

    def _destroy_tagger_window(self, release_main=True):
        self._closed = True
        clear_pause()
        if release_main and getattr(self.parent_app, "active_tagger_window", None) is self:
            self.parent_app.active_tagger_window = None
        try:
            self.parent_app._update_main_action_states()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _drain(self):
        self._consume_queue()
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
        self._started_at = None
        self._elapsed_after_id = None
        self.window = tk.Toplevel(parent_app.root)
        parent_app.active_updater_window = self
        parent_app._update_main_action_states()
        self.window.title(UPDATER_DISPLAY_VERSION)
        self.window.protocol("WM_DELETE_WINDOW", self._request_exit)
        self._build()
        self._refresh_volume_validation()
        self._refresh_elapsed_display()

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
        self.volume_status_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.elapsed_var = tk.StringVar(value="Elapsed: 0:00")

        ttk.Label(frm, text="Current Backup/Storage Drive and Volume").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frm, textvariable=self.volume_var, width=56).grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        self.volume_status_label = ttk.Label(frm, textvariable=self.volume_status_var, justify="left", wraplength=850)
        self.volume_status_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Checkbutton(frm, text="Check for Duplicates", variable=self.check_dups_var).grid(row=4, column=0, sticky="w", pady=(4, 1))
        buttons = ttk.Frame(frm)
        buttons.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.process_new_button = ttk.Button(buttons, text="Process New Shows", command=self._process_new_shows)
        self.process_new_button.grid(row=0, column=0, padx=(0, 6))
        self.process_dups_button = ttk.Button(buttons, text="Process Potential\nDuplicate/Upgrades", command=self._process_duplicates)
        self.process_dups_button.grid(row=0, column=1, padx=6)
        self.exit_button = ttk.Button(buttons, text="Exit", command=self._request_exit)
        self.exit_button.grid(row=0, column=2, padx=6)

        status_box = ttk.LabelFrame(frm, text="Current Operation", padding=8)
        status_box.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        status_box.columnconfigure(0, weight=1)
        ttk.Label(status_box, textvariable=self.status_var, justify="left", wraplength=900).grid(row=0, column=0, sticky="w")
        ttk.Label(status_box, textvariable=self.elapsed_var).grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.progress_bar = ttk.Progressbar(status_box, mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.volume_var.trace_add("write", lambda *_args: self._refresh_volume_validation())

    def _current_main_checkbox_values(self):
        getter = getattr(self.parent_app, "_current_main_checkbox_values", None)
        if callable(getter):
            return getter()
        bool_vars = getattr(self.parent_app, "bool_vars", {}) or {}
        values = {field: bool(var.get()) for field, var in bool_vars.items()}
        dry_var = getattr(self.parent_app, "dry_run_var", None)
        values["dry_run"] = bool(dry_var.get()) if dry_var is not None else bool(getattr(self.config, "main_window_dry_run", False))
        return main_window_checkbox_values(values or self.config, dry_run=values["dry_run"])

    def _current_dry_run(self):
        return bool(self._current_main_checkbox_values()["dry_run"])

    def _refresh_config(self):
        values = self._current_main_checkbox_values()
        validate_compliant_rename_exclusivity(values)
        self.config.compliant = values["compliant"]
        self.config.compliant_artist_mode = "as-is" if values["as_is_artist_name"] else "master"
        self.config.as_is_artist_name = values["as_is_artist_name"]
        self.config.tag_during_inventory = values["tag_during_inventory"]
        # Add Shows stages material inside TLOHome and does not run either
        # Full Inventory copy mode. Preserve those main selections only for
        # the consistent review dialog.
        self.config.tag_copy_during_inventory = False
        self.config.tag_copy_destination = ""
        self.config.tag_copy_and_delete_path = ""
        self.config.main_window_tag_copy_selected = values["tag_copy_during_inventory"]
        self.config.main_window_tag_copy_delete_selected = values["tag_copy_and_delete_enabled"]
        self.config.rename_compliantly = values["rename_compliantly"]
        self.config.convert_shn = values["convert_shn"]
        self.config.artist_in_album = values["artist_in_album"]
        self.config.etree_lookup = values["etree_lookup"]
        self.config.setlistfm_lookup = values["setlistfm_lookup"]
        self.config.setlistfm_upgrade = bool(values.get("setlistfm_upgrade", False))
        self.config.thorough_setlist_matching = bool(values.get("thorough_setlist_matching", False))
        if self.config.setlistfm_lookup and self.config.setlistfm_upgrade:
            self.config.setlistfm_min_interval_seconds = 1.0 / 14.0
            self.config.setlistfm_max_calls = 0
            self.config.setlistfm_max_calls_per_day = 48000
        else:
            self.config.setlistfm_min_interval_seconds = 0.600
            self.config.setlistfm_max_calls = 1400
            self.config.setlistfm_max_calls_per_day = 0
        self.config.current_volume_label = self.volume_var.get().strip()
        self.config.main_window_dry_run = values["dry_run"]
        self.config.add_shows_dry_run = values["dry_run"]
        self.config.main_window_checkbox_values = dict(values)
        return self.config

    def _volume_validation(self):
        current_volume = self.volume_var.get().strip()
        bootlist_exists = os.path.isfile(self._bootlist_path())
        if current_volume:
            return "ok", "Current storage volume is available for new bootlist rows."
        if bootlist_exists:
            return "warning", "Current storage volume is blank. New bootlist rows will not include a volume label."
        return "error", "Enter the Current Backup/Storage Drive and Volume before creating the first bootlist."

    def _refresh_volume_validation(self):
        level, message = self._volume_validation()
        marker = {"ok": "OK", "warning": "Warning", "error": "Error"}[level]
        self.volume_status_var.set(f"{marker}: {message}")
        self._set_processing_controls(not self._processing)

    def _set_processing_controls(self, enabled):
        base_state = "normal" if enabled else "disabled"
        for button_name in ("process_dups_button",):
            button = getattr(self, button_name, None)
            if button is not None:
                try:
                    button.configure(state=base_state)
                except tk.TclError:
                    pass
        process_new = getattr(self, "process_new_button", None)
        if process_new is not None:
            level, _message = self._volume_validation()
            try:
                process_new.configure(state=("normal" if enabled and (level != "error" or self._current_dry_run()) else "disabled"))
            except tk.TclError:
                pass

    def _refresh_elapsed_display(self):
        try:
            if self._processing and self._started_at is not None:
                self.elapsed_var.set(f"Elapsed: {format_elapsed(time.monotonic() - self._started_at)}")
            self._elapsed_after_id = self.window.after(500, self._refresh_elapsed_display)
        except tk.TclError:
            self._elapsed_after_id = None

    def _start_background_task(self, task_name, worker_func, done_func):
        if self._processing:
            messagebox.showinfo("TLO Inventory Updater", "Processing is already running.", parent=self.window)
            return False
        self._processing = True
        self._close_after_processing = False
        self._finish_notice_shown = False
        self._started_at = time.monotonic()
        self.status_var.set(f"{task_name}: running")
        self.elapsed_var.set("Elapsed: 0:00")
        try:
            _start_activity_indicator(self.progress_bar)
        except tk.TclError:
            pass
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
        elapsed = time.monotonic() - self._started_at if self._started_at is not None else 0.0
        self._processing = False
        self._processing_thread = None
        self._started_at = None
        try:
            self.progress_bar.stop()
        except tk.TclError:
            pass
        self.elapsed_var.set(f"Elapsed: {format_elapsed(elapsed)}")
        self._set_processing_controls(True)
        should_close = bool(self._close_after_processing)
        self._close_after_processing = False

        if error is not None:
            self.status_var.set(f"{task_name}: stopped with an error")
            if not should_close:
                messagebox.showerror("TLO Inventory Updater", str(error), parent=self.window)
            else:
                messagebox.showerror("TLO Inventory Updater", f"{task_name} did not complete: {error}", parent=self.window)
                self._destroy_updater_window()
            return

        self.status_var.set(f"{task_name}: complete")
        if should_close:
            self._destroy_updater_window()
            return

        done_func(result, elapsed_seconds=elapsed)

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

    def _new_show_review_lines(self, current_volume, check_duplicates, *, dry_run):
        ready = os.path.join(self.config.TLOHome, "readyForXfer")
        staged = os.path.join(self.config.TLOHome, "staged")
        dups = os.path.join(self.config.TLOHome, "dups")
        lines = operation_review_lines(
            self.config,
            operation="Add Shows - Process New Shows",
            path_text=ready,
            dry_run=dry_run,
            main_checkbox_source=self.config.main_window_checkbox_values,
            original_files_may_change=True,
        )
        lines[2:2] = [
            f"Accepted destination: {staged}",
            f"Potential duplicate destination: {dups}",
            f"Current storage volume: {current_volume or '(blank)'}",
            f"Check for Duplicates: {'Yes' if check_duplicates else 'No'}",
            f"Folders will be moved from readyForXfer: {'No' if dry_run else 'Yes'}",
        ]
        return lines

    def _process_new_shows(self):
        self._refresh_config()
        current_volume = self.volume_var.get().strip()
        check_duplicates = bool(self.check_dups_var.get())
        dry_run = self._current_dry_run()
        if not dry_run and not self._confirm_first_add_shows_run(current_volume):
            return
        review_lines = self._new_show_review_lines(current_volume, check_duplicates, dry_run=dry_run)
        if not _show_operation_review_and_log(
            self.window,
            config=self.config,
            action="Add Shows - Process New Shows Dry Run" if dry_run else "Add Shows - Process New Shows",
            title="Review Add Shows Dry Run" if dry_run else "Review Add Shows",
            lines=review_lines,
        ):
            return
        if dry_run:
            PreviewWindow(
                self.window,
                self.config,
                operation="Add Shows - New Shows Dry Run",
                preview_func=lambda cancel_check: preview_add_shows(
                    self.config,
                    mode="new",
                    check_duplicates=check_duplicates,
                    cancel_check=cancel_check,
                ),
            )
            return

        def worker():
            return process_new_shows(
                self.config,
                current_volume=current_volume,
                check_duplicates=check_duplicates,
            )

        self._start_background_task("Process New Shows", worker, self._show_process_new_result)

    def _show_process_new_result(self, result, *, elapsed_seconds=0.0):
        result = result or {}
        processed = int(result.get("processed", 0) or 0)
        duplicates = int(result.get("duplicates", 0) or 0)
        pdups = int(result.get("potential_duplicates_unavailable", 0) or 0)
        errors = int(result.get("errors", 0) or 0)
        staged = int(result.get("staged", 0) or 0)
        issues = []
        for entry in result.get("issues", []) or []:
            if isinstance(entry, RunIssue):
                issues.append(entry)
            elif isinstance(entry, dict):
                issues.append(RunIssue(
                    "Add Shows folder error",
                    str(entry.get("message") or "Folder processing failed."),
                    str(entry.get("path") or ""),
                    "error",
                    "add-shows",
                ))
        summary = "\n".join([
            "Add Shows processing complete",
            f"Folders considered: {processed}",
            f"Folders staged: {staged}",
            f"Potential duplicates moved to dups: {duplicates}",
            f"Cross-partition potential duplicates staged as pdup: {pdups}",
            f"Folder errors: {errors}",
            f"Elapsed: {format_elapsed(elapsed_seconds)}",
        ])
        _show_result_dialog(
            self.window,
            title="Add Shows Complete",
            summary=summary,
            issues=issues,
            tlo_home=self.config.TLOHome,
            primary_output=self._bootlist_path() if os.path.isfile(self._bootlist_path()) else "",
        )

    def _process_duplicates(self):
        self._refresh_config()
        dry_run = self._current_dry_run()
        lines = operation_review_lines(
            self.config,
            operation="Add Shows - Process Potential Duplicate/Upgrades",
            path_text=os.path.join(self.config.TLOHome, "dups"),
            dry_run=dry_run,
            main_checkbox_source=self.config.main_window_checkbox_values,
            original_files_may_change=False,
        )
        lines[2:2] = [
            "Action: identify folders and open a review window for each potential match",
            "Folders are not changed during this scan: Yes",
        ]
        if not _show_operation_review_and_log(
            self.window,
            config=self.config,
            action=(
                "Add Shows - Process Potential Duplicate/Upgrades Dry Run"
                if dry_run
                else "Add Shows - Process Potential Duplicate/Upgrades"
            ),
            title="Review Potential Duplicate/Upgrades Dry Run" if dry_run else "Review Potential Duplicate/Upgrades",
            lines=lines,
        ):
            return
        if dry_run:
            PreviewWindow(
                self.window,
                self.config,
                operation="Add Shows - Potential Duplicate/Upgrades Dry Run",
                preview_func=lambda cancel_check: preview_add_shows(
                    self.config,
                    mode="duplicates",
                    cancel_check=cancel_check,
                ),
            )
            return

        def worker():
            return duplicate_work_items(self.config)

        self._start_background_task("Process Potential Duplicate/Upgrades", worker, self._show_duplicate_work_items)

    def _show_duplicate_work_items(self, items, *, elapsed_seconds=0.0):
        if not items:
            summary = "\n".join([
                "Potential duplicate/upgrade scan complete",
                "Review items found: 0",
                f"Elapsed: {format_elapsed(elapsed_seconds)}",
            ])
            _show_result_dialog(
                self.window,
                title="Duplicate Scan Complete",
                summary=summary,
                issues=[],
                tlo_home=self.config.TLOHome,
            )
            return
        self.status_var.set(f"Duplicate review ready: {len(items)} folder(s)")
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
        self.status_var.set("Potential duplicate/upgrade processing complete")
        _show_result_dialog(
            self.window,
            title="Duplicate Processing Complete",
            summary="Potential duplicate/upgrade processing complete.\nAll reviewed folders have been resolved.",
            issues=[],
            tlo_home=self.config.TLOHome,
            primary_output=self._bootlist_path() if os.path.isfile(self._bootlist_path()) else "",
        )
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
        except tk.TclError:
            pass

    def _request_exit(self):
        if self._processing:
            if not messagebox.askokcancel(
                "TLO Inventory Updater",
                "Processing is still running. Close the updater after the current operation finishes?",
                parent=self.window,
            ):
                return
            self._close_after_processing = True
            self.status_var.set("Current operation will finish before the updater closes.")
            return
        if self.child_windows:
            if not messagebox.askokcancel(
                "TLO Inventory Updater",
                "Duplicate review windows are still open. Close all updater windows?",
                parent=self.window,
            ):
                return
            for child in list(self.child_windows):
                try:
                    child.window.destroy()
                except Exception as exc:  # noqa: BLE001 - best-effort boundary
                    debug_suppressed_exception(__name__, exc)
            self.child_windows = []
        self._destroy_updater_window()

    def _destroy_updater_window(self):
        if self._elapsed_after_id is not None:
            try:
                self.window.after_cancel(self._elapsed_after_id)
            except tk.TclError:
                pass
            self._elapsed_after_id = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass
        self.parent_app.active_updater_window = None
        self.parent_app._update_main_action_states()


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
