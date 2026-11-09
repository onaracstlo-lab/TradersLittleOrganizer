"""Build 638: one startup INI, Save & Close/Cancel, and no current-session changes."""
import tkinter as tk
from tkinter import messagebox
from unittest import mock

import pytest
import tlo_preferences as prefs


def _setup(tmp_path):
    prefs.load(tmp_path)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display required')
    root.withdraw()
    return root


def _editor(window):
    return next(child for child in window.winfo_children()[1].winfo_children()
                if isinstance(child, tk.Text))


def _button(window, name):
    return next(child for child in window.winfo_children()[-1].winfo_children()
                if child.cget('text') == name)


def test_save_close_updates_disk_only_and_leaves_app_running(tmp_path):
    root = _setup(tmp_path)
    try:
        in_memory_defaults = prefs.load(tmp_path)
        selected_tag = tk.BooleanVar(master=root, value=True)
        selected_path = tk.StringVar(master=root, value='my current operation')
        window = prefs.edit(root, tmp_path)
        assert {_button(window, 'Save & Close'), _button(window, 'Cancel')}
        editor = _editor(window)
        original = editor.get('1.0', 'end-1c')
        assert 'font_size = 0' in original
        editor.delete('1.0', tk.END)
        editor.insert('1.0', original.replace('font_size = 0', 'font_size = 16')
                      .replace('max_workers = 0', 'max_workers = 12'))
        with mock.patch.object(messagebox, 'showinfo') as info:
            _button(window, 'Save & Close').invoke()
        assert not window.winfo_exists()
        assert root.winfo_exists()
        assert selected_tag.get() is True
        assert selected_path.get() == 'my current operation'
        assert in_memory_defaults['main']['max_workers'] == 0
        assert in_memory_defaults['main']['font_size'] == 0
        assert prefs.load(tmp_path)['main']['max_workers'] == 12
        assert prefs.load(tmp_path)['main']['font_size'] == 16
        assert 'Restart' in info.call_args.args[0]
    finally:
        root.destroy()


def test_cancel_discards_edits_without_rewriting_file(tmp_path):
    root = _setup(tmp_path)
    try:
        ini = prefs.path_for(tmp_path)
        before = ini.read_bytes()
        window = prefs.edit(root, tmp_path)
        _editor(window).insert(tk.END, '\n# trial')
        with mock.patch.object(messagebox, 'askyesno', return_value=True) as confirm:
            _button(window, 'Cancel').invoke()
        confirm.assert_called_once()
        assert not window.winfo_exists()
        assert ini.read_bytes() == before
    finally:
        root.destroy()


def test_invalid_save_keeps_editor_open_and_disk_unchanged(tmp_path):
    root = _setup(tmp_path)
    try:
        ini = prefs.path_for(tmp_path)
        before = ini.read_bytes()
        window = prefs.edit(root, tmp_path)
        editor = _editor(window)
        editor.insert(tk.END, '\n[unknown]\nthing = true\n')
        with mock.patch.object(messagebox, 'showerror') as invalid:
            _button(window, 'Save & Close').invoke()
        assert window.winfo_exists()
        invalid.assert_called_once()
        assert ini.read_bytes() == before
        window.destroy()
    finally:
        root.destroy()


def test_unchanged_save_closes_without_rewrite_or_restart_prompt(tmp_path):
    root = _setup(tmp_path)
    try:
        ini = prefs.path_for(tmp_path)
        before = ini.read_bytes()
        window = prefs.edit(root, tmp_path)
        with mock.patch.object(messagebox, 'showinfo') as info:
            _button(window, 'Save & Close').invoke()
        assert not window.winfo_exists()
        assert ini.read_bytes() == before
        info.assert_not_called()
    finally:
        root.destroy()


pytestmark = pytest.mark.behavior
