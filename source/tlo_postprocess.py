"""Postprocess metadata logs into setlist files, bootlist.csv, duplicate/group outputs, and summary/unidentified-show files."""

__version__ = "v324"
# TLO-GI package version: v324
__version_summary__ = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
# TLO-GI version summary: Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.
import csv
import glob
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Dict, List, Sequence

from console_output_lib import console_print
from logging_lib import logs_dir_for_home
from tlo_text_utils import compact_ws, read_text_file_full, setlist_text_requests_generated_from_music_files, standard_ascii_text
from tlo_runtime_control import throttle_point, is_cancel_requested, normalize_performance_mode
from tlo_bootlist_volume_policy import (
    filter_rows_for_volume_actions,
    format_volume_path,
    parse_volume_path_value,
    read_bootlist_rows,
    path_is_same_or_under,
    normalize_path_for_compare,
    volume_key,
    write_bootlist_rows,
    normalize_volume_action,
)

PLACEHOLDER_SETLIST_TEXT = "*** No setlist found ***"
MAX_FILENAME_CHARS = 255
FILENAME_RESERVE_CHARS = 10
SETLIST_EXTENSION = ".txt"

MEDIA_EXTENSIONS_FOR_PLACEHOLDER_SETLIST = {
    ".3gp", ".aac", ".aif", ".aiff", ".alac", ".ape", ".avi", ".flac",
    ".flv", ".m2ts", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpg", ".oga", ".ogg", ".opus", ".shn", ".shnf", ".ts",
    ".vob", ".wav", ".webm", ".wmv", ".wv",
}

POSTPROCESS_DIR_NAMES_TO_PRUNE = {
    "$recycle.bin",
    "system volume information",
}


def _postprocess_should_prune_dir(dirname: str) -> bool:
    """Return True when postprocess placeholder-setlist scanning should skip dirname."""
    name = str(dirname or "").strip().lower()
    return name.endswith("-ignoredir") or name in POSTPROCESS_DIR_NAMES_TO_PRUNE






def _format_elapsed_seconds(seconds: float) -> str:
    """Return a compact, human-readable elapsed-time string."""
    try:
        value = float(seconds)
    except Exception:
        value = 0.0
    if value >= 60.0:
        return f"{value / 60.0:.2f} min"
    return f"{value:.2f} sec"


def _postprocess_status(config, message: str) -> None:
    console_print(config, f"POSTPROCESS: {message}")


def _record_postprocess_timing(timing_entries: List[tuple[str, float]], label: str, started_at: float) -> float:
    elapsed = time.monotonic() - started_at
    timing_entries.append((label, elapsed))
    return elapsed


def _append_postprocess_timing_summary(summary_log_path: str, timing_entries: List[tuple[str, float]]) -> None:
    """Append postprocess stage timings to summary.log after it has been written."""
    if not summary_log_path:
        return
    total = sum(max(float(seconds), 0.0) for _label, seconds in timing_entries)
    with open(summary_log_path, "a", encoding="utf-8", newline="\n") as outfile:
        outfile.write("\nPostprocess timing:\n")
        for label, seconds in timing_entries:
            outfile.write(f"  {label}: {_format_elapsed_seconds(seconds)}\n")
        outfile.write(f"  total postprocess: {_format_elapsed_seconds(total)}\n")


def _show_metadata_log_paths(tlo_home: str, tokens: Sequence[str] | None = None) -> List[str]:
    logs_dir = logs_dir_for_home(tlo_home)
    clean_tokens = [str(token or "").strip() for token in (tokens or []) if str(token or "").strip()]
    if clean_tokens:
        paths = [os.path.join(logs_dir, f"meta{token}.log") for token in clean_tokens]
        return [path for path in paths if os.path.isfile(path)]
    pattern = os.path.join(logs_dir, "meta*.log")
    return sorted(path for path in glob.glob(pattern) if os.path.isfile(path))


def _metadata_record_to_postprocess_dict(record) -> Dict[str, str]:
    """Return the postprocess dictionary shape for either log-parsed records or ShowMetadata objects.

    v208 switched postprocess to use current-run records directly, but the
    inventory engine returns ShowMetadata dataclass instances.  The log parser
    returns dictionaries.  Normalize both forms here so postprocess does not
    try to call dict() on a dataclass.
    """
    if isinstance(record, dict):
        data = dict(record)
    elif is_dataclass(record):
        data = asdict(record)
    else:
        fields = (
            "show_name", "setlist_file", "volume_label", "artist", "date",
            "venue", "location", "parentheticals", "album_name",
            "show_in_conflict", "main_dir_path", "setlist_files", "music_dirs",
        )
        data = {field: getattr(record, field, "") for field in fields}

    show_in_conflict = data.get("show_in_conflict", "no")
    if isinstance(show_in_conflict, bool):
        show_in_conflict = "yes" if show_in_conflict else "no"

    def _json_list(value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return json.dumps([str(item) for item in value if str(item).strip()], ensure_ascii=False)
        return ""

    out = {
        "show_name": str(data.get("show_name") or ""),
        "setlist_file": str(data.get("setlist_file") or ""),
        "volume_label": str(data.get("volume_label") or ""),
        "artist": str(data.get("artist") or ""),
        "date": str(data.get("date") or ""),
        "venue": str(data.get("venue") or ""),
        "location": str(data.get("location") or ""),
        "parentheticals": str(data.get("parentheticals") or ""),
        "album_name": str(data.get("album_name") or ""),
        "show_in_conflict": str(show_in_conflict or "no"),
        "main_dir_path": str(data.get("main_dir_path") or ""),
        "setlist_files_json": str(data.get("setlist_files_json") or _json_list(data.get("setlist_files")) or ""),
        "music_dirs_json": str(data.get("music_dirs_json") or _json_list(data.get("music_dirs")) or ""),
    }
    _adjust_show_name_for_output(out)
    return out


def _normalize_metadata_records_for_postprocess(records) -> List[Dict[str, str]]:
    """Normalize in-memory current-run records into log-parser-style dictionaries."""
    normalized: List[Dict[str, str]] = []
    for record in records or []:
        try:
            normalized.append(_metadata_record_to_postprocess_dict(record))
        except Exception:
            # Do not let one malformed in-memory record crash the whole run.
            # The fallback keeps at least the string representation discoverable
            # in debugging while preserving the postprocess shape.
            normalized.append({
                "show_name": "",
                "setlist_file": "",
                "volume_label": "",
                "artist": "",
                "date": "",
                "venue": "",
                "location": "",
                "parentheticals": "",
                "album_name": "",
                "show_in_conflict": "yes",
                "main_dir_path": str(record),
                "setlist_files_json": "",
                "music_dirs_json": "",
            })
    return normalized


def _parse_show_metadata_logs(tlo_home: str, tokens: Sequence[str] | None = None) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for log_path in _show_metadata_log_paths(tlo_home, tokens=tokens):
        current = {
            "show_name": "",
            "setlist_file": "",
            "volume_label": "",
            "artist": "",
            "date": "",
            "venue": "",
            "location": "",
            "parentheticals": "",
            "album_name": "",
            "show_in_conflict": "no",
            "main_dir_path": "",
            "setlist_files_json": "",
            "music_dirs_json": "",
        }
        with open(log_path, "r", encoding="utf-8", errors="ignore") as infile:
            for raw_line in infile:
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                if line == "END_SHOW_METADATA":
                    if current["show_name"] or current["main_dir_path"]:
                        records.append(dict(current))
                    current = {
                        "show_name": "",
                        "setlist_file": "",
                        "volume_label": "",
                        "artist": "",
                        "date": "",
                        "venue": "",
                        "location": "",
                        "parentheticals": "",
                        "album_name": "",
                        "show_in_conflict": "no",
                        "main_dir_path": "",
                        "setlist_files_json": "",
                        "music_dirs_json": "",
                    }
                    continue
                if ": " not in line:
                    continue
                key, value = line.split(": ", 1)
                if key == "SHOW_NAME":
                    current["show_name"] = value.strip()
                elif key == "SETLIST_FILE":
                    current["setlist_file"] = value.strip()
                elif key == "SETLIST_FILES_JSON":
                    current["setlist_files_json"] = value.strip()
                elif key == "MUSIC_DIRS_JSON":
                    current["music_dirs_json"] = value.strip()
                elif key == "VOLUME_LABEL":
                    current["volume_label"] = value.strip()
                elif key == "ARTIST":
                    current["artist"] = value.strip()
                elif key == "DATE":
                    current["date"] = value.strip()
                elif key == "VENUE":
                    current["venue"] = value.strip()
                elif key == "LOCATION":
                    current["location"] = value.strip()
                elif key == "PARENTHETICALS":
                    current["parentheticals"] = value.strip()
                elif key == "ALBUM_NAME":
                    current["album_name"] = value.strip()
                elif key == "SHOW_IN_CONFLICT":
                    current["show_in_conflict"] = value.strip().lower()
                elif key == "CONFLICT":
                    current["show_in_conflict"] = "yes"
                elif key == "MAIN_DIR_PATH":
                    current["main_dir_path"] = value.strip()
    return records




def _json_list_from_record(record: Dict[str, str], key: str) -> List[str]:
    raw = (record.get(key) or "").strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _setlist_source_paths_from_record(record: Dict[str, str]) -> List[str]:
    paths = _json_list_from_record(record, "setlist_files_json")
    single = (record.get("setlist_file") or "").strip()
    if single:
        paths.insert(0, single)
    seen = set()
    ordered: List[str] = []
    for path_name in paths:
        normalized = os.path.normpath(path_name)
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            ordered.append(normalized)
    return ordered

DATE_OR_RANGE_TOKEN_RE = re.compile(
    r"(?<!\d)(?:"
    r"(?P<ymd>(?:19|20)\d{2}(?:\s*[-_.]\s*|\s+)\d{1,2}(?:\s*[-_.]\s*|\s+)\d{1,2})"
    r"|(?P<yrange>(?:19|20)\d{2}[-_](?:19|20)\d{2})"
    r"|(?P<fourplus>(?:19|20)\d{2}[ -]\d{4})"
    r"|(?P<compact>(?:19|20)\d{6})"
    r")(?!\d)"
)


def _first_named_match_group(match: re.Match, *names: str) -> str:
    """Return the first populated named group without assuming every name exists.

    Date-token regexes have changed repeatedly as date handling has been tightened.
    Postprocess should not fail with IndexError("no such group") when a removed
    helper group name is still present in the fallback list.
    """
    groups = match.groupdict()
    for name in names:
        value = groups.get(name)
        if value:
            return value
    return match.group(0) or ""


def _compact_date_or_range_for_filename(token: str) -> str:
    text = str(token or "").strip()
    if re.fullmatch(r"(?:19|20)\d{6}", text):
        try:
            datetime(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            # Compact eight-digit values are normally YYYYMMDD dates. If that
            # interpretation is not a valid calendar date, allow the filename-
            # only compact year-range form YYYYyyyy when it increases. This keeps
            # path/date extraction from treating 19961998 as a date candidate,
            # while allowing documented setlist filenames to normalize it.
            start_year = text[:4]
            end_year = text[4:8]
            if re.fullmatch(r"(?:19|20)\d{2}", end_year) and int(end_year) > int(start_year):
                return f"{start_year}-{end_year}"
            return text
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    normalized = re.sub(r"[-_. ]+", "-", text)
    if re.fullmatch(r"(?:19|20)\d{2}-(?:19|20)\d{2}", normalized):
        return normalized
    if re.fullmatch(r"(?:19|20)\d{2}[ -]\d{4}", text):
        year = text[:4]
        tail = text[-4:]
        # Prefer US MMDD, then accept European DDMM when MMDD is invalid.
        for month, day in ((tail[:2], tail[2:]), (tail[2:], tail[:2])):
            try:
                datetime(int(year), int(month), int(day))
            except ValueError:
                continue
            return f"{year}-{int(month):02d}-{int(day):02d}"
        return text
    if re.fullmatch(r"(?:19|20)\d{2}-\d{2}-\d{2}", normalized):
        try:
            datetime(int(normalized[:4]), int(normalized[5:7]), int(normalized[8:10]))
        except ValueError:
            return text
        return normalized
    return text


def _normalize_compact_date_tokens_for_filename(value: str) -> str:
    text = str(value or "")
    pieces: List[str] = []
    pos = 0
    for match in DATE_OR_RANGE_TOKEN_RE.finditer(text):
        pieces.append(text[pos:match.start()])
        token = _compact_date_or_range_for_filename(_first_named_match_group(match, "ymd", "ymd_exc", "yrange", "fourplus", "compact"))
        pieces.append(token)
        pos = match.end()
    pieces.append(text[pos:])
    return "".join(pieces)


def _first_filename_date_token(*values: str) -> str:
    for value in values:
        text = str(value or "")
        for match in DATE_OR_RANGE_TOKEN_RE.finditer(text):
            token = _compact_date_or_range_for_filename(_first_named_match_group(match, "ymd", "ymd_exc", "yrange", "fourplus", "compact"))
            if token and token != (match.group(0) or "") or re.search(r"-", token):
                return token
    return ""


def _sanitize_setlist_text_preserving_date_dashes(value: str, fallback: str = "Show") -> str:
    text = standard_ascii_text(value)
    pieces: List[str] = []
    pos = 0
    for match in DATE_OR_RANGE_TOKEN_RE.finditer(text):
        prefix = text[pos:match.start()]
        pieces.append("".join(ch for ch in prefix if ch.isalnum() or ch in "()&"))
        token = _compact_date_or_range_for_filename(_first_named_match_group(match, "ymd", "ymd_exc", "yrange", "fourplus", "compact"))
        pieces.append(token)
        pos = match.end()
    pieces.append("".join(ch for ch in text[pos:] if ch.isalnum() or ch in "()&"))
    base = "".join(pieces)
    return base or fallback


def _normalized_setlist_base(show_name: str, fallback: str = "Show") -> str:
    return _sanitize_setlist_text_preserving_date_dashes(show_name, fallback=fallback)


def _truncate_setlist_base(base: str) -> str:
    """Reserve filename space before appending collision suffixes and .txt.

    This helper is intentionally kept separate from filename-base construction:
    postprocess must write one exported setlist text file for each generated
    bootlist row.  v137 accidentally removed the helper while retaining the
    call site, causing row generation to fail before files could be collected
    into TLOHome/setlists.
    """
    max_base_len = max(1, MAX_FILENAME_CHARS - FILENAME_RESERVE_CHARS - len(SETLIST_EXTENSION))
    return (base or "Show")[:max_base_len] or "Show"


def _sanitize_setlist_component(value: str, keep_dash: bool = False) -> str:
    allowed = {"(", ")", "&"}
    text = standard_ascii_text(value)
    if keep_dash:
        allowed.add("-")
        text = _normalize_compact_date_tokens_for_filename(text)
    return "".join(ch for ch in text if ch.isalnum() or ch in allowed)


def _sanitize_dash_album_component(value: str) -> str:
    """Sanitize a String1 - String2 component without destroying embedded date dashes."""
    return _sanitize_setlist_text_preserving_date_dashes(value, fallback="")


def _date_like_component_matches_date(component: str, date: str) -> bool:
    if not component or not date:
        return False
    normalized = _first_filename_date_token(component) or _sanitize_dash_album_component(component)
    return bool(normalized and normalized == date)


def _split_trailing_parenthetical_suffixes(value: str) -> tuple[str, str]:
    """Return (base, trailing_parentheticals) without losing the suffix text.

    This is intentionally local to setlist filename generation. Metadata parsing
    may strip trailing parentheticals so it can identify Artist/Date/Venue, but
    exported setlist filenames should preserve user-visible parenthetical release
    qualifiers such as (SBD), (Vol 1), and (Volume 2).
    """
    text = compact_ws(standard_ascii_text(value or ""))
    suffixes: List[str] = []
    while text:
        match = re.search(r"\s*(\([^()]*\))\s*$", text)
        if not match:
            break
        suffixes.insert(0, match.group(1).strip())
        text = compact_ws(text[: match.start()])
    return compact_ws(text), " ".join(suffixes).strip()


def _append_main_dir_parenthetical_suffix(base: str, record: Dict[str, str]) -> str:
    """Append parenthetical suffixes from the source folder when metadata stripped them.

    Same-base multi-volume folders are deliberately separate inventory rows in
    v278+. Their metadata base is the stripped show identity, but their setlist
    filenames must remain distinct and faithful to the source folder, e.g.
    Show(Volume1).txt and Show(Volume2).txt rather than Show.txt/Show(alt1).txt.
    The comparison is normalized through the regular setlist-base sanitizer so
    spaces and punctuation differences do not prevent a match.
    """
    current = base or ""
    main_dir_path = str(record.get("main_dir_path") or "")
    leaf = os.path.basename(os.path.normpath(main_dir_path)) if main_dir_path else ""
    stripped_leaf, suffix = _split_trailing_parenthetical_suffixes(leaf)
    if not suffix:
        return current
    suffix_component = _sanitize_setlist_component(suffix)
    if not suffix_component or current.casefold().endswith(suffix_component.casefold()):
        return current

    leaf_base = _normalized_setlist_base(stripped_leaf, fallback="")
    show_base = _normalized_setlist_base(record.get("show_name", ""), fallback="")
    show_base_without_suffix, _show_suffix = _split_trailing_parenthetical_suffixes(record.get("show_name", ""))
    show_base_without_suffix = _normalized_setlist_base(show_base_without_suffix, fallback="")

    comparable = {value.casefold() for value in (leaf_base, show_base, show_base_without_suffix) if value}
    if current and current.casefold() in comparable:
        return f"{current}{suffix_component}"
    return current


def _prefer_show_name_when_it_preserves_parentheticals(base: str, record: Dict[str, str], fallback: str = "Show") -> str:
    """Use SHOW_NAME for the filename base when it retains trailing parentheses.

    Structured metadata fields are usually best for stable filename generation,
    but they can drop a parenthetical that is still present in SHOW_NAME. When
    the structured base equals SHOW_NAME with the parenthetical removed, the
    SHOW_NAME-derived base is the more faithful filename base.
    """
    show_name = record.get("show_name", "")
    show_without_suffix, show_suffix = _split_trailing_parenthetical_suffixes(show_name)
    if not show_suffix:
        return base
    show_base = _normalized_setlist_base(show_name, fallback=fallback)
    show_base_without_suffix = _normalized_setlist_base(show_without_suffix, fallback="")
    if base and show_base_without_suffix and base.casefold() == show_base_without_suffix.casefold():
        return show_base
    return base


def _setlist_base_from_record(record: Dict[str, str], fallback: str = "Show") -> str:
    show_name = record.get("show_name", "")
    artist = _sanitize_setlist_component(record.get("artist", ""))
    date_raw = record.get("date", "")
    date = _sanitize_setlist_component(date_raw, keep_dash=True)
    venue = _sanitize_setlist_component(record.get("venue", ""))
    album_name = _sanitize_setlist_component(record.get("album_name", ""))
    venue_dash_safe = _sanitize_dash_album_component(record.get("venue", ""))
    album_name_dash_safe = _sanitize_dash_album_component(record.get("album_name", ""))
    location = _sanitize_setlist_component(record.get("location", ""))
    parentheticals = _sanitize_setlist_component(record.get("parentheticals", ""))

    # If a compliant fallback/special-case show name is already the complete
    # show identity and no structured artist/date/venue/location components
    # were parsed, use that show name directly for the setlist filename.
    # This prevents a broad parent path date/range such as 1960-2004 from
    # replacing a Billboard MP3 year-folder show name such as 1961.
    if show_name and not any([artist, date_raw.strip(), venue, album_name, location, parentheticals]):
        direct = _normalized_setlist_base(show_name, fallback=fallback)
        return _append_main_dir_parenthetical_suffix(direct, record)

    # String1 - String2 shows have no parsed date and the show name includes
    # the literal separator. Preserve that separator and preserve date dashes
    # inside String2 when String2 itself is date-like. Do this before searching
    # for fallback date tokens in the show/path so the date-like album value is
    # not appended twice as both DATE and ALBUM/VENUE.
    if artist and not date and " - " in show_name:
        dash_component = album_name_dash_safe or venue_dash_safe or album_name or venue
        if dash_component:
            base = f"{artist}-{dash_component}{parentheticals}"
            base = _prefer_show_name_when_it_preserves_parentheticals(base, record, fallback=fallback)
            return _append_main_dir_parenthetical_suffix(base, record)

    if not re.search(r"(?:19|20)\d{2}-", date):
        date = _sanitize_setlist_component(
            _first_filename_date_token(date_raw, show_name, record.get("main_dir_path", ""), record.get("setlist_file", "")),
            keep_dash=True,
        ) or date

    if _date_like_component_matches_date(record.get("venue", ""), date):
        venue = ""

    base = "".join([artist, date, venue, location, parentheticals])
    if base:
        base = _prefer_show_name_when_it_preserves_parentheticals(base, record, fallback=fallback)
        return _append_main_dir_parenthetical_suffix(base, record)
    direct = _normalized_setlist_base(show_name, fallback=fallback)
    return _append_main_dir_parenthetical_suffix(direct, record)


def _candidate_setlist_name(base: str, suffix: str = "") -> str:
    allowed_base_len = max(1, MAX_FILENAME_CHARS - len(SETLIST_EXTENSION) - len(suffix))
    candidate_base = (base or "Show")[:allowed_base_len] or "Show"
    return f"{candidate_base}{suffix}{SETLIST_EXTENSION}"


def _known_setlist_names(setlists_dir: str, used: set) -> set:
    names = {str(name or "") for name in used or [] if str(name or "").strip()}
    try:
        for name in os.listdir(setlists_dir):
            if name.lower().endswith(SETLIST_EXTENSION) and os.path.isfile(os.path.join(setlists_dir, name)):
                names.add(name)
    except OSError:
        pass
    return names


def _setlist_text_output_size(text: str) -> int:
    """Return the byte size that _write_text_file will write for setlist text."""
    output = text or ""
    if not output.endswith("\n"):
        output += "\n"
    return len(output.encode("utf-8"))


def _setlist_file_size_matches(path_name: str, new_text: str) -> bool:
    try:
        return os.path.getsize(path_name) == _setlist_text_output_size(new_text)
    except OSError:
        return False


def _existing_alt_numbers_for_base(base: str, setlists_dir: str, used: set) -> List[int]:
    numbers: List[int] = []
    # used is initialized once with existing setlist names and then updated as new
    # names are reserved.  Do not rescan TLOHome/setlists for every record.
    pattern = re.compile(rf"^{re.escape(base)}\(alt(?P<num>\d+)\){re.escape(SETLIST_EXTENSION)}$", re.IGNORECASE)
    for name in {str(name or "") for name in (used or set()) if str(name or "").strip()}:
        match = pattern.match(name)
        if match:
            try:
                numbers.append(int(match.group("num")))
            except ValueError:
                pass
    return numbers


def _resolve_setlist_filename_for_text(base: str, setlists_dir: str, new_text: str, used: set) -> tuple[str, bool]:
    """Return (filename, should_write) using size-aware alternate handling.

    The first requested filename remains <base>.txt. If that name already exists
    and its file size is the same size that the new setlist text would write, the
    new setlist is treated as a duplicate and the row resolves to the existing
    file. If the size differs, the new file becomes <base>(altN).txt, where N is
    one greater than the highest existing alternate number for that base. Existing
    alternate files are also checked by size before a new alternate is created.
    File contents are not read for collision comparison.
    """
    os.makedirs(setlists_dir, exist_ok=True)
    base = _truncate_setlist_base(base)
    exact_name = _candidate_setlist_name(base)
    exact_path = os.path.join(setlists_dir, exact_name)
    # used contains the preloaded setlist directory names plus names reserved in
    # this postprocess run.  Avoid a full directory scan for every metadata record.
    folded_known = {str(name or "").casefold() for name in (used or set())}

    if exact_name.casefold() not in folded_known:
        used.add(exact_name)
        return exact_name, True
    if os.path.isfile(exact_path) and _setlist_file_size_matches(exact_path, new_text):
        used.add(exact_name)
        return exact_name, False

    alt_numbers = _existing_alt_numbers_for_base(base, setlists_dir, used)
    for number in sorted(alt_numbers):
        alt_name = _candidate_setlist_name(base, f"(alt{number})")
        alt_path = os.path.join(setlists_dir, alt_name)
        if os.path.isfile(alt_path) and _setlist_file_size_matches(alt_path, new_text):
            used.add(alt_name)
            return alt_name, False

    next_number = (max(alt_numbers) + 1) if alt_numbers else 1
    while True:
        alt_name = _candidate_setlist_name(base, f"(alt{next_number})")
        alt_path = os.path.join(setlists_dir, alt_name)
        if alt_name.casefold() not in folded_known and not os.path.exists(alt_path):
            used.add(alt_name)
            return alt_name, True
        if os.path.isfile(alt_path) and _setlist_file_size_matches(alt_path, new_text):
            used.add(alt_name)
            return alt_name, False
        next_number += 1


def _unique_setlist_filename(base: str, used: set) -> str:
    # Compatibility helper for older callers/tests. New postprocess row building
    # uses _resolve_setlist_filename_for_text so collisions can be size-aware.
    base = _truncate_setlist_base(base)
    folded_used = {name.casefold() for name in used}
    candidate = _candidate_setlist_name(base)
    if candidate.casefold() not in folded_used:
        used.add(candidate)
        return candidate
    suffix_num = 1
    while True:
        candidate = _candidate_setlist_name(base, f"(alt{suffix_num})")
        if candidate.casefold() not in folded_used:
            used.add(candidate)
            return candidate
        suffix_num += 1


def _prepare_setlists_dir(tlo_home: str, clear_existing: bool = True) -> str:
    setlists_dir = os.path.join(tlo_home, "setlists")
    os.makedirs(setlists_dir, exist_ok=True)
    if clear_existing:
        for old_txt in glob.glob(os.path.join(setlists_dir, "*.txt")):
            try:
                os.remove(old_txt)
            except OSError:
                pass
    return setlists_dir


def _placeholder_music_filename_sort_key(filename: str) -> tuple[int, int, str]:
    stem = os.path.splitext(os.path.basename(str(filename or "")))[0]
    patterns = [
        (0, re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:d|cd|disc|disk)\s*(?P<disc>\d{1,2})\s*(?:t|track)\s*(?P<track>\d{1,3})(?:[^0-9]|$)")),
        (0, re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:s|set)\s*(?P<disc>\d{1,2})\s*(?:t|track)\s*(?P<track>\d{1,3})(?:[^0-9]|$)")),
        (0, re.compile(r"(?i)t\s*(?P<track>\d{1,3})(?:[^0-9]|$)")),
    ]
    for priority, pattern in patterns:
        matches = list(pattern.finditer(stem))
        if not matches:
            continue
        match = matches[-1]
        disc = int(match.groupdict().get("disc") or 1)
        track = int(match.group("track"))
        return (priority + max(0, disc - 1), track, os.path.basename(filename).casefold())
    leading = re.match(r"^\s*(?P<track>\d{1,3})(?:[.)_ -]+|$)", stem)
    if leading:
        return (0, int(leading.group("track")), os.path.basename(filename).casefold())
    return (9999, 9999, os.path.basename(filename).casefold())


def _iter_music_file_names_for_placeholder(main_dir_path: str, config=None, music_dirs: List[str] | None = None) -> List[str]:
    """Return recognized music filenames under the logical record directories."""
    roots = [os.path.normpath(p) for p in (music_dirs or []) if (p or "").strip()]
    if not roots and (main_dir_path or "").strip():
        roots = [os.path.normpath(main_dir_path)]

    matches: List[tuple[str, str]] = []
    seen_roots = set()
    for root_dir in roots:
        if not root_dir or root_dir.casefold() in seen_roots or not os.path.isdir(root_dir):
            continue
        seen_roots.add(root_dir.casefold())
        throttle_point(config)
        # The inventory phase already identified the music directories for this
        # show.  During postprocess, do not recursively walk an entire large root
        # just to build a missing-setlist placeholder; list files directly in the
        # recorded music directories.  This avoids a small re-inventory appearing
        # to hang while scanning a broad tree again.
        try:
            filenames = os.listdir(root_dir)
        except OSError:
            continue
        for filename in filenames:
            full_path = os.path.join(root_dir, filename)
            if os.path.isfile(full_path) and os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS_FOR_PLACEHOLDER_SETLIST:
                matches.append((_placeholder_music_filename_sort_key(filename), filename))
    return [filename for _sort_key, filename in sorted(matches, key=lambda item: (item[0], item[1]))]


def _title_from_music_filename_for_generated_setlist(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(str(filename or "")))[0]
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    patterns = [
        r"(?i)^\s*(?:cd|disc|disk|d)\s*\d{1,2}\s*(?:t|track)\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"(?i)^\s*(?:s|set)\s*\d{1,2}\s*(?:t|track)\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"(?i)^.*?(?:^|[^A-Za-z0-9])(?:s|set)\s*\d{1,2}\s*(?:t|track)\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"(?i)^.*?(?:^|[^A-Za-z0-9])(?:d|cd|disc|disk)\s*\d{1,2}\s*(?:t|track)\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"^\s*\d{3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"^\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
        r"(?i)^.*?t\s*\d{1,3}\s*[.)_ -]+(?P<title>\S.*)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stem)
        if match:
            title = compact_ws(match.group("title"))
            title = re.sub(r"(?<!\d)(?:19|20)\d{2}[-._ ]\d{1,2}[-._ ]\d{1,2}(?!\d)", "", title).strip(" -_.")
            return title or stem
    return stem or os.path.basename(str(filename or ""))


def _generated_missing_setlist_text(record: Dict[str, str], config=None) -> str:
    """Create a synthetic setlist when no usable setlist file exists."""
    lines: List[str] = []

    artist = (record.get("artist") or "").strip()
    date = (record.get("date") or "").strip()
    venue = (record.get("venue") or "").strip()
    location = (record.get("location") or "").strip()

    if artist:
        lines.append(artist)
    if date:
        lines.append(date)
    if venue:
        lines.append(venue)
    if location:
        lines.append(location)
    if not lines:
        lines.append(PLACEHOLDER_SETLIST_TEXT)

    music_file_names = _iter_music_file_names_for_placeholder(
        record.get("main_dir_path", ""),
        config=config,
        music_dirs=_json_list_from_record(record, "music_dirs_json"),
    )
    if music_file_names:
        if lines:
            lines.append("")
        lines.append("TRACKS:")
        for idx, filename in enumerate(music_file_names, start=1):
            title = _title_from_music_filename_for_generated_setlist(filename)
            lines.append(f"{idx:02d}. {title}")

    return "\n".join(lines).strip()


def _export_setlist_text(source_path: str, record: Dict[str, str] | None = None, config=None) -> str:
    normalized = os.path.normpath(source_path or "")
    if not normalized or not os.path.isfile(normalized):
        return _generated_missing_setlist_text(record or {}, config=config)

    text = read_text_file_full(normalized)
    if setlist_text_requests_generated_from_music_files(text):
        return _generated_missing_setlist_text(record or {}, config=config)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    return text or _generated_missing_setlist_text(record or {}, config=config)




def _normalize_setlist_text_for_dedupe(text: str) -> str:
    lines = [line.strip() for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).casefold()


def _export_combined_setlist_text(record: Dict[str, str], config=None) -> str:
    sources = _setlist_source_paths_from_record(record)
    if not sources:
        return _generated_missing_setlist_text(record or {}, config=config)
    parts: List[str] = []
    seen_text = set()
    for source in sources:
        text = _export_setlist_text(source, record, config=config)
        key = _normalize_setlist_text_for_dedupe(text)
        if not key or key in seen_text:
            continue
        seen_text.add(key)
        parts.append(text.strip())
    if parts:
        return "\n\n".join(part for part in parts if part).strip()
    return _generated_missing_setlist_text(record or {}, config=config)

def _write_text_file(path_name: str, text: str) -> None:
    with open(path_name, "w", encoding="utf-8", newline="\n") as outfile:
        outfile.write(text)
        if not text.endswith("\n"):
            outfile.write("\n")




def _adjust_show_name_for_output(record: Dict[str, str]) -> str:
    for key in ("artist", "date", "venue", "location", "parentheticals", "album_name", "show_name"):
        if record.get(key):
            record[key] = standard_ascii_text(record.get(key, ""))
    artist = (record.get("artist") or "").strip()
    date = (record.get("date") or "").strip()
    venue = (record.get("venue") or "").strip()
    location = (record.get("location") or "").strip()
    parentheticals = (record.get("parentheticals") or "").strip()
    show_name = (record.get("show_name") or "").strip()
    if artist and not date and not show_name:
        date = "xxxx-xx-xx"
        record["date"] = date
    if not show_name and artist and date:
        show_name = " ".join(part for part in [artist, date, venue, location] if part).strip()
    if show_name and parentheticals and not show_name.endswith(parentheticals):
        show_name = f"{show_name} {parentheticals}".strip()
    record["show_name"] = show_name
    return show_name



def _record_has_blank_show(record: Dict[str, str]) -> bool:
    """Return True when a metadata record has no established SHOW_NAME."""
    return not (record.get("show_name") or "").strip()


def _blank_show_reason(record: Dict[str, str]) -> str:
    """Build a concise reason string for blank/unresolved metadata records."""
    reasons: List[str] = []
    if not (record.get("show_name") or "").strip():
        reasons.append("blank SHOW_NAME")
    if not (record.get("artist") or "").strip():
        reasons.append("blank ARTIST")
    if (record.get("show_in_conflict") or "").strip().casefold() == "yes":
        reasons.append("SHOW_IN_CONFLICT=yes")
    return "; ".join(reasons) or "unresolved metadata record"


def _collect_unidentified_paths_from_metadata(records: List[Dict[str, str]]) -> List[str]:
    """Collect paths that must appear in unidentifiedShows.txt from meta*.log records.

    This pass is independent of bootlist row generation. It prevents blank-show
    metadata records from being missed when row-building reconstructs, skips, or
    otherwise changes a record later in postprocess.
    """
    paths: List[str] = []
    for record in records:
        if _record_has_blank_show(record):
            main_dir_path = (record.get("main_dir_path") or "").strip()
            if main_dir_path:
                paths.append(main_dir_path)
    return paths


def _dedupe_paths(paths: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for path_name in paths:
        clean = (path_name or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)
    return ordered


POSTPROCESS_EXTREME_THREAD_CAP = 64


def _configured_max_workers(config) -> int:
    """Return the user-supplied Max Workers value, accepting legacy attr names.

    Current Config objects use max_workers.  The legacy maxWorkers fallback is kept as a
    defensive compatibility guard for older GUI/test harness objects so
    postprocess never ignores an explicit cap and attempts one thread per
    filename group.
    """
    for attr_name in ("max_workers", "maxWorkers"):
        try:
            value = int(getattr(config, attr_name, 0) or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return 0


def _extreme_postprocess_default_workers(cpu_count: int, group_count: int) -> int:
    """Return the uncapped-by-mode but thread-safe extreme postprocess default.

    Extreme still queues every filename group as work, but it must not create
    one OS thread per group.  Use more workers than CPU-bound modes because this
    stage is mostly filesystem I/O, while keeping a hard safety ceiling.
    """
    io_workers = max(1, int(cpu_count or 1) * 4)
    return min(group_count, io_workers, POSTPROCESS_EXTREME_THREAD_CAP)


def _postprocess_worker_count(config, group_count: int) -> int:
    """Return postprocess worker count independent of search-path count.

    The inventory path-worker count is capped by queued search paths. A single
    search path can still produce many setlist/bootlist filename groups, so
    postprocess sizes its own pool. Filename groups remain the unit of work, but
    the ThreadPoolExecutor worker count must stay bounded.
    """
    try:
        group_count = int(group_count or 0)
    except Exception:
        group_count = 0
    if group_count < 2:
        return 1

    cpu_count = os.cpu_count() or 1
    mode = normalize_performance_mode(getattr(config, "performance_mode", "balanced"))
    if mode == "gentle":
        default_workers = 1
    elif mode == "balanced":
        default_workers = min(2, cpu_count, group_count)
    elif mode == "fast":
        default_workers = min(cpu_count, group_count)
    else:
        default_workers = _extreme_postprocess_default_workers(cpu_count, group_count)

    requested_max = _configured_max_workers(config)
    if requested_max > 0:
        if mode == "extreme":
            # In extreme mode, an explicit Max Workers value is the requested
            # postprocess pool size, still bounded by the number of filename
            # groups.  This keeps behavior deterministic on low-core hosts and
            # matches the user-facing meaning of "I asked for N workers."
            return max(1, min(requested_max, group_count))
        default_workers = min(default_workers, requested_max, group_count)
    return max(1, default_workers)


def _base_key_from_setlist_name(name: str) -> str:
    stem = os.path.splitext(str(name or ""))[0]
    stem = re.sub(r"\(alt\d+\)$", "", stem, flags=re.IGNORECASE)
    return stem.casefold()


def _existing_setlist_names_by_base(existing_setlist_names: Sequence[str] | None) -> Dict[str, List[str]]:
    by_base: Dict[str, List[str]] = defaultdict(list)
    for name in existing_setlist_names or []:
        clean = str(name or "").strip()
        if not clean:
            continue
        by_base[_base_key_from_setlist_name(clean)].append(clean)
    return dict(by_base)


def _prepare_record_for_bootlist_export(record: Dict[str, str]) -> Dict[str, str]:
    prepared = dict(record or {})
    show_name = _adjust_show_name_for_output(prepared)
    main_dir_path = (prepared.get("main_dir_path") or "").strip()
    artist = (prepared.get("artist") or "").strip()

    # Do not create setlist files for unresolved records. Previously this could
    # create bad placeholder setlists named only from Date + Venue/Location when
    # Artist was blank.
    if not artist and not show_name:
        prepared["_postprocess_skip_row"] = "yes"
        prepared["_postprocess_unidentified_path"] = main_dir_path
        prepared["_postprocess_base_key"] = f"__unresolved__:{main_dir_path.casefold()}:{id(prepared)}"
        return prepared
    if not show_name:
        prepared["_postprocess_skip_row"] = "yes"
        prepared["_postprocess_unidentified_path"] = main_dir_path
        prepared["_postprocess_base_key"] = f"__unresolved__:{main_dir_path.casefold()}:{id(prepared)}"
        return prepared

    base = _truncate_setlist_base(_setlist_base_from_record(prepared, fallback="Show"))
    prepared["_postprocess_setlist_base"] = base
    prepared["_postprocess_base_key"] = base.casefold()
    return prepared


def _build_bootlist_row_piece_for_base(
    prepared_records: List[Dict[str, str]],
    setlists_dir: str,
    existing_names_for_base: Sequence[str] | None = None,
    config=None,
) -> tuple[List[Dict[str, str]], List[str]]:
    """Build one conflict-free bootlist/setlist piece for a single filename base.

    All records in prepared_records share the same normalized/truncated setlist
    base.  Processing that group serially inside one worker prevents duplicate
    shows from spanning worker boundaries and avoids filename races.
    """
    used_names = set(existing_names_for_base or [])
    rows: List[Dict[str, str]] = []
    unidentified_paths: List[str] = []

    for record in prepared_records:
        throttle_point(config)
        if (record.get("_postprocess_skip_row") or "").strip().lower() == "yes":
            unidentified = (record.get("_postprocess_unidentified_path") or "").strip()
            if unidentified:
                unidentified_paths.append(unidentified)
            continue

        show_name = (record.get("show_name") or "").strip()
        main_dir_path = (record.get("main_dir_path") or "").strip()
        volume_label = (record.get("volume_label") or "").strip()
        base = (record.get("_postprocess_setlist_base") or "").strip() or _setlist_base_from_record(record, fallback="Show")
        setlist_text = _export_combined_setlist_text(record, config=config)
        setlist_name, should_write_setlist = _resolve_setlist_filename_for_text(base, setlists_dir, setlist_text, used_names)
        setlist_target = os.path.join(setlists_dir, setlist_name)
        if should_write_setlist:
            _write_text_file(setlist_target, setlist_text)
        rows.append({
            "Show": show_name,
            "Setlist": setlist_name,
            "Volume": volume_label,
            "Path": main_dir_path,
            "VolumePath": _format_bootlist_volume_path(volume_label, main_dir_path),
        })

    return rows, unidentified_paths


def _build_bootlist_rows_serial_groups(
    grouped_records: Dict[str, List[Dict[str, str]]],
    setlists_dir: str,
    config=None,
    existing_names_by_base: Dict[str, List[str]] | None = None,
) -> tuple[List[Dict[str, str]], List[str]]:
    rows: List[Dict[str, str]] = []
    unidentified_paths: List[str] = []
    total_records = sum(len(group) for group in grouped_records.values())
    progress_interval = max(1000, total_records // 10) if total_records else 0
    next_progress = progress_interval
    processed = 0

    for base_key in sorted(grouped_records):
        if is_cancel_requested() or bool(getattr(config, "cancel_requested", False)):
            raise KeyboardInterrupt
        group = grouped_records[base_key]
        piece_rows, piece_unidentified = _build_bootlist_row_piece_for_base(
            group,
            setlists_dir,
            existing_names_for_base=(existing_names_by_base or {}).get(base_key, []),
            config=config,
        )
        rows.extend(piece_rows)
        unidentified_paths.extend(piece_unidentified)
        processed += len(group)
        if total_records and (processed == total_records or (progress_interval and processed >= next_progress)):
            _postprocess_status(config, f"exporting setlists {processed}/{total_records}...")
            while progress_interval and next_progress <= processed:
                next_progress += progress_interval

    return rows, unidentified_paths


def _build_bootlist_rows_parallel_groups(
    grouped_records: Dict[str, List[Dict[str, str]]],
    setlists_dir: str,
    worker_count: int,
    config=None,
    existing_names_by_base: Dict[str, List[str]] | None = None,
) -> tuple[List[Dict[str, str]], List[str]]:
    rows: List[Dict[str, str]] = []
    unidentified_paths: List[str] = []
    total_records = sum(len(group) for group in grouped_records.values())
    progress_interval = max(1000, total_records // 10) if total_records else 0
    next_progress = progress_interval
    processed = 0

    _postprocess_status(
        config,
        f"parallel setlist/bootlist piece generation enabled: {worker_count} worker(s), {len(grouped_records)} filename group(s)",
    )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(
                _build_bootlist_row_piece_for_base,
                group,
                setlists_dir,
                (existing_names_by_base or {}).get(base_key, []),
                config,
            ): (base_key, len(group))
            for base_key, group in grouped_records.items()
        }
        for future in as_completed(future_map):
            if is_cancel_requested() or bool(getattr(config, "cancel_requested", False)):
                raise KeyboardInterrupt
            _base_key, group_size = future_map[future]
            piece_rows, piece_unidentified = future.result()
            rows.extend(piece_rows)
            unidentified_paths.extend(piece_unidentified)
            processed += group_size
            if total_records and (processed == total_records or (progress_interval and processed >= next_progress)):
                _postprocess_status(config, f"exporting setlists {processed}/{total_records}...")
                while progress_interval and next_progress <= processed:
                    next_progress += progress_interval

    return rows, unidentified_paths


def _build_bootlist_rows(records: List[Dict[str, str]], setlists_dir: str, config=None, existing_setlist_names: Sequence[str] | None = None) -> tuple[List[Dict[str, str]], List[str]]:
    prepared_records = [_prepare_record_for_bootlist_export(record) for record in records]
    grouped_records: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for record in prepared_records:
        grouped_records[(record.get("_postprocess_base_key") or "").strip() or f"__record__:{id(record)}"].append(record)

    existing_names_by_base = _existing_setlist_names_by_base(existing_setlist_names)
    worker_count = _postprocess_worker_count(config, len(grouped_records))

    if worker_count > 1:
        rows, unidentified_paths = _build_bootlist_rows_parallel_groups(
            dict(grouped_records),
            setlists_dir,
            worker_count,
            config=config,
            existing_names_by_base=existing_names_by_base,
        )
    else:
        rows, unidentified_paths = _build_bootlist_rows_serial_groups(
            dict(grouped_records),
            setlists_dir,
            config=config,
            existing_names_by_base=existing_names_by_base,
        )

    _postprocess_status(config, f"stitching bootlist row pieces: {len(rows)} row(s) from {len(grouped_records)} piece(s)")
    rows.sort(key=lambda row: ((row["Show"] or "").casefold(), (row["Path"] or "").casefold(), (row["Setlist"] or "").casefold()))
    return rows, unidentified_paths

def _format_bootlist_volume_path(volume_label: str, path_name: str) -> str:
    return format_volume_path(volume_label, path_name)


def _write_bootlist_csv(tlo_home: str, rows: List[Dict[str, str]]) -> str:
    csv_path = os.path.join(tlo_home, "bootlist.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as outfile:
        outfile.write("sep=^\n")
        outfile.write("Show^VolumePath\n")
        writer = csv.writer(outfile, delimiter="^", lineterminator="\n")
        for row in rows:
            writer.writerow([row["Show"], row.get("VolumePath") or _format_bootlist_volume_path(row.get("Volume", ""), row.get("Path", ""))])
    return csv_path



def _write_unidentified_shows(tlo_home: str, paths: List[str]) -> str:
    target = os.path.join(tlo_home, "unidentifiedShows.txt")
    seen = set()
    ordered = []

    if os.path.isfile(target):
        with open(target, "r", encoding="utf-8", errors="ignore") as infile:
            for raw_line in infile:
                clean = raw_line.strip()
                if clean and clean not in seen:
                    seen.add(clean)
                    ordered.append(clean)

    for path in paths:
        clean = (path or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            ordered.append(clean)

    ordered = sorted(ordered, key=lambda value: value.casefold())
    with open(target, "w", encoding="utf-8", newline="\n") as outfile:
        for path in ordered:
            outfile.write(path + "\n")
    return target


def _conflict_log_paths(tlo_home: str) -> List[str]:
    logs_dir = logs_dir_for_home(tlo_home)
    pattern = os.path.join(logs_dir, "conf*.log")
    return sorted(path for path in glob.glob(pattern) if os.path.isfile(path))


def _write_conflict_summary_log(tlo_home: str, records: List[Dict[str, str]] | None = None) -> str:
    """Write summary.log with conflicts plus blank/unresolved metadata records."""
    logs_dir = logs_dir_for_home(tlo_home)
    os.makedirs(logs_dir, exist_ok=True)
    target = os.path.join(logs_dir, "summary.log")
    entries: List[str] = []

    for log_path in _conflict_log_paths(tlo_home):
        source_name = os.path.basename(log_path)
        current_search_path = ""
        with open(log_path, "r", encoding="utf-8", errors="ignore") as infile:
            for raw_line in infile:
                line = raw_line.rstrip("\r\n")
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    if "for search path:" in stripped:
                        current_search_path = stripped.split("for search path:", 1)[1].strip()
                    continue
                if stripped.startswith("SEARCH_PATH:"):
                    current_search_path = stripped.split(":", 1)[1].strip()
                    continue
                entries.append(f"{source_name} | {current_search_path} | {stripped}")

    for record in records or []:
        if _record_has_blank_show(record):
            main_dir_path = (record.get("main_dir_path") or "").strip()
            if main_dir_path:
                entries.append(f"meta*.log | {main_dir_path} | BLANK_SHOW_RECORD: {_blank_show_reason(record)}")

    # Keep the summary log stable and readable if the same blank show is also
    # present in a conflict log.
    entries = list(dict.fromkeys(entries))

    with open(target, "w", encoding="utf-8", newline="\n") as outfile:
        outfile.write("# summaryLog: consolidated conflict and unresolved blank-show entries from TLOHome/logs\n")
        if entries:
            for entry in entries:
                outfile.write(entry + "\n")
        else:
            outfile.write("No conflicts or unresolved blank shows found.\n")
    return target



def _existing_setlist_names(setlists_dir: str) -> List[str]:
    if not os.path.isdir(setlists_dir):
        return []
    try:
        return [
            name for name in os.listdir(setlists_dir)
            if name.lower().endswith(SETLIST_EXTENSION)
            and os.path.isfile(os.path.join(setlists_dir, name))
        ]
    except OSError:
        return []


def _remove_replaced_setlists(tlo_home: str, replaced_rows: Sequence[Dict[str, str]], kept_rows: Sequence[Dict[str, str]]) -> None:
    """Remove setlist files that only belonged to rows being replaced.

    This is indexed once by filename rather than globbing the entire setlists
    directory once per replaced show.  It keeps postprocess fast for a small
    re-inventory against a large existing TLOHome/setlists folder.
    """
    setlists_dir = os.path.join(tlo_home, "setlists")
    if not os.path.isdir(setlists_dir) or not replaced_rows:
        return
    kept_shows = {(row.get("Show") or "").strip().casefold() for row in kept_rows}
    names = _existing_setlist_names(setlists_dir)
    by_fold = {name.casefold(): name for name in names}
    sorted_names = sorted(names, key=lambda value: value.casefold())
    to_remove = set()
    for row in replaced_rows:
        show = (row.get("Show") or "").strip()
        if not show or show.casefold() in kept_shows:
            continue
        base = _normalized_setlist_base(show, fallback="Show")
        exact = f"{base}{SETLIST_EXTENSION}"
        exact_name = by_fold.get(exact.casefold())
        if exact_name:
            to_remove.add(exact_name)
        base_fold = base.casefold()
        for name in sorted_names:
            folded = name.casefold()
            if folded.startswith(base_fold) and folded.endswith(SETLIST_EXTENSION):
                to_remove.add(name)
    for name in to_remove:
        try:
            os.remove(os.path.join(setlists_dir, name))
        except OSError:
            pass


def _is_reinventory_action(action) -> bool:
    """Return True only for re-inventory/replace decisions.

    Path-policy decisions include non-overlapping new search paths.  Those are
    not user actions and must not be normalized with normalize_volume_action(),
    because normalize_volume_action intentionally accepts only prompt choices
    such as skip or re-inventory.
    """
    text = str(action or "").strip().lower()
    return text in {
        "reinventory",
        "re-inventory",
        "re_inventory",
        "re inventory",
        "r",
        "overwrite",
        "over",
        "replace",
        "o",
        "append",
        "add",
        "a",
    }


def _overwrite_path_scopes(config) -> List[Dict[str, str]]:
    scopes: List[Dict[str, str]] = []
    for item in list(getattr(config, "inventory_path_actions", []) or []):
        if not _is_reinventory_action(item.get("action") or ""):
            continue
        scopes.append({
            "volume_key": volume_key(item.get("volume", "")),
            "path": item.get("path", ""),
            "path_key": normalize_path_for_compare(item.get("path", "")),
        })
    if scopes:
        return scopes

    # Compatibility fallback for older callers/tests that only provide the old
    # volume action map. This path keeps the pre-v207 volume-wide behavior.
    actions = dict(getattr(config, "inventory_volume_actions", {}) or {})
    for key, action in actions.items():
        raw_action = str(action or "").strip().lower()
        if raw_action in {"reinventory", "re-inventory", "re_inventory", "re inventory", "r", "overwrite", "over", "replace", "o"}:
            scopes.append({"volume_key": str(key or "").casefold(), "path": "", "path_key": ""})
    return scopes


def _row_matches_reinventory_scope(row: Dict[str, str], scope: Dict[str, str]) -> bool:
    volume = (row.get("Volume") or "").strip()
    path = (row.get("Path") or "").strip()
    if row.get("VolumePath") and (not volume or not path):
        parsed_volume, parsed_path = parse_volume_path_value(row.get("VolumePath") or "")
        volume = volume or parsed_volume
        path = path or parsed_path
    if volume_key(volume) != (scope.get("volume_key") or ""):
        return False
    scope_path = scope.get("path") or ""
    if not scope_path:
        return True
    return path_is_same_or_under(path, scope_path)


def _existing_rows_for_postprocess(config) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    existing_rows = read_bootlist_rows(config.TLOHome)
    if not existing_rows:
        return [], []
    scopes = _overwrite_path_scopes(config)
    if not scopes and not (getattr(config, "inventory_volume_actions", {}) or getattr(config, "inventory_path_actions", None)):
        # Legacy/full-refresh behavior: if no policy was established, do not keep
        # previous bootlist rows.
        return [], existing_rows
    kept_rows: List[Dict[str, str]] = []
    replaced_rows: List[Dict[str, str]] = []
    for row in existing_rows:
        if any(_row_matches_reinventory_scope(row, scope) for scope in scopes):
            replaced_rows.append(row)
        else:
            kept_rows.append(dict(row))
    return kept_rows, replaced_rows


def postprocess_metadata_outputs(config) -> Dict[str, int | str]:
    timing_entries: List[tuple[str, float]] = []
    overall_started = time.monotonic()

    _postprocess_status(config, "reading metadata logs...")
    stage_started = time.monotonic()
    current_tokens = list(getattr(config, "current_run_log_tokens", []) or [])
    runtime_records = getattr(config, "current_metadata_records", None)
    if isinstance(runtime_records, list) and runtime_records:
        records = _normalize_metadata_records_for_postprocess(runtime_records)
        elapsed = _record_postprocess_timing(timing_entries, "use in-memory metadata records", stage_started)
        _postprocess_status(config, f"using in-memory metadata records complete: {len(records)} record(s) ({_format_elapsed_seconds(elapsed)})")
    else:
        records = _parse_show_metadata_logs(config.TLOHome, tokens=current_tokens or None)
        elapsed = _record_postprocess_timing(timing_entries, "read metadata logs", stage_started)
        token_note = f" from {len(current_tokens)} current log token(s)" if current_tokens else ""
        _postprocess_status(config, f"reading metadata logs complete: {len(records)} record(s){token_note} ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "collecting unresolved paths...")
    stage_started = time.monotonic()
    metadata_unidentified_paths = _collect_unidentified_paths_from_metadata(records)
    elapsed = _record_postprocess_timing(timing_entries, "collect unresolved paths", stage_started)
    _postprocess_status(config, f"collecting unresolved paths complete: {len(metadata_unidentified_paths)} path(s) ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "resolving existing bootlist and volume policy...")
    stage_started = time.monotonic()
    existing_rows_to_keep, existing_rows_to_replace = _existing_rows_for_postprocess(config)
    elapsed = _record_postprocess_timing(timing_entries, "resolve existing bootlist and volume policy", stage_started)
    _postprocess_status(config, f"existing bootlist/volume policy complete: keep {len(existing_rows_to_keep)}, replace {len(existing_rows_to_replace)} ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "preparing setlists directory...")
    stage_started = time.monotonic()
    preserve_existing_setlists = bool(existing_rows_to_keep)
    setlists_dir = _prepare_setlists_dir(config.TLOHome, clear_existing=not preserve_existing_setlists)
    if existing_rows_to_replace:
        _remove_replaced_setlists(config.TLOHome, existing_rows_to_replace, existing_rows_to_keep)
    existing_setlist_names = _existing_setlist_names(setlists_dir) if preserve_existing_setlists else []
    elapsed = _record_postprocess_timing(timing_entries, "prepare setlists directory", stage_started)
    _postprocess_status(config, f"preparing setlists directory complete: {len(existing_setlist_names)} existing setlist name(s) tracked ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "exporting setlists and building bootlist rows...")
    stage_started = time.monotonic()
    rows, row_unidentified_paths = _build_bootlist_rows(records, setlists_dir, config=config, existing_setlist_names=existing_setlist_names)
    elapsed = _record_postprocess_timing(timing_entries, "export setlists and build bootlist rows", stage_started)
    _postprocess_status(config, f"exporting setlists and building bootlist rows complete: wrote/reused {len(rows)} row(s) ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "writing bootlist.csv...")
    stage_started = time.monotonic()
    final_rows = list(existing_rows_to_keep) + rows
    csv_path = _write_bootlist_csv(config.TLOHome, final_rows)
    elapsed = _record_postprocess_timing(timing_entries, "write bootlist.csv", stage_started)
    _postprocess_status(config, f"writing bootlist.csv complete: {len(final_rows)} total row(s) ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "writing unidentifiedShows.txt...")
    stage_started = time.monotonic()
    unidentified_paths = _dedupe_paths(metadata_unidentified_paths + row_unidentified_paths)
    unidentified_path = _write_unidentified_shows(config.TLOHome, unidentified_paths)
    elapsed = _record_postprocess_timing(timing_entries, "write unidentifiedShows.txt", stage_started)
    _postprocess_status(config, f"writing unidentifiedShows.txt complete: {len(unidentified_paths)} unresolved path(s) ({_format_elapsed_seconds(elapsed)})")

    _postprocess_status(config, "writing summary.log...")
    stage_started = time.monotonic()
    summary_log_path = _write_conflict_summary_log(config.TLOHome, records=records)
    elapsed = _record_postprocess_timing(timing_entries, "write summary.log", stage_started)
    # Overall time includes the instrumentation overhead as well as all measured stages.
    timing_entries.append(("postprocess overhead", max(0.0, time.monotonic() - overall_started - sum(seconds for _label, seconds in timing_entries))))
    _append_postprocess_timing_summary(summary_log_path, timing_entries)
    _postprocess_status(config, f"writing summary.log complete ({_format_elapsed_seconds(elapsed)})")

    total_elapsed = time.monotonic() - overall_started
    _postprocess_status(config, f"total complete ({_format_elapsed_seconds(total_elapsed)})")

    console_print(
        config,
        f"Postprocess complete: aggregated {len(records)} show metadata record(s), wrote {len(rows)} new setlist text file(s), kept {len(existing_rows_to_keep)} existing bootlist row(s), built {os.path.basename(csv_path)}, and wrote {os.path.basename(summary_log_path)}",
    )
    return {
        "record_count": len(records),
        "setlists_dir": setlists_dir,
        "bootlist_csv": csv_path,
        "unidentified_shows": unidentified_path,
        "summary_log": summary_log_path,
    }
