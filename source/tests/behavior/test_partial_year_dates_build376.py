"""Build 376 regressions for century-known partial dates."""

__version__ = "v421"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _duke_matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"duke ellington": {"Duke Ellington"}}
    matcher.master_aliases = {"Duke Ellington": ["Duke Ellington"]}
    matcher.master_norms = {"Duke Ellington": {"dukeellington"}}
    return matcher


def _compliant_config():
    return SimpleNamespace(
        compliant=True,
        current_volume_label="",
        current_slam="",
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
    )


def _group(folder_name: str):
    path = os.path.join(os.sep, "music", folder_name)
    return {
        "group_number": 1,
        "main_dir_name": folder_name,
        "main_dir_path": path,
        "setlist_file": os.path.join(path, "Duke ELLINGTON, Unissued Ellington by Danish Radio, 1957-1970, FM.txt"),
        "music_file_count": 20,
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


@pytest.mark.parametrize("date_value", ["19xx-xx-xx", "20xx-xx-xx"])
def test_century_known_unknown_year_dates_are_canonical_dates(date_value):
    import tlo_phase23_v2 as phase

    matches = phase._find_date_matches(date_value)
    assert [(row["raw"], row["normalized"]) for row in matches] == [(date_value, date_value)]


@pytest.mark.parametrize("date_value", ["1xxx-xx-xx", "2xxx-xx-xx"])
def test_one_digit_known_partial_year_remains_invalid(date_value):
    import tlo_phase23_v2 as phase

    assert phase._find_date_matches(date_value) == []


def test_compliant_duke_ellington_partial_year_folder_sets_artist_date_album():
    import tlo_phase23_v2 as phase

    record, date_matches, unresolved = phase._extract_metadata_for_group(
        _compliant_config(),
        _group("Duke Ellington 19xx-xx-xx Danish Radio"),
        _duke_matcher(),
    )

    assert unresolved == []
    assert record.artist == "Duke Ellington"
    assert record.date == "19xx-xx-xx"
    assert record.album_name == "Danish Radio"
    assert record.venue == "Danish Radio"
    assert record.show_name == "Duke Ellington 19xx-xx-xx Danish Radio"
    assert any(row.get("normalized") == "19xx-xx-xx" for row in date_matches)
    assert any("compliant String1 Date String2 matched" in item for item in record.observations)


def test_research_recognizes_century_known_partial_year_date():
    from tlo_research_lib import parse_research_query

    query = parse_research_query("Duke Ellington 19xx-xx-xx")
    assert query.kind == "artist_date"
    assert query.artist == "Duke Ellington"
    assert query.date == "19xx-xx-xx"
    assert query.date_candidates == ("19xx-xx-xx",)


def test_setlist_file_selector_recognizes_century_known_partial_year_text():
    import tlo_setlist_file_selection as selection

    assert any(pattern.search("Duke Ellington 19xx-xx-xx Danish Radio") for pattern in selection._COMPILED_DATE_PATTERNS)
    assert any(pattern.search("Duke Ellington 20xx-xx-xx Radio") for pattern in selection._COMPILED_DATE_PATTERNS)
