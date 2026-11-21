"""Source regressions for explicit tagging modes, recovery UX and Unicode identity."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventory_parser_lib as parser_lib
import tlo_manual_undo as undo
from tlo_phase23_v2 import (
    _normalize_record_ascii_for_output,
    _protect_numbered_show_identity,
    _protect_explicit_regionless_place,
)

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _main_module():
    spec = importlib.util.spec_from_file_location('tlo_main_710', ROOT / 'tlo-main.py')
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('settings', [
    {'tag_during_inventory': True, 'tag_copy_and_delete_path': '/anywhere'},
    {'tag_copy_during_inventory': True, 'tag_copy_and_delete_path': '/anywhere'},
    {'tag_during_inventory': True, 'tag_copy_during_inventory': True},
])
def test_conflicting_tag_modes_are_hard_errors_before_any_file_mutation(settings):
    with pytest.raises(ValueError, match='mutually exclusive'):
        parser_lib._validate_tag_copy_values(settings)


def test_gui_explicit_tag_mode_conflicts_are_rejected():
    module = _main_module()
    with pytest.raises(SystemExit) as problem:
        module._parse_gui_command_line(['--tag-during-inventory', '--tag-copy-delete-original'])
    assert problem.value.code == 2


def test_dry_run_refuses_manual_updates_before_field_or_worker_access(monkeypatch):
    module = _main_module()
    shown = []
    monkeypatch.setattr(module.messagebox, 'showwarning', lambda *args, **kwargs: shown.append(args))
    window = object.__new__(module.ManualUpdatesWindow)
    window._processing = False
    window.parent_app = SimpleNamespace(dry_run_var=SimpleNamespace(get=lambda: True))
    window.window = None
    window._save()
    assert shown and 'Dry Run' in str(shown)


def test_nonlatin_composite_show_name_is_preserved_without_losing_artist():
    record = SimpleNamespace(artist='Кино', date='1988-03-02', venue='', city='',
                             show_name='Кино 1988-03-02 Москва')
    _normalize_record_ascii_for_output(record)
    assert record.artist == 'Кино'
    assert record.show_name == 'Кино 1988-03-02 Москва'
    latin = SimpleNamespace(artist='Björk', show_name='Björk 1997-11-17')
    _normalize_record_ascii_for_output(latin)
    assert latin.artist == 'Bjork'


def test_show_number_disambiguates_same_date_even_when_venue_missing():
    first = SimpleNamespace(main_dir_name='Grateful Dead 1977-05-01 Barton Hall Show 1',
                            artist='Grateful Dead', date='1977-05-01', show_name='Grateful Dead 1977-05-01')
    second = SimpleNamespace(main_dir_name='Grateful Dead 1977-05-01 Barton Hall Show 2',
                             artist='Grateful Dead', date='1977-05-01', show_name='Grateful Dead 1977-05-01')
    _protect_numbered_show_identity(first)
    _protect_numbered_show_identity(second)
    assert first.show_name != second.show_name
    assert '(Show 1)' in first.show_name and '(Show 2)' in second.show_name
    _protect_numbered_show_identity(first)
    assert first.show_name.count('(Show 1)') == 1


def test_explicit_regionless_known_venue_and_city_are_not_dropped(tmp_path):
    venue = tmp_path / 'venues.txt'
    venue.write_text('Shepherds Bush Empire\n', encoding='utf8')
    config = SimpleNamespace(venue_reference_db_file=str(venue))
    record = SimpleNamespace(artist='Wilco', date='2005-06-20',
        main_dir_name='Wilco 2005-06-20 Shepherds Bush Empire, London',
        venue='', city='London', region='', country='', location='', album_name='')
    _protect_explicit_regionless_place(config, record)
    assert record.venue == 'Shepherds Bush Empire'
    assert record.city == 'London' and record.location == 'London'


def test_manual_journal_listing_includes_invalid_neighbors_without_crashing(tmp_path):
    home = tmp_path / 'home'
    folder = tmp_path / 'recording'
    folder.mkdir()
    (home / 'setlists').mkdir(parents=True)
    journal = undo.begin_manual_undo(str(home), str(folder), str(folder),
                                     mode='unidentified', update_tags=False, setlist_paths=[])
    undo.finish_manual_undo(str(home), journal)
    other = Path(undo._journal_dir(str(home))) / 'manual-update-corrupt.json'
    other.write_text('garbled')
    records = undo.list_manual_updates(str(home))
    assert len(records) == 2
    assert {r['state'] for r in records} == {'committed', 'invalid'}


def test_donation_menu_remains_compatible_with_existing_user_requirements():
    # Personal street address disclosure is a policy decision and is not
    # silently changed by a safety-remediation build.
    source = (ROOT / 'tlo-main.py').read_text()
    assert 'self.donate_menu.add_cascade(label="Check", menu=self.check_menu)' in source
    assert 'self.check_menu.add_command' in source
