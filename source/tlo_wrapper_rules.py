__version__ = "v334"
# TLO-GI package version: v334
__version_summary__ = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
# TLO-GI version summary: Rearranges the main-window checkboxes into the requested two-row, four-column layout.
import re

NON_MAIN_DIR_PATTERNS = [
    r"^[\[\(_][\s.\-_]*(disc|disk|cd|pt\.|pt|part|set|side|tape)[\s.\-_]*\d{1,2}[\s.\-_]*[\]\)_]$",
    r"^(disc|disk|cd|pt\.|pt|lp|set|side)[\s.\-_]*(\d{1,2}|iii|ii|i|one|two|a|b)$",
    r"^[\[\(_][\s.\-_]*d[\s.\-_]*[012]?[0-9][\s.\-_]*[\]\)_]$",
    r"^d[\s.\-_]*\d{1,2}[\s.\-_]*(aud|sbd)?[\s.\-_]*(flacs|flac|shns|shnf|shn|master)?$",
    r"^[\[\(]?[\s.\-_]*(1st|first|2nd|second|acoustic|electric|afternoon|evening)[\s.\-_]*(set|show|side|cd|disc|disk)[\s.\-_]*[\]\)]?$",
    r"^d[\s.\-_]*\d{1,2}$",
    r"^#(\s?|.\-|_)\d{1,2}$",
]

STANDARD_VIDEO_FOLDER_PATTERNS = [
    r"^video_ts$",
    r"^audio_ts$",
    r"^bdmv$",
    r"^certificate$",
    r"^video$",
    r"^dvd$",
    r"^bluray$",
    r"^blu[\s._-]*ray$",
]

EXACT_WRAPPER_PATTERNS = [
    r"^music$",
    r"^audio$",
    r"^tunes$",
    r"^aud$",
    r"^sbd$",
    r"^flac$",
    r"^flacs$",
    r"^flac files$",
    r"^shn$",
    r"^shns$",
    r"^mp3$",
    r"^unknown artist$",
    r"^full-length tracks$",
    r"^video_ts$",
    r"^audio_ts$",
    r"^bdmv$",
    r"^certificate$",
    r"^video$",
    r"^dvd$",
    r"^bluray$",
    r"^blu[\s._-]*ray$",
    r"^fm\s*broadcast$",
    r"^soundboard$",
    r"^flacs?\s*and\s*checks?$",
    r"^volume\s+\d{1,2}$",
    r"^disc\s+\d{1,2}\s+flac$",
    r"^disk\s+\d{1,2}\s+flac$",
    r"^disco\s*\d{1,2}$",
    r"^cd\s+\d{1,2}.*$",
]

CONTAINS_WRAPPER_PATTERNS = [
    r"unknown artist",
    r"fm\s*broadcast",
    r"soundboard",
    r"video_ts",
    r"audio_ts",
    r"bdmv",
    r"certificate",
    r"bluray",
    r"blu[\s._-]*ray",
    r"\bflac\b",
    r"\bflacs\b",
    r"\baudio\b",
    r"\bvideo\b",
    r"\btunes\b",
    r"\bchecks?\b",
    r"\bvolume\s+\d{1,2}\b",
    r"\bdisc\s+\d{1,2}\b",
    r"\bdisk\s+\d{1,2}\b",
    r"\bcd\s+\d{1,2}\b",
]

_COMPILED_NON_MAIN_DIR_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in NON_MAIN_DIR_PATTERNS]
_COMPILED_STANDARD_VIDEO_FOLDER_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in STANDARD_VIDEO_FOLDER_PATTERNS]
_COMPILED_EXACT_WRAPPER_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in EXACT_WRAPPER_PATTERNS]
_COMPILED_CONTAINS_WRAPPER_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in CONTAINS_WRAPPER_PATTERNS]

# Wrapper suffixes used for release-part aggregation. These match either a
# whole media-only folder name (CD1, Disc 1, Disk3, etc.) or a release folder
# name ending with such a suffix (Big Release CD 1).
WRAPPER_PART_SUFFIX_RE = re.compile(
    r"(?i)(?:^|[\s._-]+)(?:cd|disc|disk|pt\.?|part|set|side|tape|d)[\s._-]*(?:\d{1,2}|[ivx]{1,4}|one|two|three|four|a|b)\s*$"
)

# Volume suffixes are release-part identifiers too, but they have slightly
# different aggregation semantics: only differing-base sibling folders that all
# end in volume-style markers are grouped under their parent (for example
# Early Days (Vol 1) + Latter Days (Vol 2)). Same-base Volume 1/Volume 2
# folders remain separate inventory rows.
VOLUME_PART_SUFFIX_RE = re.compile(
    r"(?i)(?:^|[\s._-]+|[\[(])(?:volume|vol\.?|v\.?)[\s._-]*(?:\d{1,3}|[ivx]{1,6}|one|two|three|four|five|six|seven|eight|nine|ten)\s*[\])]?\s*$"
)


def _split_suffix_with_regex(dir_name: str, pattern: re.Pattern) -> tuple[str, str]:
    name = str(dir_name or "").strip()
    if not name:
        return "", ""
    match = pattern.search(name)
    if not match:
        return "", ""
    suffix = name[match.start():].strip(" ._-\t()[]")
    base = name[:match.start()].strip(" ._-")
    # If the regex matched from the beginning, the entire folder is the suffix.
    if match.start() == 0:
        suffix = name.strip()
        base = ""
    return base, suffix


def split_wrapper_part_suffix(dir_name: str) -> tuple[str, str]:
    """Return (base, suffix) when dir_name ends with a disc/part wrapper.

    Examples:
      CD1 -> ("", "CD1")
      Disc 1 -> ("", "Disc 1")
      Big Release CD 1 -> ("Big Release", "CD 1")
      Big Release Disk3 -> ("Big Release", "Disk3")
    """
    return _split_suffix_with_regex(dir_name, WRAPPER_PART_SUFFIX_RE)


def split_volume_part_suffix(dir_name: str) -> tuple[str, str]:
    """Return (base, suffix) when dir_name ends with a volume-style suffix.

    Examples:
      Big Release (Volume 1) -> ("Big Release", "Volume 1")
      Big Release Vol. 2 -> ("Big Release", "Vol. 2")
      Early Days (v.1) -> ("Early Days", "v.1")
    """
    return _split_suffix_with_regex(dir_name, VOLUME_PART_SUFFIX_RE)


def is_wrapper_part_folder_name(dir_name: str) -> bool:
    """Return True when a folder is, or ends with, a release-part suffix."""
    _base, suffix = split_wrapper_part_suffix(dir_name)
    if suffix:
        return True
    _base, suffix = split_volume_part_suffix(dir_name)
    return bool(suffix)


def looks_like_non_main_dir(dir_name: str) -> bool:
    name = str(dir_name or "").strip()
    return any(pattern.match(name) for pattern in _COMPILED_NON_MAIN_DIR_PATTERNS)


def is_exact_wrapper_name(dir_name: str) -> bool:
    name = str(dir_name or "").strip()
    return any(pattern.match(name) for pattern in _COMPILED_EXACT_WRAPPER_PATTERNS)


def is_standard_video_folder_name(dir_name: str) -> bool:
    """Return True for standard video wrapper folder names such as VIDEO_TS."""
    name = str(dir_name or "").strip()
    return any(pattern.match(name) for pattern in _COMPILED_STANDARD_VIDEO_FOLDER_PATTERNS)


def contains_wrapper_term(dir_name: str) -> bool:
    name = str(dir_name or "").strip()
    return any(pattern.search(name) for pattern in _COMPILED_CONTAINS_WRAPPER_PATTERNS)


def is_common_music_folder_name(dir_name: str) -> bool:
    """Return True for wrapper/common folder names that often hold only media files.

    Examples include CD1, Disc 1, flac, music, tunes, audio, and similar
    non-main directory names. These folders may not hold the setlist file, so
    setlist selection should also check the parent folder.
    """
    name = str(dir_name or "").strip()
    if not name:
        return False
    return looks_like_non_main_dir(name) or is_exact_wrapper_name(name) or contains_wrapper_term(name)
