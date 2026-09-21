"""Application-level safety helpers for untrusted collection metadata and paths."""
from __future__ import annotations

__version__ = "v482"

import os
import re

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029]")
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_WINDOWS_DEVICE_RE = re.compile(r"(?i)^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$")


def escape_structured_log_text(value) -> str:
    """Encode control characters so one untrusted value cannot create log records/keys."""
    text = str(value or "")
    return _CONTROL_RE.sub(lambda m: f"\\u{ord(m.group(0)):04x}", text)


def csv_formula_escape(value) -> str:
    """Serialize an Excel-facing CSV cell without allowing formula interpretation."""
    text = str(value or "")
    if text.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


def csv_formula_unescape(value) -> str:
    """Reverse only the apostrophe TLO adds for a spreadsheet-dangerous leading character."""
    text = str(value or "")
    if len(text) >= 2 and text[0] == "'" and text[1:].startswith(_CSV_FORMULA_PREFIXES):
        return text[1:]
    return text


def is_network_or_device_path(path_name: str) -> bool:
    """Return True for UNC/device paths that TLO must not launch/read as local files."""
    text = str(path_name or "").strip().replace("/", "\\")
    lowered = text.casefold()
    return (
        lowered.startswith("\\\\")
        or lowered.startswith("\\\\?\\")
        or lowered.startswith("\\\\.\\")
    )


def is_protected_pseudo_path(path_name: str) -> bool:
    """Block Linux pseudo-filesystems from persistent-log initiated reads."""
    try:
        resolved = os.path.realpath(os.path.abspath(path_name))
    except Exception:
        return True
    for root in ("/proc", "/dev", "/sys"):
        if resolved == root or resolved.startswith(root + os.sep):
            return True
    return False


def is_path_within(path_name: str, root: str) -> bool:
    try:
        path_real = os.path.realpath(os.path.abspath(path_name))
        root_real = os.path.realpath(os.path.abspath(root))
        return os.path.commonpath([path_real, root_real]) == root_real
    except (OSError, ValueError):
        return False


def is_safe_local_regular_file(path_name: str, allowed_roots=()) -> bool:
    """Require a local, non-symlink regular file under at least one allowed root."""
    text = str(path_name or "").strip()
    if not text or is_network_or_device_path(text) or is_protected_pseudo_path(text):
        return False
    if os.path.islink(text) or not os.path.isfile(text):
        return False
    roots = [str(root or "").strip() for root in allowed_roots if str(root or "").strip()]
    return bool(roots) and any(is_path_within(text, root) for root in roots)


def windows_reserved_folder_name(name: str) -> bool:
    """Return True when a leaf would be a reserved Windows DOS device name."""
    leaf = str(name or "").strip(" .")
    return bool(leaf and _WINDOWS_DEVICE_RE.fullmatch(leaf))
