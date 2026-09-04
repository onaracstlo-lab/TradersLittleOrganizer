"""Build 380 regressions for compliant String1 - String2 Date precedence."""

__version__ = "v433"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "the georgia satellites": {"The Georgia Satellites"},
        "georgia satellites": {"The Georgia Satellites"},
    }
    matcher.master_aliases = {
        "The Georgia Satellites": ["The Georgia Satellites", "Georgia Satellites"],
    }
    matcher.master_norms = {
        "The Georgia Satellites": {"thegeorgiasatellites", "georgiasatellites"},
    }
    return matcher


def _config():
    return SimpleNamespace(
        compliant=True,
        current_volume_label="",
        current_slam="",
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
    )


def _group(folder_name: str):
    path = os.path.join(os.sep, "x", "G", "Georgia Satellites", folder_name)
    return {
        "group_number": 1,
        "main_dir_name": folder_name,
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 4,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def test_build380_trailing_date_after_dash_precedes_generic_dash_rule():
    import tlo_phase23_v2 as phase

    record, date_matches, unresolved = phase._extract_metadata_for_group(
        _config(),
        _group("The Georgia Satellites - Santa Cruz  01-17-87"),
        _matcher(),
    )

    assert unresolved == []
    assert record.artist == "The Georgia Satellites"
    assert record.date == "1987-01-17"
    assert record.venue == "Santa Cruz"
    assert record.location == ""
    assert record.album_name == "Santa Cruz"
    assert record.show_name == "The Georgia Satellites 1987-01-17 Santa Cruz"
    assert any(row.get("source") == "compliant_string_dash_string_date" for row in date_matches)
    assert any("compliant String1 - String2 Date matched (trailing date)" in item for item in record.observations)
    assert not any("no date assigned" in item for item in record.observations)


def test_build380_leading_complete_date_inside_string2_is_same_narrow_pattern():
    import tlo_phase23_v2 as phase

    row = phase._match_compliant_string_dash_string_date(
        "The Georgia Satellites - 01-17-87 Santa Cruz"
    )

    assert row is not None
    assert row["string1"] == "The Georgia Satellites"
    assert row["string2"] == "Santa Cruz"
    assert row["date_norm"] == "1987-01-17"
    assert row["date_position"] == "leading"


def test_build380_dash_date_helper_preserves_trailing_parenthetical_qualifier():
    import tlo_phase23_v2 as phase

    row = phase._match_compliant_string_dash_string_date(
        "The Georgia Satellites - Santa Cruz 01-17-87 (FM)"
    )

    assert row is not None
    assert row["date_norm"] == "1987-01-17"
    assert row["string2"] == "Santa Cruz"
    assert row["parentheticals"] == "(FM)"


@pytest.mark.parametrize(
    "folder_name",
    [
        "The Georgia Satellites - Santa Cruz 1987",
        "The Georgia Satellites - Tour 1977-1980",
    ],
)
def test_build380_dash_date_refinement_does_not_reclassify_broad_album_text(folder_name):
    import tlo_phase23_v2 as phase

    assert phase._match_compliant_string_dash_string_date(folder_name) is None
    record, _date_matches, unresolved = phase._extract_metadata_for_group(
        _config(),
        _group(folder_name),
        _matcher(),
    )

    assert unresolved == []
    assert record.date == ""
    assert record.show_name == folder_name
    assert any("compliant String1 - String2 matched" in item for item in record.observations)


def test_build380_add_shows_recognizes_dash_date_before_generic_dash():
    import tlo_inventory_update as updater

    row = updater._compliant_string_dash_string2_date(
        os.path.join(os.sep, "readyForXfer", "The Georgia Satellites - Santa Cruz 01-17-87")
    )

    assert row is not None
    assert row["pattern"] == "string_dash_string_date"
    assert row["artist"] == "The Georgia Satellites"
    assert row["date_norm"] == "1987-01-17"
    assert row["string2"] == "Santa Cruz"
    assert row["show_name"] == "The Georgia Satellites 1987-01-17 Santa Cruz"
