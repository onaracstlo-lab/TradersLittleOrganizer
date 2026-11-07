"""Build 619: guarded, post-lookup city-suffix venue inference."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior


def _matcher():
    matcher = ArtistMatcher(db_path="")
    names = ("Lucinda", "Lucinda Williams", "Twiddle", "House of Blues", "The Fillmore")
    matcher.exact_map = {name.casefold(): {name} for name in names}
    matcher.master_aliases = {name: [name] for name in names}
    matcher.master_norms = {name: {"".join(c for c in name.casefold() if c.isalnum())} for name in names}
    return matcher


def _extract(tmp_path: Path, folder: str, *, compliant=False, setlistfm=False, cities=None):
    root = tmp_path / "show"
    root.mkdir(exist_ok=True)
    db_dir = tmp_path / "TLO_DBs"
    db_dir.mkdir(exist_ok=True)
    if cities is not None:
        (db_dir / "cities.csv").write_text(cities, encoding="utf-8")
    config = SimpleNamespace(
        compliant=compliant, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master", etree_lookup=False,
        setlistfm_lookup=setlistfm, venue_reference_db_file=str(db_dir / "venues.txt"),
        tlo_dbs_dir=str(db_dir), TLOHome=str(tmp_path), debug=False,
    )
    group = {
        "group_number": 1, "main_dir_name": folder,
        "main_dir_path": str(root.parent / folder), "setlist_file": "", "setlist_files": [],
        "music_dirs": [str(root)], "music_file_count": 1,
        "flac_tag_samples": [], "flac_tag_artist_values": [],
        "flac_tag_album_values": [], "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    return phase._extract_metadata_for_group(config, group, _matcher())


@pytest.mark.parametrize("folder,venue,city", [
    ("Twiddle at House of Blues Boston 2022-05-08", "House of Blues", "Boston"),
    ("Twiddle Live at The Fillmore Philadelphia 2022-05-08", "The Fillmore", "Philadelphia"),
    ("Twiddle Live at Great American Music Hall San Francisco 2022-05-08", "Great American Music Hall", "San Francisco"),
    ("Twiddle at The Echo Los Angeles 2022-05-08", "The Echo", "Los Angeles"),
    ("Twiddle Live in The Fillmore Denver 2022-05-08", "The Fillmore", "Denver"),
])
def test_unknown_venue_splits_only_with_recognized_right_city(tmp_path, folder, venue, city):
    record, _, problems = _extract(tmp_path, folder)
    assert (record.artist, record.date, record.venue, record.city) == ("Twiddle", "2022-05-08", venue, city)
    assert record.location == city
    assert not record.region and not record.country
    assert not problems
    assert any("medium-confidence right-to-left" in text for text in record.observations)


def test_explicit_state_not_replaced_with_regionless_inference(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at Great American Music Hall San Francisco, CA 2022-05-08")
    assert (record.venue, record.city, record.location) == ("Great American Music Hall", "San Francisco", "San Francisco, CA")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_city_csv_can_extend_but_not_supply_unmentioned_state(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at Small Theater Ithaca 2022-05-08", cities="city^region^country^aliases\nIthaca^NY^USA^\n")
    assert (record.venue, record.city, record.region, record.location) == ("Small Theater", "Ithaca", "", "Ithaca")


def test_city_csv_alias_uses_original_spelling(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at Northern Club NOLA 2022-05-08", cities="city^region^country^aliases\nNew Orleans^LA^USA^NOLA\n")
    assert record.venue == "Northern Club"
    assert record.city == "New Orleans" or record.city == "NOLA"
    assert record.region == "LA" or not record.region


@pytest.mark.parametrize("folder", [
    "Twiddle at Boston Music Hall 2022-05-08",
    "Twiddle at Unknown Hall Unknownville 2022-05-08",
    "Twiddle at The Fillmore New York 2022-05-08",
    "Twiddle at Boston 2022-05-08",
])
def test_ambiguous_or_unrecognized_suffix_not_guessed(tmp_path, folder):
    record, _, _ = _extract(tmp_path, folder)
    assert record.artist == "Twiddle"
    assert record.date == "2022-05-08"
    assert not record.venue and not record.city
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_online_venue_and_location_win_over_inferred_city(tmp_path, monkeypatch):
    def pretend_online(config, record, evidence, observations):
        record.venue, record.city, record.region = "Official Hall", "Cambridge", "MA"
        record.location = "Cambridge, MA"
        observations.append("setlist.fm lookup matched fixture")
        return True
    monkeypatch.setattr(phase, "_apply_setlistfm_lookup_to_record", pretend_online)
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08", setlistfm=True)
    assert (record.venue, record.city, record.location) == ("Official Hall", "Cambridge", "Cambridge, MA")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_city_only_live_in_not_converted_to_venue(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle Live in Boston 2022-05-08")
    assert (record.artist, record.venue, record.city) == ("Twiddle", "", "Boston")


def test_original_lucinda_parse_preserved(tmp_path):
    record, _, _ = _extract(tmp_path, "Lucinda Williams - The Catalyst, Santa Cruz, CA 8-31-07")
    assert record.show_name == "Lucinda Williams 2007-08-31 The Catalyst Santa Cruz, CA"


def test_compliant_unchanged(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08", compliant=True)
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_etree_lookup_precedes_right_to_left_inference(tmp_path, monkeypatch):
    def pretend_etree(config, record, evidence, observations):
        record.venue, record.city, record.region = "Authenticated Venue", "Somerville", "MA"
        record.location = "Somerville, MA"
        return True
    monkeypatch.setattr(phase, "_apply_etree_lookup_to_record", pretend_etree)
    record, _, _ = _extract(tmp_path, "Twiddle Live at House of Blues Boston 2022-05-08")
    assert (record.venue, record.city, record.location) == ("Authenticated Venue", "Somerville", "Somerville, MA")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_selected_setlist_metadata_precedes_inference(tmp_path, monkeypatch):
    def pretend_setlist(config, record, evidence, observations, matcher, conflicts):
        record.venue, record.city, record.region = "Setlist Confirmed Hall", "Brookline", "MA"
        record.location = "Brookline, MA"
    monkeypatch.setattr(phase, "_apply_setlist_metadata_to_noncompliant_record", pretend_setlist)
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08")
    assert (record.venue, record.city, record.location) == ("Setlist Confirmed Hall", "Brookline", "Brookline, MA")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_unrecognized_leading_artist_does_not_use_city_suffix_fallback(tmp_path):
    record, _, _ = _extract(tmp_path, "Unknown Performer at House of Blues Boston 2022-05-08")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)


def test_no_extra_date_or_trailing_album_enables_city_fallback(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08 Deluxe 2023")
    assert not any("medium-confidence right-to-left" in text for text in record.observations)
