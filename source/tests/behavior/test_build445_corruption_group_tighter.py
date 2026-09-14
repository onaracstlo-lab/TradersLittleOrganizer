"""Build 445 regression coverage for the tighter Corruption Handling group."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v465"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build445_folder_removal_dropdown_remains_compact_after_later_corrupt_files_widening():
    source = _source()
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    corrupt_block = block[block.index('self.corrupt_files_combo = ttk.Combobox'):block.index('self.corrupt_files_combo.grid')]
    folder_block = block[block.index('self.corrupt_folders_combo = ttk.Combobox'):block.index('self.corrupt_folders_combo.grid')]
    assert "width=18," in corrupt_block
    assert "width=15," in folder_block
    assert "width=16," not in block

def test_build445_percent_is_attached_to_threshold_entry():
    source = _source()
    assert "threshold_value_frame = ttk.Frame(corruption_frame)" in source
    assert 'threshold_value_frame, textvariable=self.vars["corrupt_folder_threshold"], width=5' in source
    assert 'ttk.Label(threshold_value_frame, text="%", style="Main.TLabel")' in source
    assert 'padx=(1, 0)' in source
    assert 'ttk.Label(corruption_frame, text="%"' not in source


def test_build445_corruption_group_padding_is_tighter():
    source = _source()
    assert any(marker in source for marker in ('ttk.LabelFrame(frm, text="Corruption Handling", padding=(4, 2))', 'ttk.LabelFrame(frm, text="Corruption Handling", padding=(4, 1))'))
    # Later GUI compaction may reduce this padding further; Build 445's contract is that
    # the corruption group never regresses to a looser top/bottom gap.
    assert any(
        marker in source
        for marker in (
            'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(3, 2))',
            'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 2))',
            'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(1, 2))',
            'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2))',
            'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 1))',
            'corruption_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4, pady=(0, 1))',
        )
    )
    assert ('text="Folder corruption\\nthreshold"' in source or 'text="Folder corruption threshold"' in source)
