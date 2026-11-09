"""Build 622: do not turn taping descriptors or inverted artists into cities."""
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior


def _matcher():
    matcher = ArtistMatcher(db_path="")
    aliases = {
        "Grateful Dead": ["Grateful Dead"],
        "Bob Dylan": ["Bob Dylan"],
        "Jethro Tull": ["Jethro Tull"],
        "Phish": ["Phish"],
        "The Kinks": ["The Kinks", "Kinks", "Kinks, The"],
        "The Band": ["The Band", "Band", "Band, The"],
        "John Smith": ["John Smith", "Smith", "Smith, John"],
    }
    matcher.master_aliases = aliases
    matcher.exact_map = {alias.casefold(): {master} for master, names in aliases.items() for alias in names}
    matcher.master_norms = {
        master: {"".join(c for c in alias.casefold() if c.isalnum()) for alias in names}
        for master, names in aliases.items()
    }
    return matcher


def _parse(name, tmp_path, matcher=None):
    folder = tmp_path / name
    folder.mkdir()
    config = SimpleNamespace(
        compliant=False, current_slam="", current_volume_label="", as_is_artist_name=False,
        compliant_artist_mode="master", etree_lookup=False, setlistfm_lookup=False,
        TLOHome=str(tmp_path), tlo_dbs_dir=str(tmp_path), debug=False,
    )
    group = {
        "group_number": 1, "main_dir_name": name, "main_dir_path": str(folder),
        "setlist_file": "", "setlist_files": [], "music_dirs": [str(folder)],
        "music_file_count": 1, "flac_tag_samples": [], "flac_tag_artist_values": [],
        "flac_tag_album_values": [], "flac_tag_albumartist_values": [], "flac_tag_date_values": [],
    }
    return phase._extract_metadata_for_group(config, group, matcher or _matcher())[0]


@pytest.mark.parametrize("artist,descriptor,date", [
    ("Grateful Dead", "Soundboard", "1977-05-08"),
    ("Grateful Dead", "Matrix", "1977-05-08"),
    ("Bob Dylan", "Rehearsals", "1975-10-21"),
    ("Bob Dylan", "Outtakes", "1965-06-15"),
    ("Jethro Tull", "Bootleg", "2007-02-04"),
    ("Phish", "Encore", "1997-11-22"),
    ("Phish", "Remaster", "1997-11-22"),
])
def test_descriptors_never_become_cities(tmp_path, artist, descriptor, date):
    record = _parse(f"{artist}, {descriptor} {date}", tmp_path)
    assert record.city.casefold() != descriptor.casefold()
    assert not any("guarded Artist, City Date fallback" in text for text in record.observations)


@pytest.mark.parametrize("folder,unexpected", [
    ("Kinks, The 1972-03-02", "The"),
    ("Band, The 1970-05-01", "The"),
    ("Smith, John 1999-01-01", "John"),
])
def test_inverted_artist_name_not_city(tmp_path, folder, unexpected):
    record = _parse(folder, tmp_path)
    assert record.city != unexpected
    assert not any("guarded Artist, City Date fallback" in text for text in record.observations)


def test_known_city_without_venue_remains_supported(tmp_path):
    record = _parse("Jethro Tull, Derby 2007-02-04", tmp_path)
    assert (record.artist, record.date, record.city, record.venue) == (
        "Jethro Tull", "2007-02-04", "Derby", "",
    )


def test_optional_city_reference_is_accepted(tmp_path):
    (tmp_path / "cities.csv").write_text("city^region^country^aliases\nWorcester^MA^US^\n", encoding="utf-8")
    record = _parse("Bob Dylan, Worcester 1975-10-21", tmp_path)
    assert record.city == "Worcester"
    assert record.venue == ""


def test_unknown_capitalized_word_requires_city_evidence(tmp_path):
    record = _parse("Bob Dylan, Imaginaryville 1975-10-21", tmp_path)
    assert record.city != "Imaginaryville"
