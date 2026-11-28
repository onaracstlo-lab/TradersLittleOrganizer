"""Verified alphanumeric trading shorthand and non-identifying media tails."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import load_artist_matcher
from tlo_phase23_v2 import _extract_metadata_for_group
from tlo_rename_safety import safe_rename_target, shorthand_artist_prefix
from tlo_tag_lib import prepare_inventory_tagging_target

pytestmark = pytest.mark.behavior

ARTIST = "Robert Walter's 20th Congress"
DATE = "2002-03-24"
SOURCE = "rw2c2002-03-24.aud.flac16"
TARGET = f"{ARTIST} {DATE} Stella Blue Asheville, NC"
DB = Path(__file__).resolve().parents[2] / "TLO_DBs"
SETLIST = """Robert Walter's 20th Congress
March 24, 2002
Stella Blue, Asheville, NC

Source:   B&K 4022 > V2 > A/D1K > Tascam DA-P1  mics in front of Chemy's monitor 2 feet high
Transfer: Tascam DA30mk2 > SmartCard Tascam P2 > WAV (16-bit/44.1kHz) > Traders BIG Helper
Tracking/Mastering: tracked just before each song starts, nothing removed (applause and
                    stage talk kept); no EQ or level changes; FLAC level 8
Checksums: md5 and ffp (FLAC fingerprint) included

Recorded and transferred by Chaffe McIlhenny

t01. Track 01  [9:14]
t02. White  Rust  [5:04]
t03. Track 03  [7:53]
t04. Lonny Smith  [7:18]
t05. Track 05  [7:41]
t06. Boogaloo Boogie  John Patton  [3:58]
t07. Track 07  [6:42]
t08. Track 08  [3:50]
t09. Track 09  [10:42]
t10. Track 10  [11:04]
t11. Cochemea Gastelum  [10:45]
t12. Track 12  [6:52]
t13. Track 13  [7:23]
t14. Track 14  [14:51]
t15. Track 15  [11:59]

Total: 2:05:16
 Robert Walter – electric piano and Hammond B3 organ and bass notes
 Cochemea Gastelum – alto sax, electric sax, and flute
 Chuck Prada – percussio
 George Sluppick - drums
 Chris Stillwell –  not on bass
"""


def _config(tmp_path):
    return SimpleNamespace(compliant=False, current_volume_label="", current_slam="",
                           as_is_artist_name=False, compliant_artist_mode="master",
                           etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(DB),
                           artist_sqlite_db_file=str(DB / "artists.sqlite"),
                           venue_reference_db_file=str(DB / "venues.txt"),
                           TLOHome=str(tmp_path), debug=False, rename_compliantly=True,
                           tag_copy_during_inventory=False)


@pytest.fixture(scope="module")
def matcher(tmp_path_factory):
    return load_artist_matcher(_config(tmp_path_factory.mktemp("artist-home")))


def _fixture(tmp_path, matcher):
    config = _config(tmp_path)
    folder = tmp_path / SOURCE
    folder.mkdir()
    info = folder / "rw2c2002-03-24.txt"
    info.write_text(SETLIST, encoding="utf-8")
    media = [folder / f"rw2c2002-03-24t{i:02d}.flac" for i in range(1, 16)]
    for i, file in enumerate(media):
        file.write_bytes(f"placeholder for track {i}".encode())
    group = dict(group_number=1, main_dir_name=SOURCE, main_dir_path=str(folder),
                 setlist_file=str(info), setlist_files=[str(info)],
                 music_dirs=[str(folder)], music_files=list(map(str, media)),
                 music_file_count=len(media), flac_tag_samples=[], flac_tag_artist_values=[],
                 flac_tag_album_values=[], flac_tag_albumartist_values=[], flac_tag_date_values=[])
    record, _, unresolved = _extract_metadata_for_group(config, group, matcher)
    assert (record.artist, record.date, record.venue, record.location) == (ARTIST, DATE, "Stella Blue", "Asheville, NC")
    assert record.show_name == TARGET
    assert record.verified_rename_prefix == "rw2c"
    assert not unresolved and not record.show_in_conflict
    return config, folder, group, record


def test_user_report_full_setlist_identification_and_real_folder_rename(tmp_path, matcher):
    config, source, group, record = _fixture(tmp_path, matcher)
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    messages = []
    renamed_group, renamed = prepare_inventory_tagging_target(config, group, record, messages.append)
    dest = tmp_path / TARGET
    assert dest.is_dir() and not source.exists()
    assert Path(renamed.main_dir_path) == dest
    assert Path(renamed.original_main_dir_path) == source
    assert {p.name: p.read_bytes() for p in dest.iterdir()} == original
    assert any(line.startswith("RENAME_COMPLIANTLY: ") for line in messages)
    assert not any("RENAME_COMPLIANTLY_SKIP" in line for line in messages)
    again, _, unresolved = _extract_metadata_for_group(config, renamed_group, matcher)
    assert again.show_name == TARGET and not unresolved
    messages.clear()
    prepare_inventory_tagging_target(config, renamed_group, again, messages.append)
    assert dest.is_dir() and not any(line.startswith("RENAME_COMPLIANTLY: ") for line in messages)


@pytest.mark.parametrize("mode", ["copy", "copy-delete", "add-shows"])
def test_other_workflows_use_identical_guard(tmp_path, matcher, mode):
    from tlo_inventory_update import _metadata_to_record_dict, _rename_add_shows_folder_compliantly
    from tlo_tag_lib import prepare_inventory_copy_delete_target
    config, source, group, record = _fixture(tmp_path, matcher)
    pool = tmp_path / "destination"
    pool.mkdir()
    if mode == "add-shows":
        row = _metadata_to_record_dict(record)
        path = _rename_add_shows_folder_compliantly(config, str(source), row)
        target = tmp_path / TARGET
        assert Path(path) == target
    elif mode == "copy-delete":
        config.tag_copy_and_delete_path = str(pool)
        _, record = prepare_inventory_copy_delete_target(config, group, record)
        target = pool / TARGET
        assert Path(record.main_dir_path) == target
    else:
        config.tag_copy_during_inventory = True
        config.tag_copy_destination = str(pool)
        _, record = prepare_inventory_tagging_target(config, group, record)
        target = pool / TARGET
        assert Path(record.main_dir_path) == target
    assert target.is_dir() and len(list(target.glob("*.flac"))) == 15
    assert source.exists() == (mode == "copy")


@pytest.mark.parametrize("suffix", [".aud.flac16", ".sbd.flac16", ".flac16", ".aud.flac", ".flac", ""])
def test_verified_dotted_media_suffixes_are_not_show_names(suffix):
    source = "rw2c" + DATE + suffix
    assert shorthand_artist_prefix(source) == "rw2c"
    assert safe_rename_target(source, TARGET, artist=ARTIST, date=DATE, verified_prefix="rw2c") == (TARGET, "")


@pytest.mark.parametrize("source", [
    "rw2c2002-03-24.aud.flac24",
    "rw2c2002-03-24.aud.1234.flac16",
    "rw2c2002-03-24.aud.taper.flac16",
    "rw2c2002-03-24.aud.flac16 (Late Show)",
    "rw2c2002-03-24.aud.flac16 (16)",
    "rw2c2002-03-24 SBD",
    "rw2c2002-03-25.aud.flac16",
    "fake2002-03-24.aud.flac16",
])
def test_other_identity_and_conflicting_dates_still_protected(source):
    assert not safe_rename_target(source, TARGET, artist=ARTIST, date=DATE, verified_prefix="rw2c")[0]


def test_numeric_alias_requires_unique_db_proof(matcher):
    assert matcher.exact_map["rw2c"] == {ARTIST}
    assert not safe_rename_target(SOURCE, TARGET, artist=ARTIST, date=DATE)[0]
    assert not safe_rename_target(SOURCE, TARGET, artist=ARTIST, date=DATE, verified_prefix="rwtc")[0]


def test_original_parentheticals_must_still_be_preserved():
    source = SOURCE + " (Late Show)"
    target = TARGET + " (Late Show)"
    assert safe_rename_target(source, target, artist=ARTIST, date=DATE, verified_prefix="rw2c") == (target, "")
