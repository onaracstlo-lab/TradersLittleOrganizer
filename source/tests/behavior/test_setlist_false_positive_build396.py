"""Build 396 regressions for setlist filename artist and location false positives."""

__version__ = "v414"

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior


def _matcher(*masters):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for master in masters:
        matcher.exact_map.setdefault(master.casefold(), set()).add(master)
        matcher.master_aliases[master] = [master]
        matcher.master_norms[master] = {"".join(ch for ch in master.casefold() if ch.isalpha())}
    return matcher


def test_two_gentlemen_filename_does_not_promote_artist_two(tmp_path):
    import tlo_phase23_v2 as phase
    from tlo_models import ShowMetadata

    setlist = tmp_path / "Two Gentlemen.txt"
    setlist.write_text("Two Gentlemen In New York\n", encoding="utf-8")
    record = ShowMetadata(
        group_number=1,
        main_dir_name="David Bowie - John Cale 1979-10-05 New York 7 Inch",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=2,
    )
    evidence = {}
    observations = []
    artist = phase._resolve_artist_from_setlist_filename(record, _matcher("Two"), evidence, observations)
    assert artist == ""
    assert not evidence.get("artist")


def test_single_word_filename_artist_with_date_remains_supported(tmp_path):
    import tlo_phase23_v2 as phase
    from tlo_models import ShowMetadata

    setlist = tmp_path / "Prince 1984-06-07.txt"
    setlist.write_text("01 Intro\n", encoding="utf-8")
    record = ShowMetadata(
        group_number=1,
        main_dir_name="Mystery",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
    )
    assert phase._resolve_artist_from_setlist_filename(record, _matcher("Prince"), {}, []) == "Prince"


def test_two_gentlemen_in_new_york_is_not_location(tmp_path):
    import tlo_setlist_metadata_lookup as metadata

    dbs = tmp_path / "TLO_DBs"
    dbs.mkdir()
    support = metadata._SupportData(str(dbs))
    assert metadata._parse_trailing_region_location("Two Gentlemen In New York", support) == ("", "", "", "", "", 0)
    assert metadata._parse_location_from_text("Two Gentlemen In New York", support) == ("", "", "", "", "", 0)


def test_albany_new_york_remains_valid_location(tmp_path):
    import tlo_setlist_metadata_lookup as metadata

    dbs = tmp_path / "TLO_DBs"
    dbs.mkdir()
    support = metadata._SupportData(str(dbs))
    city, region, country, _raw, pattern, confidence = metadata._parse_trailing_region_location("Albany New York", support)
    assert (city, region, country) == ("Albany", "NY", "USA")
    assert pattern == "LOCATION_TRAILING_REGION"
    assert confidence == 84


def test_string2_does_not_make_in_a_city():
    import tlo_phase23_v2 as phase

    assert phase._parse_string2("Two Gentlemen In, NY") == ("", "", "", "", "")
