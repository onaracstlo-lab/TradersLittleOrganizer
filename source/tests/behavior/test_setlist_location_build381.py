import pytest

pytestmark = pytest.mark.behavior
from pathlib import Path

import tlo_setlist_metadata_lookup as M


def _minimal_support(tmp_path: Path) -> M._SupportData:
    (tmp_path / "venues.txt").write_text("The Catalyst\n", encoding="utf-8")
    return M._SupportData(str(tmp_path))


def test_build381_artist_name_with_state_word_is_not_a_location(tmp_path):
    support = _minimal_support(tmp_path)
    city, region, country, *_ = M._parse_location_from_text("The Georgia Satellites", support)
    assert city == ""
    assert region == ""
    assert country == ""


def test_build381_mixed_case_comma_state_code_is_location_without_city_database(tmp_path):
    support = _minimal_support(tmp_path)
    city, region, country, raw, pattern, confidence = M._parse_location_from_text("Santa Cruz,Ca", support)
    assert (city, region, country) == ("Santa Cruz", "CA", "USA")
    assert raw == "Santa Cruz,Ca"
    assert pattern == "LOCATION_COMMA_STATE_CODE"
    assert confidence >= 90


def test_build381_georgia_satellites_setlist_extracts_catalyst_santa_cruz_ca(tmp_path):
    _minimal_support(tmp_path)
    setlist = tmp_path / "setlist.txt"
    setlist.write_text(
        "The Georgia Satellites\n"
        "The Catalyst\n"
        "Santa Cruz,Ca\n"
        "January 17, 1987\n\n"
        "source: nakamichi cm300 > sony tcd5m\n"
        "transfer from master cassette\n"
        "last song missing\n"
        "taper : markp\n\n"
        "01 Intro\n"
        "02 I Washed My Hands In Muddy Water\n"
        "03 Myth Of Love\n",
        encoding="utf-8",
    )
    result = M.extract_setlist_venue_location(str(setlist), str(tmp_path))
    assert result.venue == "The Catalyst"
    assert result.city == "Santa Cruz"
    assert result.region == "CA"
    assert result.country == "USA"
    assert result.location == "Santa Cruz CA"
    assert result.location != "The GA"


def test_build381_ambiguous_mixed_case_state_word_remains_rejected(tmp_path):
    support = _minimal_support(tmp_path)
    assert M._parse_location_from_text("You, Me", support)[:3] == ("", "", "")
