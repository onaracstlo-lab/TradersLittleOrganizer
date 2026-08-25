"""Behavioral coverage for commercial-release String1 - String2 parsing."""

__version__ = "v397"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _rod_matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"rod stewart": {"Rod Stewart"}}
    matcher.master_aliases = {"Rod Stewart": ["Rod Stewart"]}
    matcher.master_norms = {"Rod Stewart": {"rodstewart"}}
    return matcher


def _config():
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
    )


def _group(folder_name, tag_artist="Rod Stewart"):
    path = os.path.join(os.sep, "music", "Stewart, Rod", "Dave RIPs", folder_name)
    audio = os.path.join(path, "01. Song.flac")
    return {
        "group_number": 1,
        "main_dir_name": folder_name,
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [
            {
                "file": audio,
                "artist": tag_artist,
                "album": "The Studio Albums 1975 - 2001",
                "albumartist": tag_artist,
                "date": "2019-09-13",
            }
        ],
        "flac_tag_artist_values": [tag_artist],
        "flac_tag_album_values": ["The Studio Albums 1975 - 2001"],
        "flac_tag_albumartist_values": [tag_artist],
        "flac_tag_date_values": ["2019-09-13"],
    }


@pytest.mark.parametrize(
    ("folder_name", "expected_album"),
    [
        ("(1991) - Rod Stewart - vegabound heart", "vegabound heart"),
        ("1995 - Rod Stewart - A Spanner In The Works", "A Spanner In The Works"),
        ("(1998) - Rod Stewart - When We Were The New Boys", "When We Were The New Boys"),
        ("2001 - Rod Stewart - human", "human"),
    ],
)
def test_four_digit_commercial_release_year_is_omitted_from_show_name(folder_name, expected_album):
    import tlo_phase23_v2 as phase

    record, _date_matches, unresolved = phase._extract_metadata_for_group(
        _config(), _group(folder_name), _rod_matcher()
    )

    assert unresolved == []
    assert record.artist == "Rod Stewart"
    assert record.date == ""
    assert record.album_name == expected_album
    assert record.show_name == f"Rod Stewart - {expected_album}"
    assert any("commercial-release year prefix recognized and omitted" in item for item in record.observations)


def test_redundant_artist_prefix_is_removed_from_album_show_name():
    import tlo_phase23_v2 as phase

    record, _date_matches, unresolved = phase._extract_metadata_for_group(
        _config(), _group("Rod Stewart - Rod Stewart - Camouflage"), _rod_matcher()
    )

    assert unresolved == []
    assert record.date == ""
    assert record.album_name == "Camouflage"
    assert record.show_name == "Rod Stewart - Camouflage"
    assert any("redundant artist prefix removed" in item for item in record.observations)


@pytest.mark.parametrize(
    "year_component",
    [
        "1991-06-29",
        "(1991-06-29)",
        "1991-1998",
        "(1991-1998)",
        "91",
        "(91)",
        "199x",
        "album 1991",
    ],
)
def test_commercial_release_year_requires_only_a_four_digit_year_component(year_component):
    import tlo_phase23_v2 as phase

    row = phase._match_string_dash_string(f"{year_component} - Rod Stewart - Camouflage")
    assert phase._commercial_release_from_dash_row(row) is None


def test_commercial_release_pattern_can_supply_artist_without_tags():
    import tlo_phase23_v2 as phase

    group = _group("(1984) - Rod Stewart - Camouflage", tag_artist="")
    group["flac_tag_samples"] = []
    group["flac_tag_artist_values"] = []
    group["flac_tag_albumartist_values"] = []
    record, _date_matches, unresolved = phase._extract_metadata_for_group(
        _config(), group, _rod_matcher()
    )

    assert unresolved == []
    assert record.artist == "Rod Stewart"
    assert record.date == ""
    assert record.album_name == "Camouflage"
    assert record.show_name == "Rod Stewart - Camouflage"
