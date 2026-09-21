"""Build 484: checkbox display text uses requested capitalization only."""

__version__ = "v484"

from pathlib import Path

import pytest

from tlo_options import OPTIONS_BY_FIELD

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.behavior


def test_build484_main_checkbox_labels_are_exact():
    expected = {
        "etree_lookup": "etreeDB",
        "compliant": "Compliant",
        "tag_during_inventory": "Tag In Place",
        "artist_in_album": "Artist In Album Tag",
        "setlistfm_lookup": "setlist.fm",
        "rename_compliantly": "Rename Compliantly",
        "tag_copy_during_inventory": "Tag Copy",
        "convert_shn": "Convert shn",
        "setlistfm_upgrade": "setlist.fm Upgrade",
        "as_is_artist_name": "As-Is Artist Name",
        "tag_copy_and_delete_enabled": "Tag Copy/Delete Original",
        "thorough_setlist_matching": "Thorough setlist Matching",
        "delete_extra_tags": "Delete Extra Tags",
    }
    assert {field: OPTIONS_BY_FIELD[field].gui_label for field in expected} == expected


def test_build484_wrapped_and_action_specific_checkbox_text_is_exact():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    search_source = (ROOT / "tlo-gsi.py").read_text(encoding="utf-8")

    assert 'checkbox_text = "Thorough setlist\\nMatching"' in source
    assert 'checkbox_text = "Delete Extra\\nTags"' in source
    assert 'text="Dry Run"' in source
    assert 'text="Update Tags"' in source
    assert 'text="Check For Duplicates"' in source
    assert 'label="Auto Update"' in source
    assert 'label="Auto Update"' in search_source
    assert 'text="Deep"' in search_source


def test_build484_checkbox_change_does_not_move_main_checkbox_cells():
    expected_positions = {
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
        "delete_extra_tags": (3, 3),
    }
    assert {
        field: (OPTIONS_BY_FIELD[field].gui_row, OPTIONS_BY_FIELD[field].gui_col)
        for field in expected_positions
    } == expected_positions
