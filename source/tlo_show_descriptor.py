"""Conservative fallback descriptor extraction for unknown-date TLO shows/collections.

The descriptor is intentionally separate from venue/location metadata.  It is
used only when a show has the canonical unknown date (xxxx-xx-xx) and no venue
or location, so collections, sessions, broadcasts, releases, and similar
material can retain a useful identity without inventing geographic metadata.
"""

__version__ = "v482"

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from tlo_setlist_metadata_lookup import is_setlist_metadata_scan_boundary, looks_like_sentence_prose_line
from tlo_text_utils import compact_ws, normalized_compare_value, read_text_file_full, standard_ascii_text


MAX_DESCRIPTOR_CHARS = 60
MIN_AUTOMATIC_SCORE = 60
MAX_HEADER_LINES = 30

_EXPLICIT_DESCRIPTOR_RE = re.compile(
    r"(?i)^\s*[#*_~=\- ]{0,12}\s*"
    r"(?P<label>title|release|collection|bootleg|event|session|broadcast|program|programme|show|recording|descriptor)"
    r"\s*(?::|=|-|\u2013|\u2014)\s*(?P<value>\S.*)$"
)
_QUOTED_TITLE_RE = re.compile(r"^\s*[\"'\u201c\u201d\u2018\u2019](?P<value>[^\"'\u201c\u201d\u2018\u2019]{3,80})[\"'\u201c\u201d\u2018\u2019]\s*$")
_DECORATED_TITLE_RE = re.compile(r"^\s*(?:={2,}|-{3,}|\*{2,}|#{2,}|~{2,})\s*(?P<value>.*?)\s*(?:={2,}|-{3,}|\*{2,}|#{2,}|~{2,})\s*$")

_PRIMARY_DESCRIPTOR_RE = re.compile(
    r"(?i)\b(?:"
    r"broadcast|session|sessions|rehearsal|soundcheck|demo|demos|audition|"
    r"collection|anthology|compilation|archive|archives|rarities|outtakes?|"
    r"private\s+party|benefit|festival|recording\s+session|acetate|promo|promotional"
    r")\b"
)
_MEDIA_DESCRIPTOR_RE = re.compile(r"(?i)\b(?:radio|fm|am|bbc|tv|television|telecast|simulcast|studio|program|programme)\b")


def _strong_descriptor_line(value: str) -> bool:
    text = str(value or "")
    if _PRIMARY_DESCRIPTOR_RE.search(text):
        return True
    media_hits = {m.group(0).casefold() for m in _MEDIA_DESCRIPTOR_RE.finditer(text)}
    return len(media_hits) >= 2


_TECHNICAL_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:sbd|aud|matrix|soundboard|audience|flac|flac16|flac24|shn|shnf|wav|mp3|"
    r"24\s*bit|16\s*bit|dat|cdr|cd-r|md5|ffp|checksum|torrent|seeded|lineage|transfer|"
    r"mic(?:rophone)?s?|recorder|taper|tracked|sector\s+boundary|frequency|sample\s+rate)\b|"
    r"(?:>|->|=>).*(?:flac|wav|cdr|dat)"
    r")"
)
_STRUCTURAL_RE = re.compile(
    r"(?i)^(?:disc|disk|cd|set|part|volume|vol\.?|track|tracks)\s*[#.:_-]*\s*(?:[0-9ivx]+|one|two|three|four)?\s*$"
)
_GENERIC_RE = re.compile(
    r"(?i)^(?:info|information|notes?|read\s*me|readme|set\s*list|setlist|track\s*list|tracklist|"
    r"songs?|show|unknown|untitled|text|details?)$"
)
_DATEISH_RE = re.compile(
    r"(?i)(?:\b(?:19|20)\d{2}\b|\b[xX]{4}(?:[-_. /][xX]{2}){0,2}\b|"
    r"\b\d{1,2}[-/.]\d{1,2}[-/.](?:\d{2}|\d{4})\b)"
)
_TRACKISH_RE = re.compile(
    r"(?i)^\s*(?:d\d+t\d+|(?:disc|cd|set)?\s*\d{1,3}\s*[.)\-:]\s*\S+)"
)
_FILENAME_EXT_RE = re.compile(r"(?i)\.(?:txt|nfo|md|rtf|docx?)$")
_WRAPPER_TOKEN_RE = re.compile(
    r"(?i)\b(?:disc|disk|cd|set|part|volume|vol\.?|flac|flac16|flac24|shn|shnf|wav|mp3|16\s*bit|24\s*bit)\s*[#._-]*\s*\d*\b"
)


@dataclass(frozen=True)
class DescriptorCandidate:
    value: str
    source: str
    score: int
    order: int = 0


def _read_text(path_name: str) -> str:
    return read_text_file_full(path_name)


def _clean_candidate(value: str) -> str:
    text = standard_ascii_text(compact_ws(str(value or "").strip(" \t\ufeff*#~=|-:;,.\"'")))
    text = compact_ws(text)
    if len(text) > MAX_DESCRIPTOR_CHARS:
        text = text[:MAX_DESCRIPTOR_CHARS].rstrip(" -_,.;:")
    return text


def _same_as_artist(value: str, artist: str) -> bool:
    if not value or not artist:
        return False
    return normalized_compare_value(value) == normalized_compare_value(artist)


def _is_rejected(value: str, artist: str = "") -> bool:
    text = _clean_candidate(value)
    if len(text) < 3 or not re.search(r"[A-Za-z]", text):
        return True
    if _same_as_artist(text, artist):
        return True
    if _GENERIC_RE.fullmatch(text) or _STRUCTURAL_RE.fullmatch(text):
        return True
    if _TRACKISH_RE.match(text):
        return True
    if _TECHNICAL_RE.search(text):
        return True
    if _DATEISH_RE.fullmatch(text):
        return True
    if looks_like_sentence_prose_line(text) and not _strong_descriptor_line(text):
        return True
    return False


def _header_lines(path_name: str) -> List[tuple[str, bool]]:
    text = _read_text(path_name)
    if not text:
        return []
    entries: List[tuple[str, bool]] = []
    raw_lines = text.splitlines()
    for index, raw in enumerate(raw_lines):
        line = compact_ws(raw.strip("\ufeff"))
        if not line:
            continue
        if line.startswith("--------- End of "):
            continue
        if is_setlist_metadata_scan_boundary(line):
            break
        followed_by_blank = False
        for later in raw_lines[index + 1 :]:
            if not str(later or "").strip():
                followed_by_blank = True
            break
        entries.append((line, followed_by_blank))
        if len(entries) >= MAX_HEADER_LINES:
            break
    return entries


def _title_case_ratio(value: str) -> float:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'&.-]*", value) if w]
    if not words:
        return 0.0
    titleish = sum(1 for word in words if word[:1].isupper() or word.isupper())
    return titleish / len(words)


def _header_candidates(path_name: str, artist: str, start_order: int = 0) -> List[DescriptorCandidate]:
    candidates: List[DescriptorCandidate] = []
    lines = _header_lines(path_name)
    for idx, (line, followed_by_blank) in enumerate(lines):
        order = start_order + idx
        explicit = _EXPLICIT_DESCRIPTOR_RE.match(line)
        if explicit:
            value = _clean_candidate(explicit.group("value"))
            if not _is_rejected(value, artist):
                candidates.append(DescriptorCandidate(value, f"setlist-explicit-{explicit.group('label').casefold()}", 100, order))
            continue

        quoted = _QUOTED_TITLE_RE.match(line)
        if quoted:
            value = _clean_candidate(quoted.group("value"))
            if not _is_rejected(value, artist):
                candidates.append(DescriptorCandidate(value, "setlist-quoted-title", 85, order))
            continue

        decorated = _DECORATED_TITLE_RE.match(line)
        if decorated:
            value = _clean_candidate(decorated.group("value"))
            if not _is_rejected(value, artist):
                score = 90 if _strong_descriptor_line(value) else 80
                candidates.append(DescriptorCandidate(value, "setlist-decorated-header", score, order))
            continue

        value = _clean_candidate(line)
        if _is_rejected(value, artist):
            continue
        if _strong_descriptor_line(value):
            candidates.append(DescriptorCandidate(value, "setlist-descriptor-header", 90, order))
            continue

        # Conservative generic title/header fallback.  Restrict it to the very
        # top of the metadata region and require title-like capitalization so
        # unnumbered song/prose lines do not become collection descriptors.
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&.-]*", value)
        if followed_by_blank and idx < 6 and 1 <= len(words) <= 8 and 4 <= len(value) <= 80 and _title_case_ratio(value) >= 0.60:
            candidates.append(DescriptorCandidate(value, "setlist-title-header", 70, order))
    return candidates


def _strip_artist_and_unknown_date(value: str, artist: str) -> str:
    text = compact_ws(value.replace("_", " ").replace(".", " "))
    if artist:
        # Prefer exact textual removal and then a token-wise prefix fallback.
        text = re.sub(re.escape(artist), " ", text, flags=re.IGNORECASE)
        artist_tokens = [re.escape(tok) for tok in re.findall(r"[A-Za-z0-9]+", artist)]
        if artist_tokens:
            text = re.sub(r"^\s*" + r"[\s._-]+".join(artist_tokens) + r"\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)\b[xX]{4}(?:\s*[-_/]\s*[xX]{2}){2}\b", " ", text)
    text = re.sub(r"(?i)\b(?:19|20)\d{2}(?:\s*[-_/]\s*\d{1,2}){0,2}\b", " ", text)
    text = _WRAPPER_TOKEN_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_,.;:()[]{}")
    return _clean_candidate(text)


def _filename_candidate(path_name: str, artist: str, order: int) -> DescriptorCandidate | None:
    if not path_name:
        return None
    stem = _FILENAME_EXT_RE.sub("", os.path.basename(path_name))
    value = _strip_artist_and_unknown_date(stem, artist)
    if _is_rejected(value, artist):
        return None
    if _GENERIC_RE.fullmatch(value):
        return None
    score = 75 if _strong_descriptor_line(value) else 60
    return DescriptorCandidate(value, "setlist-filename", score, order)


def _directory_candidate(main_dir_name: str, artist: str, order: int) -> DescriptorCandidate | None:
    value = _strip_artist_and_unknown_date(main_dir_name, artist)
    if _is_rejected(value, artist):
        return None
    if _GENERIC_RE.fullmatch(value):
        return None
    score = 70 if _strong_descriptor_line(value) else 60
    return DescriptorCandidate(value, "directory-residue", score, order)


def extract_fallback_descriptor(
    *,
    setlist_file: str = "",
    setlist_files: Sequence[str] | None = None,
    artist: str = "",
    main_dir_name: str = "",
) -> DescriptorCandidate | None:
    """Return the highest-confidence non-geographic descriptor candidate.

    Selection order is score first and earliest evidence second.  The caller is
    responsible for the gate (unknown date + blank venue/location); this helper
    does not modify metadata.
    """
    paths: List[str] = []
    for path_name in [setlist_file, *(setlist_files or [])]:
        clean = os.path.normpath(str(path_name or "")) if str(path_name or "").strip() else ""
        if clean and clean not in paths and os.path.isfile(clean):
            paths.append(clean)

    candidates: List[DescriptorCandidate] = []
    serial = 0
    for path_name in paths:
        found = _header_candidates(path_name, artist, serial)
        candidates.extend(found)
        serial += MAX_HEADER_LINES + 1

    for path_name in paths:
        candidate = _filename_candidate(path_name, artist, serial)
        serial += 1
        if candidate:
            candidates.append(candidate)

    directory = _directory_candidate(main_dir_name, artist, serial)
    if directory:
        candidates.append(directory)

    usable = [candidate for candidate in candidates if candidate.score >= MIN_AUTOMATIC_SCORE]
    if not usable:
        return None

    # Deduplicate equivalent values, keeping the strongest/earliest evidence.
    best_by_value = {}
    for candidate in usable:
        key = normalized_compare_value(candidate.value)
        previous = best_by_value.get(key)
        if previous is None or (candidate.score, -candidate.order) > (previous.score, -previous.order):
            best_by_value[key] = candidate
    return sorted(best_by_value.values(), key=lambda item: (-item.score, item.order, item.value.casefold()))[0]
