"""Build 375 regressions for stronger non-compliant artist evidence."""

__version__ = "v411"

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
        tlo_dbs_dir="",
    )


def _matcher(*masters):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for master in masters:
        matcher.exact_map.setdefault(master.casefold(), set()).add(master)
        matcher.master_aliases[master] = [master]
        matcher.master_norms[master] = {"".join(ch for ch in master.casefold() if ch.isalpha())}
    return matcher


def _group(path, *, setlist_file="", tags=None):
    tags = tags or []
    return {
        "group_number": 1,
        "main_dir_name": os.path.basename(path),
        "main_dir_path": path,
        "setlist_file": setlist_file,
        "music_file_count": max(1, len(tags)),
        "setlist_files": [setlist_file] if setlist_file else [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": tags,
        "flac_tag_artist_values": [row.get("artist", "") for row in tags if row.get("artist")],
        "flac_tag_album_values": [row.get("album", "") for row in tags if row.get("album")],
        "flac_tag_albumartist_values": [row.get("albumartist", "") for row in tags if row.get("albumartist")],
        "flac_tag_date_values": [row.get("date", "") for row in tags if row.get("date")],
    }


def test_unmatched_numeric_and_date_like_artist_tags_are_skipped_not_deferred():
    import tlo_phase23_v2 as phase
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="x",
        main_dir_path="x",
        setlist_file="",
        music_file_count=2,
        flac_tag_samples=[
            {"artist": "01", "albumartist": "", "album": "", "date": ""},
            {"artist": "1976-05", "albumartist": "", "album": "", "date": ""},
        ],
    )
    observations = []
    term, source = phase._selected_artist_tag_candidate(record, _matcher("Duke Ellington"), observations)
    assert (term, source) == ("", "")
    assert any("numeric-only" in item and "01" in item for item in observations)
    assert any("date-like" in item and "1976-05" in item for item in observations)


def test_legitimate_numeric_artist_still_allowed_when_db_backed():
    import tlo_phase23_v2 as phase
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="x",
        main_dir_path="x",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "311", "albumartist": "", "album": "", "date": ""}],
    )
    assert phase._selected_artist_tag_candidate(record, _matcher("311"), []) == ("311", "flac_tag_artist")


def test_last_first_path_component_resolves_db_master():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "d", "x", "E", "Ellington, Duke", "Unknown Recording")
    artist = phase._resolve_artist_from_subdirs(_group(path), _matcher("Duke Ellington"), {}, [], config=_config())
    assert artist == "Duke Ellington"


def test_artist_embedded_in_longer_path_component_resolves_db_master():
    import tlo_phase23_v2 as phase

    path = os.path.join(os.sep, "d", "x", "Duke Ellington, Unissued recordings by Danish Radio 1957-70")
    artist = phase._resolve_artist_from_subdirs(_group(path), _matcher("Duke Ellington"), {}, [], config=_config())
    assert artist == "Duke Ellington"


def test_selected_setlist_filename_is_db_backed_artist_fallback(tmp_path):
    import tlo_phase23_v2 as phase

    root = tmp_path / "Mystery Recording"
    root.mkdir()
    setlist = root / "Duke ELLINGTON, Unissued Ellington by Danish Radio, 1957-1970, FM.txt"
    setlist.write_text("01 Race\n02 u.t.\n", encoding="utf-8")
    tags = [{"file": str(root / "001.flac"), "artist": "01", "albumartist": "", "album": "1", "date": ""}]

    record, _date_matches, _unresolved = phase._extract_metadata_for_group(
        _config(), _group(str(root), setlist_file=str(setlist), tags=tags), _matcher("Duke Ellington")
    )
    assert record.artist == "Duke Ellington"
    assert any(candidate.source.startswith("setlist_filename:Duke ELLINGTON") for candidate in record.evidence.get("artist", []))
    assert not any("flac_tag_artist_unmatched" in candidate.source for candidate in record.evidence.get("artist", []))


def test_duke_ellington_failure_case_uses_path_not_bad_track_number_tags(tmp_path):
    import tlo_phase23_v2 as phase

    path = tmp_path / "E" / "Ellington, Duke" / "Duke Ellington, Unissued recordings by Danish Radio 1957-70"
    path.mkdir(parents=True)
    setlist = path / "Duke ELLINGTON, Unissued Ellington by Danish Radio, 1957-1970, FM.txt"
    setlist.write_text("01 Race\n02 u.t.\n", encoding="utf-8")
    tags = [
        {"file": str(path / "001 01 - Race.flac"), "artist": "01", "albumartist": "", "album": "1", "date": ""},
        {"file": str(path / "002 02 - u.t..flac"), "artist": "02", "albumartist": "", "album": "1", "date": ""},
    ]
    record, _date_matches, _unresolved = phase._extract_metadata_for_group(
        _config(), _group(str(path), setlist_file=str(setlist), tags=tags), _matcher("Duke Ellington")
    )
    assert record.artist == "Duke Ellington"
    assert record.artist != "01"
    assert any("numeric-only" in item and "01" in item for item in record.observations)
    assert not any("flac_tag_artist_unmatched:01" == candidate.source for candidate in record.evidence.get("artist", []))
