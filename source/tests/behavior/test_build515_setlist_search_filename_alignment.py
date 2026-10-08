"""Build 515 regression: tlo-search and inventory use identical setlist filename normalization."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import tlo_postprocess as post

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _load_gsi():
    spec = importlib.util.spec_from_file_location("tlo_search_build515", ROOT / "tlo-search.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build515_trailing_parenthetical_dash_matches_inventory_filename():
    gsi = _load_gsi()
    show = "Bob 2015-01-02 Somewhere (pre-fm)"
    expected = "Bob2015-01-02Somewhere(prefm).txt"

    assert gsi.make_setlist_filename_from_show(show) == expected
    assert f"{post._normalized_setlist_base(show)}.txt" == expected


def test_build515_search_preserves_date_dashes_but_strips_other_parenthetical_dashes():
    gsi = _load_gsi()
    assert gsi.make_setlist_filename_from_show("Bob 2015-01-02 Somewhere (pre-fm)") == "Bob2015-01-02Somewhere(prefm).txt"
    assert gsi.make_setlist_filename_from_show("Bob 2015-01-02 Somewhere (pre fm)") == "Bob2015-01-02Somewhere(prefm).txt"
