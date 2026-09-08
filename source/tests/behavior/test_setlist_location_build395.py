"""Build 395 setlist venue/location regressions migrated from the legacy suite."""
__version__ = "v446"

import pytest
import tlo_phase23_v2 as P
import tlo_setlist_metadata_lookup as M

pytestmark = pytest.mark.behavior


def _support_files(tmp_path):
    dbs = tmp_path / "TLO_DBs"
    dbs.mkdir()
    (dbs / "venues.txt").write_text("Van\nLone Star Cafe\n", encoding="utf-8")
    (dbs / "states_regions.csv").write_text("abbrev^name^country\nMB^Manitoba^Canada\n", encoding="utf-8")
    (dbs / "countries.csv").write_text("country^canonical\nCanada^Canada\n", encoding="utf-8")
    (dbs / "cities.csv").write_text("city^region^country\nWinnipeg^MB^Canada\n", encoding="utf-8")
    return dbs


def test_location_dash_venue_header_beats_short_venue_substring(tmp_path):
    dbs = _support_files(tmp_path)
    setlist = tmp_path / "SS19910921info.txt"
    setlist.write_text(
        "Townes Van Zandt, Guy Clark, Marc Jordan, Murray McLauchlan\n\n"
        "SWINGIN' ON A STAR\n"
        "Winnipeg, MB  --  CBC Winnipeg studios\n"
        "1991-09-21  --  51:27\n\n"
        "01. -intro-\n",
        encoding="utf-8",
    )
    result = M.extract_setlist_venue_location(str(setlist), str(dbs))
    assert result.venue == "CBC Winnipeg studios"
    assert result.city == "Winnipeg"
    assert result.region == "MB"
    assert result.country == "Canada"
    assert result.location == "Winnipeg MB"
    assert result.source.endswith("LOCATION_DASH_LOCATION_VENUE")
    assert result.venue != "Van"


def test_venue_dash_location_header_is_supported(tmp_path):
    support = M._SupportData(str(_support_files(tmp_path)))
    venue, city, region, country, _raw, pattern, confidence = M._split_dash_location_venue_header_line(
        "CBC Winnipeg studios -- Winnipeg, MB", support
    )
    assert (venue, city, region, country) == ("CBC Winnipeg studios", "Winnipeg", "MB", "Canada")
    assert pattern == "LOCATION_DASH_LOCATION_VENUE"
    assert confidence >= 92


def test_performer_list_is_not_generic_venue_evidence(tmp_path):
    support = M._SupportData(str(_support_files(tmp_path)))
    line = "Townes Van Zandt, Guy Clark, Marc Jordan, Murray McLauchlan"
    assert M._looks_like_comma_separated_performer_list(line, support) is True
    assert M._best_venue_from_lines([line], support) == ("", "", 0, -1)


def test_short_one_word_venue_requires_standalone_or_explicit_context(tmp_path):
    support = M._SupportData(str(_support_files(tmp_path)))
    assert M._best_venue_from_lines(["Townes Van Zandt"], support) == ("", "", 0, -1)
    assert M._best_venue_from_lines(["Van"], support)[0] == "Van"
    assert M._best_venue_from_lines(["Venue: Van"], support)[0] == "Van"


def test_date_duration_line_is_a_date_header_and_date_evidence():
    line = "1991-09-21 -- 51:27"
    assert M._looks_like_date_header_line(line) is True
    ranked = P._ranked_setlist_date_matches([line])
    assert ranked and ranked[0]["normalized"] == "1991-09-21"
