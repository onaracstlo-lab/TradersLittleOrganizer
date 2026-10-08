from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import os
import sys
from pathlib import Path


_FFMPEG_DIRNAME = "tlo_ffmpeg_bin"
_FFMPEG_BASENAME = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _path_is_within(path_name: str, root_name: str) -> bool:
    """Return True when path_name resolves inside root_name (or equals it)."""
    try:
        path = os.path.realpath(os.path.abspath(path_name))
        root = os.path.realpath(os.path.abspath(root_name))
        common = os.path.commonpath([path, root])
        return os.path.normcase(common) == os.path.normcase(root)
    except (OSError, ValueError, TypeError):
        return False


def _candidate_roots() -> list[str]:
    roots: list[str] = []
    if bool(getattr(sys, "frozen", False)):
        meipass = str(getattr(sys, "_MEIPASS", "") or "").strip()
        executable = str(getattr(sys, "executable", "") or "").strip()
        if meipass:
            roots.append(meipass)
        if executable:
            roots.append(os.path.dirname(executable))
    else:
        roots.append(str(Path(__file__).resolve().parent))

    unique: list[str] = []
    seen: set[str] = set()
    for root in roots:
        normalized = os.path.normcase(os.path.realpath(os.path.abspath(root)))
        if normalized not in seen:
            seen.add(normalized)
            unique.append(root)
    return unique


def bundled_ffmpeg_executable() -> str:
    """Return only TLO's prepared and packaged native ffmpeg executable.

    Build 535 removes imageio-ffmpeg from runtime resolution.  The build
    scripts fetch one exact, checksum-pinned ffmpeg binary into
    ``tlo_ffmpeg_bin`` and PyInstaller carries that directory into the app.
    No environment variable, PATH, conda, current-directory, or package helper
    fallback is accepted.
    """
    try:
        for root in _candidate_roots():
            root_real = os.path.realpath(root)
            candidate = os.path.realpath(os.path.join(root, _FFMPEG_DIRNAME, _FFMPEG_BASENAME))
            if not _path_is_within(candidate, root_real):
                continue
            if not os.path.isfile(candidate):
                continue
            if os.name != "nt" and not os.access(candidate, os.X_OK):
                continue
            return candidate
    except Exception:
        pass
    return ""
