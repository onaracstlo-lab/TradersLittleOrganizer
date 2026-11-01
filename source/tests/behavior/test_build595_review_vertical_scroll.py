"""Build 595: review dialog scrolls long settings without hiding action buttons."""
import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

pytestmark = [pytest.mark.behavior, pytest.mark.gui]
ROOT = Path(__file__).resolve().parents[2]


def load_gui():
    spec = importlib.util.spec_from_file_location("tlo_main_build595_review", ROOT / "tlo-main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@pytest.mark.parametrize("long_review", [False, True])
def test_review_scrollbar_only_when_needed_and_buttons_stay_visible(long_review):
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No graphical display: {exc}")
    root.geometry("100x100+0+0")
    root.update_idletasks()
    gui = load_gui()
    all_lines = [f"Setting {number:03d}: value" for number in range(90)]
    lines = all_lines if long_review else all_lines[:3]
    lines += ["Original files may be changed: Yes"]
    seen = {}

    def inspect_and_close():
        dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        dialog.update_idletasks()
        widgets = list(descendants(dialog))
        canvas = next(w for w in widgets if isinstance(w, tk.Canvas))
        scrollbar = next(w for w in widgets if isinstance(w, ttk.Scrollbar))
        labels = [w for w in widgets if isinstance(w, ttk.Label)]
        buttons = [w for w in widgets if isinstance(w, ttk.Button)]
        text = '\n'.join(str(w.cget('text')) for w in labels)
        assert lines[0] in text and lines[-1] in text
        assert 'Dry Run is non-destructive' in text
        assert len(buttons) >= 2
        assert (scrollbar.winfo_manager() == 'grid') is long_review
        first, last = canvas.yview()
        if long_review:
            assert last < 1
            canvas.yview_moveto(1.0)
            dialog.update_idletasks()
            assert canvas.yview()[1] == pytest.approx(1.0)
        else:
            assert first == pytest.approx(0.0)
            assert last == pytest.approx(1.0)
        start_button = next(b for b in buttons if str(b.cget('text')) == 'Start')
        assert start_button.winfo_rooty() + start_button.winfo_height() <= dialog.winfo_rooty() + dialog.winfo_height()
        start_button.invoke()
        seen['clicked'] = True

    root.after(150, inspect_and_close)
    try:
        result = gui._show_operation_review(root, title='Review Test', lines=lines)
        assert seen.get('clicked')
        assert result is True
    finally:
        root.destroy()


def test_review_go_back_does_not_start():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No graphical display: {exc}")
    root.geometry("100x100+0+0")
    root.update_idletasks()
    gui = load_gui()

    def close():
        dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        dialog.update_idletasks()
        next(w for w in descendants(dialog) if isinstance(w, ttk.Button) and str(w.cget('text')) == 'Go Back').invoke()

    root.after(100, close)
    try:
        assert gui._show_operation_review(root, title='Review Test', lines=['Path(s): c:\\Music']) is False
    finally:
        root.destroy()


def test_preview_button_is_accessible_below_long_review():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No graphical display: {exc}")
    root.geometry('100x100+0+0')
    root.update_idletasks()
    gui = load_gui()
    called = []

    def inspect():
        dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        dialog.update_idletasks()
        buttons = [w for w in descendants(dialog) if isinstance(w, ttk.Button)]
        preview = next(w for w in buttons if str(w.cget('text')) == 'Preview Changes')
        assert preview.winfo_rooty() + preview.winfo_height() <= dialog.winfo_rooty() + dialog.winfo_height()
        preview.invoke()
        next(w for w in buttons if str(w.cget('text')) == 'Go Back').invoke()

    root.after(150, inspect)
    try:
        assert gui._show_operation_review(
            root, title='Review Test', lines=['A: B'] * 80,
            preview_callback=lambda dialog: called.append(dialog),
        ) is False
        assert len(called) == 1
    finally:
        root.destroy()
