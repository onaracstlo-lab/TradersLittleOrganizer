"""Path and TLOHome input normalization shared by CLI, GUI, and tagging entry points."""

__version__ = "v325"
# TLO-GI package version: v325
__version_summary__ = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
# TLO-GI version summary: Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.

import argparse
import os
import re
from urllib.parse import unquote, urlparse


def strip_optional_quotes(text):
    """Return text without one matching pair of wrapping single/double quotes."""
    text = str(text or "").strip()
    if len(text) >= 2:
        if text[0] == '"' and text[-1] == '"':
            return text[1:-1]
        if text[0] == "'" and text[-1] == "'":
            return text[1:-1]
    return text


# Backward-compatible alias for older imports/tests.
def _strip_optional_quotes(text):
    return strip_optional_quotes(text)



_WINDOWS_DRIVE_ABS_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")


def _file_uri_to_path(text: str) -> str:
    cleaned = _strip_optional_quotes(text).strip()
    if not cleaned.lower().startswith("file:"):
        return cleaned
    parsed = urlparse(cleaned)
    path = unquote(parsed.path or "")
    # Windows file URIs normally arrive as /P:/tagtest.
    if re.match(r"^/[A-Za-z]:/", path):
        path = path[1:]
    return path or cleaned


def windows_drive_path_to_wsl_path(path: str) -> str:
    """Translate a Windows drive-rooted path (P:\\dir or P:/dir) to /mnt/p/dir."""
    cleaned = _file_uri_to_path(path)
    match = _WINDOWS_DRIVE_ABS_RE.match(cleaned)
    if not match:
        return cleaned
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/").lstrip("/")
    return os.path.normpath(f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}")


def normalize_platform_input_path(path: str) -> str:
    """Normalize a user-supplied path for the current runtime.

    Native Windows keeps Windows paths native.  WSL/Linux accepts Windows
    drive-rooted paths as convenience input and maps them to /mnt/<drive>/...
    before normal absolute-path validation.
    """
    cleaned = _file_uri_to_path(path)
    if os.name != "nt":
        cleaned = windows_drive_path_to_wsl_path(cleaned)
    return os.path.normpath(cleaned)


def tlo_home_type(path):
    path = _strip_optional_quotes(path)
    if not os.path.isabs(path):
        raise argparse.ArgumentTypeError(f"TLOHome must be a fully qualified directory path: {path}")
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"TLOHome directory does not exist: {path}")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"TLOHome exists but is not a directory: {path}")
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"TLOHome directory is not writable: {path}")
    return path


def resolve_tlo_home(tlo_home: str = "", my_tlo: str = "", *, error_type=ValueError) -> str:
    """Resolve TLOHome with unchanged precedence: myTLO -> TLOHome -> env."""
    env_tlo_home = _strip_optional_quotes(os.environ.get("TLOHome", ""))
    resolved = _strip_optional_quotes(my_tlo).strip() or _strip_optional_quotes(tlo_home).strip() or env_tlo_home
    if not resolved:
        raise error_type("TLOHome must be supplied with --TLOHome, --myTLO, or the TLOHome environment variable.")
    try:
        return os.path.normpath(tlo_home_type(resolved))
    except argparse.ArgumentTypeError as exc:
        raise error_type(str(exc)) from exc


def resolve_current_storage_volume(cli_value=None) -> str:
    """Resolve the Add to Inventory storage/volume default.

    Command line --current-storage-volume wins over the TLOCurrentStorage
    environment variable. Empty or missing values return an empty string.
    """
    if cli_value is not None:
        return _strip_optional_quotes(str(cli_value)).strip()
    return _strip_optional_quotes(os.environ.get("TLOCurrentStorage", "")).strip()
