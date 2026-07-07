__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
import json
import os

VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".vob",
    ".ts",
    ".m2ts",
    ".webm",
    ".flv",
    ".3gp",
}

MEDIA_EXTENSIONS = {
    ".flac",
    ".shn",
    ".shnf",
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
    ".mp4",
    ".m4v",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".vob",
    ".ts",
    ".m2ts",
    ".webm",
    ".flv",
    ".3gp",
}


MUSIC_DIR_MARKER_PREFIX = "__TLO_MUSIC_DIR__\t"


def music_dir_marker_line(directory: str, sample_file: str, extension: str, count: int) -> str:
    """Return a compact complete-path log marker for a discovered music directory.

    Phase 1 does not need to carry every media filename forward.  The marker
    records the identified directory, one representative file, its extension,
    and a count so later phases know the media type and can rescan the known
    directory only if deeper metadata is needed.
    """
    payload = {
        "dir": os.path.normpath(directory or ""),
        "sample": os.path.normpath(sample_file or "") if sample_file else "",
        "ext": (extension or os.path.splitext(sample_file or "")[1]).lower(),
        "count": max(0, int(count or 0)),
    }
    return MUSIC_DIR_MARKER_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_music_dir_marker(line: str):
    """Parse a Phase 1 music-directory marker; return None for normal paths."""
    text = str(line or "").strip()
    if not text.startswith(MUSIC_DIR_MARKER_PREFIX):
        return None
    try:
        payload = json.loads(text[len(MUSIC_DIR_MARKER_PREFIX):])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    directory = os.path.normpath(str(payload.get("dir") or ""))
    if not directory:
        return None
    sample = str(payload.get("sample") or "")
    if sample:
        sample = os.path.normpath(sample)
    ext = str(payload.get("ext") or os.path.splitext(sample)[1]).lower()
    try:
        count = int(payload.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    return {"dir": directory, "sample": sample, "ext": ext, "count": max(0, count)}


def is_media_file(path_name: str) -> bool:
    """Return True only for real files whose extension is inventoried media."""
    if not path_name or not os.path.isfile(path_name):
        return False
    return os.path.splitext(path_name)[1].lower() in MEDIA_EXTENSIONS


def is_video_file(path_name: str) -> bool:
    """Return True only for real files whose extension is an inventoried video format."""
    if not path_name or not os.path.isfile(path_name):
        return False
    return os.path.splitext(path_name)[1].lower() in VIDEO_EXTENSIONS
