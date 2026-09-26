"""Build 493 regressions for guarded lowercase region abbreviations in paths."""

import pytest

pytestmark = pytest.mark.behavior

import tlo_phase23_v2 as P
from tlo_models import ShowMetadata


def _record() -> ShowMetadata:
    return ShowMetadata(
        group_number=1,
        main_dir_name="example",
        main_dir_path="/music/example",
        setlist_file="",
        music_file_count=1,
    )


def test_build493_default_freeform_parser_keeps_build492_uppercase_guards():
    # The relaxed behavior is path-context-only; generic/free-form callers keep
    # Build 492's protection against ordinary-word abbreviations.
    assert P._parse_string2("massey hall toronto on") == ("", "", "", "", "")
    assert P._parse_string2("crystal ballroom portland or") == ("", "", "", "", "")


@pytest.mark.parametrize(
    "value, expected",
    [
        ("massey hall toronto on", ("massey hall", "toronto", "ON", "Canada", "")),
        ("commodore ballroom vancouver bc", ("commodore ballroom", "vancouver", "BC", "Canada", "")),
        ("crystal ballroom portland or", ("crystal ballroom", "portland", "OR", "", "")),
        ("state theatre portland me", ("state theatre", "portland", "ME", "", "")),
        ("toronto, on", ("", "toronto", "ON", "Canada", "")),
        ("massey hall toronto on sbd", ("massey hall", "toronto", "ON", "Canada", "sbd")),
    ],
)
def test_build493_lowercase_path_style_can_relax_region_case(value, expected):
    assert P._parse_string2(value, allow_lowercase_region_codes=True) == expected


@pytest.mark.parametrize(
    "value",
    [
        "toronto on",
        "portland or",
        "live in",
        "made in",
        "tell me",
        "say hi",
        "all ok",
    ],
)
def test_build493_word_like_lowercase_codes_still_need_strong_location_structure(value):
    assert P._parse_string2(value, allow_lowercase_region_codes=True) == ("", "", "", "", "")


def test_build493_relaxation_requires_consistent_lowercase_not_mixed_case():
    for value in (
        "Massey Hall Toronto on",
        "massey hall Toronto on",
        "massey hall toronto On",
        "Crystal Ballroom Portland or",
    ):
        assert P._parse_string2(value, allow_lowercase_region_codes=True) == ("", "", "", "", "")


def test_build493_normal_path_string2_application_uses_lowercase_style_signal():
    record = _record()
    evidence = {}
    P._apply_string2_to_record(
        record,
        {
            "string2": "massey hall toronto on",
            "part": "todd snider 2005-04-16 massey hall toronto on",
        },
        evidence,
    )
    assert (record.venue, record.city, record.region, record.country) == (
        "massey hall",
        "toronto",
        "ON",
        "Canada",
    )

    mixed = _record()
    P._apply_string2_to_record(
        mixed,
        {
            "string2": "Massey Hall Toronto on",
            "part": "Todd Snider 2005-04-16 Massey Hall Toronto on",
        },
        {},
    )
    assert (mixed.venue, mixed.city, mixed.region, mixed.country) == ("", "", "", "")


def test_build493_requirements_and_manual_document_lowercase_path_guard():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = root / "TLO_Inventory_Requirements_Working_v493.docx"
    manual = root / "TLO_Inventory_User_Manual_v493.rtf"
    assert req.is_file()
    assert manual.is_file()

    req_text = "\n".join(p.text for p in Document(req).paragraphs)
    manual_text = manual.read_text(encoding="utf-8", errors="replace")
    assert "Current document version: v493 (v1.7 Build 493)." in req_text
    assert "Build 493 - Guarded lowercase region abbreviations in lowercase paths" in req_text
    assert "consistently lowercase" in req_text
    assert "toronto on, portland or, live in, made in" in req_text
    assert "Version v1.7 Build 493" in manual_text
    assert "Build 493: Lowercase state/province abbreviations may be accepted cautiously" in manual_text
