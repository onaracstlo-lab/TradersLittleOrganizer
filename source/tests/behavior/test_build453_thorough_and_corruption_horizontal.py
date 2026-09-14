"""Build 453: normalize Thorough row spacing and fully horizontal corruption controls."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v463"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build453_wrapped_tag_copy_spans_rows_without_pushing_thorough_down():
    source = _source()
    start = source.index("checkbox_frame = ttk.Frame(options_frame)")
    block = source[start:source.index("self.dry_run_checkbox = ttk.Checkbutton", start)]
    assert 'checkbox_text = "Thorough Setlist\\nMatching"' in block
    assert 'checkbox_text = "Tag Copy/Delete\\nOriginal"' in block
    assert 'if option.config_field == "tag_copy_and_delete_enabled":' in block
    assert 'grid_options["rowspan"] = 2' in block
    assert '"pady": (0, 0)' in block


def test_build453_corruption_group_is_one_label_control_row_below_options():
    source = _source()
    assert 'options_frame = ttk.Frame(frm)' in source
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    assert 'corruption_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(0, 1))' in block
    assert 'text="Corrupt files"' in block and 'row=0, column=0' in block
    assert 'self.corrupt_files_combo.grid(row=0, column=1' in block
    assert 'text="Folder removal"' in block and 'row=0, column=2' in block
    assert 'self.corrupt_folders_combo.grid(row=0, column=3' in block
    assert 'text="Folder corruption threshold"' in block and 'row=0, column=4' in block
    assert 'threshold_value_frame.grid(row=0, column=5' in block
    assert 'text="Folder corruption\\nthreshold"' not in block


def test_build453_existing_first_open_screen_fit_remains_enabled():
    source = _source()
    assert 'self._fit_initial_window_to_screen()' in source
    main = source[source.index("def main() -> int:"):]
    assert 'root.withdraw()' in main
    assert 'root.deiconify()' in main
