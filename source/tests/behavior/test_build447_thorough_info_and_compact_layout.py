"""Build 448 regression coverage for Thorough info accuracy and tighter main-window layout."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v461"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def _load_gui_module():
    from tests import _legacy_suite as legacy
    return legacy._load_local_module("tlo-ggi.py", "tlo_ggi_build447")


def test_build447_thorough_info_does_not_claim_etreedb_when_unchecked():
    gui = _load_gui_module()
    message = gui._thorough_setlist_info_message(
        thorough=True,
        etree_enabled=False,
        setlistfm_enabled=False,
        setlistfm_upgrade=False,
    )
    assert message == ""
    assert "etreeDB" not in message
    assert "setlist.fm candidates" not in message


def test_build447_thorough_info_never_claims_unselected_sources_under_current_policy():
    gui = _load_gui_module()
    etree_only = gui._thorough_setlist_info_message(
        thorough=True, etree_enabled=True, setlistfm_enabled=False, setlistfm_upgrade=False
    )
    assert etree_only == ""

    slow_setlistfm = gui._thorough_setlist_info_message(
        thorough=True, etree_enabled=True, setlistfm_enabled=True, setlistfm_upgrade=False
    )
    assert "setlist.fm" in slow_setlistfm
    assert "600-ms / 1,400-call limits" in slow_setlistfm
    assert "etreeDB" not in slow_setlistfm

    upgraded = gui._thorough_setlist_info_message(
        thorough=True, etree_enabled=True, setlistfm_enabled=True, setlistfm_upgrade=True
    )
    assert upgraded == ""

def test_build447_thorough_checkbox_wraps_without_changing_registry_label():
    source = _source()
    assert 'checkbox_text = "Thorough Setlist\\nMatching"' in source

    from tlo_options import OPTIONS
    option = next(item for item in OPTIONS if item.config_field == "thorough_setlist_matching")
    assert option.gui_label == "Thorough Setlist Matching"


def test_build447_checkbox_block_and_columns_shift_farther_left():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame("):source.index("self._lookup_dependency_syncing = False")]
    assert "padx=(0, 0)," in block
    assert any(marker in block for marker in ("padx=(0, 2 if option.gui_col in (0, 1, 2) else 0),", "padx=(0, 1 if option.gui_col in (0, 1, 2) else 0),", '"padx": (0, 1 if option.gui_col in (0, 1, 2) else 0)'))
    assert "padx=(8, 0)," not in block
    assert "12 if option.gui_col" not in block


def test_build447_search_path_and_slam_are_shorter():
    source = _source()
    assert 'self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=66' in source
    assert 'ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=33' in source
    assert 'width=86, style="Main.TEntry"' not in source
