__version__ = "v319"
# TLO-GI package version: v319
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
import os
from typing import Dict, List

from mutagen import File as MutagenFile


FLAC_EXTENSIONS = {".flac"}
_FILE_TAG_CACHE: Dict[str, Dict[str, str]] = {}


def is_flac_type_file(path_name: str) -> bool:
    normalized = os.path.normpath(path_name or "")
    if not normalized or not os.path.isfile(normalized):
        return False
    return os.path.splitext(normalized)[1].lower() in FLAC_EXTENSIONS



def _first_tag_value(tags, wanted_key: str) -> str:
    wanted_key = wanted_key.lower()
    for key in tags.keys():
        if str(key).lower() != wanted_key:
            continue
        values = tags.get(key)
        if values is None:
            return ""
        if not isinstance(values, (list, tuple)):
            values = [values]
        for value in values:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
        return ""
    return ""



def read_flac_type_tags(path_name: str) -> Dict[str, str]:
    normalized = os.path.normpath(path_name or "")
    if normalized in _FILE_TAG_CACHE:
        return dict(_FILE_TAG_CACHE[normalized])

    result = {"artist": "", "album": "", "albumartist": "", "date": ""}
    if not is_flac_type_file(normalized):
        _FILE_TAG_CACHE[normalized] = result
        return dict(result)

    try:
        audio = MutagenFile(normalized)
        tags = getattr(audio, "tags", None)
        if tags:
            result = {
                "artist": _first_tag_value(tags, "artist"),
                "album": _first_tag_value(tags, "album"),
                "albumartist": _first_tag_value(tags, "albumartist"),
                "date": _first_tag_value(tags, "date"),
            }
    except Exception:
        pass

    _FILE_TAG_CACHE[normalized] = result
    return dict(result)



def collect_group_flac_tag_info(music_files: List[str], max_files: int = 2) -> Dict[str, List[dict] | List[str]]:
    samples: List[dict] = []
    artist_values: List[str] = []
    album_values: List[str] = []
    albumartist_values: List[str] = []
    date_values: List[str] = []

    for path_name in list(music_files or [])[:max_files]:
        if not is_flac_type_file(path_name):
            continue
        tags = read_flac_type_tags(path_name)
        sample = {
            "file": path_name,
            "artist": tags.get("artist", ""),
            "album": tags.get("album", ""),
            "albumartist": tags.get("albumartist", ""),
            "date": tags.get("date", ""),
        }
        samples.append(sample)

        for value, bucket in (
            (sample["artist"], artist_values),
            (sample["album"], album_values),
            (sample["albumartist"], albumartist_values),
            (sample["date"], date_values),
        ):
            cleaned = (value or "").strip()
            if cleaned and cleaned not in bucket:
                bucket.append(cleaned)

    return {
        "flac_tag_samples": samples,
        "flac_tag_artist_values": artist_values,
        "flac_tag_album_values": album_values,
        "flac_tag_albumartist_values": albumartist_values,
        "flac_tag_date_values": date_values,
    }
