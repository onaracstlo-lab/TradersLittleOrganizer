"""Build 591: the NRBQ setlist and Artist/Venue/Location/Date folder fallback."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import shutil

import pytest

from tlo_artist_db import ArtistMatcher
from tlo_phase23_v2 import _extract_metadata_for_group
from tlo_setlist_metadata_lookup import extract_setlist_venue_location

pytestmark = pytest.mark.behavior

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "nrbq_talkhouse_1994_info.txt"
NAME = "NRBQ The Stephen Talkhouse Miami Beach 1994-12-10 Dolphinsmile Master"


def _matcher():
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"nrbq": {"NRBQ"}}
    matcher.master_aliases = {"NRBQ": ["NRBQ"]}
    matcher.master_norms = {"NRBQ": {"nrbq"}}
    return matcher


def _config(tmp_path):
    return SimpleNamespace(
        compliant=False, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master",
        etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(tmp_path),
        TLOHome=str(tmp_path), debug=False,
    )


def _group(tmp_path, name=NAME, text=None):
    folder = tmp_path / name
    folder.mkdir()
    info = folder / "info.txt"
    if text is None:
        shutil.copyfile(FIXTURE, info)
    elif text:
        info.write_text(text, encoding="utf-8")
    return {
        "group_number": 1, "main_dir_name": folder.name, "main_dir_path": str(folder),
        "setlist_file": str(info) if info.exists() else "",
        "setlist_files": [str(info)] if info.exists() else [],
        "music_dirs": [str(folder)], "music_file_count": 26,
        "flac_tag_samples": [], "flac_tag_artist_values": [],
        "flac_tag_album_values": [], "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def test_exact_original_setlist_extracts_artist_separately_from_slash_date(tmp_path):
    group = _group(tmp_path)
    metadata = extract_setlist_venue_location(group["setlist_file"], str(tmp_path))
    assert metadata.artist == "NRBQ"
    assert metadata.venue == "The Talkhouse"
    assert (metadata.city, metadata.region) == ("Miami", "FL")


def test_original_folder_with_source_tail_renames_correctly(tmp_path):
    group = _group(tmp_path)
    record, dates, unresolved = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert (record.artist, record.date, record.venue, record.location) == (
        "NRBQ", "1994-12-10", "The Talkhouse", "Miami, FL"
    )
    assert record.show_name == "NRBQ 1994-12-10 The Talkhouse Miami, FL"
    assert "Dolphinsmile" not in record.show_name
    assert "1994-10-12" not in record.show_name
    assert not unresolved
    assert any("setlist-confirmed Artist Venue City Date fallback" in x for x in record.observations)
    assert any(x["source"] == "setlist_confirmed_artist_place_date" for x in dates)


def test_original_without_trailing_string2(tmp_path):
    group = _group(tmp_path, NAME.replace(" Dolphinsmile Master", ""))
    record, _, unresolved = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.show_name == "NRBQ 1994-12-10 The Talkhouse Miami, FL"
    assert not unresolved


def test_unknown_db_artist_independently_confirmed(tmp_path):
    group = _group(tmp_path)
    record, _, unresolved = _extract_metadata_for_group(_config(tmp_path), group, ArtistMatcher(db_path=""))
    assert record.artist == "NRBQ"
    assert record.artist_not_in_database == "NRBQ"
    assert not unresolved


def test_setlist_with_incorrect_date_cannot_confirm_folder(tmp_path):
    text = FIXTURE.read_text().replace("12/10/1994", "12/11/1994")
    group = _group(tmp_path, text=text)
    record, _, _ = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert not any("setlist-confirmed Artist Venue City Date fallback" in x for x in record.observations)


def test_setlist_with_unrelated_venue_does_not_confirm_folder(tmp_path):
    text = FIXTURE.read_text().replace("The Talkhouse", "Unrelated Auditorium")
    group = _group(tmp_path, text=text)
    record, _, _ = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert not any("setlist-confirmed Artist Venue City Date fallback" in x for x in record.observations)


def test_setlist_with_unrelated_artist_does_not_confirm_folder(tmp_path):
    text = FIXTURE.read_text().replace("NRBQ 12/10/1994", "Other Band 12/10/1994")
    group = _group(tmp_path, text=text)
    record, _, _ = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert not any("setlist-confirmed Artist Venue City Date fallback" in x for x in record.observations)


def test_without_setlist_can_use_db_unique_artist_and_state_anchored_place(tmp_path):
    group = _group(tmp_path, "NRBQ The Talkhouse Miami FL 1994-12-10", text="")
    record, _, unresolved = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.artist == "NRBQ"
    assert record.date == "1994-12-10"
    assert record.venue == "The Talkhouse"
    assert record.location == "Miami, FL"
    assert not unresolved
    assert any("without String2" in x for x in record.observations)


def test_without_setlist_or_db_cannot_guess_venue_and_city(tmp_path):
    group = _group(tmp_path, "NRBQ The Talkhouse Miami FL 1994-12-10", text="")
    record, _, _ = _extract_metadata_for_group(_config(tmp_path), group, None)
    assert not any("without String2" in x for x in record.observations)


def test_no_string2_unstructured_place_not_promoted_without_setlist(tmp_path):
    group = _group(tmp_path, "NRBQ Mystery Theater Locality 1994-12-10", text="")
    record, _, _ = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert not any("without String2" in x for x in record.observations)


def test_add_new_shows_rename_uses_exact_setlist_confirmed_metadata(tmp_path):
    from tlo_inventory_update import _metadata_to_record_dict, _rename_add_shows_folder_compliantly

    group = _group(tmp_path)
    record, _, unresolved = _extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert not unresolved
    row = _metadata_to_record_dict(record)
    config = _config(tmp_path)
    config.rename_compliantly = True
    destination = _rename_add_shows_folder_compliantly(config, group["main_dir_path"], row)
    assert Path(destination).name == "NRBQ 1994-12-10 The Talkhouse Miami, FL"
    assert (Path(destination) / "info.txt").is_file()
    assert row["main_dir_path"] == destination
