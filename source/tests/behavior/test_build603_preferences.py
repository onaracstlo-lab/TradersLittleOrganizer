"""Build 603: per-TLOHome GUI defaults, editable preferences, and safe validation."""
from pathlib import Path
import importlib.util
import sys
import tkinter as tk
import tkinter.font as tkfont
from unittest import mock

import pytest

import tlo_preferences as pref
from tlo_options import GUI_CHECKBOX_OPTIONS

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_default_template_has_every_main_checkbox_and_all_window_settings():
    values = pref.parse_text(pref.default_text())
    assert set(option.config_field for option in GUI_CHECKBOX_OPTIONS) <= set(values['main'])
    assert [field for field, value in values['main'].items() if isinstance(value, bool) and value] == ['artist_in_album']
    assert values['main']['performance_mode'] == 'balanced'
    assert values['main']['max_workers'] == 0
    assert values['main']['corrupt_files'] == 'keep'
    assert values['main']['corrupt_folders'] == 'never'
    assert values['main']['corrupt_folder_threshold'] == 100
    assert values['main']['font_size'] == 0
    assert values['search']['deep'] is False
    assert values['manual_updates']['update_tags'] is True
    assert values['add_new_shows']['check_for_duplicates'] is True
    assert '[search]' in pref.default_text()
    assert '[main]' in (ROOT / pref.FILENAME).read_text(encoding='utf-8')


def test_creates_inside_tlohome_preserves_edits_and_existing_auto_update(tmp_path):
    data = pref.load(tmp_path, initial_auto_update=True)
    file_path = tmp_path / pref.FILENAME
    assert file_path.is_file() and data['general']['auto_update'] is True
    custom = file_path.read_text().replace('performance_mode = balanced', 'performance_mode = gentle')
    pref.save_text(tmp_path, custom)
    assert pref.load(tmp_path)['main']['performance_mode'] == 'gentle'
    assert file_path.read_text() == custom


@pytest.mark.parametrize('change', [
    ('max_workers = 0', 'max_workers = no'),
    ('max_workers = 0', 'max_workers = -1'),
    ('font_size = 0', 'font_size = 100'),
    ('performance_mode = balanced', 'performance_mode = power'),
    ('artist_in_album = true', 'artist_in_album = perhaps'),
    ('compliant = false', 'compliant = true\nunknown = true'),
    ('compliant = false', 'compliant = true\ncompliant = false'),
    ('compliant = false', 'compliant = true\nrename_compliantly = true'),
    ('tag_copy_during_inventory = false', 'tag_copy_during_inventory = true\ntag_during_inventory = true'),
    ('setlistfm_lookup = false', 'setlistfm_lookup = true'),
])
def test_invalid_edit_is_not_written(tmp_path, change):
    pref.load(tmp_path)
    path = tmp_path / pref.FILENAME
    old = path.read_text()
    modified = old.replace(*change, 1)
    assert modified != old
    with pytest.raises(ValueError):
        pref.save_text(tmp_path, modified)
    assert path.read_text() == old


def test_rejects_large_file_and_unknown_section(tmp_path):
    pref.load(tmp_path)
    with pytest.raises(ValueError, match='128 KB'):
        pref.save_text(tmp_path, '# oversized\n' + 'x' * (pref.MAX_BYTES + 1))
    with pytest.raises(ValueError, match='Unknown preferences section'):
        pref.save_text(tmp_path, pref.default_text() + '\n[secret]\nfoo = true\n')


def test_preserves_comments_when_auto_update_toggled(tmp_path):
    pref.load(tmp_path)
    pref.set_auto_update(tmp_path, True)
    text = (tmp_path / pref.FILENAME).read_text()
    assert 'auto_update = true' in text
    assert '# Traders Little Organizer startup preferences' in text
    assert pref.load(tmp_path)['general']['auto_update'] is True


def test_explicit_cli_overrides_default_file_values(tmp_path):
    module = _load('tlo_main_gui_prefs_test', 'tlo-main.py')
    args = module._parse_gui_command_line([
        '--TLOHome', str(tmp_path), '--performance-mode', 'fast',
        '--max-workers', '3', '--no-artist-in-album', '--compliant'])
    assert {'performance_mode', 'max_workers', 'artist_in_album', 'compliant'} <= args._explicit_preferences_fields
    defaults = pref.parse_text(pref.default_text())['main']
    defaults['artist_in_album'] = True
    defaults['compliant'] = False
    selected = module._initial_checkbox_values(args, defaults, args._explicit_preferences_fields)
    assert selected['artist_in_album'] is False and selected['compliant'] is True
    assert selected['deep_audio_check'] is False


def test_gui_startup_applies_main_and_search_preferences(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display required')
    root.withdraw()
    try:
        pref.load(tmp_path)
        text = (tmp_path / pref.FILENAME).read_text()
        text = text.replace('performance_mode = balanced', 'performance_mode = gentle')
        text = text.replace('max_workers = 0', 'max_workers = 3')
        text = text.replace('heading_font_size = 0', 'heading_font_size = 18')
        text = text.replace('\nfont_size = 0', '\nfont_size = 15')
        text = text.replace('deep = false', 'deep = true')
        text = text.replace('search_query = ', 'search_query = Allman Brothers Band')
        pref.save_text(tmp_path, text)
        main = _load('tlo_main_gui_live_prefs_test', 'tlo-main.py')
        with mock.patch.object(main, 'is_auto_update_enabled', return_value=False):
            gui = main.App(root, main._parse_gui_command_line(['--TLOHome', str(tmp_path)]))
        assert gui.vars['performance_mode'].get() == 'gentle'
        assert gui.vars['max_workers'].get() == '3'
        assert gui.gui_font_size == 15
        assert gui.title_font.actual('size') == 18
        assert gui.bool_vars['artist_in_album'].get()
        assert gui.dry_run_var.get() is False
        assert gui.hamburger_menu.entrycget(2, 'label') == 'Edit Preferences'
    finally:
        root.destroy()
    root = tk.Tk()
    root.withdraw()
    try:
        search = _load('tlo_search_gui_live_prefs_test', 'tlo-search.py')
        paths = search.build_paths(tmp_path)
        with mock.patch.object(search, 'is_auto_update_enabled', return_value=False):
            gui = search.BootlistSearchApp(root, paths, None)
        assert gui.deep_var.get() is True
        assert int(tkfont.nametofont('TkDefaultFont').actual('size')) == 15
        assert gui.hamburger_menu.entrycget(2, 'label') == 'Edit Preferences'
        with mock.patch.object(gui, 'execute_search'):
            gui._startup_first_search()
        assert gui.search_var.get() == 'Allman Brothers Band'
    finally:
        root.destroy()


def test_editor_save_prompts_restart_and_does_not_apply_live(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display required')
    root.withdraw()
    try:
        pref.load(tmp_path)
        editor_window = pref.edit(root, tmp_path)
        text_widget = next(w for w in editor_window.winfo_children()[1].winfo_children() if isinstance(w, tk.Text))
        text_widget.replace('1.0', 'end', pref.default_text().replace('max_workers = 0', 'max_workers = 8'))
        buttons = editor_window.winfo_children()[-1]
        with mock.patch.object(pref.messagebox, 'showinfo') as notification:
            next(w for w in buttons.winfo_children() if w.cget('text') == 'Save & Close').invoke()
        notification.assert_called_once()
        assert 'Restart' in notification.call_args.args[0]
        assert pref.load(tmp_path)['main']['max_workers'] == 8
        editor_window.destroy()
    finally:
        root.destroy()


def test_cli_conflicting_preference_reconciles_to_explicit_choice(tmp_path):
    module = _load('tlo_main_gui_cli_override_prefs_test', 'tlo-main.py')
    existing = pref.parse_text(pref.default_text())['main']
    existing['compliant'] = True
    existing['tag_copy_during_inventory'] = True
    args = module._parse_gui_command_line(['--rename-compliantly', '--tag-during-inventory'])
    flags = module._initial_checkbox_values(args, existing, args._explicit_preferences_fields)
    assert flags['rename_compliantly'] and not flags['compliant']
    assert flags['tag_during_inventory'] and not flags['tag_copy_during_inventory']


def test_invalid_existing_file_can_be_reopened_and_repaired(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display required')
    root.withdraw()
    try:
        pref.load(tmp_path)
        ini = tmp_path / pref.FILENAME
        ini.write_text('[main]\nmax_workers = nonsense\n')
        module = _load('tlo_main_gui_recovery_prefs_test', 'tlo-main.py')
        with mock.patch.object(module.messagebox, 'showwarning'):
            gui = module.App(root, module._parse_gui_command_line(['--TLOHome', str(tmp_path)]))
        with mock.patch.object(module.messagebox, 'showerror') as error:
            gui._edit_preferences()
        error.assert_not_called()
        windows = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert windows
        editor_window = windows[-1]
        text_widget = next(w for w in editor_window.winfo_children()[1].winfo_children() if isinstance(w, tk.Text))
        text_widget.replace('1.0', 'end', pref.default_text())
        buttons = editor_window.winfo_children()[-1]
        with mock.patch.object(pref.messagebox, 'showinfo'):
            next(w for w in buttons.winfo_children() if w.cget('text') == 'Save & Close').invoke()
        assert pref.load(tmp_path)['main']['max_workers'] == 0
        editor_window.destroy()
    finally:
        root.destroy()
