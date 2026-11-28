"""Conservative preflight for Rename Compliantly operations.

A verified name is better than a cosmetically normalized but lossy name.
This guard never invents missing identity details or changes duplicate matching.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import re
import unicodedata
from datetime import date as calendar_date

from tlo_constants import MONTHS
from tlo_text_utils import compact_ws, split_trailing_parenthetical_groups

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_NUMBER = re.compile(r"(?<!\d)\d+(?!\d)")
_FULL_DATE = re.compile(r"(?<!\d)(?:18|19|20)\d{2}-\d{2}-\d{2}(?!\d)")
_YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
_UNCERTAIN_DATE = re.compile(r"\b(?:xxxx|xx)(?:[-/.](?:xx|\d{2})){0,2}\b", re.I)
# Date words are allowed to disappear when a date is normalized to YYYY-MM-DD.
_GENERIC = frozenset("bad folder name original ready music directory unknown incoming temp staged raw source".split())
_DATE_MONTH_WORDS = frozenset(MONTHS)
# Only month words that truly participate in a recognised spelled-out date may
# disappear. In particular, never remove May from Brian May or New from New Riders.
_MONTH_WORD = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))
_SPELLED_DATE = re.compile(
    rf"(?<!\w)(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?P<month_after>{_MONTH_WORD})\s*,?\s*\d{{4}}|"
    rf"(?P<month_before>{_MONTH_WORD})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}})(?!\w)", re.I)


def _fold_text(value: str) -> str:
    # This applies the *same* accent folding to both names without dropping
    # Cyrillic and other non-Latin identifiers that lack ASCII equivalents.
    value = value.translate(str.maketrans({
        "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
        "ß": "ss", "ð": "d", "Ð": "D", "ł": "l", "Ł": "L",
    }))
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _date_months(source: str) -> set[str]:
    found: set[str] = set()
    for match in _SPELLED_DATE.finditer(source):
        word = match.group("month_after") or match.group("month_before")
        found.add(_fold_text(word).casefold())
    return found



def _words(value: str) -> set[str]:
    normalized = _fold_text(value)
    # Regional abbreviations W.V. / N.Y. retain identity as WV / NY.
    normalized = re.sub(r"\b(?:[A-Za-z]\.){2,}", lambda match: match.group().replace(".", ""), normalized)
    return {word.casefold() for word in _WORD.findall(normalized)}


def _normalize_verifiable_source_date(source: str, target: str) -> str:
    """Replace only a source date proven equivalent to the exact proposed ISO date.

    This allows explicit language/ordinal or two-digit-year date normalization,
    not arbitrary deletion of numeric trading IDs or non-date descriptors.
    """
    target_hit = _FULL_DATE.search(target)
    if not target_hit:
        return source
    iso = target_hit.group()
    year, month, day = (int(part) for part in iso.split("-"))

    # A complete source date is never rewritten by this helper: the existing
    # independent guard checks that it cannot change.
    if _FULL_DATE.search(source):
        return source

    # YY-MM-DD encodes an explicit calendar date only when the entire date
    # matches the normalized candidate, including its century.
    short_pattern = re.compile(r"(?<!\d)(\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
    for match in short_pattern.finditer(source):
        if (int(match.group(1)) == year % 100 and
                int(match.group(2)) == month and int(match.group(3)) == day):
            return source[:match.start()] + iso + source[match.end():]

    month_pattern = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))
    # The source's accented month spelling is matched directly; only a date
    # with the same year/month/day as target may be normalized.
    spelled = re.compile(
        rf"(?<!\w)(?P<day>\d{{1,2}})(?:st|nd|rd|th|er)?\.?\s+"
        rf"(?P<month>{month_pattern})\s*,?\s*(?P<year>\d{{4}})(?!\w)", re.I,
    )
    for match in spelled.finditer(source):
        if (int(match.group('day')) == day and
                int(match.group('year')) == year and
                MONTHS.get(match.group('month').casefold()) == month):
            return source[:match.start()] + iso + source[match.end():]
    return source


# Explicit part/collision markers are governed by grouping and duplicate validation,
# not the ordinary recording-qualifier preservation rule.
_STRUCTURAL_SUFFIX = re.compile(
    r"\((?:(?:copy|alt|disc|cd|set)\s*\d+|one|two|three|four|five)\)", re.I
)


def _ordinary_suffixes_preserved(source: str, target: str) -> bool:
    """Keep every complete ordinary source group, in its original order.

    A set of words is insufficient: (late) can be lost even when "late"
    appears in the venue, and (AUD (Remaster)) is not two separate groups.
    Accept normal accent/quote/case folding, but do not weaken the existing
    identifier or copy/alt guards. Extra metadata-derived groups are allowed.
    """
    def key(group: str) -> str:
        return compact_ws(_fold_text(group)).casefold()

    required = (key(group) for group in split_trailing_parenthetical_groups(source)[1]
                if not _STRUCTURAL_SUFFIX.fullmatch(group))
    proposed = iter(key(group) for group in split_trailing_parenthetical_groups(target)[1])
    return all(any(item == needed for item in proposed) for needed in required)


# A narrowly defined trading-directory convention, not a generic extension
# remover. An alphanumeric alias must match an exact Artist DB entry.
# The compact dotted source/ordinary-format convention (e.g. aud.flac16)
# describes trading media, not performance identity. Do not strip arbitrary
# identifiers, recording notes, higher-resolution designators or parentheticals.
_PLAIN_MEDIA = r"(?:flac|shnf?|wav|mp3)"
_SOURCE_MEDIA = r"(?:aud|sbd|sdb|matrix|fm|soundboard|audience)"
_ORDINARY_MEDIA = r"(?:flac16|flac|shnf?|wav|mp3)"
_SHORTHAND_LEAF = re.compile(
    r"(?P<prefix>[A-Za-z][A-Za-z0-9]{0,3}?)"
    r"(?P<date>(?:[0-9]{4}|[0-9]{2})-[0-9]{2}-[0-9]{2})"
    rf"(?:\.(?P<tail>(?:{_SOURCE_MEDIA}\.)?{_ORDINARY_MEDIA}))?", re.I
)


def shorthand_artist_prefix(source: str) -> str:
    core, _ = split_trailing_parenthetical_groups(source)
    match = _SHORTHAND_LEAF.fullmatch(core.strip())
    return match.group("prefix") if match else ""


def _normalize_verified_trading_leaf(source: str, target: str, artist: str,
                                     date: str, verified_prefix: str) -> str:
    core, suffixes = split_trailing_parenthetical_groups(source)
    match = _SHORTHAND_LEAF.fullmatch(core.strip())
    if not match or not artist.strip() or not _FULL_DATE.fullmatch(date):
        return source
    try:
        selected_date = calendar_date.fromisoformat(date)
    except ValueError:
        return source
    if date not in _FULL_DATE.findall(target):
        return source
    if match.group("date") not in (date, selected_date.strftime("%y-%m-%d")):
        return source
    prefix = match.group("prefix")
    tail = match.group("tail") or ""
    if prefix.casefold() == verified_prefix.casefold():
        # The extraction pipeline established a unique Artist DB alias for
        # the selected artist; the resolved date matches the original leaf.
        # The entire tail has already matched the narrow technical grammar.
        artist_text = artist
    elif prefix.casefold() in _words(artist) and (
            not tail or re.fullmatch(_PLAIN_MEDIA, tail, re.I)):
        # Preserve the old literal-word exception for plain formats only.
        # An alphanumeric alias or richer technical tail requires DB proof.
        artist_text = prefix
    else:
        return source
    return compact_ws(" ".join([artist_text, date, *suffixes]))


def spaced_album_separator(show_name: str, artist: str, date: str) -> str:
    """Normalize only the separator following the resolved artist on undated shows."""
    if not artist or date:
        return show_name
    match = re.fullmatch(re.escape(artist.strip()) + r"\s*[-–—]\s*(.+)", show_name, re.IGNORECASE)
    return f"{artist.strip()} - {match.group(1)}" if match else show_name


def safe_rename_target(source_leaf: str, candidate_leaf: str, *, artist: str = "", date: str = "", verified_prefix: str = "") -> tuple[str, str]:
    """Return (accepted target, reason); empty target means do not rename.

    Except for exact case and lossless undated Artist/Album separator repairs,
    requires a positively identified artist and a date. The normalized candidate
    must retain all source identity words other than verified shorthand and
    date spelling; known years and meaningful recording qualifiers remain protected. A punctuation-only *removal* is not a reason
    to rename a previously compliant folder again.
    """
    source = str(source_leaf or "").strip()
    target = str(candidate_leaf or "").strip()
    if not source or not target:
        return "", "show identity or date is uncertain"
    # Exact identity with capitalization-only correction never discards data.
    if source.casefold() == target.casefold():
        return target, ""
    # Undated Artist - Album folders may undergo a lossless separator repair.
    # Match the resolved artist literally; leave every interior album dash,
    # recording qualifier, year and other identifying character untouched.
    if not date.strip() and artist.strip():
        prefix = re.escape(artist.strip())
        source_match = re.fullmatch(prefix + r"\s*[-–—]\s*(.+)", source, re.IGNORECASE)
        target_match = re.fullmatch(prefix + r" - (.+)", target, re.IGNORECASE)
        if source_match and target_match and source_match.group(1).casefold() == target_match.group(1).casefold():
            return target, ""
    # A complete, specifically resolved Show can be enough when old callers
    # supply a record without separate artist/date fields. A missing or partial
    # proposed date is not enough to authorize a destructive rename.
    has_complete_date = re.search(r"(?<!\d)(?:18|19|20)\d{2}-\d{2}-\d{2}(?!\d)", target)
    if (not date.strip() and not has_complete_date) or (date.strip() and _UNCERTAIN_DATE.search(date)):
        return "", "show identity or date is uncertain"
    if artist.strip() and not _words(artist).issubset(_words(target)):
        return "", "resolved artist missing from proposed name"
    # Recognize a *proved equivalent* human-readable source date.  The rest
    # of the source identity remains protected from deletion.
    comparable_source = _normalize_verified_trading_leaf(source, target, artist, date, verified_prefix)
    comparable_source = _normalize_verifiable_source_date(comparable_source, target)
    # A year cannot disappear, and yyyy-xx-xx never replaces a known full date.
    source_years = set(_YEAR.findall(comparable_source))
    target_years = set(_YEAR.findall(target))
    if not source_years.issubset(target_years):
        return "", "known year would be lost"
    if _UNCERTAIN_DATE.search(target) and not _UNCERTAIN_DATE.search(source):
        return "", "proposed date is less specific"
    source_full_dates = set(_FULL_DATE.findall(comparable_source))
    target_full_dates = set(_FULL_DATE.findall(target))
    if source_full_dates and not source_full_dates.issubset(target_full_dates):
        return "", "known full date would change"
    # Preserve source identifiers (etree shnid, 24-96, recording numbers).
    # Permit 8 May -> 08 in a normalized date, but never simply discard a
    # numeric run or change a known yyyy-mm-dd date.
    from collections import Counter
    source_numbers = Counter(int(value) for value in _NUMBER.findall(comparable_source))
    target_numbers = Counter(int(value) for value in _NUMBER.findall(target))
    if source_numbers - target_numbers:
        return "", "numeric show or source identifier would be lost"
    missing = (_words(comparable_source) - _date_months(comparable_source) - _GENERIC) - _words(target)
    if missing:
        return "", "source identifying text would be lost: " + ", ".join(sorted(missing))
    if not _ordinary_suffixes_preserved(source, target):
        return "", "trailing recording parenthetical would be lost or altered"
    # Case changes remain permitted. Prevent losing commas/other punctuation
    # alone, which otherwise causes run-two rename churn.
    if source != target and re.sub(r"[,;]", "", source) == re.sub(r"[,;]", "", target):
        return "", "punctuation-only reduction"
    return target, ""
