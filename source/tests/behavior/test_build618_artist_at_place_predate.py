"""Build 618: anchored leading Artist (Live) at/in Place Date fallback."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
from tlo_phase23_v2 import _extract_metadata_for_group

pytestmark = pytest.mark.behavior


def _matcher():
    matcher = ArtistMatcher(db_path="")
    names = ("Lucinda", "Lucinda Williams", "Williams", "Twiddle", "House of Blues", "Catalyst")
    matcher.exact_map = {name.lower(): {name} for name in names}
    matcher.master_aliases = {name: [name] for name in names}
    matcher.master_norms = {name: {"".join(char for char in name.lower() if char.isalnum())} for name in names}
    return matcher


def _extract(tmp_path: Path, folder: str, *, venues: str = "", compliant: bool = False):
    source = tmp_path / folder
    source.mkdir()
    venue_file = tmp_path / "venues.txt"
    if venues:
        venue_file.write_text(venues, encoding="utf-8")
    config = SimpleNamespace(
        compliant=compliant, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master",
        etree_lookup=False, setlistfm_lookup=False,
        venue_reference_db_file=str(venue_file),
        tlo_dbs_dir=str(tmp_path), TLOHome=str(tmp_path), debug=False,
    )
    group = {
        "group_number": 1, "main_dir_name": folder,
        "main_dir_path": str(source), "setlist_file": "", "setlist_files": [],
        "music_dirs": [str(source)], "music_file_count": 1,
        "flac_tag_samples": [], "flac_tag_artist_values": [],
        "flac_tag_album_values": [], "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    return _extract_metadata_for_group(config, group, _matcher())


def test_lucinda_original_dash_before_date_already_worked(tmp_path):
    record, _, unresolved = _extract(tmp_path, "Lucinda Williams - The Catalyst, Santa Cruz, CA 8-31-07")
    assert record.show_name == "Lucinda Williams 2007-08-31 The Catalyst Santa Cruz, CA"
    assert not unresolved


@pytest.mark.parametrize("name", [
    "Twiddle at House of Blues Boston 2022-05-08",
    "Twiddle Live at House of Blues Boston 2022-05-08",
])
def test_twiddle_at_venue_city_with_known_venue(tmp_path, name):
    record, _, unresolved = _extract(tmp_path, name, venues="House of Blues\n")
    assert (record.artist, record.date, record.venue, record.location) == (
        "Twiddle", "2022-05-08", "House of Blues", "Boston"
    )
    assert record.show_name == "Twiddle 2022-05-08 House of Blues Boston"
    assert not unresolved


def test_build619_city_suffix_inference_supersedes_previous_blank_place_behavior(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08")
    # Build 619: after failed/disabled lookups a recognized city suffix
    # provides a guarded medium-confidence boundary even without venues.txt.
    assert (record.artist, record.date, record.venue, record.location) == (
        "Twiddle", "2022-05-08", "House of Blues", "Boston"
    )


def test_explicit_at_state_anchored(tmp_path):
    record, _, unresolved = _extract(tmp_path, "Twiddle Live at The Catalyst, Santa Cruz, CA 2022-05-08")
    assert record.show_name == "Twiddle 2022-05-08 The Catalyst Santa Cruz, CA"
    assert not unresolved


def test_live_in_city(tmp_path):
    record, _, unresolved = _extract(tmp_path, "Twiddle Live in Boston 2022-05-08")
    assert (record.artist, record.date, record.venue, record.location) == ("Twiddle", "2022-05-08", "", "Boston")
    assert not unresolved


def test_live_in_city_and_state(tmp_path):
    record, _, unresolved = _extract(tmp_path, "Twiddle Live in Santa Cruz, CA 2022-05-08")
    assert (record.artist, record.venue, record.location) == ("Twiddle", "", "Santa Cruz, CA")
    assert not unresolved


def test_longest_artist_wins_over_short_artist(tmp_path):
    record, _, unresolved = _extract(tmp_path, "Lucinda Williams Live at The Catalyst, Santa Cruz, CA 8-31-07")
    assert record.show_name == "Lucinda Williams 2007-08-31 The Catalyst Santa Cruz, CA"
    assert not unresolved


def test_no_embedded_album_date_is_taken_for_performance(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle Live at House of Blues Boston 2022-05-08 Deluxe 2023")
    assert not any("guarded Artist (Live) at/in Place Date fallback" in o for o in record.observations)


def test_no_artist_db_does_not_guess_from_first_words(tmp_path):
    record, _, _ = _extract(tmp_path, "Unknown Performer at House of Blues Boston 2022-05-08", venues="House of Blues\n")
    assert not any("guarded Artist (Live) at/in Place Date fallback" in o for o in record.observations)


def test_compliant_mode_does_not_use_fallback(tmp_path):
    record, _, _ = _extract(tmp_path, "Twiddle at House of Blues Boston 2022-05-08", venues="House of Blues\n", compliant=True)
    assert not any("guarded Artist (Live) at/in Place Date fallback" in o for o in record.observations)
