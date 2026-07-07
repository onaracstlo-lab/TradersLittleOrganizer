__version__ = "v322"
# TLO-GI package version: v322
__version_summary__ = 'Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.'
# TLO-GI version summary: Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.

import csv
import os
import posixpath
import re
from typing import Dict, Iterable, List, Sequence, Tuple


BOOTLIST_FILENAME = "bootlist.csv"
VALID_VOLUME_ACTIONS = {"skip", "reinventory"}
DEFAULT_OS_VOLUME_LABELS = {"new volume", "local disk"}


def bootlist_path(tlo_home: str) -> str:
    return os.path.join(tlo_home, BOOTLIST_FILENAME)


def normalize_volume_label(volume_label: str) -> str:
    """Normalize a user-visible volume label for storage and comparison.

    Search paths may be entered as [Volume]E:\\dir, [Volume]E:,
    [Volume]/mnt/e/dir, or [Volume] /mnt/e/dir.  The label itself is always
    stored without brackets and with leading/trailing whitespace removed.  The
    empty string is a valid label and is preserved as the empty string.
    """
    text = str(volume_label or "").strip()
    if len(text) >= 2 and text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if text.casefold() in DEFAULT_OS_VOLUME_LABELS:
        return ""
    return text


def format_volume_path(volume_label: str, path_name: str) -> str:
    volume = normalize_volume_label(volume_label)
    path = storage_path_without_drive(path_name) if (path_name or "").strip() else ""
    if path:
        return f"[{volume}] {path}"
    return f"[{volume}]"


def parse_volume_path_value(volume_path: str) -> Tuple[str, str]:
    value = (volume_path or "").strip()
    match = re.match(r"^\[(?P<volume>[^\]]*)\]\s*(?P<path>.*)$", value)
    if match:
        return normalize_volume_label(match.group("volume")), match.group("path").strip()
    return "", value


def has_bracketed_volume_prefix(value: str) -> bool:
    return bool(re.match(r"^\s*\[[^\]]*\]", str(value or "")))


def os_volume_label_for_path(path_name: str) -> str:
    if not str(path_name or "").strip():
        return ""
    try:
        from tlo_volume_label import resolve_volume_label
        return normalize_volume_label(resolve_volume_label(path_name).label)
    except Exception:
        return ""


def volume_key(volume_label: str) -> str:
    # Volume matching is intentionally by visible volume name, including the
    # empty string.  Do not substitute an UNK value here.
    return normalize_volume_label(volume_label).casefold()


def storage_path_without_drive(path_name: str) -> str:
    """Return the inventory-visible path without a Windows drive/mount root.

    Inventory identity is the visible volume label plus the path below that
    volume.  Drive letters and WSL /mnt/<drive> mount prefixes are runtime
    details and are deliberately not written to bootlist.csv or log headers.
    Native POSIX paths that are not WSL drive mounts are kept as-is.
    """
    text = _strip_storage_root_for_compare(path_name)
    if not text or text == ".":
        return ""
    text = text.replace('\\', '/')
    text = re.sub(r"/+", "/", text)
    if text != "/":
        text = text.rstrip("/")
    return text


def format_log_volume_path(volume_label: str, path_name: str) -> str:
    """Format the SEARCH_PATH value used in logs.

    Blank visible volume labels intentionally omit the path.  Blank-label
    drives all append to the single blank-volume log set and are not used for
    skip/re-inventory decisions.
    """
    volume = normalize_volume_label(volume_label)
    if not volume:
        return format_volume_path(volume, "")
    return format_volume_path(volume, storage_path_without_drive(path_name))


def read_bootlist_rows(tlo_home: str) -> List[Dict[str, str]]:
    path_name = bootlist_path(tlo_home)
    if not os.path.isfile(path_name):
        return []
    rows: List[Dict[str, str]] = []
    with open(path_name, "r", encoding="utf-8", errors="ignore", newline="") as infile:
        first = infile.readline()
        if not first:
            return []
        if first.strip().lower() != "sep=^":
            infile.seek(0)
        reader = csv.reader(infile, delimiter="^")
        first_data = True
        for row in reader:
            if not row:
                continue
            if first_data and (row[0] or "").strip().casefold() in {"show", "show name"}:
                first_data = False
                continue
            first_data = False
            show = (row[0] if len(row) >= 1 else "").strip()
            if not show:
                continue
            if len(row) >= 4:
                volume = (row[2] or "").strip()
                path = (row[3] or "").strip()
                volume_path = format_volume_path(volume, path)
            else:
                volume_path = (row[1] if len(row) >= 2 else "").strip()
            volume, path = parse_volume_path_value(volume_path)
            rows.append({
                "Show": show,
                "VolumePath": format_volume_path(volume, path),
                "Volume": volume,
                "Path": path,
            })
    return rows


def write_bootlist_rows(tlo_home: str, rows: Sequence[Dict[str, str]]) -> str:
    path_name = bootlist_path(tlo_home)
    rows_out = sorted(
        rows,
        key=lambda row: ((row.get("Show") or "").casefold(), (row.get("VolumePath") or "").casefold()),
    )
    with open(path_name, "w", encoding="utf-8", newline="") as outfile:
        outfile.write("sep=^\n")
        outfile.write("Show^VolumePath\n")
        writer = csv.writer(outfile, delimiter="^", lineterminator="\n")
        for row in rows_out:
            show = (row.get("Show") or "").strip()
            volume_path = (row.get("VolumePath") or "").strip()
            if not volume_path:
                volume_path = format_volume_path(row.get("Volume", ""), row.get("Path", ""))
            writer.writerow([show, volume_path])
    return path_name




def _strip_storage_root_for_compare(path_name: str) -> str:
    """Return a path with a Windows drive or WSL mount root removed.

    Existing-inventory decisions are volume-label scoped.  The physical mount
    spelling is therefore not part of the subtree identity: [VOL] E:\\Music,
    [VOL] F:\\Music, [VOL] /mnt/e/Music, and [VOL] /mnt/f/Music should all
    compare as the same relative subtree.  Native Linux paths that are not
    /mnt/<drive> mount paths are left alone.
    """
    text = str(path_name or "").strip().strip('\"\'')
    if not text:
        return ""
    if has_bracketed_volume_prefix(text):
        _volume, text = parse_volume_path_value(text)
    text = text.strip().strip('\"\'').replace('\\', '/')
    text = re.sub(r"/+", "/", text)

    drive = re.match(r"^[A-Za-z]:(?:/(.*))?$", text)
    if drive:
        rest = (drive.group(1) or "").strip("/")
        return f"/{rest}" if rest else "/"

    mnt = re.match(r"^/mnt/[A-Za-z](?:/(.*))?$", text, flags=re.IGNORECASE)
    if mnt:
        rest = (mnt.group(1) or "").strip("/")
        return f"/{rest}" if rest else "/"

    return text


def normalize_path_for_compare(path_name: str) -> str:
    """Normalize paths for volume-scoped subtree comparisons.

    The returned key is platform-stable and POSIX-like.  Windows drive letters
    and WSL /mnt/<drive> prefixes are stripped so the same volume subtree still
    matches if a drive is mounted under a different letter later.
    """
    text = _strip_storage_root_for_compare(path_name)
    if not text:
        return ""
    text = text.replace('\\', '/')
    text = re.sub(r"/+", "/", text)
    normalized = posixpath.normpath(text)
    if normalized == "." and text.startswith("/"):
        normalized = "/"
    if os.name == "nt":
        normalized = normalized.casefold()
    return normalized


def paths_related(path_a: str, path_b: str) -> bool:
    a = normalize_path_for_compare(path_a)
    b = normalize_path_for_compare(path_b)
    if not a or not b:
        return False
    try:
        shared = posixpath.commonpath([a, b])
    except ValueError:
        return False
    return shared == a or shared == b


def path_is_same_or_under(path_name: str, root_path: str) -> bool:
    path = normalize_path_for_compare(path_name)
    root = normalize_path_for_compare(root_path)
    if not path or not root:
        return False
    try:
        return posixpath.commonpath([path, root]) == root
    except ValueError:
        return False


def count_rows_by_volume(rows: Iterable[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        volume = (row.get("Volume") or "").strip()
        if not volume and row.get("VolumePath"):
            volume, _path = parse_volume_path_value(row.get("VolumePath") or "")
        key = volume_key(volume)
        counts[key] = counts.get(key, 0) + 1
    return counts



def _group_log_paths(tlo_home: str) -> List[str]:
    logs_dir = os.path.join(tlo_home, "logs")
    if not os.path.isdir(logs_dir):
        return []
    return sorted(
        os.path.join(logs_dir, name)
        for name in os.listdir(logs_dir)
        if re.fullmatch(r"groups[A-Za-z0-9]+\.log", name or "")
        and os.path.isfile(os.path.join(logs_dir, name))
    )


def _log_token_from_group_log_path(log_path: str) -> str:
    name = os.path.basename(log_path or "")
    match = re.fullmatch(r"groups(?P<token>[A-Za-z0-9]+)\.log", name)
    return match.group("token") if match else ""


def _search_paths_from_group_log(log_path: str) -> List[str]:
    """Return all SEARCH_PATH/header values from one groups*.log.

    Newer logs can contain more than one SEARCH_PATH in the header because one
    visible volume label can own several non-overlapping inventory roots.  Older
    logs with a single SEARCH_PATH, or only the descriptive comment header, are
    still accepted.
    """
    values: List[str] = []

    def _add(value: str) -> None:
        clean = (value or "").strip()
        if clean and clean not in values:
            values.append(clean)

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as infile:
            for index, raw_line in enumerate(infile):
                if index >= 100:
                    break
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("SEARCH_PATH:"):
                    _add(line.split(":", 1)[1].strip())
                    continue
                if line.startswith("#"):
                    for marker in ("for search paths:", "for search path:"):
                        if marker in line:
                            tail = line.split(marker, 1)[1].strip()
                            for piece in re.split(r"\s+\|\s+", tail):
                                _add(piece)
                            break
                    continue
                if values:
                    break
    except OSError:
        return []
    return values


def read_group_log_volume_rows(tlo_home: str) -> List[Dict[str, str]]:
    """Read one visible volume/search-path row from the top of each groups*.log.

    Inventory startup uses these rows to decide whether a volume has already been
    addressed by a prior inventory run. This intentionally does not inspect
    bootlist.csv, because bootlist rows may be absent, filtered, or otherwise not
    represent the runs already attempted. Empty visible volume names are valid.
    """
    rows: List[Dict[str, str]] = []
    for log_path in _group_log_paths(tlo_home):
        values = _search_paths_from_group_log(log_path)
        if not values:
            continue
        for value in values:
            volume, path = parse_volume_path_value(value)
            if not has_bracketed_volume_prefix(value):
                volume = os_volume_label_for_path(path)
            rows.append({
                "Volume": volume,
                "Path": path,
                "VolumePath": format_volume_path(volume, path),
                "GroupLog": log_path,
                "Token": _log_token_from_group_log_path(log_path),
            })
    return rows


def count_group_logs_by_volume(tlo_home: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in read_group_log_volume_rows(tlo_home):
        key = volume_key(row.get("Volume", ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def group_log_tokens_by_volume(tlo_home: str) -> Dict[str, List[str]]:
    tokens: Dict[str, List[str]] = {}
    for row in read_group_log_volume_rows(tlo_home):
        token = (row.get("Token") or "").strip()
        if not token:
            continue
        key = volume_key(row.get("Volume", ""))
        bucket = tokens.setdefault(key, [])
        if token not in bucket:
            bucket.append(token)
    for key in list(tokens):
        tokens[key] = sorted(tokens[key], key=lambda value: (len(value), value))
    return tokens


def normalize_volume_action(action: str) -> str:
    """Normalize an existing-inventory decision.

    v208 has only two user-facing choices: skip or re-inventory.  Older
    spellings such as overwrite/append are accepted as legacy aliases for
    re-inventory so saved scripts or stale GUI callbacks do not fail abruptly,
    but new prompts never present those terms.
    """
    text = (action or "").strip().lower()
    aliases = {
        "s": "skip",
        "skip": "skip",
        "r": "reinventory",
        "reinventory": "reinventory",
        "re-inventory": "reinventory",
        "re_inventory": "reinventory",
        "re inventory": "reinventory",
        # Legacy aliases retained for compatibility only.
        "o": "reinventory",
        "overwrite": "reinventory",
        "over": "reinventory",
        "replace": "reinventory",
        "a": "reinventory",
        "append": "reinventory",
        "add": "reinventory",
    }
    if text not in aliases:
        raise ValueError("Volume action must be skip or re-inventory.")
    return aliases[text]


def filter_rows_for_volume_actions(rows: Sequence[Dict[str, str]], actions_by_volume: Dict[str, str]) -> List[Dict[str, str]]:
    # Compatibility helper for older tests/callers.  The current postprocess path
    # uses path-scoped inventory_path_actions instead of volume-wide filtering.
    # Legacy append means keep old rows; legacy overwrite/re-inventory means replace.
    kept: List[Dict[str, str]] = []
    for row in rows:
        volume = (row.get("Volume") or "").strip()
        if not volume and row.get("VolumePath"):
            volume, _path = parse_volume_path_value(row.get("VolumePath") or "")
        raw_action = str(actions_by_volume.get(volume_key(volume), "append") or "append").strip().lower()
        if raw_action in {"overwrite", "over", "replace", "reinventory", "re-inventory", "re_inventory", "re inventory", "r"}:
            continue
        kept.append(dict(row))
    return kept


def volume_display_name(volume_label: str) -> str:
    label = (volume_label or "").strip()
    return label if label else "(empty)"
