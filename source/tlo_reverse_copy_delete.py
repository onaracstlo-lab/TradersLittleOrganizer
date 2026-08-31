"""Reverse a successful Full Inventory Copy/Delete + Rename Compliantly transfer.

The forward operation writes exact source -> destination mappings to the active
TLOHome/logs/tagsN.txt file.  Reversal first identifies one applicable success
log, then uses only the exact mappings from that log to restore folder location
and name without changing audio tags.
"""

from __future__ import annotations

__version__ = "v421"

from dataclasses import dataclass
from datetime import datetime
import os
import re
import shutil
import string
import sys
import unicodedata
import uuid
from typing import Callable, Iterable, List, Optional, Sequence

from logging_lib import ensure_logs_dir
from tlo_file_listing import scandir_matching_files
from tlo_bootlist_volume_policy import normalize_volume_label, parse_volume_path_value
from tlo_path_inputs import normalize_platform_input_path, resolve_tlo_home, strip_optional_quotes
from tlo_volume_label import resolve_volume_label
from tlo_tree_compare import directory_trees_exactly_match


_REVERSE_RECORD_RE = re.compile(
    r"^TAG_COPY_DELETE_(?P<kind>MOVE|COPY):\s+(?P<source>.+?)\s+->\s+(?P<destination>.+?)\s*$",
    re.IGNORECASE,
)
_COMBINED_MODE_RE = re.compile(
    r"^TAG_DURING_INVENTORY:\s*mode=copy-and-delete\b.*\brename compliantly=yes\b",
    re.IGNORECASE,
)
_COPY_DESTINATION_RE = re.compile(r"\bcopy destination=(?P<destination>.*)$", re.IGNORECASE)
_WINDOWS_DRIVE_ONLY_RE = re.compile(r"^[A-Za-z]:?$")
_WSL_DRIVE_PATH_RE = re.compile(r"^/mnt/([A-Za-z])(?:/|$)")
_FULL_DATE_RE = re.compile(r"(?<!\d)(?P<year>(?:19|20)\d{2}|xxxx)-(?P<month>\d{2}|xx)-(?P<day>\d{2}|xx)(?!\d)", re.IGNORECASE)
_SHORT_DATE_RE = re.compile(r"(?<!\d)(?P<month>\d{1,2})[-/.](?P<day>\d{1,2})[-/.](?P<year>\d{2})(?!\d)")


class ReverseCopyDeleteError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReverseRecord:
    log_path: str
    transfer_kind: str
    original_path: str
    current_path: str
    logged_original_path: str = ""
    logged_current_path: str = ""
    logged_copy_destination: str = ""


@dataclass(frozen=True)
class _OriginalInput:
    text: str
    base_path: str
    volume_root: str
    requested_label: str
    is_path: bool
    is_volume_root: bool


@dataclass(frozen=True)
class _ReverseLogCandidate:
    log_path: str
    search_path_values: tuple[str, ...]
    records: tuple[ReverseRecord, ...]


@dataclass(frozen=True)
class ReverseSelection:
    tlo_home: str
    original_input: str
    original_root: str
    moved_root: str
    log_path: str
    records: tuple[ReverseRecord, ...]
    evidence: str = ""


@dataclass
class ReverseResult:
    discovered: int = 0
    restored: int = 0
    already_restored: int = 0
    skipped_unmatched: int = 0
    missing: int = 0  # retained for compatibility with older callers/status displays
    conflicts: int = 0
    errors: int = 0
    messages: List[str] | None = None

    def __post_init__(self) -> None:
        if self.messages is None:
            self.messages = []


def _running_on_wsl() -> bool:
    if os.name == "nt":
        return False
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as infile:
            text = infile.read().casefold()
        return "microsoft" in text or "wsl" in text
    except OSError:
        return False


def _looks_like_root_input(value: str) -> bool:
    text = strip_optional_quotes(value).strip()
    if _WINDOWS_DRIVE_ONLY_RE.fullmatch(text):
        return True
    try:
        return os.path.isabs(normalize_platform_input_path(text))
    except Exception:
        return False


def _mounted_candidate_roots() -> List[str]:
    roots: List[str] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.isdir(root):
                roots.append(root)
    elif _running_on_wsl():
        for letter in string.ascii_lowercase:
            root = f"/mnt/{letter}"
            if os.path.isdir(root):
                roots.append(root)
    elif sys.platform == "darwin":
        if os.path.isdir("/"):
            roots.append("/")
        volumes = "/Volumes"
        if os.path.isdir(volumes):
            for name in sorted(os.listdir(volumes)):
                root = os.path.join(volumes, name)
                if os.path.isdir(root):
                    roots.append(root)
    else:
        roots.append("/")
        for base in ("/mnt", "/media", "/run/media"):
            if not os.path.isdir(base):
                continue
            for current, dir_names, _file_names in os.walk(base):
                depth = os.path.relpath(current, base).count(os.sep)
                if current == base:
                    depth = -1
                if depth >= 2:
                    dir_names[:] = []
                    continue
                roots.append(current)
    deduped: List[str] = []
    seen = set()
    for root in roots:
        normalized = os.path.normpath(root)
        key = os.path.normcase(normalized)
        if key in seen or not os.path.isdir(normalized):
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _mounted_roots_for_label(volume_label: str) -> List[str]:
    wanted = normalize_volume_label(volume_label).casefold()
    if not wanted:
        return []
    matches: List[str] = []
    for candidate in _mounted_candidate_roots():
        try:
            info = resolve_volume_label(candidate)
            label = normalize_volume_label(info.label)
        except Exception:
            continue
        if label.casefold() != wanted:
            continue
        root = os.path.normpath(info.volume_key or candidate)
        if os.path.isdir(root) and root not in matches:
            matches.append(root)
    return matches


def _normalize_user_root(value: str, *, label: str) -> str:
    text = strip_optional_quotes(value).strip()
    if not text:
        raise ReverseCopyDeleteError(f"{label} is required.")
    if _WINDOWS_DRIVE_ONLY_RE.fullmatch(text):
        if not text.endswith(":"):
            text += ":"
        text += "/"
    normalized = os.path.normpath(normalize_platform_input_path(text))
    if not os.path.isabs(normalized):
        raise ReverseCopyDeleteError(f"{label} must be a fully qualified drive/root path: {value}")
    if not os.path.isdir(normalized):
        raise ReverseCopyDeleteError(f"{label} does not exist or is not a directory: {normalized}")
    return normalized


def _path_key(path_name: str) -> str:
    return os.path.normcase(os.path.normpath(path_name))


def _same_or_under(path_name: str, root: str) -> bool:
    try:
        normalized_path = os.path.normpath(path_name)
        normalized_root = os.path.normpath(root)
        return os.path.commonpath([normalized_path, normalized_root]) == normalized_root
    except (ValueError, OSError):
        return False


def _normalize_logged_path(path_name: str) -> str:
    return os.path.normpath(normalize_platform_input_path(strip_optional_quotes(path_name).strip()))


def _logged_volume_root(path_name: str) -> str:
    path_name = os.path.normpath(path_name)
    if os.name == "nt":
        drive, _tail = os.path.splitdrive(path_name)
        if drive:
            return os.path.normpath(drive + os.sep)
        return ""

    match = _WSL_DRIVE_PATH_RE.match(path_name.replace("\\", "/"))
    if match:
        return os.path.normpath(f"/mnt/{match.group(1).lower()}")

    normalized = path_name.replace("\\", "/")
    patterns = (
        r"^(/Volumes/[^/]+)(?:/|$)",
        r"^(/run/media/[^/]+/[^/]+)(?:/|$)",
        r"^(/media/[^/]+/[^/]+)(?:/|$)",
        r"^(/mnt/[^/]+)(?:/|$)",
    )
    for pattern in patterns:
        found = re.match(pattern, normalized)
        if found:
            return os.path.normpath(found.group(1))
    return ""


def _current_volume_root(path_name: str) -> str:
    root = _logged_volume_root(path_name)
    if root:
        return root
    if os.path.normpath(path_name) == os.path.normpath(os.path.abspath(os.sep)):
        return os.path.normpath(os.path.abspath(os.sep))
    return ""


def _resolve_original_input(value: str) -> _OriginalInput:
    text = strip_optional_quotes(value).strip()
    if not text:
        raise ReverseCopyDeleteError("Original partition/path is required.")

    if _looks_like_root_input(text):
        base = _normalize_user_root(text, label="Original partition/path")
        volume_root = _current_volume_root(base)
        is_volume_root = bool(volume_root and _path_key(volume_root) == _path_key(base))
        return _OriginalInput(
            text=text,
            base_path=base,
            volume_root=volume_root or base,
            requested_label="",
            is_path=True,
            is_volume_root=is_volume_root,
        )

    volume_label = normalize_volume_label(text)
    if not volume_label:
        raise ReverseCopyDeleteError("Original partition/path is required.")
    matches = _mounted_roots_for_label(volume_label)
    if not matches:
        raise ReverseCopyDeleteError(
            f"No mounted partition/volume named '{volume_label}' was found. "
            "Enter its current volume name, drive/root, or full original path instead."
        )
    if len(matches) > 1:
        raise ReverseCopyDeleteError(
            f"More than one mounted partition/volume is named '{volume_label}': " + ", ".join(matches)
        )
    root = os.path.normpath(matches[0])
    return _OriginalInput(
        text=text,
        base_path=root,
        volume_root=root,
        requested_label=volume_label,
        is_path=False,
        is_volume_root=True,
    )


def _candidate_tag_logs(tlo_home: str) -> List[str]:
    logs_dir = os.path.join(tlo_home, "logs")
    patterns = ("tags*.txt", "tag*.log")
    found: List[str] = []
    for pattern in patterns:
        found.extend(scandir_matching_files(logs_dir, pattern))
    return sorted(set(os.path.normpath(path) for path in found if os.path.isfile(path)))


def _search_path_values_from_lines(lines: Sequence[str]) -> tuple[str, ...]:
    values: List[str] = []

    def add(value: str) -> None:
        clean = (value or "").strip()
        if clean and clean not in values:
            values.append(clean)

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("SEARCH_PATH:"):
            add(stripped.split(":", 1)[1].strip())
            continue
        if not stripped.startswith("#"):
            continue
        lowered = stripped.casefold()
        for marker in ("for search paths:", "for search path:"):
            if marker in lowered:
                marker_index = lowered.index(marker)
                tail = stripped[marker_index + len(marker):].strip()
                for piece in re.split(r"\s+\|\s+", tail):
                    add(piece)
                break
    return tuple(values)


def _copy_destination_from_mode_line(line: str) -> str:
    match = _COPY_DESTINATION_RE.search(line or "")
    if not match:
        return ""
    raw = match.group("destination").strip()
    try:
        return _normalize_logged_path(raw) if raw else ""
    except Exception:
        return ""


def _records_from_log(log_path: str) -> List[ReverseRecord]:
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as infile:
            lines = [line.rstrip("\r\n") for line in infile]
    except OSError:
        return []

    combined_mode = False
    active_copy_destination = ""
    records: List[ReverseRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TAG_DURING_INVENTORY:"):
            combined_mode = bool(_COMBINED_MODE_RE.search(stripped))
            active_copy_destination = _copy_destination_from_mode_line(stripped) if combined_mode else ""
            continue
        if not combined_mode:
            continue
        match = _REVERSE_RECORD_RE.match(stripped)
        if not match:
            continue
        try:
            source = _normalize_logged_path(match.group("source"))
            destination = _normalize_logged_path(match.group("destination"))
        except Exception:
            continue
        records.append(
            ReverseRecord(
                log_path=log_path,
                transfer_kind=match.group("kind").upper(),
                original_path=source,
                current_path=destination,
                logged_original_path=source,
                logged_current_path=destination,
                logged_copy_destination=active_copy_destination,
            )
        )
    return records


def _candidate_logs(tlo_home: str) -> List[_ReverseLogCandidate]:
    candidates: List[_ReverseLogCandidate] = []
    for log_path in _candidate_tag_logs(tlo_home):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as infile:
                lines = [line.rstrip("\r\n") for line in infile]
        except OSError:
            continue
        records = tuple(_records_from_log(log_path))
        if not records:
            continue
        candidates.append(
            _ReverseLogCandidate(
                log_path=log_path,
                search_path_values=_search_path_values_from_lines(lines),
                records=records,
            )
        )
    return candidates


def _log_volume_labels(candidate: _ReverseLogCandidate) -> set[str]:
    labels: set[str] = set()
    for value in candidate.search_path_values:
        volume, _path = parse_volume_path_value(value)
        volume = normalize_volume_label(volume)
        if volume:
            labels.add(volume.casefold())
    return labels


def _candidate_search_paths(candidate: _ReverseLogCandidate) -> List[str]:
    paths: List[str] = []
    for value in candidate.search_path_values:
        _volume, raw_path = parse_volume_path_value(value)
        raw_path = (raw_path or "").strip()
        if not raw_path:
            continue
        try:
            normalized = _normalize_logged_path(raw_path)
        except Exception:
            continue
        if normalized not in paths:
            paths.append(normalized)
    return paths


def _relative_if_under(path_name: str, root: str) -> str | None:
    if not root or not _same_or_under(path_name, root):
        return None
    try:
        relative = os.path.relpath(os.path.normpath(path_name), os.path.normpath(root))
    except ValueError:
        return None
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return relative


def _remap_destination(record: ReverseRecord, moved_root: str) -> str:
    logged_current = record.logged_current_path or record.current_path
    logged_parent = record.logged_copy_destination
    relative = _relative_if_under(logged_current, logged_parent) if logged_parent else None
    if relative is None:
        relative = os.path.basename(logged_current)
    return os.path.normpath(os.path.join(moved_root, relative))


def _path_components(path_name: str) -> List[str]:
    normalized = str(path_name or "").replace("\\", "/").strip("/")
    parts = [piece.casefold() for piece in normalized.split("/") if piece and not re.fullmatch(r"[a-z]:", piece, re.I)]
    return parts


def _common_suffix_count(left: str, right: str) -> int:
    a = _path_components(left)
    b = _path_components(right)
    count = 0
    for x, y in zip(reversed(a), reversed(b)):
        if x != y:
            break
        count += 1
    return count


def _clean_artist_words(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^0-9A-Za-z]+", " ", normalized).casefold()
    return " ".join(normalized.split())


def _artist_variants(text: str) -> set[str]:
    raw = str(text or "").strip(" -_,")
    variants: set[str] = set()

    def add(value: str) -> None:
        clean = _clean_artist_words(value)
        if clean:
            variants.add(clean)

    add(raw)
    if "," in raw:
        left, right = raw.rsplit(",", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            add(f"{right} {left}")
            if right.casefold() == "the":
                add(f"The {left}")
    lowered = raw.casefold()
    if lowered.startswith("the "):
        add(raw[4:] + ", The")
    return variants


def _normalize_short_year(value: str) -> str:
    year = int(value)
    return str(2000 + year if year <= 30 else 1900 + year)


def _artist_date_signatures(folder_name: str) -> set[tuple[str, str]]:
    text = os.path.basename(str(folder_name or "")).strip()
    date_value = ""
    start = -1
    full = _FULL_DATE_RE.search(text)
    if full:
        date_value = f"{full.group('year').lower()}-{full.group('month').lower()}-{full.group('day').lower()}"
        start = full.start()
    else:
        short = _SHORT_DATE_RE.search(text)
        if short:
            month = int(short.group("month"))
            day = int(short.group("day"))
            if 1 <= month <= 12 and 1 <= day <= 31:
                date_value = f"{_normalize_short_year(short.group('year'))}-{month:02d}-{day:02d}"
                start = short.start()
    if not date_value or start <= 0:
        return set()
    artist_text = text[:start].strip(" -_,")
    return {(artist, date_value) for artist in _artist_variants(artist_text)}


def _actual_destination_names(moved_root: str) -> List[str]:
    try:
        return sorted(entry.name for entry in os.scandir(moved_root) if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def _candidate_score(candidate: _ReverseLogCandidate, original: _OriginalInput, moved_root: str) -> tuple[tuple[int, int, int, int, int], str]:
    search_paths = _candidate_search_paths(candidate)
    label_match = int(bool(original.requested_label) and original.requested_label.casefold() in _log_volume_labels(candidate))
    source_under_input = sum(1 for record in candidate.records if _same_or_under(record.logged_original_path or record.original_path, original.base_path))
    suffix = max((_common_suffix_count(original.base_path, path) for path in search_paths), default=0) if original.is_path else 0

    # Strong original-location evidence is considered before destination count.
    # This prevents a large unrelated log in the same destination directory from
    # beating the log whose old search path clearly corresponds to D:\somePath.
    if source_under_input:
        original_evidence = 4
    elif label_match:
        original_evidence = 3
    elif suffix >= 2:
        original_evidence = 3
    elif suffix == 1:
        original_evidence = 2
    else:
        original_evidence = 0

    exact = sum(1 for record in candidate.records if os.path.isdir(_remap_destination(record, moved_root)))

    actual_signature_sets = [
        _artist_date_signatures(name) for name in _actual_destination_names(moved_root)
    ]
    logged_signatures: set[tuple[str, str]] = set()
    for record in candidate.records:
        logged_signatures.update(_artist_date_signatures(record.logged_current_path or record.current_path))
        logged_signatures.update(_artist_date_signatures(record.logged_original_path or record.original_path))
    # Count matching destination folders, not spelling variants. "Friedman,
    # Kinky" and "Kinky Friedman" may generate more than one normalized
    # variant but still represent one piece of artist/date evidence.
    fuzzy = sum(1 for signatures in actual_signature_sets if signatures & logged_signatures)

    score = (original_evidence, suffix, exact, fuzzy, label_match)
    evidence = (
        f"original_evidence={original_evidence}, path_suffix={suffix}, "
        f"exact_destination_matches={exact}, artist_date_matches={fuzzy}, label_match={label_match}"
    )
    return score, evidence


def _select_candidate_log(candidates: Sequence[_ReverseLogCandidate], original: _OriginalInput, moved_root: str) -> tuple[_ReverseLogCandidate, str]:
    scored: List[tuple[tuple[int, int, int, int, int], _ReverseLogCandidate, str]] = []
    for candidate in candidates:
        score, evidence = _candidate_score(candidate, original, moved_root)
        # At least one concrete clue is required. Do not pick a log merely
        # because it happens to be the only historical combined-operation log.
        if not any(score):
            continue
        scored.append((score, candidate, evidence))
    if not scored:
        raise ReverseCopyDeleteError(
            "No combined Copy/Delete + Rename success log could be identified from the original partition/path "
            "and the folders currently present at the Copy/Delete destination."
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_candidate, best_evidence = scored[0]
    tied = [item for item in scored[1:] if item[0] == best_score]
    if tied:
        names = [os.path.basename(best_candidate.log_path)] + [os.path.basename(item[1].log_path) for item in tied]
        raise ReverseCopyDeleteError(
            "More than one success log matches the supplied original partition/path and destination equally well: "
            + ", ".join(names)
            + ". Narrow the Original Partition / Path input to the original search path."
        )
    return best_candidate, best_evidence


def _best_logged_search_anchor(candidate: _ReverseLogCandidate, source: str, original: _OriginalInput) -> str:
    options = [path for path in _candidate_search_paths(candidate) if _same_or_under(source, path)]
    if not options:
        return ""
    if original.is_path and not original.is_volume_root:
        options.sort(key=lambda path: (_common_suffix_count(original.base_path, path), len(_path_components(path))), reverse=True)
    else:
        options.sort(key=lambda path: len(_path_components(path)), reverse=True)
    return options[0]


def _remap_original(record: ReverseRecord, candidate: _ReverseLogCandidate, original: _OriginalInput) -> str | None:
    source = os.path.normpath(record.logged_original_path or record.original_path)
    if _same_or_under(source, original.base_path):
        return source

    anchor = _best_logged_search_anchor(candidate, source, original)
    if original.is_path and not original.is_volume_root and anchor:
        suffix = _common_suffix_count(original.base_path, anchor)
        # A full-path input such as D:\somePath is treated as the current form
        # of the logged search root when their tail names agree. This supports
        # both a changed drive letter and a changed volume label.
        if suffix > 0 or len(_candidate_search_paths(candidate)) == 1:
            relative = _relative_if_under(source, anchor)
            if relative is not None:
                mapped = os.path.normpath(os.path.join(original.base_path, relative))
                if _same_or_under(mapped, original.base_path):
                    return mapped

    logged_root = _logged_volume_root(source)
    if logged_root and original.volume_root:
        relative = _relative_if_under(source, logged_root)
        if relative is not None:
            mapped = os.path.normpath(os.path.join(original.volume_root, relative))
            if _same_or_under(mapped, original.volume_root):
                return mapped

    if anchor and original.is_path:
        relative = _relative_if_under(source, anchor)
        if relative is not None:
            mapped = os.path.normpath(os.path.join(original.base_path, relative))
            if _same_or_under(mapped, original.base_path):
                return mapped
    return None


def prepare_reverse_selection(
    tlo_home: str = "",
    my_tlo: str = "",
    *,
    original_partition: str,
    moved_to: str,
) -> ReverseSelection:
    """Identify one applicable success log and map all of its eligible records.

    ``original_partition`` accepts a current volume label, drive/root, or full
    original path (for example ``D:\\somePath``). Historical volume labels and
    drive letters are only evidence; they are not required to still match.
    """
    try:
        resolved_home = resolve_tlo_home(tlo_home=tlo_home, my_tlo=my_tlo, error_type=ReverseCopyDeleteError)
    except TypeError:
        resolved_home = resolve_tlo_home(tlo_home, my_tlo, error_type=ReverseCopyDeleteError)
    original = _resolve_original_input(original_partition)
    moved_root = _normalize_user_root(moved_to, label="Copy/Delete destination")

    candidates = _candidate_logs(resolved_home)
    if not candidates:
        raise ReverseCopyDeleteError(
            "No success-tag logs contain a combined Copy/Delete + Rename Compliantly mapping."
        )
    candidate, evidence = _select_candidate_log(candidates, original, moved_root)

    deduped: dict[tuple[str, str], ReverseRecord] = {}
    for record in candidate.records:
        mapped_original = _remap_original(record, candidate, original)
        if not mapped_original:
            continue
        mapped_current = _remap_destination(record, moved_root)
        # Full-path inputs constrain restoration to the supplied original path;
        # volume-label/root inputs constrain it to the resolved current volume.
        allowed_root = original.base_path if original.is_path and not original.is_volume_root else original.volume_root
        if allowed_root and not _same_or_under(mapped_original, allowed_root):
            continue
        if not _same_or_under(mapped_current, moved_root):
            continue
        mapped = ReverseRecord(
            log_path=record.log_path,
            transfer_kind=record.transfer_kind,
            original_path=mapped_original,
            current_path=mapped_current,
            logged_original_path=record.logged_original_path or record.original_path,
            logged_current_path=record.logged_current_path or record.current_path,
            logged_copy_destination=record.logged_copy_destination,
        )
        key = (_path_key(mapped.original_path), _path_key(mapped.current_path))
        deduped[key] = mapped

    records = tuple(sorted(deduped.values(), key=lambda item: (item.original_path.casefold(), item.current_path.casefold())))
    if not records:
        raise ReverseCopyDeleteError(
            f"Identified {os.path.basename(candidate.log_path)}, but none of its logged original paths can be safely mapped "
            "to the supplied Original Partition / Path."
        )
    return ReverseSelection(
        tlo_home=resolved_home,
        original_input=original.text,
        original_root=original.base_path,
        moved_root=moved_root,
        log_path=candidate.log_path,
        records=records,
        evidence=evidence,
    )


def find_reverse_records(
    tlo_home: str = "",
    my_tlo: str = "",
    *,
    original_partition: str,
    moved_to: str,
) -> tuple[str, str, str, List[ReverseRecord]]:
    """Backward-compatible discovery wrapper returning one selected log's mappings."""
    selection = prepare_reverse_selection(
        tlo_home=tlo_home,
        my_tlo=my_tlo,
        original_partition=original_partition,
        moved_to=moved_to,
    )
    return selection.tlo_home, selection.original_root, selection.moved_root, list(selection.records)


def _file_size_map(root: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for current_dir, _dir_names, file_names in os.walk(root):
        for file_name in file_names:
            full_path = os.path.join(current_dir, file_name)
            relative = os.path.normcase(os.path.normpath(os.path.relpath(full_path, root)))
            result[relative] = os.path.getsize(full_path)
    return result


def _directory_path_set(root: str) -> set[str]:
    result: set[str] = set()
    for current_dir, dir_names, _file_names in os.walk(root):
        for dir_name in dir_names:
            full_path = os.path.join(current_dir, dir_name)
            relative = os.path.normcase(os.path.normpath(os.path.relpath(full_path, root)))
            result.add(relative)
    return result


def _verify_copy(source_root: str, destination_root: str) -> None:
    """Require complete structure, size, and SHA-256 identity before delete."""
    if not directory_trees_exactly_match(source_root, destination_root):
        raise ReverseCopyDeleteError("reverse copy verification failed: SHA-256 directory trees differ or could not be verified")


def _owned_restore_temp_path(original: str) -> str:
    parent = os.path.dirname(original)
    leaf = os.path.basename(original) or "TLO"
    for _ in range(20):
        candidate = os.path.join(parent, f".{leaf}.tlo-restore-{uuid.uuid4().hex}")
        if not os.path.lexists(candidate):
            return candidate
    raise ReverseCopyDeleteError("could not allocate a unique temporary restore path")


def _same_filesystem(existing_path: str, destination_parent: str) -> bool:
    try:
        return os.stat(existing_path).st_dev == os.stat(destination_parent).st_dev
    except OSError:
        return False


def _append_reverse_log(tlo_home: str, lines: Iterable[str]) -> str:
    log_path = os.path.join(ensure_logs_dir(tlo_home), "reverseCopyDelete.log")
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z").lstrip("0")
    with open(log_path, "a", encoding="utf-8", newline="\n") as outfile:
        outfile.write(f"Reverse Copy/Delete + Rename | {timestamp}\n")
        for line in lines:
            outfile.write(str(line).rstrip("\r\n") + "\n")
        outfile.write("\n")
    return log_path


def reverse_copy_delete_and_rename(
    tlo_home: str = "",
    my_tlo: str = "",
    *,
    original_partition: str = "",
    moved_to: str = "",
    selection: ReverseSelection | None = None,
    emit: Optional[Callable[[str], None]] = None,
) -> ReverseResult:
    """Restore exact folder names/locations from one already-identified log.

    When ``selection`` is supplied (the GUI path), discovery is not repeated.
    Artist/date normalization is never used to pick an individual folder: each
    restore still requires the exact destination path recorded in the selected
    log. A manually renamed/moved destination folder is therefore left alone.
    """
    if selection is None:
        selection = prepare_reverse_selection(
            tlo_home=tlo_home,
            my_tlo=my_tlo,
            original_partition=original_partition,
            moved_to=moved_to,
        )

    tlo_home_resolved = selection.tlo_home
    original_root = selection.original_root
    moved_root = selection.moved_root
    records = list(selection.records)
    result = ReverseResult(discovered=len(records))
    audit_lines = [
        f"TLOHome: {tlo_home_resolved}",
        f"Original partition/path: {original_root}",
        f"Copy/Delete destination: {moved_root}",
        f"Selected success log: {selection.log_path}",
        f"Selection evidence: {selection.evidence}",
        f"Eligible logged mappings: {len(records)}",
    ]

    def report(message: str) -> None:
        result.messages.append(message)
        audit_lines.append(message)
        if emit is not None:
            emit(message)

    for record in records:
        original = record.original_path
        current = record.current_path
        current_exists = os.path.isdir(current)
        original_exists = os.path.exists(original)

        if original_exists and not current_exists:
            result.already_restored += 1
            report(f"ALREADY_RESTORED: {current} -> {original}")
            continue
        if not current_exists and not original_exists:
            # Do not search for a fuzzy replacement after the log has been
            # selected. The folder may have been manually renamed or moved.
            result.skipped_unmatched += 1
            report(f"SKIPPED_UNMATCHED: exact logged destination is absent; left current destination contents untouched | {current}")
            continue
        if original_exists and current_exists:
            result.conflicts += 1
            report(f"CONFLICT: original path already exists; leaving both folders untouched | {current} -> {original}")
            continue
        if not os.path.isdir(current):
            result.skipped_unmatched += 1
            report(f"SKIPPED_UNMATCHED: exact logged destination is not an accessible directory; left untouched | {current}")
            continue

        original_parent = os.path.dirname(original)
        try:
            allowed_root = original_root
            # Validate containment before creating any directory derived from a
            # historical log record.
            if not _same_or_under(original, allowed_root):
                raise ReverseCopyDeleteError("logged original path escaped the selected original partition/path")
            os.makedirs(original_parent, exist_ok=True)

            # Re-check immediately before mutation. A path that appeared after
            # initial selection is a conflict and must never be overwritten.
            if os.path.lexists(original):
                raise ReverseCopyDeleteError("original path appeared during restore; leaving both locations untouched")

            if _same_filesystem(current, original_parent):
                os.rename(current, original)
                result.restored += 1
                report(f"RESTORED_MOVE: {current} -> {original}")
            else:
                temp_restore = _owned_restore_temp_path(original)
                try:
                    shutil.copytree(current, temp_restore, symlinks=False)
                    _verify_copy(current, temp_restore)
                    if os.path.lexists(original):
                        raise ReverseCopyDeleteError("original path appeared during restore; verified temporary copy retained only until rollback")
                    os.rename(temp_restore, original)
                    temp_restore = ""
                except Exception:
                    # Roll back only the temporary directory created by this
                    # operation. Never remove ``original`` in an exception path.
                    if temp_restore and os.path.isdir(temp_restore):
                        shutil.rmtree(temp_restore, ignore_errors=True)
                    raise
                shutil.rmtree(current)
                result.restored += 1
                report(f"RESTORED_COPY_DELETE: {current} -> {original}")
        except Exception as exc:
            result.errors += 1
            report(f"ERROR: {current} -> {original} | {exc}")

    report(
        "Complete: "
        f"found={result.discovered} restored={result.restored} "
        f"already_restored={result.already_restored} skipped_unmatched={result.skipped_unmatched} "
        f"conflicts={result.conflicts} errors={result.errors}"
    )
    _append_reverse_log(tlo_home_resolved, audit_lines)
    return result
