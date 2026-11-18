"""Build 669: unconditional clipboard startup; ignored legacy INI controls."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import tlo_preferences as pref

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _search_module():
    spec = importlib.util.spec_from_file_location('search669', ROOT / 'tlo-search.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_startup(*, clipboard='From Clipboard', find=None, prefs=None, clip_error=None):
    mod = _search_module()
    app = mod.BootlistSearchApp.__new__(mod.BootlistSearchApp)
    app.initial_find = find
    app.preferences = prefs or {'search': {'deep': False}}
    app.root = Mock()
    app.root.winfo_exists.return_value = True
    if clip_error is not None:
        app.root.clipboard_get.side_effect = clip_error
    else:
        app.root.clipboard_get.return_value = clipboard
    app.search_var = Mock()
    app.search_entry = Mock()
    app.execute_search = Mock()
    app._startup_first_search()
    return app


def test_new_ini_has_no_obsolete_options(tmp_path):
    loaded = pref.load(tmp_path)
    assert not set(('search_path',)) & loaded['main'].keys()
    assert not set(('clipboard_prefill', 'search_query')) & loaded['search'].keys()
    ini = (tmp_path / pref.FILENAME).read_text()
    assert 'clipboard_prefill' not in ini
    assert 'search_query' not in ini
    assert 'search_path =' not in ini


@pytest.mark.parametrize('old_value', ['false', 'true', 'not-a-boolean', ''])
def test_old_ini_keys_ignored_no_matter_their_values(tmp_path, old_value):
    pref.load(tmp_path)
    path = tmp_path / pref.FILENAME
    old_ini = path.read_text().replace('[search]', '[search]\n'
                       f'clipboard_prefill = {old_value}\n'
                       'search_query = Do not run this\n'
                       'search_query = Another obsolete value\n')
    old_ini = old_ini.replace('[main]', '[main]\nsearch_path = C:\\Music\n')
    path.write_text(old_ini)
    parsed = pref.load(tmp_path)
    assert 'clipboard_prefill' not in parsed['search']
    assert 'search_query' not in parsed['search']
    assert 'search_path' not in parsed['main']
    assert path.read_text() == old_ini
    app = _run_startup(clipboard='Kinks', prefs=parsed)
    app.root.clipboard_get.assert_called_once_with()
    app.search_var.set.assert_called_once_with('Kinks')


def test_default_startup_reads_clipboard_and_searches_once():
    app = _run_startup(clipboard='   Kinks 1987-05-28  ')
    app.root.clipboard_get.assert_called_once_with()
    app.search_var.set.assert_called_once_with('Kinks 1987-05-28')
    app.execute_search.assert_called_once_with()
    app.search_entry.focus_set.assert_called_once_with()


@pytest.mark.parametrize('find,expected,clipboard_calls', [
    ('From CLI', 'From CLI', 0),
    (None, 'From Clipboard', 1),
    ('', '', 0),
])
def test_find_takes_precedence_over_clipboard(find, expected, clipboard_calls):
    app = _run_startup(find=find, clipboard='From Clipboard')
    assert app.root.clipboard_get.call_count == clipboard_calls
    if expected:
        app.search_var.set.assert_called_once_with(expected)
    else:
        app.search_var.set.assert_not_called()
    app.execute_search.assert_called_once_with()


def test_even_stale_pref_values_cannot_override_clipboard():
    app = _run_startup(
        prefs={'search': {'search_query': 'bad', 'clipboard_prefill': False}},
        clipboard='good',
    )
    app.root.clipboard_get.assert_called_once_with()
    app.search_var.set.assert_called_once_with('good')


def test_missing_or_nontext_clipboard_is_safe():
    mod = _search_module()
    app = _run_startup(clip_error=mod.tk.TclError('CLIPBOARD selection not available'))
    app.search_var.set.assert_not_called()
    app.execute_search.assert_called_once_with()
    app = _run_startup(clipboard='  ')
    app.search_var.set.assert_not_called()
    app.execute_search.assert_called_once_with()
