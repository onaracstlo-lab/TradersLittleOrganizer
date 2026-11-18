"""Conservative preflight for Rename Compliantly operations.

A verified name is better than a cosmetically normalized but lossy name.
This guard never invents missing identity details or changes duplicate matching.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import re
import unicodedata

_WORD = re.compile(r"[A-Za-z\u00c0-\u024f]+")
_YEAR = re.compile(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)")
_UNCERTAIN_DATE = re.compile(r"\b(?:xxxx|xx)(?:[-/.](?:xx|\d{2})){0,2}\b", re.I)
# Date words are allowed to disappear when a date is normalized to YYYY-MM-DD.
_GENERIC = frozenset("bad folder name original ready show music directory unknown incoming new temp staged raw source".split())
_MONTHS = frozenset("jan january feb february mar march apr april may jun june jul july aug august sep sept september oct october nov november dec december janvier fevrier février mars avril mai juin juillet aout août septembre octobre novembre decembre décembre januar februar maerz märz april juni juli august september oktober dezember".split())


def _words(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value)
    # Regional abbreviations W.V. / N.Y. retain identity as WV / NY.
    normalized = re.sub(r"\b(?:[A-Za-z]\.){2,}", lambda match: match.group().replace(".", ""), normalized)
    return {word.casefold() for word in _WORD.findall(normalized)}


def safe_rename_target(source_leaf: str, candidate_leaf: str, *, artist: str = "", date: str = "") -> tuple[str, str]:
    """Return (accepted target, reason); empty target means do not rename.

    Requires a positively identified artist and a date. The normalized candidate
    must retain all source identity words other than date spelling; no year or
    source qualifier can be lost. A punctuation-only *removal* is not a reason
    to rename a previously compliant folder again.
    """
    source = str(source_leaf or "").strip()
    target = str(candidate_leaf or "").strip()
    if not source or not target:
        return "", "show identity or date is uncertain"
    # Exact identity with capitalization-only correction never discards data.
    if source.casefold() == target.casefold():
        return target, ""
    # A complete, specifically resolved Show can be enough when old callers
    # supply a record without separate artist/date fields. A missing or partial
    # proposed date is not enough to authorize a destructive rename.
    has_complete_date = re.search(r"(?<!\d)(?:18|19|20)\d{2}-\d{2}-\d{2}(?!\d)", target)
    if (not date.strip() and not has_complete_date) or (date.strip() and _UNCERTAIN_DATE.search(date)):
        return "", "show identity or date is uncertain"
    if artist.strip() and not _words(artist).issubset(_words(target)):
        return "", "resolved artist missing from proposed name"
    # A year cannot disappear, and yyyy-xx-xx never replaces a known full date.
    source_years = set(_YEAR.findall(source))
    target_years = set(_YEAR.findall(target))
    if not source_years.issubset(target_years):
        return "", "known year would be lost"
    if _UNCERTAIN_DATE.search(target) and not _UNCERTAIN_DATE.search(source):
        return "", "proposed date is less specific"
    missing = (_words(source) - _MONTHS - _GENERIC) - _words(target)
    if missing:
        return "", "source identifying text would be lost: " + ", ".join(sorted(missing))
    # Case changes remain permitted. Prevent losing commas/other punctuation
    # alone, which otherwise causes run-two rename churn.
    if source != target and re.sub(r"[,;]", "", source) == re.sub(r"[,;]", "", target):
        return "", "punctuation-only reduction"
    return target, ""
