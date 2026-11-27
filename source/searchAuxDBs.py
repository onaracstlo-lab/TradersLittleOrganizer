#!/usr/bin/env python3
"""Read-only lookup of artist, city and venue names/aliases in TLOHome/TLO_DBs."""

from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
import os
import sqlite3
import sys
import tkinter as tk
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox
from tkinter import scrolledtext

from tlo_gui_shortcuts import install_global_ctrl_a
from match_city import normalize as city_key
from tlo_venue_matcher import key as venue_key
from tlo_msi_install_mode import saved_msi_data_home_for_executable

try:
    from tlo_version import DISPLAY_VERSION
except ImportError:
    DISPLAY_VERSION = "version unavailable"

TLOHOME_ENV_VAR = "TLOHome"
WINDOW_TITLE = f"TLO Auxiliary Database Search - {DISPLAY_VERSION}"
DATABASES = {"Artist": "artists.sqlite", "City": "cities.sqlite", "Venue": "venues.sqlite"}


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


class AuxiliarySearchApp:
    def __init__(self, root: tk.Tk, db_dir: Path, database: str = "Artist", initial_find: str | None = None) -> None:
        self.root = root
        install_global_ctrl_a(self.root)
        self.db_dir = db_dir
        self.database_var = tk.StringVar(value=database)
        self.root.title(WINDOW_TITLE)
        self.root.geometry("820x320")
        self.root.minsize(620, 240)

        self.search_var = tk.StringVar()
        self.results_window: tk.Toplevel | None = None
        self.results_text_widget: scrolledtext.ScrolledText | None = None

        self._build_ui()
        self._bind_shortcuts()
        self.search_entry.focus_set()
        if initial_find is None:
            try:
                initial_find = root.clipboard_get()
            except tk.TclError:
                initial_find = ""
        if initial_find.strip():
            self.search_var.set(initial_find.strip())
            root.after_idle(self.run_search)

    @property
    def db_path(self) -> Path:
        return self.db_dir / DATABASES[self.database_var.get()]

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

        choice_frame = tk.Frame(outer)
        choice_frame.pack(fill="x", pady=(0, 8))
        # One shared variable: selecting another checkbox clears the previous
        # one; clicking the selected checkbox cannot leave no database selected.
        for label in DATABASES:
            tk.Checkbutton(choice_frame, text=label, variable=self.database_var,
                           onvalue=label, offvalue=label).pack(side="left", padx=(0, 12))

        button_frame = tk.Frame(outer)
        button_frame.pack(fill="x", pady=(0, 8))

        self.search_button = tk.Button(button_frame, text="Search", width=12, anchor="center", justify="center", command=self.run_search)
        self.search_button.pack(side="left")

        self.quit_button = tk.Button(button_frame, text="Quit", width=12, anchor="center", justify="center", command=self.root.destroy)
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

        if self.results_window is not None and self.results_window.winfo_exists():
            self.results_window.destroy()
            self.results_window = None
            self.results_text_widget = None

        if not self.db_path.is_file():
            messagebox.showerror("Database not found", f"Database file not found:\n{self.db_path}")
            self._set_status("database not found")
            return

        try:
            database = self.database_var.get()
            if database == "Artist":
                blocks = self._format_match_blocks(raw_term, self._query_database(raw_term))
            else:
                blocks = query_places(self.db_path, database, raw_term)
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", f"SQLite query failed:\n{exc}")
            self._set_status("database error")
            return

        if not blocks:
            self._set_status("no results")
            return

        self._set_status("match found")
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

        with closing(read_only_database(self.db_path)) as conn:
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
            self.results_window.title(f"{self.database_var.get()} DB Matches")
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


def read_only_database(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def query_places(path: Path, database: str, term: str) -> list[str]:
    """List all exact normalized master/alias matches, not an arbitrary winner."""
    blocks = []
    with closing(read_only_database(path)) as conn:
        if database == "City":
            name, _, region = term.partition(",")
            lookup = city_key(name)
            if not lookup:
                return []
            rows = conn.execute(
                """SELECT DISTINCT c.city_id, c.canonical_city, c.region
                   FROM cities c JOIN city_names n ON n.city_id = c.city_id
                   WHERE n.name_norm = ? AND (? = '' OR EXISTS (
                       SELECT 1 FROM region_names r WHERE r.city_id = c.city_id
                       AND r.region_norm = ?))
                   ORDER BY c.canonical_city, c.region""",
                (lookup, city_key(region), city_key(region)),
            )
            for city_id, city, geo in rows:
                names = conn.execute("SELECT name, is_canonical FROM city_names WHERE city_id = ? ORDER BY is_canonical DESC, name", (city_id,))
                aliases = "\n".join(f"  {name} -- {'master' if master else 'alias'}" for name, master in names)
                regions = ", ".join(row[0] for row in conn.execute(
                    "SELECT region_name FROM region_names WHERE city_id = ? ORDER BY is_canonical DESC, region_name", (city_id,)))
                blocks.append(f"Master: {city}, {geo}\nSearch term: {term}\nAssociated names:\n{aliases}\nRegion names: {regions}")
        elif database == "Venue":
            lookup = venue_key(term)
            if not lookup:
                return []
            rows = conn.execute(
                """SELECT DISTINCT display_name, anchor FROM names
                   WHERE normalized_key = ? ORDER BY display_name, anchor""", (lookup,))
            for display, anchor in rows:
                terms = conn.execute(
                    """SELECT DISTINCT spelling, strength, kind, institution
                       FROM names WHERE display_name = ? AND anchor = ?
                       ORDER BY spelling, strength, kind, institution""", (display, anchor))
                details = "\n".join(f"  {name} -- {strength}; {kind}" + (f"; institution: {institution}" if institution else "")
                                    for name, strength, kind, institution in terms)
                locations = conn.execute("SELECT DISTINCT city_key, state_key FROM locations WHERE display_name = ? ORDER BY city_key, state_key", (display,))
                geography = ", ".join(" / ".join(filter(None, row)) for row in locations)
                blocks.append(f"Venue: {display}\nSearch term: {term}\nAnchor: {anchor}\nAssociated spellings:\n{details}" +
                              (f"\nLocation keys: {geography}" if geography else ""))
        else:
            raise ValueError(f"Unsupported place database: {database}")
    return blocks


def default_tlohome() -> Path:
    env_value = os.environ.get(TLOHOME_ENV_VAR, "").strip()
    if env_value:
        return Path(env_value).expanduser()
    saved = saved_msi_data_home_for_executable()
    if saved:
        return Path(saved)
    if getattr(sys, "frozen", False):
        # Portable executable or macOS .app bundle.
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.name == "apps":
                return parent.parent
        return executable.parent
    return Path.cwd()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search TLOHome/TLO_DBs auxiliary databases.")
    parser.add_argument("--TLOHome", default=None, help="Full path to TLOHome. Overrides the TLOHome environment variable.")
    parser.add_argument("--database", choices=DATABASES, default="Artist")
    parser.add_argument("--find", default=None, help="Initial search term; defaults to clipboard.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tlohome = Path(args.TLOHome).expanduser() if args.TLOHome else default_tlohome()
    db_dir = tlohome.resolve() / "TLO_DBs"
    root = tk.Tk()
    AuxiliarySearchApp(root, db_dir, args.database, args.find)
    root.mainloop()


if __name__ == "__main__":
    main()
