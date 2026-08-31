"""Append one human-readable settings entry for every TLO action that starts."""

from __future__ import annotations

__version__ = "v423"

import os
import threading
from datetime import datetime
from typing import Iterable, Optional

from logging_lib import ensure_logs_dir


RUN_SETTINGS_LOG_FILENAME = "runSettings.log"
_RUN_SETTINGS_LOCK = threading.RLock()


def run_settings_log_path(tlo_home: str) -> str:
    """Return the single run-settings log path for a TLOHome."""
    home = os.path.normpath(str(tlo_home or "").strip())
    if not home:
        raise ValueError("TLOHome is blank; run settings cannot be logged.")
    return os.path.join(ensure_logs_dir(home), RUN_SETTINGS_LOG_FILENAME)


def _timestamp_parts(started_at: Optional[datetime] = None) -> tuple[str, str]:
    value = started_at or datetime.now().astimezone()
    if value.tzinfo is None:
        value = value.astimezone()
    date_text = value.strftime("%Y-%m-%d")
    time_text = value.strftime("%I:%M:%S %p %Z").lstrip("0").strip()
    return date_text, time_text


def format_run_settings_entry(
    action: str,
    review_lines: Iterable[object],
    *,
    started_at: Optional[datetime] = None,
) -> str:
    """Format one entry using the same lines shown by Review Operation."""
    action_text = str(action or "Operation").strip() or "Operation"
    date_text, time_text = _timestamp_parts(started_at)
    lines = [f"Action: {action_text} | Date: {date_text} | Time: {time_text}"]
    lines.extend(str(line).rstrip("\r\n") for line in (review_lines or []))
    return "\n".join(lines).rstrip() + "\n\n"


def append_run_settings(
    tlo_home: str,
    action: str,
    review_lines: Iterable[object],
    *,
    started_at: Optional[datetime] = None,
) -> str:
    """Append one complete run entry and return the log path.

    The entry is assembled in memory and written with one append operation so
    concurrent command-line starts cannot interleave individual lines.
    """
    path_name = run_settings_log_path(tlo_home)
    entry = format_run_settings_entry(action, review_lines, started_at=started_at)
    with _RUN_SETTINGS_LOCK:
        with open(path_name, "a", encoding="utf-8", newline="\n") as outfile:
            outfile.write(entry)
            outfile.flush()
    return path_name
