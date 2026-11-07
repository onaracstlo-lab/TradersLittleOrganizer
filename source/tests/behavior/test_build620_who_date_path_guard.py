"""Build 620: do not mine artist names from disc titles or date-tail venues."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior


SHOWS = (
    ("1974", "who1974-05-18.sbd", "1974-05-18"),
    ("1974", "who1974-06-14.flac16 New York, NY - Madison Square Garden", "1974-06-14"),
    ("1997", "who1997-07-23.flac16 Milwaukee, WI - Marcus Amphitheater (aud)", "1997-07-23"),
    ("2000", "who2000-07-09.flac16 Wantagh, NY - Jones Beach Amphitheater (sbd)", "2000-07-09"),
    ("2008", "who2008-11-13.flac16 Osaka, Japan - Castle Hall (2 aud-m matrix)", "2008-11-13"),
)


def _matcher():
    # Additional artists intentionally collide with the SONG titles and
    # place/venue strings. They are not the performer of these dated folders.
    names = (
        "Who", "Love", "Soccer Rock", "New York", "Madison", "Marcus",
        "Jones Beach", "Osaka", "Castle", "Milwaukee",
    )
    matcher = ArtistMatcher("")
    matcher.exact_map = {name.lower(): {name} for name in names}
    matcher.exact_map["who, the"] = {"Who"}
    matcher.exact_map["the who"] = {"Who"}
    matcher.master_aliases = {name: [name] for name in names}
    matcher.master_aliases["Who"] = ["Who", "Who, The", "The Who"]
    matcher.master_norms = {name: {name.lower().replace(" ", "")} for name in names}
    return matcher


def _config(tmp_path, compliant=False):
    return SimpleNamespace(
        compliant=compliant, current_slam="", current_volume_label="",
        as_is_artist_name=False, compliant_artist_mode="master",
        etree_lookup=False, setlistfm_lookup=False,
        tlo_dbs_dir=str(tmp_path), TLOHome=str(tmp_path), debug=False,
    )


def _group(folder: Path):
    return dict(
        group_number=1, main_dir_name=folder.name, main_dir_path=str(folder),
        music_dirs=[str(folder)], music_files=[str(folder / "01.flac")],
        music_file_count=1, setlist_file="", setlist_files=[],
        flac_tag_samples=[], flac_tag_artist_values=[], flac_tag_album_values=[],
        flac_tag_albumartist_values=[], flac_tag_date_values=[],
    )


def _path(tmp_path, year, folder_name, disc=None):
    folder = tmp_path / "xx" / "W" / "Who, The" / year / folder_name
    if disc:
        folder = folder / disc
    folder.mkdir(parents=True)
    return folder


@pytest.mark.parametrize("year,folder,date", SHOWS)
def test_who_artist_and_complete_date_even_if_venue_is_not_known(tmp_path, year, folder, date):
    path = _path(tmp_path, year, folder)
    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(tmp_path), _group(path), _matcher(),
    )
    assert record.artist == "Who"
    assert record.date == date
    assert not record.conflicts
    assert not unresolved
    assert record.show_name.startswith(f"Who {date}")
    assert "flac16" not in (record.venue + " " + record.city).lower()


@pytest.mark.parametrize("disc", ["Disc1 - Soccer Rock", "Disc2 - Love Rain O'er Me"])
def test_who_part_titles_do_not_produce_competing_db_artists(tmp_path, disc):
    path = _path(tmp_path, "1974", "who1974-05-18.sbd", disc)
    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(tmp_path), _group(path), _matcher(),
    )
    assert (record.artist, record.date) == ("Who", "1974-05-18")
    assert not record.conflicts
    assert not unresolved


def test_disc_descriptor_is_not_independent_artist_without_parent(tmp_path):
    path = tmp_path / "Disc2 - Love Rain O'er Me"
    path.mkdir()
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), _matcher(), evidence, conflicts,
    )
    assert artist == ""
    assert conflicts == []


def test_real_short_artist_in_nearby_dated_folder_still_conflicts(tmp_path):
    # Existing Build 606 protection: a different real artist with a short
    # date prefix closer to audio must not be silently ignored.
    path = tmp_path / "Who, The" / "ab1973-08-24"
    path.mkdir(parents=True)
    matcher = _matcher()
    matcher.exact_map["ab"] = {"AB"}
    matcher.master_aliases["AB"] = ["AB"]
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), matcher, evidence, conflicts,
    )
    assert artist == ""
    assert conflicts


def test_full_different_artist_directory_remains_conflict(tmp_path):
    path = tmp_path / "Love" / "Who, The" / "1974" / "who1974-05-18.sbd"
    path.mkdir(parents=True)
    evidence, conflicts = {}, []
    artist = phase._resolve_artist_from_subdirs(
        _group(path), _matcher(), evidence, conflicts,
    )
    assert artist == ""
    assert conflicts


def test_sibling_part_aggregation_stays_independent_of_artist_tags(tmp_path):
    parent = _path(tmp_path, "1974", "who1974-05-18.sbd")
    parts = [parent / "Disc1 - Soccer Rock", parent / "Disc2 - Love Rain O'er Me"]
    for part in parts:
        part.mkdir(parents=True)
    entries = [dict(music_dir=str(part)) for part in parts]
    # The date-bearing parent is the root, and the two named Disc children
    # form a coherent 1..2 sequence regardless of audio tags.
    info = phase._dated_described_part_sibling_info(entries)
    assert len(info) == 2
    assert {row["main_dir_path"] for row in info.values()} == {str(parent)}


def test_recognize_exact_artist_component_and_artist_title_separately():
    hits, collision = phase._db_backed_artist_hits_for_path_part("Who, The", _matcher())
    assert hits == [("Who", "Who, The")]
    assert collision == []
    # Love is still an actual artist when standing alone.
    assert phase._db_backed_artist_hits_for_path_part("Love", _matcher())[0] == [("Love", "Love")]
