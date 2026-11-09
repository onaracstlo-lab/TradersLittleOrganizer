"""Build 604: document all valid INI options, normalize choices and report every error."""
from pathlib import Path
from unittest import mock
import tkinter as tk

import pytest

import tlo_preferences as pref

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_template_is_concise_and_documents_boolean_aliases_once():
    lines = pref.default_text().splitlines()
    assert pref.parse_text('\n'.join(lines)) == pref.DEFAULTS
    assert lines == (ROOT / pref.FILENAME).read_text(encoding='utf-8').splitlines()
    assert pref.default_text().count('all items that take true | false') == 1
    for section, settings in pref.DEFAULTS.items():
        for key in settings:
            assert sum(line.startswith(f'{key} =') for line in lines) == (2 if key in {'font_family', 'font_size', 'heading_font_size', 'fixed_font_size'} else 1)
    assert '# artist_in_album:' not in pref.default_text()
    assert '# max_workers:' in pref.default_text()



def test_template_lists_every_enum_pull_down_option_and_labels():
    template = pref.default_text()
    for (section, key), choices in pref.CHOICES.items():
        assert f'[{section}]' in template
        assert f'# {key}: ' + ' | '.join(choices) in template
    assert 'Keep and report' in template
    assert '100% corrupt only' in template
    assert '0 (automatic' in template
    assert '0-100 (%)' in template


def test_case_insensitive_sections_keys_boolean_and_enum_but_preserve_paths():
    text = '''[MAIN]\nPERFORMANCE_MODE = EXTREME\nCORRUPT_FILES = KEEP\nCORRUPT_FOLDERS = NeVeR\nSEARCH_PATH = C:\\Concerts\\The Band;D:\\MiXeD\\Shows\nFONT_FAMILY = SYSTEM\nARTIST_IN_ALBUM = YES\n[SeArCh]\nDEEP = ON\nSEARCH_QUERY = The BAND |AND| King Crimson\n[GeNeRaL]\nAUTO_UPDATE = 0\n'''
    parsed = pref.parse_text(text)
    assert parsed['main']['performance_mode'] == 'extreme'
    assert parsed['main']['corrupt_files'] == 'keep'
    assert parsed['main']['corrupt_folders'] == 'never'
    assert parsed['main']['search_path'] == r'C:\Concerts\The Band;D:\MiXeD\Shows'
    assert parsed['main']['font_family'] == 'system'
    assert parsed['main']['artist_in_album'] is True
    assert parsed['search']['search_query'] == 'The BAND |AND| King Crimson'
    assert parsed['search']['deep'] is True
    assert parsed['general']['auto_update'] is False


def test_font_match_is_case_insensitive_without_changing_original_font_names():
    assert pref.resolve_font_family('aRiAl', ['Arial', 'Liberation Sans']) == 'Arial'
    assert pref.resolve_font_family('SYSTEM', ['Arial']) == 'system'
    assert pref.resolve_font_family('Missing Font', ['Arial']) == 'system'


def test_all_invalid_fields_and_their_line_numbers_reported_in_one_error(tmp_path):
    pref.load(tmp_path)
    saved = (tmp_path / pref.FILENAME).read_bytes()
    text = '''[Main]\nPERFORMANCE_MODE = TURBO\nmax_workers = -4\ncorrupt_files = maybe\n[SEARCH]\nfont_size = seventy\n[bad_section]\nitem = foo\n[main]\nnot_a_setting = yes\n'''
    with pytest.raises(ValueError) as caught:
        pref.save_text(tmp_path, text)
    report = str(caught.value)
    assert 'Line 2' in report and '[main] performance_mode' in report
    assert 'gentle | balanced | fast | extreme' in report
    assert 'Line 3' in report and '[main] max_workers' in report
    assert 'Line 4' in report and '[main] corrupt_files' in report
    assert 'Line 6' in report and '[search] font_size' in report
    assert 'Line 7' in report and 'Unknown preferences section [bad_section]' in report
    assert 'Line 9' in report and 'Duplicate section [main]' in report
    assert 'Line 10' in report and 'Unknown preference [main] not_a_setting' in report
    assert (tmp_path / pref.FILENAME).read_bytes() == saved


def test_multiple_cross_field_conflicts_are_all_reported_and_not_saved(tmp_path):
    pref.load(tmp_path)
    existing = (tmp_path / pref.FILENAME).read_text()
    changed = (existing.replace('compliant = false', 'compliant = true')
              .replace('rename_compliantly = false', 'rename_compliantly = true')
              .replace('tag_during_inventory = false', 'tag_during_inventory = true')
              .replace('tag_copy_during_inventory = false', 'tag_copy_during_inventory = true')
              .replace('setlistfm_lookup = false', 'setlistfm_lookup = true')
              .replace('setlistfm_upgrade = false', 'setlistfm_upgrade = true'))
    with pytest.raises(ValueError) as caught:
        pref.save_text(tmp_path, changed)
    message = str(caught.value)
    assert 'compliant' in message and 'rename_compliantly' in message
    assert 'tag_during_inventory' in message and 'tag_copy_during_inventory' in message
    assert 'setlistfm_lookup requires etree_lookup=true' in message
    assert (tmp_path / pref.FILENAME).read_text() == existing


def test_case_insensitive_duplicate_identifiers_rejected():
    report = str(pytest.raises(ValueError, pref.parse_text, '[Main]\nDry_Run = true\nDRY_RUN = false\n').value)
    assert 'Duplicate preference [main] dry_run' in report


def test_invalid_line_reports_exact_line_and_does_not_save(tmp_path):
    pref.load(tmp_path)
    original = (tmp_path / pref.FILENAME).read_text()
    with pytest.raises(ValueError, match=r'Line 3: Invalid preference assignment'):
        pref.save_text(tmp_path, '[main]\nmax_workers = 2\n?broken\n')
    assert (tmp_path / pref.FILENAME).read_text() == original


def test_editor_shows_all_items_and_does_not_save_on_error(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk display required')
    root.withdraw()
    try:
        pref.load(tmp_path)
        window = pref.edit(root, tmp_path)
        text_widget = next(item for item in window.winfo_children()[1].winfo_children()
                           if isinstance(item, tk.Text))
        text_widget.replace('1.0', 'end', '[main]\nmax_workers = 999\nperformance_mode = WARP\n')
        buttons = window.winfo_children()[-1]
        with mock.patch.object(pref.messagebox, 'showerror') as error:
            next(item for item in buttons.winfo_children() if item.cget('text') == 'Save & Close').invoke()
        error.assert_called_once()
        description = error.call_args.args[1]
        assert 'Line 2' in description and 'max_workers' in description
        assert 'Line 3' in description and 'performance_mode' in description
        assert pref.load(tmp_path)['main']['max_workers'] == 0
        window.destroy()
    finally:
        root.destroy()


def test_keep_and_report_disallows_corrupt_folder_removal(tmp_path):
    pref.load(tmp_path)
    existing = (tmp_path / pref.FILENAME).read_text()
    changed = existing.replace('corrupt_folders = never', 'corrupt_folders = all')
    with pytest.raises(ValueError, match='corrupt_files=keep requires corrupt_folders=never'):
        pref.save_text(tmp_path, changed)
    assert (tmp_path / pref.FILENAME).read_text() == existing
