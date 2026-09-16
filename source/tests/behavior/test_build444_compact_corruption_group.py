"""Build 444 regression coverage for the compact Corruption Handling group."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v468"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build444_corruption_dropdowns_remain_compact_under_current_layout():
    source = _source()
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    corrupt_block = block[block.index('self.corrupt_files_combo = ttk.Combobox'):block.index('self.corrupt_files_combo.grid')]
    folder_block = block[block.index('self.corrupt_folders_combo = ttk.Combobox'):block.index('self.corrupt_folders_combo.grid')]
    # Build 456 trims the later widening while keeping Corrupt files wider than Folder removal.
    assert "width=18," in corrupt_block
    assert "width=15," in folder_block
    assert "width=16," not in block

def test_build444_threshold_label_stays_compact():
    source = _source()
    # Build 444 used a two-line label. Build 453 intentionally returns it to
    # one line because the entire corruption group is now one horizontal strip.
    assert (
        'text="Folder corruption\\nthreshold"' in source
        or 'text="Folder corruption threshold"' in source
    )


def test_build444_corruption_group_uses_compact_spacing():
    source = _source()
    assert 'ttk.LabelFrame(frm, text="Corruption Handling", padding=' in source
    assert (
        'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w"' in source
        or 'corruption_frame.grid(row=row, column=0, columnspan=3, sticky="ew"' in source
    )


def test_build444_normal_info_line_is_hidden_but_validation_errors_remain():
    source = _source()
    assert 'self.option_status_var = tk.StringVar(value="")' in source
    assert 'self.option_status_label.grid_remove()' in source
    assert 'self.option_status_var.set(status_message)' in source
    assert 'Corruption handling: files' not in source
    assert 'option_messages = []' in source
    assert 'Folder corruption threshold must be an integer from 0 through 100' in source
