"""Persistent multi-pass Copy Request workflow for TLO inventories."""

from __future__ import annotations

__version__ = "v517"

import hashlib
import json
import ntpath
import os
import re
import shutil
import socket
import subprocess
import string
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from tlo_artist_db import ArtistMatcher, load_artist_matcher, lookup_artist_master_with_status
from tlo_bootlist_volume_policy import (
    normalize_volume_label,
    parse_volume_path_value,
    read_bootlist_rows,
    volume_key,
)
from tlo_tree_compare import directory_trees_exactly_match
from tlo_path_policy import OS_MANAGED_DIR_NAMES
from tlo_path_inputs import normalize_platform_input_path, strip_optional_quotes
from inventory_list_lib import split_search_path_entries
from tlo_volume_label import resolve_volume_label
from tlo_redundancy import (
    RedundancyGroup,
    group_display_for_volume,
    load_redundancy_groups,
    ordered_equivalents,
)

COPY_REQUESTS_DIRNAME = "copyRequests"
REQUEST_STATE_FILENAME = "state.json"
REQUEST_SNAPSHOT_FILENAME = "request.txt"
LATEST_REPORT_FILENAME = "latest-report.txt"
COPIED_REPORT_FILENAME = "copied.txt"
PENDING_REPORT_FILENAME = "pending.txt"
FAILED_REPORT_FILENAME = "failed.txt"
REPORTS_DIRNAME = "reports"
STATE_SCHEMA = 1

STATUS_IN_PROGRESS = "In Progress"
STATUS_WAITING = "Waiting For Volumes"
STATUS_MATCHES_COMPLETE = "Matches Complete / Unmatched Remain"
STATUS_COMPLETE = "Complete"
STATUS_CLOSED = "Closed"

# Whole-volume copies intentionally omit operating-system metadata/trash folders
# that are commonly unreadable to normal users and are not part of a music
# collection.  The same set is used for sizing, copying, and verification.
VOLUME_ROOT_EXCLUDED_NAMES = OS_MANAGED_DIR_NAMES
STALE_COPY_PREFIX = ".tlo-copy-"
COPY_TEMP_MARKER_FILENAME = ".tlo-copy-owned.json"
COPY_PASS_LOCK_FILENAME = ".copy-pass.lock"
DESTINATION_LOCK_PREFIX = ".tlo-copy-lock-"
FOREIGN_LOCK_STALE_SECONDS = 24 * 60 * 60

SHOW_DATE_RE = re.compile(r"(?<!\d)(?P<date>\d{4}-\d{2}-\d{2})(?!\d)")
DATE_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<date>\d{4}-\d{2}-\d{2})$")
YEAR_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<year>\d{4})$")
RANGE_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<start>\d{2}|\d{4})-(?P<end>\d{2}|\d{4})$")
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
WINDOWS_ROOTED_PATH_RE = re.compile(r"^[A-Za-z]:(?:[\\/].*)?$")
UNC_PATH_RE = re.compile(r"^\\\\[^\\/]+[\\/][^\\/]+")


class CopyRequestError(RuntimeError):
    pass


class CopyRequestCancelled(CopyRequestError):
    pass


@dataclass(frozen=True)
class RequestItem:
    raw: str
    kind: str
    artist: str = ""
    artist_key: str = ""
    exact_date: str = ""
    start_year: int = 0
    end_year: int = 0
    exact_show: str = ""
    direct_path: str = ""
    direct_volume: str = ""
    error: str = ""


@dataclass(frozen=True)
class SourceCandidate:
    show: str
    source_path: str
    volume: str
    inventory_path: str
    inventory_volume: str = ""


@dataclass
class RequestEvaluation:
    request_id: str
    name: str
    destination: str
    status: str
    items: List[RequestItem] = field(default_factory=list)
    item_matches: Dict[str, List[str]] = field(default_factory=dict)
    matched_shows: List[str] = field(default_factory=list)
    completed_shows: List[str] = field(default_factory=list)
    completed_direct_items: List[str] = field(default_factory=list)
    available: Dict[str, SourceCandidate] = field(default_factory=dict)
    direct_available: Dict[str, SourceCandidate] = field(default_factory=dict)
    waiting: Dict[str, List[str]] = field(default_factory=dict)
    direct_waiting: Dict[str, List[str]] = field(default_factory=dict)
    stale_missing: Dict[str, List[str]] = field(default_factory=dict)
    unmatched_items: List[str] = field(default_factory=list)
    invalid_items: Dict[str, str] = field(default_factory=dict)
    volume_opportunities: Dict[str, int] = field(default_factory=dict)
    preview_notes: List[str] = field(default_factory=list)

    @property
    def available_count(self) -> int:
        return len(self.available)

    @property
    def pending_count(self) -> int:
        return len(self.waiting)

    @property
    def stale_count(self) -> int:
        return len(self.stale_missing)


@dataclass
class CopyPassResult:
    request_id: str
    status: str
    copied: List[Tuple[str, str, str]] = field(default_factory=list)
    already_satisfied: List[Tuple[str, str]] = field(default_factory=list)
    failures: List[Tuple[str, str]] = field(default_factory=list)
    source_details: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    required_bytes: int = 0
    free_bytes: int = 0
    insufficient_space: bool = False
    cancelled: bool = False
    report_path: str = ""


# ---------------------------------------------------------------------------
# Request file/state helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_text(path_name: str, text: str) -> None:
    directory = os.path.dirname(path_name) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".tlo-copy-request-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as outfile:
            outfile.write(text)
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temp_name, path_name)
    except Exception:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise


def _atomic_write_json(path_name: str, payload: Mapping[str, object]) -> None:
    _atomic_write_text(path_name, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def copy_requests_root(tlo_home: str) -> str:
    return os.path.join(os.path.abspath(tlo_home), COPY_REQUESTS_DIRNAME)


def _normalized_identity_path(path_name: str) -> str:
    value = os.path.abspath(os.path.normpath(str(path_name or "")))
    return os.path.normcase(value)


def request_id_for(request_file: str, destination: str) -> str:
    request_abs = _normalized_identity_path(request_file)
    destination_abs = _normalized_identity_path(destination)
    digest = hashlib.sha256((request_abs + "\0" + destination_abs).encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
    stem = SAFE_ID_RE.sub("-", Path(request_file).stem).strip("-._") or "copy-request"
    return f"{stem[:48]}--{digest}"


def _normalized_paths_input_identity(request_input: str) -> str:
    entries = split_search_path_entries(request_input)
    return "\n".join(strip_optional_quotes(entry).strip() for entry in entries)


def _copy_request_name_from_paths_input(request_input: str) -> str:
    entries = split_search_path_entries(request_input)
    if not entries:
        return "Copy Request"
    value = strip_optional_quotes(entries[0]).strip().rstrip("\\/")
    leaf = re.split(r"[\\/]", value)[-1] if value else ""
    if leaf.lower().endswith(".txt"):
        leaf = leaf[:-4]
    leaf = " ".join(leaf.split()).strip()
    return leaf[:80] or "Copy Request"


def request_id_for_paths(request_input: str, destination: str) -> str:
    request_identity = _normalized_paths_input_identity(request_input)
    if not request_identity:
        raise CopyRequestError("Copy Request Path(s) is required.")
    destination_abs = _normalized_identity_path(destination)
    digest = hashlib.sha256((request_identity + "\0" + destination_abs).encode("utf-8", errors="surrogatepass")).hexdigest()[:12]
    stem = SAFE_ID_RE.sub("-", _copy_request_name_from_paths_input(request_input)).strip("-._") or "copy-request"
    return f"{stem[:48]}--{digest}"


def request_dir(tlo_home: str, request_id: str) -> str:
    return os.path.join(copy_requests_root(tlo_home), request_id)


def state_path(tlo_home: str, request_id: str) -> str:
    return os.path.join(request_dir(tlo_home, request_id), REQUEST_STATE_FILENAME)


def _request_text_from_file(path_name: str) -> str:
    if not os.path.isfile(path_name):
        raise CopyRequestError(f"Request file does not exist: {path_name}")
    if not str(path_name).lower().endswith(".txt"):
        raise CopyRequestError("Copy Request input must be a .txt file.")
    try:
        with open(path_name, "r", encoding="utf-8-sig", newline=None) as infile:
            return infile.read()
    except UnicodeDecodeError as exc:
        raise CopyRequestError(f"Request file must be UTF-8 text: {path_name}") from exc


def _digest_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _is_comment_line(line_text: str) -> bool:
    cleaned = str(line_text or "").lstrip("\ufeff").strip()
    lowered = cleaned.casefold()
    return cleaned.startswith("#") or lowered == "rem" or lowered.startswith("rem ")


def request_lines_from_text(text: str) -> List[str]:
    result: List[str] = []
    for raw in str(text or "").splitlines():
        value = raw.strip()
        if not value or _is_comment_line(raw):
            continue
        result.append(value)
    return result


def _expand_trailing_path_wildcard(value: str) -> List[str]:
    """Expand one direct path ending in ``*`` to matching immediate folders.

    Only the final asterisk is a wildcard. ``C:\\TLO*`` matches sibling
    folders whose names begin with ``TLO``; ``C:\\TLO\\*`` matches all
    immediate child folders of ``C:\\TLO``. Files and symbolic-link
    directories are excluded. The expansion is performed when the request is
    created so the resolved paths can be persisted in its snapshot.
    """
    raw = strip_optional_quotes(value).strip()
    if not raw.endswith("*"):
        return [raw]
    prefix_raw = raw[:-1]
    if not _looks_like_direct_path(prefix_raw):
        return [raw]

    children_mode = prefix_raw.endswith(("\\", "/"))
    if children_mode:
        scan_parent_raw = prefix_raw.rstrip("\\/")
        name_prefix = ""
    else:
        scan_parent_raw = os.path.dirname(prefix_raw.replace("\\", os.sep) if os.name != "nt" else prefix_raw)
        # Normalize the whole prefix first so Windows drive input is mapped to
        # /mnt/<drive> on WSL/Linux before its parent/name are separated.
        normalized_prefix = normalize_platform_input_path(prefix_raw)
        scan_parent_raw = os.path.dirname(normalized_prefix)
        name_prefix = os.path.basename(normalized_prefix)

    try:
        scan_parent = normalize_platform_input_path(scan_parent_raw) if children_mode else os.path.normpath(scan_parent_raw)
    except Exception as exc:
        raise CopyRequestError(f"Cannot normalize Copy Request wildcard path {raw}: {exc}") from exc
    if not scan_parent or not os.path.isdir(scan_parent):
        raise CopyRequestError(f"Copy Request wildcard parent is not an accessible folder: {scan_parent or prefix_raw}")

    try:
        matches = []
        windows_form = bool(WINDOWS_ROOTED_PATH_RE.match(raw) or UNC_PATH_RE.match(raw))
        name_prefix_key = name_prefix.casefold() if windows_form else os.path.normcase(name_prefix)
        windows_base = prefix_raw.rstrip("\\/") if children_mode else ntpath.dirname(prefix_raw)
        with os.scandir(scan_parent) as entries:
            for entry in entries:
                entry_name_key = entry.name.casefold() if windows_form else os.path.normcase(entry.name)
                if name_prefix and not entry_name_key.startswith(name_prefix_key):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                        if windows_form:
                            matches.append(ntpath.normpath(ntpath.join(windows_base, entry.name)))
                        else:
                            matches.append(os.path.normpath(entry.path))
                except OSError:
                    continue
    except OSError as exc:
        raise CopyRequestError(f"Cannot expand Copy Request wildcard path {raw}: {exc}") from exc

    matches.sort(key=lambda path_name: os.path.basename(path_name).casefold())
    if not matches:
        raise CopyRequestError(f"Copy Request wildcard path matched no folders: {raw}")
    return matches


def _expand_request_input_items(items: Sequence[str]) -> List[str]:
    expanded: List[str] = []
    for item in items:
        expanded.extend(_expand_trailing_path_wildcard(item))
    return expanded


def aggregate_request_paths_input(request_input: str) -> Tuple[str, List[Dict[str, object]]]:
    """Expand a Copy Request Path(s) field into one persisted request snapshot.

    Semicolon splitting and optional double-quote handling are exactly the same
    as the main GUI Path(s) field. Entries ending in .txt are read immediately
    as request-list files. Their blank/#/REM comment lines are discarded and
    their usable request lines are inserted at that position. Other entries are
    persisted literally as request items, so paths and ordinary Artist/Show text
    may be mixed freely. The returned snapshot is self-contained; continuing the
    request never requires the source .txt files to still exist.
    """
    try:
        entries = split_search_path_entries(request_input)
    except ValueError as exc:
        raise CopyRequestError(str(exc)) from exc
    if not entries:
        raise CopyRequestError("Copy Request Path(s) is required.")

    aggregated: List[str] = []
    sources: List[Dict[str, object]] = []
    for entry in entries:
        value = strip_optional_quotes(entry).strip()
        if not value:
            continue
        if value.lower().endswith(".txt"):
            source_path = normalize_platform_input_path(value)
            text = _request_text_from_file(source_path)
            file_items = request_lines_from_text(text)
            if not file_items:
                raise CopyRequestError(f"Copy Request .txt file contains no request items: {source_path}")
            expanded_file_items = _expand_request_input_items(file_items)
            aggregated.extend(expanded_file_items)
            sources.append({
                "kind": "file",
                "input": value,
                "expanded_items": list(expanded_file_items),
            })
            continue

        expanded_items = _expand_trailing_path_wildcard(value)
        aggregated.extend(expanded_items)
        sources.append({
            "kind": "wildcard" if expanded_items != [value] else "item",
            "input": value,
            "expanded_items": list(expanded_items),
        })

    if not aggregated:
        raise CopyRequestError("Copy Request Path(s) contains no request items.")
    return "\n".join(aggregated) + "\n", sources


def _default_state(request_file: str, destination: str, request_text: str, request_id: str) -> Dict[str, object]:
    now = _now_iso()
    return {
        "schema": STATE_SCHEMA,
        "request_id": request_id,
        "name": Path(request_file).stem,
        "request_file": os.path.abspath(request_file),
        "request_digest": _digest_text(request_text),
        "destination": os.path.abspath(destination),
        "created_at": now,
        "updated_at": now,
        "closed": False,
        "status": STATUS_IN_PROGRESS,
        "completed": {},
        "pending_copy": {},
        "history": [],
    }


def _default_paths_state(
    request_input: str,
    destination: str,
    request_text: str,
    request_id: str,
    sources: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    now = _now_iso()
    return {
        "schema": STATE_SCHEMA,
        "request_id": request_id,
        "name": _copy_request_name_from_paths_input(request_input),
        "input_mode": "paths",
        "request_input": str(request_input or "").strip(),
        "request_sources": [dict(source) for source in sources],
        "request_digest": _digest_text(request_text),
        "destination": os.path.abspath(destination),
        "created_at": now,
        "updated_at": now,
        "closed": False,
        "status": STATUS_IN_PROGRESS,
        "completed": {},
        "pending_copy": {},
        "history": [],
    }


def create_or_open_request_paths(tlo_home: str, request_input: str, destination: str) -> Dict[str, object]:
    """Create/open a request from the GUI Path(s) field.

    The request identity is derived from the entered Path(s) expression plus the
    Destination before any .txt file is opened. Therefore an already-saved
    request can be reopened with the same Path(s) text even if a contributing
    .txt file has since been moved or deleted. New requests expand every .txt
    source once and persist the resulting aggregate snapshot.
    """
    destination = os.path.abspath(os.path.normpath(destination))
    if not os.path.isdir(destination):
        raise CopyRequestError(f"Destination is not an accessible folder: {destination}")
    try:
        rid = request_id_for_paths(request_input, destination)
    except ValueError as exc:
        raise CopyRequestError(str(exc)) from exc
    existing = load_request(tlo_home, rid, missing_ok=True)
    if existing:
        return existing

    text, sources = aggregate_request_paths_input(request_input)
    state = _default_paths_state(request_input, destination, text, rid, sources)
    directory = request_dir(tlo_home, rid)
    os.makedirs(os.path.join(directory, REPORTS_DIRNAME), exist_ok=True)
    _atomic_write_text(os.path.join(directory, REQUEST_SNAPSHOT_FILENAME), text)
    _atomic_write_json(state_path(tlo_home, rid), state)
    return state


def create_or_open_request(tlo_home: str, request_file: str, destination: str) -> Dict[str, object]:
    request_file = os.path.abspath(os.path.normpath(request_file))
    destination = os.path.abspath(os.path.normpath(destination))
    if not os.path.isdir(destination):
        raise CopyRequestError(f"Destination is not an accessible folder: {destination}")
    text = _request_text_from_file(request_file)
    if not request_lines_from_text(text):
        raise CopyRequestError("The request file contains no request items.")
    rid = request_id_for(request_file, destination)
    existing = load_request(tlo_home, rid, missing_ok=True)
    if existing:
        return existing
    state = _default_state(request_file, destination, text, rid)
    directory = request_dir(tlo_home, rid)
    os.makedirs(os.path.join(directory, REPORTS_DIRNAME), exist_ok=True)
    _atomic_write_text(os.path.join(directory, REQUEST_SNAPSHOT_FILENAME), text)
    _atomic_write_json(state_path(tlo_home, rid), state)
    return state


def load_request(tlo_home: str, request_id: str, *, missing_ok: bool = False) -> Dict[str, object]:
    path_name = state_path(tlo_home, request_id)
    if not os.path.isfile(path_name):
        if missing_ok:
            return {}
        raise CopyRequestError(f"Copy Request state was not found: {request_id}")
    try:
        if os.path.getsize(path_name) > 4 * 1024 * 1024:
            raise CopyRequestError(f"Copy Request state is unexpectedly large: {path_name}")
        with open(path_name, "r", encoding="utf-8") as infile:
            payload = json.load(infile)
    except (OSError, ValueError) as exc:
        raise CopyRequestError(f"Cannot read Copy Request state: {path_name}: {exc}") from exc
    if not isinstance(payload, dict) or int(payload.get("schema", 0) or 0) != STATE_SCHEMA:
        raise CopyRequestError(f"Unsupported Copy Request state: {path_name}")
    return payload


def save_request(tlo_home: str, state: Dict[str, object]) -> None:
    state["updated_at"] = _now_iso()
    _atomic_write_json(state_path(tlo_home, str(state["request_id"])), state)


def saved_request_text(tlo_home: str, request_id: str) -> str:
    path_name = os.path.join(request_dir(tlo_home, request_id), REQUEST_SNAPSHOT_FILENAME)
    try:
        with open(path_name, "r", encoding="utf-8") as infile:
            return infile.read()
    except OSError as exc:
        raise CopyRequestError(f"Saved Copy Request specification is missing: {path_name}") from exc


def request_uses_persisted_paths_input(state: Mapping[str, object]) -> bool:
    return str(state.get("input_mode", "") or "").casefold() == "paths"


def source_request_change_state(tlo_home: str, state: Mapping[str, object]) -> str:
    """Return unchanged, changed, missing, or snapshot-only for the source input."""
    if request_uses_persisted_paths_input(state):
        return "snapshot-only"
    path_name = str(state.get("request_file", "") or "")
    if not path_name or not os.path.isfile(path_name):
        return "missing"
    try:
        current = _request_text_from_file(path_name)
    except CopyRequestError:
        return "missing"
    return "unchanged" if _digest_text(current) == str(state.get("request_digest", "") or "") else "changed"


def update_request_from_source(tlo_home: str, state: Dict[str, object]) -> Dict[str, object]:
    request_file = str(state.get("request_file", "") or "")
    text = _request_text_from_file(request_file)
    if not request_lines_from_text(text):
        raise CopyRequestError("The updated request file contains no request items.")
    state["request_digest"] = _digest_text(text)
    _atomic_write_text(os.path.join(request_dir(tlo_home, str(state["request_id"])), REQUEST_SNAPSHOT_FILENAME), text)
    save_request(tlo_home, state)
    return state


def close_request(tlo_home: str, request_id: str) -> Dict[str, object]:
    state = load_request(tlo_home, request_id)
    state["closed"] = True
    state["status"] = STATUS_CLOSED
    save_request(tlo_home, state)
    return state


def delete_request(tlo_home: str, request_id: str) -> None:
    directory = request_dir(tlo_home, request_id)
    if os.path.isdir(directory):
        shutil.rmtree(directory)


def list_requests(tlo_home: str) -> List[Dict[str, object]]:
    root = copy_requests_root(tlo_home)
    if not os.path.isdir(root):
        return []
    result: List[Dict[str, object]] = []
    for name in sorted(os.listdir(root), key=str.casefold):
        if name == REPORTS_DIRNAME:
            continue
        state = load_request(tlo_home, name, missing_ok=True)
        if state:
            result.append(state)
    result.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return result


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _normalize_show(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def _show_artist_date(show: str) -> Tuple[str, str]:
    match = SHOW_DATE_RE.search(str(show or ""))
    if not match:
        return "", ""
    artist = str(show or "")[: match.start()].strip(" -\t")
    return artist, match.group("date")


def _artist_key(text: str, matcher: Optional[ArtistMatcher]) -> Tuple[str, str]:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return "", "empty artist"
    if matcher is not None:
        status, masters = lookup_artist_master_with_status(cleaned, matcher)
        if status == "matched" and len(masters) == 1:
            return masters[0].casefold(), ""
        if status == "collision" and masters:
            return "", "Ambiguous Artist DB alias: " + ", ".join(masters)
    # An artist absent from the database may still match an exact artist string
    # already present in bootlist.csv.
    return cleaned.casefold(), ""


def _resolve_two_digit_start(two_digit: int, *, current_year: Optional[int] = None) -> int:
    current_year = int(current_year or datetime.now().year)
    current_two = current_year % 100
    century = current_year - current_two
    if two_digit <= current_two:
        return century + two_digit
    return century - 100 + two_digit


def resolve_year_range(start_text: str, end_text: str, *, current_year: Optional[int] = None) -> Tuple[int, int]:
    start = str(start_text or "").strip()
    end = str(end_text or "").strip()
    if len(start) != len(end) or len(start) not in {2, 4}:
        raise CopyRequestError("Date ranges must use yyyy-yyyy or yy-yy.")
    if not (start.isdigit() and end.isdigit()):
        raise CopyRequestError("Date ranges must use numeric years.")
    if len(start) == 4:
        first = int(start)
        second = int(end)
        if second <= first:
            raise CopyRequestError("The second year in a yyyy-yyyy range must be greater than the first year.")
        return first, second
    first = _resolve_two_digit_start(int(start), current_year=current_year)
    target_suffix = int(end)
    second = (first // 100) * 100 + target_suffix
    while second <= first:
        second += 100
    return first, second


def _looks_like_direct_path(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if value.lower().startswith("file:"):
        return True
    if WINDOWS_ROOTED_PATH_RE.match(value) or UNC_PATH_RE.match(value):
        return True
    return value.startswith("/")


def _normalize_direct_path_for_runtime(path_text: str) -> str:
    value = str(path_text or "").strip()
    drive_only = re.fullmatch(r"(?P<drive>[A-Za-z]):", value)
    if drive_only:
        if os.name == "nt":
            return drive_only.group("drive").upper() + ":\\"
        return os.path.normpath(f"/mnt/{drive_only.group('drive').lower()}")
    return normalize_platform_input_path(value)


def _direct_item_key(item: RequestItem) -> str:
    if item.kind == "volume":
        return "volume:" + volume_key(item.direct_volume)
    if item.kind == "path":
        if item.direct_volume:
            return "volume-path:" + volume_key(item.direct_volume) + ":" + str(item.direct_path or "").replace("\\", "/").casefold()
        try:
            normalized = _normalize_direct_path_for_runtime(item.direct_path)
        except Exception:
            normalized = str(item.direct_path or "")
        return "path:" + os.path.normcase(os.path.abspath(os.path.normpath(normalized)))
    return ""


def parse_request_items(
    text: str,
    inventory_shows: Sequence[str],
    matcher: Optional[ArtistMatcher],
    inventory_volumes: Sequence[str] = (),
) -> List[RequestItem]:
    exact_show_map = {_normalize_show(show): show for show in inventory_shows}
    known_volumes = {volume_key(label): str(label).strip() for label in inventory_volumes if str(label).strip()}
    items: List[RequestItem] = []
    for raw in request_lines_from_text(text):
        # Direct path/volume requests take precedence over Artist/Show grammar.
        # A bracketed bootlist-style value may name either an entire volume
        # ([Juke3]) or a path on that volume ([Juke3] /Artist/Show).
        if raw.startswith("["):
            volume, stored = parse_volume_path_value(raw)
            if volume:
                if stored:
                    items.append(RequestItem(raw=raw, kind="path", direct_path=stored, direct_volume=volume))
                else:
                    items.append(RequestItem(raw=raw, kind="volume", direct_volume=volume))
                continue

        if _looks_like_direct_path(raw):
            items.append(RequestItem(raw=raw, kind="path", direct_path=raw))
            continue

        exact = exact_show_map.get(_normalize_show(raw))
        if exact:
            items.append(RequestItem(raw=raw, kind="show", exact_show=exact))
            continue

        raw_volume_key = volume_key(raw)
        if raw_volume_key and raw_volume_key in known_volumes:
            artist_collision = False
            if matcher is not None:
                status, masters = lookup_artist_master_with_status(raw, matcher)
                artist_collision = status in {"matched", "collision"} and bool(masters)
            if not artist_collision:
                raw_artist = " ".join(raw.split()).casefold()
                artist_collision = any(_show_artist_date(show)[0].casefold() == raw_artist for show in inventory_shows)
            if artist_collision:
                items.append(RequestItem(
                    raw=raw,
                    kind="invalid",
                    error=(
                        f"Ambiguous Copy Request item: {raw!r} matches both an Artist/alias and a connected or inventoried volume label. "
                        f"Use [{raw}] to request the whole volume."
                    ),
                ))
            else:
                items.append(RequestItem(raw=raw, kind="volume", direct_volume=raw))
            continue

        range_match = RANGE_REQUEST_RE.match(raw)
        if range_match:
            artist = range_match.group("artist").strip()
            try:
                first, second = resolve_year_range(range_match.group("start"), range_match.group("end"))
                key, error = _artist_key(artist, matcher)
                items.append(RequestItem(raw=raw, kind="range", artist=artist, artist_key=key, start_year=first, end_year=second, error=error))
            except CopyRequestError as exc:
                items.append(RequestItem(raw=raw, kind="invalid", error=str(exc)))
            continue

        date_match = DATE_REQUEST_RE.match(raw)
        if date_match:
            artist = date_match.group("artist").strip()
            key, error = _artist_key(artist, matcher)
            items.append(RequestItem(raw=raw, kind="date", artist=artist, artist_key=key, exact_date=date_match.group("date"), error=error))
            continue

        year_match = YEAR_REQUEST_RE.match(raw)
        if year_match:
            artist = year_match.group("artist").strip()
            key, error = _artist_key(artist, matcher)
            year = int(year_match.group("year"))
            items.append(RequestItem(raw=raw, kind="year", artist=artist, artist_key=key, start_year=year, end_year=year, error=error))
            continue

        key, error = _artist_key(raw, matcher)
        items.append(RequestItem(raw=raw, kind="artist", artist=raw, artist_key=key, error=error))
    return items


def _inventory_show_artist_key(show: str, matcher: Optional[ArtistMatcher]) -> Tuple[str, str]:
    artist, date = _show_artist_date(show)
    if not artist:
        return "", date
    key, _error = _artist_key(artist, matcher)
    return key, date


def match_request_items(items: Sequence[RequestItem], inventory_shows: Sequence[str], matcher: Optional[ArtistMatcher]) -> Tuple[Dict[str, List[str]], List[str], Dict[str, str]]:
    inventory_info: Dict[str, Tuple[str, str]] = {}
    for show in inventory_shows:
        inventory_info[show] = _inventory_show_artist_key(show, matcher)

    matches: Dict[str, List[str]] = {}
    unmatched: List[str] = []
    invalid: Dict[str, str] = {}
    for item in items:
        if item.error:
            invalid[item.raw] = item.error
            continue
        if item.kind in {"path", "volume"}:
            matches[item.raw] = []
            continue
        if item.kind == "show":
            selected = [item.exact_show]
        else:
            selected = []
            for show, (artist_key, date) in inventory_info.items():
                if not artist_key or artist_key != item.artist_key:
                    continue
                if item.kind == "artist":
                    selected.append(show)
                elif item.kind == "date" and date == item.exact_date:
                    selected.append(show)
                elif item.kind in {"year", "range"} and date:
                    try:
                        year = int(date[:4])
                    except ValueError:
                        continue
                    if item.start_year <= year <= item.end_year:
                        selected.append(show)
        selected = sorted(set(selected), key=str.casefold)
        matches[item.raw] = selected
        if not selected:
            unmatched.append(item.raw)
    return matches, unmatched, invalid


# ---------------------------------------------------------------------------
# Connected-volume/source discovery
# ---------------------------------------------------------------------------

def _running_on_wsl() -> bool:
    if os.name == "nt":
        return False
    try:
        with open("/proc/version", "r", encoding="utf-8") as infile:
            text = infile.read().casefold()
        return "microsoft" in text or "wsl" in text
    except OSError:
        return False


def _candidate_mount_roots() -> List[str]:
    roots: List[str] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.isdir(root):
                roots.append(root)
        return roots
    if _running_on_wsl():
        for letter in string.ascii_lowercase:
            root = f"/mnt/{letter}"
            if os.path.isdir(root):
                roots.append(root)
        return roots

    # Native POSIX: include mounted filesystems.  Direct absolute bootlist paths
    # are also checked later, so missing helper commands do not block copying.
    mount_points: List[str] = []
    for proc_path in ("/proc/self/mounts", "/proc/mounts"):
        if not os.path.isfile(proc_path):
            continue
        try:
            with open(proc_path, "r", encoding="utf-8", errors="replace") as infile:
                for line in infile:
                    parts = line.split()
                    if len(parts) >= 2:
                        mount_points.append(parts[1].replace("\\040", " "))
        except OSError:
            pass
        if mount_points:
            break
    mount_points.extend(["/", "/Volumes", "/mnt", "/media"])
    for parent in ("/Volumes", "/mnt", "/media"):
        if os.path.isdir(parent):
            try:
                mount_points.extend(os.path.join(parent, name) for name in os.listdir(parent))
            except OSError:
                pass
    for root in mount_points:
        if root and os.path.isdir(root) and root not in roots:
            roots.append(root)
    return roots


def connected_volume_roots() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for root in _candidate_mount_roots():
        try:
            label = normalize_volume_label(resolve_volume_label(root).label)
        except Exception:
            label = ""
        result.setdefault(volume_key(label), []).append(os.path.normpath(root))
    for key in result:
        result[key] = sorted(set(result[key]), key=str.casefold)
    return result


def _physical_paths_for_volume_stored(
    volume: str,
    stored: str,
    roots: Mapping[str, Sequence[str]],
    *,
    allow_native_absolute: bool = False,
) -> Tuple[List[str], bool]:
    stored = str(stored or "").strip()
    vkey = volume_key(volume)
    candidates: List[str] = []
    volume_connected = bool(roots.get(vkey))

    if allow_native_absolute and os.name != "nt" and not _running_on_wsl() and stored and os.path.isabs(stored):
        candidates.append(os.path.normpath(stored))

    for root in roots.get(vkey, []):
        relative = stored.replace("\\", "/").lstrip("/")
        candidate = os.path.normpath(os.path.join(root, *([part for part in relative.split("/") if part] or [""])))
        candidates.append(candidate)

    unique: List[str] = []
    seen = set()
    for candidate in candidates:
        key = os.path.normcase(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique, volume_connected


def _physical_paths_for_row(row: Mapping[str, str], roots: Mapping[str, Sequence[str]]) -> Tuple[List[str], bool]:
    volume, stored = parse_volume_path_value(str(row.get("VolumePath", "") or ""))
    return _physical_paths_for_volume_stored(volume, stored, roots, allow_native_absolute=True)


def source_status_for_show(
    show: str,
    rows: Sequence[Mapping[str, str]],
    roots: Mapping[str, Sequence[str]],
    redundancy_groups: Sequence[RedundancyGroup] = (),
) -> Tuple[Optional[SourceCandidate], List[str], List[str]]:
    available: List[Tuple[int, int, SourceCandidate]] = []
    disconnected: List[str] = []
    stale: List[str] = []
    for row_index, row in enumerate(rows):
        inventory_volume, stored = parse_volume_path_value(str(row.get("VolumePath", "") or ""))
        equivalents = ordered_equivalents(inventory_volume, redundancy_groups)
        group_display = group_display_for_volume(inventory_volume, redundancy_groups)
        any_connected = False
        found = False
        connected_missing: List[str] = []

        for precedence, candidate_volume in enumerate(equivalents):
            candidates, is_connected = _physical_paths_for_volume_stored(
                candidate_volume,
                stored,
                roots,
                allow_native_absolute=(volume_key(candidate_volume) == volume_key(inventory_volume)),
            )
            any_connected = any_connected or is_connected
            candidate_found = False
            for candidate in candidates:
                try:
                    if os.path.isdir(candidate) and not os.path.islink(candidate):
                        available.append((
                            row_index,
                            precedence,
                            SourceCandidate(
                                show=show,
                                source_path=candidate,
                                volume=candidate_volume,
                                inventory_path=stored,
                                inventory_volume=inventory_volume,
                            ),
                        ))
                        candidate_found = True
                        found = True
                        break
                except OSError:
                    continue
            if candidate_found:
                # Declaration order is authoritative.  Once the highest-precedence
                # connected usable replica is found, lower-precedence members of
                # the same redundancy group are not candidates for this row.
                break
            if is_connected:
                connected_missing.append(f"[{candidate_volume}] {stored}".strip())

        if found:
            continue
        if any_connected:
            stale.extend(connected_missing or [f"[{group_display}] {stored}".strip()])
        if not any_connected or any(not roots.get(volume_key(member)) for member in equivalents):
            disconnected.append(f"[{group_display}] {stored}".strip())

    if available:
        # Preserve inventory-row order across unrelated rows, but honor the exact
        # left-to-right redundancy declaration within each row.
        available.sort(key=lambda item: (item[0], item[1], item[2].source_path.casefold()))
        return available[0][2], disconnected, stale
    return None, disconnected, stale


# ---------------------------------------------------------------------------
# Evaluation/copy
# ---------------------------------------------------------------------------

def _load_matcher(tlo_home: str) -> Optional[ArtistMatcher]:
    class _Config:
        TLOHome = tlo_home
        artist_sqlite_db_file = os.path.join(tlo_home, "TLO_DBs", "artists.sqlite")
    try:
        return load_artist_matcher(_Config())
    except Exception:
        return None


def _completed_entry_valid(entry: Mapping[str, object]) -> bool:
    destination = str(entry.get("destination_path", "") or "")
    return bool(destination and os.path.isdir(destination) and not os.path.islink(destination))


def _resolve_direct_source(item: RequestItem, roots: Mapping[str, Sequence[str]]) -> Tuple[Optional[SourceCandidate], List[str], str]:
    if item.kind == "volume":
        volume = str(item.direct_volume or "").strip()
        candidates = [os.path.normpath(path_name) for path_name in roots.get(volume_key(volume), [])]
        for candidate in candidates:
            try:
                if os.path.isdir(candidate) and not os.path.islink(candidate):
                    return SourceCandidate(show=item.raw, source_path=candidate, volume=volume, inventory_path=candidate, inventory_volume=volume), [], ""
            except OSError:
                continue
        return None, [f"[{volume}] volume is not currently connected or accessible."], ""

    if item.kind != "path":
        return None, [], "Not a direct path/volume request item."

    if item.direct_volume:
        volume = str(item.direct_volume or "").strip()
        candidates, connected = _physical_paths_for_volume_stored(volume, item.direct_path, roots, allow_native_absolute=False)
        for candidate in candidates:
            try:
                if os.path.isdir(candidate) and not os.path.islink(candidate):
                    return SourceCandidate(show=item.raw, source_path=candidate, volume=volume, inventory_path=item.direct_path, inventory_volume=volume), [], ""
            except OSError:
                continue
        if connected:
            return None, [f"[{volume}] {item.direct_path} is missing on the connected volume."], ""
        return None, [f"[{volume}] {item.direct_path} is waiting for that volume to be connected."], ""

    try:
        candidate = _normalize_direct_path_for_runtime(item.direct_path)
    except Exception as exc:
        return None, [], f"Cannot normalize direct path: {exc}"
    try:
        if os.path.isdir(candidate) and not os.path.islink(candidate):
            label = ""
            try:
                label = normalize_volume_label(resolve_volume_label(candidate).label)
            except Exception:
                pass
            return SourceCandidate(show=item.raw, source_path=os.path.normpath(candidate), volume=label, inventory_path=item.direct_path, inventory_volume=label), [], ""
        if os.path.lexists(candidate):
            return None, [], f"Direct Copy Request path is not a directory: {candidate}"
    except OSError as exc:
        return None, [], f"Cannot inspect direct Copy Request path {candidate}: {exc}"
    return None, [f"Direct path is not currently accessible: {candidate}"], ""


def _direct_destination_leaf(item: RequestItem, source: SourceCandidate) -> str:
    if item.kind == "volume":
        leaf = str(item.direct_volume or source.volume or "").strip()
    else:
        leaf = os.path.basename(os.path.normpath(source.source_path))
        if not leaf or leaf in {os.path.sep, "."}:
            leaf = str(source.volume or "").strip()
        if not leaf:
            match = re.match(r"^(?P<drive>[A-Za-z]):", str(item.direct_path or ""))
            leaf = (match.group("drive").upper() if match else "Copied Volume")
    leaf = re.sub(r'[<>:"/\\|?*]+', "_", leaf).strip(" .")
    return leaf or "Copied Folder"


def _path_is_at_or_below(path_name: str, root_name: str) -> bool:
    try:
        path_abs = os.path.normcase(os.path.abspath(os.path.normpath(path_name)))
        root_abs = os.path.normcase(os.path.abspath(os.path.normpath(root_name)))
        return os.path.commonpath([path_abs, root_abs]) == root_abs
    except (OSError, ValueError):
        return False


def _shows_covered_by_direct_source(
    rows: Sequence[Mapping[str, str]],
    roots: Mapping[str, Sequence[str]],
    redundancy_groups: Sequence[RedundancyGroup],
    source_root: str,
) -> Dict[str, Tuple[SourceCandidate, str]]:
    covered: Dict[str, Tuple[SourceCandidate, str]] = {}
    for row in rows:
        show = str(row.get("Show", "") or "").strip()
        if not show or show in covered:
            continue
        inventory_volume, stored = parse_volume_path_value(str(row.get("VolumePath", "") or ""))
        for candidate_volume in ordered_equivalents(inventory_volume, redundancy_groups):
            candidates, _connected = _physical_paths_for_volume_stored(
                candidate_volume, stored, roots,
                allow_native_absolute=(volume_key(candidate_volume) == volume_key(inventory_volume)),
            )
            found = False
            for candidate in candidates:
                try:
                    if _path_is_at_or_below(candidate, source_root) and os.path.isdir(candidate) and not os.path.islink(candidate):
                        relative = os.path.relpath(candidate, source_root)
                        covered[show] = (
                            SourceCandidate(
                                show=show,
                                source_path=candidate,
                                volume=candidate_volume,
                                inventory_path=stored,
                                inventory_volume=inventory_volume,
                            ),
                            relative,
                        )
                        found = True
                        break
                except OSError:
                    continue
            if found:
                break
    return covered


def _record_direct_completed(
    state: Dict[str, object],
    item: RequestItem,
    destination_path: str,
    source: SourceCandidate,
    *,
    method: str,
    tracked_shows: Sequence[str] = (),
) -> None:
    completed = state.setdefault("completed_direct", {})
    if not isinstance(completed, dict):
        completed = {}
        state["completed_direct"] = completed
    completed[_direct_item_key(item)] = {
        "item": item.raw,
        "kind": item.kind,
        "destination_path": os.path.abspath(destination_path),
        "source_volume": source.volume,
        "source_path": source.source_path,
        "completed_at": _now_iso(),
        "method": method,
        "tracked_shows": list(tracked_shows),
    }


def _record_shows_covered_by_direct_copy(
    state: Dict[str, object],
    rows: Sequence[Mapping[str, str]],
    roots: Mapping[str, Sequence[str]],
    redundancy_groups: Sequence[RedundancyGroup],
    source_root: str,
    destination_root: str,
    *,
    method: str,
) -> List[str]:
    covered = _shows_covered_by_direct_source(rows, roots, redundancy_groups, source_root)
    tracked: List[str] = []
    for show, (show_source, relative) in covered.items():
        destination_path = destination_root if relative in {"", "."} else os.path.join(destination_root, relative)
        _record_completed(state, show, destination_path, show_source, method=method)
        tracked.append(show)
    return sorted(tracked, key=str.casefold)


def evaluate_request(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None) -> RequestEvaluation:
    state = load_request(tlo_home, request_id)
    text = saved_request_text(tlo_home, request_id)
    rows = read_bootlist_rows(tlo_home)
    shows = sorted({row.get("Show", "").strip() for row in rows if row.get("Show", "").strip()}, key=str.casefold)
    roots = dict(connected_volume_roots() if roots is None else roots)
    inventory_volumes = []
    for row in rows:
        volume, _stored = parse_volume_path_value(str(row.get("VolumePath", "") or ""))
        if volume:
            inventory_volumes.append(volume)
    # Also allow an explicitly supplied connected-volume label even when that
    # volume is not represented in bootlist.csv.
    inventory_volumes.extend(str(key) for key in roots.keys() if str(key).strip())

    matcher = matcher if matcher is not None else _load_matcher(tlo_home)
    items = parse_request_items(text, shows, matcher, inventory_volumes=inventory_volumes)
    item_matches, unmatched, invalid = match_request_items(items, shows, matcher)
    matched_shows = sorted({show for selected in item_matches.values() for show in selected}, key=str.casefold)

    rows_by_show: Dict[str, List[Mapping[str, str]]] = {}
    for row in rows:
        show = str(row.get("Show", "") or "").strip()
        if show:
            rows_by_show.setdefault(show, []).append(row)

    redundancy_groups = load_redundancy_groups(tlo_home)
    completed_map = state.setdefault("completed", {})
    if not isinstance(completed_map, dict):
        completed_map = {}
        state["completed"] = completed_map
    completed_direct_map = state.setdefault("completed_direct", {})
    if not isinstance(completed_direct_map, dict):
        completed_direct_map = {}
        state["completed_direct"] = completed_direct_map

    completed: List[str] = []
    completed_direct_items: List[str] = []
    available: Dict[str, SourceCandidate] = {}
    direct_available: Dict[str, SourceCandidate] = {}
    waiting: Dict[str, List[str]] = {}
    direct_waiting: Dict[str, List[str]] = {}
    stale: Dict[str, List[str]] = {}
    volume_opportunities: Dict[str, int] = {}

    for item in items:
        if item.kind not in {"path", "volume"}:
            continue
        key = _direct_item_key(item)
        completed_entry = completed_direct_map.get(key)
        if isinstance(completed_entry, dict) and _completed_entry_valid(completed_entry):
            completed_direct_items.append(item.raw)
            continue
        if completed_entry is not None:
            completed_direct_map.pop(key, None)
        source, waiting_messages, error = _resolve_direct_source(item, roots)
        if error:
            invalid[item.raw] = error
        elif source is not None:
            direct_available[item.raw] = source
        elif waiting_messages:
            direct_waiting[item.raw] = waiting_messages

    for show in matched_shows:
        completed_entry = completed_map.get(_normalize_show(show))
        if isinstance(completed_entry, dict) and _completed_entry_valid(completed_entry):
            completed.append(show)
            continue
        if completed_entry is not None:
            completed_map.pop(_normalize_show(show), None)

        source, disconnected, stale_rows = source_status_for_show(
            show, rows_by_show.get(show, []), roots, redundancy_groups
        )
        if source is not None:
            available[show] = source
            continue
        if disconnected:
            waiting[show] = disconnected
            show_volume_labels = set()
            for value in disconnected:
                volume, _path = parse_volume_path_value(value)
                show_volume_labels.add(volume or "(blank volume label)")
            for label in show_volume_labels:
                volume_opportunities[label] = volume_opportunities.get(label, 0) + 1
        if stale_rows:
            stale[show] = stale_rows

    if bool(state.get("closed")):
        status = STATUS_CLOSED
    elif available or direct_available:
        status = STATUS_IN_PROGRESS
    elif waiting or direct_waiting:
        status = STATUS_WAITING
    elif stale:
        status = STATUS_IN_PROGRESS
    elif unmatched or invalid:
        status = STATUS_MATCHES_COMPLETE
    else:
        status = STATUS_COMPLETE

    state["status"] = status
    state["summary"] = {
        "request_items": len(items),
        "matched": len(matched_shows),
        "completed": len(completed),
        "completed_direct": len(completed_direct_items),
        "available": len(available),
        "direct_available": len(direct_available),
        "waiting": len(waiting),
        "direct_waiting": len(direct_waiting),
        "stale": len(stale),
        "unmatched": len(unmatched),
        "invalid": len(invalid),
    }
    save_request(tlo_home, state)
    return RequestEvaluation(
        request_id=request_id,
        name=str(state.get("name", request_id)),
        destination=str(state.get("destination", "") or ""),
        status=status,
        items=items,
        item_matches=item_matches,
        matched_shows=matched_shows,
        completed_shows=completed,
        completed_direct_items=completed_direct_items,
        available=available,
        direct_available=direct_available,
        waiting=waiting,
        direct_waiting=direct_waiting,
        stale_missing=stale,
        unmatched_items=unmatched,
        invalid_items=invalid,
        volume_opportunities=dict(sorted(volume_opportunities.items(), key=lambda item: (-item[1], item[0].casefold()))),
    )


def _raise_walk_error(error: OSError) -> None:
    raise error


def _normalized_path_key(path_name: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path_name or ""))))


def _source_is_volume_root(
    item: RequestItem,
    source_path: str,
    roots: Optional[Mapping[str, Sequence[str]]] = None,
) -> bool:
    """Return True when a direct source is an actual/resolved volume root.

    Whole-volume safety is based on what the source *is*, not on whether the
    request used ``[Volume]`` syntax or spelled the root as a direct path.
    """
    if item.kind == "volume":
        return True
    source_key = _normalized_path_key(source_path)
    try:
        if os.path.ismount(source_path):
            return True
    except OSError:
        pass
    # Windows drive roots are recognizable even when tests run on another OS.
    raw = str(item.direct_path or "").strip()
    if re.fullmatch(r"[A-Za-z]:[\\/]?", raw):
        return True
    for root_values in (roots or {}).values():
        for root in root_values or ():
            if source_key == _normalized_path_key(str(root)):
                return True
    return False


def _volume_ignore_names(
    item: RequestItem,
    source_path: str = "",
    roots: Optional[Mapping[str, Sequence[str]]] = None,
) -> set[str]:
    return set(VOLUME_ROOT_EXCLUDED_NAMES) if _source_is_volume_root(item, source_path, roots) else set()


def _walk_tree_size_and_reject_links(root: str, *, ignore_root_names: Sequence[str] = ()) -> int:
    total = 0
    ignored = {str(name).casefold() for name in ignore_root_names}
    root_norm = os.path.normcase(os.path.abspath(os.path.normpath(root)))
    try:
        for current, dir_names, file_names in os.walk(root, followlinks=False, onerror=_raise_walk_error):
            if os.path.normcase(os.path.abspath(os.path.normpath(current))) == root_norm and ignored:
                dir_names[:] = [name for name in dir_names if name.casefold() not in ignored]
                file_names = [name for name in file_names if name.casefold() not in ignored]
            for name in list(dir_names):
                path_name = os.path.join(current, name)
                if os.path.islink(path_name):
                    raise CopyRequestError(f"Source tree contains a symbolic link: {path_name}")
            for name in file_names:
                path_name = os.path.join(current, name)
                if os.path.islink(path_name):
                    raise CopyRequestError(f"Source tree contains a symbolic link: {path_name}")
                try:
                    total += os.path.getsize(path_name)
                except OSError as exc:
                    raise CopyRequestError(f"Cannot read source file size: {path_name}: {exc}") from exc
    except OSError as exc:
        raise CopyRequestError(f"Cannot enumerate source tree {root}: {exc}") from exc
    return total


def _copytree_ignore_root_names(source_root: str, ignored_names: Sequence[str]):
    ignored = {str(name).casefold() for name in ignored_names}
    source_norm = os.path.normcase(os.path.abspath(os.path.normpath(source_root)))
    if not ignored:
        return None

    def ignore(current: str, names: Sequence[str]) -> List[str]:
        current_norm = os.path.normcase(os.path.abspath(os.path.normpath(current)))
        if current_norm != source_norm:
            return []
        return [name for name in names if str(name).casefold() in ignored]

    return ignore


def _paths_same_existing(left: str, right: str) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return os.path.normcase(os.path.abspath(os.path.normpath(left))) == os.path.normcase(os.path.abspath(os.path.normpath(right)))


def _process_start_token(pid: int) -> str:
    """Return a stable token for one process lifetime when the platform exposes it."""
    try:
        pid = int(pid)
        if pid <= 0:
            return ""
    except (TypeError, ValueError):
        return ""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return ""
            try:
                creation = wintypes.FILETIME(); exit_time = wintypes.FILETIME(); kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
                if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
                    return ""
                value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
                return f"win:{value}"
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return ""
    stat_path = f"/proc/{pid}/stat"
    try:
        with open(stat_path, "r", encoding="ascii", errors="replace") as infile:
            value = infile.read()
        # field 22 is process start time in clock ticks; split after the command's closing ')'.
        rest = value[value.rfind(")") + 2:].split()
        if len(rest) >= 20:
            return f"proc:{rest[19]}"
    except OSError:
        pass
    # macOS and other POSIX systems may not expose /proc.  ps lstart is stable
    # for the lifetime of a process and protects against PID reuse there too.
    if os.name == "posix":
        try:
            value = subprocess.check_output(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()
            if value:
                return f"ps:{value}"
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def _copy_owner_payload(request_id: str) -> Dict[str, object]:
    pid = os.getpid()
    return {
        "request_id": str(request_id or ""),
        "pid": pid,
        "hostname": socket.gethostname(),
        "started_at": _now_iso(),
        "process_start_token": _process_start_token(pid),
    }


def _pid_is_alive(pid: int) -> bool:
    try:
        pid = int(pid)
        if pid <= 0:
            return False
    except (ValueError, TypeError):
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            ERROR_ACCESS_DENIED = 5
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.set_last_error(0)
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return ctypes.get_last_error() == ERROR_ACCESS_DENIED
            try:
                code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return True
                return int(code.value) == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False


def _read_json_file(path_name: str) -> Dict[str, object]:
    try:
        if os.path.islink(path_name) or os.path.getsize(path_name) > 64 * 1024:
            return {}
        with open(path_name, "r", encoding="utf-8") as infile:
            value = json.load(infile)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _owner_is_live(payload: Mapping[str, object]) -> bool:
    host = str(payload.get("hostname", "") or "")
    try:
        pid = int(payload.get("pid", 0) or 0)
    except (TypeError, ValueError):
        return False
    if not host or host != socket.gethostname() or not _pid_is_alive(pid):
        return False
    expected = str(payload.get("process_start_token", "") or "")
    actual = _process_start_token(pid)
    return not expected or not actual or expected == actual


def stale_lock_details(path_name: str) -> Dict[str, object]:
    """Describe a stale Copy Request lock that may be cleared with user confirmation."""
    payload = _read_json_file(path_name)
    if not payload:
        return {}
    host = str(payload.get("hostname", "") or "")
    if host == socket.gethostname():
        if _owner_is_live(payload):
            return {}
        return {"path": path_name, "hostname": host or "this computer", "age_seconds": 0.0, "same_host": True}
    raw_when = str(payload.get("started_at", "") or payload.get("created_at", "") or "")
    age = 0.0
    try:
        when = datetime.fromisoformat(raw_when.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - when.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        try:
            age = max(0.0, __import__("time").time() - os.path.getmtime(path_name))
        except OSError:
            age = 0.0
    if age < FOREIGN_LOCK_STALE_SECONDS:
        return {}
    return {"path": path_name, "hostname": host or "another computer", "age_seconds": age, "same_host": False}


def clear_stale_lock(path_name: str) -> bool:
    """Clear only a lock that stale_lock_details currently identifies as stale."""
    if not stale_lock_details(path_name):
        return False
    try:
        os.remove(path_name)
        return True
    except OSError:
        return False


def _acquire_exclusive_lock(path_name: str, request_id: str) -> str:
    """Acquire a local lock file, recovering only a dead same-host owner."""
    os.makedirs(os.path.dirname(path_name) or ".", exist_ok=True)
    payload = _copy_owner_payload(request_id)
    for _attempt in range(2):
        try:
            fd = os.open(path_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = _read_json_file(path_name)
            if existing and str(existing.get("hostname", "")) == socket.gethostname() and not _owner_is_live(existing):
                try:
                    os.remove(path_name)
                except OSError:
                    pass
                continue
            raise CopyRequestError(f"Copy Request is already active for this request/destination: {path_name}")
        except OSError as exc:
            raise CopyRequestError(f"Cannot acquire Copy Request lock {path_name}: {exc}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as outfile:
                json.dump(payload, outfile, sort_keys=True)
                outfile.write("\n")
                outfile.flush()
                os.fsync(outfile.fileno())
            return path_name
        except Exception:
            try:
                os.remove(path_name)
            except OSError:
                pass
            raise
    raise CopyRequestError(f"Cannot recover Copy Request lock: {path_name}")


def _release_exclusive_lock(path_name: str) -> None:
    try:
        os.remove(path_name)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _destination_lock_path(destination: str, request_id: str) -> str:
    del request_id
    # One lock per destination, shared by all requests, prevents two independent
    # Copy Requests from publishing or recovering trees in the same destination
    # concurrently.
    return os.path.join(destination, f"{DESTINATION_LOCK_PREFIX}destination.lock")


def destination_stale_lock_details(destination: str) -> Dict[str, object]:
    return stale_lock_details(_destination_lock_path(destination, ""))


def clear_destination_stale_lock(destination: str) -> bool:
    return clear_stale_lock(_destination_lock_path(destination, ""))


def _set_pending_copy(tlo_home: str, state: Dict[str, object], **fields: object) -> None:
    pending = dict(fields)
    pending["updated_at"] = _now_iso()
    state["pending_copy"] = pending
    save_request(tlo_home, state)


def _clear_pending_copy(tlo_home: str, state: Dict[str, object]) -> None:
    state["pending_copy"] = {}
    save_request(tlo_home, state)


def _temp_marker_matches(path_name: str, request_id: str) -> bool:
    payload = _read_json_file(os.path.join(path_name, COPY_TEMP_MARKER_FILENAME))
    return str(payload.get("request_id", "") or "") == str(request_id or "")


def _recover_pending_copy(tlo_home: str, state: Dict[str, object]) -> List[str]:
    """Recover only paths explicitly recorded by this request's state."""
    pending = state.get("pending_copy")
    if not isinstance(pending, dict) or not pending:
        return []
    recovered: List[str] = []
    request_id = str(state.get("request_id", "") or "")
    target = str(pending.get("target", "") or "")
    temp_path = str(pending.get("temp", "") or "")
    source = str(pending.get("source", "") or "")

    if temp_path and os.path.isdir(temp_path) and not os.path.islink(temp_path) and _temp_marker_matches(temp_path, request_id):
        shutil.rmtree(temp_path, ignore_errors=True)
        recovered.append(temp_path)

    if target and os.path.isdir(target) and not os.path.islink(target):
        marker = os.path.join(target, COPY_TEMP_MARKER_FILENAME)
        if os.path.isfile(marker) and _temp_marker_matches(target, request_id):
            # A verified tree may already have been published immediately before
            # a crash. Keep it; remove only the ownership marker so normal
            # planning can recognize it as an exact existing copy.
            try:
                if source and os.path.isdir(source) and directory_trees_exactly_match(
                    source, target, ignore_root_names={COPY_TEMP_MARKER_FILENAME}
                ):
                    os.remove(marker)
                    recovered.append(target)
            except (OSError, CopyRequestError):
                pass
        else:
            try:
                if not os.listdir(target):
                    os.rmdir(target)
                    recovered.append(target)
            except OSError:
                pass

    state["pending_copy"] = {}
    save_request(tlo_home, state)
    return recovered


def _cleanup_stale_copy_temps(destination: str) -> List[str]:
    """Remove only marked temp trees whose same-host owner process is gone."""
    removed: List[str] = []
    try:
        entries = list(os.scandir(destination))
    except OSError:
        return removed
    for entry in entries:
        if not entry.name.startswith(STALE_COPY_PREFIX):
            continue
        path_name = entry.path
        marker = os.path.join(path_name, COPY_TEMP_MARKER_FILENAME)
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
            payload = _read_json_file(marker)
            if not payload:
                continue
            host = str(payload.get("hostname", "") or "")
            if host:
                if host != socket.gethostname() or _owner_is_live(payload):
                    continue
            # Legacy Build 506 markers did not contain pid/hostname and are
            # safe to treat as stale because no Build 507 pass creates them.
            shutil.rmtree(path_name)
            removed.append(path_name)
        except OSError:
            continue
    return removed

def _reserve_copy_target(target: str) -> None:
    try:
        os.mkdir(target)
    except FileExistsError as exc:
        raise CopyRequestError(f"Destination appeared during copy: {target}") from exc
    except OSError as exc:
        raise CopyRequestError(f"Cannot reserve destination folder {target}: {exc}") from exc


def _create_owned_copy_temp(destination: str, request_id: str) -> str:
    request_token = SAFE_ID_RE.sub("_", str(request_id or "request")).strip("._-") or "request"
    temp_path = tempfile.mkdtemp(prefix=f"{STALE_COPY_PREFIX}{request_token}-", dir=destination)
    marker = os.path.join(temp_path, COPY_TEMP_MARKER_FILENAME)
    try:
        with open(marker, "w", encoding="utf-8", newline="") as outfile:
            payload = _copy_owner_payload(request_id)
            payload["created_at"] = payload.pop("started_at")
            json.dump(payload, outfile, sort_keys=True)
            outfile.write("\n")
    except Exception:
        shutil.rmtree(temp_path, ignore_errors=True)
        raise
    return temp_path


def _copy_into_temp_target(
    source: str,
    temp_target: str,
    *,
    ignore_root_names: Sequence[str] = (),
    cancel_check: Optional[Callable[[], bool]] = None,
) -> None:
    def copy_file(src: str, dst: str, *, follow_symlinks: bool = True):
        if cancel_check is not None and cancel_check():
            raise CopyRequestCancelled("Copy Request cancelled by user.")
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)

    if cancel_check is not None and cancel_check():
        raise CopyRequestCancelled("Copy Request cancelled by user.")
    shutil.copytree(
        source,
        temp_target,
        symlinks=False,
        dirs_exist_ok=True,
        ignore=_copytree_ignore_root_names(source, ignore_root_names),
        copy_function=copy_file,
    )


def _finalize_reserved_copy(temp_target: str, target: str) -> None:
    """Publish a verified temp tree without overwriting a foreign target."""
    if os.path.islink(target) or not os.path.isdir(target):
        raise CopyRequestError(f"Reserved destination changed before finalize: {target}")
    try:
        if os.listdir(target):
            raise CopyRequestError(f"Reserved destination was modified during copy: {target}")
    except OSError as exc:
        raise CopyRequestError(f"Cannot verify reserved destination before finalize: {target}: {exc}") from exc

    if os.name == "nt":
        # Windows cannot replace an existing directory with os.replace(). Remove
        # only TLO's still-empty reservation, then rename immediately. If a
        # foreign entry wins that tiny race, os.replace fails; it is never deleted.
        try:
            os.rmdir(target)
        except OSError as exc:
            raise CopyRequestError(f"Cannot release empty destination reservation {target}: {exc}") from exc
    try:
        os.replace(temp_target, target)
    except OSError as exc:
        raise CopyRequestError(f"Cannot finalize verified Copy Request tree {target}: {exc}") from exc


def _record_completed(state: Dict[str, object], show: str, destination_path: str, source: SourceCandidate, *, method: str) -> None:
    completed = state.setdefault("completed", {})
    if not isinstance(completed, dict):
        completed = {}
        state["completed"] = completed
    completed[_normalize_show(show)] = {
        "show": show,
        "destination_path": os.path.abspath(destination_path),
        "source_volume": source.volume,
        "inventory_volume": source.inventory_volume or source.volume,
        "source_inventory_path": source.inventory_path,
        "source_path": source.source_path,
        "completed_at": _now_iso(),
        "method": method,
    }


def _report_lines(evaluation: RequestEvaluation, result: Optional[CopyPassResult] = None) -> List[str]:
    lines = [
        f"Copy Request: {evaluation.name}",
        f"Request ID: {evaluation.request_id}",
        f"Destination: {evaluation.destination}",
        f"Status: {evaluation.status if result is None else result.status}",
        f"Generated: {_now_iso()}",
        "",
        f"Request items: {len(evaluation.items)}",
        f"Unique matched shows: {len(evaluation.matched_shows)}",
        f"Already completed shows: {len(evaluation.completed_shows)}",
        f"Already completed direct items: {len(evaluation.completed_direct_items)}",
        f"Available matched shows now: {len(evaluation.available)}",
        f"Available direct path/volume items now: {len(evaluation.direct_available)}",
        f"Waiting matched shows: {len(evaluation.waiting)}",
        f"Waiting direct path/volume items: {len(evaluation.direct_waiting)}",
        f"Stale/missing connected sources: {len(evaluation.stale_missing)}",
        f"Unmatched request items: {len(evaluation.unmatched_items)}",
        f"Invalid request items: {len(evaluation.invalid_items)}",
    ]
    if result is not None:
        lines.extend([
            f"Copied this pass: {len(result.copied)}",
            f"Already satisfied at destination: {len(result.already_satisfied)}",
            f"Copy failures this pass: {len(result.failures)}",
            f"Required bytes this pass: {result.required_bytes}",
            f"Destination free bytes at preflight: {result.free_bytes}",
        ])
    lines.extend(["", "REMAINING SHOWS BY SOURCE VOLUME"])
    if evaluation.volume_opportunities:
        for volume, count in evaluation.volume_opportunities.items():
            lines.append(f"{volume}: {count} show(s)")
    else:
        lines.append("None")

    if result is not None:
        lines.extend(["", "COPIED"])
        if result.copied:
            for show, source, destination in result.copied:
                inventory_volume, actual_volume = result.source_details.get(show, ("", ""))
                lines.append(show)
                if inventory_volume:
                    lines.append(f"  Inventoried volume: {inventory_volume}")
                if actual_volume:
                    lines.append(f"  Actual source volume: {actual_volume}")
                lines.extend([f"  From: {source}", f"  To:   {destination}"])
        else:
            lines.append("None")
        lines.extend(["", "ALREADY SATISFIED"])
        if result.already_satisfied:
            for show, destination in result.already_satisfied:
                lines.extend([show, f"  At: {destination}"])
        else:
            lines.append("None")

    if any(item.kind == "volume" for item in evaluation.items):
        lines.extend([
            "",
            "WHOLE-VOLUME EXCLUSIONS",
            "Root-level OS folders omitted from sizing, copy, and verification: " + ", ".join(sorted(VOLUME_ROOT_EXCLUDED_NAMES)),
        ])

    lines.extend(["", "WAITING FOR DISCONNECTED VOLUMES / DIRECT PATHS"])
    if evaluation.waiting or evaluation.direct_waiting:
        for show, sources in sorted(evaluation.waiting.items(), key=lambda item: item[0].casefold()):
            lines.append(show)
            for source in sources:
                lines.append(f"  {source}")
        for raw, sources in sorted(evaluation.direct_waiting.items(), key=lambda item: item[0].casefold()):
            lines.append(raw)
            for source in sources:
                lines.append(f"  {source}")
    else:
        lines.append("None")

    lines.extend(["", "STALE / MISSING CONNECTED SOURCES"])
    if evaluation.stale_missing:
        for show, sources in sorted(evaluation.stale_missing.items(), key=lambda item: item[0].casefold()):
            lines.append(show)
            for source in sources:
                lines.append(f"  {source}")
    else:
        lines.append("None")

    lines.extend(["", "UNMATCHED REQUEST ITEMS"])
    lines.extend(evaluation.unmatched_items or ["None"])
    lines.extend(["", "INVALID REQUEST ITEMS"])
    if evaluation.invalid_items:
        for raw, error in evaluation.invalid_items.items():
            lines.append(f"{raw}: {error}")
    else:
        lines.append("None")

    if result is not None:
        lines.extend(["", "FAILED COPY ATTEMPTS"])
        if result.insufficient_space:
            lines.append("No copies were attempted because destination free space was insufficient for the entire current pass.")
        if result.failures:
            for show, reason in result.failures:
                lines.append(f"{show}: {reason}")
        elif not result.insufficient_space:
            lines.append("None")
    return lines


def write_request_reports(tlo_home: str, evaluation: RequestEvaluation, result: Optional[CopyPassResult] = None) -> str:
    directory = request_dir(tlo_home, evaluation.request_id)
    os.makedirs(directory, exist_ok=True)
    os.makedirs(os.path.join(directory, REPORTS_DIRNAME), exist_ok=True)
    text = "\n".join(_report_lines(evaluation, result)).rstrip() + "\n"
    latest = os.path.join(directory, LATEST_REPORT_FILENAME)
    _atomic_write_text(latest, text)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    history_path = os.path.join(directory, REPORTS_DIRNAME, f"pass-{timestamp}.txt")
    _atomic_write_text(history_path, text)

    copied_lines: List[str] = []
    try:
        state = load_request(tlo_home, evaluation.request_id)
    except CopyRequestError:
        state = {}
    completed_state = state.get("completed") if isinstance(state.get("completed"), dict) else {}
    for entry in sorted(completed_state.values(), key=lambda item: str(item.get("show", "")).casefold() if isinstance(item, dict) else ""):
        if not isinstance(entry, dict):
            continue
        copied_lines.append(
            f"{entry.get('show', '')}\t{entry.get('method', 'completed')}\t{entry.get('source_path', '')}\t{entry.get('destination_path', '')}"
        )
    completed_direct = state.get("completed_direct") if isinstance(state.get("completed_direct"), dict) else {}
    for entry in sorted(completed_direct.values(), key=lambda item: str(item.get("item", "")).casefold() if isinstance(item, dict) else ""):
        if not isinstance(entry, dict):
            continue
        copied_lines.append(
            f"DIRECT: {entry.get('item', '')}\t{entry.get('method', 'completed')}\t{entry.get('source_path', '')}\t{entry.get('destination_path', '')}"
        )
    _atomic_write_text(os.path.join(directory, COPIED_REPORT_FILENAME), "\n".join(copied_lines) + ("\n" if copied_lines else ""))

    pending_lines: List[str] = []
    for show, sources in evaluation.waiting.items():
        pending_lines.append(show + "\t" + " | ".join(sources))
    for raw, sources in evaluation.direct_waiting.items():
        pending_lines.append("DIRECT: " + raw + "\t" + " | ".join(sources))
    for show, sources in evaluation.stale_missing.items():
        pending_lines.append(show + "\tSTALE/MISSING\t" + " | ".join(sources))
    _atomic_write_text(os.path.join(directory, PENDING_REPORT_FILENAME), "\n".join(pending_lines) + ("\n" if pending_lines else ""))

    failed_lines = list(evaluation.unmatched_items)
    failed_lines.extend(f"{raw}\t{error}" for raw, error in evaluation.invalid_items.items())
    if result is not None:
        failed_lines.extend(f"{show}\t{reason}" for show, reason in result.failures)
    _atomic_write_text(os.path.join(directory, FAILED_REPORT_FILENAME), "\n".join(failed_lines) + ("\n" if failed_lines else ""))
    return latest


def _preflight_direct_items(
    evaluation: RequestEvaluation,
    destination: str,
    rows: Sequence[Mapping[str, str]],
    roots: Mapping[str, Sequence[str]],
    redundancy_groups: Sequence[RedundancyGroup],
) -> Tuple[
    List[Tuple[str, RequestItem, SourceCandidate, str, int]],
    List[Tuple[str, RequestItem, SourceCandidate, str]],
    List[Tuple[str, str]],
    set[str],
    set[str],
]:
    item_by_raw = {item.raw: item for item in evaluation.items if item.kind in {"path", "volume"}}
    candidates: List[Tuple[str, RequestItem, SourceCandidate, str, int]] = []
    exact_existing: List[Tuple[str, RequestItem, SourceCandidate, str]] = []
    failures: List[Tuple[str, str]] = []
    target_to_items: Dict[str, List[str]] = {}

    for raw, source in evaluation.direct_available.items():
        item = item_by_raw.get(raw)
        if item is None:
            failures.append((raw, "Internal error: direct Copy Request item is missing."))
            continue
        if _path_is_at_or_below(destination, source.source_path) or _path_is_at_or_below(source.source_path, destination):
            failures.append((raw, "Copy Request destination and direct source must not overlap; no copy was made."))
            continue
        target = os.path.join(destination, _direct_destination_leaf(item, source))
        target_key = os.path.normcase(os.path.abspath(target))
        target_to_items.setdefault(target_key, []).append(raw)
        ignore_names = _volume_ignore_names(item, source.source_path, roots)
        try:
            size = _walk_tree_size_and_reject_links(source.source_path, ignore_root_names=ignore_names)
        except CopyRequestError as exc:
            failures.append((raw, str(exc)))
            continue
        if os.path.lexists(target):
            exact = False
            if os.path.isdir(target) and not os.path.islink(target):
                try:
                    _walk_tree_size_and_reject_links(target, ignore_root_names=ignore_names)
                    exact = directory_trees_exactly_match(source.source_path, target, ignore_root_names=ignore_names)
                except CopyRequestError:
                    exact = False
            if exact:
                exact_existing.append((raw, item, source, target))
                continue
            failures.append((raw, f"Destination collision: {target}"))
            continue
        candidates.append((raw, item, source, target, size))

    duplicate_targets = {key for key, labels in target_to_items.items() if len(labels) > 1}
    retained: List[Tuple[str, RequestItem, SourceCandidate, str, int]] = []
    for plan in candidates:
        raw, _item, _source, target, _size = plan
        if os.path.normcase(os.path.abspath(target)) in duplicate_targets:
            failures.append((raw, f"Two direct Copy Request items would use the same destination folder name: {os.path.basename(target)}"))
        else:
            retained.append(plan)

    covered_shows: set[str] = set()
    reserved_targets: set[str] = set()
    for raw, item, source, target in exact_existing:
        del raw, item
        reserved_targets.add(os.path.normcase(os.path.abspath(target)))
        covered_shows.update(_shows_covered_by_direct_source(rows, roots, redundancy_groups, source.source_path).keys())
    for raw, item, source, target, _size in retained:
        del raw, item
        reserved_targets.add(os.path.normcase(os.path.abspath(target)))
        covered_shows.update(_shows_covered_by_direct_source(rows, roots, redundancy_groups, source.source_path).keys())
    return retained, exact_existing, failures, covered_shows, reserved_targets


def _copy_available_unlocked(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None, cancel_check: Optional[Callable[[], bool]] = None) -> CopyPassResult:
    state = load_request(tlo_home, request_id)
    if bool(state.get("closed")):
        raise CopyRequestError("This Copy Request is Closed and cannot be continued.")
    effective_roots = dict(connected_volume_roots() if roots is None else roots)
    evaluation = evaluate_request(tlo_home, request_id, roots=effective_roots, matcher=matcher)
    destination = evaluation.destination
    if not os.path.isdir(destination):
        raise CopyRequestError(f"Destination is not accessible: {destination}")

    rows = read_bootlist_rows(tlo_home)
    redundancy_groups = load_redundancy_groups(tlo_home)
    result = CopyPassResult(request_id=request_id, status=evaluation.status)
    stale_removed = _cleanup_stale_copy_temps(destination)
    if stale_removed:
        evaluation.preview_notes.append(f"Removed {len(stale_removed)} stale .tlo-copy-* temporary item(s) from the destination.")

    direct_plans, direct_existing, direct_failures, covered_shows, direct_targets = _preflight_direct_items(
        evaluation, destination, rows, effective_roots, redundancy_groups
    )
    result.failures.extend(direct_failures)

    # Existing exact direct trees satisfy both the direct item and every inventoried
    # show fully contained by that tree.  Recording this before normal show planning
    # prevents a mixed request from scheduling the same material twice.
    for raw, item, source, target in direct_existing:
        tracked = _record_shows_covered_by_direct_copy(
            state, rows, effective_roots, redundancy_groups, source.source_path, target,
            method="covered by existing direct exact match",
        )
        _record_direct_completed(
            state, item, target, source, method="existing direct exact match", tracked_shows=tracked
        )
        result.already_satisfied.append((raw, target))
        result.source_details[raw] = (source.inventory_volume or source.volume, source.volume)

    plans: List[Tuple[str, SourceCandidate, str, int]] = []
    target_to_shows: Dict[str, List[str]] = {}

    # Preflight normal matched shows after direct-tree coverage has been determined.
    for show, source in evaluation.available.items():
        if show in covered_shows:
            continue
        target = os.path.join(destination, os.path.basename(os.path.normpath(source.source_path)))
        target_key = os.path.normcase(os.path.abspath(target))
        if target_key in direct_targets:
            result.failures.append((show, f"Destination folder is reserved by a direct path/volume request: {target}"))
            continue
        target_to_shows.setdefault(target_key, []).append(show)
        try:
            source_size = _walk_tree_size_and_reject_links(source.source_path)
        except CopyRequestError as exc:
            result.failures.append((show, str(exc)))
            continue
        if os.path.lexists(target):
            if _paths_same_existing(source.source_path, target):
                result.failures.append((show, "Destination already is the source - no copy made."))
                continue
            exact_existing = False
            if os.path.isdir(target) and not os.path.islink(target):
                try:
                    _walk_tree_size_and_reject_links(target)
                    exact_existing = directory_trees_exactly_match(source.source_path, target)
                except CopyRequestError:
                    exact_existing = False
            if exact_existing:
                result.already_satisfied.append((show, target))
                result.source_details[show] = (source.inventory_volume or source.volume, source.volume)
                _record_completed(state, show, target, source, method="existing exact match")
                continue
            result.failures.append((show, f"Destination collision: {target}"))
            continue
        plans.append((show, source, target, source_size))

    duplicate_targets = {target for target, shows in target_to_shows.items() if len(shows) > 1}
    if duplicate_targets:
        retained: List[Tuple[str, SourceCandidate, str, int]] = []
        for plan in plans:
            show, _source, target, _size = plan
            if os.path.normcase(os.path.abspath(target)) in duplicate_targets:
                result.failures.append((show, f"Two requested shows would use the same destination folder name: {os.path.basename(target)}"))
            else:
                retained.append(plan)
        plans = retained

    result.required_bytes = sum(plan[4] for plan in direct_plans) + sum(plan[3] for plan in plans)
    try:
        result.free_bytes = shutil.disk_usage(destination).free
    except OSError as exc:
        raise CopyRequestError(f"Cannot determine free space for destination: {destination}: {exc}") from exc

    if result.required_bytes > result.free_bytes:
        result.insufficient_space = True
        save_request(tlo_home, state)
        evaluation = evaluate_request(tlo_home, request_id, roots=effective_roots, matcher=matcher)
        result.status = evaluation.status
        result.report_path = write_request_reports(tlo_home, evaluation, result)
        return result

    save_request(tlo_home, state)

    # Direct path/volume items copy first. Each operation is persisted before
    # touching the destination so an unhandled interruption can be recovered
    # safely on the next pass.
    for raw, item, source, target, _size in direct_plans:
        if cancel_check is not None and cancel_check():
            result.cancelled = True
            break
        reserved = False
        temp_target = ""
        ignore_names = _volume_ignore_names(item, source.source_path, effective_roots)
        try:
            _set_pending_copy(tlo_home, state, item=raw, kind="direct", source=source.source_path, target=target, temp="", phase="prepared")
            _reserve_copy_target(target)
            reserved = True
            _set_pending_copy(tlo_home, state, item=raw, kind="direct", source=source.source_path, target=target, temp="", phase="reserved")
            temp_target = _create_owned_copy_temp(destination, request_id)
            _set_pending_copy(tlo_home, state, item=raw, kind="direct", source=source.source_path, target=target, temp=temp_target, phase="copying")
            copy_kwargs = {"ignore_root_names": ignore_names}
            if cancel_check is not None:
                copy_kwargs["cancel_check"] = cancel_check
            _copy_into_temp_target(source.source_path, temp_target, **copy_kwargs)
            verify_ignores = set(ignore_names) | {COPY_TEMP_MARKER_FILENAME}
            if not directory_trees_exactly_match(source.source_path, temp_target, ignore_root_names=verify_ignores):
                raise CopyRequestError("Copied direct tree verification failed.")
            _set_pending_copy(tlo_home, state, item=raw, kind="direct", source=source.source_path, target=target, temp=temp_target, phase="verified")
            _finalize_reserved_copy(temp_target, target)
            temp_target = ""
            reserved = False
            _set_pending_copy(tlo_home, state, item=raw, kind="direct", source=source.source_path, target=target, temp="", phase="published")
            tracked = _record_shows_covered_by_direct_copy(
                state, rows, effective_roots, redundancy_groups, source.source_path, target,
                method="covered by direct copy",
            )
            _record_direct_completed(state, item, target, source, method="direct copy", tracked_shows=tracked)
            save_request(tlo_home, state)
            try:
                os.remove(os.path.join(target, COPY_TEMP_MARKER_FILENAME))
            except OSError:
                pass
            _clear_pending_copy(tlo_home, state)
            result.copied.append((raw, source.source_path, target))
            result.source_details[raw] = (source.inventory_volume or source.volume, source.volume)
        except BaseException as exc:
            if temp_target and os.path.isdir(temp_target) and not os.path.islink(temp_target) and _temp_marker_matches(temp_target, request_id):
                shutil.rmtree(temp_target, ignore_errors=True)
            if reserved:
                try:
                    os.rmdir(target)
                except OSError:
                    pass
            try:
                _clear_pending_copy(tlo_home, state)
            except Exception:
                pass
            if isinstance(exc, CopyRequestCancelled):
                result.cancelled = True
                break
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            result.failures.append((raw, str(exc)))

    if not result.cancelled:
        for show, source, target, _size in plans:
            if cancel_check is not None and cancel_check():
                result.cancelled = True
                break
            reserved = False
            temp_target = ""
            try:
                _set_pending_copy(tlo_home, state, item=show, kind="show", source=source.source_path, target=target, temp="", phase="prepared")
                _reserve_copy_target(target)
                reserved = True
                _set_pending_copy(tlo_home, state, item=show, kind="show", source=source.source_path, target=target, temp="", phase="reserved")
                temp_target = _create_owned_copy_temp(destination, request_id)
                _set_pending_copy(tlo_home, state, item=show, kind="show", source=source.source_path, target=target, temp=temp_target, phase="copying")
                if cancel_check is None:
                    _copy_into_temp_target(source.source_path, temp_target)
                else:
                    _copy_into_temp_target(source.source_path, temp_target, cancel_check=cancel_check)
                if not directory_trees_exactly_match(
                    source.source_path, temp_target, ignore_root_names={COPY_TEMP_MARKER_FILENAME}
                ):
                    raise CopyRequestError("Copied tree verification failed.")
                _set_pending_copy(tlo_home, state, item=show, kind="show", source=source.source_path, target=target, temp=temp_target, phase="verified")
                _finalize_reserved_copy(temp_target, target)
                temp_target = ""
                reserved = False
                _set_pending_copy(tlo_home, state, item=show, kind="show", source=source.source_path, target=target, temp="", phase="published")
                _record_completed(state, show, target, source, method="copied")
                save_request(tlo_home, state)
                try:
                    os.remove(os.path.join(target, COPY_TEMP_MARKER_FILENAME))
                except OSError:
                    pass
                _clear_pending_copy(tlo_home, state)
                result.copied.append((show, source.source_path, target))
                result.source_details[show] = (source.inventory_volume or source.volume, source.volume)
            except BaseException as exc:
                if temp_target and os.path.isdir(temp_target) and not os.path.islink(temp_target) and _temp_marker_matches(temp_target, request_id):
                    shutil.rmtree(temp_target, ignore_errors=True)
                if reserved:
                    try:
                        os.rmdir(target)
                    except OSError:
                        pass
                try:
                    _clear_pending_copy(tlo_home, state)
                except Exception:
                    pass
                if isinstance(exc, CopyRequestCancelled):
                    result.cancelled = True
                    break
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                result.failures.append((show, str(exc)))

    evaluation = evaluate_request(tlo_home, request_id, roots=effective_roots, matcher=matcher)
    result.status = evaluation.status
    state = load_request(tlo_home, request_id)
    history = state.setdefault("history", [])
    if isinstance(history, list):
        history.append({
            "when": _now_iso(),
            "copied": len(result.copied),
            "already_satisfied": len(result.already_satisfied),
            "failures": len(result.failures),
            "required_bytes": result.required_bytes,
            "free_bytes": result.free_bytes,
            "status": result.status,
            "cancelled": result.cancelled,
        })
        del history[:-200]
    state["status"] = result.status
    save_request(tlo_home, state)
    result.report_path = write_request_reports(tlo_home, evaluation, result)
    return result


def copy_available(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None, cancel_check: Optional[Callable[[], bool]] = None) -> CopyPassResult:
    """Run one recoverable Copy Request pass with request/destination locks."""
    state = load_request(tlo_home, request_id)
    if bool(state.get("closed")):
        raise CopyRequestError("This Copy Request is Closed and cannot be continued.")
    destination = os.path.abspath(str(state.get("destination", "") or ""))
    if not os.path.isdir(destination):
        raise CopyRequestError(f"Destination is not accessible: {destination}")
    request_lock = os.path.join(request_dir(tlo_home, request_id), COPY_PASS_LOCK_FILENAME)
    destination_lock = _destination_lock_path(destination, request_id)
    acquired_request = _acquire_exclusive_lock(request_lock, request_id)
    acquired_destination = ""
    try:
        acquired_destination = _acquire_exclusive_lock(destination_lock, request_id)
        state = load_request(tlo_home, request_id)
        _recover_pending_copy(tlo_home, state)
        return _copy_available_unlocked(
            tlo_home, request_id, roots=roots, matcher=matcher, cancel_check=cancel_check
        )
    finally:
        if acquired_destination:
            _release_exclusive_lock(acquired_destination)
        _release_exclusive_lock(acquired_request)


def preview_request(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None) -> Tuple[RequestEvaluation, int, int, List[Tuple[str, str]]]:
    """Return evaluation, bytes required now, free bytes, and preflight errors."""
    effective_roots = dict(connected_volume_roots() if roots is None else roots)
    evaluation = evaluate_request(tlo_home, request_id, roots=effective_roots, matcher=matcher)
    destination = evaluation.destination
    rows = read_bootlist_rows(tlo_home)
    redundancy_groups = load_redundancy_groups(tlo_home)
    direct_plans, _direct_existing, errors, covered_shows, direct_targets = _preflight_direct_items(
        evaluation, destination, rows, effective_roots, redundancy_groups
    )
    item_by_raw = {item.raw: item for item in evaluation.items if item.kind in {"path", "volume"}}
    if any(
        (item := item_by_raw.get(raw)) is not None
        and _source_is_volume_root(item, source.source_path, effective_roots)
        for raw, source in evaluation.direct_available.items()
    ):
        evaluation.preview_notes.append(
            "Whole-volume copies, including volume roots supplied as direct paths, exclude these root-level OS folders when present: "
            + ", ".join(sorted(VOLUME_ROOT_EXCLUDED_NAMES))
            + "."
        )
    required = sum(plan[4] for plan in direct_plans)
    target_names: Dict[str, List[str]] = {}

    for show, source in evaluation.available.items():
        if show in covered_shows:
            continue
        target = os.path.join(destination, os.path.basename(os.path.normpath(source.source_path)))
        target_key = os.path.normcase(os.path.abspath(target))
        if target_key in direct_targets:
            errors.append((show, f"Destination folder is reserved by a direct path/volume request: {target}"))
            continue
        target_names.setdefault(target_key, []).append(show)
        try:
            size = _walk_tree_size_and_reject_links(source.source_path)
        except CopyRequestError as exc:
            errors.append((show, str(exc)))
            continue
        if os.path.lexists(target):
            if _paths_same_existing(source.source_path, target):
                errors.append((show, "Destination already is the source - no copy made."))
                continue
            exact_existing = False
            if os.path.isdir(target) and not os.path.islink(target):
                try:
                    _walk_tree_size_and_reject_links(target)
                    exact_existing = directory_trees_exactly_match(source.source_path, target)
                except CopyRequestError:
                    exact_existing = False
            if exact_existing:
                continue
            errors.append((show, f"Destination collision: {target}"))
            continue
        required += size
    for _target, shows in target_names.items():
        if len(shows) > 1:
            for show in shows:
                errors.append((show, "Two requested shows would use the same destination folder name."))
    try:
        free = shutil.disk_usage(destination).free if os.path.isdir(destination) else 0
    except OSError:
        free = 0
    write_request_reports(tlo_home, evaluation, None)
    return evaluation, required, free, errors


def format_bytes(value: int) -> str:
    amount = float(max(0, int(value or 0)))
    units = ["bytes", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(amount):,} bytes"
            return f"{amount:,.1f} {unit}"
        amount /= 1024.0
    return f"{int(value):,} bytes"
