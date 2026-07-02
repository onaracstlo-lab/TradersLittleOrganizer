#!/usr/bin/env python3
"""
tlo-gsi.py

Tkinter GUI that:
- Reads the clipboard on startup, unless --find was supplied
- Prefills the Search box
- Automatically runs the first search on startup
- In normal mode, searches TLOHome/bootlist.csv and shows matches in a multi-select results window
- In Deep mode, searches individual text files under TLOHome/setlists and shows matching filenames
- Opens one viewer window per selected setlist file using a direct setlist filename lookup
- Maintains an in-memory search history dropdown for the current app session only
"""

from __future__ import annotations

__version__ = "v318"
# TLO-GI package version: v318

import csv
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Iterable, List, Sequence

APP_FILE_NAME = "tlo-gsi.py"
try:
    from tlo_version import DISPLAY_VERSION
except ImportError:
    DISPLAY_VERSION = "v1.0 Build 318"

APP_INTERNAL_VERSION = "v030"
DISPLAY_COLUMNS = ("Show", "Volume/Path")
DEEP_RESULTS_COLUMN = ("File",)
MAX_FILES_TO_OPEN_WITHOUT_PROMPT = 5
MAX_SETLIST_FILES_TO_OPEN = 30
DEFAULT_TLOHOME = "/mnt/c/b"
TLOHOME_ENV_VAR = "TLOHome"
SETLIST_VIEWER_WIDTH = 900
SETLIST_VIEWER_HEIGHT = 700
SETLIST_VIEWER_CASCADE_LEFT = 60
SETLIST_VIEWER_CASCADE_TOP = 60
SETLIST_VIEWER_CASCADE_X_STEP = 40
SETLIST_VIEWER_CASCADE_Y_STEP = 34
_setlist_viewer_cascade_index = 0

EditableTextWidget = tk.Entry | ttk.Entry | ttk.Combobox


HELP_TEXT = f"""{APP_FILE_NAME}

Usage:
  python3 {APP_FILE_NAME}
  python3 {APP_FILE_NAME} -h
  python3 {APP_FILE_NAME} --help
  python3 {APP_FILE_NAME} --TLOHome /full/path
  python3 {APP_FILE_NAME} --find \"Deep Purple |AND| 1976\"
  python3 {APP_FILE_NAME} --TLOHome /full/path --find \"(Deep Purple |OR| Rainbow) |AND| 'Fillmore West'\"

TLOHome:
- TLOHome can be supplied by environment variable {TLOHOME_ENV_VAR} or by --TLOHome.
- --TLOHome overrides the environment variable.
- TLOHome must be a non-empty, full, accessible directory path.
- The app uses these paths under TLOHome:
    bootlist.csv
    setlists/

Startup behavior:
- On startup, the app fills the Search box and automatically runs the first search.
- If --find is supplied, that value is used for the first search instead of the clipboard.
- If --find is not supplied, the app uses the current paste buffer.
- The Search box stays focused in the main window.

Search modes:
- If Deep is unchecked, the app searches bootlist.csv.
- If Deep is checked, the app searches the text files under setlists/.
- Deep search requires a non-empty search term.
- In normal mode, an empty Search box returns all CSV rows.

Search logic:
- Use |AND| and |OR| to combine terms.
- Parentheses are supported.
- Operators are case-insensitive.
- If a term is surrounded by single or double quotes, those outer quotes are removed before searching.

Results windows:
- You can select multiple rows/files with normal Shift and Control selection.
- View is the default action in the results windows.
- If no files are selected, the app says so.
- View directly generates each setlist filename from the Show value and opens TLOHome/setlists/THAT_FILE.txt.
- View does not scan the setlists directory while opening normal search results.
- If you try to open more than {MAX_FILES_TO_OPEN_WITHOUT_PROMPT} files at once, the app asks:
  \"You're trying to open x files!  Are you sure?\"
  The default answer is No.
- Text file display windows are cascaded down and right when multiple setlists are opened.
- More than {MAX_SETLIST_FILES_TO_OPEN} setlist files cannot be opened at once.

CSV handling:
- The app honors a leading sep= line for the delimiter.
- It ignores the actual header names.
- It treats the data positionally as 2 columns:
    Show, Volume/Path
- Setlist filenames are derived from the Show value by removing spaces and punctuation except ampersands, parentheses, and all dash/hyphen characters, then appending .txt.
- When opening setlists from normal results, the app opens only the directly generated .txt filename.

Search box shortcuts:
- Control-A select all
- Control-C copy
- Control-X cut
- Control-V paste
- Shift-Insert paste
- Delete delete selection or next character
- Numeric keypad Delete is enabled

Font selector:
- The main window includes a pulldown to change the font family for the running app session.
"""


@dataclass(frozen=True)
class AppPaths:
    tlohome: Path
    bootlist_csv: Path
    setlist_dir: Path


@dataclass(frozen=True)
class CsvRow:
    show: str
    volume_path: str

    def as_display_values(self) -> tuple[str, str]:
        return (self.show, self.volume_path)

    def search_text(self) -> str:
        return " | ".join(self.as_display_values())


class SearchExpressionError(ValueError):
    pass


class ExprNode:
    def evaluate(self, haystack_casefolded: str) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class TermNode(ExprNode):
    term: str

    def evaluate(self, haystack_casefolded: str) -> bool:
        return self.term.casefold() in haystack_casefolded


@dataclass(frozen=True)
class AndNode(ExprNode):
    left: ExprNode
    right: ExprNode

    def evaluate(self, haystack_casefolded: str) -> bool:
        return self.left.evaluate(haystack_casefolded) and self.right.evaluate(haystack_casefolded)


@dataclass(frozen=True)
class OrNode(ExprNode):
    left: ExprNode
    right: ExprNode

    def evaluate(self, haystack_casefolded: str) -> bool:
        return self.left.evaluate(haystack_casefolded) or self.right.evaluate(haystack_casefolded)


class ExpressionParser:
    def __init__(self, tokens: Sequence[str]) -> None:
        self.tokens = list(tokens)
        self.index = 0

    def parse(self) -> ExprNode:
        if not self.tokens:
            raise SearchExpressionError("Empty search expression.")
        node = self._parse_or()
        if self.index != len(self.tokens):
            raise SearchExpressionError(f"Unexpected token: {self.tokens[self.index]}")
        return node

    def _parse_or(self) -> ExprNode:
        node = self._parse_and()
        while self._peek_is_operator("|OR|"):
            self.index += 1
            node = OrNode(node, self._parse_and())
        return node

    def _parse_and(self) -> ExprNode:
        node = self._parse_factor()
        while self._peek_is_operator("|AND|"):
            self.index += 1
            node = AndNode(node, self._parse_factor())
        return node

    def _parse_factor(self) -> ExprNode:
        if self.index >= len(self.tokens):
            raise SearchExpressionError("Incomplete search expression.")

        token = self.tokens[self.index]
        if token == "(":
            self.index += 1
            node = self._parse_or()
            if self.index >= len(self.tokens) or self.tokens[self.index] != ")":
                raise SearchExpressionError("Missing closing parenthesis.")
            self.index += 1
            return node

        if token == ")":
            raise SearchExpressionError("Unexpected closing parenthesis.")

        if token.casefold() in ("|and|", "|or|"):
            raise SearchExpressionError(f"Unexpected operator: {token}")

        self.index += 1
        cleaned = strip_outer_quotes(token)
        if not cleaned:
            raise SearchExpressionError("Empty quoted term in search expression.")
        return TermNode(cleaned)

    def _peek_is_operator(self, operator: str) -> bool:
        return self.index < len(self.tokens) and self.tokens[self.index].casefold() == operator.casefold()


class AppConfigError(ValueError):
    pass


class BootlistSearchApp:
    def __init__(self, root: tk.Tk, paths: AppPaths, initial_find: str | None) -> None:
        self.root = root
        self.paths = paths
        self.initial_find = initial_find

        self.root.title(f"TLO Search {DISPLAY_VERSION}")
        self.root.geometry("860x280")

        self.style = ttk.Style(self.root)
        self.search_var = tk.StringVar()
        self.tlohome_var = tk.StringVar(value=str(paths.tlohome))
        self.deep_var = tk.BooleanVar(value=False)
        self.font_family_var = tk.StringVar()
        self.search_history: List[str] = []
        self.search_entry: ttk.Combobox | None = None
        self.tlohome_entry: ttk.Entry | None = None
        self.font_selector: ttk.Combobox | None = None
        self.csv_result_windows: List[CsvSearchResultsWindow] = []
        self.available_font_families = self._build_font_family_list()
        self.font_family_var.set(self._default_font_family())
        self._apply_font_family(self.font_family_var.get())

        self._build_main_window()
        self.root.after(150, self._startup_first_search)

    def _default_font_family(self) -> str:
        try:
            return str(tkfont.nametofont("TkDefaultFont").actual("family"))
        except tk.TclError:
            return "TkDefaultFont"

    def _build_font_family_list(self) -> List[str]:
        try:
            available = sorted({name for name in tkfont.families(self.root) if name and not name.startswith("@")}, key=str.casefold)
        except tk.TclError:
            available = []

        preferred = [
            self._default_font_family(),
            "Arial",
            "Segoe UI",
            "Calibri",
            "Helvetica",
            "Verdana",
            "Tahoma",
            "Ubuntu",
            "DejaVu Sans",
            "Liberation Sans",
            "Noto Sans",
            "Cantarell",
            "Times New Roman",
            "Courier New",
        ]

        ordered: List[str] = []
        for name in preferred:
            if name and name not in ordered and (not available or name in available):
                ordered.append(name)

        for name in available:
            if name not in ordered:
                ordered.append(name)

        return ordered or [self._default_font_family()]

    def _apply_font_family(self, family: str) -> None:
        chosen = family.strip() or self._default_font_family()

        for font_name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                tkfont.nametofont(font_name).configure(family=chosen)
            except tk.TclError:
                pass

        self.style.configure("Treeview", font="TkDefaultFont")
        self.style.configure("Treeview.Heading", font="TkHeadingFont")
        self._refresh_csv_result_windows()

    def _on_font_family_changed(self, _event: tk.Event | None = None) -> None:
        self._apply_font_family(self.font_family_var.get())

    def register_csv_result_window(self, window: CsvSearchResultsWindow) -> None:
        self.csv_result_windows.append(window)

    def unregister_csv_result_window(self, window: CsvSearchResultsWindow) -> None:
        self.csv_result_windows = [item for item in self.csv_result_windows if item is not window]

    def _refresh_csv_result_windows(self) -> None:
        alive: List[CsvSearchResultsWindow] = []
        for window in self.csv_result_windows:
            try:
                if window.window.winfo_exists():
                    window.apply_column_layout()
                    alive.append(window)
            except tk.TclError:
                continue
        self.csv_result_windows = alive

    def _build_main_window(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        header_font = tkfont.nametofont("TkHeadingFont").copy()
        try:
            header_font.configure(weight="bold")
        except tk.TclError:
            pass
        ttk.Label(
            outer,
            text="Traders Little Organizer™ Collection Search App",
            font=header_font,
        ).pack(anchor="w", pady=(0, 12))

        search_frame = ttk.Frame(outer)
        search_frame.pack(fill="x", expand=True)

        ttk.Label(search_frame, text="TLOHome").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.tlohome_entry = ttk.Entry(search_frame, textvariable=self.tlohome_var)
        self.tlohome_entry.grid(row=0, column=1, sticky="ew")
        bind_standard_entry_shortcuts(self.tlohome_entry)

        ttk.Label(search_frame, text="Search").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))

        self.search_entry = ttk.Combobox(
            search_frame,
            textvariable=self.search_var,
            values=self.search_history,
            state="normal",
        )
        self.search_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self.search_entry.focus_set()
        bind_standard_entry_shortcuts(self.search_entry)
        self.search_entry.bind("<Return>", lambda event: self.execute_search())
        self.search_entry.bind("<<ComboboxSelected>>", lambda event: self.search_entry.icursor(tk.END))

        deep_check = ttk.Checkbutton(search_frame, text="Deep", variable=self.deep_var)
        deep_check.grid(row=2, column=1, sticky="w", pady=(8, 0))

        ttk.Label(search_frame, text="Font").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.font_selector = ttk.Combobox(
            search_frame,
            textvariable=self.font_family_var,
            values=self.available_font_families,
            state="readonly",
            width=28,
        )
        self.font_selector.grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.font_selector.bind("<<ComboboxSelected>>", self._on_font_family_changed)

        search_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(outer)
        button_frame.pack(fill="x", pady=(12, 0))

        ttk.Button(button_frame, text="Execute search", command=self.execute_search).pack(side="left")
        ttk.Button(button_frame, text="Quit", command=self.root.destroy).pack(side="left", padx=(8, 0))

    def _startup_first_search(self) -> None:
        initial_value = ""

        if self.initial_find is not None:
            initial_value = self.initial_find
        else:
            try:
                initial_value = self.root.clipboard_get().strip()
            except tk.TclError:
                initial_value = ""

        if initial_value:
            self.search_var.set(initial_value)

        self.execute_search()

        if not self._app_is_alive():
            return

        try:
            self.root.deiconify()
            self.root.lift()
        except tk.TclError:
            pass

        if self.search_entry is not None and self._app_is_alive():
            try:
                self.search_entry.focus_set()
            except tk.TclError:
                pass

    def _app_is_alive(self) -> bool:
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def _remember_search(self, search_text: str) -> None:
        cleaned = search_text.strip()
        if not cleaned:
            return

        updated = [cleaned]
        updated.extend(item for item in self.search_history if item != cleaned)
        self.search_history = updated

        if self.search_entry is not None:
            self.search_entry["values"] = self.search_history

    def _sync_paths_from_tlohome_box(self) -> bool:
        try:
            tlohome = validate_tlohome(self.tlohome_var.get())
        except AppConfigError as exc:
            messagebox.showerror("Error", str(exc), parent=self.root)
            return False
        self.paths = build_paths(tlohome)
        self.tlohome_var.set(str(tlohome))
        return True

    def execute_search(self) -> None:
        if not self._sync_paths_from_tlohome_box():
            return

        search_text = self.search_var.get().strip()
        self._remember_search(search_text)

        if self.deep_var.get():
            self._execute_deep_search(search_text)
        else:
            self._execute_csv_search(search_text)

    def _execute_csv_search(self, search_text: str) -> None:
        if not self.paths.bootlist_csv.is_file():
            messagebox.showerror("Error", f"bootlist.csv not found:\n{self.paths.bootlist_csv}", parent=self.root)
            self.root.destroy()
            return

        try:
            rows = load_bootlist_rows(self.paths.bootlist_csv)
            matched_rows = search_rows(rows, search_text)
        except SearchExpressionError as exc:
            messagebox.showerror("Search error", str(exc), parent=self.root)
            return
        except Exception as exc:
            messagebox.showerror(
                "Error",
                f"Failed to read CSV:\n{self.paths.bootlist_csv}\n\n{exc}",
                parent=self.root,
            )
            return

        if not matched_rows:
            messagebox.showinfo(
                "No matches",
                f"No matching rows found in:\n{self.paths.bootlist_csv}\n\nSearch: {search_text or '(empty string)'}",
                parent=self.root,
            )
            if self._app_is_alive():
                try:
                    self.root.deiconify()
                    self.root.lift()
                except tk.TclError:
                    pass
            return

        CsvSearchResultsWindow(self.root, self, self.paths, matched_rows)

    def _execute_deep_search(self, search_text: str) -> None:
        if not search_text:
            messagebox.showerror(
                "Error",
                "Must have a search term for deep search! Please try again.",
                parent=self.root,
            )
            return

        if not self.paths.setlist_dir.is_dir():
            messagebox.showerror("Error", f"Setlist directory not found:\n{self.paths.setlist_dir}", parent=self.root)
            return

        try:
            matched_files = search_setlist_files(self.paths.setlist_dir, search_text)
        except SearchExpressionError as exc:
            messagebox.showerror("Search error", str(exc), parent=self.root)
            return
        except Exception as exc:
            messagebox.showerror(
                "Error",
                f"Failed during deep search in:\n{self.paths.setlist_dir}\n\n{exc}",
                parent=self.root,
            )
            return

        if not matched_files:
            messagebox.showinfo(
                "No matches",
                f"No matching files found in:\n{self.paths.setlist_dir}\n\nSearch: {search_text}",
                parent=self.root,
            )
            if self._app_is_alive():
                try:
                    self.root.deiconify()
                    self.root.lift()
                except tk.TclError:
                    pass
            return

        DeepSearchResultsWindow(self.root, self.paths, matched_files)


class CsvSearchResultsWindow:
    def __init__(self, parent: tk.Misc, app: BootlistSearchApp, paths: AppPaths, rows: Sequence[CsvRow]) -> None:
        self.app = app
        self.paths = paths
        self.rows = list(rows)
        self.window = tk.Toplevel(parent)
        self.window.title(f"Search Results ({len(self.rows)})")
        self.window.geometry("1200x500")
        self.tree: ttk.Treeview | None = None
        self._resize_after_id: str | None = None
        self._view_in_progress = False
        self._build_window()

    def _build_window(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=DISPLAY_COLUMNS, show="headings", selectmode="extended")

        for column in DISPLAY_COLUMNS:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=180, anchor="w", stretch=True)

        vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        for idx, row in enumerate(self.rows):
            self.tree.insert("", "end", iid=str(idx), values=row.as_display_values())

        button_frame = ttk.Frame(outer)
        button_frame.pack(fill="x", pady=(10, 0))

        view_button = ttk.Button(button_frame, text="View", command=self.view_selected, default="active")
        view_button.pack(side="left")
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side="left", padx=(8, 0))

        # Bind Return only on the Treeview. The View button already handles Return when it has focus.
        self.tree.bind("<Return>", self._on_return_view)
        self.tree.bind("<Double-1>", self._on_return_view)
        self.window.bind("<Configure>", self._queue_column_layout, add="+")
        self.window.bind("<Destroy>", self._on_destroy, add="+")
        view_button.focus_set()
        self.app.register_csv_result_window(self)
        self.window.after_idle(self.apply_column_layout)

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self.window:
            self.app.unregister_csv_result_window(self)
            if self._resize_after_id is not None:
                try:
                    self.window.after_cancel(self._resize_after_id)
                except tk.TclError:
                    pass
                self._resize_after_id = None

    def _queue_column_layout(self, event: tk.Event) -> None:
        if event.widget is not self.window:
            return
        if self._resize_after_id is not None:
            try:
                self.window.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
        self._resize_after_id = self.window.after(60, self.apply_column_layout)

    def apply_column_layout(self) -> None:
        self._resize_after_id = None
        if self.tree is None:
            return
        try:
            if not self.window.winfo_exists():
                return
            self.window.update_idletasks()
        except tk.TclError:
            return

        available_width = max(self.tree.winfo_width(), self.window.winfo_width() - 60, 900)
        show_width = max(300, int(available_width * 0.55))
        volume_path_width = max(240, available_width - show_width)

        self.tree.column("Show", width=show_width, minwidth=220, anchor="w", stretch=True)
        self.tree.column("Volume/Path", width=volume_path_width, minwidth=200, anchor="w", stretch=True)

    def _on_return_view(self, event: tk.Event) -> str:
        self.view_selected()
        return "break"

    def _finish_view_action(self) -> None:
        self._view_in_progress = False
        try:
            if self.window.winfo_exists():
                self.window.focus_set()
        except tk.TclError:
            pass

    def view_selected(self) -> None:
        if self._view_in_progress:
            return

        if self.tree is None:
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "No files are selected.", parent=self.window)
            return

        selected_indices = [int(item_id) for item_id in selected]
        if not enforce_open_limit(self.window, len(selected_indices)):
            return

        file_paths: List[Path] = []
        missing_paths: List[str] = []
        seen_paths: set[str] = set()

        for row_index in selected_indices:
            if row_index < 0 or row_index >= len(self.rows):
                continue

            row = self.rows[row_index]
            file_path = resolve_setlist_path_from_show(self.paths, row.show)
            if not file_path.is_file():
                missing_paths.append(str(file_path))
                continue

            normalized_path = os.path.normcase(os.path.abspath(str(file_path)))
            if normalized_path not in seen_paths:
                seen_paths.add(normalized_path)
                file_paths.append(file_path)

        if missing_paths:
            show_missing_setlists_notice(self.window, missing_paths)

        if not file_paths:
            return

        self._view_in_progress = True
        reset_setlist_viewer_cascade()
        try:
            for file_path in file_paths:
                open_file_viewer_window(self.window, file_path)
        finally:
            self._finish_view_action()


class DeepSearchResultsWindow:
    def __init__(self, parent: tk.Misc, paths: AppPaths, file_paths: Sequence[Path]) -> None:
        self.paths = paths
        self.file_paths = list(file_paths)
        self.window = tk.Toplevel(parent)
        self.window.title(f"Deep Search Results ({len(self.file_paths)})")
        self.window.geometry("900x500")
        self.tree: ttk.Treeview | None = None
        self._view_in_progress = False
        self._build_window()

    def _build_window(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=DEEP_RESULTS_COLUMN, show="headings", selectmode="extended")
        self.tree.heading("File", text="File")
        self.tree.column("File", width=860, anchor="w", stretch=True)

        vscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        for idx, file_path in enumerate(self.file_paths):
            self.tree.insert("", "end", iid=str(idx), values=(get_display_file_name(self.paths, file_path),))

        button_frame = ttk.Frame(outer)
        button_frame.pack(fill="x", pady=(10, 0))

        view_button = ttk.Button(button_frame, text="View", command=self.view_selected, default="active")
        view_button.pack(side="left")
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side="left", padx=(8, 0))

        self.tree.bind("<Return>", self._on_return_view)
        self.tree.bind("<Double-1>", self._on_return_view)
        view_button.focus_set()

    def _on_return_view(self, event: tk.Event) -> str:
        self.view_selected()
        return "break"

    def _finish_view_action(self) -> None:
        self._view_in_progress = False
        try:
            if self.window.winfo_exists():
                self.window.focus_set()
        except tk.TclError:
            pass

    def view_selected(self) -> None:
        if self._view_in_progress:
            return
        if self.tree is None:
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "No files are selected.", parent=self.window)
            return

        selected_indices = [int(item_id) for item_id in selected]
        self._view_in_progress = True
        try:
            self.window.after_idle(lambda: self._process_selected_files(selected_indices))
        except tk.TclError:
            self._view_in_progress = False

    def _process_selected_files(self, selected_indices: Sequence[int]) -> None:
        try:
            file_paths = [self.file_paths[index] for index in selected_indices if 0 <= index < len(self.file_paths)]
            if not file_paths:
                return
            if not enforce_open_limit(self.window, len(file_paths)):
                self._finish_view_action()
                return
            reset_setlist_viewer_cascade()
            self._open_file_paths_one_at_a_time(file_paths, 0)
            return
        finally:
            if 'file_paths' not in locals() or not file_paths:
                self._finish_view_action()

    def _open_file_paths_one_at_a_time(self, file_paths: Sequence[Path], index: int) -> None:
        try:
            if index >= len(file_paths) or not self.window.winfo_exists():
                self._finish_view_action()
                return
            open_file_viewer_window(self.window, file_paths[index])
            self.window.after(25, lambda: self._open_file_paths_one_at_a_time(file_paths, index + 1))
        except tk.TclError:
            self._view_in_progress = False
        except Exception as exc:
            show_nonblocking_notice(self.window, "View error", f"Unable to open selected file:\n{exc}")
            self._finish_view_action()


class SetlistViewerWindow:
    def __init__(self, parent: tk.Misc, file_path: Path, content: str) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title(file_path.name)
        self.window.geometry(next_setlist_viewer_geometry(parent))

        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=file_path.name).pack(anchor="w", pady=(0, 8))

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)

        text_widget = tk.Text(text_frame, wrap="word", font="TkTextFont")
        text_widget.insert("1.0", content)
        text_widget.configure(state="disabled")

        vscroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        hscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=text_widget.xview)
        text_widget.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)

        text_widget.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        ttk.Button(outer, text="Close", command=self.window.destroy).pack(anchor="w", pady=(10, 0))

        try:
            self.window.lift()
        except tk.TclError:
            pass


def reset_setlist_viewer_cascade() -> None:
    global _setlist_viewer_cascade_index
    _setlist_viewer_cascade_index = 0


def next_setlist_viewer_geometry(parent: tk.Misc) -> str:
    global _setlist_viewer_cascade_index

    index = _setlist_viewer_cascade_index
    _setlist_viewer_cascade_index += 1

    width = SETLIST_VIEWER_WIDTH
    height = SETLIST_VIEWER_HEIGHT

    try:
        screen_width = int(parent.winfo_screenwidth())
        screen_height = int(parent.winfo_screenheight())
    except tk.TclError:
        screen_width = 1920
        screen_height = 1080

    max_left = max(SETLIST_VIEWER_CASCADE_LEFT, screen_width - width - SETLIST_VIEWER_CASCADE_LEFT)
    max_top = max(SETLIST_VIEWER_CASCADE_TOP, screen_height - height - SETLIST_VIEWER_CASCADE_TOP)

    x_steps = max(0, (max_left - SETLIST_VIEWER_CASCADE_LEFT) // SETLIST_VIEWER_CASCADE_X_STEP)
    y_steps = max(0, (max_top - SETLIST_VIEWER_CASCADE_TOP) // SETLIST_VIEWER_CASCADE_Y_STEP)
    max_steps = min(x_steps, y_steps)

    effective_index = index
    if max_steps > 0:
        effective_index = index % (max_steps + 1)

    left = SETLIST_VIEWER_CASCADE_LEFT + (effective_index * SETLIST_VIEWER_CASCADE_X_STEP)
    top = SETLIST_VIEWER_CASCADE_TOP + (effective_index * SETLIST_VIEWER_CASCADE_Y_STEP)

    return f"{width}x{height}+{left}+{top}"


def bind_standard_entry_shortcuts(widget: EditableTextWidget) -> None:
    widget.bind("<Control-a>", select_all_entry)
    widget.bind("<Control-A>", select_all_entry)
    widget.bind("<Control-c>", copy_entry_selection)
    widget.bind("<Control-C>", copy_entry_selection)
    widget.bind("<Control-x>", cut_entry_selection)
    widget.bind("<Control-X>", cut_entry_selection)
    widget.bind("<Control-v>", paste_into_entry)
    widget.bind("<Control-V>", paste_into_entry)
    widget.bind("<Shift-Insert>", paste_into_entry)
    widget.bind("<Delete>", delete_entry_selection_or_char)
    widget.bind("<KP_Delete>", delete_entry_selection_or_char)


def is_editable_text_widget(widget: object) -> bool:
    return isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox))


def select_all_entry(event: tk.Event) -> str:
    widget = event.widget
    if is_editable_text_widget(widget):
        widget.selection_range(0, tk.END)
        widget.icursor(tk.END)
        return "break"
    return ""


def copy_entry_selection(event: tk.Event) -> str:
    widget = event.widget
    if not is_editable_text_widget(widget):
        return ""

    try:
        selected_text = widget.selection_get()
    except tk.TclError:
        return "break"

    widget.clipboard_clear()
    widget.clipboard_append(selected_text)
    return "break"


def cut_entry_selection(event: tk.Event) -> str:
    widget = event.widget
    if not is_editable_text_widget(widget):
        return ""

    try:
        selected_text = widget.selection_get()
        sel_first = widget.index("sel.first")
        sel_last = widget.index("sel.last")
    except tk.TclError:
        return "break"

    widget.clipboard_clear()
    widget.clipboard_append(selected_text)
    widget.delete(sel_first, sel_last)
    return "break"


def paste_into_entry(event: tk.Event) -> str:
    widget = event.widget
    if not is_editable_text_widget(widget):
        return ""

    try:
        pasted_text = widget.clipboard_get()
    except tk.TclError:
        return "break"

    try:
        sel_first = widget.index("sel.first")
        sel_last = widget.index("sel.last")
        widget.delete(sel_first, sel_last)
        insert_at = sel_first
    except tk.TclError:
        insert_at = widget.index(tk.INSERT)

    widget.insert(insert_at, pasted_text)
    return "break"


def delete_entry_selection_or_char(event: tk.Event) -> str:
    widget = event.widget
    if not is_editable_text_widget(widget):
        return ""

    try:
        sel_first = widget.index("sel.first")
        sel_last = widget.index("sel.last")
        widget.delete(sel_first, sel_last)
        return "break"
    except tk.TclError:
        pass

    cursor = widget.index(tk.INSERT)
    if cursor < len(widget.get()):
        widget.delete(cursor)
    return "break"


def strip_outer_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
        return stripped[1:-1].strip()
    return stripped


def parse_cli_args(argv: Sequence[str]) -> tuple[Path, str | None]:
    env_value = strip_outer_quotes(os.environ.get(TLOHOME_ENV_VAR, ""))
    tlohome_arg_value: str | None = None
    mytlo_arg_value: str | None = None
    find_value: str | None = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print(HELP_TEXT)
            raise SystemExit(0)

        if arg in ("--TLOHome", "--myTLO"):
            if i + 1 >= len(argv):
                raise AppConfigError(f"{arg} requires a value.")
            value = strip_outer_quotes(argv[i + 1])
            if arg == "--myTLO":
                mytlo_arg_value = value
            else:
                tlohome_arg_value = value
            i += 2
            continue

        if arg == "--find":
            if i + 1 >= len(argv):
                raise AppConfigError("--find requires a value.")
            find_value = strip_outer_quotes(argv[i + 1])
            i += 2
            continue

        raise AppConfigError(f"Unknown argument: {arg}")

    tlohome_value = mytlo_arg_value or tlohome_arg_value or env_value or DEFAULT_TLOHOME
    tlohome_path = validate_tlohome(tlohome_value)
    return tlohome_path, find_value

def validate_tlohome(value: str) -> Path:
    cleaned = strip_outer_quotes(value)
    if not cleaned:
        raise AppConfigError("TLOHome must be non-empty.")

    path = Path(cleaned)
    if not path.is_absolute():
        raise AppConfigError(f"TLOHome must be a full path: {cleaned}")
    if not path.exists():
        raise AppConfigError(f"TLOHome does not exist: {path}")
    if not path.is_dir():
        raise AppConfigError(f"TLOHome is not a directory: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise AppConfigError(f"TLOHome is not accessible: {path}")

    return path


def build_paths(tlohome: Path) -> AppPaths:
    return AppPaths(
        tlohome=tlohome,
        bootlist_csv=tlohome / "bootlist.csv",
        setlist_dir=tlohome / "setlists",
    )


def load_bootlist_rows(csv_path: Path) -> List[CsvRow]:
    rows: List[CsvRow] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
        delimiter = ","
        stripped_first = first_line.strip()
        if stripped_first.casefold().startswith("sep=") and len(stripped_first) >= 5:
            delimiter = stripped_first[4]
        else:
            handle.seek(0)

        reader = csv.reader(handle, delimiter=delimiter)

        # Always skip the header row. Header text is ignored.
        next(reader, None)

        for raw_row in reader:
            if not raw_row or not any((value or "").strip() for value in raw_row):
                continue

            padded = list(raw_row[:2])
            while len(padded) < 2:
                padded.append("")

            rows.append(
                CsvRow(
                    show=(padded[0] or "").strip(),
                    volume_path=(padded[1] or "").strip(),
                )
            )

    return rows

def tokenize_search_expression(text: str) -> List[str]:
    tokens: List[str] = []
    term_buffer: List[str] = []
    quote_char: str | None = None
    i = 0

    def flush_term() -> None:
        term = "".join(term_buffer).strip()
        term_buffer.clear()
        if term:
            tokens.append(term)

    while i < len(text):
        ch = text[i]

        if quote_char is not None:
            term_buffer.append(ch)
            if ch == quote_char:
                quote_char = None
            i += 1
            continue

        if ch in ('"', "'"):
            quote_char = ch
            term_buffer.append(ch)
            i += 1
            continue

        if ch in "()":
            flush_term()
            tokens.append(ch)
            i += 1
            continue

        remaining = text[i:]
        if remaining[:5].casefold() == "|and|":
            flush_term()
            tokens.append("|AND|")
            i += 5
            continue
        if remaining[:4].casefold() == "|or|":
            flush_term()
            tokens.append("|OR|")
            i += 4
            continue

        term_buffer.append(ch)
        i += 1

    if quote_char is not None:
        raise SearchExpressionError("Missing closing quote in search expression.")

    flush_term()
    return tokens


def build_search_predicate(search_text: str) -> Callable[[str], bool]:
    if not search_text.strip():
        return lambda _haystack: True

    tokens = tokenize_search_expression(search_text)
    tree = ExpressionParser(tokens).parse()
    return lambda haystack: tree.evaluate(haystack.casefold())


def search_rows(rows: Sequence[CsvRow], search_text: str) -> List[CsvRow]:
    predicate = build_search_predicate(search_text)
    return [row for row in rows if predicate(row.search_text())]


def search_setlist_files(setlist_dir: Path, search_text: str) -> List[Path]:
    predicate = build_search_predicate(search_text)
    matched_files: List[Path] = []

    for file_path in iter_setlist_files(setlist_dir):
        try:
            content = read_text_file(file_path)
        except Exception:
            continue

        if predicate(content):
            matched_files.append(file_path)

    matched_files.sort(key=lambda path: str(path).casefold())
    return matched_files


def iter_setlist_files(setlist_dir: Path) -> Iterable[Path]:
    for file_path in setlist_dir.rglob("*"):
        if file_path.is_file():
            yield file_path


def enforce_open_limit(parent: tk.Misc, selection_count: int) -> bool:
    if selection_count > MAX_SETLIST_FILES_TO_OPEN:
        messagebox.showerror(
            "Too many files selected",
            f"Cannot open {selection_count} setlist files at once. The hard limit is {MAX_SETLIST_FILES_TO_OPEN}.",
            parent=parent,
        )
        return False

    if selection_count > MAX_FILES_TO_OPEN_WITHOUT_PROMPT:
        return messagebox.askyesno(
            "Confirm open",
            f"You're trying to open {selection_count} files!  Are you sure?",
            default=messagebox.NO,
            parent=parent,
        )

    return True


def show_missing_setlists_notice(parent: tk.Misc, missing_paths: Sequence[str]) -> None:
    missing_text = "\n".join(str(path) for path in missing_paths[:10])
    if len(missing_paths) > 10:
        missing_text += f"\n... and {len(missing_paths) - 10} more"
    show_nonblocking_notice(
        parent,
        "Setlist not found",
        f"Setlist file not found:\n{missing_text}",
    )


def show_nonblocking_notice(parent: tk.Misc, title: str, message: str) -> None:
    """Show a small app-owned notice without grab/wait/modal behavior."""
    try:
        notice = tk.Toplevel(parent)
    except tk.TclError:
        return

    notice.title(title)
    notice.geometry("620x220")

    outer = ttk.Frame(notice, padding=12)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text=title, font="TkHeadingFont").pack(anchor="w", pady=(0, 8))

    text = tk.Text(outer, wrap="word", height=7, font="TkTextFont")
    text.insert("1.0", message)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True)

    button_frame = ttk.Frame(outer)
    button_frame.pack(fill="x", pady=(10, 0))

    def close_notice() -> None:
        try:
            notice.destroy()
        except tk.TclError:
            pass

    ok_button = ttk.Button(button_frame, text="OK", command=close_notice)
    ok_button.pack(side="left")
    notice.protocol("WM_DELETE_WINDOW", close_notice)


def open_file_viewer_window(parent: tk.Misc, file_path: Path) -> None:
    if not file_path.is_file():
        show_nonblocking_notice(parent, "Setlist not found", f"Setlist file not found:\n{file_path}")
        return

    try:
        content = read_text_file(file_path)
    except Exception as exc:
        show_nonblocking_notice(parent, "Read error", f"Failed to read:\n{file_path}\n\n{exc}")
        return

    SetlistViewerWindow(parent, file_path, content)


def open_setlist_window(parent: tk.Misc, paths: AppPaths, show_name: str) -> None:
    if not show_name:
        show_nonblocking_notice(parent, "Setlist error", "Selected row does not contain a show name.")
        return

    file_path = resolve_setlist_path_from_show(paths, show_name)
    open_file_viewer_window(parent, file_path)


def make_setlist_filename_from_show(show_name: str) -> str:
    cleaned = "".join(ch for ch in show_name if is_setlist_filename_char_to_keep(ch))
    return f"{cleaned}.txt"


def is_setlist_filename_char_to_keep(ch: str) -> bool:
    # Keep letters/numbers, ampersands, parentheses, and all Unicode dash/hyphen characters.
    # Unicode category "Pd" covers hyphen-minus, en dash, em dash, nonbreaking hyphen, etc.
    return ch.isalnum() or ch in "&()" or unicodedata.category(ch) == "Pd"


def resolve_setlist_path_from_show(paths: AppPaths, show_name: str) -> Path:
    return paths.setlist_dir / make_setlist_filename_from_show(show_name)


def resolve_setlist_paths_from_show(paths: AppPaths, show_name: str) -> List[Path]:
    file_path = resolve_setlist_path_from_show(paths, show_name)
    if file_path.is_file():
        return [file_path]
    return []


def get_display_file_name(paths: AppPaths, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(paths.setlist_dir))
    except ValueError:
        return file_path.name


def read_text_file(file_path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            with file_path.open("r", encoding=encoding) as handle:
                return handle.read()
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    with file_path.open("r") as handle:
        return handle.read()


def show_config_error_dialog(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror("Error", message, parent=root)
    finally:
        root.destroy()


def main(argv: Sequence[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)

    try:
        tlohome, initial_find = parse_cli_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    except AppConfigError as exc:
        try:
            show_config_error_dialog(str(exc))
        except Exception:
            print(f"Error: {exc}", file=sys.stderr)
        return 2

    root = tk.Tk()
    paths = build_paths(tlohome)
    BootlistSearchApp(root, paths, initial_find)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
