"""Build 375 regressions for non-compliant artist/path evidence precedence."""

__version__ = "v413"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


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


def _firefall_matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"firefall": {"Firefall"}}
    matcher.master_aliases = {"Firefall": ["Firefall"]}
    matcher.master_norms = {"Firefall": {"firefall"}}
    return matcher


def _firefall_group():
    path = os.path.join(
        os.sep,
        "d",
        "x",
        "F",
        "Firefall",
        "Firefall 1976-05-xx Cleveland FM Broadcast",
    )
    return {
        "group_number": 1,
        "main_dir_name": os.path.basename(path),
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 11,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [
            {
                "file": os.path.join(path, "01 - Introduction - WMMS.flac"),
                "artist": "01 - Introduction - WMMS",
                "album": "1976-05 - Cleveland Agora FM",
                "albumartist": "",
                "date": "",
            },
            {
                "file": os.path.join(path, "02 - It Doesn't Matter.flac"),
                "artist": "1976-05",
                "album": "Cleveland Agora FM",
                "albumartist": "",
                "date": "",
            },
        ],
        "flac_tag_artist_values": ["01 - Introduction - WMMS", "1976-05"],
        "flac_tag_album_values": ["1976-05 - Cleveland Agora FM", "Cleveland Agora FM"],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def test_meaningful_show_folder_containing_fm_broadcast_is_not_metadata_wrapper():
    import tlo_phase23_v2 as phase

    assert phase._is_wrapper("FM Broadcast") is True
    assert phase._is_wrapper("Firefall 1976-05-xx Cleveland FM Broadcast") is False
    required, optional = phase._collect_pattern_matches(
        os.path.join(os.sep, "music", "Firefall", "Firefall 1976-05-xx Cleveland FM Broadcast")
    )
    matches = required or optional
    assert any(row.get("string1") == "Firefall" and row.get("date_norm") == "1976-05-xx" for row in matches)


def test_unmatched_track_title_artist_tag_does_not_block_db_backed_firefall_path():
    import tlo_phase23_v2 as phase

    record, _date_matches, unresolved = phase._extract_metadata_for_group(
        _config(), _firefall_group(), _firefall_matcher()
    )

    assert unresolved == []
    assert record.artist == "Firefall"
    assert record.date == "1976-05-xx"
    assert record.show_name.startswith("Firefall 1976-05-xx")
    assert any("deferring raw tag artist" in item and "01 - Introduction - WMMS" in item for item in record.observations)
    sources = [candidate.source for candidate in record.evidence.get("artist", [])]
    assert any(source.startswith("path pattern:Firefall") for source in sources)
    assert not any("flac_tag_artist_unmatched" in source for source in sources)


def test_unmatched_raw_tag_remains_last_resort_when_no_better_artist_exists():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "music", "Mystery Recording 1976-05-xx")
    group = {
        "group_number": 1,
        "main_dir_name": os.path.basename(path),
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [{"file": os.path.join(path, "01.flac"), "artist": "Raw Artist", "album": "", "albumartist": "", "date": ""}],
        "flac_tag_artist_values": ["Raw Artist"],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    record, _date_matches, _unresolved = phase._extract_metadata_for_group(_config(), group, _firefall_matcher())

    assert record.artist == "Raw Artist"
    assert any("using deferred raw tag artist: Raw Artist" in item for item in record.observations)
    assert any(candidate.source == "flac_tag_artist_unmatched:Raw Artist" for candidate in record.evidence.get("artist", []))
