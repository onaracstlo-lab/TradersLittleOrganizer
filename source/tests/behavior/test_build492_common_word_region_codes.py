"""Build 492 regressions for common-word state/province abbreviations."""

import pytest

pytestmark = pytest.mark.behavior

import tlo_phase23_v2 as P
import tlo_setlist_metadata_lookup as S
from tlo_constants import LOWERCASE_COMMON_STATE_CODES


@pytest.mark.parametrize("code", sorted(LOWERCASE_COMMON_STATE_CODES))
def test_build492_path_parser_rejects_lower_or_mixed_case_common_us_state_codes(code):
    word = code.lower()
    assert P._parse_string2(f"Example {word}") == ("", "", "", "", "")
    assert P._parse_string2(f"Example {word.title()}") == ("", "", "", "", "")


def test_build492_on_ontario_has_same_common_word_case_guard_as_in_indiana():
    assert P._parse_string2("Toronto on") == ("", "", "", "", "")
    assert P._parse_string2("Toronto On") == ("", "", "", "", "")
    assert P._parse_string2("Toronto ON") == ("", "Toronto", "ON", "Canada", "")

    assert P._parse_string2("Indianapolis in") == ("", "", "", "", "")
    assert P._parse_string2("Indianapolis In") == ("", "", "", "", "")
    assert P._parse_string2("Indianapolis IN") == ("", "Indianapolis", "IN", "", "")


def test_build492_common_word_examples_do_not_become_path_locations():
    for value in ("Live in", "Made in", "Portland or", "Tell me", "Say hi", "All ok", "Oh oh"):
        assert P._parse_string2(value) == ("", "", "", "", "")


def test_build492_non_common_us_code_keeps_existing_mixed_case_compatibility():
    # Build 381 compatibility: non-word U.S. postal codes may still arrive in
    # title case from old setlist/path names (e.g. Ca for California).
    assert P._parse_string2("The Catalyst Santa Cruz Ca") == ("The Catalyst", "Santa Cruz", "CA", "", "")


def test_build492_setlist_and_path_common_word_guards_are_consistent(tmp_path):
    support = S._SupportData(str(tmp_path))
    for city, lower_code, upper_code in (
        ("Indianapolis", "in", "IN"),
        ("Portland", "or", "OR"),
        ("Toronto", "on", "ON"),
    ):
        assert S._parse_location_from_text(f"{city}, {lower_code}", support)[:3] == ("", "", "")
        parsed = S._parse_location_from_text(f"{city}, {upper_code}", support)[:3]
        assert parsed[0] == city
        assert parsed[1] == upper_code


def test_build492_requirements_and_manual_document_common_word_guards():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = root / "TLO_Inventory_Requirements_Working_v493.docx"
    manual = root / "TLO_Inventory_User_Manual_v493.rtf"
    assert req.is_file()
    assert manual.is_file()

    req_text = "\n".join(p.text for p in Document(req).paragraphs)
    manual_text = manual.read_text(encoding="utf-8", errors="replace")
    assert "Current document version: v493 (v1.7 Build 493)" in req_text
    assert "CO, DE, HI, ID, IN, LA, MA, ME, MO, OH, OK, OR, and PA" in req_text
    assert "ON/Ontario" in req_text
    assert "Version v1.7 Build 493" in manual_text
    assert "IN, HI, OR, MA, OK, OH, ME, ID, PA, LA, MO, CO, and DE" in manual_text
    assert "ON/Ontario" in manual_text
