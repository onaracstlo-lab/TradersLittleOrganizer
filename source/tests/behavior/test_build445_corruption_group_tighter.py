"""Build 445 regression coverage for the tighter Corruption Handling group."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v446"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build445_corruption_dropdowns_are_slightly_narrower():
    source = _source()
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    assert block.count("width=15,") == 2
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
    assert 'ttk.LabelFrame(frm, text="Corruption Handling", padding=(4, 2))' in source
    assert 'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=4, pady=(3, 2))' in source
    assert 'text="Folder corruption\\nthreshold"' in source
