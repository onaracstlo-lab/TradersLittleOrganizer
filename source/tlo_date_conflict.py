"""Read-only ordered title comparison for conflicting performance dates."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import difflib
from tlo_text_utils import normalized_compare_value, standard_ascii_text


def title_sequence(tracks):
    """Exclude unknown/generated placeholders rather than count them as songs."""
    titles = []
    for row in tracks:
        title = normalized_compare_value(standard_ascii_text(str(row.get("title", ""))))
        if title and title not in {"unknown", "intro", "outro", "encore", "break", "banter", "crowd", "applause", "tuning"}:
            titles.append(title)
    return tuple(titles)


def sequence_fit(local, remote):
    """Return order-sensitive overlap and number of distinct matched songs.

    Use the longer sequence as denominator so a short shared fragment cannot
    masquerade as a complete concert; repeated songs cannot inflate the
    independent-title minimum.  Allow missing intros or minor track splits.
    """
    if not local or not remote:
        return 0.0, 0
    blocks = difflib.SequenceMatcher(None, local, remote, autojunk=False).get_matching_blocks()
    matched = [local[i] for block in blocks for i in range(block.a, block.a + block.size)]
    return len(matched) / max(len(local), len(remote)), len(set(matched))
