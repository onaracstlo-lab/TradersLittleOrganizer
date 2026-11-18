"""Build 683 focused filesystem, search-output, and process-crash regressions."""
import importlib.util
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from concurrent.futures.process import BrokenProcessPool

import pytest

import tlo_tag_lib
import tlo_postprocess
import walk_trees_lib

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _search():
    spec = importlib.util.spec_from_file_location('search683', ROOT / 'tlo-search.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rename(tmp_path, old_name, show_name, *, artist='Wilco', date='1997-11-28'):
    source = tmp_path / old_name
    source.mkdir()
    (source / '01.flac').write_bytes(b'track')
    group = {'main_dir_path': str(source), 'main_dir_name': old_name, 'music_dirs': [str(source)]}
    record = SimpleNamespace(show_name=show_name, artist=artist, date=date,
                             parentheticals='', main_dir_path=str(source), main_dir_name=old_name)
    messages = []
    tlo_tag_lib.prepare_inventory_tagging_target(
        SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False),
        group, record, emit=messages.append)
    return source, group, record, messages


@pytest.mark.parametrize('old,proposed,artist,date', [
    ('Wilco 2017 Tokyo Dome', 'Wilco xxxx-xx-xx Tokyo Dome', 'Wilco', 'xxxx-xx-xx'),
    ('Wilco 8 May 1987 Berlin', 'Wilco 1987-05-08', 'Wilco', '1987-05-08'),
    ('Wilco 1997-11-28 Worcester SBD', 'Wilco 1997-11-28 Worcester', 'Wilco', '1997-11-28'),
    ('Wilco 1997-11-28 Worcester AUD', 'Wilco 1997-11-28', 'Wilco', '1997-11-28'),
    ('Bruno Mars 2017 Tokyo Dome', 'Bruno xxxx-xx-xx Tokyo Dome', 'Bruno', 'xxxx-xx-xx'),
])
def test_nonlossy_rename_preserves_date_city_source_and_artist(tmp_path, old, proposed, artist, date):
    source, group, record, messages = _rename(tmp_path, old, proposed, artist=artist, date=date)
    assert source.is_dir()
    assert group['main_dir_path'] == str(source)
    assert not any(line.startswith('RENAME_COMPLIANTLY: ') for line in messages)
    assert any('RENAME_COMPLIANTLY_SKIP' in line for line in messages)


def test_rename_permitted_when_identity_preserved_and_idempotent(tmp_path):
    initial = 'Wilco 11 28 1997 Worcester'
    proposed = 'Wilco 1997-11-28 Worcester'
    source, group, record, messages = _rename(tmp_path, initial, proposed)
    renamed = tmp_path / proposed
    assert renamed.is_dir() and not source.exists()
    assert any(line.startswith('RENAME_COMPLIANTLY: ') for line in messages)
    group['main_dir_path'] = str(renamed)
    record.main_dir_path = str(renamed)
    again = []
    tlo_tag_lib.prepare_inventory_tagging_target(SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False), group, record, emit=again.append)
    assert renamed.exists() and not any(line.startswith('RENAME_COMPLIANTLY: ') for line in again)


def test_second_pass_does_not_drop_venue_comma(tmp_path):
    name = 'Grateful Dead 1977-05-08 Barton Hall, Cornell University Ithaca, NY'
    proposed = 'Grateful Dead 1977-05-08 Barton Hall Cornell University Ithaca, NY'
    source, _, _, messages = _rename(tmp_path, name, proposed, artist='Grateful Dead', date='1977-05-08')
    assert source.is_dir()
    assert any('punctuation-only reduction' in line for line in messages)


def test_search_view_row_identity_and_explicit_expression_parser(tmp_path):
    search = _search()
    setlists = tmp_path / 'setlists'
    setlists.mkdir()
    (setlists / 'Wilco1997-11-28.txt').write_text('Source: AUD\n', encoding='utf-8')
    (setlists / 'Wilco1997-11-28(alt1).txt').write_text('Source: SBD\n', encoding='utf-8')
    rows = [
        {'Show': 'Wilco 1997-11-28', 'VolumePath': '[Disk] /music/Wilco AUD', 'Setlist': 'Wilco1997-11-28.txt'},
        {'Show': 'Wilco 1997-11-28', 'VolumePath': '[Disk] /music/Wilco SBD', 'Setlist': 'Wilco1997-11-28(alt1).txt'},
    ]
    tlo_postprocess._write_bootlist_csv(str(tmp_path), rows)
    paths = search.build_paths(tmp_path)
    loaded = search.load_bootlist_rows(paths.bootlist_csv)
    assert len(loaded) == 2
    assert 'AUD' in search.resolve_setlist_path_for_row(paths, loaded[0]).read_text()
    assert 'SBD' in search.resolve_setlist_path_for_row(paths, loaded[1]).read_text()
    # Re-inventorying another volume must preserve the old setlist identity.
    tlo_postprocess._write_bootlist_csv(str(tmp_path), [{key: val for key, val in row.items() if key != 'Setlist'} for row in rows])
    assert 'SBD' in search.resolve_setlist_path_for_row(paths, loaded[1]).read_text()
    (tmp_path / 'setlist-index.json').unlink()
    assert not search.resolve_setlist_path_for_row(paths, loaded[1]).is_file(), 'ambiguity must fail closed'
    names = [search.CsvRow("Gilley's 1997-11-28 (Early Show)", '[Disk] /show'),
             search.CsvRow('O\'Brien 2000-01-02', '[Disk] /other')]
    assert search.search_rows(names, "Gilley's 1997-11-28 (Early Show)") == names[:1]
    assert search.search_rows(names, "O'Brien") == names[1:]
    assert search.search_rows(names, "Gilley's |AND| (Early Show)") == names[:1]
    assert search.search_rows(names, '(Gilley |OR| O\'Brien) |AND| 1997') == names[:1]
    with pytest.raises(search.SearchExpressionError):
        search.search_rows(names, ' |AND| '.join('Wilco' for _ in range(3000)))


# A real forked child exits abruptly; the successful worker's result must
# remain available to the caller even if the ProcessPoolExecutor breaks.
def _crashing_group_worker(snapshot, jobs):
    if jobs[0][3] == 'VolumeB':
        time.sleep(0.5)
        os._exit(23)
    return [dict(search_index=job[2], path_name=job[0], directory_count=1,
                 show_group_count=1, metadata_records=[{'show': 'safe'}],
                 groups_prepared=1, corruption_groups_removed=0, corruption_removed_paths=[])
            for job in jobs]


@pytest.mark.skipif(sys.platform == 'win32', reason='forked subprocess crash fixture requires POSIX')
def test_process_pool_crash_retains_completed_groups(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    config.performance_mode = 'fast'
    config.max_workers = 2
    monkeypatch.setattr(walk_trees_lib, 'run_search_path_group_job', _crashing_group_worker)
    groups = [
        [[str(tmp_path / 'a'), '', 'VolumeA', 'a', '0', 'w', '', '', str(tmp_path / 'a')]],
        [[str(tmp_path / 'b'), '', 'VolumeB', 'b', '1', 'w', '', '', str(tmp_path / 'b')]],
    ]
    with pytest.raises(BrokenProcessPool) as captured:
        walk_trees_lib._run_parallel_paths(config, groups, 2)
    exc = captured.value
    assert len(exc.completed_results) == 1
    assert next(iter(exc.completed_results.values()))['path_name'].endswith('/a')
    assert len(exc.pending_groups) == 1
    assert exc.pending_groups[0][0][2] == 'VolumeB'


def test_add_shows_bootlist_preserves_exact_setlist_identity(tmp_path):
    import tlo_inventory_update as updates
    search = _search()
    (tmp_path / 'setlists').mkdir()
    (tmp_path / 'setlists' / 'same.txt').write_text('AUD', encoding='utf8')
    (tmp_path / 'setlists' / 'same(alt1).txt').write_text('SBD', encoding='utf8')
    rows = [
        {'Show': 'Same Show', 'VolumePath': '[Disc] /a', 'Setlist': 'same.txt'},
        {'Show': 'Same Show', 'VolumePath': '[Disc] /b', 'Setlist': 'same(alt1).txt'},
    ]
    updates.write_bootlist(str(tmp_path), rows)
    paths = search.build_paths(tmp_path)
    loaded = search.load_bootlist_rows(paths.bootlist_csv)
    assert [search.resolve_setlist_path_for_row(paths, r).read_text() for r in loaded] == ['AUD', 'SBD']
    # A subsequent Add Shows edit retaining old CSV rows must not clear the mapping.
    updates.write_bootlist(str(tmp_path), updates.read_bootlist(str(tmp_path)))
    assert [search.resolve_setlist_path_for_row(paths, r).read_text() for r in loaded] == ['AUD', 'SBD']
