"""Persistent multi-pass Copy Request workflow for TLO inventories."""

from __future__ import annotations

__version__ = "v487"

import hashlib
import json
import os
import re
import shutil
import string
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from tlo_artist_db import ArtistMatcher, load_artist_matcher, lookup_artist_master_with_status
from tlo_bootlist_volume_policy import (
    normalize_volume_label,
    parse_volume_path_value,
    read_bootlist_rows,
    volume_key,
)
from tlo_tree_compare import directory_trees_exactly_match
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

SHOW_DATE_RE = re.compile(r"(?<!\d)(?P<date>\d{4}-\d{2}-\d{2})(?!\d)")
DATE_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<date>\d{4}-\d{2}-\d{2})$")
YEAR_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<year>\d{4})$")
RANGE_REQUEST_RE = re.compile(r"^(?P<artist>.+?)\s+(?P<start>\d{2}|\d{4})-(?P<end>\d{2}|\d{4})$")
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


class CopyRequestError(RuntimeError):
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
    available: Dict[str, SourceCandidate] = field(default_factory=dict)
    waiting: Dict[str, List[str]] = field(default_factory=dict)
    stale_missing: Dict[str, List[str]] = field(default_factory=dict)
    unmatched_items: List[str] = field(default_factory=list)
    invalid_items: Dict[str, str] = field(default_factory=dict)
    volume_opportunities: Dict[str, int] = field(default_factory=dict)

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
        "history": [],
    }


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


def source_request_change_state(tlo_home: str, state: Mapping[str, object]) -> str:
    """Return unchanged, changed, or missing for the original request file."""
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


def parse_request_items(text: str, inventory_shows: Sequence[str], matcher: Optional[ArtistMatcher]) -> List[RequestItem]:
    exact_show_map = {_normalize_show(show): show for show in inventory_shows}
    items: List[RequestItem] = []
    for raw in request_lines_from_text(text):
        exact = exact_show_map.get(_normalize_show(raw))
        if exact:
            items.append(RequestItem(raw=raw, kind="show", exact_show=exact))
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


def evaluate_request(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None) -> RequestEvaluation:
    state = load_request(tlo_home, request_id)
    text = saved_request_text(tlo_home, request_id)
    rows = read_bootlist_rows(tlo_home)
    shows = sorted({row.get("Show", "").strip() for row in rows if row.get("Show", "").strip()}, key=str.casefold)
    matcher = matcher if matcher is not None else _load_matcher(tlo_home)
    items = parse_request_items(text, shows, matcher)
    item_matches, unmatched, invalid = match_request_items(items, shows, matcher)
    matched_shows = sorted({show for selected in item_matches.values() for show in selected}, key=str.casefold)

    rows_by_show: Dict[str, List[Mapping[str, str]]] = {}
    for row in rows:
        show = str(row.get("Show", "") or "").strip()
        if show:
            rows_by_show.setdefault(show, []).append(row)

    roots = dict(connected_volume_roots() if roots is None else roots)
    redundancy_groups = load_redundancy_groups(tlo_home)
    completed_map = state.setdefault("completed", {})
    if not isinstance(completed_map, dict):
        completed_map = {}
        state["completed"] = completed_map
    completed: List[str] = []
    available: Dict[str, SourceCandidate] = {}
    waiting: Dict[str, List[str]] = {}
    stale: Dict[str, List[str]] = {}
    volume_opportunities: Dict[str, int] = {}

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
    elif available:
        status = STATUS_IN_PROGRESS
    elif waiting:
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
        "available": len(available),
        "waiting": len(waiting),
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
        available=available,
        waiting=waiting,
        stale_missing=stale,
        unmatched_items=unmatched,
        invalid_items=invalid,
        volume_opportunities=dict(sorted(volume_opportunities.items(), key=lambda item: (-item[1], item[0].casefold()))),
    )


def _walk_tree_size_and_reject_links(root: str) -> int:
    total = 0
    for current, dir_names, file_names in os.walk(root, followlinks=False):
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
    return total


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
        f"Already completed: {len(evaluation.completed_shows)}",
        f"Available now: {len(evaluation.available)}",
        f"Waiting for disconnected volumes: {len(evaluation.waiting)}",
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

    lines.extend(["", "WAITING FOR DISCONNECTED VOLUMES"])
    if evaluation.waiting:
        for show, sources in sorted(evaluation.waiting.items(), key=lambda item: item[0].casefold()):
            lines.append(show)
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
    _atomic_write_text(os.path.join(directory, COPIED_REPORT_FILENAME), "\n".join(copied_lines) + ("\n" if copied_lines else ""))

    pending_lines: List[str] = []
    for show, sources in evaluation.waiting.items():
        pending_lines.append(show + "\t" + " | ".join(sources))
    for show, sources in evaluation.stale_missing.items():
        pending_lines.append(show + "\tSTALE/MISSING\t" + " | ".join(sources))
    _atomic_write_text(os.path.join(directory, PENDING_REPORT_FILENAME), "\n".join(pending_lines) + ("\n" if pending_lines else ""))

    failed_lines = list(evaluation.unmatched_items)
    failed_lines.extend(f"{raw}\t{error}" for raw, error in evaluation.invalid_items.items())
    if result is not None:
        failed_lines.extend(f"{show}\t{reason}" for show, reason in result.failures)
    _atomic_write_text(os.path.join(directory, FAILED_REPORT_FILENAME), "\n".join(failed_lines) + ("\n" if failed_lines else ""))
    return latest


def copy_available(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None) -> CopyPassResult:
    state = load_request(tlo_home, request_id)
    if bool(state.get("closed")):
        raise CopyRequestError("This Copy Request is Closed and cannot be continued.")
    evaluation = evaluate_request(tlo_home, request_id, roots=roots, matcher=matcher)
    destination = evaluation.destination
    if not os.path.isdir(destination):
        raise CopyRequestError(f"Destination is not accessible: {destination}")

    result = CopyPassResult(request_id=request_id, status=evaluation.status)
    plans: List[Tuple[str, SourceCandidate, str, int]] = []
    target_to_shows: Dict[str, List[str]] = {}

    # First preflight every available source and destination collision.  Nothing
    # is copied until the complete current pass has a known byte requirement.
    for show, source in evaluation.available.items():
        target = os.path.join(destination, os.path.basename(os.path.normpath(source.source_path)))
        target_key = os.path.normcase(os.path.abspath(target))
        target_to_shows.setdefault(target_key, []).append(show)
        try:
            source_size = _walk_tree_size_and_reject_links(source.source_path)
        except CopyRequestError as exc:
            result.failures.append((show, str(exc)))
            continue
        if os.path.lexists(target):
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

    result.required_bytes = sum(plan[3] for plan in plans)
    try:
        result.free_bytes = shutil.disk_usage(destination).free
    except OSError as exc:
        raise CopyRequestError(f"Cannot determine free space for destination: {destination}: {exc}") from exc

    if result.required_bytes > result.free_bytes:
        result.insufficient_space = True
        save_request(tlo_home, state)
        evaluation = evaluate_request(tlo_home, request_id, roots=roots, matcher=matcher)
        result.status = evaluation.status
        result.report_path = write_request_reports(tlo_home, evaluation, result)
        return result

    save_request(tlo_home, state)

    for show, source, target, _size in plans:
        temp_target = os.path.join(destination, f".tlo-copy-{uuid.uuid4().hex}")
        try:
            shutil.copytree(source.source_path, temp_target, symlinks=False)
            if not directory_trees_exactly_match(source.source_path, temp_target):
                raise CopyRequestError("Copied tree verification failed.")
            if os.path.lexists(target):
                raise CopyRequestError(f"Destination appeared during copy: {target}")
            os.replace(temp_target, target)
            _record_completed(state, show, target, source, method="copied")
            save_request(tlo_home, state)
            result.copied.append((show, source.source_path, target))
            result.source_details[show] = (source.inventory_volume or source.volume, source.volume)
        except Exception as exc:
            try:
                if os.path.isdir(temp_target) and not os.path.islink(temp_target):
                    shutil.rmtree(temp_target)
                elif os.path.lexists(temp_target):
                    os.unlink(temp_target)
            except OSError:
                pass
            result.failures.append((show, str(exc)))

    evaluation = evaluate_request(tlo_home, request_id, roots=roots, matcher=matcher)
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
        })
        # Bound state growth; detailed history remains in text reports.
        del history[:-200]
    state["status"] = result.status
    save_request(tlo_home, state)
    result.report_path = write_request_reports(tlo_home, evaluation, result)
    return result


def preview_request(tlo_home: str, request_id: str, *, roots: Optional[Mapping[str, Sequence[str]]] = None, matcher: Optional[ArtistMatcher] = None) -> Tuple[RequestEvaluation, int, int, List[Tuple[str, str]]]:
    """Return evaluation, bytes required now, free bytes, and preflight errors."""
    evaluation = evaluate_request(tlo_home, request_id, roots=roots, matcher=matcher)
    errors: List[Tuple[str, str]] = []
    required = 0
    destination = evaluation.destination
    target_names: Dict[str, List[str]] = {}
    for show, source in evaluation.available.items():
        target = os.path.join(destination, os.path.basename(os.path.normpath(source.source_path)))
        target_names.setdefault(os.path.normcase(os.path.abspath(target)), []).append(show)
        try:
            size = _walk_tree_size_and_reject_links(source.source_path)
        except CopyRequestError as exc:
            errors.append((show, str(exc)))
            continue
        if os.path.lexists(target):
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
