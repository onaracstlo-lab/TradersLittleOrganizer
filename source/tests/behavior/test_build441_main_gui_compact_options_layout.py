"""Build 441 regression coverage for the compact main-GUI options layout."""

from pathlib import Path

import pytest

from tlo_options import GUI_CHECKBOX_OPTIONS, OPTIONS_BY_FIELD


pytestmark = pytest.mark.behavior

__version__ = "v446"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build441_performance_mode_combo_is_narrower():
    source = _source()
    assert 'values=("gentle", "balanced", "fast", "extreme")' in source
    assert "width=10," in source
    assert "width=18," not in source


def test_build441_checkbox_block_sits_right_of_three_performance_controls():
    source = _source()
    assert "performance_options_row = row" in source
    assert "row=performance_options_row," in source
    assert "column=2," in source
    assert "rowspan=3," in source
    assert 'sticky="nw",' in source


def test_build441_checkbox_internal_layout_is_unchanged():
    expected = {
        "etree_lookup": (0, 0),
        "compliant": (0, 1),
        "tag_during_inventory": (0, 2),
        "artist_in_album": (0, 3),
        "setlistfm_lookup": (1, 0),
        "rename_compliantly": (1, 1),
        "tag_copy_during_inventory": (1, 2),
        "convert_shn": (1, 3),
        "setlistfm_upgrade": (2, 0),
        "as_is_artist_name": (2, 1),
        "tag_copy_and_delete_enabled": (2, 2),
        "thorough_setlist_matching": (3, 0),
    }
    assert len(GUI_CHECKBOX_OPTIONS) == len(expected)
    for field, coordinates in expected.items():
        option = OPTIONS_BY_FIELD[field]
        assert (option.gui_row, option.gui_col) == coordinates

    # Dry run remains in its existing fourth-column slot.
    assert "self.dry_run_checkbox.grid(row=2, column=3" in _source()
