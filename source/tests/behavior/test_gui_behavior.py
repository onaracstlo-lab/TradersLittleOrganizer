"""Executable Tkinter behavior tests for layout and progress animation."""

__version__ = "v378"

from pathlib import Path

import pytest

tkinter = pytest.importorskip(
    "tkinter",
    reason="Tkinter is required for GUI regression tests",
)
from tkinter import ttk

pytestmark = [pytest.mark.behavior, pytest.mark.gui]


def _load_gui_module():
    from tests import _legacy_suite as legacy
    return legacy._load_local_module("tlo-ggi.py", "tlo_ggi_v375_gui_behavior")


@pytest.fixture
def tk_root():
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        pytest.skip("A graphical display is required for Tkinter GUI behavior tests")
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.destroy()
        except tkinter.TclError:
            pass


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_checkbox_grid_uses_registry_positions_and_dry_run_cell(tk_root, monkeypatch, tmp_path):
    gui = _load_gui_module()
    from tlo_options import GUI_CHECKBOX_OPTIONS

    monkeypatch.setenv("TLOHome", str(tmp_path))
    app = gui.App(tk_root, gui._parse_gui_command_line([]))
    tk_root.update_idletasks()

    actual = {}
    for widget in _descendants(tk_root):
        if isinstance(widget, ttk.Checkbutton):
            text = str(widget.cget("text"))
            if text in {option.gui_label for option in GUI_CHECKBOX_OPTIONS} | {"Dry run"}:
                info = widget.grid_info()
                actual[text] = (int(info["row"]), int(info["column"]))

    expected = {option.gui_label: (option.gui_row, option.gui_col) for option in GUI_CHECKBOX_OPTIONS}
    expected["Dry run"] = (2, 3)
    assert actual == expected


def test_three_progress_bars_receive_shared_interval(tk_root):
    gui = _load_gui_module()

    calls = []

    class RecordingProgressbar(ttk.Progressbar):
        def start(self, interval=None):
            calls.append(interval)

    bars = [RecordingProgressbar(tk_root, mode="indeterminate") for _ in range(3)]
    for bar in bars:
        assert gui._start_activity_indicator(bar) is True

    assert calls == [gui.ACTIVITY_INDICATOR_INTERVAL_MS] * 3
