from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION
import os
import re

from tlo_runtime_control import throttle_point, normalize_performance_mode
from tlo_path_policy import OS_MANAGED_DIR_NAMES, is_phase1_pruned_directory, is_ignorable_filesystem_artifact
from console_output_lib import console_emit

SYSTEM_DIR_NAMES_TO_PRUNE = OS_MANAGED_DIR_NAMES

from tlo_media_rules import DISCOVERY as MUSIC_FILE_EXTENSIONS_PHASE1, has_media_extension

SETLIST_LOOKUP_EXTENSIONS_PHASE1 = {".txt", ".rtf", ".doc", ".docx"}

SETLIST_HOUSEKEEPING_PATTERNS_PHASE1 = [
    re.compile(r"\bmd5\b", re.IGNORECASE),
    re.compile(r"\bffp\b", re.IGNORECASE),
    re.compile(r"\bfpt\b", re.IGNORECASE),
    re.compile(r"\bsfv\b", re.IGNORECASE),
    re.compile(r"checksum", re.IGNORECASE),
    re.compile(r"checksums", re.IGNORECASE),
    re.compile(r"fingerprint", re.IGNORECASE),
    re.compile(r"finger", re.IGNORECASE),
    re.compile(r"\bst5\b", re.IGNORECASE),
    re.compile(r"\bshn\b", re.IGNORECASE),
    re.compile(r"\bcue\b", re.IGNORECASE),
    re.compile(r"\bm3u\b", re.IGNORECASE),
    re.compile(r"\bm3u8\b", re.IGNORECASE),
    re.compile(r"\bpls\b", re.IGNORECASE),
    re.compile(r"\blog\b", re.IGNORECASE),
    re.compile(r"torrent", re.IGNORECASE),
    re.compile(r"spectrogram", re.IGNORECASE),
    re.compile(r"aucdtect", re.IGNORECASE),
    re.compile(r"dislaimer", re.IGNORECASE),
    re.compile(r"disclaimer", re.IGNORECASE),
    re.compile(r"easyed", re.IGNORECASE),
    re.compile(r"previous", re.IGNORECASE),
    re.compile(r"trader[']?s?\s*little\s*helper", re.IGNORECASE),
    re.compile(r"\btlh\b", re.IGNORECASE),
    re.compile(r"folder[\s._-]*aucdtect", re.IGNORECASE),
    re.compile(r"ffmpeg", re.IGNORECASE),
]


def _phase1_should_prune_dir(dirname):
    """Return True when phase 1 must not record or descend into dirname."""
    name = str(dirname or "").strip().lower()
    return (
        name.endswith("-ignoredir")
        or is_phase1_pruned_directory(name)
    )


def _phase1_is_real_music_file(path):
    """Return True only for real files with recognized music/media extensions."""
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
        return False
    return has_media_extension(path, MUSIC_FILE_EXTENSIONS_PHASE1)


def _phase1_is_setlist_lookup_file(path):
    """Return True for files worth logging during targeted descendant setlist search."""
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
        return False
    if is_ignorable_filesystem_artifact(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext not in SETLIST_LOOKUP_EXTENSIONS_PHASE1:
        return False
    basename = os.path.basename(path)
    if ext == ".txt" and any(pattern.search(basename) for pattern in SETLIST_HOUSEKEEPING_PATTERNS_PHASE1):
        return False
    return True


def _phase1_first_real_music_file(root, entries):
    """Return one representative media file path for root, or blank if none exists."""
    for entry in entries:
        path_name = os.path.join(root, entry.name)
        if _phase1_is_real_music_file(path_name):
            return path_name
    return ""


def _phase1_list_entries(config, current_path):
    """Return directory entries; extreme mode avoids sorting for maximum throughput."""
    with os.scandir(current_path) as entries:
        entry_list = list(entries)
    if normalize_performance_mode(getattr(config, "performance_mode", "balanced")) == "extreme":
        return entry_list
    return sorted(entry_list, key=lambda e: e.name.lower())

def _walk_and_log_recursive(config, current_path, dir_counter):
    """Iteratively walk one tree using the legacy depth-first ordering.

    The name is retained for compatibility, but no Python call-stack recursion is
    used; deeply nested collection trees therefore cannot raise RecursionError.
    """
    stack = [current_path]
    while stack:
        path_now = stack.pop()
        if _phase1_should_prune_dir(os.path.basename(os.path.normpath(path_now))):
            continue

        throttle_point(config)
        try:
            sorted_entries = _phase1_list_entries(config, path_now)
        except (OSError, PermissionError) as exc:
            config.logs.dead_end("INACCESSIBLE %s | %s", path_now, exc)
            continue

        sample_media_file = _phase1_first_real_music_file(path_now, sorted_entries)
        if sample_media_file:
            if any(0xDC80 <= ord(char) <= 0xDCFF for char in sample_media_file):
                # POSIX filenames may contain raw bytes which are not UTF-8.
                # They cannot be safely put into UTF-8 inventory/setlist paths.
                # Use an ASCII-hex identifier so the path is not silently lost
                # and the user can rename the folder without byte ambiguity.
                offending_path = (sample_media_file if any(0xDC80 <= ord(c) <= 0xDCFF for c in sample_media_file)
                                  else path_now)
                bytes_hex = os.fsencode(offending_path).hex()
                path_escaped = os.fsencode(offending_path).decode('utf-8', errors='backslashreplace')
                notice = (f"UNIDENTIFIED_NON_UTF8_PATH: path_escaped={path_escaped} | "
                          f"bytes_hex={bytes_hex} | invalid UTF-8 filename; "
                          "rename the offending file or directory using a UTF-8 name before inventory")
                config.current_non_utf8_path_count = int(getattr(config, 'current_non_utf8_path_count', 0)) + 1
                config.logs.dead_end(notice)
                console_emit('WARNING: ' + notice)
                home = str(getattr(config, 'TLOHome', '') or '')
                if home and os.path.isdir(home) and not bool(getattr(config, 'dry_run', False)):
                    target = os.path.join(home, 'unidentifiedShows.txt')
                    already_reported = set()
                    if os.path.isfile(target):
                        with open(target, 'r', encoding='utf-8') as infile:
                            already_reported = set(infile.read().splitlines())
                    if notice not in already_reported:
                        with open(target, 'a', encoding='utf-8') as outfile:
                            outfile.write(notice + '\n')
                # Do not descend into a path we cannot represent in UTF-8.
                continue
            config.logs.complete_paths(sample_media_file)

        child_dirs = []
        for entry in sorted_entries:
            child_path = entry.path
            try:
                if _phase1_should_prune_dir(entry.name):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    dir_counter += 1
                    child_dirs.append(child_path)
            except (OSError, PermissionError) as exc:
                config.logs.dead_end("INACCESSIBLE %s | %s", child_path, exc)

        # LIFO stack + reverse preserves the previous recursive visit order.
        stack.extend(reversed(child_dirs))

    return dir_counter


def initial_dir_walk(config, start_path):
    """
    Walk a directory tree and write paths to the complete_paths log.

    Rules:
      - recursively descend through nested folders even after a media folder is found
      - when a media folder is found, log one representative full media-file path only
      - do not log directories, non-media files, setlist candidates, or every media filename
      - later phases rescan known media folders/allowed parents only when those details are needed
      - directory names ending in -ignoreDir are not written and are not descended into
      - inaccessible paths are written to the dead_end log
    """
    normalized_start = os.path.abspath(start_path)

    if not os.path.exists(normalized_start):
        raise FileNotFoundError(f"Path does not exist: {normalized_start}")

    if not os.path.isdir(normalized_start):
        raise NotADirectoryError(f"Path is not a directory: {normalized_start}")

    if _phase1_should_prune_dir(os.path.basename(os.path.normpath(normalized_start))):
        return 0

    starting_non_utf8_count = int(getattr(config, 'current_non_utf8_path_count', 0))
    dir_counter = 1
    dir_counter = _walk_and_log_recursive(config, normalized_start, dir_counter)
    excluded = int(getattr(config, 'current_non_utf8_path_count', 0)) - starting_non_utf8_count
    if excluded:
        config.logs.dead_end("PHASE1_NON_UTF8_UNIDENTIFIED_COUNT: %s", excluded)
        console_emit(f"Phase 1: {excluded} non-UTF-8 media paths excluded and listed in unidentifiedShows.txt")

    return dir_counter
