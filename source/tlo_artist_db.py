__version__ = "v440"
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple
from collections import OrderedDict, deque

from tlo_db_validation import validate_artist_sqlite
from tlo_text_utils import compact_ws

THE_PREFIX_RE = re.compile(r"^(?:the|a)\s+", re.IGNORECASE)
THE_SUFFIX_RE = re.compile(r",\s*(?:the|a)$", re.IGNORECASE)
TERMINAL_ARTIST_SUFFIX_RE = re.compile(
    r"(?:"
    r"(?:\s+|-\s*)all(?:\s*-\s*|\s+)stars?\s+band"
    r"|\s+group"
    r"|\s+band"
    r"|(?:\s+|-\s*)all(?:\s*-\s*|\s*)stars?"
    r")$",
    re.IGNORECASE,
)


def _strip_article_forms(text: str) -> str:
    value = compact_ws(text)
    if not value:
        return ""
    value = THE_PREFIX_RE.sub("", value)
    value = THE_SUFFIX_RE.sub("", value)
    return compact_ws(value)


def _letters_only(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalpha())


def _split_terminal_artist_suffix(text: str) -> Tuple[str, str]:
    """Return ``(base_artist, stripped_suffix)`` for one supported terminal suffix.

    The suffix is retained so a successful *base* Artist DB lookup can identify
    the performance without discarding the performance-specific wording.  A
    leading dash is preserved (for example ``Example-AllStar`` ->
    ``("Example", "-AllStar")``); whitespace-separated forms are returned
    without their leading whitespace.
    """
    cleaned = compact_ws(text)
    if not cleaned:
        return "", ""
    match = TERMINAL_ARTIST_SUFFIX_RE.search(cleaned)
    if not match:
        return "", ""
    base = compact_ws(cleaned[:match.start()])
    raw_suffix = cleaned[match.start():]
    if not base or base.casefold() == cleaned.casefold():
        return "", ""
    suffix = raw_suffix.strip()
    return base, suffix


def _strip_terminal_artist_suffix(text: str) -> str:
    """Return *text* without one recognized terminal artist-group suffix."""
    base, _suffix = _split_terminal_artist_suffix(text)
    return base


def _restore_terminal_artist_suffix(master: str, suffix: str) -> str:
    """Reapply a fallback-only suffix to the DB-resolved base artist.

    If the resolved DB master already ends in a supported grouping suffix, do
    not append another one.  This preserves established masters such as
    ``The Marshall Tucker Band`` instead of producing ``... Band Band``.
    """
    base_master = compact_ws(master)
    raw_suffix = compact_ws(suffix) if not str(suffix or "").lstrip().startswith("-") else str(suffix or "").strip()
    if not base_master or not raw_suffix:
        return base_master
    _existing_base, existing_suffix = _split_terminal_artist_suffix(base_master)
    if existing_suffix:
        return base_master
    if raw_suffix.startswith("-"):
        return compact_ws(base_master + raw_suffix)
    return compact_ws(f"{base_master} {raw_suffix}")


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
    query_cache: "OrderedDict[str, Tuple[str, Tuple[str, ...]]]" = field(default_factory=OrderedDict)
    query_cache_max_entries: int = 4096
    recent_masters: Deque[str] = field(default_factory=lambda: deque(maxlen=5))
    # Build 418: maps original/restored suffix-fallback names to the DB base
    # used to identify them.  These names are performance artists, not full
    # Artist DB entries, and are persisted for later database review.
    terminal_suffix_fallback_info: Dict[str, Dict[str, str]] = field(default_factory=dict)


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


def _cache_query_result(matcher: ArtistMatcher, cache_key: str, status: str, masters: Tuple[str, ...]) -> None:
    matcher.query_cache[cache_key] = (status, masters)
    try:
        matcher.query_cache.move_to_end(cache_key)
    except AttributeError:
        pass
    max_entries = max(1, int(getattr(matcher, "query_cache_max_entries", 4096) or 4096))
    while len(matcher.query_cache) > max_entries:
        try:
            matcher.query_cache.popitem(last=False)
        except TypeError:
            # Plain dict fallback for old pickled/test objects; remove the oldest insertion key.
            first_key = next(iter(matcher.query_cache), None)
            if first_key is None:
                break
            matcher.query_cache.pop(first_key, None)


def _get_query_result(matcher: ArtistMatcher, cache_key: str) -> Tuple[str, Tuple[str, ...]] | None:
    cached = matcher.query_cache.get(cache_key)
    if cached is not None:
        try:
            matcher.query_cache.move_to_end(cache_key)
        except AttributeError:
            pass
    return cached

def lookup_artist_masters(
    text: str, matcher: Optional[ArtistMatcher], *, _allow_terminal_artist_suffix_fallback: bool = True
) -> List[str]:
    if matcher is None:
        return []
    variants = artist_search_variants(text)
    if not variants:
        return []

    cache_key = _cache_key(variants)
    cached = _get_query_result(matcher, cache_key)
    if cached is not None:
        _status, masters = cached
        if len(masters) == 1:
            _update_recent_master(matcher, masters[0])
        return list(masters)

    cached_recent = _query_matches_cached_aliases(variants, matcher)
    if cached_recent:
        _cache_query_result(matcher, cache_key, "matched", tuple(cached_recent))
        _update_recent_master(matcher, cached_recent[0])
        return cached_recent

    found: Set[str] = set()
    for variant in variants:
        found.update(matcher.exact_map.get(variant.casefold(), set()))

    # Secondary fallback for potential artist names ending in ``Band``,
    # ``Group``, a supported ``All Star(s)`` spelling, or a terminal
    # ``All Star Band``/``All-Star Band`` form.  Never mix the stripped form into the
    # primary variant set: if the full artist name exists in the DB, that
    # exact/full result must win.  Only a unique stripped-form result is
    # accepted; ambiguous stripped matches leave the original candidate
    # unresolved.
    if not found and _allow_terminal_artist_suffix_fallback:
        stripped_artist, stripped_suffix = _split_terminal_artist_suffix(text)
        if stripped_artist and stripped_suffix:
            stripped_masters = lookup_artist_masters(
                stripped_artist, matcher, _allow_terminal_artist_suffix_fallback=False
            )
            if len(stripped_masters) == 1:
                db_master = stripped_masters[0]
                performance_artist = _restore_terminal_artist_suffix(db_master, stripped_suffix)
                if performance_artist:
                    found.add(performance_artist)
                    info = {
                        "candidate": compact_ws(text),
                        "base_query": stripped_artist,
                        "db_master": db_master,
                        "suffix": stripped_suffix,
                        "performance_artist": performance_artist,
                    }
                    for key_text in (text, performance_artist):
                        key = compact_ws(key_text).casefold()
                        if key:
                            matcher.terminal_suffix_fallback_info[key] = dict(info)
                    # Returned fallback values intentionally represent the
                    # performance artist rather than a literal DB master.
                    # Seed alias/norm data so repeated queries and downstream
                    # alias helpers continue to work normally.
                    aliases = [performance_artist]
                    for alias in matcher.master_aliases.get(db_master, [db_master]):
                        if alias.casefold() not in {item.casefold() for item in aliases}:
                            aliases.append(alias)
                    matcher.master_aliases.setdefault(performance_artist, aliases)
                    matcher.master_norms.setdefault(
                        performance_artist, set(matcher.master_norms.get(db_master, set()))
                    )

    masters = tuple(sorted(found, key=lambda item: item.casefold()))
    status = "matched" if len(masters) == 1 else ("collision" if len(masters) > 1 else "no_match")
    _cache_query_result(matcher, cache_key, status, masters)
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
    cached = _get_query_result(matcher, cache_key)
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


def terminal_suffix_fallback_info_for_artist(
    artist: str, matcher: Optional[ArtistMatcher]
) -> Optional[Dict[str, str]]:
    """Return Build 418 suffix-fallback metadata for *artist*, if applicable."""
    if matcher is None:
        return None
    key = compact_ws(artist).casefold()
    if not key:
        return None
    info = matcher.terminal_suffix_fallback_info.get(key)
    return dict(info) if info else None


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
