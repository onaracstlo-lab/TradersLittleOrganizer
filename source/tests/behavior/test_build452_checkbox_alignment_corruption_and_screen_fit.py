"""Build 452: tighter checkbox alignment, horizontal corruption controls, and safe startup sizing."""

from pathlib import Path

import pytest

from tlo_gui_shortcuts import bounded_initial_window_size

pytestmark = pytest.mark.behavior

__version__ = "v458"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build452_multiline_checkbox_indicator_and_grid_are_top_aligned():
    source = _source()
    assert '("Checkbutton.indicator", {"side": "left", "sticky": "n"})' in source
    assert 'anchor="nw"' in source
    assert 'justify="left"' in source
    start = source.index("checkbox_frame = ttk.Frame(")
    block = source[start:source.index("self._lookup_dependency_syncing = False", start)]
    assert 'sticky="nw"' in block
    assert '"pady": (0, 0)' in block or 'pady=(0, 0)' in block
    assert 'padding=(1, 0, 3, 0)' in source


def test_build452_corruption_group_remains_horizontal():
    source = _source()
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    assert 'text="Corrupt files"' in block
    assert 'text="Folder removal"' in block
    assert ('text="Folder corruption\\nthreshold"' in block or 'text="Folder corruption threshold"' in block)
    # Build 452 placed labels over controls in three horizontal columns. Build
    # 453 tightens this to one label/control row; both preserve horizontal order.
    if 'self.corrupt_files_combo.grid(row=1, column=0' in block:
        assert 'self.corrupt_folders_combo.grid(row=1, column=1' in block
        assert 'threshold_value_frame.grid(row=1, column=2' in block
    else:
        assert 'self.corrupt_files_combo.grid(row=0, column=1' in block
        assert 'self.corrupt_folders_combo.grid(row=0, column=3' in block
        assert 'threshold_value_frame.grid(row=0, column=5' in block


def test_build452_initial_window_size_never_exceeds_safe_screen_area():
    assert bounded_initial_window_size(1100, 900, 1920, 1080) == (1100, 900)
    assert bounded_initial_window_size(1800, 1200, 1366, 768) == (1318, 672)
    assert bounded_initial_window_size(2000, 2000, 1280, 1024) == (1232, 928)


def test_build452_main_launch_is_hidden_until_screen_fit_is_applied():
    source = _source()
    main = source[source.index("def main() -> int:"):]
    assert 'root.withdraw()' in main
    assert 'app = App(root, cli_args=cli_args)' in main
    assert 'root.deiconify()' in main
    init = source[source.index("class App:"):source.index("    def _configure_gui_fonts", source.index("class App:"))]
    assert 'self._build()' in init
    assert 'self._fit_initial_window_to_screen()' in init
