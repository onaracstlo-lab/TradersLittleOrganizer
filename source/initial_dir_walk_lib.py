__version__ = "v322"
# TLO-GI package version: v322
__version_summary__ = 'Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.'
# TLO-GI version summary: Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.
import os
import re

from console_output_lib import console_print
from tlo_runtime_control import throttle_point, normalize_performance_mode

SYSTEM_DIR_NAMES_TO_PRUNE = {
    "$recycle.bin",
    "system volume information",
}

MUSIC_FILE_EXTENSIONS_PHASE1 = {
    ".3gp", ".aac", ".aif", ".aiff", ".alac", ".ape", ".avi", ".flac",
    ".flv", ".m2ts", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpg", ".oga", ".ogg", ".opus", ".shn", ".shnf", ".ts",
    ".vob", ".wav", ".webm", ".wmv", ".wv",
}

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
    return name.endswith("-ignoredir") or name in SYSTEM_DIR_NAMES_TO_PRUNE


def _phase1_is_real_music_file(path):
    """Return True only for real files with recognized music/media extensions."""
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
        return False
    return os.path.splitext(path)[1].lower() in MUSIC_FILE_EXTENSIONS_PHASE1


def _phase1_is_setlist_lookup_file(path):
    """Return True for files worth logging during targeted descendant setlist search."""
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
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
    # Safety guard: this function must never scan inside a directory that phase 1
    # is supposed to prune.
    if _phase1_should_prune_dir(os.path.basename(os.path.normpath(current_path))):
        return dir_counter

    throttle_point(config)
    try:
        sorted_entries = _phase1_list_entries(config, current_path)
    except (OSError, PermissionError) as exc:
        config.logs.dead_end("INACCESSIBLE %s | %s", current_path, exc)
        return dir_counter

    sample_media_file = _phase1_first_real_music_file(current_path, sorted_entries)
    if sample_media_file:
        # One full media path is enough for later phases to derive the music
        # directory and representative media type.  Do not carry directory
        # listings, setlist filenames, or all media filenames in the tree-walk
        # log; later phases rescan the known folder or allowed parent only when
        # those details are actually needed.
        config.logs.complete_paths(sample_media_file)
        return dir_counter

    for entry in sorted_entries:
        child_path = entry.path

        try:
            # Pruned path components are never recorded and never descended into.
            if _phase1_should_prune_dir(entry.name):
                continue

            if entry.is_dir(follow_symlinks=False):
                dir_counter += 1
                dir_counter = _walk_and_log_recursive(config, child_path, dir_counter)

        except (OSError, PermissionError) as exc:
            config.logs.dead_end("INACCESSIBLE %s | %s", child_path, exc)

    return dir_counter


def initial_dir_walk(config, start_path):
    """
    Walk a directory tree and write paths to the complete_paths log.

    Rules:
      - recursively descend until a real media file is found
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

    dir_counter = 1
    dir_counter = _walk_and_log_recursive(config, normalized_start, dir_counter)

    return dir_counter
