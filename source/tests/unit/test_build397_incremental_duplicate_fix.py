"""Regression tests for incremental Add Shows duplicate artist validation."""

__version__ = "v421"

from types import SimpleNamespace

import pytest

import tlo_inventory_update as U
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.unit


def _matcher_with_phish_and_dead():
    matcher = ArtistMatcher(db_path="test")
    matcher.exact_map = {
        "phish": {"Phish"},
        "grateful dead": {"Grateful Dead"},
        "gd": {"Grateful Dead"},
    }
    matcher.master_aliases = {
        "Phish": ["Phish"],
        "Grateful Dead": ["Grateful Dead", "GD"],
    }
    matcher.master_norms = {
        "Phish": {"phish"},
        "Grateful Dead": {"gratefuldead", "gd"},
    }
    return matcher


def test_incremental_duplicate_does_not_accept_date_from_folder_as_artist(tmp_path):
    U.write_bootlist(
        str(tmp_path),
        [{"Show": "Grateful Dead 1977-05-08 Barton Hall Ithaca NY", "VolumePath": "E:/Music/GD"}],
    )
    config = SimpleNamespace(TLOHome=str(tmp_path), compliant=False)
    record = SimpleNamespace(
        artist="Phish",
        date="1977-05-08",
        show_name="Phish 1977-05-08 Some Venue",
    )

    matches = U.find_potential_duplicate_rows_for_folder(
        config,
        "/incoming/1977-05-08",
        record,
        _matcher_with_phish_and_dead(),
    )

    assert matches == []


def test_duplicate_artist_matching_is_token_bounded_not_arbitrary_substring():
    assert U._show_matches_any_artist_value(
        "Hayes Carll 2008-05-10 Continental Club",
        ["Yes"],
    ) is False
    assert U._show_matches_any_artist_value(
        "Grateful Dead 1977-05-08 Barton Hall",
        ["Grateful Dead"],
    ) is True


def test_extra_show_and_folder_probes_only_contribute_db_validated_artists():
    matcher = _matcher_with_phish_and_dead()
    values = U._artist_values_for_duplicate_check(
        "Phish",
        matcher,
        ["1977-05-08", "Grateful Dead 1977-05-08 Barton Hall"],
    )

    normalized = {U.normalized_compare_value(value) for value in values}
    assert "1977 05 08" not in normalized
    assert "grateful dead 1977 05 08 barton hall" not in normalized
    assert "phish" in normalized
    assert "grateful dead" in normalized


def test_artist_and_date_still_match_known_alias_on_same_show(tmp_path):
    U.write_bootlist(
        str(tmp_path),
        [{"Show": "Grateful Dead 1977-05-08 Barton Hall", "VolumePath": "E:/Music/GD"}],
    )
    rows = U.find_potential_duplicate_rows(
        str(tmp_path),
        "GD",
        "1977-05-08",
        artist_matcher=_matcher_with_phish_and_dead(),
    )
    assert [row["Show"] for row in rows] == ["Grateful Dead 1977-05-08 Barton Hall"]
