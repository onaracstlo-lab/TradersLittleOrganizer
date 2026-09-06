"""Build 392 regressions for terminal ``Band`` Artist DB fallback."""

__version__ = "v440"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _matcher(mapping):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for term, masters in mapping.items():
        values = set(masters if isinstance(masters, (list, tuple, set)) else [masters])
        matcher.exact_map[term.casefold()] = values
        for master in values:
            matcher.master_aliases.setdefault(master, [master, term])
            matcher.master_norms.setdefault(master, {"".join(ch for ch in master.casefold() if ch.isalpha())})
    return matcher


def test_terminal_band_full_db_match_still_wins_before_stripped_fallback():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({
        "Example Band": "Example Band",
        "Example": "Different Example Master",
    })
    assert lookup_artist_master_with_status("Example Band", matcher) == ("matched", ["Example Band"])


def test_terminal_band_no_match_retries_without_band_and_returns_db_master():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Marshall Tucker": "The Marshall Tucker Band"})
    assert lookup_artist_master_with_status("Marshall Tucker Band", matcher) == (
        "matched",
        ["The Marshall Tucker Band"],
    )


def test_terminal_band_fallback_is_case_insensitive_and_article_aware():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Foo": "The Foo Band"})
    assert lookup_artist_master_with_status("The Foo bAnD", matcher) == ("matched", ["The Foo Band"])


def test_band_word_not_at_end_does_not_trigger_fallback():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Horses": "Horses"})
    assert lookup_artist_master_with_status("Band of Horses", matcher) == ("no_match", [])


def test_terminal_band_ambiguous_stripped_lookup_is_not_promoted():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": ["Example One", "Example Two"]})
    assert lookup_artist_master_with_status("Example Band", matcher) == ("no_match", [])


def test_path_artist_resolution_uses_master_from_terminal_band_fallback():
    import tlo_phase23_v2 as phase

    matcher = _matcher({"Marshall Tucker": "The Marshall Tucker Band"})
    path = os.path.join(os.sep, "music", "Marshall Tucker Band", "1980-01-01 Venue City NY")
    group = {
        "group_number": 1,
        "main_dir_name": os.path.basename(path),
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [path],
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
        tlo_dbs_dir="",
    )
    artist = phase._resolve_artist_from_subdirs(group, matcher, {}, [], config=config)
    assert artist == "The Marshall Tucker Band"
