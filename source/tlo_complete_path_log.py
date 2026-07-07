__version__ = "v321"
# TLO-GI package version: v321
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
import os

from tlo_media_rules import MEDIA_EXTENSIONS, parse_music_dir_marker


def _is_media_path_by_extension(path_name: str) -> bool:
    return os.path.splitext(str(path_name or '').strip())[1].lower() in MEDIA_EXTENSIONS


def compact_complete_path_log(log_file: str) -> int:
    """Rewrite compN.log so it keeps one representative media path per music directory.

    Older logs, append-mode runs, or interrupted runs can leave many media
    filenames in compN.log for the same music directory.  Phase 1 should remain
    a lightweight discovery step: one representative media file path identifies
    the directory; tagging and metadata stages rescan the known directory when
    they need counts or full file lists.  Header/SEARCH_PATH lines are preserved.

    Returns the number of duplicate media rows removed.
    """
    if not log_file or not os.path.isfile(log_file):
        return 0
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as infile:
            lines = infile.readlines()
    except OSError:
        return 0

    kept_media_dirs = set()
    output = []
    removed = 0

    for raw_line in lines:
        stripped = raw_line.rstrip('\r\n').strip()
        if not stripped:
            output.append(raw_line)
            continue
        if stripped.startswith('#') or stripped.startswith('SEARCH_PATH:'):
            output.append(raw_line)
            continue

        marker = parse_music_dir_marker(stripped)
        if marker:
            media_dir = os.path.normcase(os.path.normpath(marker.get('dir') or ''))
            if media_dir and media_dir in kept_media_dirs:
                removed += 1
                continue
            if media_dir:
                kept_media_dirs.add(media_dir)
            output.append(raw_line)
            continue

        if _is_media_path_by_extension(stripped):
            media_dir = os.path.normcase(os.path.normpath(os.path.dirname(stripped)))
            if media_dir in kept_media_dirs:
                removed += 1
                continue
            kept_media_dirs.add(media_dir)
            # Normalize retained payload rows for stable downstream path parsing.
            output.append(os.path.normpath(stripped) + '\n')
            continue

        # Non-media payload rows are unusual in compN.log, but preserve them so
        # malformed or future diagnostic lines are not silently discarded.
        output.append(raw_line)

    if removed:
        try:
            with open(log_file, 'w', encoding='utf-8', newline='') as outfile:
                outfile.writelines(output)
        except OSError:
            return 0
    return removed


def path_has_ignored_component(path_name: str) -> bool:
    """Return True when any path component should be pruned from inventory."""
    parts = [part.strip().lower() for part in os.path.normpath(path_name).split(os.sep) if part]
    return any(part.endswith("-ignoredir") or part in {"$recycle.bin", "system volume information"} for part in parts)


def load_complete_path_lines(config):
    log_file = config.logs.paths.complete_paths

    if not os.path.isfile(log_file):
        raise FileNotFoundError(f"Complete path log not found: {log_file}")

    path_lines = []
    seen = set()
    with open(log_file, "r", encoding="utf-8") as infile:
        for raw_line in infile:
            line = raw_line.rstrip("\r\n").strip()
            if not line or ": " in line:
                continue

            normalized = os.path.normpath(line)
            if path_has_ignored_component(normalized):
                continue
            if normalized in seen:
                config.logs.duplicate("DUPLICATE_COMPLETE_PATH: %s", normalized)
                continue

            seen.add(normalized)
            path_lines.append(normalized)

    return path_lines
