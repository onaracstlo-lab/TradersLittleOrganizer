"""Build 378 regressions for weak artist-abbreviation precedence."""

__version__ = "v394"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _config(**overrides):
    values = dict(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        tlo_dbs_dir="",
        debug=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "grateful dead": {"Grateful Dead"},
        "gd": {"Grateful Dead"},
        "phish": {"Phish"},
    }
    matcher.master_aliases = {
        "Grateful Dead": ["Grateful Dead", "gd"],
        "Phish": ["Phish"],
    }
    matcher.master_norms = {
        "Grateful Dead": {"gratefuldead", "gd"},
        "Phish": {"phish"},
    }
    return matcher


def _group(path, *, setlist_file="", tags=None, music_files=None):
    tags = list(tags or [])
    music_files = list(music_files or [])
    return {
        "group_number": 1,
        "main_dir_name": os.path.basename(path),
        "main_dir_path": path,
        "setlist_file": setlist_file,
        "music_file_count": max(1, len(music_files), len(tags)),
        "setlist_files": [setlist_file] if setlist_file else [],
        "music_dirs": [path],
        "music_files": music_files,
        "music_sample_files": music_files[:2],
        "flac_tag_samples": tags,
        "flac_tag_artist_values": [row.get("artist", "") for row in tags if row.get("artist")],
        "flac_tag_album_values": [row.get("album", "") for row in tags if row.get("album")],
        "flac_tag_albumartist_values": [row.get("albumartist", "") for row in tags if row.get("albumartist")],
        "flac_tag_date_values": [row.get("date", "") for row in tags if row.get("date")],
    }


def test_short_no_space_date_abbreviation_is_last_resort_artist():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "music", "gd1977-05-08 Barton Hall Ithaca NY")
    group = _group(
        path,
        music_files=[os.path.join(path, "gd1977-05-08d1t01.flac")],
    )

    record, _dates, unresolved = phase._extract_metadata_for_group(_config(), group, _matcher())

    assert record.artist == "Grateful Dead"
    assert not any(reason == "unable to identify artist" for reason in unresolved)
    sources = [candidate.source for candidate in record.evidence.get("artist", [])]
    assert any(source.startswith("path_pattern_abbreviation_last_resort:gd") for source in sources)
    assert not any(source == "path pattern:gd" for source in sources)
    assert any("deferring the short prefix" in item for item in record.observations)
    assert any("using short artist abbreviation as last resort" in item for item in record.observations)


def test_full_artist_elsewhere_in_path_beats_short_abbreviation():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "music", "Grateful Dead", "gd1977-05-08 Barton Hall Ithaca NY")
    group = _group(
        path,
        music_files=[os.path.join(path, "gd1977-05-08d1t01.flac")],
    )

    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(), group, _matcher())

    assert record.artist == "Grateful Dead"
    sources = [candidate.source for candidate in record.evidence.get("artist", [])]
    assert any(source.startswith("path_artist_before_abbreviation:") for source in sources)
    assert not any("abbreviation_last_resort" in source for source in sources)


def test_explicit_setlist_artist_beats_short_abbreviation(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "gd1997-12-31 Madison Square Garden New York NY"
    path.mkdir()
    setlist = path / "show-info.txt"
    setlist.write_text(
        "Artist: Phish\nDate: 1997-12-31\nVenue: Madison Square Garden\nLocation: New York NY\n\n01 Song\n",
        encoding="utf-8",
    )
    group = _group(
        str(path),
        setlist_file=str(setlist),
        music_files=[str(path / "gd1997-12-31d1t01.flac")],
    )

    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(), group, _matcher())

    assert record.artist == "Phish"
    sources = [candidate.source for candidate in record.evidence.get("artist", [])]
    assert "setlist_metadata:EXPLICIT_ARTIST_KEY" in sources
    assert not any("abbreviation_last_resort" in source for source in sources)


def test_usable_raw_artist_tag_beats_short_abbreviation():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "music", "gd1977-05-08 Barton Hall Ithaca NY")
    music_file = os.path.join(path, "gd1977-05-08d1t01.flac")
    group = _group(
        path,
        music_files=[music_file],
        tags=[{"file": music_file, "artist": "Different Artist", "albumartist": "", "album": "", "date": ""}],
    )

    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(), group, _matcher())

    assert record.artist == "Different Artist"
    sources = [candidate.source for candidate in record.evidence.get("artist", [])]
    assert "flac_tag_artist_unmatched:Different Artist" in sources
    assert not any("abbreviation_last_resort" in source for source in sources)
