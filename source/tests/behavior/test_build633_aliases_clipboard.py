"""Build 633: CLI aliases and explicit clipboard preference compatibility."""
from pathlib import Path
import importlib.util
import sys
import pytest
import tlo_preferences as P

ROOT = Path(__file__).resolve().parents[2]

def load_gui(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_search_clipboard_and_search_path_are_not_preferences(tmp_path):
    loaded = P.load(tmp_path)
    assert 'clipboard_prefill' not in loaded['search']
    assert 'search_query' not in loaded['search']
    assert 'search_path' not in loaded['main']
    assert all(key not in P.default_text() for key in ('clipboard_prefill', 'search_query', 'search_path ='))


def test_main_cli_aliases_equivalent(tmp_path):
    main = load_gui('tlo_main_633_cli', 'tlo-main.py')
    old = main._parse_gui_command_line(['--TLOHome', str(tmp_path), '--tag-copy-and-delete', str(tmp_path)])
    new = main._parse_gui_command_line(['--tlo-home', str(tmp_path), '--tag-move-to', str(tmp_path)])
    assert old.TLOHome == new.TLOHome
    assert old.tag_copy_and_delete_path == new.tag_copy_and_delete_path
    assert old.tag_copy_and_delete_enabled and new.tag_copy_and_delete_enabled
    assert 'tag_copy_and_delete_path' in new._explicit_preferences_fields
    with pytest.raises(SystemExit):
        main._parse_gui_command_line(['--tag-move-to'])


def test_search_home_alias(tmp_path):
    search = load_gui('tlo_search_633_cli', 'tlo-search.py')
    assert search.parse_cli_args(['--tlo-home', str(tmp_path)])[0] == tmp_path


pytestmark = pytest.mark.behavior
