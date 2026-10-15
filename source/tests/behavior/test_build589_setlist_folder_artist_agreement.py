"""Build 589: independent artist corroboration from selected setlist and show folder."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

import tlo_phase23_v2 as inventory
from tlo_artist_db import ArtistMatcher
from tlo_postprocess import _collect_artists_not_in_database, _write_artists_not_in_database


def _config(root: Path, *, compliant: bool = False):
    return SimpleNamespace(
        compliant=compliant, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master",
        etree_lookup=False, setlistfm_lookup=False,
        tlo_dbs_dir=str(root), TLOHome=str(root), debug=False,
    )


def _group(tmp_path: Path, folder: str, text: str):
    show = tmp_path / folder
    show.mkdir()
    info = show / "info.txt"
    info.write_text(text, encoding="utf-8")
    return {
        "group_number": 1, "main_dir_name": folder, "main_dir_path": str(show),
        "setlist_file": str(info), "setlist_files": [str(info)],
        "txt_files": [str(info)], "music_dirs": [str(show)],
        "music_files": [str(show / "01.flac")], "music_file_count": 1,
    }


def _structured_setlist(artist: str) -> str:
    return (f"{artist}\n"
            "Live at Great Hall, Lexington, KY, 2026-03-03\n\n"
            "01. An Original Song\n")


def test_folder_agreement_handles_articles_collaboration_punctuation():
    agree = inventory._artist_agrees_with_leading_show_folder
    assert agree("The Bad Plus, Chris Potter, & Craig Taborn", "Bad Plus, Chris Potter, and Craig Taborn 2026-03-03 Kentucky KY (24)")
    assert agree("Arlo's New Band", "Arlo’s New Band 2026-03-03 Venue")
    assert agree("Fresh Act", "Fresh Act 2026-03-03 Hall")
    assert not agree("Fresh Act", "Fresh Acting 2026-03-03 Hall")
    assert not agree("Fresh Act", "Other Fresh Act 2026-03-03 Hall")
    assert not agree("Fresh Act", "Fresh Actor 2026-03-03 Hall")
    assert not agree("Live", "Live Concert Hall")
    assert not agree("", "Fresh Act 2026-03-03")


def test_unlisted_structured_artist_with_matching_folder_is_recognized_and_logged(tmp_path):
    artist = "The Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall Lexington KY", _structured_setlist(artist))
    matcher = ArtistMatcher(db_path="")
    record, _, unresolved = inventory._extract_metadata_for_group(_config(tmp_path), group, matcher)
    assert record.artist == artist
    assert record.date == "2026-03-03"
    assert record.artist_not_in_database == artist
    assert "unable to identify artist" not in unresolved
    assert any("artist not in Artist DB" in value for value in record.observations)
    rows = [{"artist_not_in_database": record.artist_not_in_database}]
    artists = _collect_artists_not_in_database(rows)
    target = _write_artists_not_in_database(str(tmp_path), artists)
    assert Path(target).read_text(encoding="utf-8").strip() == artist


def test_unlisted_structured_artist_missing_db_matcher(tmp_path):
    artist = "Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall", _structured_setlist(artist))
    record, _, unresolved = inventory._extract_metadata_for_group(_config(tmp_path), group, None)
    assert record.artist == artist
    assert record.artist_not_in_database == artist
    assert "unable to identify artist" not in unresolved


def test_unlisted_structured_artist_unrelated_folder_not_promoted(tmp_path):
    group = _group(tmp_path, "Different Act 2026-03-03 Great Hall", _structured_setlist("The Zeta Blue Trio"))
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path), group, ArtistMatcher(db_path=""))
    assert record.artist != "The Zeta Blue Trio"
    assert record.artist_not_in_database != "The Zeta Blue Trio"


def test_unlisted_structured_artist_cannot_match_parent_dir(tmp_path):
    parent = tmp_path / "The Zeta Blue Trio"
    parent.mkdir()
    group = _group(parent, "Different Act 2026-03-03 Great Hall", _structured_setlist("The Zeta Blue Trio"))
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path), group, None)
    assert record.artist_not_in_database != "The Zeta Blue Trio"


def test_explicit_header_folder_agreement_is_logged(tmp_path):
    artist = "The New Unlisted Quartet"
    text = f"Artist: {artist}\nDate: 2026-03-03\nVenue: Great Hall\n\n01. An Original Song\n"
    group = _group(tmp_path, "New Unlisted Quartet 2026-03-03 Great Hall", text)
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path), group, None)
    assert record.artist == artist
    assert record.artist_not_in_database == artist


def test_db_known_structured_artist_is_not_logged_unlisted(tmp_path):
    artist = "Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall", _structured_setlist(artist))
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"zeta blue trio": {artist}}
    matcher.master_aliases = {artist: [artist]}
    matcher.master_norms = {artist: {"zetabluetrio"}}
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path), group, matcher)
    assert record.artist == artist
    assert not record.artist_not_in_database


def test_compliant_unknown_artist_is_reported_without_changing_folder_based_show_name(tmp_path):
    artist = "The Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall", _structured_setlist(artist))
    record, _, unresolved = inventory._extract_metadata_for_group(_config(tmp_path, compliant=True), group, None)
    assert record.artist == "Zeta Blue Trio"
    assert record.artist_not_in_database == "Zeta Blue Trio"
    assert "Zeta Blue Trio 2026-03-03" in record.show_name
    assert "unable to identify artist" not in unresolved


def test_compliant_known_artist_not_reported_as_missing(tmp_path):
    artist = "Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall", _structured_setlist(artist))
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"zeta blue trio": {artist}}
    matcher.master_aliases = {artist: [artist]}
    matcher.master_norms = {artist: {"zetabluetrio"}}
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path, compliant=True), group, matcher)
    assert record.artist == artist
    assert not record.artist_not_in_database


def test_compliant_unrelated_setlist_artist_is_not_logged_as_corrobated(tmp_path):
    group = _group(tmp_path, "Different Act 2026-03-03 Great Hall", _structured_setlist("Zeta Blue Trio"))
    record, _, _ = inventory._extract_metadata_for_group(_config(tmp_path, compliant=True), group, None)
    assert record.artist_not_in_database != "Zeta Blue Trio"


def test_confirmed_bad_plus_event_header_is_logged_even_without_db_entry(tmp_path):
    from tests.behavior.test_build588_inventory_tag_setlist import EXAMPLE

    group = _group(tmp_path, "Bad Plus, Chris Potter, and Craig Taborn 2026-03-03 Kentucky Lexington KY", EXAMPLE)
    record, _, unresolved = inventory._extract_metadata_for_group(_config(tmp_path), group, None)
    assert record.artist == "The Bad Plus, Chris Potter, & Craig Taborn"
    assert record.artist_not_in_database == record.artist
    assert "unable to identify artist" not in unresolved


def test_actual_flac_tagging_accepts_unlisted_artist_confirmed_by_folder(tmp_path):
    """A matched unknown artist must not be skipped as unidentified in Tag in Place."""
    import shutil
    import subprocess

    from mutagen.flac import FLAC
    from inventory_parser_lib import Config
    from tlo_tag_lib import tag_group_with_record

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable to generate a valid short FLAC")
    artist = "The Zeta Blue Trio"
    group = _group(tmp_path, "Zeta Blue Trio 2026-03-03 Great Hall Lexington KY", _structured_setlist(artist))
    filename = Path(group["music_files"][0])
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "0.2", "-c:a", "flac", "-y", str(filename)],
        check=True, capture_output=True, timeout=20,
    )
    config = Config(
        debug=False, silent=True, TLOHome=str(tmp_path),
        current_search_path=str(filename.parent), tlo_dbs_dir=str(tmp_path / "TLO_DBs"),
        corrupt_files="keep", corrupt_folders="never", tag_during_inventory=True,
    )
    record, _, unresolved = inventory._extract_metadata_for_group(config, group, None)
    assert not unresolved
    assert record.artist_not_in_database == artist
    results = tag_group_with_record(
        config, group, record, allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        fallback_to_title_tags_on_track_problem=True,
    )
    assert results["tagged"] == 1 and results["errors"] == 0 and results["skipped"] == 0
    tagged = FLAC(filename)
    assert tagged["artist"][0] == artist
    assert tagged["title"][0] == "An Original Song"
