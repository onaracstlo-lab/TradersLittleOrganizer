"""Conservative adapter for the optional external TLO venue catalog."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from functools import lru_cache
import logging
import re
from pathlib import Path
import sqlite3
import threading

from tlo_venue_matcher import VenueMatcher, exact, key

_LOCK = threading.RLock()


@lru_cache(maxsize=2)
def _load(path: str, stamp: tuple[int, int, int, int]) -> VenueMatcher | None:
    try:
        return VenueMatcher(path)
    except (OSError, ValueError, sqlite3.Error) as exc:
        logging.getLogger(__name__).warning('Venue catalog unavailable; retaining existing parser: %s', exc)
        return None


def get_matcher(tlo_dbs_dir: str) -> VenueMatcher | None:
    if not tlo_dbs_dir:
        return None
    try:
        path = (Path(tlo_dbs_dir) / 'venues.sqlite').resolve()
        stat = path.stat()
        if not path.is_file():
            return None
        with _LOCK:
            return _load(str(path), (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns))
    except OSError:
        return None


def match_full_venue(value: str, tlo_dbs_dir: str, *, artist: str = '', city: str = '',
                     state: str = '', explicit: bool = False, corroborated: bool = False):
    """Only accept a complete venue field; never discard residual text.

    Context-required/provisional entries in opaque path text require independent
    evidence. Distinct historical display names are returned as supplied by the
    matcher, never by its anchor. No fuzzy edits or substring truncation.
    """
    if not value or len(value) > 240 or '\n' in value or '\r' in value:
        return None
    value = value.strip()
    if not value or not key(value) or key(value) == key(artist):
        return None
    matcher = get_matcher(tlo_dbs_dir)
    if matcher is None:
        return None
    # Exact indexed key or controlled complete room expansion. Passing explicit
    # avoids interpreting the date in a legitimate named venue as a show date.
    # The caller's known geography is for disambiguation, not a text boundary
    # inside an already isolated venue field.
    found = matcher.candidates(value, city=city, state=state, explicit=True)
    eligible = []
    for c in found:
        if value[:c.start].strip() or value[c.end:].strip():
            continue
        if c.reason == 'legacy_compact':
            continue
        structural_context = c.reason in {'structural_expansion', 'corroborated_expansion'} and bool(c.institution) and key(c.venue) == key(value)
        if not explicit and not corroborated and not structural_context and c.strength not in {'strong', 'supported'}:
            local = matcher.locations.get((key(value), key(city), key(state)), set())
            if c.venue not in local:
                continue
        if c.reason == 'room' and not (explicit or corroborated or (city and state) or (c.strength in {'strong', 'supported'} and len(value.split()) >= 2)):
            continue
        # Compact keys may collide with punctuation-distinct phrases. Only
        # accept an indexed spelling with the same case-folded text, or a
        # punctuation-only variation of the exact display itself.
        rows = matcher.index.get(key(value), [])
        if not any(exact(r[0]) == exact(value) and r[2] == c.venue for r in rows) and key(c.venue) != key(value):
            continue
        if key(c.venue) == key(artist):
            continue
        eligible.append(c)
    if not eligible:
        return None
    best = eligible[0]
    if any(c.score == best.score and c.venue != best.venue for c in eligible[1:]):
        return None
    return best


def _regional_spelling_key(value: str) -> str:
    """Treat valid English regional spellings as equivalent, not typos."""
    value = re.sub(r'\b(?:theatre|theater)\b', 'theater', value.casefold())
    return re.sub(r'\b(?:centre|center)\b', 'center', value)


def safe_venue_display(value: str, candidate) -> str:
    """Guard database display quality; recognize unsafe aliases without renaming.

    Preserve source casing (including acronyms), avoid new unsafe filename
    characters and suspicious terminal delimiters or fused ordinals.
    """
    display = candidate.venue
    if _regional_spelling_key(value) == _regional_spelling_key(display):
        return value
    if not display.strip() or display != display.strip() or display.endswith((",", ";", ":", "-")):
        return value
    if set(re.findall(r'[\\/:*?"<>|]', display)) - set(re.findall(r'[\\/:*?"<>|]', value)):
        return value
    if re.search(r"(?i)\b\d+(?:st|nd|rd|th)[a-z]+", display):
        return value
    if candidate.reason == "historical" and key(value) != key(display):
        return value
    # Do not drop room/stage numbers or a city already present in the venue text.
    numbers = re.findall(r"\d+", value)
    if numbers != re.findall(r"\d+", display):
        return value
    return display


def normalized_venue(value: str, tlo_dbs_dir: str, **context) -> str:
    candidate = match_full_venue(value, tlo_dbs_dir, **context)
    return safe_venue_display(value, candidate) if candidate is not None else value
