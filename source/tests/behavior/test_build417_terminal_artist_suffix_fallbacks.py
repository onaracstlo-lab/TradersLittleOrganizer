"""Build 417 regressions for terminal artist-group suffix fallback."""

__version__ = "v446"

import pytest

pytestmark = pytest.mark.behavior


def _matcher(mapping):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for term, masters in mapping.items():
        values = set(masters if isinstance(masters, (list, tuple, set)) else [masters])
        matcher.exact_map[term.casefold()] = values
        for master in values:
            matcher.master_aliases.setdefault(master, [master, term])
            matcher.master_norms.setdefault(master, {"".join(ch for ch in master.casefold() if ch.isalpha())})
    return matcher


@pytest.mark.parametrize(
    "candidate",
    [
        "Example Group",
        "Example All Star Band",
        "Example All-Star Band",
        "Example All Stars Band",
        "Example All-Stars Band",
        "Example all-star band",
    ],
)
def test_new_terminal_suffixes_retry_unique_remaining_artist(candidate):
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": "Example Master"})
    suffix = candidate[len("Example"):].strip()
    expected = f"Example Master {suffix}"
    assert lookup_artist_master_with_status(candidate, matcher) == ("matched", [expected])


@pytest.mark.parametrize(
    "candidate",
    ["Example Group", "Example All Star Band", "Example All-Star Band"],
)
def test_new_terminal_suffix_full_db_match_wins(candidate):
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({candidate: candidate, "Example": "Different Example Master"})
    assert lookup_artist_master_with_status(candidate, matcher) == ("matched", [candidate])


@pytest.mark.parametrize(
    "candidate",
    ["Group Example", "All Star Band Example", "All-Star Band Example"],
)
def test_new_terminal_suffixes_only_apply_at_end(candidate):
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": "Example Master"})
    assert lookup_artist_master_with_status(candidate, matcher) == ("no_match", [])


@pytest.mark.parametrize(
    "candidate",
    ["Example Group", "Example All Star Band", "Example All-Star Band"],
)
def test_new_terminal_suffix_ambiguous_remaining_lookup_is_not_promoted(candidate):
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": ["Example One", "Example Two"]})
    assert lookup_artist_master_with_status(candidate, matcher) == ("no_match", [])


def test_build417_requirements_and_manual_document_new_suffix_rule():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v446.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v446.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v446 (v1.6 Build 446)." in req_text
    assert "Band or Group" in req_text
    assert "All Star Band / All-Star Band" in req_text
    assert "Build 407, 417, 418: Terminal Band/Group/All-Star-family Artist DB fallback" in req_text
    assert "Version v1.6 Build 446" in manual
    assert "terminal Band, Group, All Star/All-Star/All Stars/All-Stars" in manual
    assert "corresponding ... Band form" in manual
