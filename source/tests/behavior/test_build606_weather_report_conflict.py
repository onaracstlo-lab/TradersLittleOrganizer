from pathlib import Path
"""Build 606: organizational path buckets and missing-venue setlist headers."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "weather report": {"Weather Report"},
        "xx": {"XX"},
        "ab": {"AB"},
        "other artist": {"Other Artist"},
    }
    matcher.master_aliases = {
        "Weather Report": ["Weather Report"],
        "XX": ["XX"],
        "AB": ["AB"],
        "Other Artist": ["Other Artist"],
    }
    matcher.master_norms = {
        "Weather Report": {"weatherreport"},
        "XX": {"xx"},
        "AB": {"ab"},
        "Other Artist": {"otherartist"},
    }
    return matcher


def _config(root):
    return SimpleNamespace(
        compliant=False, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master", etree_lookup=False,
        setlistfm_lookup=False, tlo_dbs_dir=str(root), debug=False,
    )


def _group(path, setlist=None):
    return {
        "group_number": 389,
        "main_dir_name": path.name,
        "main_dir_path": str(path),
        "setlist_file": str(setlist) if setlist else "",
        "music_file_count": 6,
        "setlist_files": [str(setlist)] if setlist else [],
        "music_dirs": [str(path)],
        "music_files": [str(path / "1-fixed.flac")],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def _actual_setlist(path):
    # Preserve the user's exact header and realistic tracklist from the report.
    path.write_text(
        "WEATHER REPORT\n\nChateauvallon, France\n\nUnknown venue.\n"
        "August 24, 1973\n\nSBD FM\n\n492 Mb\nTT 1:24:41\n"
        "1. Boogie Woogie Waltz\n2. 125th Street Congress\n"
        "3. Sophisticated Lady\n4. Early Minor - Directions\n",
        encoding="utf-8",
    )
    return path


def test_build606_setlist_header_without_venue(tmp_path):
    from tlo_setlist_metadata_lookup import extract_setlist_venue_location

    setlist = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "build606_weather_report.txt"
    result = extract_setlist_venue_location(str(setlist), str(tmp_path))
    assert result.artist == "WEATHER REPORT"
    assert result.artist_source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
    assert result.venue == ""
    assert (result.city, result.country) == ("Chateauvallon", "France")


def test_build606_real_path_noncompliant_with_organizational_xx(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "xx" / "W" / "Weather Report" / "1973" / "wr1973-08-24.sbd.sbeok.flac16"
    path.mkdir(parents=True)
    setlist = path / "WR1973-08-24.sbd.sbeok.flac16.txt"
    setlist.write_bytes((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "build606_weather_report.txt").read_bytes())
    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(tmp_path), _group(path, setlist), _matcher()
    )
    assert record.artist == "Weather Report"
    assert record.date == "1973-08-24"
    assert record.venue == ""
    assert record.city == "Chateauvallon"
    assert record.country == "France"
    assert not record.conflicts
    assert not unresolved


def test_build606_short_artist_can_still_be_recording_artist(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "Weather Report" / "AB" / "ab1973-08-24"
    path.mkdir(parents=True)
    # A short artist closer to the recording than the long artist directory
    # must not be silently removed by the organizational-directory guard.
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), _matcher(), evidence, conflicts
    )
    assert artist == ""
    assert conflicts


def test_build606_different_full_artist_directory_remains_conflict(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "Other Artist" / "Weather Report" / "1973" / "wr1973-08-24"
    path.mkdir(parents=True)
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), _matcher(), evidence, conflicts
    )
    assert artist == ""
    assert conflicts


def test_build606_nearby_short_artist_is_valid_without_stronger_dir(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "xx" / "wr1973-08-24"
    path.mkdir(parents=True)
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), _matcher(), evidence, conflicts
    )
    assert artist == "XX"
    assert not conflicts


def test_build606_missing_venue_marker_is_never_promoted(tmp_path):
    from tlo_setlist_metadata_lookup import extract_setlist_venue_location

    (tmp_path / "venues.txt").write_text("Unknown Venue\n", encoding="utf-8")
    setlist = _actual_setlist(tmp_path / "info.txt")
    result = extract_setlist_venue_location(str(setlist), str(tmp_path))
    assert result.venue == ""
    assert result.artist == "WEATHER REPORT"
