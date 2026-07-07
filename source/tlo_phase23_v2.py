"""Phase 2/3 metadata extraction, compliant/non-compliant path parsing, online lookup merging, grouping, and inventory-time tagging orchestration."""

__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from console_output_lib import console_print
from tlo_media_rules import MEDIA_EXTENSIONS, VIDEO_EXTENSIONS, parse_music_dir_marker
from tlo_wrapper_rules import (
    contains_wrapper_term,
    is_exact_wrapper_name,
    is_standard_video_folder_name,
    looks_like_non_main_dir,
    split_volume_part_suffix,
    split_wrapper_part_suffix,
)
from tlo_complete_path_log import load_complete_path_lines
from tlo_setlist_file_selection import find_setlist_file_for_music_dir, find_setlist_files_for_music_dir
from tlo_artist_db import ArtistMatcher, lookup_artist_master_with_status
from tlo_audio_tags import collect_group_flac_tag_info
from tlo_constants import (
    BIT24_PATTERNS,
    COUNTRY_ALIASES,
    COUNTRY_SEARCH_TERMS,
    MONTH_NAME_CASED_PATTERN,
    MONTHS,
    ORDINAL_SUFFIX,
    QUALIFIER_PATTERNS,
    US_STATE_CODES,
    US_STATE_ALIASES,
)
from tlo_models import Candidate, ShowMetadata
from tlo_text_utils import compact_ws, normalized_compare_value, standard_ascii_text
from tlo_etree_lookup import ETreeDBError, lookup_venue_and_location
from tlo_setlistfm_lookup import SetlistFMError, collect_setlists_by_performance as collect_setlistfm_setlists_by_performance, is_us_country, lookup_venue_and_location as lookup_setlistfm_venue_and_location
from tlo_setlist_metadata_lookup import extract_setlist_venue_location, is_setlist_metadata_scan_boundary, explicit_metadata_match, looks_like_sentence_prose_line
from tlo_runtime_control import throttle_point

FOUR_DIGIT_WRAPPER_RE = re.compile(r"^\d{4}$")
INTEGER_RE = re.compile(r"^\d+$")
MULTI_EXT_RE = re.compile(
    r"(?i)(?:\.(?:txt|docx?|rtf|nfo|md5|ffp|fpt|sfv|log|cue|m3u8?|pls|shn|shnf|flac|flac16|flac24|wav|mp3|m4a|aac|ogg|oga|opus|aiff?|ape|wv|alac|aucdtect))+$"
)
SEP_REQ = r"[\s._-]+"
TEXT_DATE_SEP_OPT = r"[\s._,\-]*"
YEAR4_FULL_RE_TEXT = r"(?:19|20)\d{2}"
YEAR4_PARTIAL_RE_TEXT = r"(?:(?:19|20)\d[xX]|[xX]{4})"
YEAR4_TOKEN_RE_TEXT = rf"(?:{YEAR4_FULL_RE_TEXT}|{YEAR4_PARTIAL_RE_TEXT})"
YEAR_TOKEN_RE_TEXT = rf"(?:\d{{2}}|{YEAR4_TOKEN_RE_TEXT})"
NUMERIC_COMPONENT_SEP_RE_TEXT = r"(?:\s*[._-]\s*|\s+)"
YEAR_FIRST_RE = re.compile(
    rf"(?<![0-9xX])(?P<year>{YEAR_TOKEN_RE_TEXT})(?P<sep1>{NUMERIC_COMPONENT_SEP_RE_TEXT})(?P<month>[0-9xX]{{1,2}})(?P<sep2>{NUMERIC_COMPONENT_SEP_RE_TEXT})(?P<day>[0-9xX]{{1,2}})(?![0-9xX])",
    re.IGNORECASE,
)
COMPLIANT_PRIMARY_YMD_RE = re.compile(
    rf"(?<![0-9xX])(?P<year>{YEAR4_TOKEN_RE_TEXT})-(?P<month>[0-9xX]{{1,2}})-(?P<day>[0-9xX]{{1,2}})(?![0-9xX])",
    re.IGNORECASE,
)
YEAR_SPACE_MONTH_PUNCT_DAY_RE = re.compile(r"a^")  # Disabled: all-numeric mixed separators are no longer allowed.
END_FIRST_RE = re.compile(
    rf"(?<![0-9xX])(?P<a>[0-9xX]{{1,2}})(?P<sep1>{NUMERIC_COMPONENT_SEP_RE_TEXT})(?P<b>[0-9xX]{{1,2}})(?P<sep2>{NUMERIC_COMPONENT_SEP_RE_TEXT})(?P<year>{YEAR_TOKEN_RE_TEXT})(?![0-9xX])",
    re.IGNORECASE,
)
SLASH_END_FIRST_RE = re.compile(
    rf"(?<![0-9xX])(?P<a>[0-9xX]{{1,2}})\s*/\s*(?P<b>[0-9xX]{{1,2}})\s*/\s*(?P<year>\d{{2}}|{YEAR4_FULL_RE_TEXT})(?![0-9xX])",
    re.IGNORECASE,
)
MONTH_DAY_YEAR_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<month_name>{MONTH_NAME_CASED_PATTERN}){TEXT_DATE_SEP_OPT}(?P<day>\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?){TEXT_DATE_SEP_OPT}(?P<year>{YEAR_TOKEN_RE_TEXT})(?![A-Za-z0-9])"
)
DAY_MONTH_YEAR_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<day>\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?){TEXT_DATE_SEP_OPT}(?P<month_name>{MONTH_NAME_CASED_PATTERN}){TEXT_DATE_SEP_OPT}(?P<year>{YEAR_TOKEN_RE_TEXT})(?![A-Za-z0-9])"
)
YEAR_MONTHNAME_DAY_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<year>{YEAR4_TOKEN_RE_TEXT}){TEXT_DATE_SEP_OPT}(?P<month_name>{MONTH_NAME_CASED_PATTERN}){TEXT_DATE_SEP_OPT}(?P<day>\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?)(?![A-Za-z0-9])"
)
MONTH_YEAR_RE = re.compile(
    rf"(?<![A-Za-z0-9])(?P<month_name>{MONTH_NAME_CASED_PATTERN}){TEXT_DATE_SEP_OPT}(?P<year>{YEAR4_TOKEN_RE_TEXT})(?![A-Za-z0-9])"
)
FOUR_PLUS_FOUR_RE = re.compile(rf"(?<![0-9xX])(?P<year>{YEAR4_TOKEN_RE_TEXT})(?P<four_sep>[ -])(?P<monthday>\d{{4}})(?![0-9xX])", re.IGNORECASE)
DASHED_YEAR_RANGE_RE = re.compile(rf"(?<![\d._/-])(?P<range>(?:{YEAR4_FULL_RE_TEXT}|\d{{2}})(?:[-_](?:{YEAR4_FULL_RE_TEXT}|\d{{2}})){{1,3}})(?![\d._/-])")
COMPACT_YMD_RE = re.compile(rf"(?<![0-9xX])(?P<year>{YEAR4_TOKEN_RE_TEXT})(?P<month>[0-9xX]{{2}})(?P<day>[0-9xX]{{2}})(?![0-9xX])", re.IGNORECASE)
COMPACT_YEAR_MONTH_OR_RANGE_RE = re.compile(rf"(?<![0-9xX])(?P<year>{YEAR4_FULL_RE_TEXT})(?P<tail>\d{{2}})(?![0-9xX])")
COMPACT_YEAR_RANGE_RE = re.compile(r"a^")  # Disabled: ranges must be dash/underscore-delimited, except yyyyYY ambiguity handled above.
MAX_YEAR_RANGE_SPAN = 5
THE_PREFIX_RE = re.compile(r"^(?:the|a)\s+", re.IGNORECASE)
THE_SUFFIX_RE = re.compile(r",\s*(?:the|a)$", re.IGNORECASE)
ORDINAL_RE = re.compile(r"(?i)(\d{1,2})(?:st|nd|rd|th)$")
MULTIPART_CITY_PREFIXES = [
    "Marina Del", "de la", "La", "El", "San", "Santa", "Le", "Los", "Las", "New", "West", "North", "Al",
    "East", "Villa", "South", "Saint", "Lake", "Bad", "Les", "Mount", "Santiago", "Nova",
    "Port", "Valea", "Puerto", "Nuevo", "Fort", "Sao", "Colonia", "Santo", "Monte", "Guadalupe",
    "Río", "Sankt", "Great", "Nueva", "Nea", "Cerro", "Rancho", "Pueblo", "Rio", "Agua",
    "Emiliano", "Campo", "Palo", "Upper", "Lower", "College", "Old", "Grand",
]
MULTIPART_CITY_PREFIXES.sort(key=lambda value: (-len(value.split()), -len(value), value.casefold()))

COMMON_NON_US_REGION_TERMS = {
    "new south wales", "nsw", "victoria", "vic", "queensland", "qld",
    "south australia", "western australia", "tasmania", "tas",
    "australian capital territory", "act", "northern territory", "nt",
    "ontario", "on", "quebec", "québec", "qc", "british columbia", "bc",
    "alberta", "ab", "manitoba", "mb", "saskatchewan", "sk",
    "nova scotia", "ns", "new brunswick", "nb", "newfoundland",
    "newfoundland and labrador", "labrador", "nl", "prince edward island", "pe",
    "yukon", "yt", "northwest territories", "nu", "nunavut",
}


def _clean_piece(text: str) -> str:
    value = compact_ws((text or "").replace("_", " "))
    value = _strip_multi_extension(value)
    value = value.strip(" ,;:_-./\\")
    return compact_ws(value)



def _strip_multi_extension(name: str) -> str:
    return MULTI_EXT_RE.sub("", name or "")



def _strip_trailing_parenthetical_items(text: str) -> str:
    value = compact_ws(text)
    while value:
        updated = re.sub(r"\s*\([^()]*\)\s*$", "", value).strip()
        if updated == value:
            break
        value = compact_ws(updated)
    return compact_ws(value)



def _strip_trailing_parenthetical_items_with_cache(text: str) -> Tuple[str, str]:
    value = compact_ws(text)
    cached: List[str] = []
    while value:
        match = re.search(r"\s*(\([^()]*\))\s*$", value)
        if not match:
            break
        cached.insert(0, match.group(1).strip())
        value = compact_ws(value[: match.start()])
    return compact_ws(value), " ".join(cached)



def _is_music_file(path_name: str) -> bool:
    return bool(path_name and os.path.isfile(path_name) and os.path.splitext(path_name)[1].lower() in MEDIA_EXTENSIONS)


def _is_video_media_file_name(path_name: str) -> bool:
    return os.path.splitext(path_name or "")[1].lower() in VIDEO_EXTENSIONS


def _all_media_files_have_extension(paths: Sequence[str], extension: str) -> bool:
    files = [path_name for path_name in (paths or []) if path_name]
    return bool(files) and all(os.path.splitext(path_name)[1].lower() == extension for path_name in files)


def _group_media_extensions(group: dict) -> List[str]:
    extensions: List[str] = []
    for value in group.get("music_media_extensions", []) or []:
        ext = str(value or "").lower()
        if ext and ext not in extensions:
            extensions.append(ext)
    for path_name in group.get("music_files", []) or []:
        ext = os.path.splitext(path_name or "")[1].lower()
        if ext and ext in MEDIA_EXTENSIONS and ext not in extensions:
            extensions.append(ext)
    return extensions


def _group_media_is_all_extension(group: dict, extension: str) -> bool:
    extensions = _group_media_extensions(group)
    return bool(extensions) and all(ext == extension for ext in extensions)


def _group_has_video_media(group: dict) -> bool:
    return any(ext in VIDEO_EXTENSIONS for ext in _group_media_extensions(group))


def _iter_group_media_files(group: dict, limit: Optional[int] = None):
    """Yield media files from known group directories only when later logic needs them."""
    seen = set()
    yielded = 0
    for path_name in group.get("music_files", []) or []:
        normalized = os.path.normpath(path_name or "")
        if normalized and normalized.casefold() not in seen and _is_music_file(normalized):
            seen.add(normalized.casefold())
            yield normalized
            yielded += 1
            if limit is not None and yielded >= limit:
                return
    for music_dir in group.get("music_dirs", []) or []:
        try:
            with os.scandir(music_dir) as entries:
                children = sorted(list(entries), key=lambda entry: entry.name.lower())
        except (OSError, PermissionError):
            continue
        for entry in children:
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                normalized = os.path.normpath(entry.path)
                if normalized.casefold() in seen or not _is_music_file(normalized):
                    continue
                seen.add(normalized.casefold())
                yield normalized
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            except (OSError, PermissionError):
                continue


def _flac_tag_sample_files_for_group(group: dict, max_files: int = 2) -> List[str]:
    samples: List[str] = []
    for path_name in _iter_group_media_files(group):
        if os.path.splitext(path_name)[1].lower() in {".flac", ".shn", ".shnf"}:
            samples.append(path_name)
            if len(samples) >= max_files:
                break
    return samples


def _compliant_mp3_year_show_name(group: dict, folder_name: str) -> str:
    cleaned = _clean_piece(folder_name)
    if not re.fullmatch(r"\d{4}", cleaned or ""):
        return ""
    year = int(cleaned)
    if not (1959 <= year <= 2005):
        return ""
    if "billboard" not in os.path.normpath(group.get("main_dir_path", "")).lower():
        return ""
    if not _group_media_is_all_extension(group, ".mp3"):
        return ""
    return cleaned


def _compliant_text_has_folder_pattern(text: str) -> bool:
    cleaned = _clean_piece(text)
    if not cleaned:
        return False
    if _compliant_string_date_matches(cleaned, allow_string2=False):
        return True
    if _compliant_string_date_matches(cleaned, allow_string2=True):
        return True
    return bool(_match_string_dash_string(cleaned))


def _video_path_pattern_candidates(group: dict) -> List[Tuple[str, str]]:
    if not _group_has_video_media(group):
        return []
    roots = list(group.get("music_dirs", []) or [])
    if group.get("main_dir_path"):
        roots.insert(0, group.get("main_dir_path"))
    candidates: List[Tuple[str, str]] = []
    seen = set()
    for root in roots:
        for cleaned, part_path in _all_clean_path_parts(root):
            if not cleaned or _phase23_should_prune_dir(cleaned):
                continue
            key = (cleaned.casefold(), os.path.normcase(os.path.normpath(part_path)))
            if key in seen:
                continue
            seen.add(key)
            candidates.append((cleaned, part_path))
    return candidates


def _compliant_pattern_text_for_group(record: ShowMetadata, group: dict, observations: List[str]) -> Tuple[str, str]:
    """Return (text, source_path) used by compliant folder-name pattern matching."""
    video_candidates = _video_path_pattern_candidates(group)
    if video_candidates:
        for candidate_text, candidate_path in video_candidates:
            if _compliant_text_has_folder_pattern(candidate_text):
                observations.append("compliant video folder matched: path subdirectory checked for compliant folder pattern")
                return candidate_text, candidate_path
        # Backward-compatible fallback for VIDEO_TS/BDMV-style wrappers: even if
        # no pattern is found, use the immediate parent rather than the wrapper
        # folder as the final compliant fallback text.
        main_dir_path = os.path.normpath(record.main_dir_path or "")
        folder_name = os.path.basename(main_dir_path) or record.main_dir_name
        if is_standard_video_folder_name(folder_name):
            parent_dir = os.path.dirname(main_dir_path)
            parent_text = _clean_piece(os.path.basename(parent_dir))
            if parent_text:
                observations.append("compliant video wrapper folder matched; parent directory checked for compliant folder pattern")
                return parent_text, parent_dir
    return _clean_piece(record.main_dir_name), record.main_dir_path


def _phase23_should_prune_dir(dirname: str) -> bool:
    """Return True when phase 2/3 discovery must not scan or descend into dirname."""
    name = str(dirname or "").strip().lower()
    return name.endswith("-ignoredir") or name in {"$recycle.bin", "system volume information"}




def _new_music_entry(music_dir: str) -> dict:
    return {
        "music_dir": os.path.normpath(music_dir or ""),
        "music_files": [],
        "music_sample_files": [],
        "music_file_count": 0,
        "music_media_extensions": [],
        "has_marker_count": False,
    }


def _add_music_sample(entry: dict, sample_path: str) -> None:
    normalized = os.path.normpath(sample_path or "")
    if not normalized:
        return
    if normalized not in entry["music_files"]:
        entry["music_files"].append(normalized)
    if normalized not in entry["music_sample_files"]:
        entry["music_sample_files"].append(normalized)


def _add_music_extension(entry: dict, extension: str) -> None:
    ext = str(extension or "").lower()
    if ext and ext in MEDIA_EXTENSIONS and ext not in entry["music_media_extensions"]:
        entry["music_media_extensions"].append(ext)


def _count_media_files_in_dir(music_dir: str) -> int:
    """Count media files in a known music directory without carrying their names forward."""
    count = 0
    try:
        with os.scandir(music_dir) as entries:
            children = list(entries)
    except (OSError, PermissionError, FileNotFoundError):
        return 0
    for entry in children:
        try:
            if entry.is_file(follow_symlinks=False) and _is_music_file(entry.path):
                count += 1
        except (OSError, PermissionError):
            continue
    return count


def _entry_from_media_files(music_dir: str, media_files: Sequence[str]) -> dict:
    entry = _new_music_entry(music_dir)
    for path_name in sorted(media_files or [], key=lambda value: value.lower()):
        _add_music_sample(entry, path_name)
        _add_music_extension(entry, os.path.splitext(path_name)[1])
    entry["music_file_count"] = len(entry["music_files"])
    return entry


def _discover_music_dirs(config, start_path: str) -> List[dict]:
    discovered: List[dict] = []

    def walk(current_path: str):
        # Phase 2/3 performs its own music-directory discovery from the search
        # root, so it must enforce the same hard-prune rules as phase 1.
        # Any directory whose visible name ends in -ignoreDir is disregarded: it
        # is not scanned, not recorded, and no further descent takes place.
        if _phase23_should_prune_dir(os.path.basename(os.path.normpath(current_path))):
            return

        try:
            with os.scandir(current_path) as entries:
                children = sorted(list(entries), key=lambda entry: entry.name.lower())
        except (OSError, PermissionError) as exc:
            config.logs.dead_end("INACCESSIBLE %s | %s", current_path, exc)
            return

        media_files: List[str] = []
        child_dirs: List[str] = []
        for entry in children:
            try:
                # Check the visible entry name before file/dir type checks so
                # protected or symlinked pruned directories are never touched.
                if _phase23_should_prune_dir(entry.name):
                    continue
                if entry.is_file(follow_symlinks=False) and _is_music_file(entry.path):
                    media_files.append(entry.path)
                elif entry.is_dir(follow_symlinks=False):
                    child_dirs.append(entry.path)
            except (OSError, PermissionError) as exc:
                config.logs.dead_end("INACCESSIBLE %s | %s", entry.path, exc)

        if media_files:
            discovered.append(_entry_from_media_files(current_path, media_files))
            return

        for child_dir in child_dirs:
            walk(child_dir)

    walk(start_path)
    return discovered


def _discover_music_dirs_from_logged_paths(config, logged_paths: List[str], start_path: str) -> List[dict]:
    """Build music directory entries from the Phase 1 complete-path log.

    New Phase 1 logs one compact marker per music directory instead of every
    media file.  Legacy logs that contain individual media filenames are still
    understood for compatibility.
    """
    normalized_start = os.path.normpath(os.path.abspath(start_path))
    media_by_dir: Dict[str, dict] = {}

    def under_start(path_name: str) -> bool:
        try:
            normalized_path = os.path.normpath(path_name)
            return os.path.commonpath([normalized_start, normalized_path]) == normalized_start
        except ValueError:
            return False

    for path_name in logged_paths:
        throttle_point(config)
        marker = parse_music_dir_marker(path_name)
        if marker:
            music_dir = os.path.normpath(marker.get("dir", ""))
            if not music_dir or not under_start(music_dir):
                continue
            entry = media_by_dir.setdefault(music_dir, _new_music_entry(music_dir))
            entry["music_file_count"] = max(entry.get("music_file_count", 0), int(marker.get("count") or 0))
            entry["has_marker_count"] = True
            _add_music_extension(entry, marker.get("ext", ""))
            _add_music_sample(entry, marker.get("sample", ""))
            continue

        try:
            normalized_path = os.path.normpath(path_name)
        except (TypeError, ValueError):
            continue
        if not under_start(normalized_path):
            continue
        if _is_music_file(normalized_path):
            music_dir = os.path.dirname(normalized_path)
            entry = media_by_dir.setdefault(music_dir, _new_music_entry(music_dir))
            _add_music_extension(entry, os.path.splitext(normalized_path)[1])
            # v215+ Phase 1 logs only one representative media file path.  Count
            # direct media files later from the known directory, but keep only
            # representative sample paths in memory/logs. Legacy logs with many
            # media paths are also compacted to representative samples here.
            if not entry.get("has_marker_count"):
                entry["music_file_count"] = max(entry.get("music_file_count", 0), _count_media_files_in_dir(music_dir) or 1)
            _add_music_sample(entry, normalized_path)

    return [
        dict(entry, music_files=sorted(entry.get("music_files", []), key=lambda value: value.lower()), music_sample_files=sorted(entry.get("music_sample_files", []), key=lambda value: value.lower()))
        for _music_dir, entry in sorted(media_by_dir.items(), key=lambda item: item[0].lower())
    ]



def _volume_part_parent_info(music_dir_entries: Sequence[dict]) -> Dict[str, dict]:
    """Return parent-level aggregation info for collection-style volume folders.

    Volume suffixes such as ``(Vol 1)`` and ``(Volume 2)`` are only aggregated
    when sibling music directories under the same parent have different stripped
    base names.  That represents a collection parent such as
    ``Bob Dylan - Collection/Early Days (Vol 1)`` plus
    ``Bob Dylan - Collection/Latter Days (Vol 2)``.  Same-base siblings such as
    ``Show Name (Volume 1)`` plus ``Show Name (Volume 2)`` remain separate
    inventory entries so each row points to its own folder.
    """
    rows_by_parent: Dict[str, List[Tuple[str, str, str]]] = {}
    for entry in music_dir_entries or []:
        music_dir = _entry_music_dir(entry) if isinstance(entry, dict) else os.path.normpath(str(entry or ""))
        if not music_dir:
            continue
        folder_name = os.path.basename(os.path.normpath(music_dir))
        parent_dir = os.path.dirname(os.path.normpath(music_dir))
        if not parent_dir:
            continue
        base_name, suffix = split_volume_part_suffix(folder_name)
        if not suffix:
            continue
        rows_by_parent.setdefault(os.path.normcase(parent_dir), []).append((parent_dir, base_name, suffix))

    info: Dict[str, dict] = {}
    for parent_key, rows in rows_by_parent.items():
        if len(rows) < 2:
            continue
        parent_dir = rows[0][0]
        bases = [compact_ws(base) for _parent, base, _suffix in rows if compact_ws(base)]
        distinct_bases = {base.casefold(): base for base in bases}
        # Same-base siblings are separate shows/releases: for example
        #   Bill Dickens 1987-03-14 Great Venue NY NY (Volume 1)
        #   Bill Dickens 1987-03-14 Great Venue NY NY (Volume 2)
        # They should produce two inventory rows with the same stripped show base
        # and size-aware setlist alternates, not one aggregate parent row.
        if len(distinct_bases) <= 1:
            continue
        aggregate_name = os.path.basename(parent_dir)
        info[parent_key] = {
            "parent_dir": parent_dir,
            "aggregate_album_name": aggregate_name,
            "aggregate_release_base": "",
            "common_volume_base": False,
        }
    return info


def _wrapper_release_aggregation_info(music_dir: str, volume_parent_info: Optional[Dict[str, dict]] = None) -> Optional[Dict[str, str]]:
    """Return aggregation metadata for non-compliant wrapper/part folders.

    Exact wrapper names such as CD1, Disc 1, or flac aggregate to their parent
    folder. Suffix forms such as Big Release CD 1 aggregate with sibling folders
    that share the same parent and the same stripped release base. Volume-style
    suffixes such as (Volume 1), (Vol. 2), and (v.3) aggregate under their
    parent only when at least two sibling music directories use volume suffixes
    with different stripped base names. Same-base volume siblings remain
    separate inventory entries.
    """
    normalized = os.path.normpath(music_dir)
    folder_name = os.path.basename(normalized)
    parent_dir = os.path.dirname(normalized)
    if not parent_dir:
        return None

    volume_base, volume_suffix = split_volume_part_suffix(folder_name)
    parent_key = os.path.normcase(parent_dir)
    if volume_suffix and volume_parent_info and parent_key in volume_parent_info:
        info = volume_parent_info[parent_key]
        aggregate_name = info.get("aggregate_album_name", "")
        return {
            "aggregation_key": f"volume::{parent_key}",
            "main_dir_path": parent_dir,
            "main_dir_name": os.path.basename(parent_dir),
            "aggregate_album_name": aggregate_name,
            "aggregate_release_base": info.get("aggregate_release_base", ""),
            "aggregation_reason": f"volume_suffix:{volume_suffix}",
        }

    base_name, suffix = split_wrapper_part_suffix(folder_name)
    if suffix:
        if base_name:
            key = f"suffix::{os.path.normcase(parent_dir)}::{base_name.casefold()}"
            return {
                "aggregation_key": key,
                "main_dir_path": parent_dir,
                "main_dir_name": os.path.basename(parent_dir),
                "aggregate_album_name": base_name,
                "aggregate_release_base": base_name,
                "aggregation_reason": f"wrapper_suffix:{suffix}",
            }
        key = f"exact::{os.path.normcase(parent_dir)}"
        return {
            "aggregation_key": key,
            "main_dir_path": parent_dir,
            "main_dir_name": os.path.basename(parent_dir),
            "aggregate_album_name": "",
            "aggregate_release_base": "",
            "aggregation_reason": f"wrapper_folder:{folder_name}",
        }

    return None


def _unique_paths_preserve_order(paths: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for path_name in paths:
        normalized = os.path.normpath(path_name or "")
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered

def _entry_music_dir(entry: dict) -> str:
    return os.path.normpath(entry.get("music_dir", ""))


def _extend_unique(target: List[str], values: Sequence[str]) -> None:
    seen = {os.path.normcase(os.path.normpath(value)) for value in target if value}
    for value in values or []:
        normalized = os.path.normpath(value or "")
        if not normalized:
            continue
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        target.append(normalized)


def _new_group_bucket(main_dir_path: str, main_dir_name: str, aggregate_album_name: str = "", aggregate_release_base: str = "", aggregation_reason: str = "") -> dict:
    return {
        "main_dir_path": os.path.normpath(main_dir_path),
        "main_dir_name": main_dir_name,
        "music_dirs": [],
        "music_files": [],
        "music_sample_files": [],
        "music_file_count": 0,
        "music_media_extensions": [],
        "aggregate_album_name": aggregate_album_name,
        "aggregate_release_base": aggregate_release_base,
        "aggregation_reason": aggregation_reason,
    }


def _add_entry_to_bucket(bucket: dict, entry: dict) -> None:
    music_dir = _entry_music_dir(entry)
    if music_dir:
        bucket["music_dirs"].append(music_dir)
    _extend_unique(bucket["music_files"], entry.get("music_files", []))
    _extend_unique(bucket["music_sample_files"], entry.get("music_sample_files", []))
    _extend_unique(bucket["music_media_extensions"], entry.get("music_media_extensions", []))
    bucket["music_file_count"] += int(entry.get("music_file_count") or len(entry.get("music_files", [])) or 0)


def _build_groups_from_search_path(config, start_path: str) -> List[dict]:
    logged_paths = load_complete_path_lines(config)
    music_dir_entries = _discover_music_dirs_from_logged_paths(config, logged_paths, start_path)

    # Non-compliant mode treats sibling release parts as one logical show when
    # the music directory is, or ends in, a wrapper-like disc/part suffix.
    # Compliant mode remains one group per music directory.
    buckets: Dict[str, dict] = {}
    volume_parent_info = _volume_part_parent_info(music_dir_entries)
    if getattr(config, "compliant", False):
        for entry in music_dir_entries:
            music_dir = _entry_music_dir(entry)
            key = f"single::{os.path.normcase(os.path.normpath(music_dir))}"
            bucket = _new_group_bucket(music_dir, os.path.basename(os.path.normpath(music_dir)))
            _add_entry_to_bucket(bucket, entry)
            buckets[key] = bucket
    else:
        for entry in sorted(music_dir_entries, key=lambda item: _entry_music_dir(item).lower()):
            throttle_point(config)
            music_dir = _entry_music_dir(entry)
            info = _wrapper_release_aggregation_info(music_dir, volume_parent_info)
            if info:
                key = info["aggregation_key"]
                bucket = buckets.setdefault(key, _new_group_bucket(
                    info["main_dir_path"],
                    info["main_dir_name"],
                    aggregate_album_name=info.get("aggregate_album_name", ""),
                    aggregate_release_base=info.get("aggregate_release_base", ""),
                    aggregation_reason=info.get("aggregation_reason", ""),
                ))
            else:
                key = f"single::{os.path.normcase(music_dir)}"
                bucket = buckets.setdefault(key, _new_group_bucket(music_dir, os.path.basename(music_dir)))
            _add_entry_to_bucket(bucket, entry)

    groups: List[dict] = []
    for _key, bucket in sorted(buckets.items(), key=lambda item: (item[1]["main_dir_path"].lower(), item[0].lower())):
        throttle_point(config)
        music_dirs = _unique_paths_preserve_order(bucket.get("music_dirs", []))
        music_files = _unique_paths_preserve_order(sorted(bucket.get("music_files", []), key=lambda value: value.lower()))
        music_sample_files = _unique_paths_preserve_order(sorted(bucket.get("music_sample_files", []), key=lambda value: value.lower()))
        music_media_extensions = sorted({str(ext or "").lower() for ext in bucket.get("music_media_extensions", []) if str(ext or "").strip()})
        main_dir_path = os.path.normpath(bucket["main_dir_path"])
        setlist_files: List[str] = []
        for music_dir in music_dirs:
            setlist_files.extend(find_setlist_files_for_music_dir(logged_paths, music_dir, main_dir_path))
        setlist_files = _unique_paths_preserve_order(setlist_files)
        chosen = setlist_files[0] if setlist_files else ""
        item = {
            "main_dir_path": main_dir_path,
            "main_dir_name": bucket["main_dir_name"],
            "music_dirs": music_dirs,
            "music_files": music_files,
            "music_sample_files": music_sample_files,
            "music_media_extensions": music_media_extensions,
            "txt_files": setlist_files,
            "setlist_files": setlist_files,
            "setlist_file": chosen,
            "aggregate_album_name": bucket.get("aggregate_album_name", ""),
            "aggregate_release_base": bucket.get("aggregate_release_base", ""),
            "aggregation_reason": bucket.get("aggregation_reason", ""),
        }
        item["music_file_count"] = int(bucket.get("music_file_count") or len(item["music_files"]))
        if getattr(config, "compliant", False):
            item.update({
                "flac_tag_samples": [],
                "flac_tag_artist_values": [],
                "flac_tag_album_values": [],
                "flac_tag_albumartist_values": [],
                "flac_tag_date_values": [],
            })
        else:
            item.update(collect_group_flac_tag_info(_flac_tag_sample_files_for_group(item)))
        groups.append(item)

    return groups

def _path_parts(path_name: str) -> List[str]:
    parts: List[str] = []
    current = os.path.normpath(path_name)
    while True:
        head, tail = os.path.split(current)
        if tail:
            parts.append(tail)
        if not head or head == current:
            break
        current = head
    parts = list(reversed(parts))
    # On WSL/Linux, Windows drive-rooted inputs such as D:\Music are
    # normalized to /mnt/d/Music.  The /mnt/<drive> mount prefix is storage
    # plumbing, not music metadata.  Do not let /mnt or the drive letter become
    # candidate artist/date/location path parts, and do not let a comma-bearing
    # artist folder such as "Dudek, Les" be effectively displaced by /mnt/d.
    if len(parts) >= 2 and parts[0].casefold() == "mnt" and re.fullmatch(r"[A-Za-z]", parts[1] or ""):
        return parts[2:]
    return parts



def _is_wrapper(name: str) -> bool:
    stripped = compact_ws(name)
    if not stripped:
        return True
    if FOUR_DIGIT_WRAPPER_RE.fullmatch(stripped):
        return True
    return looks_like_non_main_dir(stripped) or is_exact_wrapper_name(stripped) or contains_wrapper_term(stripped)



def _candidate_path_parts(music_dir: str) -> List[Tuple[str, str]]:
    parts = _path_parts(music_dir)
    candidates: List[Tuple[str, str]] = []
    for idx in range(len(parts) - 1, -1, -1):
        raw = parts[idx]
        cleaned = _clean_piece(_strip_trailing_parenthetical_items(raw))
        if not cleaned or _is_wrapper(cleaned):
            continue
        part_path = os.path.join(os.sep, *parts[: idx + 1]) if os.path.isabs(music_dir) else os.path.join(*parts[: idx + 1])
        candidates.append((cleaned, part_path))
    return candidates



def _all_clean_path_parts(music_dir: str) -> List[Tuple[str, str]]:
    parts = _path_parts(music_dir)
    results: List[Tuple[str, str]] = []
    for idx in range(len(parts) - 1, -1, -1):
        raw = parts[idx]
        cleaned = _clean_piece(_strip_trailing_parenthetical_items(raw))
        if not cleaned:
            continue
        part_path = os.path.join(os.sep, *parts[: idx + 1]) if os.path.isabs(music_dir) else os.path.join(*parts[: idx + 1])
        results.append((cleaned, part_path))
    return results



def _eligible_artist_path_parts(group: dict) -> List[Tuple[str, str]]:
    parts: List[Tuple[str, str]] = []
    seen = set()
    music_dirs = list(group.get("music_dirs", []) or [])
    if not music_dirs and group.get("main_dir_path"):
        music_dirs = [group.get("main_dir_path")]
    for music_dir in music_dirs:
        for cleaned, part_path in _all_clean_path_parts(music_dir):
            if INTEGER_RE.fullmatch(cleaned) or len(cleaned) == 1 or _is_wrapper(cleaned):
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            parts.append((cleaned, part_path))
    return parts



def _letters_only_compare(text: str) -> str:
    return re.sub(r"[^a-z]+", "", (text or "").lower())



def _has_subset_relationship(left: str, right: str) -> bool:
    left_norm = _letters_only_compare(left)
    right_norm = _letters_only_compare(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm



def _normalized_length(text: str) -> int:
    return len(_letters_only_compare(text))



def _strip_string1_articles(text: str) -> str:
    value = compact_ws(text)
    value = THE_PREFIX_RE.sub("", value)
    value = THE_SUFFIX_RE.sub("", value)
    return compact_ws(value)



def _normalize_year_token(token: str) -> str:
    value = (token or "").strip().lower()
    if not value:
        return ""
    if re.fullmatch(r"\d{2}", value):
        year = int(value)
        return f"{2000 + year:04d}" if year < 35 else f"{1900 + year:04d}"
    if re.fullmatch(YEAR4_FULL_RE_TEXT, value):
        return value
    if re.fullmatch(YEAR4_PARTIAL_RE_TEXT, value):
        return value
    return ""


def _unknown_placeholders_are_right_suffix(year_norm: str, month_norm: str, day_norm: str) -> bool:
    """Allow x placeholders only as a contiguous right-side suffix.

    Valid examples include 2001-04-1x, 2001-04-xx, 2004-0x-xx,
    200x-xx-xx, 202x-xx-xx, and xxxx-xx-xx. Once an x appears
    in the fourth digit of the year, the only broader unknown-year form
    is xxxx; examples such as 20xx-xx-xx and 2xxx-xx-xx are rejected.
    Invalid examples also include xxxx-04-14, 2001-x4-14,
    2001-xx-14, and 2001-04-x4.
    """
    compact = f"{year_norm}{month_norm}{day_norm}".lower()
    return bool(re.fullmatch(r"[0-9]*x*", compact))


def _normalize_partial_component(token: str, component: str) -> str:
    value = (token or "").strip().lower()
    if not value:
        return ""
    if value in {"0", "00", "x", "xx"}:
        return "xx"
    if not re.fullmatch(r"[0-9x]{1,2}", value):
        return ""
    if value.isdigit():
        number = int(value)
        if component == "month":
            if not 1 <= number <= 12:
                return ""
        else:
            if not 1 <= number <= 31:
                return ""
        return f"{number:02d}"
    if len(value) == 1:
        return "xx" if value == "x" else ""
    if value == "xx":
        return value
    first, second = value[0], value[1]
    if component == "month":
        if second == "x":
            if first not in {"0", "1"}:
                return ""
            return value
        if first == "x":
            if second not in "0123456789":
                return ""
            return value
        return ""
    if second == "x":
        if first not in {"0", "1", "2", "3"}:
            return ""
        return value
    if first == "x":
        return value
    return ""



def _normalize_date(year: str, month: str, day: str) -> str:
    year_norm = _normalize_year_token(year)
    month_norm = _normalize_partial_component(month, "month")
    day_norm = _normalize_partial_component(day, "day")
    if not year_norm or not month_norm or not day_norm:
        return ""
    if not _unknown_placeholders_are_right_suffix(year_norm, month_norm, day_norm):
        return ""
    if year_norm.isdigit() and month_norm.isdigit() and day_norm.isdigit():
        try:
            datetime(int(year_norm), int(month_norm), int(day_norm))
        except ValueError:
            return ""
    return f"{year_norm}-{month_norm}-{day_norm}"


def _normalize_filename_date(date_value: str) -> str:
    """Return a filename-derived date in normalized form without stripping day precision."""
    return date_value or ""




def _normalize_year_range(left: str, right: str, *, enforce_max_span: bool = True) -> str:
    """Normalize a 4-digit year range as yyyy-yyyy.

    Explicit four-digit ranges such as 1917-1939 are valid as long as the
    years increase left-to-right.  The five-year span cap is retained only for
    shorthand-derived ranges where a two-digit component had to be expanded.
    """
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not (re.fullmatch(YEAR4_FULL_RE_TEXT, left_text) and re.fullmatch(YEAR4_FULL_RE_TEXT, right_text)):
        return ""
    if int(right_text) <= int(left_text):
        return ""
    if enforce_max_span and int(right_text) - int(left_text) > MAX_YEAR_RANGE_SPAN:
        return ""
    return f"{left_text}-{right_text}"


def _expand_two_digit_year_near_base(value: str, base_year: int) -> str:
    """Expand a two-digit range component near the preceding year.

    The normal case keeps the component in the same century (1996-97 ->
    1997). A century rollover is allowed only for values such as 1999-00,
    where the base year is near the end of the century and the short year is
    near the beginning of the next one. This rejects decreasing ranges such as
    1998-97 instead of treating them as 1998-2097.
    """
    text = str(value or "").strip()
    if re.fullmatch(YEAR4_FULL_RE_TEXT, text):
        return text
    if not re.fullmatch(r"\d{2}", text):
        return ""
    short = int(text)
    century = (base_year // 100) * 100
    same_century = century + short
    if same_century > base_year and 1900 <= same_century <= 2099:
        return f"{same_century:04d}"
    base_short = base_year % 100
    if base_short >= 90 and short <= 35:
        rolled = century + 100 + short
        if 1900 <= rolled <= 2099:
            return f"{rolled:04d}"
    return ""


def _normalize_dashed_year_range(range_text: str) -> str:
    """Normalize dash/underscore year ranges like 1996-97, 96_98, and 1996-1998.

    Ranges may use only dashes or underscores, not dots, spaces, slashes, or
    compact 8-digit forms. Each successive component must increase.  Fully
    explicit four-digit ranges are not span-capped; shorthand/mixed ranges keep
    the five-year cap to avoid false positives.
    """
    raw = str(range_text or "").strip()
    if not raw or _is_audio_rate_depth_reference(raw):
        return ""
    if "-" in raw and "_" in raw:
        return ""
    separator = "_" if "_" in raw else "-"
    parts = raw.split(separator)
    if len(parts) < 2 or len(parts) > 4:
        return ""
    if any(not re.fullmatch(r"\d{2}|(?:19|20)\d{2}", part) for part in parts):
        return ""
    all_parts_are_four_digit_years = all(re.fullmatch(YEAR4_FULL_RE_TEXT, part) for part in parts)

    first = parts[0]
    if len(first) == 4:
        years = [int(first)]
    else:
        first_year = _normalize_year_token(first)
        if not first_year or not first_year.isdigit():
            return ""
        years = [int(first_year)]

    for part in parts[1:]:
        expanded = _expand_two_digit_year_near_base(part, years[-1])
        if not expanded or not expanded.isdigit():
            return ""
        year = int(expanded)
        if year <= years[-1]:
            return ""
        years.append(year)

    if not all_parts_are_four_digit_years and years[-1] - years[0] > MAX_YEAR_RANGE_SPAN:
        return ""

    return f"{years[0]:04d}-{years[-1]:04d}"


def _normalize_compact_year_plus_two_range(year_text: str, tail_text: str) -> str:
    """Return yyyy-yyyy for compact yyyyYY only when YY plausibly advances the year."""
    year_norm = _normalize_year_token(year_text)
    tail = str(tail_text or "").strip()
    if not (year_norm and year_norm.isdigit() and re.fullmatch(r"\d{2}", tail)):
        return ""
    expanded = _expand_two_digit_year_near_base(tail, int(year_norm))
    if not expanded:
        return ""
    return _normalize_year_range(year_norm, expanded)


def _normalize_four_plus_four_range_candidate(year_text: str, tail_text: str, separator: str) -> str:
    """Return a range for the dash form yyyy-yyyy, never for the space form."""
    if separator != "-":
        return ""
    if not re.fullmatch(YEAR4_FULL_RE_TEXT, str(tail_text or "")):
        return ""
    return _normalize_year_range(_normalize_year_token(year_text), str(tail_text or ""), enforce_max_span=False)


def _normalize_four_plus_four_date_candidate(year_text: str, tail_text: str, separator: str) -> str:
    """Normalize yyyy MMDD / yyyy DDMM and non-range yyyy-MMDD / yyyy-DDMM.

    The dash form is first checked as a possible yyyy-yyyy range by
    _normalize_four_plus_four_range_candidate.  Only non-range dash forms are
    allowed to become compact dates.  The space form must resolve to an actual
    valid date in either US MMDD or European DDMM order; ambiguous valid values
    continue to prefer the US MMDD interpretation to match the existing
    END_FIRST_RE behavior.
    """
    tail = str(tail_text or "").strip().lower()
    if not re.fullmatch(r"\d{4}", tail):
        return ""
    if separator == "-" and _normalize_four_plus_four_range_candidate(year_text, tail, separator):
        return ""

    # Prefer US-style MMDD, then accept European-style DDMM when MMDD is not
    # a valid date.  This makes 2001 0414 and 2001 1404 both resolve to
    # 2001-04-14 while still rejecting impossible values.
    mdy = _normalize_date(year_text, tail[:2], tail[2:])
    if mdy:
        return mdy
    dmy = _normalize_date(year_text, tail[2:], tail[:2])
    if dmy:
        return dmy
    return ""

def _month_name_to_number(name: str) -> str:
    month = MONTHS.get((name or "").strip().lower())
    return f"{month:02d}" if month else ""



def _strip_ordinal(day_value: str) -> str:
    text = (day_value or "").strip()
    match = ORDINAL_RE.fullmatch(text)
    return match.group(1) if match else text



AUDIO_RATE_DEPTH_RE = re.compile(
    r"(?i)(?<!\d)(?:"
    r"(?:44(?:\.1)?|48|88(?:\.2)?|96|176(?:\.4)?|192)\s*[-/]\s*(?:16|24|32)"
    r"|(?:16|24|32)\s*[-/]\s*(?:44(?:\.1)?|48|88(?:\.2)?|96|176(?:\.4)?|192)"
    r")(?![0-9xX])"
)


def _is_audio_rate_depth_reference(raw: str) -> bool:
    return bool(AUDIO_RATE_DEPTH_RE.search(str(raw or "")))


def _separator_kind(separator: str) -> str:
    cleaned = re.sub(r",+", "", str(separator or "")).strip()
    if not cleaned:
        return "space"
    if "-" in cleaned:
        return "-"
    if "/" in cleaned:
        return "/"
    if "." in cleaned:
        return "."
    if "_" in cleaned:
        return "_"
    if cleaned.isspace() or re.fullmatch(r"\s+", cleaned):
        return "space"
    return cleaned


def _is_year_space_month_punct_day_exception(raw: str) -> bool:
    """Allow one narrow repair case for malformed year-first dates.

    Folder names occasionally contain a complete date with a dash between the
    year and month and a space before the day, e.g. ``2014-04 18``.  Treat that
    as a repairable yyyy-mm-dd typo while continuing to reject broad mixed
    separator triples such as 2010-08/01 or 10/08-83.
    """
    text = str(raw or "").strip()
    return bool(re.fullmatch(rf"{YEAR4_TOKEN_RE_TEXT}\s*-\s*[0-9xX]{{1,2}}\s+[0-9xX]{{1,2}}", text, re.IGNORECASE))


def _date_raw_has_mixed_component_separators(raw: str, allow_year_space_month_day_exception: bool = False) -> bool:
    """Reject date-like triples that mix component separators.

    Examples rejected: 2010-08/01, 2010.08/01, 10/08-83, 44.1/16.
    Numeric-only separated dates may use dash, dot, underscore, or space,
    with optional spaces around punctuation, but all component separators must
    have the same effective kind.  Slash dates are handled only for tags and
    selected setlist contents.
    """
    text = str(raw or "").strip()
    if allow_year_space_month_day_exception and _is_year_space_month_punct_day_exception(text):
        return False
    tokens = re.findall(r"[A-Za-z]+|[0-9xX]+(?:st|nd|rd|th|ST|ND|RD|TH)?|[^A-Za-z0-9xX]+", text)
    separators = []
    for index in range(1, len(tokens) - 1):
        prev_token = tokens[index - 1]
        token = tokens[index]
        next_token = tokens[index + 1]
        if re.search(r"[A-Za-z0-9xX]", prev_token) and re.search(r"[A-Za-z0-9xX]", next_token) and not re.search(r"[A-Za-z0-9xX]", token):
            # Ignore punctuation that only terminates a component, e.g. the comma in June 15, 2006.
            without_commas = re.sub(r",+", "", token)
            if without_commas.strip() or re.search(r"\s", without_commas):
                separators.append(_separator_kind(token))
    if len(separators) < 2:
        return False
    return len(set(separators)) > 1

def _append_date_result(results: List[Dict[str, str]], seen: set, raw: str, normalized: str, start: int, end: int, allow_year_space_month_day_exception: bool = False, **extra: str) -> None:
    if not normalized:
        return
    if _is_audio_rate_depth_reference(raw) or _date_raw_has_mixed_component_separators(raw, allow_year_space_month_day_exception=allow_year_space_month_day_exception):
        return
    key = (start, end, normalized, extra.get("date_order", ""), extra.get("date_source_kind", ""))
    if key in seen:
        return
    seen.add(key)
    item = {
        "raw": raw,
        "normalized": normalized,
        "start": start,
        "end": end,
    }
    item.update({key: value for key, value in extra.items() if value})
    results.append(item)



def _find_date_matches(text: str, allow_slash: bool = False, allow_year_space_month_day_exception: bool = False) -> List[Dict[str, str]]:
    if not text:
        return []
    results: List[Dict[str, str]] = []
    seen = set()

    for match in YEAR_FIRST_RE.finditer(text):
        normalized = _normalize_date(match.group("year"), match.group("month"), match.group("day"))
        extra = {"date_order": "ymd"}
        if normalized and _is_year_space_month_punct_day_exception(match.group(0)):
            extra["date_separator_repaired"] = "1"
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end(), allow_year_space_month_day_exception=allow_year_space_month_day_exception, **extra)


    for match in DASHED_YEAR_RANGE_RE.finditer(text):
        normalized = _normalize_dashed_year_range(match.group("range"))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())

    for match in COMPACT_YMD_RE.finditer(text):
        normalized = _normalize_date(match.group("year"), match.group("month"), match.group("day"))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())

    for match in COMPACT_YEAR_MONTH_OR_RANGE_RE.finditer(text):
        raw = match.group(0)
        normalized_date = _normalize_date(match.group("year"), match.group("tail"), "xx")
        _append_date_result(results, seen, raw, normalized_date, match.start(), match.end())
        normalized_range = _normalize_compact_year_plus_two_range(match.group("year"), match.group("tail"))
        _append_date_result(results, seen, raw, normalized_range, match.start(), match.end())

    for match in END_FIRST_RE.finditer(text):
        year = match.group("year")
        first = match.group("a")
        second = match.group("b")
        mdy = _normalize_date(year, first, second)
        dmy = _normalize_date(year, second, first)
        if mdy:
            _append_date_result(results, seen, match.group(0), mdy, match.start(), match.end(), date_order="mdy")
        elif dmy:
            _append_date_result(
                results,
                seen,
                match.group(0),
                dmy,
                match.start(),
                match.end(),
                date_order="dmy",
                needs_setlist_confirmation="1",
            )

    if allow_slash:
        for match in SLASH_END_FIRST_RE.finditer(text):
            year = match.group("year")
            first = match.group("a")
            second = match.group("b")
            mdy = _normalize_date(year, first, second)
            dmy = _normalize_date(year, second, first)
            if mdy:
                _append_date_result(results, seen, match.group(0), mdy, match.start(), match.end(), date_order="slash_mdy")
            elif dmy:
                _append_date_result(results, seen, match.group(0), dmy, match.start(), match.end(), date_order="slash_dmy")

    for match in MONTH_DAY_YEAR_RE.finditer(text):
        # A compact month-year value such as November2020 or November 2020 is
        # partial, not November 20, 2020. Let MONTH_YEAR_RE handle it later.
        if re.fullmatch(rf"(?:{MONTH_NAME_CASED_PATTERN})\.?(?:{TEXT_DATE_SEP_OPT})(?:{YEAR4_TOKEN_RE_TEXT})", match.group(0)):
            continue
        normalized = _normalize_date(match.group("year"), _month_name_to_number(match.group("month_name")), _strip_ordinal(match.group("day")))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())

    for match in DAY_MONTH_YEAR_RE.finditer(text):
        normalized = _normalize_date(match.group("year"), _month_name_to_number(match.group("month_name")), _strip_ordinal(match.group("day")))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())

    occupied_spans = [(item["start"], item["end"]) for item in results]

    for match in YEAR_MONTHNAME_DAY_RE.finditer(text):
        normalized = _normalize_date(match.group("year"), _month_name_to_number(match.group("month_name")), _strip_ordinal(match.group("day")))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())
        if normalized:
            occupied_spans.append((match.start(), match.end()))

    for match in MONTH_YEAR_RE.finditer(text):
        # Month-year forms such as November2020 or November 2020 are less
        # specific than complete dates. Do not add a month-year match when its
        # span overlaps a fuller date already extracted from the same text.
        if any(not (match.end() <= start or match.start() >= end) for start, end in occupied_spans):
            continue
        normalized = _normalize_date(match.group("year"), _month_name_to_number(match.group("month_name")), "xx")
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end())

    for match in FOUR_PLUS_FOUR_RE.finditer(text):
        separator = match.group("four_sep")
        monthday = match.group("monthday")
        normalized_range = _normalize_four_plus_four_range_candidate(match.group("year"), monthday, separator)
        _append_date_result(results, seen, match.group(0), normalized_range, match.start(), match.end())
        normalized_date = _normalize_four_plus_four_date_candidate(match.group("year"), monthday, separator)
        _append_date_result(results, seen, match.group(0), normalized_date, match.start(), match.end())

    results.sort(key=lambda item: (item["start"], item["end"], item["normalized"]))
    return results



def _is_abbreviation_candidate(source_text: str, date_start: int, string1: str) -> bool:
    if date_start <= 0:
        return False
    cleaned = compact_ws(string1)
    if not cleaned or len(cleaned) > 4:
        return False
    if not re.fullmatch(r"[A-Za-z]{1,4}", cleaned):
        return False
    if not (cleaned.lower() == cleaned or cleaned.upper() == cleaned):
        return False
    prefix = source_text[:date_start]
    return bool(prefix and prefix[-1].isalpha())



def _string_date_matches(text: str, allow_string2: bool, allow_year_space_month_day_exception: bool = False) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    for date_match in _find_date_matches(text, allow_year_space_month_day_exception=allow_year_space_month_day_exception):
        left_raw = text[: date_match["start"]]
        right_raw = text[date_match["end"] :]
        string1 = _clean_piece(left_raw)
        string2 = _clean_piece(right_raw)
        if not string1:
            continue
        if not allow_string2 and not string2:
            continue
        item = {
            "string1": string1,
            "string1_stripped": _strip_string1_articles(string1),
            "date_raw": date_match["raw"],
            "date_norm": date_match["normalized"],
            "string2": string2,
            "abbr_candidate": _is_abbreviation_candidate(text, date_match["start"], string1),
        }
        for key in ("date_order", "needs_setlist_confirmation", "date_separator_repaired"):
            if date_match.get(key):
                item[key] = date_match[key]
        matches.append(item)
    return matches


def _find_compliant_primary_date_matches(text: str) -> List[Dict[str, str]]:
    """Return compliant-first date hits: yyyy-mm-dd or a dash/underscore year range.

    Compliant folder names are expected to put the performance date between
    String1 and String2 (or after String1) as yyyy-mm-dd or as a range.  These
    matches are tried before the broader date parser so nearby collection
    ranges, compact dates, month-name dates, or end-first dates do not win when
    the compliant form is present.
    """
    if not text:
        return []
    results: List[Dict[str, str]] = []
    seen = set()
    for match in COMPLIANT_PRIMARY_YMD_RE.finditer(text):
        normalized = _normalize_date(match.group("year"), match.group("month"), match.group("day"))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end(), date_order="ymd", date_source_kind="compliant_primary")
    for match in DASHED_YEAR_RANGE_RE.finditer(text):
        normalized = _normalize_dashed_year_range(match.group("range"))
        _append_date_result(results, seen, match.group(0), normalized, match.start(), match.end(), date_source_kind="compliant_primary_range")
    results.sort(key=lambda item: (item["start"], item["end"], item["normalized"]))
    return results


def _date_matches_to_string_date_matches(text: str, date_matches_in: Sequence[Dict[str, str]], allow_string2: bool) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    for date_match in date_matches_in:
        left_raw = text[: date_match["start"]]
        right_raw = text[date_match["end"] :]
        string1 = _clean_piece(left_raw)
        string2 = _clean_piece(right_raw)
        if not string1:
            continue
        if not allow_string2 and not string2:
            continue
        item = {
            "string1": string1,
            "string1_stripped": _strip_string1_articles(string1),
            "date_raw": date_match["raw"],
            "date_norm": date_match["normalized"],
            "string2": string2,
            "abbr_candidate": _is_abbreviation_candidate(text, int(date_match["start"]), string1),
        }
        for key in ("date_order", "needs_setlist_confirmation", "date_separator_repaired"):
            if date_match.get(key):
                item[key] = date_match[key]
        matches.append(item)
    return matches


def _compliant_string_date_matches(text: str, allow_string2: bool) -> List[Dict[str, str]]:
    """Return compliant String1 Date [String2] matches, strict form first.

    The primary compliant date forms are yyyy-mm-dd and accepted year ranges.
    If none are present, retain the broader historical parser as a fallback for
    older inventories and malformed legacy folders.
    """
    primary_dates = _find_compliant_primary_date_matches(text)
    ymd_primary = [item for item in primary_dates if item.get("date_source_kind") == "compliant_primary"]
    ymd_matches = _date_matches_to_string_date_matches(text, ymd_primary, allow_string2)
    if ymd_matches:
        return ymd_matches
    range_primary = [item for item in primary_dates if item.get("date_source_kind") == "compliant_primary_range"]
    range_matches = _date_matches_to_string_date_matches(text, range_primary, allow_string2)
    if range_matches:
        return range_matches
    return _string_date_matches(text, allow_string2=allow_string2, allow_year_space_month_day_exception=True)



def _choose_lookup_text(match: Dict[str, str]) -> str:
    stripped = compact_ws(match.get("string1_stripped", ""))
    original = compact_ws(match.get("string1", ""))
    if match.get("abbr_candidate"):
        return original or stripped
    return stripped or original


def _match_date_string3(text: str) -> Optional[Dict[str, str]]:
    cleaned = _clean_piece(text)
    if not cleaned:
        return None
    for date_match in _find_date_matches(cleaned):
        if _clean_piece(cleaned[: date_match["start"]]):
            continue
        string3 = _clean_piece(cleaned[date_match["end"] :])
        if not string3:
            continue
        item = {
            "date_raw": date_match["raw"],
            "date_norm": date_match["normalized"],
            "string3": string3,
        }
        for key in ("date_order", "needs_setlist_confirmation", "date_separator_repaired"):
            if date_match.get(key):
                item[key] = date_match[key]
        return item
    return None


_STRING_DASH_STRING_RE = re.compile(r"^(?P<string1>.+?)\s+-\s+(?P<string2>.+)$")


def _match_string_dash_string(text: str) -> Optional[Dict[str, str]]:
    cleaned = _clean_piece(text)
    if not cleaned:
        return None
    match = _STRING_DASH_STRING_RE.match(cleaned)
    if not match:
        return None
    string1 = _clean_piece(match.group("string1"))
    string2 = _clean_piece(match.group("string2"))
    if not string1 or not string2:
        return None
    return {
        "string1": string1,
        "string1_stripped": _strip_string1_articles(string1),
        "string2": string2,
    }




def _date_match_consumes_entire_text(text: str) -> Optional[Dict[str, str]]:
    """Return a normalized date match when the whole value is date-like.

    This is used to distinguish true album-style ``String1 - String2``
    folders from folders such as ``Artist - 2010-08-01``.  The date match
    must consume the complete cleaned String2 value apart from punctuation and
    whitespace so ordinary album titles that merely contain a date are not
    reclassified.
    """
    cleaned = _clean_piece(text)
    if not cleaned:
        return None
    for match in _find_date_matches(cleaned):
        before = _clean_piece(cleaned[: match["start"]])
        after = _clean_piece(cleaned[match["end"] :])
        if before or after:
            continue
        return match
    return None


def _string_dash_string_tail_date(row: Optional[Dict[str, str]]) -> str:
    if not row:
        return ""
    match = _date_match_consumes_entire_text(row.get("string2", ""))
    return match.get("normalized", "") if match else ""

def _resolve_artist_from_date_string3(group: dict, matcher: Optional[ArtistMatcher], evidence: Dict[str, List[Candidate]], conflicts: List[str]) -> Tuple[str, str]:
    for part, part_path in _candidate_path_parts(group["main_dir_path"]):
        row = _match_date_string3(part)
        if not row:
            continue
        term = _strip_string1_articles(row["string3"]) or row["string3"]
        detail = _lookup_artist_detail(term, matcher)
        if detail["status"] == "collision":
            conflicts.append(_collision_note(f"artist query collision for Date String3: {term}", detail["masters"]))
            return "", ""
        if detail["status"] == "matched" and detail["masters"]:
            master = detail["masters"][0]
            evidence.setdefault("artist", []).append(Candidate(master, f"date_string3:{part_path}", 58))
            evidence.setdefault("date", []).append(Candidate(row["date_norm"], f"date_string3:{part_path}", 58))
            return master, row["date_norm"]
    return "", ""


def _find_string_dash_string_match(group: dict) -> Optional[Dict[str, str]]:
    for part, part_path in _candidate_path_parts(group["main_dir_path"]):
        row = _match_string_dash_string(part)
        if not row:
            continue
        row["part"] = part
        row["part_path"] = part_path
        return row
    return None


def _resolve_from_string_dash_string(
    group: dict,
    matcher: Optional[ArtistMatcher],
    evidence: Dict[str, List[Candidate]],
    conflicts: List[str],
    compliant: bool = False,
    assume_unmatched_artist: bool = False,
) -> Tuple[str, Optional[Dict[str, str]]]:
    for part, part_path in _candidate_path_parts(group["main_dir_path"]):
        row = _match_string_dash_string(part)
        if not row:
            continue
        term = row["string1"] if len(re.sub(r"[^A-Za-z]", "", row["string1"])) <= 4 and row["string1"].isupper() else (row["string1_stripped"] or row["string1"])
        detail = _lookup_artist_detail(term, matcher)
        if detail["status"] == "collision":
            conflicts.append(_collision_note(f"artist query collision for String1 - String2: {term}", detail["masters"]))
            return "", None
        if detail["status"] == "matched" and detail["masters"]:
            master = detail["masters"][0]
            evidence.setdefault("artist", []).append(Candidate(master, f"string_dash_string:{part_path}", 56 if not compliant else 66))
            row["part"] = part
            row["part_path"] = part_path
            return master, row
        if compliant or assume_unmatched_artist:
            artist_name = row["string1_stripped"] or row["string1"]
            source_prefix = "compliant:string_dash_string" if compliant else "string_dash_string_unmatched"
            confidence = 64 if compliant else 55
            evidence.setdefault("artist", []).append(Candidate(artist_name, f"{source_prefix}:{part_path}", confidence))
            row["part"] = part
            row["part_path"] = part_path
            return artist_name, row
    return "", None





def _resolve_noncompliant_from_string_dash_string(
    group: dict,
    matcher: Optional[ArtistMatcher],
    evidence: Dict[str, List[Candidate]],
    conflicts: List[str],
    observations: List[str],
) -> Tuple[str, Optional[Dict[str, str]]]:
    """Resolve the non-compliant String1 - String2 fallback.

    String1 is checked against the Artist DB first. If String1 does not
    resolve, scan the remaining path subdirectories for a valid DB-backed
    artist before using raw String1 as the artist. String2 remains the album
    name either way.
    """
    for part, part_path in _candidate_path_parts(group["main_dir_path"]):
        row = _match_string_dash_string(part)
        if not row:
            continue
        term = row["string1"] if len(re.sub(r"[^A-Za-z]", "", row["string1"])) <= 4 and row["string1"].isupper() else (row["string1_stripped"] or row["string1"])
        detail = _lookup_artist_detail(term, matcher)
        row["part"] = part
        row["part_path"] = part_path
        if detail["status"] == "collision":
            conflicts.append(_collision_note(f"artist query collision for String1 - String2: {term}", detail["masters"]))
            return "", None
        if detail["status"] == "matched" and detail["masters"]:
            master = detail["masters"][0]
            evidence.setdefault("artist", []).append(Candidate(master, f"string_dash_string:{part_path}", 56))
            return master, row

        path_artist = _resolve_artist_from_subdirs(
            group,
            matcher,
            evidence,
            conflicts,
            pattern_artist="",
            exclude_part_paths={part_path},
            source_label="string_dash_string_path_artist",
        )
        if path_artist:
            observations.append(f"String1 - String2 artist not found in DB; using artist found elsewhere in path: {path_artist}")
            return path_artist, row

        artist_name = row["string1_stripped"] or row["string1"]
        evidence.setdefault("artist", []).append(Candidate(artist_name, f"string_dash_string_unmatched:{part_path}", 55))
        observations.append(f"String1 - String2 artist not found in DB or elsewhere in path; using String1 as artist: {artist_name}")
        return artist_name, row
    return "", None


def _lookup_artist_detail(term: str, matcher: Optional[ArtistMatcher]) -> Dict[str, object]:
    status, masters = lookup_artist_master_with_status(term, matcher)
    aliases: Dict[str, List[str]] = {}
    if matcher is not None:
        for master in masters:
            aliases[master] = list(matcher.master_aliases.get(master, [master]))
    return {
        "term": term,
        "status": status,
        "masters": list(masters),
        "aliases": aliases,
    }


def _compliant_artist_mode(config) -> str:
    value = str(getattr(config, "compliant_artist_mode", "master") or "master").strip().lower().replace("_", "-")
    if value in {"as-is", "asis", "as is", "raw"}:
        return "as-is"
    return "master"


def _set_compliant_artist_from_string1(
    config,
    candidate_artist: str,
    lookup_term: str,
    artist_matcher: Optional[ArtistMatcher],
    evidence: Dict[str, List[Candidate]],
    observations: List[str],
    source_label: str,
    confidence: int,
    context_label: str,
) -> str:
    candidate = compact_ws(candidate_artist)
    if not candidate:
        return ""
    if _compliant_artist_mode(config) == "as-is":
        observations.append(f"compliant artist mode As-Is: using String1 without artist DB lookup: {candidate}")
        evidence.setdefault("artist", []).append(Candidate(candidate, f"{source_label}_as_is:{candidate}", confidence))
        return candidate

    term = compact_ws(lookup_term) or _strip_string1_articles(candidate) or candidate
    detail = _lookup_artist_detail(term, artist_matcher)
    if detail["status"] == "matched" and detail["masters"]:
        master = detail["masters"][0]
        evidence.setdefault("artist", []).append(Candidate(master, f"{source_label}:{term}", confidence))
        return master
    if detail["status"] == "collision":
        observations.append(_collision_note(f"compliant artist query collision for {context_label}; using raw String1: {term}", detail["masters"]))
        evidence.setdefault("artist", []).append(Candidate(candidate, f"{source_label}_collision_raw:{candidate}", max(1, confidence - 5)))
        return candidate

    observations.append(f"compliant artist not found in DB; using candidate artist: {candidate}")
    evidence.setdefault("artist", []).append(Candidate(candidate, f"{source_label}_unmatched:{candidate}", max(1, confidence - 5)))
    return candidate


def _resolve_compliant_dash_from_group_as_is(
    group: dict,
    evidence: Dict[str, List[Candidate]],
    observations: List[str],
) -> Tuple[str, Optional[Dict[str, str]]]:
    for part, part_path in _candidate_path_parts(group["main_dir_path"]):
        row = _match_string_dash_string(part)
        if not row:
            continue
        row["part"] = part
        row["part_path"] = part_path
        artist_name = compact_ws(row.get("string1", ""))
        if artist_name:
            observations.append(f"compliant artist mode As-Is: using String1 without artist DB lookup: {artist_name}")
            evidence.setdefault("artist", []).append(Candidate(artist_name, f"compliant:string_dash_string_as_is:{part_path}", 64))
            return artist_name, row
    return "", None



def _unique_preserve(values: Sequence[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        cleaned = compact_ws(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered



def _collision_note(prefix: str, masters: Sequence[str]) -> str:
    ordered = _unique_preserve(list(masters))
    if ordered:
        return f"{prefix}: {' | '.join(ordered)}"
    return prefix


def _state_term_to_code(term: str) -> str:
    value = compact_ws(term).strip(" .,")
    if not value:
        return ""
    upper = value.upper()
    if upper in US_STATE_CODES:
        return upper
    return (US_STATE_ALIASES.get(value.casefold()) or "").upper()


def _state_search_terms(include_codes: bool = True) -> List[str]:
    terms: List[str] = []
    if include_codes:
        terms.extend(US_STATE_CODES)
    for alias, code in US_STATE_ALIASES.items():
        # For path String2 parsing, include full state names and legacy/long
        # abbreviations, but do not duplicate the two-letter codes here.  Codes
        # are handled explicitly so LA remains Louisiana and is not mixed with
        # any city shorthand logic.
        if len(alias) > 2 or " " in alias:
            terms.append(alias)
    return sorted(set(terms), key=lambda item: (-len(item), item.casefold()))


def _state_terms_regex(include_codes: bool = True) -> str:
    return "|".join(r"\s+".join(re.escape(part) for part in term.split()) for term in _state_search_terms(include_codes))


def _state_anchor_at_end(value: str) -> Tuple[str, str]:
    terms = _state_terms_regex(include_codes=True)
    if not terms:
        return "", ""
    pattern = re.compile(rf"(?:^|[\s,])({terms})$", re.IGNORECASE)
    match = pattern.search(value)
    if not match:
        return "", ""
    code = _state_term_to_code(match.group(1))
    if not code:
        return "", ""
    return code, value[: match.start(1)].rstrip(" ,")


def _ends_with_full_state_name(value: str) -> bool:
    terms = _state_terms_regex(include_codes=False)
    if not terms:
        return False
    return bool(re.search(rf"(?:^|[\s,])(?:{terms})$", compact_ws(value).strip(" ,"), re.IGNORECASE))


def _extract_anchor_at_end(text: str) -> Tuple[str, str]:
    value = compact_ws(text).rstrip(" ,")
    upper = value.upper()
    if upper.endswith(" NYC") or upper == "NYC":
        return "NYC", value[:-3].rstrip(" ,") if len(value) > 3 else ""
    if upper.endswith(" NOLA") or upper == "NOLA":
        return "NOLA", value[:-4].rstrip(" ,") if len(value) > 4 else ""

    for country in COUNTRY_SEARCH_TERMS:
        pattern = re.compile(rf"(?:^|[\s,])({re.escape(country)})$", re.IGNORECASE)
        match = pattern.search(value)
        if match:
            return COUNTRY_ALIASES.get(match.group(1).casefold(), country), value[: match.start(1)].rstrip(" ,")

    state_anchor, state_left = _state_anchor_at_end(value)
    if state_anchor:
        return state_anchor, state_left

    return "", ""



def _adjust_city_prefix(venue_tokens: List[str], city_tokens: List[str]) -> Tuple[List[str], List[str]]:
    changed = True
    while changed and venue_tokens:
        changed = False
        for prefix in MULTIPART_CITY_PREFIXES:
            prefix_tokens = prefix.split()
            if len(venue_tokens) >= len(prefix_tokens):
                suffix = venue_tokens[-len(prefix_tokens):]
                if [token.casefold() for token in suffix] == [token.casefold() for token in prefix_tokens]:
                    city_tokens = suffix + city_tokens
                    venue_tokens = venue_tokens[:-len(prefix_tokens)]
                    changed = True
                    break
    return venue_tokens, city_tokens



def _split_left_for_city_and_venue(left_text: str, *, allow_city_only: bool = False) -> Tuple[str, str]:
    left = compact_ws(left_text).strip(" ,")
    if not left:
        return "", ""
    tokens = [token.strip(",") for token in left.split() if token.strip(",")]
    if not tokens:
        return "", ""

    if allow_city_only:
        # Full state-name path fragments frequently appear as city/state/source
        # with no venue, e.g. "Boca Raton Florida - Schoeps".  When the text to
        # the left of the state is short and not venue-marked, keep it as a
        # location-only city rather than splitting it into a fake venue and a
        # one-word city.  Longer fragments continue through the normal
        # venue-last-word-city heuristic below.
        lower_tokens = [token.casefold() for token in tokens]
        if len(tokens) <= 2 and lower_tokens[0] not in {"the"}:
            return "", compact_ws(" ".join(tokens)).strip(" ,")

    city_tokens = [tokens[-1]]
    venue_tokens = tokens[:-1]
    venue_tokens, city_tokens = _adjust_city_prefix(venue_tokens, city_tokens)
    venue = compact_ws(" ".join(token for token in venue_tokens if token)).strip(" ,")
    city = compact_ws(" ".join(token for token in city_tokens if token)).strip(" ,")
    return venue, city



def _parse_country_qualified_region(value: str, anchor: str, left: str) -> Tuple[str, str, str, str, str]:
    """Parse String2 values with city + region/state + trailing country.

    Examples:
      - Marina Del Rey, California USA -> city=Marina Del Rey, region=CA
      - Austin Texas U.S.A. -> city=Austin, region=TX
      - Toronto, ON Canada -> city=Toronto, region=ON, country=Canada

    Known region names/codes come from the local state/region alias tables used
    by this parser.  Country-only values continue through the normal fallback.
    """
    if not anchor or not left:
        return "", "", "", "", ""
    state_anchor, state_left = _state_anchor_at_end(left)
    if state_anchor:
        state_text = left[len(state_left):].strip(" ,") if state_left else left
        is_full_state_name = len(compact_ws(state_text)) > 2
        if is_full_state_name and state_left:
            # A comma immediately before a full state name is strong evidence
            # that the entire left side is a city, not venue + one-word city.
            if re.search(rf"{re.escape(state_left)}\s*,\s*{re.escape(state_text)}$", left, re.I):
                venue, city = "", compact_ws(state_left).strip(" ,")
            else:
                venue, city = _split_left_for_city_and_venue(state_left, allow_city_only=True)
        else:
            venue, city = _split_left_for_city_and_venue(state_left, allow_city_only=False)
        if city:
            return venue, city, state_anchor, "" if anchor == "USA" else anchor, ""
    # Non-US country values with an explicitly comma-separated region/province
    # can be represented even when the region is not in the built-in US table.
    # Keep this conservative: require exactly a city and a short/few-word
    # region-like segment after a comma.
    if anchor != "USA" and "," in left:
        parts = [compact_ws(part) for part in left.split(",") if compact_ws(part)]
        if len(parts) == 2 and parts[1].casefold() in COMMON_NON_US_REGION_TERMS:
            return "", parts[0], parts[1], anchor, ""
    return "", "", "", "", ""


def _parse_string2(string2: str) -> Tuple[str, str, str, str, str]:
    value = compact_ws(string2).strip(" ,")
    if not value:
        return "", "", "", "", ""
    anchor, left = _extract_anchor_at_end(value)
    if anchor:
        if anchor == "NYC":
            return compact_ws(left), "New York", "NY", "", ""
        if anchor == "NOLA":
            return compact_ws(left), "New Orleans", "LA", "", ""
        if anchor in COUNTRY_ALIASES.values() and anchor not in US_STATE_CODES:
            venue, city, region, country, extra = _parse_country_qualified_region(value, anchor, left)
            if city and (region or country):
                return venue, city, region, country, extra
        allow_city_only = bool(anchor in US_STATE_CODES and _ends_with_full_state_name(value))
        venue, city = _split_left_for_city_and_venue(left, allow_city_only=allow_city_only)
        if anchor in COUNTRY_ALIASES.values() and anchor not in US_STATE_CODES:
            return venue, city, "", "" if anchor == "USA" else anchor, ""
        return venue, city, anchor, "", ""

    state_terms = _state_terms_regex(include_codes=True)
    if state_terms:
        state_pattern = re.compile(rf"(?:^|[\s,])({state_terms})(?:[\s,-]+)(?P<tail>.+)$", re.IGNORECASE)
        match = state_pattern.search(value)
        if match:
            region = _state_term_to_code(match.group(1))
            if region:
                left_text = value[: match.start(1)].rstrip(" ,-")
                tail = compact_ws(match.group('tail')).strip(" -,")
                is_full_state_name = len(compact_ws(match.group(1))) > 2
                venue, city = _split_left_for_city_and_venue(left_text, allow_city_only=is_full_state_name)
                return venue, city, region, "", tail

    return "", "", "", "", ""



def _join_location(city: str, region: str, country: str) -> str:
    pieces = []
    if city:
        pieces.append(city)
    if region:
        pieces.append(region)
    elif country:
        pieces.append(country)
    return ", ".join(pieces)



def _detect_qualifier(values: Sequence[str]) -> str:
    for value in values:
        for pattern, label in QUALIFIER_PATTERNS:
            if pattern.search(value or ""):
                return label
    return ""



def _detect_24_bit(values: Sequence[str]) -> bool:
    for value in values:
        for pattern in BIT24_PATTERNS:
            if pattern.search(value or ""):
                return True
    return False



def _is_exact_yyyy_mm_dd_date(value: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}-\d{2}-\d{2}", value or ""))



def _set_compliant_string2_raw(record: ShowMetadata, string2: str, parentheticals: str, evidence: Dict[str, List[Candidate]], source: str) -> None:
    """Compliant mode: String2 is used as found; do not parse venue/location unless eTreeDB succeeds."""
    value = compact_ws(string2).strip()
    record.venue = value
    record.city = ""
    record.region = ""
    record.country = ""
    record.location = ""
    record.parentheticals = parentheticals
    record.album_name = value
    if value:
        evidence.setdefault("venue", []).append(Candidate(value, source, 70))


def _build_compliant_string2_show_name(record: ShowMetadata) -> str:
    if not record.artist or not record.date:
        return ""
    return compact_ws(" ".join(part for part in [record.artist, record.date, record.venue] if part))


def _build_compliant_dash_show_name(record: ShowMetadata) -> str:
    if not record.artist or not record.venue:
        return ""
    return compact_ws(f"{record.artist} - {record.venue}")


def _build_dash_album_show_name(record: ShowMetadata) -> str:
    album_name = compact_ws(record.album_name or record.venue)
    if not record.artist or not album_name:
        return ""
    return _append_parentheticals_to_show_name(compact_ws(f"{record.artist} - {album_name}"), record.parentheticals)


def _apply_string_dash_album_to_record(record: ShowMetadata, dash_match: Optional[Dict[str, str]], evidence: Dict[str, List[Candidate]], source: str) -> None:
    if not dash_match:
        return
    stripped_string2, parentheticals = _strip_trailing_parenthetical_items_with_cache(dash_match.get("string2", ""))
    album_name = compact_ws(stripped_string2)
    if not album_name:
        return
    record.album_name = album_name
    # String1 - String2 in non-compliant mode treats String2 as an album name,
    # not parsed venue/location metadata. Keep venue/location blank so generated
    # placeholder setlists do not mislabel an album as a venue.
    record.venue = ""
    record.city = ""
    record.region = ""
    record.country = ""
    record.location = ""
    if parentheticals:
        record.parentheticals = compact_ws(f"{record.parentheticals} {parentheticals}").strip()
    evidence.setdefault("album", []).append(Candidate(album_name, source, 70))


def _build_compliant_string_date_show_name(record: ShowMetadata) -> str:
    if not record.artist or not record.date:
        return ""
    return compact_ws(f"{record.artist} {record.date}")


def _etree_lookup_is_usable(record: ShowMetadata) -> bool:
    return bool(record.venue and record.city and (record.region or record.country or record.location))


def _evidence_has_explicit_setlist_value(evidence: Dict[str, List[Candidate]], field: str) -> bool:
    """Return True when a field came from explicit labels inside the selected setlist.

    Explicit setlist labels such as Venue:, City:, Country:, and Location: are
    local source metadata and must not be silently overwritten by online lookup
    results. Online lookups may still fill missing fields and may be logged as
    a disagreement when they return different data.
    """
    for candidate in evidence.get(field, []):
        source = (candidate.source or "").upper()
        if source.startswith("SETLIST_METADATA:") and "EXPLICIT" in source:
            return True
    return False


def _normalize_etree_location_parts(result) -> Tuple[str, str, str, str]:
    """Normalize eTreeDB city/state into TLO city/region/country/location fields.

    eTreeDB exposes a generic state/location field. For non-US performances that
    field often contains a country name, so normalize known countries into
    record.country rather than record.region.
    """
    city = compact_ws(getattr(result, "city", "") or "")
    region = ""
    country = ""
    raw_state = compact_ws(getattr(result, "state", "") or "")
    if raw_state:
        state_code = ""
        if len(raw_state) == 2 and raw_state.upper() in US_STATE_CODES:
            state_code = raw_state.upper()
        else:
            state_code = (US_STATE_ALIASES.get(raw_state.casefold().strip()) or "").upper()
        if state_code:
            region = state_code
        else:
            country_value = COUNTRY_ALIASES.get(raw_state.casefold().strip())
            if country_value and country_value != "USA":
                country = country_value
            elif country_value == "USA":
                country = ""
            else:
                region = raw_state
    return city, region, country, _join_location(city, region, country)


def _normalized_contains(haystack_norm: str, needle: str) -> bool:
    needle_norm = normalized_compare_value(needle or "")
    if not haystack_norm or not needle_norm:
        return False
    return f" {needle_norm} " in f" {haystack_norm} "


def _record_setlist_text_for_etree_fit(record: ShowMetadata) -> str:
    paths = _unique_preserve([getattr(record, "setlist_file", "")] + list(getattr(record, "setlist_files", []) or []))
    parts: List[str] = []
    for path_name in paths:
        if not path_name or not os.path.isfile(path_name):
            continue
        text = _read_text_for_date_fallback(path_name)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _etree_result_setlist_fit_score(result, setlist_text_norm: str) -> int:
    if not setlist_text_norm:
        return 0
    score = 0
    venue = compact_ws(getattr(result, "venue", "") or "")
    city, region, country, location = _normalize_etree_location_parts(result)
    title = compact_ws(getattr(result, "title", "") or "")

    if venue and _normalized_contains(setlist_text_norm, venue):
        score += 60
    if location and _normalized_contains(setlist_text_norm, location):
        score += 50
    if city and _normalized_contains(setlist_text_norm, city):
        score += 30
    if region and _normalized_contains(setlist_text_norm, region):
        score += 15
    if country and _normalized_contains(setlist_text_norm, country):
        score += 15
    if title and _normalized_contains(setlist_text_norm, title):
        score += 10
    return score


def _choose_etree_result_for_record(results: Sequence[object], record: ShowMetadata, observations: List[str]):
    if not results:
        return None
    if len(results) == 1:
        return results[0]
    setlist_text = _record_setlist_text_for_etree_fit(record)
    setlist_norm = normalized_compare_value(setlist_text)
    if not setlist_norm:
        observations.append(f"etree lookup returned {len(results)} same-date matches; no setlist text available for best-fit selection; using first result")
        return results[0]

    scored = [(_etree_result_setlist_fit_score(result, setlist_norm), index, result) for index, result in enumerate(results)]
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, _best_index, best_result = scored[0]
    tied_best = [item for item in scored if item[0] == best_score]
    if best_score > 0 and len(tied_best) == 1:
        observations.append(
            f"etree lookup returned {len(results)} same-date matches; selected best setlist-text fit performance id {getattr(best_result, 'performance_id', '')}"
        )
        return best_result

    observations.append(f"etree lookup returned {len(results)} same-date matches; no unique setlist-text best fit; using first result")
    return results[0]


def _metadata_values_equivalent(left: str, right: str) -> bool:
    """Return True when two metadata values are equal or one is a token subset of the other.

    This deliberately treats values such as "Fillmore" and "Fillmore West" as
    equivalent for disagreement reporting.  The check is token-boundary aware so
    short values like "CA" do not match inside unrelated words such as
    "Canada".
    """
    left_norm = normalized_compare_value(left or "")
    right_norm = normalized_compare_value(right or "")
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    padded_left = f" {left_norm} "
    padded_right = f" {right_norm} "
    return padded_left in padded_right or padded_right in padded_left


def _observe_metadata_disagreement(observations: List[str], source: str, field: str, existing_value: str, candidate_value: str) -> None:
    existing_value = compact_ws(existing_value or "")
    candidate_value = compact_ws(candidate_value or "")
    if existing_value and candidate_value and not _metadata_values_equivalent(existing_value, candidate_value):
        observations.append(f"{source} did not override existing {field}: {candidate_value}")


def _observe_online_disagreement(observations: List[str], source: str, field: str, local_value: str, online_value: str) -> None:
    _observe_metadata_disagreement(observations, f"{source} lookup", field, local_value, online_value)


def _has_complete_local_venue_location(record: ShowMetadata) -> bool:
    return bool(record.venue and record.city and (record.region or record.country or record.location))


def _apply_online_fields_fill_blanks(
    record: ShowMetadata,
    evidence: Dict[str, List[Candidate]],
    observations: List[str],
    source_label: str,
    confidence: int,
    online_venue: str,
    online_city: str,
    online_region: str,
    online_country: str,
    online_location: str,
) -> bool:
    """Apply a lookup source only to blank metadata fields.

    Lookup sources may complete missing venue/location parts, but they must not
    replace any nonblank field already identified by an earlier source.  In
    non-compliant mode the order is path, eTreeDB, selected setlist metadata,
    then setlist.fm.  Differences are logged unless the values are equivalent
    or one is a token-boundary subset of the other.
    """
    applied = False

    if not record.venue and online_venue:
        record.venue = online_venue
        evidence.setdefault("venue", []).append(Candidate(record.venue, source_label, confidence))
        applied = True
    elif record.venue and online_venue:
        _observe_online_disagreement(observations, source_label, "venue", record.venue, online_venue)

    if not record.city and online_city:
        record.city = online_city
        evidence.setdefault("city", []).append(Candidate(record.city, source_label, confidence))
        applied = True
    elif record.city and online_city:
        _observe_online_disagreement(observations, source_label, "city", record.city, online_city)

    # Region/country are mutually exclusive in normal TLO display: US locations
    # use region; non-US locations use country.  Fill whichever is blank only
    # when the other local field is also blank.
    if online_region:
        if not record.region and not record.country:
            record.region = online_region
            evidence.setdefault("region", []).append(Candidate(record.region, source_label, confidence))
            applied = True
        elif record.region:
            _observe_online_disagreement(observations, source_label, "region", record.region, online_region)
    if online_country:
        if not record.country and not record.region:
            record.country = online_country
            evidence.setdefault("country", []).append(Candidate(record.country, source_label, confidence))
            applied = True
        elif record.country:
            _observe_online_disagreement(observations, source_label, "country", record.country, online_country)

    if not record.location and (record.city or record.region or record.country):
        record.location = online_location or _join_location(record.city, record.region, record.country)
        applied = True
    elif record.location and online_location:
        _observe_online_disagreement(observations, source_label, "location", record.location, online_location)

    return applied


def _apply_etree_lookup_to_record(config, record: ShowMetadata, evidence: Dict[str, List[Candidate]], observations: List[str]) -> bool:
    """Use eTreeDB as an online venue/location source when enabled.

    In non-compliant mode, eTreeDB runs after path parsing and before setlist
    metadata fallback. It may fill blank venue/location fields, but it must not
    replace any nonblank field.
    """
    if not getattr(config, "etree_lookup", False):
        return False
    if not record.artist or not record.date:
        return False
    if not _is_exact_yyyy_mm_dd_date(record.date):
        observations.append(f"etree lookup skipped: date is not yyyy-mm-dd: {record.date}")
        return False
    try:
        results = lookup_venue_and_location(record.artist, record.date, debug=bool(getattr(config, "debug", False)))
    except Exception as exc:
        observations.append(f"etree lookup failed: {exc}")
        return False
    if not results:
        observations.append(f"etree lookup found no match for {record.artist} on {record.date}")
        return False

    result = _choose_etree_result_for_record(results, record, observations)
    if result is None:
        observations.append(f"etree lookup found no usable match for {record.artist} on {record.date}")
        return False
    etree_venue = compact_ws(getattr(result, "venue", "") or "")
    etree_city, etree_region, etree_country, etree_location = _normalize_etree_location_parts(result)
    if not (etree_venue and etree_city and (etree_region or etree_country or etree_location)):
        observations.append(f"etree lookup returned incomplete venue/location for {record.artist} on {record.date}")
        return False

    applied = _apply_online_fields_fill_blanks(
        record, evidence, observations, "etreedb", 95, etree_venue, etree_city, etree_region, etree_country, etree_location
    )
    if not applied:
        observations.append("etree lookup returned usable data but existing metadata already populated the same fields")

    if not _etree_lookup_is_usable(record):
        observations.append(f"etree lookup returned incomplete venue/location for {record.artist} on {record.date}")
        return False
    observations.append(f"etree lookup matched performance id {getattr(result, 'performance_id', '')}")
    if record.parentheticals:
        observations.append("etree lookup retained trailing parentheticals for show name")
    return True


def _store_setlistfm_setlist_candidates(record: ShowMetadata, results: Sequence[object], observations: List[str]) -> None:
    """Attach setlist.fm track candidates returned by the existing lookup call.

    No setlist.fm API request is made here.  The results were already fetched for
    venue/location lookup, so cached setlist rows can be made available to the
    inventory-time tagger without changing lookup precedence or call volume.
    """
    candidates = []
    try:
        result_candidates = collect_setlistfm_setlists_by_performance(list(results or []))
    except Exception:
        result_candidates = []
    for result, setlists in result_candidates:
        clean_setlists = [str(text or "").strip() for text in (setlists or []) if str(text or "").strip()]
        if not clean_setlists:
            continue
        candidates.append({
            "url": compact_ws(getattr(result, "setlist_url", "") or ""),
            "venue": compact_ws(getattr(result, "venue", "") or ""),
            "city": compact_ws(getattr(result, "city", "") or ""),
            "state_code": compact_ws(getattr(result, "state_code", "") or ""),
            "country": compact_ws(getattr(result, "country", "") or ""),
            "setlists": clean_setlists,
        })
    if candidates:
        record.setlistfm_setlist_candidates = candidates
        observations.append(f"setlist.fm lookup returned cached setlist text in same API response for {len(candidates)} matching result(s)")


def _apply_setlistfm_lookup_to_record(config, record: ShowMetadata, evidence: Dict[str, List[Candidate]], observations: List[str]) -> bool:
    """Use setlist.fm as the last venue/location lookup source when requested.

    In non-compliant mode this runs after path parsing, eTreeDB, and selected
    setlist metadata have all had a chance to fill fields.  It may fill blank
    fields only and logs non-equivalent differences without overwriting.
    """
    if not getattr(config, "setlistfm_lookup", False):
        return False
    if not record.artist or not record.date:
        return False
    if not _is_exact_yyyy_mm_dd_date(record.date):
        observations.append(f"setlist.fm lookup skipped: date is not yyyy-mm-dd: {record.date}")
        return False
    try:
        results = lookup_setlistfm_venue_and_location(
            record.artist,
            record.date,
            debug=bool(getattr(config, "debug", False)),
            min_interval_seconds=float(getattr(config, "setlistfm_min_interval_seconds", 0.600) or 0.600),
            max_calls=int(getattr(config, "setlistfm_max_calls", 1400) or 1400),
            run_id=str(getattr(config, "setlistfm_run_id", "") or ""),
        )
    except Exception as exc:
        observations.append(f"setlist.fm lookup failed: {exc}")
        return False
    if not results:
        observations.append(f"setlist.fm lookup found no match for {record.artist} on {record.date}")
        return False
    _store_setlistfm_setlist_candidates(record, results, observations)
    result = results[0]
    lookup_venue = compact_ws(getattr(result, "venue", "") or "")
    lookup_city = compact_ws(getattr(result, "city", "") or "")
    lookup_region = ""
    lookup_country = ""
    if is_us_country(result.country, result.country_code):
        lookup_region = (result.state_code or US_STATE_ALIASES.get((result.state or "").casefold().strip(), "") or "").upper()
    else:
        lookup_country = result.country or result.country_code or ""
    lookup_location = _join_location(lookup_city, lookup_region, lookup_country)
    if not (lookup_venue and lookup_city and lookup_location):
        observations.append(f"setlist.fm lookup returned incomplete venue/location for {record.artist} on {record.date}")
        return False

    applied = _apply_online_fields_fill_blanks(
        record, evidence, observations, "setlist.fm", 90, lookup_venue, lookup_city, lookup_region, lookup_country, lookup_location
    )
    if not applied:
        observations.append("setlist.fm lookup returned usable data but existing metadata already populated the same fields")

    if not (record.venue and record.city and record.location):
        observations.append(f"setlist.fm lookup returned incomplete venue/location for {record.artist} on {record.date}")
        return False
    observations.append(f"setlist.fm lookup matched {result.setlist_url or 'setlist.fm result'}")
    if record.parentheticals:
        observations.append("setlist.fm lookup retained trailing parentheticals for show name")
    return True


def _apply_online_lookup_to_record(config, record: ShowMetadata, evidence: Dict[str, List[Candidate]], observations: List[str]) -> bool:
    """Compliant-mode online lookup chain: eTreeDB first, setlist.fm fallback.

    Non-compliant mode uses the same fallback rule around the setlist metadata
    step: setlist.fm is only queried when eTreeDB did not return usable data
    for the current artist/date lookup key.
    """
    etree_success = _apply_etree_lookup_to_record(config, record, evidence, observations)
    if etree_success:
        return True
    return _apply_setlistfm_lookup_to_record(config, record, evidence, observations)


def _online_lookup_key(record: ShowMetadata) -> Tuple[str, str]:
    """Return the artist/date key used to decide whether eTreeDB was tried.

    Setlist metadata can fill a missing artist/date after the first online lookup
    opportunity.  When that happens, non-compliant mode must give eTreeDB a
    chance with the new key before falling back to setlist.fm.
    """
    return (compact_ws(record.artist).casefold(), compact_ws(record.date))


def _apply_setlistfm_only_after_etree_fallback(
    config,
    record: ShowMetadata,
    evidence: Dict[str, List[Candidate]],
    observations: List[str],
    etree_success: bool,
    etree_lookup_key: Optional[Tuple[str, str]],
) -> Tuple[bool, Optional[Tuple[str, str]]]:
    """Apply setlist.fm only after eTreeDB has failed for the current key.

    The setlist.fm checkbox is a fallback to eTreeDB, not an additional online
    validator.  A successful eTreeDB venue/location answer must therefore stop
    the online chain.  If setlist metadata has supplied a new artist/date key
    since the earlier eTreeDB opportunity, retry eTreeDB first and call
    setlist.fm only if that retry still does not produce usable data.
    """
    if etree_success:
        return etree_success, etree_lookup_key
    if not getattr(config, "setlistfm_lookup", False):
        return etree_success, etree_lookup_key
    if not record.artist or not record.date:
        return etree_success, etree_lookup_key

    current_key = _online_lookup_key(record)
    if getattr(config, "etree_lookup", False) and current_key != etree_lookup_key:
        etree_lookup_key = current_key
        etree_success = _apply_etree_lookup_to_record(config, record, evidence, observations)
        if etree_success:
            return etree_success, etree_lookup_key

    _apply_setlistfm_lookup_to_record(config, record, evidence, observations)
    return etree_success, etree_lookup_key


def _append_parentheticals_to_show_name(show_name: str, parentheticals: str) -> str:
    show_name = compact_ws(show_name)
    parentheticals = compact_ws(parentheticals)
    if show_name and parentheticals and not show_name.endswith(parentheticals):
        return compact_ws(f"{show_name} {parentheticals}")
    return show_name


def _build_show_name(record: ShowMetadata) -> str:
    if not record.artist or not record.date:
        return ""
    parts = [part for part in [record.artist, record.date, record.venue, record.location] if part]
    return _append_parentheticals_to_show_name(" ".join(parts), record.parentheticals)


def _normalize_record_ascii_for_output(record: ShowMetadata) -> ShowMetadata:
    """Normalize user-facing metadata fields before logs, bootlist, folders and tags use them."""
    for attr in (
        "artist", "date", "venue", "city", "region", "country", "location",
        "parentheticals", "album_name", "qualifier", "show_name",
    ):
        try:
            value = getattr(record, attr, "")
            if value:
                setattr(record, attr, standard_ascii_text(value))
        except Exception:
            pass
    return record



def _date_evidence_supports_structured_show_name(evidence: Dict[str, List[Candidate]]) -> bool:
    """Return True when date evidence came from a source that should beat a dash-album label.

    Non-compliant ``String1 - String2`` handling intentionally treats String2 as
    an album/release name at first.  Later sources may provide a real performance
    date and/or venue/location.  When that happens, the displayed show name must
    be rebuilt from the same structured metadata used for the generated setlist
    filename; otherwise bootlist rows can say ``Artist - Album`` while the
    setlist filename says ``ArtistYYYY-MM-DDVenueLocation``.
    """
    trusted_fragments = (
        "setlist",
        "flac",
        "tag",
        "music_filename",
        "filename",
        "date_string3",
    )
    for candidate in evidence.get("date", []) or []:
        source = (getattr(candidate, "source", "") or "").lower()
        if any(fragment in source for fragment in trusted_fragments):
            return True
    return False


def _dash_album_mode_should_use_structured_show_name(record: ShowMetadata, evidence: Dict[str, List[Candidate]]) -> bool:
    """Return True when richer metadata should replace an early dash-album name.

    A dash-album guess is useful for folders like ``Artist - Album`` when no show
    metadata is available.  It should not survive after later parsing finds a
    performance date plus venue/location, or a complete setlist/tag/filename date.
    """
    if not (record.artist and record.date):
        return False
    if record.venue or record.location:
        return True
    return _is_complete_normalized_date(record.date) and _date_evidence_supports_structured_show_name(evidence)


def _log_group(config, item: dict, group_number: int) -> None:
    item["group_number"] = group_number
    item["volume_label"] = (getattr(config, "current_volume_label", "") or "").strip()
    config.logs.groups("GROUP_NUMBER: %s", group_number)
    config.logs.groups("MAIN_DIR_NAME: %s", item["main_dir_name"])
    config.logs.groups("MAIN_DIR_PATH: %s", item["main_dir_path"])
    config.logs.groups("MUSIC_FILE_COUNT: %s", item["music_file_count"])
    config.logs.groups("SETLIST_FILE: %s", item["setlist_file"])
    if item.get("setlist_files"):
        config.logs.groups("SETLIST_FILES_JSON: %s", json.dumps(item.get("setlist_files", []), ensure_ascii=False))
    if item.get("music_dirs"):
        config.logs.groups("MUSIC_DIRS_JSON: %s", json.dumps(item.get("music_dirs", []), ensure_ascii=False))
    if item.get("music_media_extensions"):
        config.logs.groups("MUSIC_MEDIA_EXTENSIONS_JSON: %s", json.dumps(item.get("music_media_extensions", []), ensure_ascii=False))
    if item.get("music_sample_files"):
        config.logs.groups("MUSIC_SAMPLE_FILES_JSON: %s", json.dumps(item.get("music_sample_files", []), ensure_ascii=False))
    if item.get("aggregate_album_name"):
        config.logs.groups("AGGREGATE_ALBUM_NAME: %s", item.get("aggregate_album_name", ""))
    if item.get("aggregation_reason"):
        config.logs.groups("AGGREGATION_REASON: %s", item.get("aggregation_reason", ""))
    config.logs.groups("VOLUME_LABEL: %s", item.get("volume_label", ""))
    for txt_file in item.get("txt_files", []):
        config.logs.groups("TXT_FILE: %s", txt_file)
    for music_dir in item.get("music_dirs", []):
        config.logs.groups("MUSIC_DIR: %s", music_dir)
    for music_file in item.get("music_sample_files", []) or item.get("music_files", []):
        config.logs.groups("MUSIC_SAMPLE_FILE: %s", music_file)
    for sample in item.get("flac_tag_samples", []):
        config.logs.groups("FLAC_TAG_FILE: %s", sample.get("file", ""))
        config.logs.groups("FLAC_TAG_ARTIST: %s", sample.get("artist", ""))
        config.logs.groups("FLAC_TAG_ALBUM: %s", sample.get("album", ""))
        config.logs.groups("FLAC_TAG_ALBUMARTIST: %s", sample.get("albumartist", ""))
        config.logs.groups("FLAC_TAG_DATE: %s", sample.get("date", ""))
    config.logs.groups("END_GROUP")
    config.logs.groups("")



def _format_show_metadata_log_lines(record: ShowMetadata, date_matches: List[Dict[str, str]]) -> List[str]:
    """Return the exact meta-log entry lines for one show metadata record."""
    lines: List[str] = []
    lines.append(f"SHOW_NAME: {record.show_name}")
    lines.append(f"SHOW_IN_CONFLICT: {'yes' if record.show_in_conflict else 'no'}")
    lines.append(f"MAIN_DIR_PATH: {record.main_dir_path}")
    lines.append(f"GROUP_NUMBER: {record.group_number}")
    lines.append(f"MAIN_DIR_NAME: {record.main_dir_name}")
    lines.append(f"SETLIST_FILE: {record.setlist_file}")
    if getattr(record, "setlist_files", None):
        lines.append(f"SETLIST_FILES_JSON: {json.dumps(record.setlist_files, ensure_ascii=False)}")
    if getattr(record, "music_dirs", None):
        lines.append(f"MUSIC_DIRS_JSON: {json.dumps(record.music_dirs, ensure_ascii=False)}")
    lines.append(f"MUSIC_FILE_COUNT: {record.music_file_count}")
    lines.append(f"VOLUME_LABEL: {record.volume_label}")
    lines.append(f"ARTIST: {record.artist}")
    lines.append(f"DATE: {record.date}")
    for match in date_matches:
        lines.append(
            "DATE_MATCH: %s | %s | %s"
            % (
                match.get("part", match.get("source", "")),
                match.get("raw", match.get("date_raw", "")),
                match.get("normalized", match.get("date_norm", "")),
            )
        )
    lines.append(f"VENUE: {record.venue}")
    lines.append(f"LOCATION: {record.location}")
    lines.append(f"CITY: {record.city}")
    lines.append(f"REGION: {record.region}")
    lines.append(f"COUNTRY: {record.country}")
    lines.append(f"QUALIFIER: {record.qualifier}")
    lines.append(f"PARENTHETICALS: {record.parentheticals}")
    lines.append(f"ALBUM_NAME: {getattr(record, 'album_name', '')}")
    lines.append(f"IS_24_BIT: {'yes' if record.is_24_bit else 'no'}")
    if getattr(record, "setlistfm_setlist_candidates", None):
        lines.append(f"SETLISTFM_SETLISTS_JSON: {json.dumps(record.setlistfm_setlist_candidates, ensure_ascii=False)}")
    for sample in record.flac_tag_samples:
        lines.append(f"FLAC_TAG_FILE: {sample.get('file', '')}")
        lines.append(f"FLAC_TAG_ARTIST: {sample.get('artist', '')}")
        lines.append(f"FLAC_TAG_ALBUM: {sample.get('album', '')}")
        lines.append(f"FLAC_TAG_ALBUMARTIST: {sample.get('albumartist', '')}")
        lines.append(f"FLAC_TAG_DATE: {sample.get('date', '')}")
    for field_name in ("artist", "date", "venue", "city", "region", "country", "qualifier"):
        for candidate in record.evidence.get(field_name, []):
            lines.append(
                "EVIDENCE_%s: %s | %s | %s"
                % (field_name.upper(), candidate.value, candidate.source, candidate.confidence)
            )
    for conflict in record.conflicts:
        lines.append(f"CONFLICT: {conflict}")
    for observation in getattr(record, "observations", []):
        lines.append(f"OBSERVATION: {observation}")
    lines.append("END_SHOW_METADATA")
    return lines


def _format_show_metadata_log_entry(record: ShowMetadata, date_matches: List[Dict[str, str]]) -> str:
    return "\n".join(_format_show_metadata_log_lines(record, date_matches)) + "\n"


def _log_show_metadata(config, record: ShowMetadata, date_matches: List[Dict[str, str]]) -> None:
    for line in _format_show_metadata_log_lines(record, date_matches):
        config.logs.show_metadata("%s", line)
    config.logs.show_metadata("")



def _collect_tag_date_candidates(record: ShowMetadata) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    for sample in record.flac_tag_samples[:2]:
        raw = (sample.get("date") or "").strip()
        if not raw:
            continue
        for item in _find_date_matches(raw, allow_slash=True):
            result = {
                "raw": item["raw"],
                "normalized": item["normalized"],
                "part": f"DATE tag: {os.path.basename(sample.get('file', ''))}",
                "source": "tag",
            }
            for key in ("date_order", "needs_setlist_confirmation"):
                if item.get(key):
                    result[key] = item[key]
            matches.append(result)
    return matches



NONCOMPLIANT_BLANK_ARTIST_TAG_MARKERS = (
    "unknown",
    "track",
    "artiste inconnu",
    "artista desconocido",
    "interprete desconocido",
    "artista sconosciuto",
    "artista desconhecido",
    "unbekannter kunstler",
    "kunstler unbekannt",
    "onbekende artiest",
    # Standalone foreign-language unknown words that commonly follow
    # artist/artiste/artista/interprete/kunstler/artiest in generic tags.
    "inconnu",
    "inconnue",
    "inconnus",
    "inconnues",
    "desconocido",
    "desconocida",
    "desconocidos",
    "desconocidas",
    "sconosciuto",
    "sconosciuta",
    "sconosciuti",
    "sconosciute",
    "desconhecido",
    "desconhecida",
    "desconhecidos",
    "desconhecidas",
    "unbekannt",
    "unbekannte",
    "unbekannter",
    "onbekend",
    "onbekende",
    "ukjent",
)


def _contains_blankable_noncompliant_artist_tag(value: str) -> str:
    folded = standard_ascii_text(value).casefold()
    for marker in NONCOMPLIANT_BLANK_ARTIST_TAG_MARKERS:
        if marker in folded:
            return marker
    return ""


def _blank_unusable_artist_tags_for_noncompliant(record: ShowMetadata, observations: Optional[List[str]] = None) -> None:
    """Blank unusable non-compliant artist-tag values before tag resolution.

    In non-compliant mode, tag-derived artist values containing generic
    unknown/track markers, including foreign-language unknown artist words,
    are treated as blank so they do not win over path-based artist detection. The metadata
    record is updated too, so meta logs show the ignored artist tag fields as
    blank. This rule is deliberately applied before the shared tag resolver
    and is not applied to compliant-mode extraction.
    """
    changed = False
    for sample in record.flac_tag_samples:
        for field_name, label in (("artist", "ARTIST"), ("albumartist", "ALBUMARTIST")):
            value = (sample.get(field_name) or "").strip()
            marker = _contains_blankable_noncompliant_artist_tag(value)
            if value and marker:
                sample[field_name] = ""
                changed = True
                if observations is not None:
                    observations.append(f"non-compliant {label} tag contains {marker}; treating tag value as blank: {value}")

    if changed:
        record.flac_tag_artist_values = _unique_preserve([
            compact_ws((sample.get("artist") or "").strip())
            for sample in record.flac_tag_samples
            if (sample.get("artist") or "").strip()
        ])
        record.flac_tag_albumartist_values = _unique_preserve([
            compact_ws((sample.get("albumartist") or "").strip())
            for sample in record.flac_tag_samples
            if (sample.get("albumartist") or "").strip()
        ])


def _resolve_artist_from_tags(record: ShowMetadata, matcher: Optional[ArtistMatcher], evidence: Dict[str, List[Candidate]], conflicts: List[str], observations: Optional[List[str]] = None) -> str:
    """Resolve the show artist from music tags.

    Requirements rule: once a usable tag artist is found, tag-derived artist
    wins and path-based artist identification must not be consulted for this
    show. Prefer ARTIST over ALBUMARTIST; use ALBUMARTIST only when ARTIST is
    blank. If the selected tag value resolves in the Artist DB, store the DB
    master name. Otherwise keep the tag artist as supplied/normalized and
    record only an observation.
    """
    artist_tag = ""
    albumartist_tag = ""
    for sample in record.flac_tag_samples[:2]:
        if not artist_tag and (sample.get("artist") or "").strip():
            artist_tag = compact_ws(sample.get("artist", "").strip())
        if not albumartist_tag and (sample.get("albumartist") or "").strip():
            albumartist_tag = compact_ws(sample.get("albumartist", "").strip())

    tag_source = "flac_tag_artist"
    term = artist_tag
    if not term:
        term = albumartist_tag
        tag_source = "flac_tag_albumartist"

    if not term:
        return ""

    if artist_tag and albumartist_tag and artist_tag.casefold() != albumartist_tag.casefold():
        if observations is not None:
            observations.append(f"tag ARTIST and ALBUMARTIST differ; using ARTIST tag: {artist_tag}")

    detail = _lookup_artist_detail(term, matcher)
    if detail["status"] == "matched":
        master = detail["masters"][0]
        evidence.setdefault("artist", []).append(Candidate(master, f"{tag_source}:{term}", 95))
        return master

    if detail["status"] == "collision" and observations is not None:
        observations.append(_collision_note(f"tag artist query collision; using raw tag artist: {term}", detail["masters"]))
    elif observations is not None:
        observations.append(f"tag artist not found in DB; using raw tag artist: {term}")

    evidence.setdefault("artist", []).append(Candidate(term, f"{tag_source}_unmatched:{term}", 90))
    return term



def _collect_pattern_matches_from_parts(parts: Sequence[Tuple[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    required_matches: List[Dict[str, str]] = []
    optional_matches: List[Dict[str, str]] = []
    for part_text, part_path in parts:
        required = _string_date_matches(part_text, allow_string2=False)
        if required:
            for match in required:
                item = dict(match)
                item["part"] = part_text
                item["part_path"] = part_path
                required_matches.append(item)
        else:
            optional = _string_date_matches(part_text, allow_string2=True)
            for match in optional:
                item = dict(match)
                item["part"] = part_text
                item["part_path"] = part_path
                optional_matches.append(item)
    return required_matches, optional_matches


def _collect_pattern_matches(main_dir_path: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    return _collect_pattern_matches_from_parts(_candidate_path_parts(main_dir_path))


def _collect_pattern_matches_for_group(group: dict) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Collect path pattern matches plus preserved aggregate-name hints.

    Volume-style aggregation can make the shared parent the logical group path.
    When all volume siblings share the same stripped base, preserve that base as
    a metadata hint so a name like "Artist Date Venue City ST (Volume 1)" can
    still provide Artist/Date/Venue/Location after the folders are grouped.
    """
    required_matches, optional_matches = _collect_pattern_matches(group.get("main_dir_path", ""))
    hint = compact_ws(group.get("aggregate_release_base", ""))
    if not hint:
        return required_matches, optional_matches
    cleaned = _clean_piece(_strip_trailing_parenthetical_items(hint))
    if not cleaned or _is_wrapper(cleaned):
        return required_matches, optional_matches
    existing_keys = {(m.get("part", "").casefold(), m.get("date_norm", ""), m.get("string2", "").casefold()) for m in required_matches + optional_matches}
    hint_required, hint_optional = _collect_pattern_matches_from_parts([(cleaned, f"{os.path.normpath(group.get('main_dir_path', ''))}::{cleaned}")])
    for match in hint_required:
        key = (match.get("part", "").casefold(), match.get("date_norm", ""), match.get("string2", "").casefold())
        if key not in existing_keys:
            required_matches.append(match)
            existing_keys.add(key)
    for match in hint_optional:
        key = (match.get("part", "").casefold(), match.get("date_norm", ""), match.get("string2", "").casefold())
        if key not in existing_keys:
            optional_matches.append(match)
            existing_keys.add(key)
    return required_matches, optional_matches




def _pattern_matches_have_abbreviation_candidate(pattern_matches: List[Dict[str, str]]) -> bool:
    return any(bool(match.get("abbr_candidate")) for match in pattern_matches)


def _resolve_artist_from_path_before_abbreviation(
    group: dict,
    pattern_matches: List[Dict[str, str]],
    matcher: Optional[ArtistMatcher],
    evidence: Dict[str, List[Candidate]],
    conflicts: List[str],
) -> str:
    """For artist-no-space-date cases, prefer a DB-backed artist elsewhere in path.

    A String1Date pattern can make String1 look like an abbreviation. Before
    resolving that short String1 as an abbreviation, non-compliant mode should
    scan the other path components for a normal DB-backed artist. The matched
    String1Date component is excluded so that the abbreviation itself is not
    counted as the path artist.
    """
    exclude_paths = {
        match.get("part_path", "")
        for match in pattern_matches
        if match.get("abbr_candidate") and match.get("part_path")
    }
    return _resolve_artist_from_subdirs(
        group,
        matcher,
        evidence,
        conflicts,
        pattern_artist="",
        exclude_part_paths=exclude_paths,
        source_label="path_artist_before_abbreviation",
    )

def _resolve_artist_from_pattern_matches(pattern_matches: List[Dict[str, str]], matcher: Optional[ArtistMatcher], evidence: Dict[str, List[Candidate]], conflicts: List[str]) -> Tuple[str, List[Dict[str, object]]]:
    lookups: List[Dict[str, object]] = []
    if not pattern_matches:
        return "", lookups

    for match in pattern_matches:
        term = _choose_lookup_text(match)
        detail = _lookup_artist_detail(term, matcher)
        lookups.append({
            "match": match,
            "term": term,
            "status": detail["status"],
            "masters": list(detail["masters"]),
            "aliases": detail["aliases"],
        })

    if len(pattern_matches) == 1:
        row = lookups[0]
        if row["status"] == "matched" and row["masters"]:
            master = row["masters"][0]
            evidence.setdefault("artist", []).append(Candidate(master, f"path pattern:{row['term']}", 70))
            return master, lookups
        if row["status"] == "collision":
            conflicts.append(_collision_note(f"artist query collision for String1: {row['term']}", row["masters"]))
        return "", lookups

    matched_masters = [row["masters"][0] for row in lookups if row["status"] == "matched" and row["masters"]]
    if any(row["status"] == "collision" for row in lookups):
        collision_names: List[str] = []
        for row in lookups:
            if row["status"] == "collision":
                collision_names.extend(row["masters"])
        conflicts.append(_collision_note("artist query collision across path pattern matches", collision_names))
        return "", lookups

    unique_masters = _unique_preserve(matched_masters)
    if len(unique_masters) == 1:
        master = unique_masters[0]
        evidence.setdefault("artist", []).append(Candidate(master, "path_pattern_consensus", 72))
        return master, lookups
    if len(unique_masters) > 1:
        conflicts.append(_collision_note("artist conflict across path pattern matches", unique_masters))
    return "", lookups



def _resolve_artist_from_subdirs(
    group: dict,
    matcher: Optional[ArtistMatcher],
    evidence: Dict[str, List[Candidate]],
    conflicts: List[str],
    pattern_artist: str = "",
    exclude_part_paths: Optional[set] = None,
    source_label: str = "subdirectory",
) -> str:
    hits: List[Tuple[str, str]] = []
    exclude_norm = {os.path.normcase(os.path.normpath(path)) for path in (exclude_part_paths or set()) if path}
    seen = set()
    for part, _part_path in _eligible_artist_path_parts(group):
        if _part_path and os.path.normcase(os.path.normpath(_part_path)) in exclude_norm:
            continue
        detail = _lookup_artist_detail(part, matcher)
        if detail["status"] == "collision":
            conflicts.append(_collision_note(f"artist query collision for {source_label}: {part}", detail["masters"]))
            continue
        if detail["status"] == "matched" and detail["masters"]:
            master = detail["masters"][0]
            key = (master.casefold(), part.casefold())
            if key not in seen:
                seen.add(key)
                hits.append((master, part))

    if not hits:
        return pattern_artist

    chosen_master = ""
    chosen_source = ""
    incompatible: List[str] = []

    for master, source_part in sorted(hits, key=lambda item: (-_normalized_length(item[0]), -len(item[1]), item[0].casefold(), item[1].casefold())):
        if pattern_artist and not _has_subset_relationship(master, pattern_artist):
            incompatible.append(master)
            continue
        if not chosen_master:
            chosen_master = master
            chosen_source = source_part
            continue
        if _has_subset_relationship(chosen_master, master):
            if _normalized_length(master) > _normalized_length(chosen_master):
                chosen_master = master
                chosen_source = source_part
            continue
        if _has_subset_relationship(master, chosen_master):
            continue
        incompatible.extend([chosen_master, master])

    if incompatible:
        if pattern_artist:
            conflicts.append(_collision_note(f"artist conflict between pattern artist and {source_label} artist", [pattern_artist] + incompatible))
        else:
            conflicts.append(_collision_note(f"artist conflict across {source_label} matches", incompatible))
        return ""

    if chosen_master:
        evidence.setdefault("artist", []).append(Candidate(chosen_master, f"{source_label}:{chosen_source}", 60 if not pattern_artist else 62))
    return chosen_master or pattern_artist



def _collect_path_date_matches(group: dict) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    for part, part_path in _all_clean_path_parts(group["main_dir_path"]):
        for date_match in _find_date_matches(part):
            result = {
                "raw": date_match["raw"],
                "normalized": date_match["normalized"],
                "part": part,
                "part_path": part_path,
                "source": "path",
            }
            for key in ("date_order", "needs_setlist_confirmation"):
                if date_match.get(key):
                    result[key] = date_match[key]
            matches.append(result)
    return matches



def _collect_filename_date_matches(group: dict) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    for music_file in _iter_group_media_files(group):
        name = _clean_piece(_strip_multi_extension(os.path.basename(music_file)))
        for date_match in _find_date_matches(name):
            result = {
                "raw": date_match["raw"],
                "normalized": _normalize_filename_date(date_match["normalized"]),
                "part": name,
                "part_path": music_file,
                "source": "filename",
            }
            for key in ("date_order", "needs_setlist_confirmation"):
                if date_match.get(key):
                    result[key] = date_match[key]
            matches.append(result)
    return matches




_SETLIST_AIRDATE_SPLIT_RE = re.compile(r"(?i)\bair\s*date\b\s*[:=-]?.*$")
_SETLIST_BROADCAST_LABEL_RE = re.compile(r"(?i)\b(?:air\s*date|aired|broadcast(?:\s*date)?|simulcast|telecast)\b")
_SETLIST_COLLECTION_RANGE_CLUE_RE = re.compile(
    r"(?i)\b(?:collection|series|archive|archives|complete\s+run|from\s+(?:19|20)?\d{2}\s*[-_]\s*(?:\d{2}|(?:19|20)\d{2})|between)\b"
)


def _setlist_date_specificity_weight(normalized: str) -> int:
    if _is_complete_normalized_date(normalized):
        return 30
    if _is_normalized_year_range(normalized):
        return 5
    return _date_specificity(normalized) * 8


def _setlist_line_date_fragments(line: str) -> List[Tuple[str, int, str]]:
    """Return text fragments to scan for setlist date fallback, with scores.

    Explicit metadata lines are trusted before prose filtering.  For ``VENUE:``
    values, scan only the performance-side text before labels such as
    ``Air date:`` so a performance date embedded after the city outranks the
    later broadcast date.  Paragraph prose remains low confidence and will not
    beat explicit metadata or short header lines.
    """
    raw = compact_ws(str(line or "").strip())
    if not raw:
        return []
    matched = explicit_metadata_match(raw)
    if matched:
        key, value = matched
        value = compact_ws(value)
        before_airdate = _SETLIST_AIRDATE_SPLIT_RE.sub("", value).strip(" ,;.-")
        fragments: List[Tuple[str, int, str]] = []
        if key == "date":
            fragments.append((value, 110, "explicit_date"))
        elif key == "venue":
            if before_airdate:
                fragments.append((before_airdate, 105, "explicit_venue_performance_side"))
            # Do not scan the air-date/broadcast tail as performance evidence.
        elif key in {"location", "loc", "city", "state", "region", "province", "country", "place"}:
            if before_airdate:
                fragments.append((before_airdate, 80, f"explicit_{key}"))
        elif before_airdate:
            fragments.append((before_airdate, 70, f"explicit_{key}"))
        return [(frag, score, kind) for frag, score, kind in fragments if frag]

    if _SETLIST_BROADCAST_LABEL_RE.search(raw):
        raw = _SETLIST_AIRDATE_SPLIT_RE.sub("", raw).strip(" ,;.-")
        if not raw:
            return []

    if looks_like_sentence_prose_line(raw):
        score = 12 if _SETLIST_COLLECTION_RANGE_CLUE_RE.search(raw) else 5
        return [(raw, score, "prose_collection_or_commentary")]

    if _SETLIST_COLLECTION_RANGE_CLUE_RE.search(raw):
        return [(raw, 20, "collection_range_clue")]

    return [(raw, 70, "header_like")]


def _ranked_setlist_date_matches(header_lines: Sequence[str]) -> List[Dict[str, str]]:
    ranked: List[Tuple[int, int, int, int, Dict[str, str]]] = []
    serial = 0
    for line_index, line in enumerate(header_lines):
        for fragment, base_score, kind in _setlist_line_date_fragments(line):
            for match in _find_date_matches(fragment, allow_slash=True):
                normalized = match.get("normalized", "")
                if not normalized:
                    continue
                item = dict(match)
                item["line_index"] = str(line_index)
                item["setlist_date_context"] = kind
                item["setlist_date_score"] = str(base_score)
                score = base_score + _setlist_date_specificity_weight(normalized)
                # Collection/prose ranges are clues, not performance dates.  Keep
                # them available only after explicit/header evidence fails.
                if kind in {"prose_collection_or_commentary", "collection_range_clue"} and _is_normalized_year_range(normalized):
                    score -= 8
                ranked.append((score, -line_index, -int(match.get("start", 0)), -serial, item))
                serial += 1
    ranked.sort(reverse=True)
    return [item for _score, _line_neg, _start_neg, _serial_neg, item in ranked]

def _read_text_for_date_fallback(path_name: str) -> str:
    try:
        with open(path_name, "rb") as infile:
            data = infile.read()
    except OSError:
        return ""
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.count("\x00") >= max(3, len(text) // 100):
            continue
        return text.replace("\r\n", "\n").replace("\r", "\n")
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _setlist_content_lines_for_date(text: str, limit: int = 80) -> List[str]:
    """Return setlist lines eligible for date fallback scanning.

    Setlist-file date fallback must be bounded to the same metadata header
    window used for venue/location extraction.  Stop at the first true
    track-list line or checksum/hash/log section so song titles, lineage,
    verification logs, and hashes cannot provide date evidence.
    """
    lines: List[str] = []
    for raw in (text or "").splitlines():
        line = compact_ws(raw.strip("\ufeff"))
        if not line:
            continue
        if line.startswith("--------- End of "):
            continue
        if is_setlist_metadata_scan_boundary(line):
            break
        lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _collect_setlist_date_matches(group: dict) -> List[Dict[str, str]]:
    """Return the best setlist-text date candidate per unique setlist file.

    Explicit metadata/header evidence is scored higher than prose paragraphs.
    This lets lines such as ``VENUE: ... 23/12/72; Air date: ...`` supply the
    performance date while broad prose such as ``from 1972-75`` remains only a
    low-confidence collection/range clue.
    """
    paths = _unique_preserve([group.get("setlist_file", "")] + list(group.get("setlist_files", []) or []))
    matches: List[Dict[str, str]] = []
    for setlist_path in paths:
        if not setlist_path or not os.path.isfile(setlist_path):
            continue
        text = _read_text_for_date_fallback(setlist_path)
        if not text:
            continue
        header_lines = _setlist_content_lines_for_date(text, limit=80)
        ranked_matches = _ranked_setlist_date_matches(header_lines)
        if not ranked_matches:
            header_text = "\n".join(header_lines)
            if "," in header_text:
                ranked_matches = _ranked_setlist_date_matches([header_text.replace(",", " ")])
        if not ranked_matches:
            continue
        chosen = ranked_matches[0]
        basename = os.path.basename(setlist_path)
        result = {
            "raw": chosen.get("raw", ""),
            "normalized": chosen.get("normalized", ""),
            "part": basename,
            "part_path": setlist_path,
            "source": f"setlist_file:{basename}:{chosen.get('setlist_date_context', 'date')}",
        }
        for key in ("date_order", "needs_setlist_confirmation", "setlist_date_context", "setlist_date_score"):
            if chosen.get(key):
                result[key] = chosen[key]
        matches.append(result)
    return matches


def _setlist_collection_clue_near_beginning(group: dict) -> bool:
    """Return True when a selected setlist starts like a collection/range file."""
    paths = _unique_preserve([group.get("setlist_file", "")] + list(group.get("setlist_files", []) or []))
    for setlist_path in paths:
        if not setlist_path or not os.path.isfile(setlist_path):
            continue
        text = _read_text_for_date_fallback(setlist_path)
        if not text:
            continue
        header_text = "\n".join(_setlist_content_lines_for_date(text, limit=40))
        if re.search(r"(?i)\bcollection\b", header_text):
            return True
    return False


def _is_normalized_year_range(normalized: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}-(?:19|20)\d{2}", normalized or ""))


def _normalized_year_range_bounds(normalized: str) -> Tuple[int, int]:
    if not _is_normalized_year_range(normalized):
        return (0, 0)
    left, right = normalized.split("-", 1)
    return int(left), int(right)


def _date_specificity(normalized: str) -> int:
    if _is_normalized_year_range(normalized):
        return 1
    parts = (normalized or "").split("-")
    if len(parts) != 3:
        return 0
    score = 0
    for part in parts:
        if part and part.isdigit() and "x" not in part.lower():
            score += 1
    return score

def _is_complete_normalized_date(normalized: str) -> bool:
    return _date_specificity(normalized) == 3


def _dates_compatible(left: str, right: str) -> bool:
    if _is_normalized_year_range(left) or _is_normalized_year_range(right):
        if _is_normalized_year_range(left) and _is_normalized_year_range(right):
            return left == right
        range_value = left if _is_normalized_year_range(left) else right
        date_value = right if range_value == left else left
        parts = (date_value or "").split("-")
        if len(parts) != 3 or not parts[0].isdigit():
            return False
        start_year, end_year = _normalized_year_range_bounds(range_value)
        return start_year <= int(parts[0]) <= end_year
    left_parts = (left or "").split("-")
    right_parts = (right or "").split("-")
    if len(left_parts) != 3 or len(right_parts) != 3:
        return False
    for a, b in zip(left_parts, right_parts):
        a_known = a.isdigit() and "x" not in a.lower()
        b_known = b.isdigit() and "x" not in b.lower()
        if a_known and b_known and a != b:
            return False
    return True

def _most_specific_compatible_date(left: str, right: str) -> str:
    if _date_specificity(right) > _date_specificity(left):
        return right
    return left


def _filtered_preferred_date_candidates(candidates: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    filtered = [dict(candidate) for candidate in candidates if candidate.get("normalized")]
    if not filtered:
        return []
    best_specificity = max(_date_specificity(candidate["normalized"]) for candidate in filtered)
    if best_specificity >= 3:
        # A complete date is more reliable than partial path noise such as
        # November2020. If all complete candidates agree, ignore less-specific
        # candidates even if the less-specific value appears in the path too.
        complete = [candidate for candidate in filtered if _is_complete_normalized_date(candidate["normalized"])]
        unique_complete = _unique_preserve([candidate["normalized"] for candidate in complete])
        if len(unique_complete) == 1:
            return complete
    return filtered


def _resolve_date_from_candidates(candidates: Sequence[Dict[str, str]], evidence: Dict[str, List[Candidate]], conflicts: List[str], conflict_label: str) -> Tuple[str, List[Dict[str, str]]]:
    filtered = _filtered_preferred_date_candidates(candidates)
    if not filtered:
        return "", []
    unique_values = _unique_preserve([candidate["normalized"] for candidate in filtered])
    if len(unique_values) == 1:
        normalized = unique_values[0]
        source = filtered[0].get("source", "date")
        evidence.setdefault("date", []).append(Candidate(normalized, source, 65))
        return normalized, filtered
    conflicts.append(conflict_label)
    return "", filtered


def _resolve_date_from_candidates_with_setlist_validation(
    group: dict,
    candidates: Sequence[Dict[str, str]],
    evidence: Dict[str, List[Candidate]],
    conflicts: List[str],
    conflict_label: str,
    observations: List[str],
) -> Tuple[str, List[Dict[str, str]]]:
    filtered_initial = _filtered_preferred_date_candidates(candidates)
    confirmation_needed = [
        candidate for candidate in filtered_initial
        if candidate.get("needs_setlist_confirmation") and str(candidate.get("source", "")).startswith(("path", "filename"))
    ]
    range_only = filtered_initial and all(_is_normalized_year_range(candidate.get("normalized", "")) for candidate in filtered_initial)
    if range_only:
        setlist_matches = _collect_setlist_date_matches(group)
        compatible_complete_hits: List[Tuple[int, str, Dict[str, str], str]] = []
        for candidate in filtered_initial:
            candidate_range = candidate.get("normalized", "")
            for setlist_match in setlist_matches:
                setlist_date = setlist_match.get("normalized", "")
                if not (_is_complete_normalized_date(setlist_date) and _dates_compatible(candidate_range, setlist_date)):
                    continue
                confidence = int(str(setlist_match.get("setlist_date_score", "0") or "0"))
                compatible_complete_hits.append((confidence, setlist_date, setlist_match, candidate_range))
        unique_complete = _unique_preserve([hit[1] for hit in compatible_complete_hits])
        if len(unique_complete) == 1:
            compatible_complete_hits.sort(key=lambda item: (-item[0], item[1], item[2].get("source", "")))
            _confidence, chosen_date, chosen_setlist, candidate_range = compatible_complete_hits[0]
            evidence.setdefault("date", []).append(Candidate(chosen_date, f"setlist_validation:{chosen_setlist.get('source', 'setlist_file')}", 82))
            observations.append(
                "complete selected-setlist date overrides path/range clue: "
                f"{chosen_setlist.get('raw', chosen_date)} is within {candidate_range}; using {chosen_date}"
            )
            return chosen_date, filtered_initial + setlist_matches
        if len(unique_complete) > 1:
            observations.append("selected setlist contains multiple complete dates compatible with the path/range clue")

    if confirmation_needed:
        setlist_matches = _collect_setlist_date_matches(group)
        validation_hits: List[Tuple[int, str, Dict[str, str], str]] = []
        for candidate in confirmation_needed:
            candidate_date = candidate.get("normalized", "")
            for setlist_match in setlist_matches:
                setlist_date = setlist_match.get("normalized", "")
                if candidate_date and setlist_date and _dates_compatible(candidate_date, setlist_date):
                    chosen = _most_specific_compatible_date(candidate_date, setlist_date)
                    validation_hits.append((_date_specificity(chosen), chosen, setlist_match, candidate_date))
        if validation_hits:
            validation_hits.sort(key=lambda item: (-item[0], item[1], item[2].get("source", "")))
            chosen_date = validation_hits[0][1]
            chosen_setlist = validation_hits[0][2]
            evidence.setdefault("date", []).append(Candidate(chosen_date, f"setlist_validation:{chosen_setlist.get('source', 'setlist_file')}", 78))
            observations.append(
                "European-style path date confirmed from selected setlist contents: "
                f"{chosen_setlist.get('raw', chosen_date)} validates {validation_hits[0][3]}; using {chosen_date}"
            )
            return chosen_date, filtered_initial + setlist_matches
        range_candidates = [candidate for candidate in filtered_initial if _is_normalized_year_range(candidate.get("normalized", ""))]
        if range_candidates and _setlist_collection_clue_near_beginning(group):
            chosen_range = sorted(candidate["normalized"] for candidate in range_candidates)[0]
            evidence.setdefault("date", []).append(Candidate(chosen_range, "setlist_collection_clue", 72))
            observations.append(
                "European-style path date was not confirmed; selected setlist begins like a collection, so using range "
                f"{chosen_range}"
            )
            return chosen_range, filtered_initial + setlist_matches
        observations.append("European-style path date found but not confirmed by selected setlist contents")
        return "", filtered_initial + setlist_matches

    before_conflicts = len(conflicts)
    normalized, matches = _resolve_date_from_candidates(candidates, evidence, conflicts, conflict_label)
    if normalized or len(conflicts) == before_conflicts:
        return normalized, matches

    setlist_matches = _collect_setlist_date_matches(group)
    if not setlist_matches:
        return "", matches

    conflict_values = _unique_preserve([match["normalized"] for match in matches if match.get("normalized")])
    validation_hits: List[Tuple[int, str, Dict[str, str], str]] = []
    for setlist_match in setlist_matches:
        setlist_date = setlist_match.get("normalized", "")
        if not setlist_date:
            continue
        for conflict_value in conflict_values:
            if not _dates_compatible(conflict_value, setlist_date):
                continue
            chosen = _most_specific_compatible_date(conflict_value, setlist_date)
            validation_hits.append((_date_specificity(chosen), chosen, setlist_match, conflict_value))

    if not validation_hits:
        range_candidates = [value for value in conflict_values if _is_normalized_year_range(value)]
        if range_candidates and _setlist_collection_clue_near_beginning(group):
            chosen_range = sorted(range_candidates)[0]
            del conflicts[before_conflicts:]
            evidence.setdefault("date", []).append(Candidate(chosen_range, "setlist_collection_clue", 72))
            observations.append(
                "date/range conflict resolved as range because selected setlist begins like a collection: "
                f"using {chosen_range}"
            )
            return chosen_range, matches + setlist_matches
        observations.append("setlist date validation did not match any conflicting date candidate")
        return "", matches + setlist_matches

    validation_hits.sort(key=lambda item: (-item[0], item[1], item[2].get("source", "")))
    chosen_date = validation_hits[0][1]
    chosen_setlist = validation_hits[0][2]
    chosen_conflict_value = validation_hits[0][3]
    compatible_chosen = [hit for hit in validation_hits if hit[1] == chosen_date]
    unique_chosen_dates = _unique_preserve([hit[1] for hit in validation_hits])
    if len(unique_chosen_dates) > 1:
        # Keep the conflict if setlist validation is itself ambiguous.
        observations.append("setlist date validation matched more than one conflicting candidate")
        return "", matches + setlist_matches

    del conflicts[before_conflicts:]
    evidence.setdefault("date", []).append(Candidate(chosen_date, f"setlist_validation:{chosen_setlist.get('source', 'setlist_file')}", 78))
    observations.append(
        "date conflict resolved from setlist contents: "
        f"{chosen_setlist.get('raw', chosen_date)} validates {chosen_conflict_value}; using {chosen_date}"
    )
    return chosen_date, matches + setlist_matches


def _apply_string2_to_record(record: ShowMetadata, match: Optional[Dict[str, str]], evidence: Dict[str, List[Candidate]]) -> None:
    if not match or not match.get("string2"):
        return
    venue, city, region, country, extra_parenthetical = _parse_string2(match["string2"])
    record.venue = venue
    record.city = city
    record.region = region
    record.country = country
    record.location = _join_location(city, region, country)
    if extra_parenthetical:
        record.parentheticals = compact_ws(f"{record.parentheticals} ({extra_parenthetical})").strip()
    if record.venue:
        evidence.setdefault("venue", []).append(Candidate(record.venue, f"path_part:{match['part']}", 40))
    if record.city:
        evidence.setdefault("city", []).append(Candidate(record.city, f"path_part:{match['part']}", 35))
    if record.region:
        evidence.setdefault("region", []).append(Candidate(record.region, f"path_part:{match['part']}", 35))
    if record.country:
        evidence.setdefault("country", []).append(Candidate(record.country, f"path_part:{match['part']}", 35))


def _apply_setlist_metadata_to_noncompliant_record(config, record: ShowMetadata, evidence: Dict[str, List[Candidate]], observations: List[str]) -> bool:
    """Use the selected setlist text after path and eTreeDB metadata.

    Non-compliant precedence is path, then eTreeDB, then selected setlist
    metadata, then setlist.fm.  The setlist extractor always runs when a
    selected file exists so it can log meaningful differences, but it fills only
    blank artist/venue/location fields and never overwrites metadata that was
    already identified.  Differences are not logged when values are equal or one
    is a token-boundary subset of the other (for example, "Fillmore" vs.
    "Fillmore West").
    """
    if getattr(config, "compliant", False):
        return False
    if not record.setlist_file:
        observations.append("setlist metadata lookup skipped: no selected setlist file")
        return False

    result = extract_setlist_venue_location(record.setlist_file, getattr(config, "tlo_dbs_dir", ""))
    if not (getattr(result, "artist", "") or result.venue or result.city or result.region or result.country or result.location):
        if result.source and result.source not in {"setlist_metadata:missing_setlist_file"}:
            observations.append(f"setlist metadata lookup found no usable artist/venue/location: {result.source}")
        return False

    applied = False
    confidence = int(result.confidence or 55)
    source = result.source or "setlist_metadata"

    if getattr(result, "artist", ""):
        if not record.artist:
            record.artist = result.artist
            evidence.setdefault("artist", []).append(Candidate(record.artist, "setlist_metadata:EXPLICIT_ARTIST_KEY", max(confidence, 80)))
            applied = True
        else:
            _observe_metadata_disagreement(observations, "setlist metadata", "artist", record.artist, result.artist)

    if result.venue:
        if not record.venue:
            record.venue = result.venue
            evidence.setdefault("venue", []).append(Candidate(record.venue, source, confidence))
            applied = True
        else:
            _observe_metadata_disagreement(observations, "setlist metadata", "venue", record.venue, result.venue)

    if result.city:
        if not record.city:
            record.city = result.city
            evidence.setdefault("city", []).append(Candidate(record.city, source, confidence))
            applied = True
        else:
            _observe_metadata_disagreement(observations, "setlist metadata", "city", record.city, result.city)

    if result.region:
        if not record.region and not record.country:
            record.region = result.region
            evidence.setdefault("region", []).append(Candidate(record.region, source, confidence))
            applied = True
        elif record.region:
            _observe_metadata_disagreement(observations, "setlist metadata", "region", record.region, result.region)

    if result.country:
        if not record.country and not record.region:
            record.country = result.country
            evidence.setdefault("country", []).append(Candidate(record.country, source, confidence))
            applied = True
        elif record.country:
            _observe_metadata_disagreement(observations, "setlist metadata", "country", record.country, result.country)

    result_location = result.location or _join_location(result.city, result.region, result.country)
    if not record.location and (record.city or record.region or record.country):
        record.location = _join_location(record.city, record.region, record.country)
        applied = True
    elif record.location and result_location:
        _observe_metadata_disagreement(observations, "setlist metadata", "location", record.location, result_location)

    if applied:
        observations.append(f"setlist metadata lookup used selected setlist file: {os.path.basename(record.setlist_file)}")
        if result.raw:
            observations.append(f"setlist metadata raw match: {result.raw}")
    else:
        observations.append("setlist metadata lookup returned usable data but existing metadata already populated the same fields")
        if result.raw:
            observations.append(f"setlist metadata raw match: {result.raw}")
    return applied



def _extract_metadata_for_group_compliant(config, group: dict, artist_matcher: Optional[ArtistMatcher]) -> Tuple[ShowMetadata, List[Dict[str, str]], List[str]]:
    record = ShowMetadata(
        group_number=group["group_number"],
        main_dir_name=group["main_dir_name"],
        main_dir_path=group["main_dir_path"],
        setlist_file=group.get("setlist_file", ""),
        music_file_count=group.get("music_file_count", 0),
        setlist_files=list(group.get("setlist_files", []) or ([group.get("setlist_file", "")] if group.get("setlist_file") else [])),
        music_dirs=list(group.get("music_dirs", []) or ([group.get("main_dir_path", "")] if group.get("main_dir_path") else [])),
        volume_label=(getattr(config, "current_volume_label", "") or "").strip(),
        flac_tag_samples=[],
        flac_tag_artist_values=[],
        flac_tag_album_values=[],
        flac_tag_albumartist_values=[],
        flac_tag_date_values=[],
    )
    evidence: Dict[str, List[Candidate]] = {}
    conflicts: List[str] = []
    observations: List[str] = []
    unresolved_reasons: List[str] = []
    date_matches: List[Dict[str, str]] = []
    compliant_dash_match = False
    compliant_string_date_match = False
    compliant_folder_name_show_match = False
    compliant_mp3_year_show_match = False

    compliant_text, compliant_source_path = _compliant_pattern_text_for_group(record, group, observations)
    matches = _compliant_string_date_matches(compliant_text, allow_string2=False)
    if not matches:
        observations.append("unable to find String1 Date String2 in compliant path text")
        dash_match = _match_string_dash_string(compliant_text)
        dash_artist = ""
        if dash_match:
            dash_match["part"] = compliant_text
            dash_match["part_path"] = compliant_source_path
            dash_term = dash_match["string1"] if len(re.sub(r"[^A-Za-z]", "", dash_match["string1"])) <= 4 and dash_match["string1"].isupper() else (dash_match["string1_stripped"] or dash_match["string1"])
            dash_artist = _set_compliant_artist_from_string1(
                config,
                dash_match.get("string1", ""),
                dash_term,
                artist_matcher,
                evidence,
                observations,
                "compliant:string_dash_string",
                66,
                "String1 - String2",
            )
        else:
            if _compliant_artist_mode(config) == "as-is":
                dash_artist, dash_match = _resolve_compliant_dash_from_group_as_is(group, evidence, observations)
            else:
                dash_artist, dash_match = _resolve_from_string_dash_string(group, artist_matcher, evidence, conflicts, compliant=True)
        if dash_artist:
            record.artist = dash_artist
        if dash_match:
            compliant_dash_match = True
            raw_string2 = compact_ws(dash_match.get("string2", ""))
            stripped_string2, parentheticals = _strip_trailing_parenthetical_items_with_cache(raw_string2)
            # For compliant String1 - String2, String2 is the show title as
            # supplied.  If it is parenthetical-only, do not strip it to an
            # empty value (e.g., "James Taylor - (Live)").
            string2_for_show = stripped_string2 or raw_string2
            parentheticals_for_show = parentheticals if stripped_string2 else ""
            _set_compliant_string2_raw(record, string2_for_show, parentheticals_for_show, evidence, f"compliant:string_dash_string:{dash_match.get('part_path', '')}")
            observations.append("compliant String1 - String2 matched: String2 stored as raw venue and album name; no date assigned")
        else:
            string_date_matches = _compliant_string_date_matches(compliant_text, allow_string2=True)
            if string_date_matches:
                chosen = dict(string_date_matches[0])
                candidate_artist = (chosen.get("string1", "") or "").strip()
                artist_term = _strip_string1_articles(candidate_artist)
                record.artist = _set_compliant_artist_from_string1(
                    config,
                    candidate_artist,
                    artist_term,
                    artist_matcher,
                    evidence,
                    observations,
                    "compliant:string_date",
                    68,
                    "String1 Date",
                )
                record.date = chosen.get("date_norm", "")
                if record.date:
                    evidence.setdefault("date", []).append(Candidate(record.date, "compliant:string_date", 68))
                    date_matches.append({"raw": chosen.get("date_raw", ""), "normalized": record.date, "part": compliant_text, "source": "compliant_string_date"})
                    if chosen.get("date_separator_repaired"):
                        observations.append(f"compliant date separator repair: {chosen.get('date_raw', '')} normalized to {record.date}")
                compliant_string_date_match = bool(record.artist and record.date)
                observations.append("compliant String1 Date matched: no venue or location assigned")
            else:
                mp3_year_show_name = _compliant_mp3_year_show_name(group, record.main_dir_name)
                if mp3_year_show_name:
                    record.show_name = mp3_year_show_name
                    compliant_mp3_year_show_match = True
                    observations.append("compliant MP3 year folder matched: using four-digit year as show name")
                else:
                    record.show_name = compliant_text
                    compliant_folder_name_show_match = bool(record.show_name)
                    observations.append("unable to find compliant String1 Date String2, String1 - String2, or String1 Date pattern")
                    observations.append("compliant fallback matched: using folder name as show name with no artist, date, venue, or location")
    else:
        chosen = dict(matches[0])
        candidate_artist = (chosen.get("string1", "") or "").strip()
        artist_term = _strip_string1_articles(candidate_artist)
        record.artist = _set_compliant_artist_from_string1(
            config,
            candidate_artist,
            artist_term,
            artist_matcher,
            evidence,
            observations,
            "compliant:path_part",
            70,
            "String1 Date String2",
        )

        record.date = chosen.get("date_norm", "")
        if record.date:
            evidence.setdefault("date", []).append(Candidate(record.date, "compliant:path_part", 70))
            date_matches.append({"raw": chosen.get("date_raw", ""), "normalized": record.date, "part": compliant_text, "source": "compliant"})
            if chosen.get("date_separator_repaired"):
                observations.append(f"compliant date separator repair: {chosen.get('date_raw', '')} normalized to {record.date}")

        stripped_string2, parentheticals = _strip_trailing_parenthetical_items_with_cache(chosen.get("string2", ""))
        _set_compliant_string2_raw(record, stripped_string2, parentheticals, evidence, "compliant:string2_raw")
        observations.append("compliant String1 Date String2 matched: String2 used as found without venue/location parsing")

    record.qualifier = _detect_qualifier([record.main_dir_name, record.main_dir_path])
    if record.qualifier:
        evidence.setdefault("qualifier", []).append(Candidate(record.qualifier, "path", 15))
    record.is_24_bit = _detect_24_bit([record.main_dir_name, record.main_dir_path] + list(_iter_group_media_files(group)))

    lookup_success = _apply_online_lookup_to_record(config, record, evidence, observations)

    # Final compliant-mode safety net: a String1 Date String2 DB miss/collision
    # is not unresolved. If the pattern matched, use String1 as the artist and
    # record only an observation.
    if not record.artist and matches:
        fallback_artist = compact_ws(matches[0].get("string1", ""))
        if fallback_artist:
            record.artist = fallback_artist
            observations.append(f"compliant artist not found in DB; using candidate artist: {fallback_artist}")
            evidence.setdefault("artist", []).append(Candidate(record.artist, f"compliant:path_part_unmatched_safety:{fallback_artist}", 64))

    if not record.artist and not (compliant_folder_name_show_match or compliant_mp3_year_show_match):
        unresolved_reasons.append("unable to identify artist")
    if compliant_dash_match:
        record.show_name = _build_compliant_dash_show_name(record)
    elif compliant_string_date_match:
        record.show_name = _build_compliant_string_date_show_name(record)
    elif record.artist and record.date:
        if lookup_success:
            record.show_name = _build_show_name(record)
        else:
            record.show_name = _build_compliant_string2_show_name(record)
    if not record.show_name:
        unresolved_reasons.append("unable to create show name")

    record.evidence = evidence
    record.conflicts = _unique_preserve(conflicts)
    record.observations = _unique_preserve(observations)
    record.show_in_conflict = bool(record.conflicts)
    _normalize_record_ascii_for_output(record)
    # In compliant mode, observations are written into the metadata record but are not unresolved reasons.
    # An artist DB miss for String1 is only an observation when String1 is used as the artist.
    # Do not return observations as unresolved reasons.
    return record, date_matches, _unique_preserve(unresolved_reasons + record.conflicts)


def _extract_metadata_for_group(config, group: dict, artist_matcher: Optional[ArtistMatcher]) -> Tuple[ShowMetadata, List[Dict[str, str]], List[str]]:
    if getattr(config, "compliant", False):
        return _extract_metadata_for_group_compliant(config, group, artist_matcher)

    record = ShowMetadata(
        group_number=group["group_number"],
        main_dir_name=group["main_dir_name"],
        main_dir_path=group["main_dir_path"],
        setlist_file=group.get("setlist_file", ""),
        music_file_count=group.get("music_file_count", 0),
        setlist_files=list(group.get("setlist_files", []) or ([group.get("setlist_file", "")] if group.get("setlist_file") else [])),
        music_dirs=list(group.get("music_dirs", []) or ([group.get("main_dir_path", "")] if group.get("main_dir_path") else [])),
        volume_label=(getattr(config, "current_volume_label", "") or "").strip(),
        flac_tag_samples=group.get("flac_tag_samples", []),
        flac_tag_artist_values=group.get("flac_tag_artist_values", []),
        flac_tag_album_values=group.get("flac_tag_album_values", []),
        flac_tag_albumartist_values=group.get("flac_tag_albumartist_values", []),
        flac_tag_date_values=group.get("flac_tag_date_values", []),
    )

    evidence: Dict[str, List[Candidate]] = {}
    conflicts: List[str] = []
    observations: List[str] = []
    unresolved_reasons: List[str] = []
    date_matches: List[Dict[str, str]] = []

    required_matches, optional_matches = _collect_pattern_matches_for_group(group)
    string_date_string_found = bool(required_matches)
    string_date_found = bool(optional_matches)
    pattern_matches = required_matches if required_matches else optional_matches

    if not string_date_string_found and not string_date_found:
        observations.append("unable to find String1 Date String2 or String1 Date in path")

    pattern_artist = ""
    dash_album_match: Optional[Dict[str, str]] = None
    dash_album_mode = False
    aggregate_album_name = compact_ws(group.get("aggregate_album_name", ""))
    if aggregate_album_name:
        observations.append(f"wrapper-suffixed related folders aggregated as album: {aggregate_album_name}")

    if config.current_slam:
        record.artist = config.current_slam.strip()
        evidence.setdefault("artist", []).append(Candidate(record.artist, "slam_override", 100))
        if not string_date_string_found:
            dash_album_match = _find_string_dash_string_match(group)
    else:
        _blank_unusable_artist_tags_for_noncompliant(record, observations)
        tag_artist = _resolve_artist_from_tags(record, artist_matcher, evidence, conflicts, observations)
        if tag_artist:
            record.artist = tag_artist

        if not string_date_string_found:
            if record.artist:
                dash_album_match = _find_string_dash_string_match(group)
            else:
                dash_artist, dash_album_match = _resolve_noncompliant_from_string_dash_string(
                    group,
                    artist_matcher,
                    evidence,
                    conflicts,
                    observations,
                )
                if dash_artist:
                    record.artist = dash_artist

        if not record.artist and not dash_album_match and pattern_matches:
            if _pattern_matches_have_abbreviation_candidate(pattern_matches):
                conflict_count_before_path_artist = len(conflicts)
                path_artist_before_abbreviation = _resolve_artist_from_path_before_abbreviation(
                    group,
                    pattern_matches,
                    artist_matcher,
                    evidence,
                    conflicts,
                )
                if path_artist_before_abbreviation:
                    record.artist = path_artist_before_abbreviation
                    observations.append(
                        "artist-no-space-date pattern found; using DB-backed artist found elsewhere in path before abbreviation lookup: "
                        f"{path_artist_before_abbreviation}"
                    )
                elif len(conflicts) == conflict_count_before_path_artist:
                    observations.append("artist-no-space-date pattern found; no DB-backed artist found elsewhere in path before abbreviation lookup")
            if not record.artist and len(conflicts) == 0:
                pattern_artist, _lookups = _resolve_artist_from_pattern_matches(pattern_matches, artist_matcher, evidence, conflicts)
                record.artist = pattern_artist
        if not record.artist and not dash_album_match and len(conflicts) == 0:
            if not string_date_string_found and string_date_found:
                observations.append("String1 Date retry match found in path")
            record.artist = _resolve_artist_from_subdirs(group, artist_matcher, evidence, conflicts, pattern_artist=pattern_artist)

    if aggregate_album_name and not dash_album_match and not string_date_string_found:
        if not record.artist and len(conflicts) == 0:
            record.artist = _resolve_artist_from_subdirs(group, artist_matcher, evidence, conflicts, pattern_artist=pattern_artist)
        if record.artist:
            dash_album_mode = True
            record.album_name = aggregate_album_name
            evidence.setdefault("album", []).append(Candidate(aggregate_album_name, "wrapper_part_aggregation", 72))
            observations.append("non-compliant wrapper-part aggregation matched: stripped folder base treated as album name; no date assigned")

    dash_string2_date = _string_dash_string_tail_date(dash_album_match)
    if dash_album_match and dash_string2_date:
        record.date = dash_string2_date
        date_matches.append({
            "raw": dash_album_match.get("string2", dash_string2_date),
            "normalized": dash_string2_date,
            "part": dash_album_match.get("part", ""),
            "part_path": dash_album_match.get("part_path", ""),
            "source": "string_dash_string_date_tail",
        })
        evidence.setdefault("date", []).append(Candidate(dash_string2_date, f"string_dash_string_date_tail:{dash_album_match.get('part_path', '')}", 68))
        observations.append("non-compliant String1 - String2 matched with date-like String2; String2 treated as date, not album name")
        dash_album_match = None
    elif dash_album_match:
        dash_album_mode = True
        _apply_string_dash_album_to_record(record, dash_album_match, evidence, f"string_dash_album:{dash_album_match.get('part_path', '')}")
        observations.append("non-compliant String1 - String2 matched: String2 treated as album name; no date assigned")

    tag_date_matches = _collect_tag_date_candidates(record)
    date_candidates: List[Dict[str, str]] = []
    chosen_string2_match: Optional[Dict[str, str]] = None

    if not dash_album_mode:
        if record.date:
            if pattern_matches:
                for match in pattern_matches:
                    if match.get("date_norm") == record.date and match.get("string2"):
                        chosen_string2_match = match
                        break
        elif pattern_matches:
            for match in pattern_matches:
                item = {
                    "raw": match["date_raw"],
                    "normalized": match["date_norm"],
                    "part": match["part"],
                    "part_path": match["part_path"],
                    "source": "path_pattern",
                }
                for key in ("date_order", "needs_setlist_confirmation"):
                    if match.get(key):
                        item[key] = match[key]
                date_candidates.append(item)
            date_candidates.extend(tag_date_matches)
            record.date, date_matches = _resolve_date_from_candidates_with_setlist_validation(group, date_candidates, evidence, conflicts, "date conflict across pattern/tag matches", observations)
            if record.date:
                for match in required_matches:
                    if match.get("date_norm") == record.date and match.get("string2"):
                        chosen_string2_match = match
                        break
        else:
            path_date_only = _collect_path_date_matches(group)
            if path_date_only:
                date_candidates = path_date_only + tag_date_matches
                record.date, date_matches = _resolve_date_from_candidates_with_setlist_validation(group, date_candidates, evidence, conflicts, "date conflict across path parts", observations)
            else:
                if tag_date_matches:
                    record.date, date_matches = _resolve_date_from_candidates_with_setlist_validation(group, tag_date_matches, evidence, conflicts, "date conflict across DATE tags", observations)
                if not record.date:
                    filename_date_matches = _collect_filename_date_matches(group)
                    if filename_date_matches:
                        record.date, date_matches = _resolve_date_from_candidates_with_setlist_validation(group, filename_date_matches, evidence, conflicts, "date conflict across music filenames", observations)
                    else:
                        setlist_date_matches = []
                        if not any("date conflict" in conflict.lower() for conflict in conflicts):
                            setlist_date_matches = _collect_setlist_date_matches(group)
                        if setlist_date_matches:
                            record.date, date_matches = _resolve_date_from_candidates(
                                setlist_date_matches,
                                evidence,
                                conflicts,
                                "date conflict across setlist files",
                            )
                            if record.date:
                                observations.append("date fallback used selected setlist file contents")
                            else:
                                observations.append("setlist date fallback found conflicting dates")
                        else:
                            observations.append("unable to identify date in path, DATE tags, music filenames, or setlist file")

        if chosen_string2_match:
            _apply_string2_to_record(record, chosen_string2_match, evidence)

        etree_success = False
        etree_lookup_key = None
        if not dash_album_mode and record.artist and record.date:
            etree_lookup_key = _online_lookup_key(record)
            etree_success = _apply_etree_lookup_to_record(config, record, evidence, observations)

        _apply_setlist_metadata_to_noncompliant_record(config, record, evidence, observations)

        if not dash_album_mode:
            etree_success, etree_lookup_key = _apply_setlistfm_only_after_etree_fallback(
                config, record, evidence, observations, etree_success, etree_lookup_key
            )

        if not record.artist:
            date_string3_artist, date_string3_date = _resolve_artist_from_date_string3(group, artist_matcher, evidence, conflicts)
            if date_string3_artist:
                record.artist = date_string3_artist
                if not record.date:
                    record.date = date_string3_date
                    date_matches.append({"raw": date_string3_date, "normalized": date_string3_date, "part": group["main_dir_path"], "source": "date_string3"})
    else:
        # Even album-style String1 - String2 folders may have selected setlist
        # files with explicit Artist:/Date:/Venue:/Location: labels. Apply the
        # same non-compliant source order: path, eTreeDB, setlist metadata,
        # setlist.fm. Each source fills blanks only and logs non-equivalent
        # disagreements without overwriting.
        etree_success = False
        etree_lookup_key = None
        if record.artist and record.date:
            etree_lookup_key = _online_lookup_key(record)
            etree_success = _apply_etree_lookup_to_record(config, record, evidence, observations)
        _apply_setlist_metadata_to_noncompliant_record(config, record, evidence, observations)
        if not record.date:
            setlist_date_matches = _collect_setlist_date_matches(group)
            if setlist_date_matches:
                record.date, date_matches = _resolve_date_from_candidates(
                    setlist_date_matches,
                    evidence,
                    conflicts,
                    "date conflict across setlist files",
                )
                if record.date:
                    observations.append("date fallback used selected setlist file contents in String1 - String2 album mode")
        etree_success, etree_lookup_key = _apply_setlistfm_only_after_etree_fallback(
            config, record, evidence, observations, etree_success, etree_lookup_key
        )

    record.qualifier = _detect_qualifier([record.main_dir_name, record.main_dir_path])
    if record.qualifier:
        evidence.setdefault("qualifier", []).append(Candidate(record.qualifier, "path", 15))
    record.is_24_bit = _detect_24_bit([record.main_dir_name, record.main_dir_path] + list(_iter_group_media_files(group)))

    lookup_success = False

    if not record.artist:
        unresolved_reasons.append("unable to identify artist")
    if dash_album_mode:
        if _dash_album_mode_should_use_structured_show_name(record, evidence):
            record.show_name = _build_show_name(record)
            observations.append("dash-album show name rebuilt from structured date/venue metadata to match generated setlist filename")
        else:
            record.show_name = _build_dash_album_show_name(record)
    else:
        if not record.date and not any("date conflict" in conflict.lower() for conflict in conflicts):
            record.date = "xxxx-xx-xx"
        if record.artist and record.date:
            record.show_name = _build_show_name(record)
    if not record.show_name:
        unresolved_reasons.append("unable to create show name")

    record.evidence = evidence
    record.conflicts = _unique_preserve(conflicts)
    record.observations = _unique_preserve(observations)
    record.show_in_conflict = bool(record.conflicts)
    _normalize_record_ascii_for_output(record)
    return record, date_matches, _unique_preserve(unresolved_reasons + record.conflicts)





def _representative_music_file_for_complete_log(group: dict) -> str:
    for key in ("music_sample_files", "music_files"):
        for path_name in group.get(key, []) or []:
            clean = os.path.normpath(str(path_name or ""))
            if clean:
                return clean
    for music_dir in group.get("music_dirs", []) or []:
        clean_dir = os.path.normpath(str(music_dir or ""))
        if not clean_dir or not os.path.isdir(clean_dir):
            continue
        try:
            names = sorted(os.listdir(clean_dir), key=lambda value: value.lower())
        except OSError:
            continue
        for name in names:
            candidate = os.path.join(clean_dir, name)
            if os.path.isfile(candidate):
                return os.path.normpath(candidate)
    return ""


def _physical_path_is_same_or_under(path_name: str, root_path: str) -> bool:
    if not path_name or not root_path:
        return False
    try:
        path_norm = os.path.normcase(os.path.abspath(os.path.normpath(path_name)))
        root_norm = os.path.normcase(os.path.abspath(os.path.normpath(root_path)))
        return os.path.commonpath([path_norm, root_norm]) == root_norm
    except (OSError, ValueError):
        return False


def _replace_complete_paths_log_with_inventory_samples(config, groups: Sequence[dict], source_root: str = "") -> None:
    """Replace this run's original-path samples with current inventory samples.

    Phase 1 records the original source path before Stage 3 can move or rename
    folders.  Copy/Delete Original and in-place Rename Compliantly therefore
    replace those source samples with representative paths from the final
    inventoried locations while preserving unrelated existing log entries.
    """
    log_path = getattr(getattr(config, "logs", None), "paths", None)
    complete_path = getattr(log_path, "complete_paths", "") if log_path is not None else ""
    if not complete_path:
        return
    samples = []
    seen = set()
    for group in groups or []:
        sample = _representative_music_file_for_complete_log(group)
        if not sample:
            continue
        sample = os.path.normpath(sample)
        key = os.path.normcase(sample)
        if key in seen:
            continue
        seen.add(key)
        samples.append(sample)
    if not samples:
        return
    try:
        with open(complete_path, "r", encoding="utf-8", errors="ignore") as infile:
            lines = infile.readlines()
    except OSError:
        lines = []
    header = []
    body_start = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("SEARCH_PATH:"):
            header.append(line)
            continue
        body_start = index
        break
    body = lines[body_start:] if body_start < len(lines) else []
    preserved = []
    for line in body:
        clean = line.strip()
        if not clean:
            continue
        key = os.path.normcase(os.path.normpath(clean))
        if key in seen:
            continue
        if source_root and _physical_path_is_same_or_under(clean, source_root):
            continue
        preserved.append(os.path.normpath(clean))
    if header and header[-1].strip():
        header.append("\n")
    with open(complete_path, "w", encoding="utf-8", newline="\n") as outfile:
        outfile.writelines(header)
        for line in preserved:
            outfile.write(line + "\n")
        for sample in samples:
            outfile.write(sample + "\n")

def _record_is_unidentified_for_mutation(record, unresolved_reasons: Sequence[str]) -> bool:
    """Return True when the show should not be copied, moved, renamed, or tagged.

    Inventory output can still include unresolved/original-path records, but any
    operation that mutates the source tree must wait until a show name exists.
    """
    if not compact_ws(getattr(record, "show_name", "")):
        return True
    lowered = {compact_ws(reason).lower() for reason in (unresolved_reasons or [])}
    return any("unable to create show name" in reason for reason in lowered)


def process_groups_for_search_path_v2(config, artist_matcher: Optional[ArtistMatcher]) -> List[ShowMetadata]:
    groups = _build_groups_from_search_path(config, config.current_search_path)
    console_print(config, f"Stage 2 complete: {config.current_search_path} | show groups prepared: {len(groups)}")
    console_print(config, f"Stage 3 starting: {config.current_search_path}")

    records: List[ShowMetadata] = []
    unresolved_paths: List[Tuple[str, str]] = []
    tag_in_place_during_inventory = bool(getattr(config, "tag_during_inventory", False))
    path_copy_destination = str(getattr(config, "current_path_copy_destination", "") or "").strip()
    path_copy_delete_destination = str(getattr(config, "current_path_copy_delete_destination", "") or "").strip()
    global_copy_delete_path = str(getattr(config, "tag_copy_and_delete_path", "") or "").strip()

    # A filled global Tag Copy and Delete Path overrides any per-path --$copy or
    # --$copy-delete directive.  Otherwise a per-path directive overrides the
    # global Tag Copy checkbox/destination for this one search path.
    tag_copy_and_delete_path = global_copy_delete_path or path_copy_delete_destination
    tag_copy_and_delete_enabled = bool(tag_copy_and_delete_path)
    if tag_copy_and_delete_enabled:
        config.tag_copy_and_delete_path = tag_copy_and_delete_path
        config.tag_copy_during_inventory = False
        config.tag_copy_destination = ""
        tag_copy_during_inventory = False
    elif path_copy_destination:
        config.tag_copy_and_delete_path = ""
        config.tag_copy_during_inventory = True
        config.tag_copy_destination = path_copy_destination
        tag_copy_during_inventory = True
    else:
        tag_copy_during_inventory = bool(getattr(config, "tag_copy_during_inventory", False))

    # A copy/copy-delete directive is an inventory-time tagging mode. Tag Copy
    # keeps inventory ownership with the original tree. Tag Copy/Delete Original
    # reads metadata from the original tree, transfers the show, then inventories
    # the transferred destination and tags that destination.
    tag_during_inventory = tag_in_place_during_inventory or tag_copy_during_inventory or tag_copy_and_delete_enabled
    rename_in_place_only = bool(getattr(config, "rename_compliantly", False)) and not tag_during_inventory
    tag_totals = {"groups": 0, "tagged": 0, "skipped": 0, "errors": 0, "comma_item_folders": [], "comma_line_folders": []}
    copy_delete_inventory_groups: List[dict] = []
    renamed_inventory_groups: List[dict] = []
    if tag_during_inventory:
        tag_mode = "copy-and-delete" if tag_copy_and_delete_enabled else ("copy" if tag_copy_during_inventory else "in-place")
        tag_destination = tag_copy_and_delete_path if tag_copy_and_delete_enabled else (getattr(config, "tag_copy_destination", "") if tag_copy_during_inventory else "")
        config.logs.tag(
            "TAG_DURING_INVENTORY: mode=%s | convert shn=%s | rename compliantly=%s | copy destination=%s",
            tag_mode,
            "yes" if bool(getattr(config, "convert_shn", False)) else "no",
            "yes" if bool(getattr(config, "rename_compliantly", False)) else "no",
            tag_destination,
        )
    else:
        config.logs.tag("TAG_DURING_INVENTORY: disabled")
    if rename_in_place_only:
        config.logs.tag("RENAME_COMPLIANTLY: enabled | mode=in-place | tagging=disabled")
    if tag_copy_and_delete_enabled:
        config.logs.tag("TAG_COPY_AND_DELETE: enabled | destination=%s", tag_copy_and_delete_path)

    for group_number, group in enumerate(groups, start=1):
        throttle_point(config)
        group["group_number"] = group_number
        record, date_matches, unresolved_reasons = _extract_metadata_for_group(config, group, artist_matcher)
        if not record.show_name and "unable to create show name" not in unresolved_reasons:
            unresolved_reasons.append("unable to create show name")
        if not record.artist and "unable to identify artist" not in unresolved_reasons:
            unresolved_reasons.append("unable to identify artist")
        tag_group = group
        tag_record = record
        inventory_group = group
        inventory_record = record
        tag_group_ready = True
        unidentified_for_mutation = _record_is_unidentified_for_mutation(record, unresolved_reasons)
        if unidentified_for_mutation and (tag_during_inventory or tag_copy_and_delete_enabled or bool(getattr(config, "rename_compliantly", False))):
            if tag_copy_and_delete_enabled:
                config.logs.tag(
                    "TAG_COPY_AND_DELETE_SKIP: %s | show unidentified; leaving original folder untouched",
                    record.main_dir_path,
                )
            if tag_during_inventory:
                tag_totals["groups"] += 1
                tag_totals["skipped"] += 1
                config.logs.tag(
                    "TAG_SKIP: %s | show unidentified; leaving original folder untouched",
                    record.main_dir_path,
                )
            elif bool(getattr(config, "rename_compliantly", False)):
                config.logs.tag(
                    "RENAME_COMPLIANTLY_SKIP: %s | show unidentified; leaving original folder untouched",
                    record.main_dir_path,
                )
            tag_group_ready = False
        elif tag_during_inventory or tag_copy_and_delete_enabled or rename_in_place_only:
            try:
                from tlo_tag_lib import prepare_inventory_copy_delete_target, prepare_inventory_tagging_target

                def _tag_prepare_emit(text: str) -> None:
                    line = str(text or "").rstrip("\r\n")
                    if line:
                        config.logs.tag("%s", line)

                if tag_copy_and_delete_enabled:
                    tag_group, tag_record = prepare_inventory_copy_delete_target(config, tag_group, tag_record, emit=_tag_prepare_emit)
                    inventory_group = tag_group
                    inventory_record = tag_record
                if tag_during_inventory or rename_in_place_only:
                    tag_group, tag_record = prepare_inventory_tagging_target(config, tag_group, tag_record, emit=_tag_prepare_emit)
                    if not tag_copy_and_delete_enabled:
                        inventory_group = tag_group
                        inventory_record = tag_record
                    if rename_in_place_only:
                        renamed_inventory_groups.append(inventory_group)
            except Exception as exc:
                config.logs.tag("ERROR_TAG_TARGET_PREP: %s | rename/tag/copy-delete target preparation failed: %s", record.main_dir_path, exc)
                tag_group_ready = False
                if tag_copy_and_delete_enabled:
                    config.logs.conflicts("COPY_DELETE_FAILED_NOT_INVENTORIED: %s | %s", record.main_dir_path, exc)
                    continue

        _log_group(config, inventory_group, group_number)
        meta_log_entry = _format_show_metadata_log_entry(inventory_record, date_matches)
        _log_show_metadata(config, inventory_record, date_matches)
        if tag_copy_and_delete_enabled and tag_group_ready and not unidentified_for_mutation:
            copy_delete_inventory_groups.append(inventory_group)
        if tag_during_inventory and tag_group_ready and not unidentified_for_mutation:
            try:
                from tlo_tag_lib import tag_group_with_record, merge_tag_stats, emit_tag_fallback_summary

                def _tag_log_emit(text: str) -> None:
                    line = str(text or "").rstrip("\r\n")
                    if line:
                        config.logs.tag("%s", line)

                subtotal = tag_group_with_record(
                    config,
                    tag_group,
                    tag_record,
                    emit=_tag_log_emit,
                    allow_unknown_metadata=True,
                    fallback_to_filenames_on_track_problem=True,
                    metadata_problems=unresolved_reasons,
                    meta_log_entry=meta_log_entry,
                )
                merge_tag_stats(tag_totals, subtotal)
            except Exception as exc:
                tag_totals["groups"] += 1
                tag_totals["errors"] += 1
                config.logs.tag("ERROR_TAGGING: %s | inventory-time tagging failed: %s", record.main_dir_path, exc)
        elif tag_during_inventory and not tag_group_ready and not unidentified_for_mutation:
            tag_totals["groups"] += 1
            tag_totals["errors"] += 1
        if unresolved_reasons:
            unresolved_paths.append((inventory_record.main_dir_path, "; ".join(unresolved_reasons)))
            config.logs.conflicts("UNRESOLVED_MAIN_DIR_PATH: %s | %s", inventory_record.main_dir_path, "; ".join(unresolved_reasons))
        records.append(inventory_record)

    if tag_copy_and_delete_enabled and copy_delete_inventory_groups:
        _replace_complete_paths_log_with_inventory_samples(config, copy_delete_inventory_groups, config.current_search_path)
    elif renamed_inventory_groups:
        _replace_complete_paths_log_with_inventory_samples(config, renamed_inventory_groups, config.current_search_path)

    if tag_during_inventory:
        from tlo_tag_lib import emit_tag_fallback_summary, emit_tag_problem_summary

        def _tag_summary_emit(text: str) -> None:
            line = str(text or "").rstrip("\r\n")
            if line:
                config.logs.tag("%s", line)

        emit_tag_fallback_summary(tag_totals, _tag_summary_emit)
        emit_tag_problem_summary(config, _tag_summary_emit)
        config.logs.tag(
            "TAG_SUMMARY: folders=%s tagged_files=%s skipped_folders=%s file_errors=%s",
            tag_totals["groups"],
            tag_totals["tagged"],
            tag_totals["skipped"],
            tag_totals["errors"],
        )

    if unresolved_paths:
        config.logs.conflicts("UNRESOLVED_PATH_COUNT: %s", len(unresolved_paths))
        for path_name, reason in unresolved_paths:
            config.logs.conflicts("UNRESOLVED_PATH: %s | %s", path_name, reason)

    console_print(config, f"Stage 3 complete: {config.current_search_path} | show groups processed: {len(records)}")
    return records
