#!/usr/bin/env python3
"""
artist_db_search_gui.py
Version: v1.1 Build 317

Simple Tkinter GUI for searching TLOHome/TLO_DBs/artists.sqlite using the
newer artists / aliases / terms schema. TLOHome is resolved from --TLOHome,
the TLOHome environment variable, or the executable/package location.

Behavior:
- Main window contains:
  - query entry box
  - Search button
  - Quit button
  - result/status text box
- Searches the SQLite DB through the terms table.
- If no matches are found, writes "no results" to the result/status text box.
- If matches are found, writes "match found" to the result/status text box
  and opens a new window listing, for each matching artist:
      master/prime name
      search term
      all associated terms, one per line, as:
          term_text  --  term_type

Notes for the new schema:
- The terms table stores one searchable row for the master and each alias.
- term_type is either "master" or "alias".
- The schema no longer stores normalized lookup fields or typed alias tags
  such as abbreviation.
"""

from __future__ import annotations

__version__ = "v335"
# TLO-GI package version: v335

import argparse
import os
import sqlite3
import sys
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox
from tkinter import scrolledtext

try:
    from tlo_version import DISPLAY_VERSION
except ImportError:
    DISPLAY_VERSION = "v1.2 Build 335"

TLOHOME_ENV_VAR = "TLOHome"
WINDOW_TITLE = f"Artist DB Search - {DISPLAY_VERSION}"
RESULTS_WINDOW_TITLE = "Artist DB Matches"


@dataclass
class AssociatedTerm:
    term_text: str
    term_type: str
    term_order: int


@dataclass
class MatchRecord:
    artist_id: int
    master_name: str
    source_row_number: int
    associated_terms: list[AssociatedTerm] = field(default_factory=list)


class ArtistSearchApp:
    def __init__(self, root: tk.Tk, db_path: Path) -> None:
        self.root = root
        self.db_path = db_path
        self.root.title(WINDOW_TITLE)
        self.root.geometry("820x320")
        self.root.minsize(620, 240)

        self.search_var = tk.StringVar()
        self.results_window: tk.Toplevel | None = None
        self.results_text_widget: scrolledtext.ScrolledText | None = None

        self._build_ui()
        self._bind_shortcuts()
        self.search_entry.focus_set()

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, padx=12, pady=12)
        outer.pack(fill="both", expand=True)

        input_frame = tk.Frame(outer)
        input_frame.pack(fill="x")
        input_frame.columnconfigure(1, weight=1)

        tk.Label(input_frame, text="Search term:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
            pady=(0, 8),
        )

        self.search_entry = tk.Entry(input_frame, textvariable=self.search_var, width=72)
        self.search_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        button_frame = tk.Frame(outer)
        button_frame.pack(fill="x", pady=(0, 8))

        self.search_button = tk.Button(button_frame, text="Search", width=12, command=self.run_search)
        self.search_button.pack(side="left")

        self.quit_button = tk.Button(button_frame, text="Quit", width=12, command=self.root.destroy)
        self.quit_button.pack(side="left", padx=(8, 0))

        tk.Label(outer, text="Result:").pack(anchor="w")

        self.status_box = scrolledtext.ScrolledText(outer, height=6, wrap="word")
        self.status_box.pack(fill="both", expand=True)
        self.status_box.configure(state="disabled")

        self.root.bind("<Return>", self._on_return)
        self.root.bind("<KP_Enter>", self._on_return)

    def _bind_shortcuts(self) -> None:
        self.search_entry.bind("<Control-a>", self._select_all)
        self.search_entry.bind("<Control-A>", self._select_all)
        self.search_entry.bind("<Control-c>", self._copy_selection)
        self.search_entry.bind("<Control-C>", self._copy_selection)
        self.search_entry.bind("<Control-x>", self._cut_selection)
        self.search_entry.bind("<Control-X>", self._cut_selection)
        self.search_entry.bind("<Control-v>", self._paste_clipboard)
        self.search_entry.bind("<Control-V>", self._paste_clipboard)
        self.search_entry.bind("<Delete>", self._delete_forward)
        self.search_entry.bind("<KP_Delete>", self._delete_forward)

    def _set_status(self, text: str) -> None:
        self.status_box.configure(state="normal")
        self.status_box.delete("1.0", tk.END)
        self.status_box.insert("1.0", text)
        self.status_box.configure(state="disabled")

    def _select_all(self, event: tk.Event) -> str:
        event.widget.selection_range(0, tk.END)
        event.widget.icursor(tk.END)
        return "break"

    def _copy_selection(self, event: tk.Event) -> str:
        try:
            selection = event.widget.selection_get()
        except tk.TclError:
            return "break"

        self.root.clipboard_clear()
        self.root.clipboard_append(selection)
        return "break"

    def _cut_selection(self, event: tk.Event) -> str:
        try:
            selection = event.widget.selection_get()
        except tk.TclError:
            return "break"

        self.root.clipboard_clear()
        self.root.clipboard_append(selection)
        try:
            first = event.widget.index("sel.first")
            last = event.widget.index("sel.last")
            event.widget.delete(first, last)
        except tk.TclError:
            pass
        return "break"

    def _paste_clipboard(self, event: tk.Event) -> str:
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            clipboard_text = ""

        if not clipboard_text:
            return "break"

        try:
            first = event.widget.index("sel.first")
            last = event.widget.index("sel.last")
            event.widget.delete(first, last)
            insert_at = first
        except tk.TclError:
            insert_at = event.widget.index(tk.INSERT)

        event.widget.insert(insert_at, clipboard_text)
        return "break"

    def _delete_forward(self, event: tk.Event) -> str:
        widget = event.widget
        try:
            first = widget.index("sel.first")
            last = widget.index("sel.last")
            widget.delete(first, last)
        except tk.TclError:
            insert_pos = widget.index(tk.INSERT)
            end_pos = widget.index(tk.END)
            if insert_pos != end_pos:
                widget.delete(insert_pos)
        return "break"

    def _on_return(self, _event: tk.Event) -> str:
        self.run_search()
        return "break"

    def run_search(self) -> None:
        raw_term = self.search_var.get().strip()
        if not raw_term:
            self._set_status("enter a search term")
            return

        if not self.db_path.exists():
            messagebox.showerror("Database not found", f"Database file not found:\n{self.db_path}")
            self._set_status("database not found")
            return

        try:
            matches = self._query_database(raw_term)
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", f"SQLite query failed:\n{exc}")
            self._set_status("database error")
            return

        if not matches:
            self._set_status("no results")
            return

        self._set_status("match found")
        blocks = self._format_match_blocks(raw_term, matches)
        self._show_results_window(blocks)

    def _query_database(self, raw_term: str) -> list[MatchRecord]:
        match_sql = """
            SELECT DISTINCT
                a.artist_id,
                a.master_name,
                a.source_row_number
            FROM artists AS a
            INNER JOIN terms AS t
                ON t.artist_id = a.artist_id
            WHERE t.term_text = ? COLLATE NOCASE
            ORDER BY a.master_name COLLATE NOCASE, a.artist_id
        """

        terms_sql = """
            SELECT
                term_text,
                term_type,
                term_order
            FROM terms
            WHERE artist_id = ?
            ORDER BY term_order ASC, term_id ASC
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            self._validate_required_tables(cursor)

            match_rows = cursor.execute(match_sql, (raw_term,)).fetchall()
            matches: list[MatchRecord] = []

            for artist_id, master_name, source_row_number in match_rows:
                term_rows = cursor.execute(terms_sql, (artist_id,)).fetchall()
                associated_terms = [
                    AssociatedTerm(
                        term_text=(term_text or "").strip(),
                        term_type=(term_type or "").strip() or "unspecified",
                        term_order=int(term_order or 0),
                    )
                    for term_text, term_type, term_order in term_rows
                    if (term_text or "").strip()
                ]

                matches.append(
                    MatchRecord(
                        artist_id=int(artist_id),
                        master_name=(master_name or "").strip(),
                        source_row_number=int(source_row_number),
                        associated_terms=associated_terms,
                    )
                )

        return matches

    @staticmethod
    def _validate_required_tables(cursor: sqlite3.Cursor) -> None:
        required_tables = {"artists", "terms"}
        found_rows = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        found_tables = {row[0] for row in found_rows if row and row[0]}
        missing = sorted(required_tables - found_tables)
        if missing:
            raise sqlite3.DatabaseError(
                "missing required table(s): " + ", ".join(missing)
            )

    @staticmethod
    def _format_match_blocks(raw_term: str, matches: list[MatchRecord]) -> list[str]:
        blocks: list[str] = []

        for match in matches:
            term_lines = [
                f"  {term.term_text}  --  {term.term_type}"
                for term in match.associated_terms
            ]

            if not term_lines:
                term_lines = ["  (no associated terms found)"]

            block = (
                f"Master/Prime: {match.master_name}\n"
                f"Search term: {raw_term}\n"
                f"Source row: {match.source_row_number}\n"
                f"Associated terms:\n"
                + "\n".join(term_lines)
            )
            blocks.append(block)

        return blocks

    def _show_results_window(self, blocks: list[str]) -> None:
        if self.results_window is None or not self.results_window.winfo_exists():
            self.results_window = tk.Toplevel(self.root)
            self.results_window.title(RESULTS_WINDOW_TITLE)
            self.results_window.geometry("940x560")
            self.results_window.minsize(680, 360)

            container = tk.Frame(self.results_window, padx=12, pady=12)
            container.pack(fill="both", expand=True)

            tk.Label(container, text="Matches:").pack(anchor="w")

            self.results_text_widget = scrolledtext.ScrolledText(container, wrap="word")
            self.results_text_widget.pack(fill="both", expand=True)
            self.results_text_widget.configure(state="disabled")
        else:
            self.results_window.deiconify()
            self.results_window.lift()
            self.results_window.focus_force()

        if self.results_text_widget is not None:
            self.results_text_widget.configure(state="normal")
            self.results_text_widget.delete("1.0", tk.END)
            self.results_text_widget.insert("1.0", "\n\n".join(blocks))
            self.results_text_widget.configure(state="disabled")


def default_tlohome() -> Path:
    env_value = os.environ.get(TLOHOME_ENV_VAR, "").strip()
    if env_value:
        return Path(env_value).expanduser()
    if getattr(sys, "frozen", False):
        # TLOHome/apps/<platform>/executable
        return Path(sys.executable).resolve().parent.parent.parent
    return Path.cwd()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search TLOHome/TLO_DBs/artists.sqlite.")
    parser.add_argument("--TLOHome", default=None, help="Full path to TLOHome. Overrides the TLOHome environment variable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tlohome = Path(args.TLOHome).expanduser() if args.TLOHome else default_tlohome()
    db_path = tlohome.resolve() / "TLO_DBs" / "artists.sqlite"
    root = tk.Tk()
    ArtistSearchApp(root, db_path)
    root.mainloop()


if __name__ == "__main__":
    main()