"""Build 382 regressions for structured unlabeled setlist artist evidence."""

__version__ = "v446"

from types import SimpleNamespace

import pytest

from tlo_models import Candidate, ShowMetadata

pytestmark = pytest.mark.behavior


def _matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "kinky friedman": {"Kinky Friedman"},
        "lone star cafe": {"Lone Star Cafe"},
    }
    matcher.master_aliases = {
        "Kinky Friedman": ["Kinky Friedman"],
        "Lone Star Cafe": ["Lone Star Cafe"],
    }
    matcher.master_norms = {
        "Kinky Friedman": {"kinkyfriedman"},
        "Lone Star Cafe": {"lonestarcafe"},
    }
    return matcher


def _write_kinky_setlist(tmp_path):
    (tmp_path / "venues.txt").write_text("Lone Star Cafe\n", encoding="utf-8")
    setlist = tmp_path / "Kinky Friedman Lone Star Cafe.txt"
    setlist.write_text(
        "Kinky Friedman\n"
        "Lone Star Cafe, New York, NY\n"
        "Early 1980s (exact date unknown - see notes below)\n\n"
        "NBC Country Sessions #55\n"
        "Hosted by Dan Daniel\n\n"
        "01. Country Sessions #55 Promo - Dan Daniel\n"
        "02. Country Sessions #55 Intro and Interview - Dan Daniel Kinky Friedman\n"
        "03. Jambalaya\n",
        encoding="utf-8",
    )
    return setlist


def _config(tmp_path):
    return SimpleNamespace(
        compliant=False,
        tlo_dbs_dir=str(tmp_path),
        as_is_artist_name=False,
    )


def _record(setlist, artist="Lone Star Cafe"):
    return ShowMetadata(
        group_number=1,
        main_dir_name="Kinky Friedman 1980s Lone Star Cafe NYC",
        main_dir_path=r"d:\\x\\F\\Friedman, Kinky\\Kinky Friedman 1980s Lone Star Cafe NYC",
        setlist_file=str(setlist),
        music_file_count=36,
        artist=artist,
    )


def test_build382_structured_unlabeled_header_returns_artist_and_location(tmp_path):
    import tlo_setlist_metadata_lookup as metadata

    setlist = _write_kinky_setlist(tmp_path)
    result = metadata.extract_setlist_venue_location(str(setlist), str(tmp_path))

    assert result.artist == "Kinky Friedman"
    assert result.artist_source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
    assert result.artist_confidence >= 88
    assert result.venue == "Lone Star Cafe"
    assert result.city == "New York"
    assert result.region == "NY"
    assert result.location == "New York NY"


def test_build382_db_confirmed_structured_artist_overrides_weak_subdirectory_artist(tmp_path):
    import tlo_phase23_v2 as phase

    setlist = _write_kinky_setlist(tmp_path)
    record = _record(setlist)
    evidence = {"artist": [Candidate("Lone Star Cafe", "subdirectory:Lone Star Cafe", 60)]}
    observations = []

    changed = phase._apply_setlist_metadata_to_noncompliant_record(
        _config(tmp_path), record, evidence, observations, _matcher()
    )

    assert changed is True
    assert record.artist == "Kinky Friedman"
    assert record.venue == "Lone Star Cafe"
    assert record.location == "New York, NY"
    assert any(
        candidate.source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
        for candidate in evidence["artist"]
    )
    assert any(
        "structured setlist artist overrode weaker path artist: Lone Star Cafe -> Kinky Friedman" in item
        for item in observations
    )


def test_build382_structured_artist_does_not_override_slam(tmp_path):
    import tlo_phase23_v2 as phase

    setlist = _write_kinky_setlist(tmp_path)
    record = _record(setlist, artist="Forced Artist")
    evidence = {"artist": [Candidate("Forced Artist", "slam_override", 100)]}
    observations = []

    phase._apply_setlist_metadata_to_noncompliant_record(
        _config(tmp_path), record, evidence, observations, _matcher()
    )

    assert record.artist == "Forced Artist"
    assert any("did not override existing artist" in item for item in observations)


def test_build382_unmatched_structured_header_cannot_override_path_artist(tmp_path):
    import tlo_phase23_v2 as phase

    (tmp_path / "venues.txt").write_text("Some Venue\n", encoding="utf-8")
    setlist = tmp_path / "unknown.txt"
    setlist.write_text(
        "Unknown Header Name\n"
        "Some Venue, New York, NY\n"
        "January 1, 1984\n\n"
        "01 Song\n",
        encoding="utf-8",
    )
    record = _record(setlist)
    evidence = {"artist": [Candidate("Lone Star Cafe", "subdirectory:Lone Star Cafe", 60)]}
    observations = []

    phase._apply_setlist_metadata_to_noncompliant_record(
        _config(tmp_path), record, evidence, observations, _matcher()
    )

    assert record.artist == "Lone Star Cafe"
    assert any("not found uniquely in Artist DB" in item for item in observations)


def test_build382_structured_setlist_resolves_generic_path_artist_conflict(tmp_path):
    import os
    import tlo_phase23_v2 as phase

    setlist = _write_kinky_setlist(tmp_path)
    show_dir = tmp_path / "Friedman, Kinky" / "Kinky Friedman 1980s Lone Star Cafe NYC"
    show_dir.mkdir(parents=True, exist_ok=True)
    local_setlist = show_dir / "show.txt"
    local_setlist.write_text(setlist.read_text(encoding="utf-8"), encoding="utf-8")

    group = {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": str(local_setlist),
        "music_file_count": 36,
        "setlist_files": [str(local_setlist)],
        "music_dirs": [str(show_dir)],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    config = SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        tlo_dbs_dir=str(tmp_path),
        debug=False,
    )

    record, _dates, unresolved = phase._extract_metadata_for_group(config, group, _matcher())

    assert record.artist == "Kinky Friedman"
    assert record.date == "xxxx-xx-xx"
    assert record.venue == "Lone Star Cafe"
    assert record.location == "New York, NY"
    assert record.show_name == "Kinky Friedman xxxx-xx-xx Lone Star Cafe New York, NY"
    assert not any("artist conflict across subdirectory matches" in item for item in record.conflicts)
    assert not any("artist conflict across subdirectory matches" in item for item in unresolved)
    assert any(
        candidate.source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
        for candidate in record.evidence["artist"]
    )
