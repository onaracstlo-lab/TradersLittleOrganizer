"""Build 457 regressions for same-month multi-day date ranges."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior

__version__ = "v467"


def _matcher(*artists: str) -> ArtistMatcher:
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {artist.casefold(): {artist} for artist in artists}
    matcher.master_aliases = {artist: [artist] for artist in artists}
    matcher.master_norms = {
        artist: {"".join(ch for ch in artist.casefold() if ch.isalnum())}
        for artist in artists
    }
    return matcher


def _group(show_dir: Path) -> dict:
    return {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": "",
        "setlist_files": [],
        "music_dirs": [str(show_dir)],
        "music_file_count": 1,
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def _compliant_config() -> SimpleNamespace:
    return SimpleNamespace(
        compliant=True,
        current_volume_label="",
        current_slam="",
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
    )


def _noncompliant_config(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
        tlo_dbs_dir=str(tmp_path),
        debug=False,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "1970-04-12-13",
        "1970-04-12-13-14",
        "1970-04-12,13",
        "1970-04-12,13,14",
        "12-13 April 1970",
        "12-13-14 April 1970",
        "12,13 April 1970",
        "April 12-13, 1970",
        "April 12,13, 1970",
        "1970 April 12-13",
        "12th-13th Apr. 1970",
        "1970-04-12–13",
    ],
)
def test_build457_valid_multiday_ranges_use_first_day_as_canonical_date(raw):
    assert [
        (item["raw"], item["normalized"], item.get("date_range_kind"))
        for item in P._find_date_matches(raw)
    ] == [(raw, "1970-04-12", "same_month_day")]


@pytest.mark.parametrize(
    "raw",
    [
        "1970-04-13-12",
        "1970-04-12-12",
        "1970-04-14-13-15",
        "1970-04-12-13-14-15",
        "12-13-14-15 April 1970",
        "April 12-13-14-15, 1970",
        "1970-04-30-31",
        "1970-02-28-29",
        "13-12 April 1970",
        "April 13-12, 1970",
    ],
)
def test_build457_invalid_or_nonascending_multiday_ranges_are_rejected_as_a_whole(raw):
    assert P._find_date_matches(raw) == []


def test_build457_leap_year_range_validates_every_day():
    assert [(item["raw"], item["normalized"]) for item in P._find_date_matches("1972-02-28-29")] == [
        ("1972-02-28-29", "1972-02-28")
    ]


def test_build457_existing_year_range_rules_are_unchanged():
    assert [(item["raw"], item["normalized"]) for item in P._find_date_matches("1996-97-98")] == [
        ("1996-97-98", "1996-1998")
    ]
    assert [(item["raw"], item["normalized"]) for item in P._find_date_matches("96-98")] == [
        ("96-98", "1996-1998")
    ]
    assert [(item["raw"], item["normalized"]) for item in P._find_date_matches("1996-1998")] == [
        ("1996-1998", "1996-1998")
    ]


def test_build457_compliant_range_keeps_full_original_range_in_parentheticals(tmp_path: Path):
    show_dir = tmp_path / "Grateful Dead 1970-04-12-13 Fillmore West"
    show_dir.mkdir()

    record, dates, unresolved = P._extract_metadata_for_group(
        _compliant_config(), _group(show_dir), _matcher("Grateful Dead")
    )

    assert unresolved == []
    assert record.artist == "Grateful Dead"
    assert record.date == "1970-04-12"
    assert record.venue == "Fillmore West"
    assert record.parentheticals == "(1970-04-12-13)"
    assert record.show_name == "Grateful Dead 1970-04-12 Fillmore West (1970-04-12-13)"
    assert dates == [
        {
            "raw": "1970-04-12-13",
            "normalized": "1970-04-12",
            "part": "Grateful Dead 1970-04-12-13 Fillmore West",
            "source": "compliant",
        }
    ]
    assert any("multi-day date range retained in parentheticals" in item for item in record.observations)


def test_build457_textual_compliant_range_removes_entire_range_from_string2(tmp_path: Path):
    show_dir = tmp_path / "Grateful Dead 12-13 April 1970 Fillmore West"
    show_dir.mkdir()

    record, _dates, unresolved = P._extract_metadata_for_group(
        _compliant_config(), _group(show_dir), _matcher("Grateful Dead")
    )

    assert unresolved == []
    assert record.date == "1970-04-12"
    assert record.venue == "Fillmore West"
    assert record.album_name == "Fillmore West"
    assert record.parentheticals == "(12-13 April 1970)"
    assert record.show_name == "Grateful Dead 1970-04-12 Fillmore West (12-13 April 1970)"


def test_build457_noncompliant_date_artist_venue_location_range_uses_first_day(tmp_path: Path):
    show_dir = tmp_path / "1997-04-05-06 Genesis Old Pub London England"
    show_dir.mkdir()

    record, dates, unresolved = P._extract_metadata_for_group(
        _noncompliant_config(tmp_path), _group(show_dir), _matcher("Genesis")
    )

    assert unresolved == []
    assert record.artist == "Genesis"
    assert record.date == "1997-04-05"
    assert record.venue == "Old Pub"
    assert record.location == "London, England"
    assert record.parentheticals == "(1997-04-05-06)"
    assert record.show_name == "Genesis 1997-04-05 Old Pub London, England (1997-04-05-06)"
    assert any(item["source"] == "date_artist_venue_location" and item["raw"] == "1997-04-05-06" for item in dates)


def test_build457_research_uses_same_canonical_range_date():
    from tlo_research_lib import parse_research_query

    query = parse_research_query("Grateful Dead 12-13 April 1970")
    assert query.kind == "artist_date"
    assert query.artist == "Grateful Dead"
    assert query.date == "1970-04-12"
    assert query.date_candidates == ("1970-04-12",)


def test_build457_add_shows_shared_parser_understands_multiday_range():
    import tlo_inventory_update as updater

    row = updater._compliant_string_date_string2(
        "/readyForXfer/Grateful Dead 1970-04-12,13 Fillmore West"
    )
    assert row is not None
    assert row["date_norm"] == "1970-04-12"
    assert row["string2"] == "Fillmore West"
