"""Build 451: compact the main GUI header and top input rows."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v467"

ROOT = Path(__file__).resolve().parents[2]


def _build_block() -> str:
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("    def _build(self):")
    end = source.index("    def _enable_search_path_drag_drop", start)
    return source[start:end]


def test_build451_tlohome_shares_title_row_immediately_left_of_hamburger():
    block = _build_block()
    assert "header_frame = ttk.Frame(frm)" in block
    assert 'header_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=(4, 4), pady=(0, 1))' in block
    assert 'ttk.Label(header_frame, text=f"TLOHome: {tlohome_display}"' in block
    assert 'self.hamburger_button = ttk.Menubutton(\n            header_frame,' in block
    assert 'row=0, column=1, sticky="e", padx=(6, 4), pady=0' in block
    assert 'self.hamburger_button.grid(row=0, column=2, sticky="e", padx=0, pady=0)' in block
    assert 'text=f"TLOHome: {tlohome_display}", style="Main.TLabel").grid(\n            row=row, column=0, columnspan=3' not in block


def test_build451_search_path_is_single_line_label_with_no_helper_row():
    block = _build_block()
    # Build 461 removed the helper line; Build 463 renames the visible label to Path(s).
    assert 'text="Path(s)"' in block
    assert 'text="Search Path\\n(optional/override)"' not in block
    assert 'search_path_note =' not in block
    assert 'Drag a folder here from File Explorer.' not in block
    assert 'row=row, column=1, columnspan=2, sticky="ew", padx=(6, 4), pady=0' in block


def test_build451_slam_optional_is_inline_and_has_no_helper_row():
    block = _build_block()
    assert 'text="Slam (optional)"' in block
    assert 'ttk.Label(frm, text="(optional/override)"' not in block
    assert 'textvariable=self.vars["search_path_slam_override"], width=33' in block


def test_build451_top_controls_use_compact_vertical_padding():
    block = _build_block()
    assert 'pady=(0, 1)' in block  # header
    assert ').grid(row=row, column=0, sticky="w", padx=(4, 6), pady=0)' in block  # search label
    assert ('self.performance_combo.grid(row=row, column=1, sticky="w", padx=(6, 4), pady=(1, 2))' in block or 'self.performance_combo.grid(row=0, column=1, sticky="w", padx=(0, 4), pady=(0, 1))' in block)
    assert any(marker in block for marker in ('corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(1, 2))', 'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 1))', 'corruption_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(0, 1))'))
    assert any(marker in block for marker in ('pady=(1, 3),', 'pady=(0, 1),', 'pady=(0, 0),', '"pady": (0, 0)'))  # later builds may tighten further
