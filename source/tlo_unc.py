"""Canonical Windows UNC share identity and safe path handling.

A network share is a storage root, not a physical disk/volume label. The
canonical identity ``UNC:server/share`` is recorded in existing Volume fields
without introducing a new bootlist.csv column. Credentials are never recorded.
"""
from __future__ import annotations

import ntpath
import re

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

_UNC_RE = re.compile(r"^\\\\(?P<server>[^\\/]+)\\(?P<share>[^\\/]+)(?P<tail>(?:\\.*)?)$")
_UNC_ID_RE = re.compile(r"^UNC:(?P<server>[^/\\:]+)[/](?P<share>[^/\\:]+)$", re.IGNORECASE)


def unc_parts(value: str) -> tuple[str, str, str] | None:
    """Parse true UNC shares; refuse device namespaces, partial roots and URL paths."""
    text = str(value or "").strip().replace("/", "\\")
    if not text.startswith("\\\\"):
        return None
    match = _UNC_RE.fullmatch(text)
    if not match:
        return None
    server, share, tail = match.group("server", "share", "tail")
    if server in {".", "?", ".."} or share in {".", ".."} or server.startswith("?"):
        return None
    if ":" in server or ":" in share or any(ord(ch) < 32 for ch in text):
        return None
    return server, share, tail


def is_unc_path(path: str) -> bool:
    return unc_parts(path) is not None


def unc_root(path: str) -> str:
    parts = unc_parts(path)
    return f"\\\\{parts[0]}\\{parts[1]}" if parts else ""


def unc_label(path: str) -> str:
    parts = unc_parts(path)
    return f"UNC:{parts[0].casefold()}/{parts[1].casefold()}" if parts else ""


def root_from_unc_label(label: str) -> str:
    match = _UNC_ID_RE.fullmatch(str(label or "").strip())
    if not match:
        return ""
    server, share = match.group("server", "share")
    return unc_root(f"\\\\{server}\\{share}")


def share_relative_path(path: str) -> str:
    parts = unc_parts(path)
    if not parts:
        return ""
    tail = ntpath.normpath(parts[2] or "\\").replace("\\", "/")
    if tail in ("", "."):
        return "/"
    return "/" + tail.lstrip("/")


def compose_unc_path(label: str, stored: str) -> str:
    """Reconstruct the true share path, never allow traversal outside its root."""
    root = root_from_unc_label(label)
    if not root:
        return ""
    source_subpath = str(stored or "")
    if any(part == ".." for part in re.split(r"[\\/]+", source_subpath)) or "\x00" in source_subpath:
        return ""
    subpath = source_subpath.replace("/", "\\").lstrip("\\")
    candidate = ntpath.normpath(ntpath.join(root, subpath)) if subpath else root
    if unc_root(candidate).casefold() != root.casefold():
        return ""
    # Legacy rows sometimes stored a fully qualified UNC path instead of a
    # share-relative suffix. Do not duplicate or cross the named share.
    return candidate
