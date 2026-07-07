__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.

import csv
import glob
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from tlo_artist_db import load_artist_matcher, lookup_artist_master_with_status, match_line_to_artists
from logging_lib import setup_logging
from tlo_db_validation import validate_required_databases
from tlo_audio_tags import collect_group_flac_tag_info
from tlo_media_rules import MEDIA_EXTENSIONS
from tlo_phase23_v2 import _extract_metadata_for_group, _find_date_matches, _match_string_dash_string, _string_date_matches, _compliant_string_date_matches
from tlo_postprocess import (
    _adjust_show_name_for_output,
    _export_combined_setlist_text,
    _format_bootlist_volume_path,
    _normalized_setlist_base,
    _setlist_base_from_record,
    _unique_setlist_filename,
    _write_text_file,
)
from tlo_setlist_file_selection import find_setlist_files_for_music_dir
from tlo_text_utils import normalized_compare_value
from tlo_version import versioned_title


BOOTLIST_HEADER = ["Show", "VolumePath"]
UPDATER_TITLE = "Traders Little Helper™ Inventory Update App"
UPDATER_DISPLAY_VERSION = versioned_title("TLO Inventory Updater")
INVALID_FOLDER_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')


class InventoryUpdateError(RuntimeError):
    pass


def prepare_updater_config(config):
    """Populate and validate TLOHome-derived paths needed by the updater workflow.

    The full inventory path calls setup_logging() before loading artist/venue
    databases.  The Add to Inventory GUI path builds the same Config object,
    but does not run the full inventory bootstrap.  This helper keeps the
    updater from reaching load_artist_matcher() with blank database paths.
    """
    if config is None:
        raise InventoryUpdateError("Updater configuration is missing.")
    if not getattr(config, "logs", None) or not getattr(config, "artist_sqlite_db_file", "") or not getattr(config, "venue_reference_db_file", ""):
        setup_logging(config)
    validate_required_databases(config)
    return config


def updater_delete_script_path(tlo_home: str) -> str:
    suffix = ".bat" if os.name == "nt" or platform.system().casefold().startswith("win") else ".sh"
    return os.path.join(tlo_home, f"deleteBackupFolders{suffix}")


def updater_directories(tlo_home: str) -> Dict[str, str]:
    return {
        "ready": os.path.join(tlo_home, "readyForXfer"),
        "dups": os.path.join(tlo_home, "dups"),
        "staged": os.path.join(tlo_home, "staged"),
        "setlists": os.path.join(tlo_home, "setlists"),
    }


def ensure_updater_directories(tlo_home: str) -> Dict[str, str]:
    dirs = updater_directories(tlo_home)
    for path_name in dirs.values():
        os.makedirs(path_name, exist_ok=True)
    return dirs


def _iter_top_level_dirs(path_name: str) -> List[str]:
    if not os.path.isdir(path_name):
        return []
    out: List[str] = []
    with os.scandir(path_name) as entries:
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    out.append(entry.path)
            except OSError:
                continue
    return sorted(out, key=lambda value: os.path.basename(value).casefold())


def _should_prune_dir(dirname: str) -> bool:
    name = str(dirname or "").strip().lower()
    return name.endswith("-ignoredir") or name in {"$recycle.bin", "system volume information", "__pycache__"}


def _collect_folder_paths(folder_path: str) -> Tuple[List[str], List[str], List[str]]:
    """Return all file paths, music files, and music directories for one candidate folder."""
    all_paths: List[str] = []
    music_files: List[str] = []
    music_dirs_seen = set()
    music_dirs: List[str] = []
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [dirname for dirname in dirs if not _should_prune_dir(dirname)]
        for filename in sorted(files, key=lambda value: value.casefold()):
            path_name = os.path.join(root, filename)
            all_paths.append(path_name)
            if os.path.splitext(filename)[1].lower() in MEDIA_EXTENSIONS:
                music_files.append(path_name)
                key = os.path.normcase(os.path.normpath(root))
                if key not in music_dirs_seen:
                    music_dirs_seen.add(key)
                    music_dirs.append(os.path.normpath(root))
    return sorted(all_paths, key=lambda value: value.casefold()), sorted(music_files, key=lambda value: value.casefold()), sorted(music_dirs, key=lambda value: value.casefold())


def _safe_first_txt(all_paths: Sequence[str]) -> str:
    txts = [p for p in all_paths if os.path.splitext(p)[1].lower() in {".txt", ".nfo"}]
    if not txts:
        return ""
    def sort_key(path_name: str) -> Tuple[int, str]:
        base = os.path.basename(path_name).casefold()
        priority = 0 if base == "info.txt" else 1
        return priority, path_name.casefold()
    return sorted(txts, key=sort_key)[0]


def _build_single_folder_group(config, folder_path: str) -> dict:
    folder_path = os.path.normpath(folder_path)
    all_paths, music_files, music_dirs = _collect_folder_paths(folder_path)
    if not music_dirs:
        music_dirs = [folder_path]

    setlist_files: List[str] = []
    for music_dir in music_dirs:
        setlist_files.extend(find_setlist_files_for_music_dir(all_paths, music_dir, folder_path))
    seen = set()
    unique_setlists: List[str] = []
    for item in setlist_files:
        key = os.path.normcase(os.path.normpath(item))
        if key not in seen:
            seen.add(key)
            unique_setlists.append(os.path.normpath(item))
    if not unique_setlists:
        fallback = _safe_first_txt(all_paths)
        if fallback:
            unique_setlists.append(os.path.normpath(fallback))

    group = {
        "group_number": 1,
        "main_dir_path": folder_path,
        "main_dir_name": os.path.basename(folder_path),
        "music_dirs": music_dirs,
        "music_files": music_files,
        "txt_files": unique_setlists,
        "setlist_files": unique_setlists,
        "setlist_file": unique_setlists[0] if unique_setlists else "",
        "music_file_count": len(music_files),
        "aggregate_album_name": "",
        "aggregate_release_base": "",
        "aggregation_reason": "add_to_inventory_folder",
    }
    if not getattr(config, "compliant", False) and music_files:
        group.update(collect_group_flac_tag_info(music_files))
    else:
        group.update({
            "flac_tag_samples": [],
            "flac_tag_artist_values": [],
            "flac_tag_album_values": [],
            "flac_tag_albumartist_values": [],
            "flac_tag_date_values": [],
        })
    return group


def _metadata_to_record_dict(record) -> Dict[str, str]:
    data = asdict(record)
    out = {
        "show_name": data.get("show_name", "") or "",
        "setlist_file": data.get("setlist_file", "") or "",
        "volume_label": data.get("volume_label", "") or "",
        "artist": data.get("artist", "") or "",
        "date": data.get("date", "") or "",
        "venue": data.get("venue", "") or "",
        "location": data.get("location", "") or "",
        "parentheticals": data.get("parentheticals", "") or "",
        "album_name": data.get("album_name", "") or "",
        "main_dir_path": data.get("main_dir_path", "") or "",
        "show_in_conflict": "yes" if data.get("show_in_conflict") else "no",
        "setlist_files_json": json.dumps(data.get("setlist_files", []) or [], ensure_ascii=False),
        "music_dirs_json": json.dumps(data.get("music_dirs", []) or [], ensure_ascii=False),
    }
    _adjust_show_name_for_output(out)
    return out


def identify_folder(config, folder_path: str, artist_matcher=None):
    prepare_updater_config(config)
    matcher = artist_matcher or load_artist_matcher(config)
    old_current = getattr(config, "current_search_path", "")
    old_volume = getattr(config, "current_volume_label", "")
    try:
        config.current_search_path = os.path.normpath(folder_path)
        group = _build_single_folder_group(config, folder_path)
        group["volume_label"] = old_volume or ""
        record, _date_matches, _unresolved = _extract_metadata_for_group(config, group, matcher)
        return record
    finally:
        config.current_search_path = old_current


def identify_folder_dict(config, folder_path: str, artist_matcher=None) -> Dict[str, str]:
    return _metadata_to_record_dict(identify_folder(config, folder_path, artist_matcher=artist_matcher))


def bootlist_path(tlo_home: str) -> str:
    return os.path.join(tlo_home, "bootlist.csv")


def read_bootlist(tlo_home: str) -> List[Dict[str, str]]:
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
            if first_data and row[0].strip().casefold() in {"show", "show name"}:
                first_data = False
                continue
            first_data = False
            show = (row[0] if len(row) >= 1 else "").strip()
            if not show:
                continue
            if len(row) >= 4:
                volume = (row[2] or "").strip()
                path = (row[3] or "").strip()
                volume_path = _format_bootlist_volume_path(volume, path)
            else:
                volume_path = (row[1] if len(row) >= 2 else "").strip()
            rows.append({"Show": show, "VolumePath": volume_path})
    return rows


def write_bootlist(tlo_home: str, rows: List[Dict[str, str]]) -> str:
    path_name = bootlist_path(tlo_home)
    rows_out = sorted(rows, key=lambda row: ((row.get("Show") or "").casefold(), (row.get("VolumePath") or "").casefold()))
    with open(path_name, "w", encoding="utf-8", newline="") as outfile:
        outfile.write("sep=^\n")
        outfile.write("Show^VolumePath\n")
        writer = csv.writer(outfile, delimiter="^", lineterminator="\n")
        for row in rows_out:
            writer.writerow([(row.get("Show") or "").strip(), (row.get("VolumePath") or "").strip()])
    return path_name


def _normalized_dates_in_show(show_name: str) -> set:
    values = set()
    text = show_name or ""
    for match in _find_date_matches(text):
        normalized = match.get("normalized", "") or ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
            values.add(normalized)
    return values


def _show_has_date(show_name: str, date: str) -> bool:
    show = show_name or ""
    date_value = date or ""
    if not date_value:
        return False
    if date_value in show:
        return True
    return date_value in _normalized_dates_in_show(show)


def _artist_values_for_duplicate_check(artist: str, artist_matcher=None, extra_values: Optional[Sequence[str]] = None) -> List[str]:
    values: List[str] = []
    seen = set()

    def add(value: str) -> None:
        cleaned = str(value or "").strip()
        key = normalized_compare_value(cleaned)
        if cleaned and key and key not in seen:
            seen.add(key)
            values.append(cleaned)

    add(artist)
    for value in extra_values or []:
        add(value)

    if artist_matcher is not None:
        for probe in [artist] + list(extra_values or []):
            cleaned_probe = str(probe or "").strip()
            if not cleaned_probe:
                continue
            status, masters = lookup_artist_master_with_status(cleaned_probe, artist_matcher)
            if status in {"matched", "collision"}:
                for master in masters:
                    add(master)
                    for alias in getattr(artist_matcher, "master_aliases", {}).get(master, []):
                        add(alias)
            for master, phrase in match_line_to_artists(cleaned_probe, artist_matcher):
                add(master)
                add(phrase)
                for alias in getattr(artist_matcher, "master_aliases", {}).get(master, []):
                    add(alias)
    return values


def _show_has_artist_and_date(show_name: str, artist: str, date: str, artist_matcher=None, extra_artist_values: Optional[Sequence[str]] = None) -> bool:
    show = show_name or ""
    if not _show_has_date(show, date):
        return False
    artist_values = _artist_values_for_duplicate_check(artist, artist_matcher, extra_artist_values)
    return _show_matches_any_artist_value(show, artist_values)


def find_potential_duplicate_rows(tlo_home: str, artist: str, date: str, artist_matcher=None, extra_artist_values: Optional[Sequence[str]] = None) -> List[Dict[str, str]]:
    return [
        row for row in read_bootlist(tlo_home)
        if _show_has_artist_and_date(row.get("Show", ""), artist, date, artist_matcher, extra_artist_values)
    ]


def _norm_contains_either(left: str, right: str) -> bool:
    left_norm = normalized_compare_value(left)
    right_norm = normalized_compare_value(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    return left_norm in right_norm or right_norm in left_norm


def _compliant_string_date_string2(folder_path: str) -> Optional[Dict[str, str]]:
    """Return the best compliant String1 Date String2 row for one folder leaf."""
    leaf = os.path.basename(os.path.normpath(folder_path))
    matches = _compliant_string_date_matches(leaf, allow_string2=False)
    if not matches:
        return None
    row = dict(matches[0])
    row["folder_leaf"] = leaf
    return row


def _compliant_string_dash_string2(folder_path: str) -> Optional[Dict[str, str]]:
    """Return compliant String1 - String2 information for one folder leaf.

    This is intentionally checked only after String1 Date String2 fails.  In
    compliant Add to Inventory mode, String1 is the artist and the show name is
    the literal ``String1 - String2`` value.  Duplicate detection for this
    branch is by show-name match only, not by artist/date.
    """
    leaf = os.path.basename(os.path.normpath(folder_path))
    row = _match_string_dash_string(leaf)
    if not row:
        return None
    show_name = f"{row.get('string1', '').strip()} - {row.get('string2', '').strip()}".strip()
    if not show_name or show_name == "-":
        return None
    out = dict(row)
    out["folder_leaf"] = leaf
    out["show_name"] = show_name
    out["artist"] = row.get("string1", "").strip()
    return out


def _bootlist_show_name_matches(tlo_home: str, show_name: str) -> List[Dict[str, str]]:
    """Return bootlist rows whose first column matches a show name."""
    target = normalized_compare_value(show_name)
    if not target:
        return []
    return [
        row for row in read_bootlist(tlo_home)
        if normalized_compare_value(row.get("Show", "")) == target
    ]


def _artist_values_for_compliant_string1(string1: str, artist_matcher) -> List[str]:
    values: List[str] = []
    seen = set()

    def add(value: str) -> None:
        cleaned = str(value or "").strip()
        key = normalized_compare_value(cleaned)
        if cleaned and key and key not in seen:
            seen.add(key)
            values.append(cleaned)

    status, masters = lookup_artist_master_with_status(string1, artist_matcher)
    if status in {"matched", "collision"}:
        for master in masters:
            add(master)
            add(string1)
            for alias in getattr(artist_matcher, "master_aliases", {}).get(master, []):
                add(alias)

    # The Add to Inventory compliant path is often fed real-world folder names
    # where String1 is not an exact DB term but contains one, such as extra
    # site/source text plus an artist.  Use the same artist-line scanning helper
    # that the full metadata engine uses before declaring the folder new.
    for master, phrase in match_line_to_artists(string1, artist_matcher):
        add(master)
        add(phrase)
        add(string1)
        for alias in getattr(artist_matcher, "master_aliases", {}).get(master, []):
            add(alias)

    return values


def _show_matches_any_artist_value(show_name: str, values: Sequence[str]) -> bool:
    show_norm = normalized_compare_value(show_name)
    if not show_norm:
        return False
    for value in values:
        value_norm = normalized_compare_value(value)
        if not value_norm:
            continue
        if value_norm == show_norm or value_norm in show_norm or show_norm in value_norm:
            return True
    return False


def find_compliant_potential_duplicate_rows(tlo_home: str, folder_path: str, artist_matcher, artist_mode: str = "master") -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]], List[str]]:
    """Duplicate check for compliant Add to Inventory folders.

    Compliant mode first checks the folder leaf for String1 Date String2.  If
    the date appears in bootlist column 1, String1 must resolve through the
    artist DB and the resolved master/alias/String1 value must match the same
    show-name cell before the folder is treated as a potential duplicate.
    """
    match = _compliant_string_date_string2(folder_path)
    if not match:
        return [], None, []
    date_value = match.get("date_norm", "") or ""
    string1 = (match.get("string1", "") or "").strip()
    if not date_value or not string1:
        return [], match, []
    if str(artist_mode or "master").strip().lower().replace("_", "-") in {"as-is", "asis", "as is", "raw"}:
        artist_values = [string1]
    else:
        artist_values = _artist_values_for_compliant_string1(string1, artist_matcher)
    if not artist_values:
        return [], match, []
    date_rows = [row for row in read_bootlist(tlo_home) if date_value in (row.get("Show", "") or "")]
    if not date_rows:
        return [], match, artist_values
    matches = [row for row in date_rows if _show_matches_any_artist_value(row.get("Show", ""), artist_values)]
    return matches, match, artist_values


def find_potential_duplicate_rows_for_folder(config, folder_path: str, record, artist_matcher) -> List[Dict[str, str]]:
    if getattr(config, "compliant", False):
        matches, match, artist_values = find_compliant_potential_duplicate_rows(config.TLOHome, folder_path, artist_matcher, getattr(config, "compliant_artist_mode", "master"))
        if matches:
            return matches
        # If String1 Date String2 did not match, try the compliant
        # String1 - String2 branch.  This branch has no reliable date, so the
        # duplicate check is deliberately limited to an exact normalized show
        # name comparison against bootlist column 1.
        if match is None:
            dash_match = _compliant_string_dash_string2(folder_path)
            if dash_match is not None:
                return _bootlist_show_name_matches(config.TLOHome, dash_match.get("show_name", ""))
        # If the compliant String1 Date String2 pattern matched but its exact
        # String1 artist lookup did not find a row, still let the resolved
        # metadata check run.  That keeps the updater aligned with the full
        # inventory engine and prevents known shows from being staged merely
        # because String1 contained extra source text or an alias variant.
        if match is not None:
            date_value = match.get("date_norm", "") or getattr(record, "date", "")
            fallback_matches = find_potential_duplicate_rows(
                config.TLOHome,
                getattr(record, "artist", ""),
                date_value,
                artist_matcher=artist_matcher,
                extra_artist_values=[match.get("string1", "") or ""] + list(artist_values or []),
            )
            if fallback_matches:
                return fallback_matches
            return []
    return find_potential_duplicate_rows(
        config.TLOHome,
        getattr(record, "artist", ""),
        getattr(record, "date", ""),
        artist_matcher=artist_matcher,
        extra_artist_values=[getattr(record, "show_name", "") or "", os.path.basename(os.path.normpath(folder_path))],
    )


def _record_dict_for_new_folder(config, folder_path: str, record, artist_matcher) -> Dict[str, str]:
    record_dict = _metadata_to_record_dict(record)
    if getattr(config, "compliant", False):
        matches, match, artist_values = find_compliant_potential_duplicate_rows(config.TLOHome, folder_path, artist_matcher, getattr(config, "compliant_artist_mode", "master"))
        if match is not None and not artist_values:
            # Compliant String1 Date String2 with no artist DB match: keep the
            # folder leaf as the show name, per Add to Inventory rules.
            record_dict["show_name"] = os.path.basename(os.path.normpath(folder_path))
        elif match is None:
            # Compliant fallback: if the folder leaf is String1 - String2,
            # String1 is the artist and the show name remains exactly
            # String1 - String2.
            dash_match = _compliant_string_dash_string2(folder_path)
            if dash_match is not None:
                record_dict["artist"] = dash_match.get("artist", "")
                record_dict["show_name"] = dash_match.get("show_name", "")
                record_dict["date"] = ""
                record_dict["venue"] = dash_match.get("string2", "")
                record_dict["location"] = ""
                record_dict["album_name"] = dash_match.get("string2", "")
    return record_dict


def _unique_destination_path(dest_dir: str, leaf_name: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    base = leaf_name or "folder"
    candidate = os.path.join(dest_dir, base)
    if not os.path.exists(candidate):
        return candidate
    index = 2
    while True:
        candidate = os.path.join(dest_dir, f"{base}_{index}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def move_folder_to(folder_path: str, dest_dir: str) -> str:
    destination = _unique_destination_path(dest_dir, os.path.basename(os.path.normpath(folder_path)))
    shutil.move(folder_path, destination)
    return destination


def _safe_compliant_folder_name(show_name: str, fallback: str = "TLO Show") -> str:
    value = re.sub(r"\s+", " ", str(show_name or "")).strip()
    value = INVALID_FOLDER_CHARS_RE.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    fallback_value = re.sub(r"\s+", " ", str(fallback or "")).strip(" .")
    return value or fallback_value or "TLO Show"


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


def _rewrite_record_dict_paths(record_dict: Dict[str, str], old_root: str, new_root: str) -> Dict[str, str]:
    for key in ("main_dir_path", "setlist_file"):
        if record_dict.get(key):
            record_dict[key] = _rewrite_path_under_root(record_dict[key], old_root, new_root)
    for key in ("setlist_files_json", "music_dirs_json"):
        raw_value = record_dict.get(key, "")
        if not raw_value:
            continue
        try:
            values = json.loads(raw_value)
        except Exception:
            continue
        if isinstance(values, list):
            record_dict[key] = json.dumps([_rewrite_path_under_root(value, old_root, new_root) for value in values], ensure_ascii=False)
    return record_dict


def _rename_add_shows_folder_compliantly(config, folder_path: str, record_dict: Dict[str, str]) -> str:
    """Rename an Add Shows source folder in place when Rename Compliantly is enabled."""
    if not bool(getattr(config, "rename_compliantly", False)):
        return folder_path
    show_name = (record_dict.get("show_name") or "").strip()
    if not show_name:
        return folder_path
    source_root = os.path.normpath(folder_path)
    if not os.path.isdir(source_root):
        return folder_path
    original_leaf = os.path.basename(source_root)
    target_leaf = _safe_compliant_folder_name(show_name, fallback=original_leaf)
    parent_dir = os.path.dirname(source_root)
    direct_target = os.path.normpath(os.path.join(parent_dir, target_leaf))
    if os.path.normcase(direct_target) == os.path.normcase(source_root):
        return source_root
    destination = direct_target if not os.path.exists(direct_target) else _unique_destination_path(parent_dir, target_leaf)
    try:
        os.rename(source_root, destination)
    except Exception as exc:
        raise InventoryUpdateError(f"Rename Compliantly failed for {source_root}: {exc}") from exc
    _rewrite_record_dict_paths(record_dict, source_root, destination)
    return os.path.normpath(destination)


def _used_setlist_names(tlo_home: str) -> set:
    setlists_dir = os.path.join(tlo_home, "setlists")
    os.makedirs(setlists_dir, exist_ok=True)
    return {os.path.basename(path_name) for path_name in glob.glob(os.path.join(setlists_dir, "*.txt"))}


def create_or_replace_generated_setlist(tlo_home: str, record_dict: Dict[str, str]) -> str:
    setlists_dir = os.path.join(tlo_home, "setlists")
    os.makedirs(setlists_dir, exist_ok=True)
    used = _used_setlist_names(tlo_home)
    base = _setlist_base_from_record(record_dict, fallback="Show")
    filename = _unique_setlist_filename(base, used)
    target = os.path.join(setlists_dir, filename)
    text = _export_combined_setlist_text(record_dict)
    _write_text_file(target, text)
    return target


def _add_bootlist_row_for_record(tlo_home: str, record_dict: Dict[str, str], current_volume: str, folder_leaf: str) -> None:
    show = (record_dict.get("show_name") or "").strip()
    if not show:
        raise InventoryUpdateError(f"Unable to create show name for {record_dict.get('main_dir_path') or folder_leaf}")
    rows = read_bootlist(tlo_home)
    rows.append({
        "Show": show,
        "VolumePath": _format_bootlist_volume_path(current_volume, folder_leaf),
    })
    write_bootlist(tlo_home, rows)


def _remove_bootlist_rows(tlo_home: str, remove_rows: Sequence[Dict[str, str]]) -> None:
    keys = {(row.get("Show", ""), row.get("VolumePath", "")) for row in remove_rows}
    rows = [row for row in read_bootlist(tlo_home) if (row.get("Show", ""), row.get("VolumePath", "")) not in keys]
    write_bootlist(tlo_home, rows)


def parse_volume_path_value(volume_path: str) -> Tuple[str, str]:
    value = (volume_path or "").strip()
    match = re.match(r"^\[(?P<volume>[^\]]*)\]\s*(?P<path>.*)$", value)
    if match:
        return match.group("volume").strip(), match.group("path").strip()
    return "", value


def infer_setlist_paths_for_show(tlo_home: str, show_name: str) -> List[str]:
    setlists_dir = os.path.join(tlo_home, "setlists")
    if not os.path.isdir(setlists_dir):
        return []
    base = _normalized_setlist_base(show_name, fallback="Show")
    candidates: List[str] = []
    exact = os.path.join(setlists_dir, f"{base}.txt")
    if os.path.isfile(exact):
        candidates.append(exact)
    base_fold = base.casefold()
    for path_name in sorted(glob.glob(os.path.join(setlists_dir, "*.txt")), key=lambda value: os.path.basename(value).casefold()):
        name = os.path.basename(path_name)
        name_fold = name.casefold()
        if path_name in candidates:
            continue
        if name_fold.startswith(base_fold) and name_fold.endswith(".txt"):
            candidates.append(path_name)
    return candidates


def open_paths(paths: Iterable[str]) -> None:
    clean_paths = [p for p in paths if p and os.path.exists(p)]
    if not clean_paths:
        return
    if os.name == "nt":
        for path_name in clean_paths:
            os.startfile(path_name)  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    for path_name in clean_paths:
        try:
            subprocess.Popen([opener, path_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def _append_delete_command(script_path: str, path_to_delete: str) -> None:
    if not path_to_delete:
        return
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    is_bat = script_path.lower().endswith(".bat")
    existed = os.path.exists(script_path)
    with open(script_path, "a", encoding="utf-8", newline="\n") as outfile:
        if not existed:
            outfile.write("@echo off\n" if is_bat else "#!/bin/sh\n")
        if is_bat:
            outfile.write(f'rmdir /s /q "{path_to_delete}"\n')
        else:
            outfile.write(f"rm -rf -- {shlex.quote(path_to_delete)}\n")
    if not is_bat:
        try:
            os.chmod(script_path, 0o755)
        except OSError:
            pass


def process_new_shows(config, current_volume: str, check_duplicates: bool = True) -> Dict[str, int]:
    prepare_updater_config(config)
    dirs = ensure_updater_directories(config.TLOHome)
    artist_matcher = load_artist_matcher(config)
    duplicate_count = 0
    staged_count = 0
    processed_count = 0
    error_count = 0
    for folder in _iter_top_level_dirs(dirs["ready"]):
        processed_count += 1
        try:
            record = identify_folder(config, folder, artist_matcher=artist_matcher)
            matches = []
            if check_duplicates:
                matches = find_potential_duplicate_rows_for_folder(config, folder, record, artist_matcher)
            if matches:
                move_folder_to(folder, dirs["dups"])
                duplicate_count += 1
                continue
            record_dict = _record_dict_for_new_folder(config, folder, record, artist_matcher)
            folder = _rename_add_shows_folder_compliantly(config, folder, record_dict)
            folder_leaf = os.path.basename(os.path.normpath(folder))
            create_or_replace_generated_setlist(config.TLOHome, record_dict)
            _add_bootlist_row_for_record(config.TLOHome, record_dict, current_volume, folder_leaf)
            move_folder_to(folder, dirs["staged"])
            staged_count += 1
        except Exception:
            error_count += 1
    return {
        "processed": processed_count,
        "staged": staged_count,
        "duplicates": duplicate_count,
        "errors": error_count,
    }


def duplicate_work_items(config) -> List[Dict[str, object]]:
    prepare_updater_config(config)
    dirs = ensure_updater_directories(config.TLOHome)
    artist_matcher = load_artist_matcher(config)
    items: List[Dict[str, object]] = []
    for folder in _iter_top_level_dirs(dirs["dups"]):
        record = identify_folder(config, folder, artist_matcher=artist_matcher)
        record_dict = _record_dict_for_new_folder(config, folder, record, artist_matcher)
        matches = find_potential_duplicate_rows_for_folder(config, folder, record, artist_matcher)
        if matches:
            items.append({
                "folder": folder,
                "record": record_dict,
                "show_name": record_dict.get("show_name", "") or os.path.basename(folder),
                "matches": matches,
            })
    return items


def review_paths_for_duplicate(config, item: Dict[str, object], selected_rows: Sequence[Dict[str, str]]) -> List[str]:
    record = dict(item.get("record") or {})
    paths: List[str] = []
    source = record.get("setlist_file", "")
    if source and os.path.isfile(source):
        paths.append(source)
    else:
        try:
            paths.append(create_or_replace_generated_setlist(config.TLOHome, record))
        except Exception:
            if source:
                paths.append(source)
    for row in selected_rows:
        paths.extend(infer_setlist_paths_for_show(config.TLOHome, row.get("Show", "")))
    return paths


def process_duplicate_folder(config, item: Dict[str, object], selected_rows: Sequence[Dict[str, str]], current_volume: str) -> Dict[str, int]:
    dirs = ensure_updater_directories(config.TLOHome)
    script_path = updater_delete_script_path(config.TLOHome)
    folder = str(item.get("folder") or "")
    record = dict(item.get("record") or {})
    deleted_old = 0
    for row in selected_rows:
        _volume, path_to_delete = parse_volume_path_value(row.get("VolumePath", ""))
        if path_to_delete:
            _append_delete_command(script_path, path_to_delete)
            deleted_old += 1
    if selected_rows:
        _remove_bootlist_rows(config.TLOHome, selected_rows)
    folder = _rename_add_shows_folder_compliantly(config, folder, record)
    folder_leaf = os.path.basename(os.path.normpath(folder))
    create_or_replace_generated_setlist(config.TLOHome, record)
    _add_bootlist_row_for_record(config.TLOHome, record, current_volume, folder_leaf)
    move_folder_to(folder, dirs["staged"])
    return {"delete_commands": deleted_old, "staged": 1}


def delete_new_keep_old(item: Dict[str, object]) -> None:
    folder = str(item.get("folder") or "")
    if folder and os.path.isdir(folder):
        shutil.rmtree(folder)
