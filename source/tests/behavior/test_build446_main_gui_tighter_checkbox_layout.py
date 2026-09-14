"""Build 446 regression coverage for the tighter main-window checkbox layout."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v461"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build446_checkbox_block_moves_left_without_changing_grid_coordinates():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame("):source.index("self._lookup_dependency_syncing = False")]
    assert "padx=(0, 0)," in block
    assert "padx=(18, 0)," not in block
    assert ("row=option.gui_row," in block or '"row": option.gui_row' in block)
    assert ("column=option.gui_col," in block or '"column": option.gui_col' in block)


def test_build446_checkbox_columns_use_tighter_horizontal_spacing():
    source = _source()
    block = source[source.index("checkbox_frame = ttk.Frame("):source.index("self._lookup_dependency_syncing = False")]
    assert any(marker in block for marker in ("padx=(0, 2 if option.gui_col in (0, 1, 2) else 0),", "padx=(0, 1 if option.gui_col in (0, 1, 2) else 0),", '"padx": (0, 1 if option.gui_col in (0, 1, 2) else 0)'))
    assert "24 if option.gui_col" not in block
    assert any(marker in block for marker in ('self.dry_run_checkbox.grid(row=2, column=3, sticky="w", padx=(0, 0)', 'self.dry_run_checkbox.grid(row=2, column=3, sticky="nw", padx=(0, 0)'))


def test_build446_main_path_entries_are_narrower_to_reduce_natural_window_width():
    source = _source()
    assert 'self.search_path_entry = ttk.Entry(frm, textvariable=self.vars["search_path_override"], width=66' in source
    assert 'ttk.Entry(frm, textvariable=self.vars["search_path_slam_override"], width=33' in source
    assert 'width=92, style="Main.TEntry"' not in source
