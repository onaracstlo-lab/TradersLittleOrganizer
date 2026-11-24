"""Read-only adapter to the optional TLO_DBs/cities.sqlite city matcher.

This augments, never replaces, the existing region/venue/setlist parsers.
Only positive, geography-qualified, high-confidence matches may change fields.
All other outcomes preserve the old parser's result verbatim.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION

__version__ = _TLO_CANONICAL_VERSION

from functools import lru_cache
import logging
from pathlib import Path
import re
import sqlite3
import threading

from match_city import CityMatcher

_THREAD = threading.local()
_REPORTED: set[str] = set()
_WORDS = re.compile(r"[^\W_]+(?:['’.-][^\W_]+)*", re.UNICODE)
_ACCEPTED = frozenset({'EXACT', 'ALIAS', 'FUZZY_HIGH'})


def _db_path(tlo_dbs_dir: str) -> Path | None:
    """Never probe an unrelated installation when a caller supplies a DB dir."""
    if not tlo_dbs_dir:
        return None
    return Path(tlo_dbs_dir) / 'cities.sqlite'


def _open_on_thread(path: Path, stamp: tuple[int, int]) -> CityMatcher:
    identity = (str(path.resolve()), stamp)
    old_identity = getattr(_THREAD, 'identity', None)
    if old_identity != identity:
        previous = getattr(_THREAD, 'matcher', None)
        if previous is not None:
            previous.close()
        # Open a new read-only connection after an installer replaces the DB.
        _THREAD.matcher = None
        _THREAD.identity = None
        matcher = CityMatcher(path)
        _THREAD.matcher = matcher
        _THREAD.identity = identity
    return _THREAD.matcher


@lru_cache(maxsize=4096)
def _resolve_cached(path: str, stamp: tuple[int, int], city: str, region: str) -> dict:
    return _open_on_thread(Path(path), stamp).resolve(city, region)


def resolve_city(city: str, region: str, tlo_dbs_dir: str) -> dict | None:
    """Return prototype result, or None if the optional DB is unavailable.

    A missing or invalid DB never makes inventory, tagging, or setlist parsing
    fail. Fuzzy matches without explicit geography are never auto-applied.
    """
    path = _db_path(tlo_dbs_dir)
    if not path or not city or len(city) > 120 or len(region) > 120:
        return None
    try:
        stat = path.stat()
        if not path.is_file() or stat.st_size < 4096:
            return None
        stamp = (stat.st_mtime_ns, stat.st_size)
        return _resolve_cached(str(path.resolve()), stamp, city, region)
    except (OSError, ValueError, sqlite3.Error) as exc:
        # Corruption or a hot-swapped file must not abort inventory.
        key = f'{path}: {type(exc).__name__}: {exc}'
        if key not in _REPORTED:
            _REPORTED.add(key)
            logging.getLogger(__name__).warning('SQLite city matcher unavailable; existing location parsing retained: %s', key)
        return None


def corrected_city(city: str, region: str, country: str, tlo_dbs_dir: str) -> str:
    """Correct *only* safe typos; keep valid source aliases and unlisted towns.

    Country is a fallback geographic qualifier when a state/province is absent.
    Do not let a failed state-qualified query silently match a different country.
    """
    geography = region or country
    if not geography:
        return city
    result = resolve_city(city, geography, tlo_dbs_dir)
    if result and result.get('status') == 'FUZZY_HIGH':
        return str(result['canonical_city'])
    return city


def split_city_suffix(left: str, geography: str, tlo_dbs_dir: str) -> tuple[str, str] | None:
    """City-aware boundary for a location with an independently parsed region.

    Prefer the *longest* complete geographical city, never a partial substring.
    On REVIEW/AMBIGUOUS/NOT_FOUND the existing splitter remains in charge.
    A fuzzy split requires a multiword city; a one-word typo is corrected by
    the existing splitter + corrected_city() only when the boundary is known.
    """
    if not (geography and tlo_dbs_dir and left):
        return None
    words = list(_WORDS.finditer(left))
    if not words or len(words) > 18:
        return None
    best: tuple[str, str] | None = None
    # Full remaining phrase or up to four trailing city words. Exact first.
    for count in range(min(5, len(words)), 0, -1):
        start = words[-count].start()
        raw = left[start:words[-1].end()].strip(' ,;:-')
        prefix = left[:start].strip(' ,;:-')
        if not raw or (prefix and count == 1 and not re.search(r'[,;:]\s*$', left[:start])):
            # Let the historical known one-word city splitter handle these.
            continue
        result = resolve_city(raw, geography, tlo_dbs_dir)
        if not result or result.get('status') not in _ACCEPTED:
            continue
        status = result['status']
        if status == 'FUZZY_HIGH' and count < 2:
            continue
        # Single short city names can be homonymous venue or band fragments.
        if prefix and count == 1:
            continue
        display = result['canonical_city'] if status == 'FUZZY_HIGH' else raw
        best = (prefix, display)
        break
    return best


def isolated_city_suffix(text: str, tlo_dbs_dir: str) -> str:
    """Only for proven Artist + Date + City with *no* remaining venue text.

    Exact city-only matches are usable without a state only if the prototype
    considers the place unambiguous. Fuzzy guesses are never allowed here.
    """
    candidate = text.strip(' ,;:-')
    if not candidate or not re.fullmatch(r"[\w .'-]{2,80}", candidate):
        return ''
    result = resolve_city(candidate, '', tlo_dbs_dir)
    return candidate if result and result['status'] in {'EXACT', 'ALIAS'} else ''
