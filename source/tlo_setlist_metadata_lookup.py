"""Setlist-header metadata extraction helpers for artist, venue, city, region, and country evidence."""

from __future__ import annotations

__version__ = "v334"
# TLO-GI package version: v334
__version_summary__ = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
# TLO-GI version summary: Rearranges the main-window checkboxes into the requested two-row, four-column layout.

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tlo_constants import COUNTRY_ALIASES, COUNTRY_SEARCH_TERMS, MONTH_NAME_CASED_PATTERN, US_STATE_ALIASES, US_STATE_CODES
from tlo_text_utils import compact_ws, normalized_compare_value, safe_title


@dataclass(frozen=True)
class SetlistVenueLocationResult:
    artist: str = ""
    venue: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    location: str = ""
    source: str = ""
    raw: str = ""
    confidence: int = 0


def _clean_spaces(value: str) -> str:
    return compact_ws(str(value or "").strip())


def _deaccent_light(value: str) -> str:
    repl = {
        "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
        "é": "e", "è": "e", "ê": "e", "ë": "e", "á": "a", "à": "a", "ä": "a", "â": "a",
        "ö": "o", "ó": "o", "ò": "o", "ü": "u", "ú": "u", "ù": "u", "ñ": "n", "ç": "c",
        "É": "E", "Ö": "O", "Ü": "U", "Á": "A", "À": "A", "Ñ": "N", "Ç": "C",
    }
    return "".join(repl.get(ch, ch) for ch in str(value or ""))


def _norm_key(value: str) -> str:
    value = _deaccent_light(value).casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return _clean_spaces(value)


def _read_text_file(path: str) -> Tuple[str, str]:
    data = Path(path).read_bytes()
    if not data:
        return "", "empty"
    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = data.decode(enc)
            if text.count("\x00") < max(3, len(text) // 100):
                return text.replace("\r\n", "\n").replace("\r", "\n"), enc
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc).replace("\r\n", "\n").replace("\r", "\n"), enc
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n"), "utf-8-replace"


def _content_lines(text: str, limit: Optional[int] = None) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").splitlines():
        line = _clean_spaces(raw.strip("\ufeff"))
        if not line:
            continue
        if line.startswith("--------- End of "):
            continue
        lines.append(line)
        if limit is not None and len(lines) >= limit:
            break
    return lines


def _read_caret_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        first = handle.readline()
        if first.lower().startswith("sep="):
            delimiter = first.strip()[-1] if first.strip() else "^"
        else:
            delimiter = "^"
            handle.seek(0)
        try:
            return list(csv.DictReader(handle, delimiter=delimiter))
        except csv.Error:
            return []


def _load_venues(tlo_dbs_dir: str) -> List[str]:
    venues_path = Path(tlo_dbs_dir) / "venues.txt"
    venues: List[str] = []
    if not venues_path.exists():
        return []
    with venues_path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            value = _clean_spaces(raw.lstrip("\ufeff"))
            if value and not value.startswith("#") and not value.lower().startswith("sep="):
                venues.append(safe_title(value))
    seen = set()
    out: List[str] = []
    for venue in venues:
        key = _norm_key(venue)
        if len(key) >= 3 and key not in seen:
            seen.add(key)
            out.append(venue)
    return sorted(out, key=lambda item: (-len(_norm_key(item)), item.casefold()))


def _load_cities(tlo_dbs_dir: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for row in _read_caret_csv(Path(tlo_dbs_dir) / "cities.csv"):
        city = _clean_spaces(row.get("city", ""))
        if not city:
            continue
        aliases = [_clean_spaces(alias) for alias in str(row.get("aliases", "")).split("|") if _clean_spaces(alias)]
        rows.append({
            "city": city,
            "region": _clean_spaces(row.get("region", "")),
            "country": _clean_spaces(row.get("country", "")),
            "aliases": aliases,
        })
    return sorted(rows, key=lambda row: (-len(str(row["city"])), str(row["city"]).casefold()))


def _load_regions(tlo_dbs_dir: str) -> Dict[str, Dict[str, str]]:
    regions: Dict[str, Dict[str, str]] = {}
    for code in sorted(US_STATE_CODES):
        regions[code.upper()] = {"region": code.upper(), "country": "USA"}
    for alias, code in US_STATE_ALIASES.items():
        regions[_norm_key(alias)] = {"region": code.upper(), "country": "USA"}

    for row in _read_caret_csv(Path(tlo_dbs_dir) / "states_regions.csv"):
        abbrev = _clean_spaces(row.get("abbrev", ""))
        name = _clean_spaces(row.get("name", ""))
        country = _clean_spaces(row.get("country", "")) or "USA"
        if abbrev:
            regions[abbrev.upper()] = {"region": abbrev.upper(), "country": country}
        if name:
            regions[_norm_key(name)] = {"region": abbrev.upper() if abbrev else name, "country": country}
    return regions


def _load_countries(tlo_dbs_dir: str) -> Dict[str, str]:
    countries: Dict[str, str] = { _norm_key(term): COUNTRY_ALIASES.get(_norm_key(term), safe_title(term)) for term in COUNTRY_SEARCH_TERMS }
    for alias, canonical in COUNTRY_ALIASES.items():
        countries[_norm_key(alias)] = canonical
    for row in _read_caret_csv(Path(tlo_dbs_dir) / "countries.csv"):
        country = _clean_spaces(row.get("country", ""))
        canonical = _clean_spaces(row.get("canonical", country))
        if country:
            countries[_norm_key(country)] = canonical or country
    return countries


class _SupportData:
    def __init__(self, tlo_dbs_dir: str):
        self.tlo_dbs_dir = str(tlo_dbs_dir or "")
        self.venues = _load_venues(self.tlo_dbs_dir)
        self.venue_terms = [(venue, _norm_key(venue)) for venue in self.venues if _norm_key(venue)]
        self.cities = _load_cities(self.tlo_dbs_dir)
        self.regions = _load_regions(self.tlo_dbs_dir)
        self.countries = _load_countries(self.tlo_dbs_dir)


_NOISE_LINE_RE = re.compile(
    r"(?i)\b(lineage|source|transfer|taper|recorded by|encoded by|flac|checksum|md5|ffp|fingerprint|"
    r"trader'?s little helper|torrent|seeded|uploaded|audio|bitrate|sample rate|equipment|mic(?:rophone)?s?|"
    r"soundboard|audience|matrix|notes?|personnel|band members?|artwork|cover|discography)\b"
)

_TRACKLIST_START_RE = re.compile(
    r"(?i)^\s*(?:"
    r"(?:cd|disc|disk|set)\s*\d+\s*[:.-]?\s*$|"
    # Punctuated track numbers: 01. Title, 1)Title, 1) Title, 03 - Title, etc.
    r"(?:track\s*)?\d{1,3}\s*(?:[.)]|[-:])\s*\S|"
    # Track number plus bracketed running time before the title: 01 [08:23] Title.
    r"(?:track\s*)?\d{1,3}\s*(?:[.)]|[-:])?\s*(?:\[[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\]\s*)+\S|"
    # Plain one/two digit track numbers: 01 Title or 1 Title.  Do not allow
    # three/four plain digits here so dates/years at the top are not mistaken
    # for track-list starts.
    r"(?:track\s*)?(?:0?\d|[1-9]\d)\s+(?!bit\b|bits\b|khz\b|hz\b|flac\b|wav\b|source\b)\S|"
    # Common file-style set/disc/track identifiers.
    r"(?:(?:s|set)\s*\d{1,2}|(?:cd|d|disc|disk)\s*\d{1,2})\s*(?:t|track)\s*\d{1,3}\s*(?:[.)]|[-:])?\s*\S|"
    r"[a-z]\d{1,2}\s*(?:[.)]|[-:])\s+\S"
    r")"
)

_NUMBERED_EVENT_HEADER_RE = re.compile(
    r"(?i)^\s*\d{1,3}\s*[.)]\s+.*\b(?:festival|fest|jazzfestival|jazz\s*festival|"
    r"blues\s*festival|rock\s*festival|internationales|international|annual|event|fair|expo)\b"
)

_TRACKLIST_SECTION_RE = re.compile(
    r"(?i)^\s*(?:songs?|setlists?|track\s*lists?|tracks?|contents?)\s*:?.*$"
)

_CHECKSUM_OR_HASH_SECTION_RE = re.compile(
    r"(?i)^\s*(?:logfiles?|checksums?|fingerprints?|ffp|md5|st5|sfv|fpt|"
    r"verification|verify(?:ing)?|flac\s+conversion|shntool|aucdtect|"
    r"trader'?s\s+little\s+helper)\s*:?.*$"
)
_HASH_LINE_RE = re.compile(
    r"(?i)^\s*(?:[\w .,'+()\[\]{}-]+(?:\.(?:flac|wav|shn|ape|aiff?|mp3|m4a|wv))?\s*[:=]\s*)?"
    r"[a-f0-9]{32,64}\s*$"
)


def _looks_like_hash_or_checksum_boundary(line: str) -> bool:
    raw = str(line or "").strip()
    if not raw:
        return False
    if _CHECKSUM_OR_HASH_SECTION_RE.search(raw):
        return True
    return bool(_HASH_LINE_RE.search(raw))


def _looks_like_tracklist_section_line(line: str) -> bool:
    return bool(_TRACKLIST_SECTION_RE.search(str(line or "")))


def _is_strong_tracklist_line(line: str) -> bool:
    """Return True for an individual line that strongly looks like a track row.

    This intentionally excludes date headers.  A line such as ``09-20-1941``
    looks like a numbered track to a simple regex, but in a setlist header it is
    a date and must not stop metadata scanning.
    """
    raw = str(line or "").strip()
    if not raw:
        return False
    if _looks_like_date_header_line(raw) or _looks_like_explicit_metadata_line(raw):
        return False
    if _looks_like_numbered_event_header_line(raw):
        return False
    return _looks_like_tracklist_start(raw)


def _non_decorative_tail(lines: List[str], start: int, limit: int = 8) -> List[str]:
    out: List[str] = []
    for line in lines[start:start + limit]:
        if _is_decorative_separator_line(line):
            continue
        cleaned = _clean_spaces(str(line or "").strip(" *-_=#~"))
        if cleaned:
            out.append(cleaned)
    return out


def _is_confirmed_tracklist_boundary(lines: List[str], idx: int, header_so_far: List[str]) -> bool:
    """Return True when line idx is a reliable metadata/track-list boundary.

    Do not end the header on one weak track-shaped line.  Prefer a section
    label or multiple nearby track/hash lines.  For very small files, allow a
    single or two-track/one-hash ending after enough header evidence has already
    been collected.
    """
    if idx < 0 or idx >= len(lines):
        return False
    raw = str(lines[idx] or "").strip()
    if not raw:
        return False
    if _looks_like_tracklist_section_line(raw):
        return True
    if _CHECKSUM_OR_HASH_SECTION_RE.search(raw):
        return True
    if _looks_like_date_header_line(raw) or _looks_like_explicit_metadata_line(raw):
        return False

    is_hash = bool(_HASH_LINE_RE.search(raw))
    is_track = _is_strong_tracklist_line(raw)
    if not (is_hash or is_track):
        return False

    tail = _non_decorative_tail(lines, idx, 8)
    if not tail:
        return False
    track_or_hash_count = 0
    consecutive = 0
    for item in tail:
        item_is_hash = bool(_HASH_LINE_RE.search(item)) or bool(_CHECKSUM_OR_HASH_SECTION_RE.search(item))
        item_is_track = _is_strong_tracklist_line(item)
        if item_is_hash or item_is_track:
            track_or_hash_count += 1
            consecutive += 1
        else:
            break
    if consecutive >= 2 or track_or_hash_count >= 3:
        return True

    # Tiny files may legitimately contain a complete header followed by a single
    # track or checksum/hash line.  Permit that only after clear header evidence
    # exists and there is little remaining content to misclassify.
    remaining_non_decorative = _non_decorative_tail(lines, idx, 4)
    header_evidence_count = sum(
        1 for line in header_so_far
        if _looks_like_date_header_line(line)
        or _looks_like_explicit_metadata_line(line)
        or _is_usable_metadata_candidate_line(line)
    )
    if header_evidence_count >= 3 and len(remaining_non_decorative) <= 2:
        return True

    return False


def _is_setlist_metadata_scan_boundary(line: str) -> bool:
    # Legacy single-line predicate retained for conservative call sites.  Main
    # header scanning uses _is_confirmed_tracklist_boundary() with look-ahead.
    raw = str(line or "").strip()
    if not raw:
        return False
    if _looks_like_tracklist_section_line(raw) or _CHECKSUM_OR_HASH_SECTION_RE.search(raw):
        return True
    if _looks_like_date_header_line(raw) or _looks_like_explicit_metadata_line(raw):
        return False
    return (_is_header_terminating_tracklist_start(raw) and not _looks_like_date_header_line(raw)) or bool(_HASH_LINE_RE.search(raw))


def _looks_like_numbered_event_header_line(line: str) -> bool:
    """Return True for numbered event/header lines that are not tracks.

    Old setlists sometimes put event names in the header, e.g.
    ``27. Internationales Jazzfestival``.  Those lines look like track 27 to a
    simple boundary regex, but they should not terminate metadata scanning.
    """
    raw = str(line or "").strip()
    if not raw:
        return False
    return bool(_NUMBERED_EVENT_HEADER_RE.search(raw))


def _looks_like_tracklist_start(line: str) -> bool:
    return bool(_TRACKLIST_START_RE.search(str(line or "")))


def _is_header_terminating_tracklist_start(line: str) -> bool:
    raw = str(line or "").strip()
    return (
        _looks_like_tracklist_start(raw)
        and not _looks_like_date_header_line(raw)
        and not _looks_like_numbered_event_header_line(raw)
    )


def _metadata_header_lines(lines: List[str], limit: int = 80) -> List[str]:
    header: List[str] = []
    bounded = lines[:limit]
    for idx, line in enumerate(bounded):
        if _is_confirmed_tracklist_boundary(bounded, idx, header):
            break
        header.append(line)
    return header


_FALSE_HEADER_KEYWORDS_RE = re.compile(
    r"(?i)\b(this|these|those|please|note|notes|recording|recorded|uploaded|seeded|shared|"
    r"download|torrent|thanks|enjoy|lineage|source|transfer|taper|equipment|microphones?|"
    r"originally|converted|remastered|sorry|warning|do not|don't)\b"
)


def _word_tokens(line: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9&.'-]+", str(line or ""))


_EXPLICIT_METADATA_LABEL_RE = re.compile(
    r"(?i)^\s*[\*#~_=\- ]{0,12}\s*"
    r"(artist|band|performer|act|venue|location|loc|city|state|region|province|country|date|place)"
    r"\s*(?::|=|-|\u2013|\u2014)\s*(\S.*)$"
)


def _explicit_metadata_match(line: str) -> Optional[Tuple[str, str]]:
    """Return a start-of-line explicit metadata label and value, if present.

    Labels are accepted only near the beginning of a line, after optional light
    decoration, and must use a separator such as ':', '=', or '-'.  This keeps
    embedded prose such as "the venue was ..." from becoming authoritative
    metadata while still accepting common header forms like "Venue- Fillmore"
    and "location - Boston, MA".
    """
    raw = str(line or "").strip()
    if not raw:
        return None
    match = _EXPLICIT_METADATA_LABEL_RE.match(raw)
    if not match:
        return None
    value = _clean_spaces(match.group(2).strip(" -*#~_="))
    if not value:
        return None
    return _norm_key(match.group(1)), value


def _looks_like_explicit_metadata_line(line: str) -> bool:
    return _explicit_metadata_match(line) is not None


def _looks_like_false_header_commentary_line(line: str) -> bool:
    """Return True for leading commentary/noise before the real setlist header.

    Some setlists begin with recorder comments, warnings, or decorated notes.
    Those lines should not be treated as artist/venue/location header lines.
    """
    raw = str(line or "").strip()
    if not raw:
        return True
    if _looks_like_explicit_metadata_line(raw):
        return False

    stripped = raw.strip("*-_=#~ ")
    if not stripped:
        return True
    if _NOISE_LINE_RE.search(raw):
        return True

    words = _word_tokens(stripped)
    word_count = len([w for w in words if re.search(r"[A-Za-z]", w)])
    if word_count == 0:
        return True

    # Decorative/comment blocks often use asterisks or rule characters but still
    # contain full sentences about the recording.
    decorated = raw != stripped
    sentence_punct = bool(re.search(r"[.!?;]", stripped))
    lower_words = sum(1 for w in words if w[:1].islower())
    lower_ratio = lower_words / max(1, len(words))

    if decorated and word_count >= 4:
        return True
    if word_count >= 12:
        return True
    if word_count >= 8 and (sentence_punct or lower_ratio >= 0.45):
        return True
    if word_count >= 6 and _FALSE_HEADER_KEYWORDS_RE.search(stripped):
        return True
    return False


def _looks_like_metadata_header_start(line: str) -> bool:
    """Return True for the first plausible artist/metadata line after commentary."""
    raw = str(line or "").strip()
    if not raw:
        return False
    if _looks_like_tracklist_start(raw) or _NOISE_LINE_RE.search(raw):
        return False
    if _looks_like_explicit_metadata_line(raw):
        return True
    stripped = raw.strip("*-_=#~ ")
    if not stripped or _looks_like_false_header_commentary_line(stripped):
        return False
    words = _word_tokens(stripped)
    alpha_count = sum(ch.isalpha() for ch in stripped)
    if 1 <= len(words) <= 6 and alpha_count >= 2 and len(stripped) <= 90:
        if not re.search(r"[.!?;]$", stripped):
            return True
    # Location-like lines such as Westwood, CA or Boca Raton Florida are also
    # plausible header starts when an artist line is absent.
    if len(stripped) <= 90 and re.search(r"[A-Za-z]", stripped) and re.search(r",\s*[A-Z]{2}\b", stripped):
        return True
    return False


_MAX_METADATA_CANDIDATE_LINE_CHARS = 120

COMMON_NON_US_REGION_TERMS = {
    "new south wales", "nsw", "victoria", "vic", "queensland", "qld",
    "south australia", "western australia", "tasmania", "tas",
    "australian capital territory", "act", "northern territory", "nt",
    "ontario", "on", "quebec", "québec", "qc", "british columbia", "bc",
    "alberta", "ab", "manitoba", "mb", "saskatchewan", "sk",
    "nova scotia", "ns", "new brunswick", "nb", "newfoundland",
    "newfoundland and labrador", "labrador", "nl", "prince edward island", "pe",
    "yukon", "yt", "northwest territories", "nu", "nunavut",
}

_CITY_PREFIX_TERMS = [
    "Marina Del", "St", "St.", "Saint", "San", "Santa", "Los", "Las", "New",
    "West", "North", "East", "South", "La", "Le", "El", "De", "Del",
    "Port", "Fort", "Mount", "Mt", "Lake", "Rio", "Río", "Sankt",
]
_CITY_PREFIX_KEYS = [tuple(_norm_key(term).split()) for term in _CITY_PREFIX_TERMS if _norm_key(term)]
_CITY_PREFIX_KEYS.sort(key=lambda parts: (-len(parts), parts))


def _line_word_count(line: str) -> int:
    return len([w for w in _word_tokens(line) if re.search(r"[A-Za-z]", w)])


def _looks_like_sentence_prose_line(line: str) -> bool:
    """Return True for prose/commentary lines that must not be venue/location evidence."""
    raw = str(line or "").strip()
    if not raw:
        return True
    if _looks_like_explicit_metadata_line(raw):
        return False
    stripped = raw.strip("*-_=#~ ")
    if not stripped:
        return True
    words = _word_tokens(stripped)
    word_count = len([w for w in words if re.search(r"[A-Za-z]", w)])
    if word_count == 0:
        return True
    if len(stripped) > _MAX_METADATA_CANDIDATE_LINE_CHARS:
        return True
    if _NOISE_LINE_RE.search(stripped):
        return True
    sentence_punct = bool(re.search(r"[.!?;]", stripped))
    lower_words = sum(1 for w in words if w[:1].islower())
    lower_ratio = lower_words / max(1, len(words))
    if word_count >= 10:
        return True
    if word_count >= 7 and (sentence_punct or lower_ratio >= 0.45):
        return True
    if word_count >= 5 and sentence_punct and lower_ratio >= 0.30:
        return True
    return False




_AIRDATE_OR_BROADCAST_TAIL_RE = re.compile(
    r"(?i)\s*(?:;|\||\s[-–—]+\s)\s*(?:air\s*date|broadcast(?:\s*date)?|aired|simulcast|telecast|tv\b|radio\b)\b.*$"
)
_TRAILING_SLASH_DATE_RE = re.compile(r"\s+\d{1,2}\s*/\s*\d{1,2}\s*/\s*(?:\d{2}|(?:19|20)\d{2})\s*$")
_TRAILING_NUMERIC_DATE_RE = re.compile(
    r"\s+(?:(?:19|20)\d{2}|\d{1,2})\s*[-_. ]\s*\d{1,2}\s*[-_. ]\s*(?:\d{1,2}|(?:19|20)\d{2})\s*$"
)
_TRAILING_TEXT_DATE_RE = re.compile(
    rf"\s+(?:"
    rf"{MONTH_NAME_CASED_PATTERN}\.?\s*,?\s*\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?(?:\s*,?\s*(?:\d{{2}}|(?:19|20)\d{{2}}))?|"
    rf"\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?\s*{MONTH_NAME_CASED_PATTERN}\.?(?:\s*(?:\d{{2}}|(?:19|20)\d{{2}}))?"
    rf")\s*$"
)



def is_setlist_metadata_scan_boundary(line: str) -> bool:
    """Public wrapper for deciding where setlist metadata scanning must stop."""
    return _is_setlist_metadata_scan_boundary(line)


def explicit_metadata_match(line: str) -> Optional[Tuple[str, str]]:
    """Public wrapper for matching explicit metadata header lines."""
    return _explicit_metadata_match(line)


def looks_like_sentence_prose_line(line: str) -> bool:
    """Public wrapper for excluding prose/commentary from metadata fields."""
    return _looks_like_sentence_prose_line(line)

def _trim_explicit_metadata_value_tail(value: str) -> str:
    """Trim broadcast/source tails from an explicit metadata value.

    Explicit header lines such as ``VENUE: Madison Square Garden, New York
    23/12/72; Air date: ...`` are useful metadata even though the complete
    value looks like prose.  Trim the secondary/broadcast clause first and let
    downstream venue/location splitting inspect the remaining concise value.
    """
    cleaned = _clean_spaces(str(value or "").strip(" -*#~_="))
    if not cleaned:
        return ""
    cleaned = _AIRDATE_OR_BROADCAST_TAIL_RE.sub("", cleaned)
    return _clean_spaces(cleaned.strip(" ,;.-"))


def _strip_trailing_performance_date_from_metadata_value(value: str) -> str:
    """Remove a trailing date token after extracting it as date evidence elsewhere."""
    cleaned = _trim_explicit_metadata_value_tail(value)
    if not cleaned:
        return ""
    for _ in range(3):
        before = cleaned
        cleaned = _TRAILING_SLASH_DATE_RE.sub("", cleaned)
        cleaned = _TRAILING_TEXT_DATE_RE.sub("", cleaned)
        cleaned = _TRAILING_NUMERIC_DATE_RE.sub("", cleaned)
        cleaned = _clean_spaces(cleaned.strip(" ,;.-"))
        if cleaned == before:
            break
    return cleaned


def _sanitize_explicit_metadata_value(key: str, value: str) -> str:
    """Normalize an explicit metadata field before prose rejection.

    Venue/location headers may contain useful structured data followed by dates,
    air-date clauses, or station/source parentheticals.  Preserve the metadata
    prefix and remove the tail before deciding whether the line is prose.
    """
    mapped_key = _norm_key(key)
    cleaned = _clean_spaces(str(value or ""))
    if mapped_key in {"venue", "location", "loc", "place", "city", "state", "region", "province", "country"}:
        return _strip_trailing_performance_date_from_metadata_value(cleaned)
    return _trim_explicit_metadata_value_tail(cleaned)

def _is_usable_metadata_candidate_line(line: str) -> bool:
    """Return True when a header line may be searched for venue/location evidence."""
    raw = str(line or "").strip()
    if not raw:
        return False
    if _looks_like_tracklist_start(raw):
        return False
    explicit = _explicit_metadata_match(raw)
    if explicit:
        key, value = explicit
        cleaned_value = _sanitize_explicit_metadata_value(key, value)
        return bool(cleaned_value) and not _looks_like_sentence_prose_line(cleaned_value)
    return not _looks_like_sentence_prose_line(raw)


def _has_explicit_location_evidence(line: str) -> bool:
    """Return True for text that carries explicit location punctuation/region/country evidence."""
    raw = str(line or "").strip()
    if not raw:
        return False
    if re.search(r",\s*[A-Z]{2,3}\b", raw):
        return True
    if "," in raw or "/" in raw:
        return True
    if re.search(r"\b(?:in|at)\s+[A-Z][A-Za-z.'-]+", raw):
        return True
    return False


def _trim_false_header_lines(lines: List[str], scan_limit: int = 25) -> List[str]:
    """Skip leading prose/commentary before the actual setlist metadata block."""
    if not lines:
        return []
    if not _looks_like_false_header_commentary_line(lines[0]):
        return lines

    for idx, line in enumerate(lines[:scan_limit]):
        if _is_header_terminating_tracklist_start(line):
            return []
        if _looks_like_false_header_commentary_line(line):
            continue
        if _looks_like_metadata_header_start(line):
            return lines[idx:]
        # First non-commentary line after a false header is the safest available
        # starting point; do not keep earlier prose/noise.
        return lines[idx:]
    return []

_ALIAS_MAP = {
    "NYC": ("New York", "NY", "USA"),
    "NOLA": ("New Orleans", "LA", "USA"),
    "SF": ("San Francisco", "CA", "USA"),
    "DC": ("Washington", "DC", "USA"),
}

_EXACT_LOCATION_ALIASES = {
    "new york": ("New York", "NY", "USA"),
    "new york city": ("New York", "NY", "USA"),
}

_LOS_ANGELES_SHORTHAND_KEYS = {"la", "l a"}


def _is_los_angeles_shorthand(city: str, alias: str) -> bool:
    return _norm_key(city) == "los angeles" and _norm_key(alias) in _LOS_ANGELES_SHORTHAND_KEYS


def _has_explicit_california_after(text: str, pos: int) -> bool:
    tail = str(text or "")[pos:]
    return bool(re.match(r"^\s*(?:[,;/\-]|\bat\b|\bin\b)?\s*(?:CA\b|(?i:California)\b)", tail))


def _should_skip_los_angeles_shorthand(text: str, city: str, alias: str, match: Optional[re.Match]) -> bool:
    """Avoid treating LA/L.A. as Los Angeles when it is likely Louisiana.

    LA is also the U.S. state abbreviation for Louisiana.  The setlist metadata
    parser may load LA or L.A. as an alias for Los Angeles from cities.csv.  That
    shorthand is accepted only when California is explicitly present immediately
    after the alias; full "Los Angeles" text is still accepted normally.
    """
    if not match or not _is_los_angeles_shorthand(city, alias):
        return False
    return not _has_explicit_california_after(text, match.end())


def _join_location(city: str, region: str, country: str) -> str:
    if country in {"USA", "United States", "US"}:
        country = ""
    return " ".join(part for part in [city, region or country] if part)


def _region_search_terms(support: _SupportData) -> List[Tuple[str, str, str, str]]:
    terms: List[Tuple[str, str, str, str]] = []
    for key, info in support.regions.items():
        region = info.get("region", "")
        country = info.get("country", "")
        if not key or not region:
            continue
        if key.isupper():
            # State/province abbreviations are deliberately case-sensitive.
            # ME means Maine; Me in a title such as "She Left Me" must not.
            pattern = re.escape(key)
            display = key
        else:
            # Full state/region names remain case-insensitive.
            inner = r"\s+".join(re.escape(part) for part in key.split())
            pattern = rf"(?i:{inner})"
            display = key
        terms.append((display, pattern, region, country))
    return sorted(terms, key=lambda item: (-len(item[0]), item[0].casefold()))


def _region_anchor_at_end(line: str, support: _SupportData) -> Tuple[str, str, str, str]:
    """Return (left_text, region, country, raw_region) when a region ends the line."""
    terms = _region_search_terms(support)
    if not terms:
        return "", "", "", ""
    region_alt = "|".join(f"(?P<R{i}>{pattern})" for i, (_display, pattern, _region, _country) in enumerate(terms))
    match = re.search(rf"(?:^|[\s,])({region_alt})$", line)
    if not match:
        return "", "", "", ""
    matched_term_index = -1
    for i, _item in enumerate(terms):
        if match.groupdict().get(f"R{i}") is not None:
            matched_term_index = i
            break
    if matched_term_index < 0:
        return "", "", "", ""
    _display, _pattern, region, country = terms[matched_term_index]
    return _clean_spaces(line[: match.start(1)].rstrip(" ,")), region, country, _clean_spaces(match.group(1))


def _parse_trailing_region_location(line: str, support: _SupportData) -> Tuple[str, str, str, str, str, int]:
    terms = _region_search_terms(support)
    if not terms:
        return "", "", "", "", "", 0
    region_alt = "|".join(f"(?P<R{i}>{pattern})" for i, (_display, pattern, _region, _country) in enumerate(terms))
    match = re.search(rf"\b([A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+){{0,4}})(?:,|\s)+({region_alt})\b", line)
    if not match:
        return "", "", "", "", "", 0
    matched_term_index = -1
    for i, _item in enumerate(terms):
        if match.groupdict().get(f"R{i}") is not None:
            matched_term_index = i
            break
    if matched_term_index < 0:
        return "", "", "", "", "", 0
    _display, _pattern, region, country = terms[matched_term_index]
    city = _clean_spaces(match.group(1))
    return city, region, country, match.group(0), "LOCATION_TRAILING_REGION", 84


def _parse_region_country_location(line: str, support: _SupportData) -> Tuple[str, str, str, str, str, int]:
    """Parse forms such as 'Marina Del Rey, California USA'.

    This handles a city followed by a known region/state/province and then a
    trailing country.  The country may be USA/U.S./U.S.A. or any configured
    country.  Region abbreviations remain case-sensitive through
    _region_search_terms(), so title words such as 'Me' do not become 'ME'.
    """
    cleaned = _clean_spaces(line).strip(" .;")
    if not cleaned:
        return "", "", "", "", "", 0
    country_names = sorted([key for key in support.countries.keys() if len(key) >= 2], key=len, reverse=True)
    for key in country_names:
        canonical = support.countries[key]
        country_words = key.split()
        cpat = r"\s+".join(re.escape(word) for word in country_words)
        match = re.search(rf"(?:^|[\s,])({cpat})$", cleaned, re.I)
        if not match:
            continue
        before_country = _clean_spaces(cleaned[: match.start(1)].rstrip(" ,"))
        if not before_country:
            continue
        before_region, region, region_country, raw_region = _region_anchor_at_end(before_country, support)
        if before_region and region:
            # Keep country explicit for non-USA locations.  For USA, the state code
            # is enough for display, but preserving country internally is harmless.
            if canonical == "USA" or (region_country == "USA" and canonical in {"USA", "United States", "US"}):
                country = "USA"
            else:
                country = canonical
            city = _clean_spaces(before_region.strip(" ,"))
            if not city or _looks_like_sentence_prose_line(city):
                continue
            raw = _clean_spaces(f"{city} {raw_region} {match.group(1)}")
            return city, region, country, raw, "LOCATION_CITY_REGION_COUNTRY", 90
        # For non-USA countries, also handle comma-separated city/province/country
        # forms when the province/region is not in the local support files, e.g.
        # "Sydney, New South Wales Australia".  This is deliberately limited to
        # two comma-separated pieces before the country so venue-bearing strings
        # are less likely to be reinterpreted as locations.
        if canonical != "USA" and "," in before_country:
            parts = [_clean_spaces(part) for part in before_country.split(",") if _clean_spaces(part)]
            if len(parts) == 2 and parts[1].casefold() in COMMON_NON_US_REGION_TERMS:
                city, region = parts[0], parts[1]
                if city and region and not _looks_like_sentence_prose_line(city):
                    raw = _clean_spaces(f"{city} {region} {match.group(1)}")
                    return city, region, canonical, raw, "LOCATION_CITY_REGION_COUNTRY", 86
    return "", "", "", "", "", 0


def _parse_location_from_text(raw: str, support: _SupportData) -> Tuple[str, str, str, str, str, int]:
    line = _clean_spaces(str(raw or "").strip(" .;"))
    if not line:
        return "", "", "", "", "", 0

    exact_alias = _EXACT_LOCATION_ALIASES.get(_norm_key(line))
    if exact_alias:
        city, region, country = exact_alias
        return city, region, country, line, "LOCATION_EXACT_ALIAS", 94

    for alias, (city, region, country) in _ALIAS_MAP.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", line):
            return city, region, country, alias, "LOCATION_ALIAS", 95

    parsed_city, parsed_region, parsed_country, parsed_raw, parsed_pattern, parsed_conf = _parse_region_country_location(line, support)
    if parsed_city and (parsed_region or parsed_country):
        return parsed_city, parsed_region, parsed_country, parsed_raw, parsed_pattern, parsed_conf

    line_norm_blob = f" {_norm_key(line)} "
    for cityrow in support.cities:
        names = [str(cityrow.get("city", ""))] + list(cityrow.get("aliases", []))
        for name in names:
            nk = _norm_key(name)
            if not nk or f" {nk} " not in line_norm_blob:
                continue
            city = str(cityrow.get("city", ""))
            region = str(cityrow.get("region", ""))
            country = str(cityrow.get("country", ""))
            mcity = re.search(re.escape(name).replace(r"\ ", r"\s+"), line, re.I)
            if _should_skip_los_angeles_shorthand(line, city, name, mcity):
                continue
            tail = _clean_spaces(line[mcity.end():].strip(" ,;-()[]"))[:80] if mcity else ""
            tail_norm = _norm_key(tail)
            found_tail = False
            mt = re.match(r"([A-Z]{2,3})\b", tail)
            if mt and mt.group(1).upper() in support.regions:
                info = support.regions[mt.group(1).upper()]
                region = info.get("region", region)
                country = info.get("country", country)
                found_tail = True
            else:
                for key, info in support.regions.items():
                    if not key.isupper() and tail_norm.startswith(key):
                        region = info.get("region", region)
                        country = info.get("country", country)
                        found_tail = True
                        break
                if not found_tail:
                    for key, canonical in support.countries.items():
                        if len(key) >= 3 and tail_norm.startswith(key):
                            country = canonical
                            found_tail = True
                            break
            exactish = _norm_key(line) in {_norm_key(city), _norm_key(name)}
            if not found_tail and exactish:
                # A standalone city-list hit such as "Nice" is too ambiguous in
                # setlist headers and can be a comment/adjective/title fragment.
                # Require explicit state/country tail evidence or broader header
                # context with location punctuation before using DB-supplied
                # region/country values.
                continue
            if not found_tail and not _has_explicit_location_evidence(line):
                continue
            confidence = 88 if found_tail else 55
            return city, region, country, name, "LOCATION_CITY_REGION_COUNTRY_LIST", confidence

    parsed_city, parsed_region, parsed_country, parsed_raw, parsed_pattern, parsed_conf = _parse_trailing_region_location(line, support)
    if parsed_city and (parsed_region or parsed_country):
        return parsed_city, parsed_region, parsed_country, parsed_raw, parsed_pattern, parsed_conf

    country_names = sorted([key for key in support.countries.keys() if len(key) >= 3], key=len, reverse=True)
    for key in country_names:
        canonical = support.countries[key]
        # Convert normalized country key back to a loose text regexp.
        country_words = key.split()
        cpat = r"\s+".join(re.escape(word) for word in country_words)
        match = re.search(rf"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){{0,3}}),?\s+({cpat})\b", line, re.I)
        if match:
            city = _clean_spaces(match.group(1))
            return city, "", canonical, match.group(0), "LOCATION_TRAILING_COUNTRY", 52

    return "", "", "", "", "", 0




def _split_explicit_venue_value(value: str, support: _SupportData) -> Tuple[str, str, str, str, str, str, int]:
    """Split ``Venue:`` values that also carry a trailing location.

    Common setlists use a single line such as
    ``Venue: Osheaga Festival, Parc Jean-Drapeau, Montréal, QC``.  The venue
    portion may itself contain commas, so work from the right edge and accept
    the first trailing segment that parses as a location.
    """
    cleaned = _strip_trailing_performance_date_from_metadata_value(value)
    if not cleaned or "," not in cleaned:
        return cleaned, "", "", "", "", "", 0
    parts = [_clean_spaces(part) for part in cleaned.split(",") if _clean_spaces(part)]
    if len(parts) < 2:
        return cleaned, "", "", "", "", "", 0
    # Start near the right edge so comma-bearing venue names are preserved.
    for cut in range(len(parts) - 1, 0, -1):
        venue_candidate = _clean_spaces(", ".join(parts[:cut]))
        location_candidate = _clean_spaces(", ".join(parts[cut:]))
        if not venue_candidate or not location_candidate:
            continue
        city, region, country, raw, pattern_id, confidence = _parse_location_from_text(location_candidate, support)
        if city and (region or country):
            return venue_candidate, city, region, country, raw or location_candidate, pattern_id, max(confidence, 90)
    return cleaned, "", "", "", "", "", 0


def _parsed_location_city_is_only_region_or_country(city: str, support: _SupportData) -> bool:
    key = _norm_key(city)
    if not key:
        return True
    if key in support.countries:
        return True
    if key in support.regions:
        return True
    for _display, _pattern, region, _country in _region_search_terms(support):
        if key == _norm_key(region) or key == _norm_key(_display):
            return True
    return False


def _country_anchor_at_end(line: str, support: _SupportData) -> Tuple[str, str, str]:
    cleaned = _clean_spaces(str(line or "").strip(" .;"))
    if not cleaned:
        return "", "", ""
    for key in sorted([k for k in support.countries.keys() if len(k) >= 3], key=len, reverse=True):
        canonical = support.countries[key]
        cpat = r"\s+".join(re.escape(word) for word in key.split())
        match = re.search(rf"(?:^|[\s,])({cpat})$", cleaned, re.I)
        if match:
            return canonical, _clean_spaces(cleaned[: match.start(1)].rstrip(" ,")), _clean_spaces(match.group(1))
    return "", "", ""


def _city_suffix_length(tokens: List[str]) -> int:
    if not tokens:
        return 0
    max_len = min(5, len(tokens))
    norm_tokens = [_norm_key(token) for token in tokens]
    for size in range(max_len, 1, -1):
        suffix = norm_tokens[-size:]
        for prefix in _CITY_PREFIX_KEYS:
            if len(prefix) < size and tuple(suffix[:len(prefix)]) == prefix:
                return size
    return 1


def _split_unlabeled_space_combined_venue_location_line(line: str, support: _SupportData) -> Tuple[str, str, str, str, str, str, int]:
    """Split short unlabeled ``Venue City Country`` header lines.

    Example: ``Stadthalle St. Ingbert Germany`` -> venue ``Stadthalle``,
    city ``St. Ingbert``, country ``Germany``.  This is intentionally used
    only for short, header-like lines and only when at least one token remains
    on the left as a plausible venue.
    """
    cleaned = _clean_spaces(str(line or "").strip(" *-_=#~"))
    if not cleaned or "," in cleaned:
        return "", "", "", "", "", "", 0
    if _explicit_metadata_match(cleaned) or _is_header_terminating_tracklist_start(cleaned):
        return "", "", "", "", "", "", 0
    if _looks_like_sentence_prose_line(cleaned):
        return "", "", "", "", "", "", 0
    country, left, raw_country = _country_anchor_at_end(cleaned, support)
    if not country or country == "USA" or not left:
        return "", "", "", "", "", "", 0
    # Avoid reinterpreting known region/province/country location forms as
    # venue-bearing strings; those are handled by normal location parsing.
    if _parse_region_country_location(cleaned, support)[0]:
        return "", "", "", "", "", "", 0
    tokens = [token for token in left.split() if token]
    if len(tokens) < 2:
        return "", "", "", "", "", "", 0
    city_len = _city_suffix_length(tokens)
    if city_len <= 0 or city_len >= len(tokens):
        return "", "", "", "", "", "", 0
    venue = _clean_spaces(" ".join(tokens[:-city_len])).strip(" ,")
    city = _clean_spaces(" ".join(tokens[-city_len:])).strip(" ,")
    if not venue or not city:
        return "", "", "", "", "", "", 0
    if not _looks_like_unlabeled_venue_line(venue):
        return "", "", "", "", "", "", 0
    if _parsed_location_city_is_only_region_or_country(city, support):
        return "", "", "", "", "", "", 0
    raw = _clean_spaces(f"{city} {raw_country or country}")
    return venue, city, "", country, raw, "LOCATION_SPACE_COMBINED_VENUE_LOCATION", 84


def _split_unlabeled_combined_venue_location_line(line: str, support: _SupportData) -> Tuple[str, str, str, str, str, str, int]:
    """Split unlabeled header lines like ``Venue, City, Country``.

    This is deliberately narrower than normal location parsing.  It is used for
    short header lines only, after false-header/prose/track-list filtering, and
    it avoids treating a pure location such as ``Marina Del Rey, California USA``
    as venue ``Marina Del Rey`` plus location ``California USA``.
    """
    cleaned = _clean_spaces(str(line or "").strip(" *-_=#~"))
    if not cleaned or "," not in cleaned:
        return "", "", "", "", "", "", 0
    if _explicit_metadata_match(cleaned) or _looks_like_tracklist_start(cleaned):
        return "", "", "", "", "", "", 0
    if _looks_like_sentence_prose_line(cleaned):
        return "", "", "", "", "", "", 0
    parts = [_clean_spaces(part) for part in cleaned.split(",") if _clean_spaces(part)]
    if len(parts) < 2:
        return "", "", "", "", "", "", 0

    for cut in range(len(parts) - 1, 0, -1):
        venue_candidate = _clean_spaces(", ".join(parts[:cut]))
        location_candidate = _clean_spaces(", ".join(parts[cut:]))
        if not venue_candidate or not location_candidate:
            continue
        if not _looks_like_unlabeled_venue_line(venue_candidate):
            continue
        city, region, country, raw, pattern_id, confidence = _parse_location_from_text(location_candidate, support)
        if not (city and (region or country)):
            continue
        if _parsed_location_city_is_only_region_or_country(city, support):
            continue
        return venue_candidate, city, region, country, raw or location_candidate, pattern_id or "LOCATION_COMBINED_VENUE_LOCATION", max(confidence, 88)

    return "", "", "", "", "", "", 0

def _extract_explicit_fields(lines: List[str]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    key_map = {
        "artist": "artist",
        "band": "artist",
        "performer": "artist",
        "act": "artist",
        "venue": "venue",
        "location": "location",
        "loc": "location",
        "city": "city",
        "state": "region",
        "region": "region",
        "province": "region",
        "country": "country",
        "date": "date",
        "place": "location",
    }
    for line in lines[:80]:
        matched = _explicit_metadata_match(line)
        if not matched:
            continue
        key, value = matched
        mapped = key_map.get(key)
        cleaned_value = _sanitize_explicit_metadata_value(key, value)
        if mapped and cleaned_value and not _looks_like_sentence_prose_line(cleaned_value):
            fields.setdefault(mapped, cleaned_value)
    return fields


def _looks_like_unlabeled_venue_line(line: str) -> bool:
    raw = _clean_spaces(str(line or "").strip(" *-_=#~"))
    if not raw:
        return False
    if _explicit_metadata_match(raw) or _looks_like_tracklist_start(raw):
        return False
    if _looks_like_sentence_prose_line(raw):
        return False
    if len(raw) > 90 or _line_word_count(raw) > 8:
        return False
    # Do not infer dates, locations, source/lineage labels, or obvious notes as venues.
    if re.search(r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", raw):
        return False
    if re.search(r"\b(?:19|20)\d{2}\b", raw):
        return False
    if re.search(r"(?i)^(?:source|lineage|quality|recorded|taped|transfer|notes?|setlist|band|members?)\b", raw):
        return False
    return bool(re.search(r"[A-Za-z]", raw))


def _infer_unlabeled_venue_near_location(lines: List[str], location_index: int) -> str:
    # Common old-school headers are Artist / Venue / Location / Date.  If a
    # location is found on line N and line N-1 is short/header-like, use line
    # N-1 as the venue only when there is at least one earlier line that can be
    # the artist/header.  This avoids treating Artist / Location / Date as a
    # venue-bearing header.
    if location_index < 2 or location_index >= len(lines):
        return ""
    candidate = lines[location_index - 1]
    if not _looks_like_unlabeled_venue_line(candidate):
        return ""
    return _clean_spaces(candidate.strip(" *-_=#~"))


WEEKDAY_CASED_PATTERN = r"(?:mon|monday|tue|tuesday|wed|wednesday|thu|thursday|fri|friday|sat|saturday|sun|sunday|MON|MONDAY|TUE|TUESDAY|WED|WEDNESDAY|THU|THURSDAY|FRI|FRIDAY|SAT|SATURDAY|SUN|SUNDAY|Mon|Monday|Tue|Tuesday|Wed|Wednesday|Thu|Thursday|Fri|Friday|Sat|Saturday|Sun|Sunday)"
_DATE_HEADER_RE = re.compile(
    rf"^(?:"
    rf"{WEEKDAY_CASED_PATTERN}[,\s-]+)?"
    rf"(?:\d{{1,2}}(?:\s*[-_.]\s*|\s+)\d{{1,2}}(?:\s*[-_.]\s*|\s+)(?:\d{{2}}|(?:19|20)\d{{2}})|"
    rf"(?:19|20)\d{{2}}(?:\s*[-_.]\s*|\s+)\d{{1,2}}(?:\s*[-_.]\s*|\s+)\d{{1,2}}|"
    rf"\d{{1,2}}\s*/\s*\d{{1,2}}\s*/\s*(?:\d{{2}}|(?:19|20)\d{{2}})|"
    rf"(?:19|20)\d{{2}}[ -]\d{{4}}|"
    rf"{MONTH_NAME_CASED_PATTERN}[\s._,\-]*\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?(?:[\s._,\-]*(?:\d{{2}}|(?:19|20)\d{{2}}))?|"
    rf"\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?[\s._,\-]*{MONTH_NAME_CASED_PATTERN}(?:[\s._,\-]*(?:\d{{2}}|(?:19|20)\d{{2}}))?"
    rf")\s*$"
)


def _looks_like_date_header_line(line: str) -> bool:
    raw = _clean_spaces(str(line or "").strip(" *-_=#~"))
    if not raw or len(raw) > 80:
        return False
    return bool(_DATE_HEADER_RE.match(raw))


def _is_decorative_separator_line(line: str) -> bool:
    raw = str(line or "").strip()
    if not raw:
        return True
    if re.search(r"[A-Za-z0-9]", raw):
        return False
    return len(raw) >= 3


def _structured_scan_items(lines: List[str], limit: int = 160) -> List[Tuple[int, str]]:
    """Return non-decorative lines for conservative multi-line header matching.

    The scan is bounded by a confirmed true track-list or checksum/hash/log
    section.  A single date-looking or track-shaped line is not enough to stop
    the scan, which prevents valid Artist/Date/Venue/Location headers from
    being truncated.
    """
    items: List[Tuple[int, str]] = []
    bounded = lines[:limit]
    header_so_far: List[str] = []
    for idx, line in enumerate(bounded):
        if _is_confirmed_tracklist_boundary(bounded, idx, header_so_far):
            break
        if _is_decorative_separator_line(line):
            continue
        cleaned = _clean_spaces(str(line or "").strip(" *-_=#~"))
        if cleaned:
            items.append((idx, cleaned))
            header_so_far.append(cleaned)
    return items


def _looks_like_unlabeled_artist_header_line(line: str, support: Optional[_SupportData] = None) -> bool:
    raw = _clean_spaces(str(line or "").strip(" *-_=#~"))
    if not raw:
        return False
    if _looks_like_date_header_line(raw) or _looks_like_tracklist_start(raw):
        return False
    if _looks_like_sentence_prose_line(raw):
        return False
    if support is not None and _parse_location_from_text(raw, support)[0]:
        # Avoid treating a location-only line as the artist in a structured block.
        return False
    return 1 <= _line_word_count(raw) <= 8 and len(raw) <= 100


def _parse_unlabeled_location_header_line(line: str, support: _SupportData) -> Tuple[str, str, str, str, str, int]:
    if not _is_usable_metadata_candidate_line(line):
        return "", "", "", "", "", 0
    return _parse_location_from_text(line, support)


def _extract_structured_unlabeled_header_block(lines: List[str], support: _SupportData) -> Tuple[str, str, str, str, str, str, int]:
    """Extract strict unlabeled Artist/Venue/Location/Date style headers.

    Handles both ordinary top-of-file headers and repeated/copied header blocks
    later in a text file.  Accepted shapes include:
      Artist / Venue / Location / Date
      Artist / Date / Venue / Location
      Artist / Venue, City, Country / Date

    The match is intentionally multi-line and location-anchored.  A single
    arbitrary location-looking song title cannot pass by itself.
    """
    items = _structured_scan_items(lines)
    if len(items) < 3:
        return "", "", "", "", "", "", 0

    for pos, (_idx, line) in enumerate(items):
        # One-line combined venue/location may sit below an artist/event header.
        if pos >= 1:
            split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_unlabeled_combined_venue_location_line(line, support)
            if split_venue and split_city and (split_region or split_country):
                next_is_date = pos + 1 < len(items) and _looks_like_date_header_line(items[pos + 1][1])
                prev_is_artist = _looks_like_unlabeled_artist_header_line(items[pos - 1][1], support)
                if prev_is_artist or next_is_date:
                    return split_venue, split_city, split_region, split_country, split_raw or line, split_pattern or "LOCATION_STRUCTURED_UNLABELED_HEADER", max(split_conf, 88)
            split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_unlabeled_space_combined_venue_location_line(line, support)
            if split_venue and split_city and (split_region or split_country):
                next_is_date = pos + 1 < len(items) and _looks_like_date_header_line(items[pos + 1][1])
                prev_is_artist_or_event = _looks_like_unlabeled_artist_header_line(items[pos - 1][1], support) or _looks_like_numbered_event_header_line(items[pos - 1][1])
                if prev_is_artist_or_event or next_is_date:
                    return split_venue, split_city, split_region, split_country, split_raw or line, split_pattern or "LOCATION_STRUCTURED_UNLABELED_HEADER", max(split_conf, 84)

        if not _looks_like_unlabeled_artist_header_line(line, support):
            continue

        # Artist / Venue / Location / Date
        if pos + 2 < len(items):
            venue_line = items[pos + 1][1]
            location_line = items[pos + 2][1]
            if _looks_like_unlabeled_venue_line(venue_line):
                city, region, country, raw, pattern_id, conf = _parse_unlabeled_location_header_line(location_line, support)
                if city and (region or country):
                    date_nearby = pos + 3 < len(items) and _looks_like_date_header_line(items[pos + 3][1])
                    if date_nearby or pos <= 10:
                        return venue_line, city, region, country, raw or location_line, pattern_id or "LOCATION_STRUCTURED_UNLABELED_HEADER", max(conf, 88)

        # Artist / Date / Venue / Location
        if pos + 3 < len(items) and _looks_like_date_header_line(items[pos + 1][1]):
            venue_line = items[pos + 2][1]
            location_line = items[pos + 3][1]
            if _looks_like_unlabeled_venue_line(venue_line):
                city, region, country, raw, pattern_id, conf = _parse_unlabeled_location_header_line(location_line, support)
                if city and (region or country):
                    return venue_line, city, region, country, raw or location_line, pattern_id or "LOCATION_STRUCTURED_UNLABELED_HEADER", max(conf, 88)

        # Artist / combined Venue, City, Country / Date
        if pos + 1 < len(items):
            combined_line = items[pos + 1][1]
            split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_unlabeled_combined_venue_location_line(combined_line, support)
            if split_venue and split_city and (split_region or split_country):
                date_nearby = pos + 2 < len(items) and _looks_like_date_header_line(items[pos + 2][1])
                if date_nearby or pos <= 10:
                    return split_venue, split_city, split_region, split_country, split_raw or combined_line, split_pattern or "LOCATION_STRUCTURED_UNLABELED_HEADER", max(split_conf, 88)

    return "", "", "", "", "", "", 0


def _best_venue_from_lines(lines: List[str], support: _SupportData) -> Tuple[str, str, int, int]:
    best: Tuple[str, str, int, int] = ("", "", 0, -1)
    usable_lines = [
        (idx, line, f" {_norm_key(line)} ")
        for idx, line in enumerate(lines[:80])
        if _is_usable_metadata_candidate_line(line)
    ]
    if not usable_lines:
        return best
    for venue, key in support.venue_terms:
        if len(key) < 3:
            continue
        line_index = -1
        raw_line = venue
        for idx, line, line_norm in usable_lines:
            if f" {key} " in line_norm:
                line_index = idx
                raw_line = line
                break
        if line_index < 0:
            continue
        score = 72 + min(20, len(key) // 4) - max(0, line_index) // 2
        if line_index < 10:
            score += 15
        if score > best[2]:
            best = (venue, raw_line, score, line_index)
    return best



def extract_setlist_venue_location(setlist_file: str, tlo_dbs_dir: str) -> SetlistVenueLocationResult:
    """Extract venue/location from one selected setlist text file.

    This is intentionally local-only and intended for the non-compliant path.
    It uses TLOHome/TLO_DBs support files: venues.txt plus optional cities.csv,
    states_regions.csv, and countries.csv.
    """
    if not setlist_file:
        return SetlistVenueLocationResult(source="setlist_metadata:missing_setlist_file")
    if not os.path.exists(setlist_file) or not os.path.isfile(setlist_file):
        return SetlistVenueLocationResult(source="setlist_metadata:unreadable_setlist_file", raw=setlist_file)

    try:
        text, _encoding = _read_text_file(setlist_file)
    except Exception as exc:
        return SetlistVenueLocationResult(source="setlist_metadata:read_error", raw=str(exc))

    lines = _content_lines(text, 100)
    if not lines:
        return SetlistVenueLocationResult(source="setlist_metadata:empty_setlist")
    metadata_lines = _trim_false_header_lines(_metadata_header_lines(lines, 80))
    if not metadata_lines:
        return SetlistVenueLocationResult(source="setlist_metadata:no_usable_header_metadata_before_tracklist")

    support = _SupportData(tlo_dbs_dir)
    structured_venue, structured_city, structured_region, structured_country, structured_raw, structured_pattern, structured_conf = _extract_structured_unlabeled_header_block(metadata_lines, support)
    fields = _extract_explicit_fields(metadata_lines)

    artist = safe_title(_clean_spaces(fields.get("artist", "")))
    venue = _clean_spaces(fields.get("venue", ""))
    raw_venue = venue
    venue_confidence = 0
    venue_line_index = -1
    city = region = country = raw_location = pattern_id = ""
    location_confidence = 0
    if venue:
        split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_explicit_venue_value(venue, support)
        if split_venue and (split_city or split_region or split_country):
            venue = split_venue
            city, region, country = split_city, split_region, split_country
            raw_location, pattern_id, location_confidence = split_raw, split_pattern or "LOCATION_EXPLICIT_VENUE_TRAILING_LOCATION", split_conf
        venue_confidence = 95
    elif structured_venue and structured_city and (structured_region or structured_country):
        venue = structured_venue
        raw_venue = structured_venue
        venue_confidence = max(84, structured_conf)
        city, region, country = structured_city, structured_region, structured_country
        raw_location = structured_raw
        pattern_id = structured_pattern or "LOCATION_STRUCTURED_UNLABELED_HEADER"
        location_confidence = max(84, structured_conf)
    else:
        venue, raw_venue, venue_confidence, venue_line_index = _best_venue_from_lines(metadata_lines, support)

    if not city and (fields.get("location") or fields.get("city")):
        raw_location = fields.get("location") or " ".join([fields.get("city", ""), fields.get("region", ""), fields.get("country", "")])
        city, region, country, _raw, pattern_id, location_confidence = _parse_location_from_text(raw_location, support)
        if not city and fields.get("city"):
            city = fields.get("city", "")
            region = fields.get("region", "")
            country = fields.get("country", "")
            pattern_id = "LOCATION_EXPLICIT_KEY"
            location_confidence = 80

    candidate_line_indexes: List[int] = []
    if venue_line_index >= 0:
        candidate_line_indexes.extend([venue_line_index, venue_line_index + 1, venue_line_index - 1])
    candidate_line_indexes.extend(range(0, min(20, len(metadata_lines))))
    seen_indexes = set()
    for idx in candidate_line_indexes:
        if city or idx < 0 or idx >= len(metadata_lines) or idx in seen_indexes:
            continue
        seen_indexes.add(idx)
        line = metadata_lines[idx]
        if not _is_usable_metadata_candidate_line(line):
            continue
        if not venue:
            split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_unlabeled_combined_venue_location_line(line, support)
            if split_venue and split_city and (split_region or split_country):
                venue = split_venue
                raw_venue = split_venue
                venue_confidence = max(venue_confidence, 86)
                city, region, country = split_city, split_region, split_country
                raw_location = split_raw or line
                pattern_id = split_pattern or "LOCATION_COMBINED_VENUE_LOCATION"
                location_confidence = max(location_confidence, split_conf)
                break
            split_venue, split_city, split_region, split_country, split_raw, split_pattern, split_conf = _split_unlabeled_space_combined_venue_location_line(line, support)
            if split_venue and split_city and (split_region or split_country):
                venue = split_venue
                raw_venue = split_venue
                venue_confidence = max(venue_confidence, 84)
                city, region, country = split_city, split_region, split_country
                raw_location = split_raw or line
                pattern_id = split_pattern or "LOCATION_SPACE_COMBINED_VENUE_LOCATION"
                location_confidence = max(location_confidence, split_conf)
                break
        # If the line contains the venue, remove the venue text before parsing location.
        parse_line = line
        if venue:
            parse_line = re.sub(re.escape(venue), " ", parse_line, flags=re.I)
        parsed_city, parsed_region, parsed_country, parsed_raw, parsed_pattern, parsed_conf = _parse_location_from_text(parse_line, support)
        if parsed_city and (parsed_region or parsed_country):
            city, region, country = parsed_city, parsed_region, parsed_country
            raw_location, pattern_id, location_confidence = parsed_raw or line, parsed_pattern, parsed_conf
            if not venue:
                inferred_venue = _infer_unlabeled_venue_near_location(metadata_lines, idx)
                if inferred_venue:
                    venue = inferred_venue
                    raw_venue = inferred_venue
                    venue_confidence = max(venue_confidence, 78)
            if idx == venue_line_index or abs(idx - venue_line_index) == 1:
                location_confidence += 8
            break

    location = _join_location(city, region, country)
    raw = _clean_spaces(" | ".join(part for part in [raw_venue, raw_location] if part))
    confidence = max(venue_confidence, location_confidence)
    if venue and location:
        confidence = max(confidence, 86)
    source = "setlist_metadata"
    if pattern_id:
        source = f"setlist_metadata:{pattern_id}"
    return SetlistVenueLocationResult(
        artist=artist,
        venue=venue,
        city=city,
        region=region,
        country=country,
        location=location,
        source=source,
        raw=raw,
        confidence=min(99, int(confidence or 0)),
    )
