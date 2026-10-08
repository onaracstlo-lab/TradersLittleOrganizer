"""Build 520: tlo-search uses the inventory filename creator for partial dates."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import tlo_postprocess as post

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_search():
    spec = importlib.util.spec_from_file_location("tlo_search_build520", ROOT / "tlo-search.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _inventory_filename(show: str, artist: str, date: str, venue: str) -> str:
    record = {
        "show_name": show,
        "artist": artist,
        "date": date,
        "venue": venue,
        "location": "",
        "parentheticals": "",
        "album_name": "",
        "descriptor": "",
        "main_dir_path": "",
        "setlist_file": "",
    }
    return f"{post._setlist_base_from_record(record)}.txt"


def test_build520_search_preserves_yyyy_mm_xx_exactly_like_inventory():
    search = _load_search()
    show = "Bob 1973-12-xx Somewhere"
    expected = _inventory_filename(show, "Bob", "1973-12-xx", "Somewhere")

    assert expected == "Bob1973-12-xxSomewhere.txt"
    assert search.make_setlist_filename_from_show(show) == expected
    assert post.setlist_filename_from_show_name(show) == expected


@pytest.mark.parametrize(
    "show,expected",
    [
        ("Artist 2001-04-1x Venue", "Artist2001-04-1xVenue.txt"),
        ("Artist 2001-04-xx Venue", "Artist2001-04-xxVenue.txt"),
        ("Artist 2004-0x-xx Venue", "Artist2004-0x-xxVenue.txt"),
        ("Artist 202x-xx-xx Venue", "Artist202x-xx-xxVenue.txt"),
        ("Artist 19xx-xx-xx Venue", "Artist19xx-xx-xxVenue.txt"),
        ("Artist 20xx-xx-xx Venue", "Artist20xx-xx-xxVenue.txt"),
        ("Artist xxxx-xx-xx Venue", "Artistxxxx-xx-xxVenue.txt"),
    ],
)
def test_build520_search_preserves_supported_partial_date_dashes(show, expected):
    search = _load_search()
    assert search.make_setlist_filename_from_show(show) == expected
    assert post.setlist_filename_from_show_name(show) == expected


def test_build520_search_still_uses_inventory_parenthetical_normalization():
    search = _load_search()
    show = "Bob 1973-12-xx Somewhere (pre-fm)"
    assert search.make_setlist_filename_from_show(show) == "Bob1973-12-xxSomewhere(prefm).txt"
