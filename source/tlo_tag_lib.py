"""Tagging engine for standalone Tag runs and inventory-time tag/copy/move workflows."""

__version__ = "v319"
# TLO-GI package version: v319
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.

import os
import re
import shutil
import subprocess
import copy
import unicodedata
import sys
import traceback
import html
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from mutagen import File as MutagenFile
from console_output_lib import console_emit

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TIT2, TPE1, TRCK
    from mutagen.mp4 import MP4
except Exception:  # pragma: no cover - optional fallback imports vary by mutagen build
    FLAC = None
    ID3 = None
    ID3NoHeaderError = Exception
    TALB = TIT2 = TPE1 = TRCK = None
    MP4 = None

from inventory_parser_lib import Config
from tlo_path_inputs import strip_optional_quotes, normalize_platform_input_path, resolve_tlo_home as resolve_tlo_home_common
from logging_lib import ARTIST_SQLITE_DB_FILENAME, TLO_DBS_DIRNAME, VENUE_REFERENCE_DB_FILENAME, setup_logging
from tlo_artist_db import load_artist_matcher
from tlo_audio_tags import collect_group_flac_tag_info
from tlo_db_validation import validate_required_databases
from tlo_media_rules import VIDEO_EXTENSIONS
from tlo_phase23_v2 import (
    _build_groups_from_search_path,
    _extract_metadata_for_group,
    _unique_paths_preserve_order,
    _volume_part_parent_info,
    _wrapper_release_aggregation_info,
)
from tlo_runtime_control import clear_cancel_request, is_cancel_requested, throttle_point
from tlo_etree_lookup import ETreeDBError, lookup_setlists_by_performance, lookup_setlists_for_performance
from initial_dir_walk_lib import initial_dir_walk
from tlo_setlist_file_selection import find_setlist_files_for_music_dir
from tlo_text_utils import compact_ws, setlist_text_requests_generated_from_music_files, standard_ascii_text
from tlo_postprocess import _candidate_setlist_name, _setlist_base_from_record
from tlo_wrapper_rules import is_wrapper_part_folder_name


TAGGER_TITLE = "Traders Little Helper™ Tagger App"
READY_FOR_XFER_DIRNAME = "readyForXfer"

# Audio formats with common metadata containers.  SHN/SHNF are intentionally
# omitted because they are normally not taggable through mutagen.
TAGGABLE_AUDIO_EXTENSIONS = {
    ".flac",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".oga",
    ".opus",
    ".aiff",
    ".aif",
    ".ape",
    ".wv",
    ".alac",
}


UNWANTED_TOTAL_DISC_TAG_KEYS = {"tracktotal", "discnumber", "disctotal"}
UNWANTED_TOTAL_DISC_ID3_TXXX_DESCS = {"TRACKTOTAL", "DISCNUMBER", "DISCTOTAL"}



TAG_TITLE_PRINTABLE_TRANSLATION = str.maketrans({
    "\u00a0": " ",   # no-break space
    "\u1680": " ",
    "\u2000": " ",
    "\u2001": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u2004": " ",
    "\u2005": " ",
    "\u2006": " ",
    "\u2007": " ",
    "\u2008": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
    "\u205f": " ",
    "\u3000": " ",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2212": "-",
    "\ufe58": "-",
    "\ufe63": "-",
    "\uff0d": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u2032": "'",
    "\u2035": "'",
    "\u0060": "'",
    "\u00b4": "'",
    "\uff07": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2033": '"',
    "\u2036": '"',
    "\uff02": '"',
    "\u2026": "...",
    "\u00ad": "",
    "\ufeff": "",
    "\ufffd": "",
})


def normalize_tag_title_printable(title: str) -> str:
    """Return a tag title containing regular printable ASCII characters only."""
    # Keep the v268 punctuation/control cleanup behavior, but v269 also forces
    # accented and other non-ASCII characters to standard ASCII before any audio
    # metadata is written.
    value = unicodedata.normalize("NFKC", str(title or ""))
    value = value.translate(TAG_TITLE_PRINTABLE_TRANSLATION)
    return standard_ascii_text(value)

def _delete_mapping_key_case_insensitive(mapping, key_name: str) -> None:
    target = str(key_name).lower()
    for existing in list(getattr(mapping, "keys", lambda: [])()):
        if str(existing).lower() == target:
            try:
                del mapping[existing]
            except Exception:
                try:
                    mapping.pop(existing, None)
                except Exception:
                    pass


def _clear_total_disc_easy_tags(audio) -> None:
    """Remove track-total/disc tags from mutagen Easy-style mappings.

    TLO writes only Artist, Album, Title and TrackNo.  Older tags such as
    TRACKTOTAL, DISCNUMBER and DISCTOTAL can mislead players, so clear them
    every time tagging writes the file.  Mutagen exposes these with lowercase
    Easy keys for most containers, while Vorbis/FLAC comments may preserve
    arbitrary case.
    """
    for key in UNWANTED_TOTAL_DISC_TAG_KEYS:
        _delete_mapping_key_case_insensitive(audio, key)


def _clear_total_disc_id3_tags(tags) -> None:
    """Remove ID3 disc/total fields corresponding to requested cleared tags."""
    try:
        tags.delall("TPOS")  # DISCNUMBER / disc position
    except Exception:
        pass
    for frame_key in list(getattr(tags, "keys", lambda: [])()):
        frame = tags.get(frame_key)
        desc = str(getattr(frame, "desc", "") or "").upper()
        frame_id = str(getattr(frame, "FrameID", "") or "").upper()
        if frame_id == "TXXX" and desc in UNWANTED_TOTAL_DISC_ID3_TXXX_DESCS:
            try:
                tags.delall(frame_key)
            except Exception:
                try:
                    del tags[frame_key]
                except Exception:
                    pass


def _clear_total_disc_mp4_tags(audio) -> None:
    # MP4 has no literal TRACKTOTAL key; track total is the second value in trkn.
    # Preserve track number with total=0 in _write_mp4_tags and remove disc info.
    for key in ("disk", "----:com.apple.iTunes:TRACKTOTAL", "----:com.apple.iTunes:DISCNUMBER", "----:com.apple.iTunes:DISCTOTAL"):
        try:
            if key in audio:
                del audio[key]
        except Exception:
            pass

SHN_AUDIO_EXTENSIONS = {".shn", ".shnf"}
AUDIO_EXTENSIONS_FOR_COUNTING = TAGGABLE_AUDIO_EXTENSIONS | SHN_AUDIO_EXTENSIONS
AUDIO_FILENAME_EXT_RE = re.compile(
    r"\.(?:flac|mp3|wav|m4a|aac|ogg|oga|opus|aiff?|ape|wv|alac|shn|shnf)$",
    re.IGNORECASE,
)
SAMPLE_AUDIO_STEM_RE = re.compile(r"(?i)(?:^|[ _.-])sample(?:[ _.-]*\d*)?$")

PRUNE_DIR_NAMES = {"$recycle.bin", "system volume information", "__pycache__"}
TRACK_SECTION_RE = re.compile(r"(?i)^\s*(?:the\s+)?(?:(?:tracks?|songs?|contents?)\s*:?|track\s*list\s*:?|set\s*list\s*:?)\s*$")
DISC_OR_SET_RE = re.compile(
    r"(?ix)^\s*"
    r"[-–—_=*~#\[\]{}()<>/\\| .:]*"
    r"(?:"
    r"(?:cd|disc|disk|set)\s*(?:\#\s*)?(?:0*\d+|[ivx]{1,5}|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:\s+(?:cd|disc|disk|set)\s*(?:\#\s*)?(?:0*\d+|[ivx]{1,5}|one|two|three|four|five|six|seven|eight|nine|ten))*"
    r"|\d+(?:st|nd|rd|th)\s+set"
    r"|(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s+set"
    r"|set\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)"
    r"|encore"
    r")"
    r"[-–—_=*~#\[\]{}()<>/\\| .:]*\s*$"
)
DISC_OR_SET_HEADING_RE = re.compile(
    r"(?ix)^\s*"
    r"(?:cd|disc|disk|set)\s*"
    r"(?:0*\d{1,2}|[ivx]{1,5}|one|two|three|four|five|six|seven|eight|nine|ten)\b"
    r"(?!\s*(?:t|track)\b)"
    r"(?=.*(?:\bset\b|\bdisc\b|\bdisk\b|\bcd\b|\d{1,2}:\d{2}|\d{1,3}\s*(?:min|mins|minutes?)\b))"
    r".*$"
)
DISC_OR_SET_SHOW_HEADING_RE = re.compile(
    r"(?ix)^\s*"
    r"(?:cd|disc|disk|set)\s*"
    r"(?:0*\d+|[ivx]{1,5}|one|two|three|four|five|six|seven|eight|nine|ten)\b"
    r"(?!\s*(?:t|track)\b)"
    r"(?:\s*[/\-–—:]\s*(?:early|late|first|second|third|matinee|evening|afternoon|night)\s+show)?"
    r"(?:\s*[-–—:]?\s*\d{1,2}:\d{2})?"
    r"\s*:?\s*$"
)


def _is_disc_or_set_heading(line: str) -> bool:
    raw = str(line or "").strip()
    return bool(DISC_OR_SET_RE.match(raw) or DISC_OR_SET_HEADING_RE.match(raw) or DISC_OR_SET_SHOW_HEADING_RE.match(raw))


SHOW_SECTION_RE = re.compile(r"(?i)^\s*(?:early|late|first|second|third|matinee|evening|afternoon|night)\s+show\b.*$")

TRACK_LIST_TERMINATOR_RE = re.compile(
    r"(?i)^\s*(?:note(?:s)?\b|note\s+to\b|comments?\b|collectors?\b|"
    r"lineage\b|source\b|transfer\b|taper\b|recording\s+info\b|"
    r"technical\s+notes?\b|editing\s+by\b|thanks?\b|checksum\b|patch\b)"
)
FILE_HASH_LINE_RE = re.compile(
    r"(?i)^\s*"
    r"[\w .,'+()\[\]{}-]+\.(?:flac|mp3|wav|m4a|aac|ogg|oga|opus|aiff?|ape|wv|alac|shn|shnf)"
    r"\s*[:=]\s*[a-f0-9]{32,64}\s*$"
)
HASH_LINE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"[a-f0-9]{32,64}(?:\s+\S.*)?|"
    r"[\w .,'+()\[\]{}-]+\.(?:flac|mp3|wav|m4a|aac|ogg|oga|opus|aiff?|ape|wv|alac|shn|shnf)"
    r"\s*[:=]\s*[a-f0-9]{32,64}"
    r")\s*$"
)
CHECKSUM_SECTION_RE = re.compile(r"(?i)^\s*(?:checksums?|fingerprints?|ffp|md5|st5|sfv|shntool|verify|verification|aucdtect|trader'?s\s+little\s+helper)\b")
AUCDTECT_RESULT_LINE_RE = re.compile(
    r"(?i)^\s*"
    r"(?:d\d{1,2}t)?\d{1,3}\s+"
    r".+?\.(?:wav|flac|shn|aiff?|ape|wv|mp3|m4a)"
    r"\s*:\s*track\s+looks\s+like\s+CDDA\s+with\s+probability\s+\d{1,3}%\.?\s*$"
)
SHNTOOL_LENGTH_ROW_RE = re.compile(
    r"(?i)^\s*\d{1,3}:\d{2}(?:\.\d{2})?\s+.+?\.(?:flac|mp3|wav|m4a|aac|ogg|oga|opus|aiff?|ape|wv|alac|shn|shnf)(?:\s|$)"
)
EXTINF_TRACK_RE = re.compile(r"(?i)^\s*#EXTINF\s*:\s*[^,]*,\s*(?:\[(?P<num>\d{1,3})\]\s*)?(?P<title>\S.*)$")
BRACKETED_TRACK_RE = re.compile(r"(?i)^\s*(?:(?:cd|disc|disk|d|set|s)\s*\d{1,2}\s*\\?[/_. -]*)?\[(?P<num>\d{1,3})\]\s*(?P<title>\S.*)$")
DISC_DASH_TRACK_RE = re.compile(r"(?i)^\s*(?P<disc>\d{1,2})\s*[-]\s*(?P<num>\d{1,3})\s+(?P<title>\S.*)$")
SIDE_LETTER_TRACK_RE = re.compile(r"(?i)^\s*(?P<side>[A-H])\s*(?P<num>\d{1,3})\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$")
DATE_WORD_LIKE_RE = re.compile(r"(?i)^\s*\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\.?\s+(?:\d{2}|(?:19|20)\d{2})\b")
COMMA_ITEM_WORD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9&\'./+()\[\]{}>:-]*(?:\s+[A-Za-z0-9][A-Za-z0-9&\'./+()\[\]{}>:-]*){0,7}$")
DURATION_STAMP_RE_PART = r"[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?"
TIME_PREFIX_RE = re.compile(
    rf"^\s*(?:\[{DURATION_STAMP_RE_PART}\]|\({DURATION_STAMP_RE_PART}\)|{DURATION_STAMP_RE_PART})(?:\s+|\s*[-–—:;,.]+\s*|$)"
)
TIME_SUFFIX_RE = re.compile(
    rf"(?:\s*[-–—:;,.]+\s*|\s*)(?:\[{DURATION_STAMP_RE_PART}\]|\({DURATION_STAMP_RE_PART}\)|{DURATION_STAMP_RE_PART})\s*$"
)
DATE_LIKE_RE = re.compile(r"^\s*(?:(?:19|20)\d{2}[-./ ]\d{1,2}[-./ ]\d{1,2}|\d{1,2}[-./ ]\d{1,2}[-./ ](?:\d{2}|(?:19|20)\d{2}))\s*$")
DURATION_ONLY_RE = re.compile(rf"^\s*{DURATION_STAMP_RE_PART}\s*$")
SAMPLE_RATE_OR_BIT_DEPTH_RE = re.compile(
    r"(?ix)^\s*"
    r"(?:"
    r"\d{1,3}(?:\.\d+)?\s*(?:k?hz|bit|bits?)(?:\b|\d)"
    r"|"
    r"\d{1,3}\s*/\s*\d{1,3}(?:\.\d+)?\s*(?:k?hz|bit|bits?)(?:\b|\d)"
    r")"
)

TRACK_PATTERNS = [
    # s2t01 Song, s2t01 - Song, cd1t01 Song, d01t01: Song, disc 1 track 01 Song.
    re.compile(r"(?i)^\s*(?:(?:s|set)\s*\d{1,2}|(?:cd|d|disc|disk)\s*\d{1,2})\s*(?:t|track)\s*(?P<num>\d{1,3})\s*(?:[.)\-:]\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^\s*(?:(?:s|set)\s*\d{1,2}|(?:cd|d|disc|disk)\s*\d{1,2})\s*(?:t|track)\s*(?P<num>\d{1,3})(?P<title>[A-Za-z(][^\r\n]*)$"),
    # t01 - Song, trk01 - Song, track01 - Song, Track 01 - Song, 01. Song, 1)Song, 1 - Song, 01: Song
    re.compile(r"(?i)^\s*(?:t|trk|track)\s*(?P<num>\d{1,3})\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^\s*(?:track\s*)?(?P<num>\d{1,3})\s*(?:[.)\-:]\s*|\s+)(?P<title>\S.*)$"),
    # 01[08:23] Song or 01 [08:23] Song
    re.compile(r"(?i)^\s*(?:track\s*)?(?P<num>\d{1,3})\s*(?P<title>(?:\[[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\]\s*)+\S.*)$"),
    # Compact form requested by the user: 1Name / 01Name.  Keep this last and
    # require an alphabetic first title character so dates and hashes do not match.
    re.compile(r"(?i)^\s*(?P<num>\d{1,2})(?P<title>[A-Za-z][^\r\n]*)$"),
]


class TaggerError(RuntimeError):
    pass


def _emit(emit: Optional[Callable[[str], None]], text: str) -> None:
    line = str(text or "")
    if emit is None:
        console_emit(line)
        return
    emit(line if line.endswith("\n") else line + "\n")


def _validate_existing_directory(path_name: str, label: str) -> str:
    original = strip_optional_quotes(path_name).strip()
    cleaned = normalize_platform_input_path(original)
    if not cleaned:
        raise TaggerError(f"{label} is blank.")
    if not os.path.isabs(cleaned):
        raise TaggerError(f"{label} must be a fully qualified directory path: {cleaned}")
    if not os.path.exists(cleaned):
        raise TaggerError(f"{label} does not exist: {cleaned}")
    if not os.path.isdir(cleaned):
        raise TaggerError(f"{label} exists but is not a directory: {cleaned}")
    return os.path.normpath(cleaned)


def resolve_tlo_home(tlo_home: str = "", my_tlo: str = "") -> str:
    try:
        return resolve_tlo_home_common(tlo_home=tlo_home, my_tlo=my_tlo, error_type=TaggerError)
    except TaggerError:
        raise


def resolve_tagging_path(tlo_home: str, tag_path: str = "") -> str:
    override = strip_optional_quotes(tag_path).strip()
    if override:
        return _validate_existing_directory(override, "tagPath")
    return os.path.normpath(os.path.join(tlo_home, READY_FOR_XFER_DIRNAME))


def default_tagging_path(tlo_home: str = "", my_tlo: str = "", tag_path: str = "") -> str:
    resolved_home = resolve_tlo_home(tlo_home=tlo_home, my_tlo=my_tlo)
    override = strip_optional_quotes(tag_path).strip()
    if override:
        return normalize_platform_input_path(override)
    return os.path.normpath(os.path.join(resolved_home, READY_FOR_XFER_DIRNAME))


def build_tagger_config(
    tlo_home: str = "",
    my_tlo: str = "",
    compliant: bool = False,
    etree_lookup: bool = False,
    debug: bool = False,
    tag_in_place: bool = True,
    tag_copy: bool = False,
    tag_copy_destination: str = "",
    rename_compliantly: bool = False,
    convert_shn: bool = False,
) -> Config:
    resolved_home = resolve_tlo_home(tlo_home=tlo_home, my_tlo=my_tlo)
    tag_copy_enabled = bool(tag_copy)
    tag_in_place_enabled = bool(tag_in_place) and not tag_copy_enabled
    normalized_destination = ""
    if tag_copy_enabled:
        normalized_destination = normalize_platform_input_path(strip_optional_quotes(str(tag_copy_destination or "")).strip())
        if not normalized_destination or not os.path.isabs(normalized_destination) or not os.path.isdir(normalized_destination):
            raise TaggerError(f"Tag Copy destination is not a valid existing full path: {tag_copy_destination}")
        normalized_destination = os.path.normpath(normalized_destination)
    config = Config(
        debug=bool(debug),
        silent=False,
        TLOHome=resolved_home,
        search_path_override="",
        search_path_slam_override="",
        compliant=bool(compliant),
        tag_during_inventory=tag_in_place_enabled,
        tag_copy_during_inventory=tag_copy_enabled,
        tag_copy_destination=normalized_destination,
        rename_compliantly=bool(rename_compliantly),
        etree_lookup=bool(etree_lookup),
        setlistfm_lookup=False,
        performance_mode="gentle",
        max_workers=1,
        convert_shn=bool(convert_shn),
    )
    config.tlo_dbs_dir = os.path.join(config.TLOHome, TLO_DBS_DIRNAME)
    config.artist_sqlite_db_file = os.path.join(config.tlo_dbs_dir, ARTIST_SQLITE_DB_FILENAME)
    config.venue_reference_db_file = os.path.join(config.tlo_dbs_dir, VENUE_REFERENCE_DB_FILENAME)
    return config


def _should_prune_dir(dir_name: str) -> bool:
    lowered = str(dir_name or "").strip().lower()
    return lowered in PRUNE_DIR_NAMES or lowered.endswith("-ignoredir")


def _is_audio_file(path_name: str) -> bool:
    if not path_name or not os.path.isfile(path_name):
        return False
    return os.path.splitext(path_name)[1].lower() in AUDIO_EXTENSIONS_FOR_COUNTING


def _is_sample_audio_file(path_name: str) -> bool:
    """Return True for short torrent sample audio files that are not tracks."""
    if not path_name:
        return False
    stem, ext = os.path.splitext(os.path.basename(path_name))
    if ext.lower() not in AUDIO_EXTENSIONS_FOR_COUNTING:
        return False
    return bool(SAMPLE_AUDIO_STEM_RE.search(stem.strip()))


def _is_taggable_audio_file(path_name: str) -> bool:
    if not path_name or not os.path.isfile(path_name):
        return False
    return os.path.splitext(path_name)[1].lower() in TAGGABLE_AUDIO_EXTENSIONS


def _natural_sort_key(path_name: str) -> List[object]:
    name = os.path.basename(path_name or "")
    parts = re.split(r"(\d+)", name.casefold())
    key: List[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return key


def _walk_tagging_path(config: Config, tagging_path: str) -> Tuple[List[str], Dict[str, List[str]]]:
    all_paths: List[str] = []
    media_by_dir: Dict[str, List[str]] = {}
    root = os.path.normpath(tagging_path)

    for current_dir, dir_names, file_names in os.walk(root):
        throttle_point(config)
        dir_names[:] = sorted([d for d in dir_names if not _should_prune_dir(d)], key=lambda value: value.lower())
        current_dir = os.path.normpath(current_dir)
        all_paths.append(current_dir)
        for dir_name in dir_names:
            all_paths.append(os.path.normpath(os.path.join(current_dir, dir_name)))
        for file_name in sorted(file_names, key=lambda value: value.lower()):
            path_name = os.path.normpath(os.path.join(current_dir, file_name))
            all_paths.append(path_name)
            if _is_audio_file(path_name):
                media_by_dir.setdefault(current_dir, []).append(path_name)

    for key in list(media_by_dir.keys()):
        media_by_dir[key] = sorted(media_by_dir[key], key=_natural_sort_key)
    return _unique_paths_preserve_order(all_paths), media_by_dir


def _group_music_dirs(config: Config, all_logged_paths: List[str], media_by_dir: Dict[str, List[str]]) -> List[dict]:
    """Legacy tagger grouping helper retained for compatibility tests.

    The live tagger path now uses ``_groups_from_inventory_discovery`` so that
    music-file discovery, setlist discovery, wrapper aggregation, and metadata
    inputs are the same as inventory.
    """
    buckets: Dict[str, dict] = {}
    volume_parent_info = _volume_part_parent_info([{"music_dir": music_dir} for music_dir in media_by_dir.keys()])
    if getattr(config, "compliant", False):
        for music_dir, music_files in sorted(media_by_dir.items(), key=lambda item: item[0].lower()):
            key = f"single::{os.path.normcase(os.path.normpath(music_dir))}"
            buckets[key] = {
                "main_dir_path": os.path.normpath(music_dir),
                "main_dir_name": os.path.basename(os.path.normpath(music_dir)),
                "music_dirs": [os.path.normpath(music_dir)],
                "music_files": sorted(music_files, key=_natural_sort_key),
                "aggregate_album_name": "",
                "aggregate_release_base": "",
                "aggregation_reason": "",
            }
    else:
        for music_dir, music_files in sorted(media_by_dir.items(), key=lambda item: item[0].lower()):
            throttle_point(config)
            music_dir = os.path.normpath(music_dir)
            info = _wrapper_release_aggregation_info(music_dir, volume_parent_info)
            if info:
                key = info["aggregation_key"]
                bucket = buckets.setdefault(key, {
                    "main_dir_path": os.path.normpath(info["main_dir_path"]),
                    "main_dir_name": info["main_dir_name"],
                    "music_dirs": [],
                    "music_files": [],
                    "aggregate_album_name": info.get("aggregate_album_name", ""),
                    "aggregate_release_base": info.get("aggregate_release_base", ""),
                    "aggregation_reason": info.get("aggregation_reason", ""),
                })
            else:
                key = f"single::{os.path.normcase(music_dir)}"
                bucket = buckets.setdefault(key, {
                    "main_dir_path": music_dir,
                    "main_dir_name": os.path.basename(music_dir),
                    "music_dirs": [],
                    "music_files": [],
                    "aggregate_album_name": "",
                    "aggregate_release_base": "",
                    "aggregation_reason": "",
                })
            bucket["music_dirs"].append(music_dir)
            bucket["music_files"].extend(music_files)

    groups: List[dict] = []
    for _key, bucket in sorted(buckets.items(), key=lambda item: (item[1]["main_dir_path"].lower(), item[0].lower())):
        music_dirs = _unique_paths_preserve_order(bucket.get("music_dirs", []))
        music_files = _unique_paths_preserve_order(sorted(bucket.get("music_files", []), key=_natural_sort_key))
        main_dir_path = os.path.normpath(bucket["main_dir_path"])
        setlist_files: List[str] = []
        for music_dir in music_dirs:
            setlist_files.extend(find_setlist_files_for_music_dir(all_logged_paths, music_dir, main_dir_path))
        setlist_files = _unique_paths_preserve_order(setlist_files)
        chosen = setlist_files[0] if setlist_files else ""
        item = {
            "main_dir_path": main_dir_path,
            "main_dir_name": bucket["main_dir_name"],
            "music_dirs": music_dirs,
            "music_files": music_files,
            "txt_files": setlist_files,
            "setlist_files": setlist_files,
            "setlist_file": chosen,
            "aggregate_album_name": bucket.get("aggregate_album_name", ""),
            "aggregate_release_base": bucket.get("aggregate_release_base", ""),
            "aggregation_reason": bucket.get("aggregation_reason", ""),
            "music_file_count": len(music_files),
        }
        if getattr(config, "compliant", False):
            item.update({
                "flac_tag_samples": [],
                "flac_tag_artist_values": [],
                "flac_tag_album_values": [],
                "flac_tag_albumartist_values": [],
                "flac_tag_date_values": [],
            })
        else:
            item.update(collect_group_flac_tag_info(item["music_files"]))
        groups.append(item)
    return groups


def _groups_from_inventory_discovery(config: Config, tagging_path: str) -> List[dict]:
    """Discover taggable groups with the same Stage 1/2 logic as inventory."""
    config.current_search_path = os.path.normpath(tagging_path)
    config.current_search_index = 1
    config.current_slam = ""
    config.current_volume_label = ""
    config.current_volume_key = ""
    config.current_log_token = "T"
    if getattr(getattr(config, "logs", None), "current_log_token", "") != "T":
        config.logs.start_search_path(config.current_search_path, config.current_search_index, log_token=config.current_log_token)
    initial_dir_walk(config, config.current_search_path)
    return _build_groups_from_search_path(config, config.current_search_path)


def _read_text(path_name: str) -> str:
    with open(path_name, "rb") as infile:
        raw = infile.read()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding, errors="replace")
            if sum(ch.isalpha() for ch in text) >= 2:
                return text
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")


def _clean_track_title(title: str) -> str:
    value = html.unescape(str(title or "")).strip()
    value = TIME_PREFIX_RE.sub("", value).strip()
    # Drop duration-plus-note tails such as "12:20 (end cut)" before the
    # simpler bare-duration suffix pass.  These are timing/condition notes,
    # not part of the song title.
    value = re.sub(rf"\s+{DURATION_STAMP_RE_PART}\s+\([^)]{{1,80}}\)\s*$", "", value).strip()
    value = TIME_SUFFIX_RE.sub("", value).strip()
    # Drop inline duration notes and trailing tape-flip annotations from track
    # rows such as "The Dance/ [12:25] tape flip".
    value = re.sub(rf"\s*(?:\[{DURATION_STAMP_RE_PART}\]|\({DURATION_STAMP_RE_PART}\))\s*(?=(?:tape\s+flip)\b)", " ", value, flags=re.I).strip()
    value = re.sub(r"(?i)\s+tape\s+flip\s*$", "", value).strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" \t-–—:.;/\\")
    # Drop list-position prefixes that survive numeric-prefix stripping, e.g.
    # "4 of 28 Song Title" -> "Song Title" after the track number has
    # already been separated, and title tags that still contain the full form.
    full_of_total = re.match(r"(?i)^\s*\d{1,3}\s+of\s+\d{1,3}\s+(?P<title>\S.*)$", value)
    if full_of_total:
        value = full_of_total.group("title").strip()
    leading_of_total = re.match(r"(?i)^\s*of\s+\d{1,3}\s+(?P<title>\S.*)$", value)
    if leading_of_total:
        value = leading_of_total.group("title").strip()
    # Drop common trailing footnote markers from setlist titles, e.g. "Song*".
    value = re.sub(r"(?<=[A-Za-z0-9)])\s*[*†‡]+$", "", value).strip()
    # Also remove inline footnote markers before medley delimiters, e.g.
    # "Jam**>Flute Down**" -> "Jam>Flute Down".
    value = re.sub(r"(?<=[A-Za-z0-9)])\s*[*†‡]+\s*(?=>)", "", value).strip()
    # When a setlist line gives a bare audio filename, use the filename stem as
    # the best available title.
    if AUDIO_FILENAME_EXT_RE.search(value) and len(value.split()) <= 2:
        value = AUDIO_FILENAME_EXT_RE.sub("", os.path.basename(value)).strip()
        value = re.sub(r"(?i)^(?:(?:s|set)\s*\d{1,2}|(?:d|cd|disc|disk)\s*\d{1,2})\s*t\s*\d{1,3}\s*[-_. ]*", "", value).strip()
        value = re.sub(r"^\d{1,3}\s*[-_. ]*", "", value).strip()
    # Drop common encore prefixes when they are embedded in a numbered title
    # row, e.g. "09. E: Midnight Hour" or "09. Encore: Midnight Hour".
    value = re.sub(r"(?i)^(?:e|enc|encore)\s*:\s+", "", value).strip()
    value = compact_ws(value)
    # Some release-style filenames append the show date token after the title,
    # e.g. "101-Introduction 11-26.flac".  Drop only a trailing numeric
    # month-day token after an otherwise alphabetic title.
    value = re.sub(r"(?i)(?<=[A-Za-z)])\s+\d{1,2}[-_.]\d{1,2}$", "", value).strip()
    value = normalize_tag_title_printable(value)
    if not re.search(r"[A-Za-z0-9]", value):
        return ""
    return value


def _raw_title_part_is_unknown_placeholder(raw_title_part: str) -> bool:
    """Return True when a numbered setlist row supplies only a placeholder.

    Rows such as ``10 ?`` or ``12 ?// 6:52`` are real numbered track rows even
    though the title is unknown.  They must count toward the local setlist so a
    strong numbered 1..N list is not thrown away in favor of header or lineage
    prose.
    """
    value = str(raw_title_part or "").strip()
    value = TIME_PREFIX_RE.sub("", value).strip()
    value = TIME_SUFFIX_RE.sub("", value).strip()
    value = re.sub(r"(?i)\btape\s*flip\b", " ", value).strip()
    value = compact_ws(value)
    if re.fullmatch(r"(?i)(?:unknown|unk|untitled|no\s+title)", value):
        return True
    stripped = value.strip(" \t-–—:.;,/\\")
    if re.fullmatch(r"[?]+", stripped):
        return True
    return bool(stripped and not re.search(r"[A-Za-z0-9]", stripped) and "?" in stripped)


def _looks_like_aucdtect_result_line(line: str) -> bool:
    return bool(AUCDTECT_RESULT_LINE_RE.match(str(line or "").strip()))


def _is_non_song_technical_track_line(line: str) -> bool:
    """Return True for technical rows that can look like numbered songs.

    auCDtect reports commonly contain rows such as
    ``101 Ted the Mechanic.wav: track looks like CDDA with probability 100%.``.
    The leading number and filename can look like a song row, but the row is
    an audio-analysis result and must never be used as a track title.
    """
    raw = str(line or "").strip()
    return bool(_looks_like_aucdtect_result_line(raw) or SHNTOOL_LENGTH_ROW_RE.match(raw))


def _numbered_tracks_start_like_song_list(tracks: Sequence[Dict[str, object]]) -> bool:
    """True when parsed numbered rows begin like a real song list.

    TLO setlists should begin with track 1, occasionally 0, or no numbers at
    all.  This prevents venue/header rows such as ``5-øren Copenhagen`` from
    blocking the unnumbered-song fallback.
    """
    rows = list(tracks or [])
    if not rows:
        return False
    try:
        first = int(rows[0].get("original_number", -9999))
    except Exception:
        return False
    return _numbered_track_start_allowed(first)


def _parse_track_line(line: str) -> Optional[Tuple[int, str]]:
    raw = str(line or "").strip()
    if not raw:
        return None
    if _is_non_song_technical_track_line(raw):
        return None
    if (
        DATE_LIKE_RE.match(raw)
        or DATE_WORD_LIKE_RE.match(raw)
        or DURATION_ONLY_RE.match(raw)
        or SAMPLE_RATE_OR_BIT_DEPTH_RE.match(raw)
        or HASH_LINE_RE.match(raw)
        or CHECKSUM_SECTION_RE.match(raw)
    ):
        return None
    if _is_disc_or_set_heading(raw) or TRACK_SECTION_RE.match(raw):
        return None

    extinf_match = EXTINF_TRACK_RE.match(raw)
    if extinf_match:
        number = int(extinf_match.group("num") or 0)
        title = _clean_track_title(extinf_match.group("title"))
        title = re.sub(r"^\[\d{1,3}\]\s*", "", title).strip()
        if title:
            return number, title

    bracketed_match = BRACKETED_TRACK_RE.match(raw)
    if bracketed_match and not AUDIO_FILENAME_EXT_RE.search(raw):
        number = int(bracketed_match.group("num") or 0)
        title = _clean_track_title(bracketed_match.group("title"))
        if title:
            return number, title

    # Disc/set dash rows such as "1-1 Back Seat Betty 8:29" encode
    # disc/set number and track number separately.  Convert to the existing
    # CD/set-prefixed integer form (101, 102, 201, ...), so sequence checks
    # stay conservative and do not mistake these rows for repeated track 1.
    disc_dash_match = DISC_DASH_TRACK_RE.match(raw)
    if disc_dash_match and not AUDIO_FILENAME_EXT_RE.search(raw):
        try:
            disc = int(disc_dash_match.group("disc") or 0)
            track = int(disc_dash_match.group("num") or 0)
        except Exception:
            disc = 0
            track = 0
        if 1 <= disc <= 9 and 0 <= track <= 99:
            title = _clean_track_title(disc_dash_match.group("title"))
            if title:
                return disc * 100 + track, title

    side_letter_match = SIDE_LETTER_TRACK_RE.match(raw)
    if side_letter_match and not AUDIO_FILENAME_EXT_RE.search(raw):
        try:
            number = int(side_letter_match.group("num") or 0)
        except Exception:
            number = 0
        if 0 <= number <= 999:
            title = _clean_track_title(side_letter_match.group("title"))
            if title:
                return number, title

    for pattern in TRACK_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue
        try:
            number = int(match.group("num"))
        except Exception:
            number = 0
        if number < 0:
            continue
        raw_title_part = str(match.group("title") or "")
        # Do not let compact number+letter parsing turn ordinal prose/header
        # lines into tracks, e.g. "9th Annual Eddie Moore Jazz Festival".
        if re.match(r"(?i)^\s*(?:st|nd|rd|th)\b", raw_title_part) and re.match(r"(?i)^\s*\d{1,2}(?:st|nd|rd|th)\b", raw):
            continue
        if _raw_title_part_is_unknown_placeholder(raw_title_part):
            return number, "unknown"
        title = _clean_track_title(raw_title_part)
        if not title:
            # A numbered placeholder such as "17 ??" is still a supplied
            # track-title value, not a parser failure.  Tag it as unknown but
            # do not mark it as a generated Unknown-title fallback.
            if _raw_title_part_is_unknown_placeholder(raw_title_part):
                return number, "unknown"
            continue
        lowered = title.lower()
        if lowered in {"flac", "mp3", "wav", "shn", "aiff", "aif"}:
            continue
        if CHECKSUM_SECTION_RE.search(title):
            continue
        return number, title
    return None


FILENAME_TRACK_PATTERNS = [
    re.compile(r"(?i)^\s*(?:d|cd|disc|disk)\d{1,2}\s*t\s*\d{1,3}\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^\s*(?:d|cd|disc|disk)\d{1,2}\s*t\s*\d{1,3}(?P<title>[A-Za-z][^\r\n]*)$"),
    re.compile(r"(?i)^\s*(?:track\s*)?\d{1,3}\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^\s*\d{1,3}(?P<title>[A-Za-z][^\r\n]*)$"),
]


def _filename_stem_for_track_title(path_name: str) -> str:
    stem = os.path.basename(path_name or "")
    while True:
        new_stem, ext = os.path.splitext(stem)
        if not ext or ext.lower() not in AUDIO_EXTENSIONS_FOR_COUNTING:
            break
        stem = new_stem
    stem = stem.replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


FILENAME_DISC_TRACK_RE = re.compile(r"(?i)^\s*(?:d|cd|disc|disk)(?P<disc>\d{1,2})\s*(?:t|track)\s*(?P<track>\d{1,3})")
FILENAME_DISC_TRACK_ANYWHERE_RE = re.compile(r"(?i)(?<![A-Za-z])(?:d|cd|disc|disk)(?P<disc>\d{1,2})\s*(?:t|track)\s*(?P<track>\d{1,3})(?=\D|$)")
FILENAME_SET_TRACK_ANYWHERE_RE = re.compile(r"(?i)(?<![A-Za-z])s(?P<set>\d{1,2})\s*(?:t|track)\s*(?P<track>\d{1,3})(?=\D|$)")
FILENAME_TRACK_ANYWHERE_RE = re.compile(r"(?i)(?:t|track)\s*(?P<track>\d{1,3})(?=\D|$)")
FILENAME_LEADING_TRACK_RE = re.compile(r"(?i)^\s*(?:track\s*)?(?P<track>\d{1,3})(?=\D|$)")
FILENAME_EMBEDDED_TRACK_TITLE_PATTERNS = [
    re.compile(r"(?i)^.*?(?:^|[^A-Za-z0-9])s\d{1,2}\s*t\s*\d{1,3}\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^.*?(?:^|[^A-Za-z0-9])(?:d|cd|disc|disk)\d{1,2}\s*t\s*\d{1,3}\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
    re.compile(r"(?i)^.*?t\s*\d{1,3}\s*(?:[.)\-_:]+\s*|\s+)(?P<title>\S.*)$"),
]

GENERIC_FILENAME_TITLE_RE_LIST = [
    re.compile(r"(?i)^\s*(?:track|trk|title|song|audio\s*track|unknown|untitled|no\s*title|none|null)\s*$"),
    re.compile(r"(?i)^\s*(?:track|trk|title|song|audio\s*track)\s*0*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*(?:d|cd|disc|disk)\d{1,2}\s*t\s*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*s\d{1,2}\s*t\s*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*t\s*\d{1,3}\s*$"),
]


def _is_generic_filename_title(title: str) -> bool:
    value = compact_ws(title)
    if not value:
        return True
    if re.fullmatch(r"\d{1,3}", value):
        return True
    return any(pattern.match(value) for pattern in GENERIC_FILENAME_TITLE_RE_LIST)


def _parent_wrapper_disc_index(path_name: str) -> int:
    """Return a zero-based disc/set index from the immediate parent folder.

    Multi-disc releases sometimes use generic filenames such as Track01.flac in
    each Disc/CD folder.  In that case the filename alone cannot distinguish
    Disc 1 Track 01 from Disc 2 Track 01, so use the wrapper folder name as the
    first sort key.
    """
    parent = os.path.basename(os.path.dirname(os.path.normpath(path_name or "")))
    match = re.search(r"(?i)(?:^|[\s._-]+)(?:cd|disc|disk|set|part|side|tape|d)[\s._-]*(?P<num>\d{1,2})(?:\b|$)", parent)
    if not match:
        return 0
    try:
        return max(0, int(match.group("num")) - 1)
    except (TypeError, ValueError):
        return 0


def _audio_track_order(path_name: str) -> Tuple[int, int, str]:
    stem = _filename_stem_for_track_title(path_name)
    parent_disc_index = _parent_wrapper_disc_index(path_name)
    match = FILENAME_DISC_TRACK_RE.match(stem)
    if match:
        return (max(0, int(match.group("disc")) - 1), int(match.group("track")), os.path.basename(path_name).casefold())
    matches = list(FILENAME_DISC_TRACK_ANYWHERE_RE.finditer(stem))
    if matches:
        match = matches[-1]
        return (max(0, int(match.group("disc")) - 1), int(match.group("track")), os.path.basename(path_name).casefold())
    matches = list(FILENAME_SET_TRACK_ANYWHERE_RE.finditer(stem))
    if matches:
        match = matches[-1]
        return (max(0, int(match.group("set")) - 1), int(match.group("track")), os.path.basename(path_name).casefold())
    matches = list(FILENAME_TRACK_ANYWHERE_RE.finditer(stem))
    if matches:
        match = matches[-1]
        return (parent_disc_index, int(match.group("track")), os.path.basename(path_name).casefold())
    match = FILENAME_LEADING_TRACK_RE.match(stem)
    if match:
        return (parent_disc_index, int(match.group("track")), os.path.basename(path_name).casefold())
    return (parent_disc_index if parent_disc_index else 9999, 9999, os.path.basename(path_name).casefold())


def track_title_from_audio_filename(path_name: str) -> str:
    """Return a title parsed from a numbered audio filename, or ``unknown``.

    The trusted forms are ordinary leading track numbers, dNtNN/sNtNN prefixes,
    and release-style names where an artist/date prefix is followed by a
    set/track token and then the song title, e.g.
    ``artist1998-08-12s2t07 Encore Yourself.flac``.
    """
    stem = _filename_stem_for_track_title(path_name)
    for pattern in FILENAME_TRACK_PATTERNS:
        match = pattern.match(stem)
        if not match:
            continue
        title = _clean_track_title(match.group("title"))
        if _is_generic_filename_title(title):
            return "unknown"
        return title or "unknown"
    for pattern in FILENAME_EMBEDDED_TRACK_TITLE_PATTERNS:
        match = pattern.match(stem)
        if not match:
            continue
        title = _clean_track_title(match.group("title"))
        if _is_generic_filename_title(title):
            return "unknown"
        return title or "unknown"
    return "unknown"


def tracks_from_audio_filenames(music_files: Sequence[str]) -> List[Dict[str, object]]:
    tracks: List[Dict[str, object]] = []
    audio_files = sorted([path for path in music_files if _is_audio_file(path)], key=_audio_track_order)
    for idx, audio_path in enumerate(audio_files, start=1):
        tracks.append({
            "original_number": idx,
            "normalized_number": idx,
            "title": track_title_from_audio_filename(audio_path),
            "source_line": os.path.basename(audio_path),
            "source": "filename",
        })
    return tracks


TITLE_TAG_NUMBER_PREFIX_RE = re.compile(r"^\s*\d{1,3}\s*[.)\-_:]+\s*(?P<title>\S.*)$")
TITLE_TAG_OF_TOTAL_PREFIX_RE = re.compile(r"(?i)^\s*\d{1,3}\s+of\s+\d{1,3}\s+(?P<title>\S.*)$")
TITLE_LEADING_OF_TOTAL_RE = re.compile(r"(?i)^\s*of\s+\d{1,3}\s+(?P<title>\S.*)$")
GENERIC_TITLE_TAG_RE_LIST = [
    re.compile(r"(?i)^\s*(?:d|cd|disc|disk)\d{1,2}\s*t\s*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*s\d{1,2}\s*t\s*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*(?:track|trk|title|song|audio\s*track)\s*$"),
    re.compile(r"(?i)^\s*(?:track|trk|title|song|audio\s*track)\s*0*\d{1,3}\s*$"),
    re.compile(r"(?i)^\s*(?:track|trk|title|song|audio\s*track)\s*[x#]+\s*$"),
    re.compile(r"(?i)^\s*(?:untitled|unknown|no\s*title|none|null)\s*\d*\s*$"),
]


def _first_tag_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _first_tag_text(item)
            if text:
                return text
        return ""
    text_attr = getattr(value, "text", None)
    if text_attr is not None and text_attr is not value:
        text = _first_tag_text(text_attr)
        if text:
            return text
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return str(value or "")


def read_existing_audio_title_tag(path_name: str) -> str:
    """Return the current audio title tag, if one can be read."""
    if not path_name or not os.path.isfile(path_name):
        return ""
    try:
        audio = MutagenFile(path_name, easy=True)
        tags = getattr(audio, "tags", None) if audio is not None else None
        if tags is not None:
            try:
                title = _first_tag_text(tags.get("title"))
            except Exception:
                title = ""
            if compact_ws(title):
                return compact_ws(title)
    except Exception:
        pass

    try:
        audio = MutagenFile(path_name)
        tags = getattr(audio, "tags", None) if audio is not None else None
    except Exception:
        tags = None
    if tags is None:
        return ""

    for key in ("TIT2", "\xa9nam", "TITLE", "Title", "title"):
        try:
            value = tags.get(key)
        except Exception:
            value = None
        title = _first_tag_text(value)
        if compact_ws(title):
            return compact_ws(title)
    return ""


def _is_generic_audio_title_tag(title: str) -> bool:
    value = compact_ws(title)
    if not value:
        return True
    for pattern in GENERIC_TITLE_TAG_RE_LIST:
        if pattern.match(value):
            return True
    # A bare one-to-three digit title is just another generic track number.
    if re.fullmatch(r"\d{1,3}", value):
        return True
    return False


def _usable_title_from_audio_title_tag(raw_title: str) -> Tuple[str, bool]:
    """Return (title, usable) from an existing title tag.

    Valid last-resort title tags are normal strings with spaces, short single
    tokens, or numbered tags such as ``01. Song`` where the numeric prefix can
    be stripped. Empty/generic values become ``Unknown``.
    """
    raw = compact_ws(raw_title)
    if not raw:
        return "Unknown", False
    candidate = _clean_track_title(raw)
    numbered = TITLE_TAG_NUMBER_PREFIX_RE.match(candidate)
    if numbered:
        candidate = _clean_track_title(numbered.group("title"))
    if _is_generic_audio_title_tag(candidate):
        return "Unknown", False
    if not re.search(r"[A-Za-z]", candidate):
        return "Unknown", False
    if " " in candidate:
        return candidate, True
    if len(candidate) <= 40:
        return candidate, True
    return "Unknown", False


def tracks_from_audio_title_tags(music_files: Sequence[str]) -> Tuple[List[Dict[str, object]], int]:
    """Build one track-title row per audio file from existing title tags.

    The row count intentionally matches the audio-file count. Bad, generic, or
    missing title tags are represented as ``Unknown`` so tagging can proceed
    while the tag log records that the source titles were not usable.
    """
    tracks: List[Dict[str, object]] = []
    invalid_count = 0
    audio_files = sorted([path for path in music_files if _is_audio_file(path)], key=_audio_track_order)
    for idx, audio_path in enumerate(audio_files, start=1):
        raw_title = read_existing_audio_title_tag(audio_path)
        title, usable = _usable_title_from_audio_title_tag(raw_title)
        if not usable:
            invalid_count += 1
        tracks.append({
            "original_number": idx,
            "normalized_number": idx,
            "title": title,
            "source_line": raw_title or os.path.basename(audio_path),
            "source": "title-tags",
            "title_unknown_fallback": not usable,
        })
    return tracks, invalid_count


def _is_file_hash_run(lines: Sequence[str], idx: int) -> bool:
    """Return True when a filename.ext:<hex> checksum line is part of a run.

    Fingerprint/checksum sections commonly list one hash row per audio file,
    such as ``01 Song.flac:81b2...``.  The leading track number and title make
    those lines look like tracks unless the checksum form is recognized first.
    Requiring a neighboring checksum row prevents one isolated line from being
    treated as the start/end of a checksum block, while still excluding the line
    itself from track parsing.
    """
    if idx < 0 or idx >= len(lines):
        return False
    if not FILE_HASH_LINE_RE.match(str(lines[idx] or "").strip()):
        return False
    for neighbor in (idx - 1, idx + 1):
        if 0 <= neighbor < len(lines) and FILE_HASH_LINE_RE.match(str(lines[neighbor] or "").strip()):
            return True
    return False


def _disc_or_set_prefixed_track_part(number: int) -> Optional[int]:
    """Return the track part from set/CD-prefixed numbers such as 101 or 201.

    Some setlists encode disc/set plus track number as one integer, e.g.
    101, 102, ... for CD/set 1 and 201, 202, ... for CD/set 2.
    Treat the final two digits as the track number for start/sequence checks
    while preserving the original number in diagnostics.
    """
    try:
        value = int(number)
    except Exception:
        return None
    if 100 <= value <= 999:
        disc_or_set = value // 100
        track_part = value % 100
        if 1 <= disc_or_set <= 9 and 0 <= track_part <= 99:
            return track_part
    return None


def _disc_or_set_prefixed_disc_part(number: int) -> Optional[int]:
    try:
        value = int(number)
    except Exception:
        return None
    if 100 <= value <= 999:
        disc_or_set = value // 100
        track_part = value % 100
        if 1 <= disc_or_set <= 9 and 0 <= track_part <= 99:
            return disc_or_set
    return None


def _is_next_disc_or_set_prefixed_start(previous: int, current: int) -> bool:
    """True for transitions like 104 -> 201 without a section header.

    A few info files use disc-track row numbers (1-1, 1-2, 2-1) without a
    separate Disc 2 heading.  After conversion to 101, 102, 201, this allows
    a new disc/set to start at track 0 or 1 while still requiring the disc/set
    number to increase.
    """
    prev_disc = _disc_or_set_prefixed_disc_part(previous)
    cur_disc = _disc_or_set_prefixed_disc_part(current)
    cur_track = _disc_or_set_prefixed_track_part(current)
    if prev_disc is None or cur_disc is None or cur_track is None:
        return False
    return cur_disc > prev_disc and cur_track in (0, 1)


def _track_sequence_part(number: int) -> Optional[int]:
    """Return the list-sequence track number for reset/sequence checks."""
    try:
        value = int(number)
    except Exception:
        return None
    prefixed = _disc_or_set_prefixed_track_part(value)
    if prefixed is not None:
        return prefixed
    return value


def _is_implicit_numbered_reset_start(previous: int, current: int) -> bool:
    """True when a new unheaded numbered section appears to restart at 1.

    Some setlists omit Disc/CD/Set headings entirely and simply number rows as
    1, 2, 3, 4, 1, 2, 3.  Treat the second 1 as a candidate reset only after
    an established ascending run; the caller confirms it by requiring the next
    parsed row to continue as 2 before accepting it.
    """
    previous_part = _track_sequence_part(previous)
    current_part = _track_sequence_part(current)
    if previous_part is None or current_part is None:
        return False
    return previous_part >= 1 and current_part == 1



def _has_later_valid_numbered_continuation(
    lines: Sequence[str],
    start_index: int,
    expected_next: Optional[int],
    previous_original_number: int,
) -> bool:
    """Return True if later numbered rows continue/restart the current list.

    Info files sometimes include source notes, URLs, personnel, comments, or
    entire mini writeups between two numbered song-list blocks.  A terminator
    line such as ``Note:`` should not end parsing when the next numbered row
    still continues the song sequence.  This helper looks ahead without adding
    any titles and accepts only high-confidence continuations:

    * the next numbered row equals the current expected number;
    * a disc/set-prefixed next section begins, e.g. 112 -> 201;
    * an implicit restart to 0/1 is confirmed by the following numbered row.
    """
    if not lines:
        return False
    first_candidate: Optional[Tuple[int, str]] = None
    for future_line in lines[start_index + 1:]:
        line = str(future_line or "").strip()
        if not line:
            continue
        if CHECKSUM_SECTION_RE.match(line) or HASH_LINE_RE.match(line) or _is_non_song_technical_track_line(line):
            return False
        if TRACK_SECTION_RE.match(line) or _is_disc_or_set_heading(line) or SHOW_SECTION_RE.match(line):
            continue
        parsed = _parse_track_line(line)
        if parsed is None:
            continue
        number, title = parsed
        if expected_next is not None and number == expected_next:
            return True
        if _is_next_disc_or_set_prefixed_start(previous_original_number, number):
            return True
        if first_candidate is None:
            if _numbered_track_start_allowed(number):
                first_candidate = (number, title)
                continue
            return False
        first_number, _first_title = first_candidate
        return number == _next_expected_track_number(first_number)
    return False

def _numbered_track_start_allowed(number: int) -> bool:
    try:
        value = int(number)
    except Exception:
        return False
    if value in (0, 1):
        return True
    prefixed = _disc_or_set_prefixed_track_part(value)
    return prefixed in (0, 1)


def _next_expected_track_number(number: int) -> int:
    value = int(number)
    track_part = _disc_or_set_prefixed_track_part(value)
    if track_part is not None:
        return value + 1
    return 1 if value == 0 else value + 1


def parse_setlist_tracks(setlist_file: str) -> List[Dict[str, object]]:
    if not setlist_file or not os.path.isfile(setlist_file):
        return []
    text = _read_text(setlist_file)
    if setlist_text_requests_generated_from_music_files(text):
        return []
    tracks: List[Dict[str, object]] = []
    pending_high_start: Optional[Tuple[int, str, str]] = None
    pending_implicit_reset: Optional[Tuple[int, str, str]] = None
    pending_forward_gap: Optional[Tuple[int, str, str, int]] = None
    seen_track_section = False
    section_boundary_since_track = False
    expected_next: Optional[int] = None
    lines = [raw_line.strip() for raw_line in text.splitlines()]

    def append_track(original_number: int, title: str, source_line: str) -> None:
        nonlocal expected_next, section_boundary_since_track, pending_high_start, pending_implicit_reset, pending_forward_gap
        tracks.append({
            "original_number": original_number,
            "normalized_number": len(tracks) + 1,
            "title": title,
            "source_line": source_line,
        })
        expected_next = _next_expected_track_number(original_number)
        section_boundary_since_track = False
        pending_high_start = None
        pending_implicit_reset = None
        pending_forward_gap = None

    for idx, line in enumerate(lines):
        if not line:
            continue
        if tracks and TRACK_LIST_TERMINATOR_RE.match(line):
            if (
                len(tracks) == 1
                and not seen_track_section
                and int(tracks[0].get("original_number", 0) or 0) > 20
            ):
                tracks = []
                expected_next = None
                continue
            if re.match(r"(?i)^\s*patch\b", line):
                break
            previous_original_number = int(tracks[-1].get("original_number", -9999) or -9999)
            if _has_later_valid_numbered_continuation(lines, idx, expected_next, previous_original_number):
                section_boundary_since_track = True
                pending_high_start = None
                pending_implicit_reset = None
                pending_forward_gap = None
                continue
            break
        if (
            CHECKSUM_SECTION_RE.match(line)
            or HASH_LINE_RE.match(line)
            or _is_file_hash_run(lines, idx)
            or _is_non_song_technical_track_line(line)
        ):
            if tracks:
                break
            continue
        if TRACK_SECTION_RE.match(line) or _is_disc_or_set_heading(line) or SHOW_SECTION_RE.match(line):
            seen_track_section = True
            pending_high_start = None
            if tracks:
                section_boundary_since_track = True
            continue
        parsed = _parse_track_line(line)
        if parsed is None and (seen_track_section or tracks):
            blank_match = re.match(r"^\s*(?:track\s*)?(?P<num>\d{1,3})\s*(?:[.)\-:]+\s*[-–—]*|)$", line, re.I)
            if blank_match:
                parsed = (int(blank_match.group("num")), "Unknown")
        if parsed is None:
            continue
        original_number, title = parsed

        if pending_implicit_reset is not None:
            pending_number, pending_title, pending_line = pending_implicit_reset
            if original_number == _next_expected_track_number(pending_number):
                append_track(pending_number, pending_title, pending_line)
                append_track(original_number, title, line)
                continue
            pending_implicit_reset = None

        if pending_forward_gap is not None:
            gap_number, gap_title, gap_line, missing_number = pending_forward_gap
            pending_forward_gap = None
            if original_number == gap_number and gap_number == missing_number + 1:
                # Some otherwise valid setlists have a one-number typo at a
                # section boundary or encore break, e.g. 1..7, 9, 9 where the
                # first 9 is really track 8.  Accept both rows only when the
                # duplicate immediately confirms the skipped number.
                append_track(missing_number, gap_title, gap_line)
                append_track(original_number, title, line)
                continue
            append_track(gap_number, gap_title, gap_line)

        if not tracks:
            # A real numbered song list normally starts at 0 or 1.  Ignore a
            # stray greater-than-one line unless the next parsed numbered line
            # proves it is part of a consecutive numbered block.  This keeps
            # lines like "20 feet away..." and "5-øren..." from poisoning the
            # list while preserving rare setlist excerpts that begin at 10/11.
            if not _numbered_track_start_allowed(original_number):
                if pending_high_start and original_number == pending_high_start[0] + 1:
                    append_track(*pending_high_start)
                    append_track(original_number, title, line)
                else:
                    pending_high_start = (original_number, title, line)
                continue
            pending_high_start = None
            append_track(original_number, title, line)
            continue

        if expected_next is not None and original_number == expected_next:
            append_track(original_number, title, line)
            continue

        previous_original_number = int(tracks[-1].get("original_number", -9999) or -9999)
        if _is_next_disc_or_set_prefixed_start(previous_original_number, original_number):
            append_track(original_number, title, line)
            continue

        if _numbered_track_start_allowed(original_number):
            if len(tracks) == 1 and not section_boundary_since_track:
                # If the next numbered-looking line starts at 0/1 again, the
                # first match was likely a false positive.  Throw it away and
                # start the real list here.
                tracks = []
                expected_next = None
                append_track(original_number, title, line)
                continue
            if section_boundary_since_track or line.lstrip().lower().startswith("#extinf"):
                # Multiple-disc/multiple-set lists legitimately restart at 0/1
                # after a delimiter.  M3U EXTINF rows can also restart by disc
                # without an intervening human-readable delimiter.
                append_track(original_number, title, line)
                continue
            previous_original_number = int(tracks[-1].get("original_number", -9999) or -9999)
            if _is_implicit_numbered_reset_start(previous_original_number, original_number):
                # Some files omit set/disc headings and simply restart at 1.
                # Hold this row until the next parsed row confirms the restart
                # by continuing to 2, so a single stray note beginning with 1
                # does not become a song title.
                pending_implicit_reset = (original_number, title, line)
                continue
            # A second 0/1 without a boundary or confirming continuation is most
            # likely unrelated text or a separate list; ignore it.
            continue

        if expected_next is not None and original_number > expected_next:
            if len(tracks) > 1 or seen_track_section:
                # Keep a forward gap in an otherwise established run so later
                # gap-fill logic can repair damaged rows such as "0+. Song".
                # For the common typo 1..7, 9, 9, hold the first high row
                # briefly; if the next parsed row repeats the same number, the
                # first high row is treated as the missing number and both
                # titles are preserved.
                pending_forward_gap = (original_number, title, line, expected_next)
                continue
            # A single first row followed by the wrong number is not a proven
            # list.  Throw away the false first match and keep looking.
            tracks = []
            expected_next = None
            pending_high_start = (original_number, title, line)
            continue

    if pending_forward_gap is not None:
        gap_number, gap_title, gap_line, _missing_number = pending_forward_gap
        append_track(gap_number, gap_title, gap_line)
        pending_forward_gap = None

    if pending_high_start and not tracks:
        # One isolated greater-than-one row is not enough evidence for a track list.
        pending_high_start = None
    if tracks and not seen_track_section and not _numbered_tracks_start_like_song_list(tracks):
        return []
    return tracks


def _split_comma_track_items(line: str, min_items: int = 5) -> List[str]:
    """Return comma-separated candidate titles from one long setlist line.

    This supports old-style setlists where a whole set is one comma-separated
    sentence rather than numbered track rows.  Each item must be one to eight
    words and a line must contain at least five valid items to be trusted as a
    comma-track source. Commas do not need to be followed by spaces; trailing
    footnote markers such as asterisks are stripped before validation.
    """
    raw = str(line or "").strip()
    if not raw or "," not in raw:
        return []
    if HASH_LINE_RE.match(raw) or CHECKSUM_SECTION_RE.match(raw) or DATE_LIKE_RE.match(raw):
        return []
    pieces = [_clean_track_title(part) for part in raw.split(",")]
    pieces = [part for part in pieces if part]
    minimum = max(2, int(min_items or 5))
    if len(pieces) < minimum:
        return []
    for piece in pieces:
        words = [word for word in piece.split() if word]
        if not (1 <= len(words) <= 8):
            return []
        if not COMMA_ITEM_WORD_RE.match(piece):
            return []
    return pieces


def parse_setlist_text_tracks(text: str) -> List[Dict[str, object]]:
    """Parse numbered track lines from already-loaded setlist text."""
    tracks: List[Dict[str, object]] = []
    lines = [raw_line.strip() for raw_line in str(text or "").splitlines()]
    for idx, line in enumerate(lines):
        if not line:
            continue
        if tracks and TRACK_LIST_TERMINATOR_RE.match(line):
            break
        if (
            CHECKSUM_SECTION_RE.match(line)
            or HASH_LINE_RE.match(line)
            or _is_file_hash_run(lines, idx)
            or _is_non_song_technical_track_line(line)
        ):
            if tracks:
                break
            continue
        if TRACK_SECTION_RE.match(line) or _is_disc_or_set_heading(line):
            continue
        parsed = _parse_track_line(line)
        if parsed is None:
            continue
        original_number, title = parsed
        tracks.append({
            "original_number": original_number,
            "normalized_number": len(tracks) + 1,
            "title": title,
            "source_line": line,
            "source": "etreedb",
        })
    return tracks



UNNUMBERED_PROSE_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:source|transfer|lineage|master|taper|recorded|recording|notes?|comments?|"
    r"thanks?|enjoy|total\s+time|personnel|musicians?|with|http|www\.|venue|location|date|artist|"
    r"style|city|country|sound\s+quality|quality|promoted\s+album)\b"
)
UNNUMBERED_CONTEXT_PROSE_RE = re.compile(
    r"(?ix)^\s*(?:"
    r"filler\s*:|songs?\s*\#|w/|wxrt\b|nak\b|samplitude\b|deck\s+with\b|"
    r"by\s+.+\b\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})\b|"
    r"from\s+.+\b(?:collection|archive|cassette|tape|master)\b|"
    r"(?:band|personnel|musicians?)\s*:?\s*$|"
    r"md5'?s?\b|fingerprints?\b"
    r")"
)


def _looks_like_unnumbered_song_title(line: str) -> bool:
    raw = compact_ws(line)
    if not raw:
        return False
    if TRACK_LIST_TERMINATOR_RE.match(raw) or CHECKSUM_SECTION_RE.match(raw):
        return False
    if DATE_LIKE_RE.match(raw) or HASH_LINE_RE.match(raw) or _is_non_song_technical_track_line(raw):
        return False
    if TRACK_SECTION_RE.match(raw) or _is_disc_or_set_heading(raw):
        return False
    if re.match(r"^[A-Za-z .'-]+,\s*[A-Z]{2}$", raw):
        return False
    if UNNUMBERED_PROSE_PREFIX_RE.match(raw):
        return False
    if UNNUMBERED_CONTEXT_PROSE_RE.match(raw):
        return False
    if re.fullmatch(r"(?i)(?:encores?|encore\s*\d+)\s*:?(?:\s*[-–—:.>]*)?", raw):
        return False
    if ":" in raw and re.match(r"(?i)^(?:source|transfer|lineage|record(?:ed|ing)?|taper|location|venue|date|artist|notes?|comments?|personnel|band)\s*:", raw):
        return False
    if len(raw) > 120:
        return False
    if not re.search(r"[A-Za-z]", raw):
        if not re.fullmatch(r"\d{1,4}", raw):
            return False
    words = [w for w in re.split(r"\s+", raw) if w]
    if len(words) > 14:
        return False
    return True


def parse_unnumbered_section_tracks(setlist_file: str, expected_count: int = 0) -> Tuple[List[Dict[str, object]], str]:
    """Parse unnumbered song lists that follow CD/Disc/Set delimiters.

    Many old info files contain blocks such as ``CD1:`` or ``Set 1`` followed
    by one song title per line without leading track numbers.  This parser is
    intentionally conservative: it only trusts lines inside such a delimited
    section, and when ``expected_count`` is supplied the count must match.
    """
    if not setlist_file or not os.path.isfile(setlist_file):
        return [], ""
    text = _read_text(setlist_file)
    if setlist_text_requests_generated_from_music_files(text):
        return [], ""
    titles: List[Tuple[str, str]] = []
    active = False
    had_title_in_section = False
    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            if active and had_title_in_section:
                active = False
                had_title_in_section = False
            continue
        if CHECKSUM_SECTION_RE.match(line) or _is_non_song_technical_track_line(line):
            if active or titles:
                active = False
            continue
        if TRACK_LIST_TERMINATOR_RE.match(line):
            if titles:
                break
            active = False
            continue
        if _is_disc_or_set_heading(line):
            active = True
            had_title_in_section = False
            continue
        # If true numbered tracks exist, let the primary numbered parser handle
        # the file instead of mixing numbered and unnumbered interpretations.
        if _parse_track_line(line) is not None:
            return [], ""
        if not active:
            continue
        if not _looks_like_unnumbered_song_title(line):
            if had_title_in_section:
                active = False
                had_title_in_section = False
            continue
        title = _clean_unstructured_title_line(line)
        if title:
            titles.append((title, line))
            had_title_in_section = True
    expected = int(expected_count or 0)
    if expected > 0 and len(titles) != expected:
        return [], ""
    tracks: List[Dict[str, object]] = []
    for idx, (title, source_line) in enumerate(titles, start=1):
        tracks.append({
            "original_number": idx,
            "normalized_number": idx,
            "title": title,
            "source_line": source_line,
            "source": "unnumbered-sections",
        })
    return tracks, "unnumbered-sections" if tracks else ""


def _clean_unstructured_title_line(line: str) -> str:
    value = compact_ws(line)
    value = re.sub(r"(?i)^e(?:ncore)?\s*[:.\-–—>]+\s*", "", value).strip()
    value = re.sub(r"\s*[-–—>]+\s*$", "", value).strip()
    value = re.sub(r"\*+$", "", value).strip()
    return _clean_track_title(value)


def _looks_like_personnel_or_credit_line(line: str) -> bool:
    raw = compact_ws(line).casefold()
    if not raw:
        return False
    credit_words = r"(?:guitar|vocals?|bass|drums?|keyboards?|sax(?:ophone)?|trombone|trumpet|flute|percussion|taper|recorded|transferred|mastered|lineage|source|transfer)"
    if re.match(rf"^(?:source|transfer|lineage|recorded|taped|transferred|mastered)\b", raw):
        return True
    # Personnel lines usually look like "Name - guitar" or "Name: vocals".
    # Do not reject legitimate song titles such as "I Play Guitar".
    if re.search(rf"\s[-–—:]\s*.*\b{credit_words}\b", raw):
        return True
    return False


def parse_unstructured_unnumbered_tracks(setlist_file: str, expected_count: int = 0) -> Tuple[List[Dict[str, object]], str]:
    """Parse plain one-song-per-line setlists without CD/Set delimiters.

    This is intentionally count-gated: it only returns a block that matches the
    number of audio files, so header/credit prose blocks are not used as song
    titles by accident.
    """
    expected = int(expected_count or 0)
    if expected <= 0 or not setlist_file or not os.path.isfile(setlist_file):
        return [], ""
    text = _read_text(setlist_file)
    if setlist_text_requests_generated_from_music_files(text):
        return [], ""

    blocks: List[List[Tuple[str, str]]] = []
    current: List[Tuple[str, str]] = []

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append(current)
            current = []

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line or re.match(r"^[\-_=]{5,}$", line):
            flush()
            continue
        if (
            TRACK_LIST_TERMINATOR_RE.match(line)
            or CHECKSUM_SECTION_RE.match(line)
            or HASH_LINE_RE.match(line)
            or _is_file_hash_run([line], 0)
            or _is_non_song_technical_track_line(line)
        ):
            flush()
            if blocks:
                break
            continue
        # Let the numbered parser handle true numbered lists.  This function is
        # only for plain title-per-line blocks.
        if _parse_track_line(line) is not None:
            flush()
            continue
        if line.count(",") >= 4:
            flush()
            continue
        title = _clean_unstructured_title_line(line)
        if not title or not _looks_like_unnumbered_song_title(title) or _looks_like_personnel_or_credit_line(line):
            flush()
            continue
        current.append((title, line))
    flush()

    def build_tracks(block_rows: List[Tuple[str, str]], source_name: str) -> List[Dict[str, object]]:
        tracks: List[Dict[str, object]] = []
        for idx, (title, source_line) in enumerate(block_rows, start=1):
            tracks.append({
                "original_number": idx,
                "normalized_number": idx,
                "title": title,
                "source_line": source_line,
                "source": source_name,
            })
        return tracks

    for block in blocks:
        if len(block) == expected:
            return build_tracks(block, "unnumbered-lines"), "unnumbered-lines"

    # Some old multi-CD/set info files have several blank-separated title blocks,
    # and encores may be separated by one or two blank lines.  Try contiguous
    # block runs that sum to the expected audio count.  Require at least one
    # multi-line block so isolated header/venue lines do not become a setlist.
    for start in range(len(blocks)):
        combined: List[Tuple[str, str]] = []
        has_multi_line_block = False
        for end in range(start, len(blocks)):
            block = blocks[end]
            combined.extend(block)
            has_multi_line_block = has_multi_line_block or len(block) >= 2
            if len(combined) == expected and has_multi_line_block:
                return build_tracks(combined, "unnumbered-line-blocks"), "unnumbered-line-blocks"
            if len(combined) > expected:
                break

    # If no contiguous run works, keep the older conservative behavior of
    # combining all multi-line title blocks.
    eligible_blocks = [block for block in blocks if len(block) >= 2]
    if len(eligible_blocks) > 1:
        combined: List[Tuple[str, str]] = []
        for block in eligible_blocks:
            combined.extend(block)
        if len(combined) == expected:
            return build_tracks(combined, "unnumbered-line-blocks"), "unnumbered-line-blocks"

    return [], ""


_NORMALIZED_TITLE_CHAR_RE = re.compile(r"[^a-z0-9]+")


def _normalize_title_for_confirmation(value: str) -> str:
    return _NORMALIZED_TITLE_CHAR_RE.sub(" ", str(value or "").casefold()).strip()


def _filename_title_confirmed_by_setlist(title: str, setlist_text: str) -> bool:
    candidate = _normalize_title_for_confirmation(title)
    haystack = _normalize_title_for_confirmation(setlist_text)
    if not candidate or not haystack:
        return False
    if candidate in haystack:
        return True
    words = [word for word in candidate.split() if len(word) > 1]
    return bool(words and all(word in haystack for word in words))


def tracks_from_audio_filenames_confirmed_by_setlist(
    music_files: Sequence[str],
    setlist_file: str = "",
) -> Tuple[List[Dict[str, object]], str]:
    """Return filename-derived tracks, confirmed by setlist text when present."""
    audio_files = sorted([path for path in music_files if _is_audio_file(path)], key=_audio_track_order)
    if not audio_files:
        return [], ""
    setlist_text = ""
    if setlist_file and os.path.isfile(setlist_file):
        setlist_text = _read_text(setlist_file)
    tracks: List[Dict[str, object]] = []
    for idx, audio_path in enumerate(audio_files, start=1):
        title = track_title_from_audio_filename(audio_path)
        if _is_generic_audio_title_tag(title):
            return [], ""
        if setlist_text and not _filename_title_confirmed_by_setlist(title, setlist_text):
            return [], ""
        tracks.append({
            "original_number": idx,
            "normalized_number": idx,
            "title": title,
            "source_line": os.path.basename(audio_path),
            "source": "filenames-confirmed" if setlist_text else "filenames",
        })
    return tracks, "filenames-confirmed" if setlist_text else "filenames"

def _record_artist_and_date(record) -> Tuple[str, str]:
    artist = compact_ws(getattr(record, "artist", "") if record is not None else "")
    date_text = compact_ws(getattr(record, "date", "") if record is not None else "")
    if not re.fullmatch(r"(?:19|20)\d{2}-\d{2}-\d{2}", date_text or ""):
        date_text = ""
    return artist, date_text


def tracks_from_etreedb_setlist(
    config: Config,
    record,
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Return eTreeDB setlist tracks when the GUI/CLI eTree option is enabled.

    When eTreeDB returns multiple performances for the same artist/date, each
    performance's set1/set2/set3 text is combined independently and scored by
    track-count fit. This avoids flattening unrelated same-date performances
    into one oversized setlist.
    """
    if not bool(getattr(config, "etree_lookup", False)):
        return []
    artist, date_text = _record_artist_and_date(record)
    if not artist or not date_text:
        _emit(emit, f"INFO: {folder} | eTreeDB setlist fallback skipped; artist/date not available")
        return []
    try:
        performance_candidates = lookup_setlists_by_performance(
            artist=artist,
            date_yyyy_mm_dd=date_text,
            debug=bool(getattr(config, "debug", False)),
        )
    except Exception as exc:
        _emit(emit, f"WARN: {folder} | eTreeDB setlist fallback failed for {artist} {date_text}: {exc}")
        return []
    if not performance_candidates:
        _emit(emit, f"INFO: {folder} | eTreeDB returned no setlist titles for {artist} {date_text}")
        return []

    expected = int(expected_count or 0)
    parsed_candidates: List[Tuple[int, int, object, List[Dict[str, object]]]] = []
    for ordinal, (performance, normalized_setlists) in enumerate(performance_candidates):
        tracks = parse_setlist_text_tracks("\n".join(normalized_setlists))
        if not tracks:
            continue
        parsed_candidates.append((abs(len(tracks) - expected), ordinal, performance, tracks))

    if not parsed_candidates:
        _emit(emit, f"INFO: {folder} | eTreeDB returned setlist text but no parseable track titles")
        return []

    exact_matches = [item for item in parsed_candidates if len(item[3]) == expected]
    if exact_matches:
        _distance, _ordinal, performance, tracks = exact_matches[0]
        suffix = ""
        if len(performance_candidates) > 1:
            suffix = f"; selected performance id {getattr(performance, 'performance_id', '')} from {len(performance_candidates)} same-date matches"
        _emit(emit, f"INFO: {folder} | using eTreeDB setlist titles for {artist} {date_text}{suffix}")
        return tracks

    parsed_candidates.sort(key=lambda item: (item[0], item[1]))
    _distance, _ordinal, performance, tracks = parsed_candidates[0]
    _emit(
        emit,
        f"WARN: {folder} | eTreeDB setlist track count mismatch: best_performance_id={getattr(performance, 'performance_id', '')} "
        f"etree={len(tracks)} audio_files={expected} matches={len(performance_candidates)}",
    )
    return []


def tracks_from_cached_setlistfm_setlist(
    record,
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Return setlist.fm titles cached during the venue/location lookup call.

    This function never calls setlist.fm.  It only consumes setlist text already
    attached to the metadata record by ``_apply_setlistfm_lookup_to_record``.
    Different same-date setlist.fm performances remain separate candidates and
    are scored independently by track count.
    """
    candidates = getattr(record, "setlistfm_setlist_candidates", None) if record is not None else None
    if not candidates:
        return []
    expected = int(expected_count or 0)
    parsed_candidates: List[Tuple[int, int, Dict[str, object], List[Dict[str, object]]]] = []
    for ordinal, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        setlists = [str(text or "").strip() for text in (candidate.get("setlists") or []) if str(text or "").strip()]
        if not setlists:
            continue
        tracks = parse_setlist_text_tracks("\n".join(setlists))
        if not tracks:
            continue
        parsed_candidates.append((abs(len(tracks) - expected), ordinal, candidate, tracks))

    if not parsed_candidates:
        _emit(emit, f"INFO: {folder} | setlist.fm cached setlist text contained no parseable track titles")
        return []

    exact_matches = [item for item in parsed_candidates if len(item[3]) == expected]
    if exact_matches:
        _distance, _ordinal, candidate, tracks = exact_matches[0]
        url = compact_ws(str(candidate.get("url") or ""))
        suffix = f" from {url}" if url else ""
        if len(parsed_candidates) > 1:
            suffix += f"; selected 1 of {len(parsed_candidates)} same-date cached result(s)"
        _emit(emit, f"INFO: {folder} | using cached setlist.fm setlist titles{suffix}")
        return tracks

    parsed_candidates.sort(key=lambda item: (item[0], item[1]))
    _distance, _ordinal, candidate, tracks = parsed_candidates[0]
    _emit(
        emit,
        f"WARN: {folder} | cached setlist.fm setlist track count mismatch: "
        f"best={len(tracks)} audio_files={expected} matches={len(parsed_candidates)}",
    )
    return []


def parse_unnumbered_comma_tracks(setlist_file: str, expected_count: int) -> Tuple[List[Dict[str, object]], str]:
    """Parse unnumbered comma-separated setlist content for tagging fallback.

    Returns ``(tracks, source)`` where source is ``comma-items`` when comma
    items become the track titles, ``comma-lines`` when each long comma line is
    used as one title, or blank when no fallback applies.
    """
    if not setlist_file or not os.path.isfile(setlist_file) or int(expected_count or 0) <= 0:
        return [], ""
    text = _read_text(setlist_file)
    if setlist_text_requests_generated_from_music_files(text):
        return [], ""
    candidate_lines: List[Tuple[str, List[str]]] = []
    active_set_section = False
    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            active_set_section = False
            continue
        if TRACK_SECTION_RE.match(line) or _is_disc_or_set_heading(line):
            active_set_section = True
            continue
        # This fallback is only for setlists without numbered tracks.  A line
        # that parses as a numbered track is not a comma-fallback line.
        if _parse_track_line(line) is not None:
            active_set_section = False
            continue
        items = _split_comma_track_items(line, min_items=2 if active_set_section else 5)
        if items:
            candidate_lines.append((line, items))
            continue
        active_set_section = False
    if not candidate_lines:
        return [], ""

    flattened: List[str] = []
    for _line, items in candidate_lines:
        flattened.extend(items)
    if len(flattened) == expected_count:
        tracks = []
        for idx, title in enumerate(flattened, start=1):
            tracks.append({
                "original_number": idx,
                "normalized_number": idx,
                "title": title or "unknown",
                "source_line": title,
                "source": "comma-items",
            })
        return tracks, "comma-items"

    if len(candidate_lines) == expected_count:
        tracks = []
        for idx, (line, _items) in enumerate(candidate_lines, start=1):
            title = _clean_track_title(line) or "unknown"
            tracks.append({
                "original_number": idx,
                "normalized_number": idx,
                "title": title,
                "source_line": line,
                "source": "comma-lines",
            })
        return tracks, "comma-lines"

    return [], ""


def format_tag_track_number(track_number: int, total_tracks: int) -> str:
    """Return the track number string written to file tags.

    Folders with up to 99 tracks use 2 digits (01, 02, ...).  Folders with
    more than 99 tracks use 3 digits (001, 002, ...), so the first number
    starts with 00 as requested.
    """
    try:
        number = int(track_number)
    except Exception:
        number = 0
    try:
        total = int(total_tracks)
    except Exception:
        total = 0
    width = 3 if total > 99 else 2
    return str(max(0, number)).zfill(width)

def _album_for_record(config: Config, record) -> str:
    if getattr(config, "compliant", False):
        album_piece = compact_ws(getattr(record, "album_name", "") or getattr(record, "venue", ""))
        date_piece = compact_ws(getattr(record, "date", ""))
        if date_piece and album_piece:
            return compact_ws(f"{date_piece} {album_piece}")
        if date_piece:
            return date_piece
        return album_piece
    return compact_ws(" ".join(part for part in [
        getattr(record, "date", ""),
        getattr(record, "venue", ""),
        getattr(record, "location", ""),
    ] if compact_ws(part)))


def _safe_message_parts(messages: Sequence[str]) -> str:
    return "; ".join(compact_ws(str(item)) for item in messages if compact_ws(str(item)))


def _is_invalid_flac_error(path_name: str, exc: BaseException) -> bool:
    if os.path.splitext(path_name)[1].lower() != ".flac":
        return False
    message = str(exc).lower()
    return "not a valid flac file" in message or "not a flac file" in message


def _normalize_tag_write_error(path_name: str, exc: BaseException) -> str:
    if _is_invalid_flac_error(path_name, exc):
        return "Not a valid FLAC file"
    return compact_ws(str(exc)) or exc.__class__.__name__


def _quote_log_path(path_name: str) -> str:
    return "'" + str(path_name).replace("'", "\\'") + "'"


def _format_tag_file_error_line(path_name: str, error_text: str, code: str = "ERROR_AUDIO_FILE") -> str:
    reason_code = compact_ws(str(code or "ERROR_AUDIO_FILE")).upper().replace(" ", "_")
    if not reason_code.startswith("ERROR"):
        reason_code = "ERROR_" + reason_code
    return f"{reason_code}: {_quote_log_path(path_name)} - {error_text}"


CORRUPT_FLACS_FILENAME = "CorruptFlacs.txt"
SHN_CONVERSION_TIMEOUT_SECONDS = 30 * 60


def _corrupt_flacs_log_path(config: Config) -> str:
    tlo_home = str(getattr(config, "TLOHome", "") or "").strip()
    if not tlo_home:
        return ""
    return os.path.join(tlo_home, CORRUPT_FLACS_FILENAME)


def ensure_corrupt_flacs_log(config: Config) -> None:
    """Create TLOHome/CorruptFlacs.txt if TLOHome is available.

    This file is an operator-friendly list of FLAC files that failed during
    tagging because the file could not be opened or written successfully.
    The function is intentionally best-effort so corrupt-file logging never
    interrupts an inventory or tag run.
    """
    try:
        log_path = _corrupt_flacs_log_path(config)
        if not log_path:
            return
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8"):
            pass
    except Exception:
        pass


def record_corrupt_flac(config: Config, path_name: str) -> None:
    """Append one full FLAC path to TLOHome/CorruptFlacs.txt.

    Only FLAC paths are recorded.  Duplicates are allowed because repeated
    failures across runs are useful evidence that the file still needs repair
    or replacement.
    """
    try:
        if os.path.splitext(str(path_name or ""))[1].lower() != ".flac":
            return
        log_path = _corrupt_flacs_log_path(config)
        if not log_path:
            return
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8", newline="") as outfile:
            outfile.write(os.path.normpath(str(path_name)) + "\n")
    except Exception:
        pass


def _skip_reason_code(reason: str) -> str:
    text = compact_ws(str(reason or "")).casefold()
    if "cancel" in text:
        return "SKIP_CANCELLED"
    if "no parseable tracks" in text:
        return "SKIP_TITLE_PARSE"
    if "track count mismatch" in text or "setlist contained" in text:
        return "SKIP_TITLE_COUNT"
    if "no setlist found" in text or "no readable" in text or "setlist file" in text and "found" in text:
        return "SKIP_SETLIST_MISSING"
    if "unreadable" in text or "decode" in text or "could not read" in text:
        return "SKIP_SETLIST_UNREADABLE"
    if "artist not found" in text or "album metadata not found" in text or "metadata" in text or "show name" in text:
        return "SKIP_METADATA"
    if "tag target preparation" in text or "rename compliantly" in text or "copy" in text and "failed" in text:
        return "SKIP_TARGET_PREP"
    if "audio files" in text and "no" in text:
        return "SKIP_NO_AUDIO"
    return "SKIP_TAGGING"


def _warning_line(folder: str, reason: str, emit: Optional[Callable[[str], None]], code: str = "WARN_TAGGING") -> None:
    reason_code = compact_ws(str(code or "WARN_TAGGING")).upper().replace(" ", "_")
    if not reason_code.startswith("WARN"):
        reason_code = "WARN_" + reason_code
    _emit(emit, f"{reason_code}: {folder} | {reason}")


def _tag_output_line_is_error(line: str) -> bool:
    text = str(line or "").strip()
    upper = text.upper()
    if not text:
        return False
    if upper.startswith(("ERROR", "WARN", "SKIP", "CANCELLED")):
        return True
    if upper.startswith(("TAG_SKIP", "TAG_COPY_AND_DELETE_SKIP", "RENAME_COMPLIANTLY_SKIP")):
        return True
    if "_FAILED" in upper or " FAILED" in upper or "FILE_ERROR" in upper or "CONVERT_SHN_ERROR" in upper:
        return True
    match = re.search(r"\bfile_errors=(\d+)", text, re.IGNORECASE)
    if match and int(match.group(1) or 0) > 0:
        return True
    return False


def _write_easy_tags(path_name: str, artist: str, album: str, track_number: object, title: str) -> None:
    audio = MutagenFile(path_name, easy=True)
    if audio is None:
        raise TaggerError("mutagen could not identify audio type")
    if getattr(audio, "tags", None) is None:
        audio.add_tags()
    _clear_total_disc_easy_tags(audio)
    audio["artist"] = [artist]
    audio["album"] = [album]
    audio["title"] = [title]
    audio["tracknumber"] = [str(track_number)]
    audio.save()


def _write_id3_tags(path_name: str, artist: str, album: str, track_number: object, title: str) -> None:
    if ID3 is None:
        raise TaggerError("ID3 fallback unavailable")
    try:
        tags = ID3(path_name)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("TPE1")
    tags.delall("TALB")
    tags.delall("TIT2")
    tags.delall("TRCK")
    _clear_total_disc_id3_tags(tags)
    tags.add(TPE1(encoding=3, text=[artist]))
    tags.add(TALB(encoding=3, text=[album]))
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TRCK(encoding=3, text=[str(track_number)]))
    tags.save(path_name)


def _write_flac_tags(path_name: str, artist: str, album: str, track_number: object, title: str) -> None:
    if FLAC is None:
        raise TaggerError("FLAC fallback unavailable")
    audio = FLAC(path_name)
    _clear_total_disc_easy_tags(audio)
    audio["artist"] = artist
    audio["album"] = album
    audio["title"] = title
    audio["tracknumber"] = str(track_number)
    audio.save()


def _write_mp4_tags(path_name: str, artist: str, album: str, track_number: object, title: str, total_tracks: int) -> None:
    if MP4 is None:
        raise TaggerError("MP4 fallback unavailable")
    audio = MP4(path_name)
    _clear_total_disc_mp4_tags(audio)
    audio["\xa9ART"] = [artist]
    audio["\xa9alb"] = [album]
    audio["\xa9nam"] = [title]
    audio["trkn"] = [(int(str(track_number).lstrip("0") or "0"), 0)]
    audio.save()


def write_audio_tags(path_name: str, artist: str, album: str, track_number: object, title: str, total_tracks: int = 0) -> None:
    ext = os.path.splitext(path_name)[1].lower()
    if not _is_taggable_audio_file(path_name):
        raise TaggerError(f"unsupported or non-taggable audio extension: {ext or '(none)'}")
    artist = standard_ascii_text(artist, fallback="Unknown") or "Unknown"
    album = standard_ascii_text(album, fallback="Unknown") or "Unknown"
    title = normalize_tag_title_printable(title) or "unknown"
    try:
        _write_easy_tags(path_name, artist, album, track_number, title)
        return
    except Exception as first_exc:
        fallback_exc = first_exc
    try:
        if ext == ".mp3":
            _write_id3_tags(path_name, artist, album, track_number, title)
            return
        if ext == ".flac":
            _write_flac_tags(path_name, artist, album, track_number, title)
            return
        if ext in {".m4a", ".mp4", ".aac", ".alac"}:
            _write_mp4_tags(path_name, artist, album, track_number, title, int(total_tracks or 0))
            return
    except Exception as second_exc:
        fallback_exc = second_exc
    raise TaggerError(_normalize_tag_write_error(path_name, fallback_exc))


def _folder_label(group: dict) -> str:
    return group.get("main_dir_path", "") or group.get("main_dir_name", "") or "(unknown folder)"


def _rescan_group_audio_files(group: dict) -> List[str]:
    """Return all audio files from the known group folders.

    Phase 1 intentionally carries only a representative media path per folder.
    Tagging is different: when tags are actually being written, every eligible
    audio file in the already-identified folder(s) must be visited.  Rescan the
    known music directories at tagging time, and use the carried sample paths
    only as a fallback for older tests/logs or inaccessible folders.
    """
    seen = set()
    audio_files: List[str] = []

    def add(path_name: str) -> None:
        normalized = os.path.normpath(path_name or "")
        if not normalized:
            return
        key = normalized.casefold()
        if key in seen or not _is_audio_file(normalized):
            return
        seen.add(key)
        audio_files.append(normalized)

    for music_dir in group.get("music_dirs", []) or []:
        normalized_dir = os.path.normpath(music_dir or "")
        if not normalized_dir or not os.path.isdir(normalized_dir):
            continue
        try:
            with os.scandir(normalized_dir) as entries:
                children = sorted(list(entries), key=lambda entry: entry.name.lower())
        except (OSError, PermissionError):
            continue
        for entry in children:
            try:
                if entry.is_file(follow_symlinks=False):
                    add(entry.path)
            except (OSError, PermissionError):
                continue

    if audio_files:
        return sorted(audio_files, key=_audio_track_order)

    for path_name in group.get("music_files", []) or []:
        add(path_name)
    return sorted(audio_files, key=_audio_track_order)


def _is_shn_audio_file(path_name: str) -> bool:
    return os.path.splitext(str(path_name or ""))[1].lower() in SHN_AUDIO_EXTENSIONS


INVALID_FOLDER_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')


def safe_compliant_folder_name(show_name: str, fallback: str = "TLO Show") -> str:
    fallback_ascii = standard_ascii_text(fallback, fallback="TLO Show") or "TLO Show"
    value = standard_ascii_text(show_name, fallback=fallback_ascii)
    value = INVALID_FOLDER_CHARS_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or fallback_ascii or "TLO Show"


def _unique_destination_path(parent_dir: str, folder_name: str) -> str:
    base = safe_compliant_folder_name(folder_name)
    candidate = os.path.normpath(os.path.join(parent_dir, base))
    if not os.path.exists(candidate):
        return candidate
    for idx in range(1, 10000):
        candidate = os.path.normpath(os.path.join(parent_dir, f"{base} (copy{idx})"))
        if not os.path.exists(candidate):
            return candidate
    raise TaggerError(f"could not allocate unique destination folder under {parent_dir}")


def _rewrite_path_under_root(path_name: str, old_root: str, new_root: str) -> str:
    if not path_name:
        return path_name
    try:
        normalized_path = os.path.normpath(path_name)
        normalized_old = os.path.normpath(old_root)
        if os.path.commonpath([normalized_path, normalized_old]) != normalized_old:
            return normalized_path
        rel = os.path.relpath(normalized_path, normalized_old)
        return os.path.normpath(os.path.join(new_root, rel))
    except Exception:
        return path_name


def _rewrite_group_paths(group: dict, old_root: str, new_root: str, *, mutate: bool = False) -> dict:
    target = group if mutate else dict(group)
    for key in ("main_dir_path", "setlist_file"):
        if target.get(key):
            target[key] = _rewrite_path_under_root(target[key], old_root, new_root)
    for key in ("music_dirs", "music_files", "music_sample_files", "txt_files", "setlist_files"):
        values = target.get(key, []) or []
        target[key] = [_rewrite_path_under_root(value, old_root, new_root) for value in values]
    if target.get("main_dir_path"):
        target["main_dir_name"] = os.path.basename(os.path.normpath(target["main_dir_path"]))
    return target


def _rewrite_record_paths(record, old_root: str, new_root: str, *, mutate: bool = False):
    target = record if mutate else copy.copy(record)
    for attr in ("main_dir_path", "setlist_file"):
        value = getattr(target, attr, "")
        if value:
            setattr(target, attr, _rewrite_path_under_root(value, old_root, new_root))
    music_dirs = list(getattr(target, "music_dirs", []) or [])
    if music_dirs:
        setattr(target, "music_dirs", [_rewrite_path_under_root(value, old_root, new_root) for value in music_dirs])
    setlist_files = list(getattr(target, "setlist_files", []) or [])
    if setlist_files:
        setattr(target, "setlist_files", [_rewrite_path_under_root(value, old_root, new_root) for value in setlist_files])
    if getattr(target, "main_dir_path", ""):
        setattr(target, "main_dir_name", os.path.basename(os.path.normpath(getattr(target, "main_dir_path"))))
    return target


def _path_is_under(path_name: str, parent: str) -> bool:
    try:
        normalized_path = os.path.normpath(path_name)
        normalized_parent = os.path.normpath(parent)
        return os.path.commonpath([normalized_path, normalized_parent]) == normalized_parent
    except Exception:
        return False


def _paths_on_same_filesystem(path_a: str, path_b: str) -> bool:
    try:
        return os.stat(path_a).st_dev == os.stat(path_b).st_dev
    except OSError:
        return False


def _file_size_map(root: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for current_dir, _dir_names, file_names in os.walk(root):
        for file_name in file_names:
            full_path = os.path.join(current_dir, file_name)
            try:
                relative = os.path.relpath(full_path, root)
                result[os.path.normcase(os.path.normpath(relative))] = os.path.getsize(full_path)
            except OSError:
                result[os.path.normcase(os.path.normpath(os.path.relpath(full_path, root)))] = -1
    return result


def _verify_copy_by_file_size(source_root: str, destination_root: str) -> None:
    source_sizes = _file_size_map(source_root)
    destination_sizes = _file_size_map(destination_root)
    if source_sizes != destination_sizes:
        missing = sorted(set(source_sizes) - set(destination_sizes))[:5]
        extra = sorted(set(destination_sizes) - set(source_sizes))[:5]
        mismatched = sorted(
            rel for rel in set(source_sizes) & set(destination_sizes)
            if source_sizes.get(rel) != destination_sizes.get(rel)
        )[:5]
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        if mismatched:
            details.append(f"size_mismatch={mismatched}")
        raise TaggerError("Tag Copy and Delete verification failed" + (": " + "; ".join(details) if details else ""))


def prepare_inventory_copy_delete_target(
    config: Config,
    group: dict,
    record,
    emit: Optional[Callable[[str], None]] = None,
) -> Tuple[dict, object]:
    """Copy/move the original inventory folder away after metadata capture.

    The returned group/record point at the moved/copied folder. Inventory-time
    callers should use the returned record for log/bootlist output because
    Copy/Delete Original removes the source and makes the destination the
    inventoried tree.
    """
    destination_parent = os.path.normpath(str(getattr(config, "tag_copy_and_delete_path", "") or "").strip())
    if not destination_parent:
        return group, record
    if not os.path.isabs(destination_parent) or not os.path.isdir(destination_parent):
        raise TaggerError(f"Tag Copy and Delete Path is not a valid existing full path: {destination_parent}")

    source_root = os.path.normpath(group.get("main_dir_path", "") or "")
    if not source_root or not os.path.isdir(source_root):
        raise TaggerError(f"Tag Copy and Delete source folder is not a valid directory: {source_root}")
    if os.path.normcase(source_root) == os.path.normcase(destination_parent) or _path_is_under(destination_parent, source_root):
        raise TaggerError("Tag Copy and Delete destination must not be the source folder or a child of it")

    source_leaf = os.path.basename(source_root) or compact_ws(getattr(record, "main_dir_name", "")) or "TLO Show"
    show_name = compact_ws(getattr(record, "show_name", ""))
    use_compliant_name = bool(getattr(config, "rename_compliantly", False)) and bool(show_name)
    destination_leaf = safe_compliant_folder_name(show_name if use_compliant_name else source_leaf, fallback=source_leaf)
    destination_root = _unique_destination_path(destination_parent, destination_leaf)

    if _paths_on_same_filesystem(source_root, destination_parent):
        try:
            shutil.move(source_root, destination_root)
            _emit(emit, f"TAG_COPY_DELETE_MOVE: {source_root} -> {destination_root}")
        except Exception as exc:
            raise TaggerError(f"Tag Copy and Delete move failed: {exc}") from exc
    else:
        try:
            shutil.copytree(source_root, destination_root, symlinks=False)
            _verify_copy_by_file_size(source_root, destination_root)
            shutil.rmtree(source_root)
            _emit(emit, f"TAG_COPY_DELETE_COPY: {source_root} -> {destination_root}")
        except Exception as exc:
            if isinstance(exc, TaggerError):
                raise
            raise TaggerError(f"Tag Copy and Delete copy/delete failed: {exc}") from exc

    return (
        _rewrite_group_paths(group, source_root, destination_root, mutate=False),
        _rewrite_record_paths(record, source_root, destination_root, mutate=False),
    )


def prepare_inventory_tagging_target(
    config: Config,
    group: dict,
    record,
    emit: Optional[Callable[[str], None]] = None,
) -> Tuple[dict, object]:
    """Return the group/record that inventory-time tagging should modify."""
    source_root = os.path.normpath(group.get("main_dir_path", "") or "")
    if not source_root or not os.path.isdir(source_root):
        return group, record

    show_name = compact_ws(getattr(record, "show_name", ""))
    original_name = os.path.basename(source_root) or compact_ws(getattr(record, "main_dir_name", "")) or "TLO Show"
    use_compliant_name = bool(getattr(config, "rename_compliantly", False)) and bool(show_name)
    target_name = safe_compliant_folder_name(show_name if use_compliant_name else original_name, fallback=original_name)

    if bool(getattr(config, "tag_copy_during_inventory", False)):
        destination_parent = os.path.normpath(str(getattr(config, "tag_copy_destination", "") or ""))
        if not destination_parent or not os.path.isdir(destination_parent):
            raise TaggerError(f"Tag Copy destination is not a valid directory: {destination_parent}")
        destination_root = _unique_destination_path(destination_parent, target_name)
        try:
            shutil.copytree(source_root, destination_root, symlinks=False)
            _emit(emit, f"TAG_COPY: {source_root} -> {destination_root}")
        except Exception as exc:
            raise TaggerError(f"Tag Copy failed: {exc}") from exc
        return (
            _rewrite_group_paths(group, source_root, destination_root, mutate=False),
            _rewrite_record_paths(record, source_root, destination_root, mutate=False),
        )

    if bool(getattr(config, "rename_compliantly", False)) and show_name:
        parent_dir = os.path.dirname(source_root)
        intended_root = os.path.normpath(os.path.join(parent_dir, target_name))
        if os.path.normcase(intended_root) == os.path.normcase(os.path.normpath(source_root)):
            return group, record
        destination_root = _unique_destination_path(parent_dir, target_name)
        try:
            os.rename(source_root, destination_root)
            _emit(emit, f"RENAME_COMPLIANTLY: {source_root} -> {destination_root}")
            _rewrite_group_paths(group, source_root, destination_root, mutate=True)
            _rewrite_record_paths(record, source_root, destination_root, mutate=True)
        except Exception as exc:
            _emit(emit, f"ERROR: {source_root} | Rename Compliantly failed: {exc}")
    return group, record


def _bundled_ffmpeg_executable() -> str:
    """Return the app-bundled ffmpeg executable supplied by imageio-ffmpeg.

    SHN conversion should not depend on a user-installed command-line tool.
    For PyInstaller builds, include imageio_ffmpeg and its binary data.  The
    runtime then resolves the native converter from inside the application
    bundle.  Source-tree test/dev runs may also work when imageio_ffmpeg is
    installed in the Python environment, but PATH and environment-variable
    fallbacks are intentionally not used here.
    """
    try:
        import imageio_ffmpeg  # type: ignore
    except Exception:
        return ""
    try:
        exe = str(imageio_ffmpeg.get_ffmpeg_exe() or "").strip()
    except Exception:
        return ""
    if exe and os.path.isfile(exe):
        return exe
    return ""


def _shn_converter_available() -> bool:
    return bool(_bundled_ffmpeg_executable())

def _converted_flac_path_for_shn(path_name: str) -> str:
    stem, _ext = os.path.splitext(os.path.normpath(path_name or ""))
    return stem + ".flac"


def convert_shn_to_flac(path_name: str, emit: Optional[Callable[[str], None]] = None) -> str:
    """Convert one .shn/.shnf file to .flac and delete the source on success.

    Returns the new FLAC path. Raises TaggerError on any failure. Conversion is
    intentionally explicit and conservative: an existing destination is not
    overwritten, and the source is deleted only after a non-empty FLAC has been
    produced and moved into place.
    """
    source = os.path.normpath(str(path_name or ""))
    if not _is_shn_audio_file(source):
        raise TaggerError(f"not an SHN file: {source}")
    if not os.path.isfile(source):
        raise TaggerError(f"SHN file does not exist: {source}")
    target = _converted_flac_path_for_shn(source)
    if os.path.exists(target):
        raise TaggerError(f"FLAC destination already exists: {target}")
    converter = _bundled_ffmpeg_executable()
    if not converter:
        raise TaggerError("bundled native SHN converter is unavailable; rebuild the PyInstaller app with imageio-ffmpeg data included")
    temp_target = target + ".tlo-convert.tmp.flac"
    try:
        if os.path.exists(temp_target):
            os.remove(temp_target)
        command = [converter, "-nostdin", "-y", "-i", source, "-compression_level", "5", temp_target]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=SHN_CONVERSION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise TaggerError(f"bundled SHN converter timed out after {SHN_CONVERSION_TIMEOUT_SECONDS} seconds") from exc
        if result.returncode != 0:
            details = compact_ws((result.stderr or result.stdout or "").splitlines()[-1] if (result.stderr or result.stdout) else "")
            raise TaggerError(f"bundled SHN converter failed with exit code {result.returncode}" + (f": {details}" if details else ""))
        if not os.path.isfile(temp_target) or os.path.getsize(temp_target) <= 0:
            raise TaggerError("ffmpeg did not create a non-empty FLAC output")
        os.replace(temp_target, target)
        os.remove(source)
        _emit(emit, f"  CONVERTED SHN: {os.path.basename(source)} -> {os.path.basename(target)} | converter=app-bundled")
        return target
    except Exception:
        try:
            if os.path.exists(temp_target):
                os.remove(temp_target)
        except Exception:
            pass
        raise


def _prepare_audio_files_for_tagging(
    config: Config,
    group: dict,
    audio_files: Sequence[str],
    emit: Optional[Callable[[str], None]] = None,
) -> Tuple[List[str], int]:
    """Convert SHN files when requested and return files eligible for tagging.

    SHN files are inventory media but not directly taggable.  When --convert-shn
    is enabled, convert them before title selection so the setlist/audio count is
    compared against the files that will actually be tagged.  Failed conversions
    are logged and skipped; successful conversions replace the SHN path with the
    new FLAC path and delete the original.
    """
    converted_or_existing: List[str] = []
    errors = 0
    convert_enabled = bool(getattr(config, "convert_shn", False))
    for audio_path in sorted(list(audio_files or []), key=_audio_track_order):
        path = os.path.normpath(str(audio_path or ""))
        if not path:
            continue
        if _is_sample_audio_file(path):
            _emit(emit, f"  SKIP SAMPLE AUDIO: {os.path.basename(path)}")
            continue
        if _is_shn_audio_file(path):
            if not convert_enabled:
                converted_or_existing.append(path)
                continue
            try:
                converted_or_existing.append(convert_shn_to_flac(path, emit=emit))
            except Exception as exc:
                errors += 1
                _emit(emit, _format_tag_file_error_line(path, f"SHN conversion failed: {exc}"))
            continue
        converted_or_existing.append(path)
    # Keep the group's file list current for debug copies and later fallbacks.
    group["music_files"] = list(converted_or_existing)
    return sorted(converted_or_existing, key=_audio_track_order), errors


def _problem(folder: str, reason: str, emit: Optional[Callable[[str], None]], code: str = "") -> None:
    reason_code = compact_ws(str(code or _skip_reason_code(reason))).upper().replace(" ", "_")
    if not reason_code.startswith("SKIP"):
        reason_code = "SKIP_" + reason_code
    _emit(emit, f"{reason_code}: {folder} | {reason}")


def _title_tag_fallback_tracks(
    audio_files: Sequence[str],
    folder: str,
    reason: str,
    emit: Optional[Callable[[str], None]] = None,
    require_any_usable: bool = False,
) -> Tuple[List[Dict[str, object]], str, Optional[str]]:
    if not audio_files:
        return [], "", f"{reason}; no audio files found for title-tag fallback"
    fallback_tracks, invalid_count = tracks_from_audio_title_tags(audio_files)
    if require_any_usable and invalid_count >= len(fallback_tracks):
        return [], "", f"{reason}; no usable existing audio title tags found"
    _warning_line(folder, f"{reason}; using existing audio title tags as last-resort track titles", emit, code="WARN_TITLE_FALLBACK")
    if invalid_count:
        _warning_line(folder, f"{invalid_count} audio title tag(s) were empty, generic, or unusable; writing Unknown for those title(s)", emit, code="WARN_TITLE_PARTIAL")
    return fallback_tracks, "title-tags", None


def _debug_unknown_title_copy_enabled(config: Config) -> bool:
    return bool(getattr(config, "debug", False) and getattr(config, "TLOHome", ""))


def _debug_safe_filename(name: str) -> str:
    base = os.path.basename(str(name or "")).strip() or "unknown-setlist"
    base = re.sub(r'[\\/:*?"<>|]+', "_", base)
    base = compact_ws(base).replace(" ", "_") or "unknown-setlist"
    stem, _ext = os.path.splitext(base)
    return (stem or "unknown-setlist") + ".txt"


def _unique_debug_output_path(debug_dir: str, source_name: str) -> str:
    safe_name = _debug_safe_filename(source_name)
    stem, ext = os.path.splitext(safe_name)
    candidate = os.path.join(debug_dir, safe_name)
    idx = 1
    while os.path.exists(candidate):
        idx += 1
        candidate = os.path.join(debug_dir, f"{stem}(debug{idx}){ext or '.txt'}")
    return candidate


def _record_to_postprocess_dict(record) -> Dict[str, str]:
    keys = (
        "show_name", "artist", "date", "venue", "album_name", "location",
        "parentheticals", "main_dir_path", "setlist_file",
    )
    return {key: str(getattr(record, key, "") or "") for key in keys}


def _inventory_setlist_debug_filename(group: dict, record) -> str:
    try:
        base = _setlist_base_from_record(_record_to_postprocess_dict(record), fallback="Show")
        return _candidate_setlist_name(base or "Show")
    except Exception:
        show_name = compact_ws(str(getattr(record, "show_name", "") or ""))
        if show_name:
            safe = re.sub(r'[^A-Za-z0-9()&-]+', '', standard_ascii_text(show_name)) or "Show"
        else:
            safe = os.path.basename(os.path.normpath(str(group.get("main_dir_path", "") or ""))) or "Show"
            safe = _debug_safe_filename(safe).rsplit(".", 1)[0]
        return (safe or "Show") + ".txt"


def _fallback_meta_log_entry(record) -> str:
    lines = [
        f"SHOW_NAME: {compact_ws(getattr(record, 'show_name', ''))}",
        f"SHOW_IN_CONFLICT: {'yes' if getattr(record, 'show_in_conflict', False) else 'no'}",
        f"MAIN_DIR_PATH: {getattr(record, 'main_dir_path', '')}",
        f"GROUP_NUMBER: {getattr(record, 'group_number', '')}",
        f"MAIN_DIR_NAME: {getattr(record, 'main_dir_name', '')}",
        f"SETLIST_FILE: {getattr(record, 'setlist_file', '')}",
        f"MUSIC_FILE_COUNT: {getattr(record, 'music_file_count', '')}",
        f"VOLUME_LABEL: {getattr(record, 'volume_label', '')}",
        f"ARTIST: {getattr(record, 'artist', '')}",
        f"DATE: {getattr(record, 'date', '')}",
        f"VENUE: {getattr(record, 'venue', '')}",
        f"LOCATION: {getattr(record, 'location', '')}",
        f"CITY: {getattr(record, 'city', '')}",
        f"REGION: {getattr(record, 'region', '')}",
        f"COUNTRY: {getattr(record, 'country', '')}",
        f"QUALIFIER: {getattr(record, 'qualifier', '')}",
        f"PARENTHETICALS: {getattr(record, 'parentheticals', '')}",
        f"ALBUM_NAME: {getattr(record, 'album_name', '')}",
        f"IS_24_BIT: {'yes' if getattr(record, 'is_24_bit', False) else 'no'}",
        "END_SHOW_METADATA",
    ]
    return "\n".join(lines) + "\n"


def _debug_music_file_lines(group: dict, audio_files: Sequence[str] = ()) -> List[str]:
    music_file_lines = [str(path) for path in audio_files if str(path or "").strip()]
    if not music_file_lines:
        music_file_lines = [str(path) for path in group.get("music_files", []) or [] if str(path or "").strip()]
    if not music_file_lines:
        music_file_lines = ["(no music filenames available)"]
    return music_file_lines


def _is_unknown_title_debug_track(track: Dict[str, object], track_source: str = "") -> bool:
    """Return True when an Unknown title represents a TLO fallback/failure.

    A literal setlist title such as "unknown" or "(unknown title)" is still a
    title supplied by the setlist and should not create an Unknown-title debug
    failure.  Debug Unknown-title diagnostics are intended for generated
    Unknown values, especially unusable existing audio title tags.
    """
    title = str((track or {}).get("title") or "").strip().casefold()
    if title != "unknown":
        return False
    if bool((track or {}).get("title_unknown_fallback")):
        return True
    return str(track_source or "").strip().casefold() not in {"setlist", "comma-items", "comma-lines", "etreedb", "setlist.fm"}


def _write_tag_debug_setlist_copy(
    config: Config,
    group: dict,
    record,
    reason: str,
    tracks: Sequence[Dict[str, object]] = (),
    track_source: str = "",
    audio_files: Sequence[str] = (),
    meta_log_entry: str = "",
    emit: Optional[Callable[[str], None]] = None,
    force: bool = False,
) -> None:
    if not _debug_unknown_title_copy_enabled(config):
        return
    if group.get("_tag_debug_setlist_copy_written") and not force:
        return

    setlist_file = str(group.get("setlist_file", "") or getattr(record, "setlist_file", "") or "")
    unknown_numbers = [
        str(track.get("normalized_number", ""))
        for track in tracks
        if _is_unknown_title_debug_track(track, track_source)
    ]

    try:
        debug_dir = os.path.join(str(getattr(config, "TLOHome", "")), "debug")
        os.makedirs(debug_dir, exist_ok=True)
        meta_entry = str(meta_log_entry or "").strip("\r\n")
        if not meta_entry:
            meta_entry = _fallback_meta_log_entry(record).strip("\r\n")
        music_file_lines = _debug_music_file_lines(group, audio_files)

        readable_setlist = bool(setlist_file and os.path.isfile(setlist_file))
        if readable_setlist:
            original_text = _read_text(setlist_file)
        else:
            original_text = "(no readable selected setlist file)\n"
        source_name = _inventory_setlist_debug_filename(group, record)

        debug_lines = [
            meta_entry,
            "----- TAG DEBUG -----",
            "DEBUG_REASON: " + compact_ws(reason or "tagging diagnostic"),
            "DEBUG_UNKNOWN_TITLE_TRACKS: " + (", ".join(unknown_numbers) if unknown_numbers else "(none)"),
            "DEBUG_TRACK_TITLE_SOURCE: " + str(track_source or ""),
            "DEBUG_ORIGINAL_SETLIST_FILE: " + (setlist_file or "(none)"),
            "----- MUSIC FILES -----",
            "\n".join(music_file_lines),
            "----- ORIGINAL SETLIST FILE -----",
            original_text,
        ]
        output_path = _unique_debug_output_path(debug_dir, source_name)
        with open(output_path, "w", encoding="utf-8", newline="") as outfile:
            outfile.write("\n".join(debug_lines))
        group["_tag_debug_setlist_copy_written"] = True
        _emit(emit, f"DEBUG: {_folder_label(group)} | wrote tag debug setlist copy: {output_path}")
    except Exception as exc:
        _emit(emit, f"WARN: {_folder_label(group)} | could not write tag debug setlist copy: {exc}")



def _renormalize_track_rows(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    for idx, row in enumerate(rows, start=1):
        copy = dict(row)
        copy["normalized_number"] = idx
        normalized.append(copy)
    return normalized


def _coerce_tracks_to_expected_count(
    tracks: Sequence[Dict[str, object]],
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Return an exact-count numbered run when headers/tails were misparsed.

    Some info files contain date/event headers like ``20 April 1974`` before a
    proper 01..NN setlist, or checksum/analysis tables after it.  If a clean
    contiguous run matching the audio-file count is present, prefer that run
    over falling through to title tags.
    """
    rows = list(tracks or [])
    expected = int(expected_count or 0)
    if expected <= 0 or len(rows) == expected:
        return rows

    for start_idx, row in enumerate(rows):
        try:
            first_num = int(row.get("original_number", -9999))
        except Exception:
            continue
        if first_num not in (0, 1):
            continue
        candidate = rows[start_idx:start_idx + expected]
        if len(candidate) != expected:
            continue
        try:
            nums = [int(item.get("original_number", -9999)) for item in candidate]
        except Exception:
            continue
        if nums == list(range(first_num, first_num + expected)):
            if start_idx or len(rows) > expected:
                _emit(emit, f"WARN: {folder} | selected {expected} contiguous setlist track row(s) from {len(rows)} parseable row(s); ignored likely header/footer rows")
            return _renormalize_track_rows(candidate)

    # Handle multi-disc lists with track numbers reset to 1.  Trust this only
    # when the combined rows with plausible resets exactly match the audio count.
    selected: List[Dict[str, object]] = []
    last = None
    started = False
    for row in rows:
        try:
            num = int(row.get("original_number", -9999))
        except Exception:
            continue
        if not started:
            if num not in (0, 1):
                continue
            started = True
            selected = [row]
            last = num
            continue
        if num == (last or 0) + 1 or num in (0, 1):
            selected.append(row)
            last = num
            if len(selected) == expected:
                _emit(emit, f"WARN: {folder} | selected {expected} reset-aware setlist track row(s) from {len(rows)} parseable row(s); ignored likely header/footer rows")
                return _renormalize_track_rows(selected)
        else:
            if num in (0, 1):
                selected = [row]
                last = num
            else:
                selected = []
                last = None
                started = False
    return rows



def _fill_missing_numbered_track_rows_from_filenames(
    tracks: Sequence[Dict[str, object]],
    audio_files: Sequence[str],
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Fill small numbered-track gaps using the matching audio filename title.

    This is for otherwise clear numbered setlists with one or a few damaged rows,
    such as a typo in the track number.  It is more useful than writing Unknown
    when the corresponding audio filename contains a real song title.
    """
    rows = list(tracks or [])
    expected = int(expected_count or 0)
    if expected <= 0 or len(rows) == expected or not rows:
        return rows
    by_num: Dict[int, Dict[str, object]] = {}
    for row in rows:
        try:
            num = int(row.get("original_number", -1))
        except Exception:
            return rows
        if num < 1 or num > expected or num in by_num:
            return rows
        by_num[num] = row
    if not by_num or max(by_num) != expected:
        return rows
    missing = [num for num in range(1, expected + 1) if num not in by_num]
    if not missing or len(missing) > max(3, expected // 5):
        return rows
    filename_tracks = tracks_from_audio_filenames(audio_files)
    if len(filename_tracks) != expected:
        return rows
    filled: List[Dict[str, object]] = []
    used_filename_titles: List[int] = []
    for idx in range(1, expected + 1):
        if idx in by_num:
            copy = dict(by_num[idx])
        else:
            candidate = dict(filename_tracks[idx - 1])
            title = compact_ws(str(candidate.get("title", "")))
            if _is_generic_filename_title(title):
                return rows
            copy = {
                "original_number": idx,
                "title": title,
                "source_line": os.path.basename(str(candidate.get("source_line", ""))) or f"audio filename track {idx}",
                "source": "setlist+filename-gap",
            }
            used_filename_titles.append(idx)
        copy["normalized_number"] = idx
        filled.append(copy)
    if used_filename_titles:
        _emit(emit, f"WARN: {folder} | filled missing setlist track title(s) {', '.join(str(n) for n in used_filename_titles)} from audio filename(s)")
    return filled

def _fill_missing_numbered_track_rows(
    tracks: Sequence[Dict[str, object]],
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    rows = list(tracks or [])
    expected = int(expected_count or 0)
    if expected <= 0 or len(rows) == expected or not rows:
        return rows
    by_num: Dict[int, Dict[str, object]] = {}
    for row in rows:
        try:
            num = int(row.get("original_number", -1))
        except Exception:
            return rows
        if num < 1 or num > expected or num in by_num:
            return rows
        by_num[num] = row
    if not by_num or max(by_num) != expected:
        return rows
    missing = [num for num in range(1, expected + 1) if num not in by_num]
    if not missing:
        return rows
    # Fill small gaps in otherwise clear 1..N lists.  Do not synthesize a large
    # portion of the titles from blanks.
    if len(missing) > max(3, expected // 5):
        return rows
    filled: List[Dict[str, object]] = []
    for idx in range(1, expected + 1):
        if idx in by_num:
            copy = dict(by_num[idx])
        else:
            copy = {
                "original_number": idx,
                "title": "Unknown",
                "source_line": f"missing track {idx}",
                "title_unknown_fallback": True,
            }
        copy["normalized_number"] = idx
        filled.append(copy)
    _emit(emit, f"WARN: {folder} | setlist skipped track number(s) {', '.join(str(n) for n in missing)}; filled missing title(s) as Unknown")
    return filled


def _filename_tracks_have_usable_titles(tracks: Sequence[Dict[str, object]], require_all: bool = True) -> bool:
    rows = list(tracks or [])
    if not rows:
        return False
    usable = [str(row.get("title", "")).strip().casefold() != "unknown" for row in rows]
    if require_all:
        return all(usable)
    return any(usable)


def _has_strong_numbered_track_run(tracks: Sequence[Dict[str, object]]) -> bool:
    rows = list(tracks or [])
    if len(rows) < 3:
        return False
    try:
        nums = [int(row.get("original_number", -9999)) for row in rows]
    except Exception:
        return False
    if not nums or not _numbered_track_start_allowed(nums[0]):
        return False
    consecutive_pairs = 0
    for prev, cur in zip(nums, nums[1:]):
        if cur == prev + 1 or _is_next_disc_or_set_prefixed_start(prev, cur):
            consecutive_pairs += 1
    return consecutive_pairs >= max(2, len(nums) - 2)


def _local_setlist_fallback_tracks(
    setlist_file: str,
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Dict[str, object]], str]:
    """Try local non-numbered setlist formats after numbered parsing fails.

    These fallbacks are count-gated and are also useful when a stray numbered
    venue/header line caused the primary parser to produce the wrong count.
    """
    section_tracks, section_source = parse_unnumbered_section_tracks(setlist_file, expected_count)
    if section_tracks:
        _emit(emit, f"INFO: {folder} | using unnumbered CD/Set section lines as track titles")
        return section_tracks, section_source
    line_tracks, line_source = parse_unstructured_unnumbered_tracks(setlist_file, expected_count)
    if line_tracks:
        _emit(emit, f"INFO: {folder} | using unnumbered one-title-per-line block as track titles")
        return line_tracks, line_source
    comma_tracks, comma_source = parse_unnumbered_comma_tracks(setlist_file, expected_count)
    if comma_tracks:
        if comma_source == "comma-items":
            _emit(emit, f"INFO: {folder} | using comma-separated items as track titles")
        else:
            _emit(emit, f"INFO: {folder} | using comma-separated lines as track titles")
        return comma_tracks, comma_source
    return [], ""


def _best_local_setlist_candidate_by_position(setlist_file: str) -> List[Dict[str, object]]:
    """Return the longest local title candidate for filling sparse unknowns.

    This does not choose the source for tagging by itself.  It is only used to
    fill a small number of unknown title-tag fallbacks when local evidence has a
    title at the same position.
    """
    candidates: List[List[Dict[str, object]]] = []
    numbered = parse_setlist_tracks(setlist_file)
    if numbered:
        candidates.append(numbered)
    try:
        text = _read_text(setlist_file) if setlist_file and os.path.isfile(setlist_file) else ""
    except Exception:
        text = ""
    if text and not setlist_text_requests_generated_from_music_files(text):
        # Include comma items even when their total is not an exact count.
        flat: List[Dict[str, object]] = []
        for raw_line in text.splitlines():
            items = _split_comma_track_items(str(raw_line or ""))
            for title in items:
                flat.append({
                    "original_number": len(flat) + 1,
                    "normalized_number": len(flat) + 1,
                    "title": title,
                    "source_line": raw_line,
                    "source": "comma-items",
                })
        if flat:
            candidates.append(flat)
    if not candidates:
        return []
    candidates.sort(key=lambda rows: len(rows), reverse=True)
    return candidates[0]


def _fill_unknown_title_tracks_from_position_candidate(
    tracks: Sequence[Dict[str, object]],
    candidate_tracks: Sequence[Dict[str, object]],
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    rows = [dict(row) for row in (tracks or [])]
    candidates = list(candidate_tracks or [])
    if not rows or not candidates or len(candidates) < len(rows):
        return rows
    filled: List[int] = []
    for idx, row in enumerate(rows):
        title = compact_ws(str(row.get("title", "")))
        if title and title.casefold() not in {"unknown", "untitled", "no title"}:
            continue
        if idx >= len(candidates):
            continue
        replacement = compact_ws(str(candidates[idx].get("title", "")))
        if not replacement or replacement.casefold() in {"unknown", "untitled", "no title", "?", "??"}:
            continue
        row["title"] = replacement
        row["source_line"] = candidates[idx].get("source_line", replacement)
        row["source"] = "title-tags+setlist-fill"
        filled.append(idx + 1)
    if filled:
        _emit(emit, f"WARN: {folder} | filled unknown title-tag track(s) {', '.join(str(n) for n in filled)} from local setlist position(s)")
    return rows


def _trim_probable_trailing_nontracks(
    tracks: Sequence[Dict[str, object]],
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Trim obvious prose accidentally parsed after a complete track list.

    A real missing-file mismatch such as setlist tracks 1-13 vs 12 audio files
    should still fall through to the last-resort title-tag path.  This only
    fixes cases where the first N tracks are a complete contiguous list matching
    the audio-file count and later prose is misread as a much larger track
    number, such as ``40 years...`` in collector notes.
    """
    expected = int(expected_count or 0)
    track_rows = list(tracks or [])
    if expected <= 0 or len(track_rows) <= expected:
        return track_rows
    head = track_rows[:expected]
    tail = track_rows[expected:]
    try:
        numbers = [int(row.get("original_number", -9999)) for row in head]
        tail_numbers = [int(row.get("original_number", -9999)) for row in tail]
    except Exception:
        return track_rows
    if not numbers or numbers[0] not in (0, 1):
        return track_rows
    if numbers != list(range(numbers[0], numbers[0] + expected)):
        return track_rows
    next_real = numbers[-1] + 1
    if any(num <= next_real + 3 for num in tail_numbers):
        return track_rows
    _emit(
        emit,
        f"WARN: {folder} | setlist contained {len(track_rows)} parseable track-like line(s) "
        f"for {expected} audio file(s); ignored {len(tail)} probable non-track note/prose line(s) after the complete track list",
    )
    trimmed: List[Dict[str, object]] = []
    for idx, row in enumerate(head, start=1):
        copy = dict(row)
        copy["normalized_number"] = idx
        trimmed.append(copy)
    return trimmed


def _looks_like_short_consecutive_numbered_run(tracks: Sequence[Dict[str, object]]) -> bool:
    rows = list(tracks or [])
    if len(rows) < 2:
        return False
    try:
        nums = [int(row.get("original_number", -9999)) for row in rows]
    except Exception:
        return False
    if not nums or not _numbered_track_start_allowed(nums[0]):
        return False
    return all(cur == prev + 1 or _is_next_disc_or_set_prefixed_start(prev, cur) for prev, cur in zip(nums, nums[1:]))


def _strong_numbered_partial_tracks_to_expected_count(
    tracks: Sequence[Dict[str, object]],
    expected_count: int,
    folder: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, object]]:
    """Pad a strong but short local numbered setlist with Unknown rows.

    Some folders have more audio files than listed songs because the audio adds
    intro, crowd, tuning, or banter tracks.  When the local setlist is already a
    strong numbered run, preserve the known titles instead of discarding them and
    mark only the unlisted tail tracks as Unknown.  Do not truncate long setlists
    here; a long setlist may indicate an unsafe offset or extra listed encore.
    """
    expected = int(expected_count or 0)
    rows = [dict(row) for row in (tracks or [])]
    if expected <= 0 or not rows or len(rows) >= expected:
        return rows
    if not (_has_strong_numbered_track_run(rows) or _looks_like_short_consecutive_numbered_run(rows)):
        return rows
    padded = _renormalize_track_rows(rows)
    for idx in range(len(padded) + 1, expected + 1):
        padded.append({
            "original_number": idx,
            "normalized_number": idx,
            "title": "Unknown",
            "source_line": "(no local setlist title for this audio file)",
            "source": "setlist-partial",
            "title_unknown_fallback": True,
        })
    _emit(
        emit,
        f"WARN: {folder} | found a strong numbered setlist run with {len(rows)} title row(s) "
        f"for {expected} audio file(s); using listed titles and marking {expected - len(rows)} unmatched audio file(s) Unknown",
    )
    return padded


def _select_tracks_for_tagging(
    config: Config,
    group: dict,
    audio_files: Sequence[str],
    emit: Optional[Callable[[str], None]] = None,
    fallback_to_filenames_on_track_problem: bool = False,
    fallback_to_title_tags_on_track_problem: bool = False,
    record=None,
) -> Tuple[List[Dict[str, object]], str, Optional[str]]:
    folder = _folder_label(group)
    setlist_file = group.get("setlist_file", "") or ""
    if setlist_file:
        tracks = parse_setlist_tracks(setlist_file)
        if tracks and len(tracks) != len(audio_files):
            tracks = _coerce_tracks_to_expected_count(tracks, len(audio_files), folder, emit=emit)
        if tracks and len(tracks) != len(audio_files):
            tracks = _trim_probable_trailing_nontracks(tracks, len(audio_files), folder, emit=emit)
        if tracks and len(tracks) != len(audio_files):
            tracks = _fill_missing_numbered_track_rows_from_filenames(tracks, audio_files, len(audio_files), folder, emit=emit)
        if tracks and len(tracks) != len(audio_files):
            tracks = _fill_missing_numbered_track_rows(tracks, len(audio_files), folder, emit=emit)
        if tracks and len(tracks) != len(audio_files):
            tracks = _strong_numbered_partial_tracks_to_expected_count(tracks, len(audio_files), folder, emit=emit)
        if tracks and len(tracks) == len(audio_files):
            return tracks, "setlist", None
        if tracks and _has_strong_numbered_track_run(tracks):
            _emit(emit, f"WARN: {folder} | found a strong numbered setlist run with {len(tracks)} row(s) for {len(audio_files)} audio file(s); not using unnumbered prose fallback")
        else:
            fallback_tracks, fallback_source = _local_setlist_fallback_tracks(setlist_file, len(audio_files), folder, emit=emit)
            if fallback_tracks:
                return fallback_tracks, fallback_source, None

        etree_tracks = tracks_from_etreedb_setlist(config, record, len(audio_files), folder, emit=emit)
        if etree_tracks:
            return etree_tracks, "etreedb", None

        setlistfm_tracks = tracks_from_cached_setlistfm_setlist(record, len(audio_files), folder, emit=emit)
        if setlistfm_tracks:
            return setlistfm_tracks, "setlist.fm", None

        if fallback_to_filenames_on_track_problem or fallback_to_title_tags_on_track_problem:
            if not tracks:
                reason = f"no parseable tracks in setlist: {setlist_file}"
            else:
                reason = f"track count mismatch: setlist={len(tracks)} audio_files={len(audio_files)}"
            if fallback_to_filenames_on_track_problem:
                filename_tracks, filename_source = tracks_from_audio_filenames_confirmed_by_setlist(audio_files, setlist_file)
                if filename_tracks:
                    _emit(emit, f"INFO: {folder} | {reason}; using filename-derived track titles confirmed by setlist text")
                    return filename_tracks, filename_source, None
            fallback_tracks, fallback_source, fallback_error = _title_tag_fallback_tracks(
                audio_files,
                folder,
                reason,
                emit=emit,
                require_any_usable=fallback_to_title_tags_on_track_problem and not fallback_to_filenames_on_track_problem,
            )
            if fallback_tracks:
                position_candidate = _best_local_setlist_candidate_by_position(setlist_file)
                fallback_tracks = _fill_unknown_title_tracks_from_position_candidate(fallback_tracks, position_candidate, folder, emit=emit)
            return fallback_tracks, fallback_source, fallback_error
        if not tracks:
            return [], "", f"no parseable tracks in setlist: {setlist_file}"
        return [], "", f"track count mismatch: setlist={len(tracks)} audio_files={len(audio_files)}"

    etree_tracks = tracks_from_etreedb_setlist(config, record, len(audio_files), folder, emit=emit)
    if etree_tracks:
        return etree_tracks, "etreedb", None

    setlistfm_tracks = tracks_from_cached_setlistfm_setlist(record, len(audio_files), folder, emit=emit)
    if setlistfm_tracks:
        return setlistfm_tracks, "setlist.fm", None

    if fallback_to_filenames_on_track_problem:
        filename_tracks = tracks_from_audio_filenames(audio_files)
        if _filename_tracks_have_usable_titles(filename_tracks, require_all=True):
            _emit(emit, f"INFO: {folder} | no setlist found; using filename-derived track titles")
            return filename_tracks, "filenames", None
        return _title_tag_fallback_tracks(audio_files, folder, "no setlist found", emit=emit)

    tracks = tracks_from_audio_filenames(audio_files)
    if fallback_to_title_tags_on_track_problem and not _filename_tracks_have_usable_titles(tracks, require_all=True):
        fallback_tracks, fallback_source, fallback_error = _title_tag_fallback_tracks(
            audio_files,
            folder,
            "no setlist found",
            emit=emit,
            require_any_usable=True,
        )
        if fallback_tracks:
            return fallback_tracks, fallback_source, fallback_error
    if not tracks:
        return [], "", "no audio files found for filename-based track fallback"
    _emit(emit, f"INFO: {folder} | no setlist found; using filename-derived track titles")
    return tracks, "filenames", None


def tag_group_with_record(
    config: Config,
    group: dict,
    record,
    emit: Optional[Callable[[str], None]] = None,
    allow_unknown_metadata: bool = False,
    fallback_to_filenames_on_track_problem: bool = False,
    fallback_to_title_tags_on_track_problem: bool = False,
    metadata_problems: Optional[Sequence[str]] = None,
    meta_log_entry: str = "",
) -> Dict[str, int]:
    """Tag one already-discovered inventory/tagger group.

    The standalone tagger requires usable metadata but can now use existing
    audio title tags as a final title source when setlist titles are missing or
    count-mismatched. Inventory-time tagging remains more permissive: it can use
    Unknown for artist/album when no show name is available and can fall back to
    filename titles when setlist titles cannot be used.
    """
    folder = _folder_label(group)
    stats = {"groups": 1, "tagged": 0, "skipped": 0, "errors": 0, "comma_item_folders": [], "comma_line_folders": [], "etreedb_folders": [], "title_tag_folders": [], "setlistfm_folders": []}
    if is_cancel_requested():
        stats["skipped"] += 1
        _problem(folder, "cancel requested", emit)
        return stats

    problems = list(metadata_problems or [])
    if problems and not allow_unknown_metadata:
        stats["skipped"] += 1
        reason = _safe_message_parts(problems)
        _problem(folder, reason, emit)
        return stats

    album = _album_for_record(config, record)
    artist = compact_ws(getattr(record, "artist", ""))
    show_name = compact_ws(getattr(record, "show_name", ""))

    if allow_unknown_metadata:
        if not show_name:
            if problems:
                _emit(emit, f"WARN: {folder} | {_safe_message_parts(problems)}")
            _emit(emit, f"WARN: {folder} | show name not determined; tagging artist and album as Unknown")
            artist = "Unknown"
            album = "Unknown"
        else:
            if not artist:
                _emit(emit, f"WARN: {folder} | artist not determined; tagging artist as Unknown")
                artist = "Unknown"
            if not album:
                _emit(emit, f"WARN: {folder} | album metadata not determined; tagging album as Unknown")
                album = "Unknown"
    else:
        metadata_problems = []
        if not artist:
            metadata_problems.append("artist not found")
        if not album:
            metadata_problems.append("album metadata not found")
        if metadata_problems:
            stats["skipped"] += 1
            reason = _safe_message_parts(metadata_problems)
            _problem(folder, reason, emit)
            return stats

    raw_audio_files = _rescan_group_audio_files(group)
    shn_count = sum(1 for path_name in raw_audio_files if _is_shn_audio_file(path_name))
    if shn_count:
        _emit(emit, f"INFO: {folder} | SHN files detected: {shn_count}; convert shn={'yes' if bool(getattr(config, 'convert_shn', False)) else 'no'}")
    audio_files, conversion_errors = _prepare_audio_files_for_tagging(config, group, raw_audio_files, emit=emit)
    remaining_shn_after_prepare = [path_name for path_name in audio_files if _is_shn_audio_file(path_name)]
    if remaining_shn_after_prepare and bool(getattr(config, "convert_shn", False)):
        stats["errors"] += len(remaining_shn_after_prepare)
        for shn_path in remaining_shn_after_prepare:
            _emit(emit, _format_tag_file_error_line(shn_path, "convert shn is enabled, but the file remained SHN after conversion preparation; skipping non-taggable source"))
        remaining_keys = {os.path.normpath(path).casefold() for path in remaining_shn_after_prepare}
        audio_files = [path for path in audio_files if os.path.normpath(path).casefold() not in remaining_keys]
        group["music_files"] = list(audio_files)
    if conversion_errors:
        stats["errors"] += conversion_errors
    tracks, track_source, track_error = _select_tracks_for_tagging(
        config,
        group,
        audio_files,
        emit=emit,
        fallback_to_filenames_on_track_problem=fallback_to_filenames_on_track_problem,
        fallback_to_title_tags_on_track_problem=fallback_to_title_tags_on_track_problem,
        record=record,
    )
    if track_error:
        stats["skipped"] += 1
        _problem(folder, track_error, emit)
        setlist_for_debug = str(group.get("setlist_file", "") or getattr(record, "setlist_file", "") or "")
        if setlist_for_debug and os.path.isfile(setlist_for_debug):
            _write_tag_debug_setlist_copy(
                config,
                group,
                record,
                reason="TAG_SKIP: " + str(track_error),
                tracks=(),
                track_source=track_source,
                audio_files=audio_files,
                meta_log_entry=meta_log_entry,
                emit=emit,
            )
        return stats

    if track_source == "comma-items":
        stats["comma_item_folders"].append(folder)
    elif track_source == "comma-lines":
        stats["comma_line_folders"].append(folder)
    elif track_source == "etreedb":
        stats["etreedb_folders"].append(folder)
    elif track_source == "setlist.fm":
        stats["setlistfm_folders"].append(folder)
    elif track_source == "title-tags":
        stats["title_tag_folders"].append(folder)

    # Do not create TLOHome/debug setlist copies merely because one or
    # more song titles are written as Unknown.  Unknown titles are already
    # logged through WARN_TITLE_PARTIAL / WARN_TITLE_FALLBACK lines, while
    # debug copies remain reserved for skipped title-selection problems that
    # have an actual setlist file to inspect.

    for audio_path, track in zip(audio_files, tracks):
        if is_cancel_requested():
            stats["skipped"] += 1
            _emit(emit, f"CANCELLED: {folder} | stopping before {os.path.basename(audio_path)}")
            break
        normalized_number = int(track["normalized_number"])
        tag_track_number = format_tag_track_number(normalized_number, len(tracks))
        title = _clean_track_title(str(track.get("title") or "unknown")) or "unknown"
        if _is_shn_audio_file(audio_path):
            stats["errors"] += 1
            if bool(getattr(config, "convert_shn", False)):
                error_text = "SHN reached tag writer even though convert shn is enabled; skipping non-taggable source"
            else:
                error_text = "SHN is not directly taggable; enable Convert shn to convert before tagging"
            _emit(emit, _format_tag_file_error_line(audio_path, error_text))
            continue
        try:
            write_audio_tags(audio_path, artist, album, tag_track_number, title, total_tracks=len(tracks))
            stats["tagged"] += 1
        except Exception as exc:
            stats["errors"] += 1
            error_text = _normalize_tag_write_error(audio_path, exc)
            record_corrupt_flac(config, audio_path)
            _emit(emit, _format_tag_file_error_line(audio_path, error_text))
    return stats


def process_tagging_group(
    config: Config,
    group: dict,
    artist_matcher,
    emit: Optional[Callable[[str], None]] = None,
) -> Dict[str, int]:
    folder = _folder_label(group)
    stats = {"groups": 1, "tagged": 0, "skipped": 0, "errors": 0, "comma_item_folders": [], "comma_line_folders": [], "etreedb_folders": [], "title_tag_folders": [], "setlistfm_folders": []}
    if is_cancel_requested():
        stats["skipped"] += 1
        _problem(folder, "cancel requested", emit)
        return stats

    try:
        record, _date_matches, unresolved_reasons = _extract_metadata_for_group(config, group, artist_matcher)
    except Exception as exc:
        stats["errors"] += 1
        _problem(folder, f"metadata extraction failed: {exc}", emit)
        return stats

    album = _album_for_record(config, record)
    metadata_problems = []
    if not compact_ws(getattr(record, "artist", "")):
        metadata_problems.append("artist not found")
    if not album:
        metadata_problems.append("album metadata not found")
    if unresolved_reasons:
        metadata_problems.extend(unresolved_reasons)

    if metadata_problems:
        # Do not copy, move, rename, or tag an unidentified standalone tagger
        # group.  Report the metadata problem against the original folder and
        # leave the source tree untouched.
        return tag_group_with_record(
            config,
            group,
            record,
            emit=emit,
            allow_unknown_metadata=False,
            fallback_to_filenames_on_track_problem=False,
            fallback_to_title_tags_on_track_problem=True,
            metadata_problems=metadata_problems,
        )

    if bool(getattr(config, "tag_copy_during_inventory", False)) or bool(getattr(config, "rename_compliantly", False)):
        try:
            group, record = prepare_inventory_tagging_target(config, group, record, emit=emit)
            folder = _folder_label(group)
        except Exception as exc:
            stats["errors"] += 1
            _problem(folder, f"tag target preparation failed: {exc}", emit)
            return stats

    return tag_group_with_record(
        config,
        group,
        record,
        emit=emit,
        allow_unknown_metadata=False,
        fallback_to_filenames_on_track_problem=False,
        fallback_to_title_tags_on_track_problem=True,
        metadata_problems=metadata_problems,
    )



TAG_STATS_NUMERIC_KEYS = ("groups", "tagged", "skipped", "errors")
TAG_STATS_LIST_KEYS = ("comma_item_folders", "comma_line_folders", "etreedb_folders", "setlistfm_folders", "title_tag_folders")


def empty_tag_stats() -> Dict[str, object]:
    return {"groups": 0, "tagged": 0, "skipped": 0, "errors": 0, "comma_item_folders": [], "comma_line_folders": [], "etreedb_folders": [], "title_tag_folders": [], "setlistfm_folders": []}


def merge_tag_stats(totals: Dict[str, object], subtotal: Dict[str, object]) -> Dict[str, object]:
    for key in TAG_STATS_NUMERIC_KEYS:
        totals[key] = int(totals.get(key, 0) or 0) + int(subtotal.get(key, 0) or 0)
    for key in TAG_STATS_LIST_KEYS:
        bucket = totals.setdefault(key, [])
        if not isinstance(bucket, list):
            bucket = []
            totals[key] = bucket
        for item in subtotal.get(key, []) or []:
            if item and item not in bucket:
                bucket.append(item)
    return totals


def emit_tag_fallback_summary(totals: Dict[str, object], emit: Optional[Callable[[str], None]]) -> None:
    comma_items = list(totals.get("comma_item_folders", []) or [])
    comma_lines = list(totals.get("comma_line_folders", []) or [])
    etreedb = list(totals.get("etreedb_folders", []) or [])
    setlistfm = list(totals.get("setlistfm_folders", []) or [])
    title_tags = list(totals.get("title_tag_folders", []) or [])
    if comma_items:
        _emit(emit, "SUMMARY: comma-separated setlist items used for track titles in " + str(len(comma_items)) + " folder(s): " + "; ".join(comma_items))
    if comma_lines:
        _emit(emit, "SUMMARY: comma-separated setlist lines used as track titles in " + str(len(comma_lines)) + " folder(s): " + "; ".join(comma_lines))
    if etreedb:
        _emit(emit, "SUMMARY: eTreeDB setlist titles used for tagging in " + str(len(etreedb)) + " folder(s): " + "; ".join(etreedb))
    if setlistfm:
        _emit(emit, "SUMMARY: cached setlist.fm setlist titles used for tagging in " + str(len(setlistfm)) + " folder(s): " + "; ".join(setlistfm))
    if title_tags:
        _emit(emit, "SUMMARY: existing audio title tags used as last-resort track titles in " + str(len(title_tags)) + " folder(s): " + "; ".join(title_tags))


def emit_tag_problem_summary(config: Config, emit: Optional[Callable[[str], None]]) -> None:
    counts = {}
    try:
        counts = dict(getattr(getattr(config, "logs", None), "tag_reason_counts", {}) or {})
    except Exception:
        counts = {}
    if not counts:
        return
    try:
        setattr(getattr(config, "logs", None), "_emitting_tag_reason_summary", True)
    except Exception:
        pass
    _emit(emit, "WARN_SUMMARY: tagging problem summary by reason code")
    for code in sorted(counts):
        _emit(emit, f"WARN_SUMMARY: {code}: {counts[code]}")
    try:
        setattr(getattr(config, "logs", None), "_emitting_tag_reason_summary", False)
    except Exception:
        pass

def _append_tag_log_line(config: Config, log_line: str) -> None:
    """Append one line directly to the active success/error tag log.

    Standalone/GUI tagging creates tagsT.txt and tageT.txt through LogManager.
    Direct append keeps progress logging deterministic and mirrors the same
    success/error split used by inventory-time tagging.
    """
    try:
        paths = getattr(getattr(config, "logs", None), "paths", None)
        if paths is None:
            return
        log_path = getattr(paths, "tag_error", "") if _tag_output_line_is_error(log_line) else getattr(paths, "tag_success", "")
        if not log_path:
            return
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        if log_path == getattr(paths, "tag_error", ""):
            recorder = getattr(getattr(config, "logs", None), "record_tag_reason_line", None)
            if callable(recorder):
                recorder(log_line)
        with open(log_path, "a", encoding="utf-8", newline="") as outfile:
            outfile.write(str(log_line or "") + "\n")
    except Exception:
        # Tag logging must never stop a tagging run or GUI update.
        pass


def _build_tag_log_emit(config: Config, emit: Optional[Callable[[str], None]]) -> Callable[[str], None]:
    """Return an emit callback that mirrors tagger output to tagsN.txt/tageN.txt."""
    def tag_emit(text: str) -> None:
        line = str(text or "")
        if emit is None:
            console_emit(line, end="" if line.endswith("\n") else "\n")
        else:
            emit(line if line.endswith("\n") else line + "\n")
        for log_line in (line.rstrip("\r\n").splitlines() or [""]):
            _append_tag_log_line(config, log_line)
    return tag_emit


def run_tagger(
    tlo_home: str = "",
    my_tlo: str = "",
    compliant: bool = False,
    tag_path: str = "",
    etree_lookup: bool = False,
    debug: bool = False,
    tag_in_place: bool = True,
    tag_copy: bool = False,
    tag_copy_destination: str = "",
    rename_compliantly: bool = False,
    convert_shn: bool = False,
    emit: Optional[Callable[[str], None]] = None,
) -> Dict[str, int]:
    clear_cancel_request()
    config = build_tagger_config(
        tlo_home=tlo_home,
        my_tlo=my_tlo,
        compliant=compliant,
        etree_lookup=etree_lookup,
        debug=debug,
        tag_in_place=tag_in_place,
        tag_copy=tag_copy,
        tag_copy_destination=tag_copy_destination,
        rename_compliantly=rename_compliantly,
        convert_shn=convert_shn,
    )
    ensure_corrupt_flacs_log(config)
    tagging_path = resolve_tagging_path(config.TLOHome, tag_path=tag_path)
    validate_required_databases(config)
    setup_logging(config)
    config.current_search_path = os.path.normpath(tagging_path)
    config.current_search_index = 1
    config.current_slam = ""
    config.current_volume_label = ""
    config.current_volume_key = ""
    config.current_log_token = "T"
    config.logs.start_search_path(config.current_search_path, config.current_search_index, log_token=config.current_log_token)
    tag_emit = _build_tag_log_emit(config, emit)
    artist_matcher = load_artist_matcher(config)

    tag_mode = "copy" if bool(getattr(config, "tag_copy_during_inventory", False)) else "in-place"
    _emit(tag_emit, f"Starting TLO Tagger | compliant={'yes' if config.compliant else 'no'} | etreeDB fallback={'yes' if config.etree_lookup else 'no'} | tag mode={tag_mode} | rename compliantly={'yes' if config.rename_compliantly else 'no'} | convert shn={'yes' if config.convert_shn else 'no'} | debug={'yes' if config.debug else 'no'}")
    _emit(tag_emit, f"TLOHome: {config.TLOHome}")
    _emit(tag_emit, f"Tagging Path: {tagging_path}")
    if bool(getattr(config, "tag_copy_during_inventory", False)):
        _emit(tag_emit, f"Tag Copy Destination: {config.tag_copy_destination}")

    groups = _groups_from_inventory_discovery(config, tagging_path)
    if not groups:
        _emit(tag_emit, "No folders with audio files were found.")
        return empty_tag_stats()

    totals = empty_tag_stats()
    for idx, group in enumerate(groups, start=1):
        if is_cancel_requested():
            _emit(tag_emit, "Tagger cancelled.")
            break
        group["group_number"] = idx
        subtotal = process_tagging_group(config, group, artist_matcher, emit=tag_emit)
        merge_tag_stats(totals, subtotal)

    emit_tag_fallback_summary(totals, tag_emit)
    emit_tag_problem_summary(config, tag_emit)
    _emit(tag_emit, f"Complete: folders={totals['groups']} tagged_files={totals['tagged']} skipped_folders={totals['skipped']} file_errors={totals['errors']}")
    return totals
