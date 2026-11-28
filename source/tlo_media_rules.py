from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION
import json
import os
from tlo_path_policy import is_ignorable_filesystem_artifact

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

# Discovery includes all supported videos and recognized audio containers.
TAG_WRITABLE = frozenset({".flac", ".mp3", ".wav", ".m4a", ".aac", ".ogg",
                         ".oga", ".opus", ".aiff", ".aif", ".ape", ".wv", ".alac"})
SHN_AUDIO = frozenset({".shn", ".shnf"})
COUNTED_AUDIO = TAG_WRITABLE | SHN_AUDIO | {".wma", ".tta"}
DISCOVERY = COUNTED_AUDIO | VIDEO_EXTENSIONS
MEDIA_EXTENSIONS = DISCOVERY  # historical public name

def has_media_extension(path_name: str, extensions=DISCOVERY) -> bool:
    return (not is_ignorable_filesystem_artifact(path_name)
            and os.path.splitext(str(path_name or ""))[1].lower() in extensions)



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
    return has_media_extension(path_name)


def is_video_file(path_name: str) -> bool:
    """Return True only for real files whose extension is an inventoried video format."""
    if not path_name or not os.path.isfile(path_name):
        return False
    return has_media_extension(path_name, VIDEO_EXTENSIONS)
