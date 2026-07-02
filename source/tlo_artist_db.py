__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple
from collections import deque

from tlo_db_validation import validate_artist_sqlite
from tlo_text_utils import compact_ws

THE_PREFIX_RE = re.compile(r"^(?:the|a)\s+", re.IGNORECASE)
THE_SUFFIX_RE = re.compile(r",\s*(?:the|a)$", re.IGNORECASE)


def _strip_article_forms(text: str) -> str:
    value = compact_ws(text)
    if not value:
        return ""
    value = THE_PREFIX_RE.sub("", value)
    value = THE_SUFFIX_RE.sub("", value)
    return compact_ws(value)


def _letters_only(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalpha())


def artist_search_variants(text: str) -> List[str]:
    variants: List[str] = []
    seen = set()
    for candidate in (compact_ws(text), _strip_article_forms(text)):
        cleaned = compact_ws(candidate)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            variants.append(cleaned)
    return variants


@dataclass
class ArtistMatcher:
    db_path: str
    exact_map: Dict[str, Set[str]] = field(default_factory=dict)
    master_aliases: Dict[str, List[str]] = field(default_factory=dict)
    master_norms: Dict[str, Set[str]] = field(default_factory=dict)
    query_cache: Dict[str, Tuple[str, Tuple[str, ...]]] = field(default_factory=dict)
    recent_masters: Deque[str] = field(default_factory=lambda: deque(maxlen=5))


def load_artist_matcher(config) -> ArtistMatcher:
    db_path = validate_artist_sqlite(config)
    matcher = ArtistMatcher(db_path=db_path)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        artist_rows = cur.execute("SELECT artist_id, master_name FROM artists ORDER BY artist_id").fetchall()
        term_rows = cur.execute(
            "SELECT artist_id, term_text FROM terms ORDER BY artist_id, term_order"
        ).fetchall()
    except sqlite3.Error as exc:
        conn.close()
        raise RuntimeError(f"Artist database query failed: {db_path} | {exc}") from exc
    finally:
        conn.close()

    artist_by_id = {int(artist_id): compact_ws(master_name) for artist_id, master_name in artist_rows}
    master_aliases: Dict[str, List[str]] = {}
    master_norms: Dict[str, Set[str]] = {}
    exact_map: Dict[str, Set[str]] = {}

    for master in artist_by_id.values():
        master_aliases[master] = [master]
        norm = _letters_only(master)
        master_norms[master] = {norm} if norm else set()

    for artist_id, term_text in term_rows:
        master = artist_by_id.get(int(artist_id), "")
        term = compact_ws(term_text)
        if not master or not term:
            continue
        aliases = master_aliases.setdefault(master, [master])
        if term.casefold() not in {item.casefold() for item in aliases}:
            aliases.append(term)
        exact_map.setdefault(term.casefold(), set()).add(master)
        norm = _letters_only(term)
        if norm:
            master_norms.setdefault(master, set()).add(norm)

    matcher.exact_map = exact_map
    matcher.master_aliases = master_aliases
    matcher.master_norms = master_norms
    return matcher


def _cache_key(variants: List[str]) -> str:
    return "|".join(value.casefold() for value in variants)


def _query_matches_cached_aliases(variants: List[str], matcher: ArtistMatcher) -> List[str]:
    variant_folded = {value.casefold() for value in variants}
    for master in list(matcher.recent_masters):
        aliases = matcher.master_aliases.get(master, [master])
        alias_folded = {alias.casefold() for alias in aliases}
        if variant_folded & alias_folded:
            return [master]
    return []


def _update_recent_master(matcher: ArtistMatcher, master: str) -> None:
    if master in matcher.recent_masters:
        matcher.recent_masters.remove(master)
    matcher.recent_masters.appendleft(master)


def lookup_artist_masters(text: str, matcher: Optional[ArtistMatcher]) -> List[str]:
    if matcher is None:
        return []
    variants = artist_search_variants(text)
    if not variants:
        return []

    cache_key = _cache_key(variants)
    cached = matcher.query_cache.get(cache_key)
    if cached is not None:
        _status, masters = cached
        if len(masters) == 1:
            _update_recent_master(matcher, masters[0])
        return list(masters)

    cached_recent = _query_matches_cached_aliases(variants, matcher)
    if cached_recent:
        matcher.query_cache[cache_key] = ("matched", tuple(cached_recent))
        _update_recent_master(matcher, cached_recent[0])
        return cached_recent

    found: Set[str] = set()
    for variant in variants:
        found.update(matcher.exact_map.get(variant.casefold(), set()))

    masters = tuple(sorted(found, key=lambda item: item.casefold()))
    status = "matched" if len(masters) == 1 else ("collision" if len(masters) > 1 else "no_match")
    matcher.query_cache[cache_key] = (status, masters)
    if len(masters) == 1:
        _update_recent_master(matcher, masters[0])
    return list(masters)


def lookup_artist_master_with_status(text: str, matcher: Optional[ArtistMatcher]) -> Tuple[str, List[str]]:
    if matcher is None:
        return "no_match", []
    variants = artist_search_variants(text)
    if not variants:
        return "no_match", []
    cache_key = _cache_key(variants)
    cached = matcher.query_cache.get(cache_key)
    if cached is not None:
        status, masters = cached
        if status == "matched" and masters:
            _update_recent_master(matcher, masters[0])
        return status, list(masters)

    masters = lookup_artist_masters(text, matcher)
    if not masters:
        return "no_match", []
    if len(masters) == 1:
        return "matched", masters
    return "collision", masters


def aliases_for_artist(artist: str, matcher: ArtistMatcher) -> List[str]:
    status, masters = lookup_artist_master_with_status(artist, matcher)
    if status == "matched" and masters:
        return list(matcher.master_aliases.get(masters[0], [masters[0]]))
    if artist in matcher.master_aliases:
        return list(matcher.master_aliases[artist])
    return []


def match_line_to_artists(text: str, matcher: ArtistMatcher) -> List[Tuple[str, str]]:
    cleaned = compact_ws(text)
    if not cleaned:
        return []
    status, masters = lookup_artist_master_with_status(cleaned, matcher)
    if status in {"matched", "collision"}:
        return [(master, cleaned) for master in masters]
    tokens = re.findall(r"[A-Za-z][A-Za-z'&.+-]*", cleaned)
    results: List[Tuple[str, str]] = []
    seen = set()
    for width in range(len(tokens), 0, -1):
        for start in range(0, len(tokens) - width + 1):
            phrase = " ".join(tokens[start:start + width]).strip()
            status, masters = lookup_artist_master_with_status(phrase, matcher)
            for master in masters:
                key = (master.casefold(), phrase.casefold())
                if key not in seen:
                    seen.add(key)
                    results.append((master, phrase))
        if results:
            break
    return results


def artist_norms_for_master(master_name: str, matcher: Optional[ArtistMatcher]) -> Set[str]:
    if matcher is None:
        return set()
    master = compact_ws(master_name)
    return set(matcher.master_norms.get(master, set()))
