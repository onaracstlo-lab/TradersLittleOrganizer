"""Build 448 regressions for simpler Thorough status and further GUI compaction."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v448"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def _load_gui_module():
    from tests import _legacy_suite as legacy
    return legacy._load_local_module("tlo-ggi.py", "tlo_ggi_build448")


def test_build448_thorough_has_no_info_line_without_enabled_online_sources():
    gui = _load_gui_module()
    assert gui._thorough_setlist_info_message(
        thorough=True,
        etree_enabled=False,
        setlistfm_enabled=False,
        setlistfm_upgrade=False,
    ) == ""


def test_build448_thorough_info_is_plain_and_only_names_enabled_online_sources():
    gui = _load_gui_module()
    etree = gui._thorough_setlist_info_message(
        thorough=True,
        etree_enabled=True,
        setlistfm_enabled=False,
        setlistfm_upgrade=False,
    )
    assert etree == "Thorough Setlist Matching will use etreeDB for additional setlist comparison."

    both = gui._thorough_setlist_info_message(
        thorough=True,
        etree_enabled=True,
        setlistfm_enabled=True,
        setlistfm_upgrade=False,
    )
    assert "will use etreeDB and setlist.fm for additional setlist comparison" in both
    assert "600-ms / 1,400-call limits" in both
    assert "local candidates" not in both


def test_build448_tag_copy_delete_wraps_and_last_checkbox_column_moves_left():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame(frm)"):source.index("self._lookup_dependency_syncing = False")]
    assert 'checkbox_text = "Tag Copy/Delete\\nOriginal"' in block
    assert "padx=(0, 2 if option.gui_col in (0, 1, 2) else 0)," in block
    assert 'self.dry_run_checkbox.grid(row=2, column=3, sticky="w", padx=(0, 0)' in block


def test_build448_search_path_and_slam_are_trimmed_again():
    source = _source()
    assert 'self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=66' in source
    assert 'ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=66' in source
    assert 'width=74, style="Main.TEntry"' not in source
