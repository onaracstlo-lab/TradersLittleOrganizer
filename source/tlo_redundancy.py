"""Persistent ordered redundancy/equivalent-volume groups for TLO."""

from __future__ import annotations

__version__ = "v490"

import os
import re
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from tlo_bootlist_volume_policy import normalize_volume_label, volume_key
from tlo_volume_label import resolve_volume_label

REDUNDANCY_FILENAME = "redundancyGroups.txt"
_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


class RedundancyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RedundancyGroup:
    members: Tuple[str, ...]

    @property
    def display(self) -> str:
        return " = ".join(self.members)


def redundancy_path(tlo_home: str) -> str:
    return os.path.join(os.path.abspath(tlo_home), REDUNDANCY_FILENAME)


def _is_comment_line(line_text: str) -> bool:
    cleaned = str(line_text or "").lstrip("\ufeff").strip()
    lowered = cleaned.casefold()
    return cleaned.startswith("#") or lowered == "rem" or lowered.startswith("rem ")


def _strip_optional_quotes(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _looks_like_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(
        os.path.isabs(text)
        or _WINDOWS_PATH_RE.match(text)
        or text.startswith("/mnt/")
        or text.startswith("/Volumes/")
        or text.startswith("\\\\")
        or text.startswith("//")
    )


def _member_to_label(value: str) -> str:
    """Resolve an entered member to a visible volume label.

    Members may be visible labels or currently accessible root/folder paths.
    Paths never require quotes: '=' is the declaration separator, so spaces are
    ordinary characters.  A path must be accessible when saved because the
    persistent declaration stores the resolved volume label, not a mount path.
    """
    text = _strip_optional_quotes(value)
    if not text:
        raise RedundancyError("Redundancy group members cannot be blank.")
    if _looks_like_path(text):
        if not os.path.exists(text):
            raise RedundancyError(
                f"Redundancy group path is not currently accessible, so its volume label cannot be resolved: {text}"
            )
        try:
            label = normalize_volume_label(resolve_volume_label(text).label)
        except Exception as exc:
            raise RedundancyError(f"Cannot resolve a volume label for redundancy path: {text}: {exc}") from exc
        if not label:
            raise RedundancyError(
                f"Redundancy group path has no usable visible volume label: {text}. Enter the volume label directly instead."
            )
        return label
    label = normalize_volume_label(text)
    if not label:
        raise RedundancyError("Blank volume labels cannot be members of a redundancy group.")
    if "[" in label or "]" in label:
        raise RedundancyError(f"Invalid redundancy volume label: {text}")
    return label


def parse_redundancy_text(text: str) -> List[RedundancyGroup]:
    groups: List[RedundancyGroup] = []
    seen_members: Dict[str, int] = {}
    for line_number, raw in enumerate(str(text or "").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or _is_comment_line(raw):
            continue
        pieces = [part.strip() for part in stripped.split("=")]
        if len(pieces) < 2 or any(not part for part in pieces):
            raise RedundancyError(
                f"Line {line_number}: use A = B = C with at least two nonblank members."
            )
        labels = tuple(_member_to_label(piece) for piece in pieces)
        keys = [volume_key(label) for label in labels]
        if len(set(keys)) != len(keys):
            raise RedundancyError(f"Line {line_number}: the same volume appears more than once in this group.")
        for label, key in zip(labels, keys):
            if key in seen_members:
                raise RedundancyError(
                    f"Line {line_number}: volume '{label}' already appears in redundancy group line {seen_members[key]}."
                )
            seen_members[key] = line_number
        groups.append(RedundancyGroup(labels))
    return groups


def load_redundancy_groups(tlo_home: str) -> List[RedundancyGroup]:
    path_name = redundancy_path(tlo_home)
    if not os.path.isfile(path_name):
        return []
    try:
        if os.path.getsize(path_name) > 1024 * 1024:
            raise RedundancyError(f"Redundancy group file is unexpectedly large: {path_name}")
        with open(path_name, "r", encoding="utf-8-sig", errors="strict") as infile:
            return parse_redundancy_text(infile.read())
    except UnicodeDecodeError as exc:
        raise RedundancyError(f"Redundancy group file must be UTF-8 text: {path_name}") from exc
    except OSError as exc:
        raise RedundancyError(f"Cannot read redundancy group file: {path_name}: {exc}") from exc


def canonical_redundancy_text(groups: Sequence[RedundancyGroup]) -> str:
    if not groups:
        return ""
    return "\n".join(group.display for group in groups) + "\n"


def save_redundancy_text(tlo_home: str, text: str) -> List[RedundancyGroup]:
    groups = parse_redundancy_text(text)
    path_name = redundancy_path(tlo_home)
    os.makedirs(os.path.dirname(path_name) or ".", exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".redundancy-groups-", suffix=".tmp", dir=os.path.dirname(path_name) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as outfile:
            outfile.write(canonical_redundancy_text(groups))
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temp_name, path_name)
    except Exception:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise
    return groups


def ordered_equivalents(volume_label: str, groups: Sequence[RedundancyGroup]) -> Tuple[str, ...]:
    """Return equivalent labels in declaration precedence order."""
    label = normalize_volume_label(volume_label)
    key = volume_key(label)
    for group in groups:
        if any(volume_key(member) == key for member in group.members):
            return group.members
    return (label,)


def group_for_volume(volume_label: str, groups: Sequence[RedundancyGroup]) -> RedundancyGroup | None:
    key = volume_key(volume_label)
    for group in groups:
        if any(volume_key(member) == key for member in group.members):
            return group
    return None


def group_display_for_volume(volume_label: str, groups: Sequence[RedundancyGroup]) -> str:
    group = group_for_volume(volume_label, groups)
    return group.display if group is not None else normalize_volume_label(volume_label)


def preferred_connected_member(
    volume_label: str,
    roots: Mapping[str, Sequence[str]],
    groups: Sequence[RedundancyGroup],
) -> str:
    for member in ordered_equivalents(volume_label, groups):
        if roots.get(volume_key(member)):
            return member
    return ""
