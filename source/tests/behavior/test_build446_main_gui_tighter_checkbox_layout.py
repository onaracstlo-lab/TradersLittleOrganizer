"""Build 446 regression coverage for the tighter main-window checkbox layout."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v446"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build446_checkbox_block_moves_left_without_changing_grid_coordinates():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame(frm)"):source.index("self._lookup_dependency_syncing = False")]
    assert "padx=(8, 0)," in block
    assert "padx=(18, 0)," not in block
    assert "row=option.gui_row," in block
    assert "column=option.gui_col," in block


def test_build446_checkbox_columns_use_tighter_horizontal_spacing():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame(frm)"):source.index("self._lookup_dependency_syncing = False")]
    assert "padx=(2, 12 if option.gui_col in (0, 1, 2) else 2)," in block
    assert "24 if option.gui_col" not in block
    assert 'self.dry_run_checkbox.grid(row=2, column=3, sticky="w", padx=(2, 2)' in block


def test_build446_main_path_entries_are_narrower_to_reduce_natural_window_width():
    source = _source()
    assert 'self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=86' in source
    assert 'ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=86' in source
    assert 'width=92, style="Main.TEntry"' not in source
