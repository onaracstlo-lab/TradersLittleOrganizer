"""Conservative display casing for *identified* venue/city/location metadata.

This does not participate in lookup, artist identification, or evidence scoring.
Only all-uppercase place labels are changed; mixed/lowercase source spelling is
preserved, including intentional trademarks and non-Latin writing systems.
"""

from __future__ import annotations

import re
import unicodedata

from tlo_constants import REGION_CODES
from tlo_version import VERSION as _TLO_CANONICAL_VERSION

__version__ = _TLO_CANONICAL_VERSION

# Well-established uppercase initials that should not become 'Mgm', 'Cbgb', etc.
# Keep this narrow: ordinary uppercase words such as ROME and ROXY must become
# Rome and Roxy, even when they happen to be only four letters long.
_ACRONYMS = frozenset({
    "ABC", "ACL", "BBC", "CBGB", "CBGBS", "CMT", "DC", "FM", "JFK", "KEXP",
    "LA", "MGM", "MIT", "MSG", "MTV", "NASA", "NBA", "NPR", "NYC", "NYU",
    "PBS", "RCA", "RFK", "SXSW", "TD", "TV", "UCLA", "UK", "UMASS", "US",
    "USA", "USC", "UBS", "VFW", "WFUV", "WFMU", "YMCA",
})
# Keep connector words lowercase except when they begin a proper name.
_CONNECTORS = frozenset({"and", "at", "da", "das", "de", "del", "der", "des", "di", "do", "dos", "du", "et", "in", "of", "on", "the", "van", "von", "y"})
_SPECIAL_WORDS = {
    "MCMENAMINS": "McMenamins",
    "MCDONALD": "McDonald",
    "MCDONALDS": "McDonalds",
}
# Match alphabetic runs with apostrophes, including accented Latin characters.
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)


def _all_uppercase(value: str) -> bool:
    letters = [letter for letter in value if letter.isalpha() and (letter.islower() or letter.isupper())]
    return bool(letters) and all(letter.isupper() for letter in letters)


def display_place_case(value: str, *, kind: str = "venue") -> str:
    """Titlecase an all-caps place label, without guessing at mixed-case text.

    ``kind`` is ``venue``, ``city``, ``region``, ``country`` or ``location``.
    A two-letter region code stays uppercase, as do known venue acronyms.
    Returns the original exact string if the label is not entirely uppercase.
    """
    if not value or not _all_uppercase(value):
        return value
    # Non-Latin scripts need language-aware casing; never guess them here.
    if any(c.isalpha() and (c.islower() or c.isupper()) and
           not unicodedata.name(c, "").startswith("LATIN") for c in value):
        return value
    if kind == "region" and re.fullmatch(r"[A-Z]{2}", value.strip()):
        return value
    if kind == "city" and value.strip() in {"LA", "NYC", "DC"}:
        return value
    index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        word = match.group()
        upper = word.upper()
        is_first = index == 0
        index += 1
        if upper == "LA" and kind == "city" and len(value.strip().split()) > 1:
            return "La"
        if upper in _SPECIAL_WORDS:
            return _SPECIAL_WORDS[upper]
        if upper in _ACRONYMS:
            return upper
        if kind == "location" and upper in REGION_CODES and len(upper) == 2 and upper not in {"IN", "ON", "OR"}:
            return upper
        # Preserve acronym punctuation without turning U.S. into U.s.
        if word in {"AT", "T"} and kind == "venue" and "AT&T" in value:
            return upper
        if not is_first and upper.lower() in _CONNECTORS:
            return upper.lower()
        # Python's .title() turns JOE'S into Joe'S. Apostrophe suffixes are
        # grammatical contractions, whereas O'BRIEN must capitalize Brien.
        if "'" in word or "’" in word:
            chunks = re.split(r"(['’])", word)
            first = _SPECIAL_WORDS.get(chunks[0].upper(), chunks[0].capitalize())
            for chunk_index in range(2, len(chunks), 2):
                component = chunks[chunk_index]
                if component.upper() in {"S", "T", "D", "RE", "VE", "LL"}:
                    first += chunks[chunk_index - 1] + component.lower()
                else:
                    first += chunks[chunk_index - 1] + component.capitalize()
            return first
        return word.title()

    return _WORD.sub(replace, value)


def replace_place_in_show_tail(show_name: str, artist: str, changes: tuple[tuple[str, str], ...]) -> str:
    """Change exact place tokens *after* the artist, not the artist's name.

    Preserve date/descriptor, qualifiers, and parenthetical text verbatim.
    Never reinterpret or rebuild the selected compliant show naming pattern.
    """
    if not show_name or not changes or not artist or not show_name.startswith(artist):
        return show_name
    prefix, tail = show_name[:len(artist)], show_name[len(artist):]
    for before, after in sorted(changes, key=lambda pair: len(pair[0]), reverse=True):
        if not before or before == after:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(before) + r"(?!\w)")
        tail = pattern.sub(lambda _: after, tail)
    return prefix + tail
