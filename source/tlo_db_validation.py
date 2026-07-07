__version__ = "v321"
# TLO-GI package version: v321
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
import os
import sqlite3
from typing import Tuple


class DatabaseAccessError(RuntimeError):
    pass


REQUIRED_SQLITE_TABLES = {
    "artists": ("artist_id", "source_row_number", "master_name"),
    "aliases": ("alias_id", "artist_id", "alias_text", "alias_order"),
    "terms": ("term_id", "artist_id", "term_text", "term_type", "term_order"),
}


def _require_path(config, attr_name: str, label: str) -> str:
    path = getattr(config, attr_name, "")
    if not path:
        raise DatabaseAccessError(f"{label} path is not configured ({attr_name}).")
    return path


def ensure_readable_file(path: str, label: str) -> str:
    if not os.path.exists(path):
        raise DatabaseAccessError(f"{label} not found: {path}")
    if not os.path.isfile(path):
        raise DatabaseAccessError(f"{label} path is not a file: {path}")
    if not os.access(path, os.R_OK):
        raise DatabaseAccessError(f"{label} is not readable: {path}")
    return path


def validate_artist_sqlite(config) -> str:
    path = ensure_readable_file(_require_path(config, "artist_sqlite_db_file", "Artist database"), "Artist database")
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error as exc:
        raise DatabaseAccessError(f"Unable to open artist database: {path} | {exc}") from exc

    try:
        cur = conn.cursor()
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table_name, required_columns in REQUIRED_SQLITE_TABLES.items():
            if table_name not in tables:
                raise DatabaseAccessError(f"Artist database is missing required table '{table_name}': {path}")
            cols = {row[1] for row in cur.execute(f"PRAGMA table_info({table_name})")}
            for col in required_columns:
                if col not in cols:
                    raise DatabaseAccessError(
                        f"Artist database table '{table_name}' is missing required column '{col}': {path}"
                    )

        artist_row = cur.execute("SELECT COUNT(*) FROM artists").fetchone()
        alias_row = cur.execute("SELECT COUNT(*) FROM aliases").fetchone()
        term_row = cur.execute("SELECT COUNT(*) FROM terms").fetchone()
        if not artist_row or int(artist_row[0]) <= 0:
            raise DatabaseAccessError(f"Artist database loaded but no artist records were found: {path}")
        if not alias_row or int(alias_row[0]) <= 0:
            raise DatabaseAccessError(f"Artist database loaded but no alias records were found: {path}")
        if not term_row or int(term_row[0]) <= 0:
            raise DatabaseAccessError(f"Artist database loaded but no term records were found: {path}")
    except sqlite3.Error as exc:
        raise DatabaseAccessError(f"Artist database query failed: {path} | {exc}") from exc
    finally:
        conn.close()

    return path


def validate_venue_reference(config) -> str:
    path = ensure_readable_file(_require_path(config, "venue_reference_db_file", "Venue database"), "Venue database")
    try:
        with open(path, "r", encoding="utf-8") as infile:
            count = sum(1 for line in infile if line.strip() and not line.lstrip().startswith("#"))
    except OSError as exc:
        raise DatabaseAccessError(f"Unable to read venue database: {path} | {exc}") from exc

    if count <= 0:
        raise DatabaseAccessError(f"Venue database loaded but no venue records were found: {path}")
    return path


def validate_required_databases(config) -> Tuple[str, str]:
    return validate_artist_sqlite(config), validate_venue_reference(config)
