"""Build 444 regression coverage for the compact Corruption Handling group."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v448"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def test_build444_corruption_dropdowns_remain_compact():
    source = _source()
    block = source[source.index('corruption_frame = ttk.LabelFrame'):source.index('self._sync_corruption_threshold_state()')]
    assert "width=20," not in block


def test_build444_threshold_label_is_split_over_two_lines():
    source = _source()
    assert 'text="Folder corruption\\nthreshold"' in source
    assert 'text="Folder corruption threshold"' not in source


def test_build444_corruption_group_uses_compact_spacing():
    source = _source()
    assert 'ttk.LabelFrame(frm, text="Corruption Handling", padding=' in source
    assert 'corruption_frame.grid(row=row, column=0, columnspan=2, sticky="w"' in source


def test_build444_normal_info_line_is_hidden_but_validation_errors_remain():
    source = _source()
    assert 'self.option_status_var = tk.StringVar(value="")' in source
    assert 'self.option_status_label.grid_remove()' in source
    assert 'self.option_status_var.set(status_message)' in source
    assert 'Corruption handling: files' not in source
    assert 'option_messages = []' in source
    assert 'Folder corruption threshold must be an integer from 0 through 100' in source
