"""Build 617: setlist first-line artist with 'Recorded Live in City YEAR'."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher
from tlo_setlist_metadata_lookup import extract_setlist_venue_location

pytestmark = pytest.mark.behavior

PFUNK = (
    "Parliament-Funkadelic\n"
    'Liberated Bootleg - "Rocky Mountain Shakedown"\n'
    "Recorded Live in Denver 1976\n"
    "SBD (??)\n"
    "CD > eac > WAV > FLAC\n\n"
    " 1. Children of Production\n"
    " 2. Mothership Connection (Starchild)\n"
    " 3. Swing Down, Sweet Chariot\n\n"
    "While the bootleg lists only Funkadelic, I've decided to just call "
    "the artist, Parliament-Funkadelic.\n"
)


def _matcher():
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"parliamentfunkadelic": {"Parliament Funkadelic"}}
    matcher.master_aliases = {"Parliament Funkadelic": ["Parliament Funkadelic", "Parliament-Funkadelic"]}
    matcher.master_norms = {"Parliament Funkadelic": {"parliamentfunkadelic"}}
    return matcher


def _group(tmp_path: Path, text: str = PFUNK, folder_name: str = "- xxxx-xx-xx"):
    show = tmp_path / folder_name
    show.mkdir()
    info = show / "funkadelic1976info.txt"
    info.write_text(text, encoding="utf-8")
    flac = show / "01 - - Track01.flac"
    return {
        "group_number": 1, "main_dir_name": folder_name, "main_dir_path": str(show),
        "setlist_file": str(info), "setlist_files": [str(info)], "txt_files": [str(info)],
        "music_dirs": [str(show)], "music_files": [str(flac)], "music_file_count": 9,
        "flac_tag_samples": [
            {"file": str(flac), "artist": "-", "album": "- xxxx-xx-xx", "date": "", "albumartist": ""},
        ],
    }


def _config(tmp_path: Path, compliant: bool = False):
    return SimpleNamespace(
        compliant=compliant, current_volume_label="", current_slam="", proper_grammar=False,
        as_is_artist_name=False, compliant_artist_mode="master", etree_lookup=False,
        setlistfm_lookup=False, tlo_dbs_dir=str(tmp_path), TLOHome=str(tmp_path), debug=False,
    )


def test_actual_uploaded_setlist_style_extracts_artist_year_city(tmp_path):
    group = _group(tmp_path)
    result = extract_setlist_venue_location(group["setlist_file"], str(tmp_path))
    assert result.artist == "Parliament-Funkadelic"
    assert result.artist_source == "setlist_metadata:CORROBORATED_RECORDED_LIVE_HEADER"
    assert result.year_hint == "1976"
    assert result.city == "Denver"
    assert result.location == "Denver"
    assert result.venue == "" and result.region == "" and result.country == ""


def test_full_metadata_uses_master_and_partial_date_not_filename_descriptor(tmp_path):
    group = _group(tmp_path)
    record, _date_matches, unresolved = phase._extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.artist == "Parliament Funkadelic"
    assert record.date == "1976-xx-xx"
    assert record.city == "Denver"
    assert record.venue == "" and record.region == ""
    assert record.descriptor == ""
    assert record.show_name == "Parliament Funkadelic 1976-xx-xx Denver"
    assert not unresolved
    assert record.flac_tag_samples[0]["artist"] == ""
    assert any("punctuation-only" in note for note in record.observations)
    assert any("recorded-live year" in note for note in record.observations)


def test_real_setlist_body_note_can_confirm_artist_even_without_db(tmp_path):
    group = _group(tmp_path)
    record, _dates, unresolved = phase._extract_metadata_for_group(_config(tmp_path), group, ArtistMatcher(db_path=""))
    assert record.artist == "Parliament-Funkadelic"
    assert record.date == "1976-xx-xx"
    assert record.city == "Denver"
    assert "unable to identify artist" not in unresolved


def test_uncorroborated_first_line_without_db_is_not_promoted(tmp_path):
    text = PFUNK.split("While the bootleg")[0]
    group = _group(tmp_path, text)
    record, _dates, _unresolved = phase._extract_metadata_for_group(
        _config(tmp_path), group, ArtistMatcher(db_path="")
    )
    assert record.artist != "Parliament-Funkadelic"
    assert record.date != "1976-xx-xx"
    assert "Parliament-Funkadelic" not in record.show_name


def test_uncorroborated_header_can_use_unique_artist_db_match(tmp_path):
    group = _group(tmp_path, PFUNK.split("While the bootleg")[0])
    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.artist == "Parliament Funkadelic"
    assert record.date == "1976-xx-xx"


def test_explicit_existing_date_not_overwritten_by_year_hint(tmp_path):
    group = _group(tmp_path, folder_name="Parliament Funkadelic 1977-05-09 Live")
    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.date == "1977-05-09"


def test_prose_year_not_promoted_without_explicit_recorded_live_header(tmp_path):
    text = PFUNK.replace("Recorded Live in Denver 1976", "An old recording from Denver in 1976")
    group = _group(tmp_path, text)
    result = extract_setlist_venue_location(group["setlist_file"], str(tmp_path))
    assert result.year_hint == ""
    assert result.artist == ""


def test_compliant_mode_keeps_existing_folder_based_rules(tmp_path):
    group = _group(tmp_path)
    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(tmp_path, compliant=True), group, _matcher())
    assert record.show_name != "Parliament Funkadelic 1976-xx-xx Denver"


@pytest.mark.parametrize("tag", ["-", "--", "...", "???", " "])
def test_punctuation_only_tags_do_not_become_artists(tmp_path, tag):
    group = _group(tmp_path)
    group["flac_tag_samples"][0]["artist"] = tag
    record, _dates, _unresolved = phase._extract_metadata_for_group(_config(tmp_path), group, _matcher())
    assert record.artist == "Parliament Funkadelic"
