"""Build 687 targeted regressions for review N3/N8/N10/N11/N12/N13."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import tlo_tag_lib
from tlo_rename_safety import safe_rename_target

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _search():
    spec = importlib.util.spec_from_file_location('tlo_search_build687', ROOT / 'tlo-search.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_unicode_and_month_rename_guard_preserves_identity():
    for source, target in [
        ('Björk 2007-08-20 Paris', 'Bjork 2007-08-20 Paris'),
        ('Sigur Rós 2007-08-20 Paris', 'Sigur Ros 2007-08-20 Paris'),
        ('Pink Floyd 3 Agosto 1971 Hakone', 'Pink Floyd 1971-08-03 Hakone'),
    ]:
        accepted, reason = safe_rename_target(source, target, date='1971-08-03')
        assert accepted == target, (source, reason)
    for source, target in [
        ('Brian May 1997-11-28 London', 'Brian 1997-11-28 London'),
        ('New Riders 1997-11-28 New Haven', 'Riders 1997-11-28 Haven'),
        ('Кино 1990-06-24 Москва', 'Кино 1990-06-24'),
    ]:
        accepted, reason = safe_rename_target(source, target, date='1997-11-28')
        assert not accepted and reason, (source, target)


def test_run_two_keeps_show_and_album_identity_when_punctuation_only_rename_skipped(tmp_path):
    folder = 'Grateful Dead 1977-05-08 Barton Hall, Cornell University Ithaca, NY'
    source = tmp_path / folder
    source.mkdir()
    (source / '01.flac').write_bytes(b'audio')
    group = {'main_dir_path': str(source), 'main_dir_name': folder, 'music_dirs': [str(source)]}
    candidate = folder.replace('Hall, Cornell', 'Hall Cornell')
    record = SimpleNamespace(show_name=candidate, artist='Grateful Dead', date='1977-05-08',
                             main_dir_path=str(source), main_dir_name=folder)
    events = []
    new_group, new_record = tlo_tag_lib.prepare_inventory_tagging_target(
        SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False),
        group, record, emit=events.append)
    assert source.is_dir()
    assert new_group['main_dir_path'] == str(source)
    assert new_record.show_name == folder  # passed to tag ALBUM and postprocess Show
    assert any('punctuation-only reduction' in event for event in events)
    # A repeat is a no-op and preserves exact Show identity.
    again = []
    tlo_tag_lib.prepare_inventory_tagging_target(
        SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False),
        new_group, new_record, emit=again.append)
    assert new_record.show_name == folder and source.is_dir()


def test_search_explicit_expressions_preserve_qualifiers_and_typographic_text():
    search = _search()
    rows = [search.CsvRow("'Til Tuesday 1985", '[Disk] /til'),
            search.CsvRow("Gilley's 1997-05-08", '[Disk] /gilley'),
            search.CsvRow('Phish (Early Show) 1997', '[Disk] /phish'),
            search.CsvRow('Wilco 1997', '[Disk] /wilco')]
    assert [r.show for r in search.search_rows(rows, "'Til Tuesday |OR| Gilley's")] == [rows[0].show, rows[1].show]
    assert [r.show for r in search.search_rows(rows, '(Phish (Early Show) |OR| Wilco)')] == [rows[2].show, rows[3].show]
    assert search.search_rows(rows, 'Gilley’s') == rows[1:2]
    assert search.search_rows(rows, 'Phish  (Early Show) 1997') == rows[2:3]
    with pytest.raises(search.SearchExpressionError):
        search.search_rows(rows, ' |AND| '.join('Wilco' for _ in range(3000)))


def test_ambiguous_search_view_avoids_internal_placeholder_name(tmp_path, monkeypatch):
    search = _search()
    paths = search.build_paths(tmp_path)
    paths.setlist_dir.mkdir()
    paths.bootlist_csv.write_text('sep=^\nShow^VolumePath\nSame show^/a\nSame show^/b\n', encoding='utf-8')
    rows = search.load_bootlist_rows(paths.bootlist_csv)
    assert all(search.resolve_setlist_path_for_row(paths, row).name ==
               '__TLO_AMBIGUOUS_SETLIST_IDENTITY__.txt' for row in rows)
    # Exercise the actual View callback without a real Tk toplevel.
    notices = []
    monkeypatch.setattr(search, 'show_nonblocking_notice', lambda _parent, title, message: notices.append((title, message)))
    monkeypatch.setattr(search, 'enforce_open_limit', lambda _parent, _count: True)

    class Selection:
        def selection(self):
            return ['0']

    frame = object.__new__(search.CsvSearchResultsWindow)
    frame._view_in_progress = False
    frame.tree = Selection()
    frame.rows = rows
    frame.paths = paths
    frame.window = object()
    frame.view_selected()
    assert len(notices) == 1
    assert 'Re-inventory' in notices[0][1]
    assert '__TLO_AMBIGUOUS' not in notices[0][1]


def test_parallel_mutation_abort_message_does_not_claim_bootlist_is_finalized():
    code = (ROOT / 'walk_trees_lib.py').read_text(encoding='utf-8')
    assert 'bootlist and setlist outputs were not finalized' in code
    assert 'Completed volumes were retained;' not in code


def test_rename_summary_counts_on_actual_group_processing(tmp_path, monkeypatch):
    import tlo_phase23_v2 as phase
    source = tmp_path / 'Brian May 1997-11-28 London'
    source.mkdir()
    (source / '01.flac').write_bytes(b'not decoded in rename-only fixture')
    group = {'main_dir_path': str(source), 'main_dir_name': source.name,
             'music_dirs': [str(source)], 'group_number': 1}
    record = SimpleNamespace(main_dir_path=str(source), main_dir_name=source.name,
                             artist='Brian May', date='1997-11-28',
                             show_name='Brian 1997-11-28 London')
    log_lines = []
    class Logs:
        def tag(self, text, *args):
            log_lines.append(text % args if args else text)
        def conflicts(self, text, *args):
            log_lines.append(text % args if args else text)

    console_lines = []
    config = SimpleNamespace(TLOHome=str(tmp_path), current_search_path=str(tmp_path),
                             current_path_copy_destination='', current_path_copy_delete_destination='',
                             tag_copy_and_delete_path='', tag_copy_during_inventory=False,
                             tag_during_inventory=False, rename_compliantly=True,
                             convert_shn=False, deep_audio_check=False, dry_run=False,
                             logs=Logs(), silent=False)
    monkeypatch.setattr(phase, '_build_groups_from_search_path', lambda *_: [group])
    monkeypatch.setattr(phase, '_extract_metadata_for_group', lambda *_: (record, [], []))
    monkeypatch.setattr(phase, '_log_group', lambda *_args, **_kw: None)
    monkeypatch.setattr(phase, '_log_show_metadata', lambda *_args, **_kw: None)
    monkeypatch.setattr(phase, '_format_show_metadata_log_entry', lambda *_args, **_kw: '')
    monkeypatch.setattr(phase, '_format_switches_log_line', lambda *_args, **_kw: '')
    monkeypatch.setattr(phase, '_replace_complete_paths_log_with_inventory_samples', lambda *_args: None)
    monkeypatch.setattr(phase, 'console_print', lambda _config, msg, **_kw: console_lines.append(str(msg)))
    import tlo_corruption
    monkeypatch.setattr(tlo_corruption, 'handle_group_corruption', lambda *_args, **_kw:
                        SimpleNamespace(unverifiable=False, show_removed=False))
    result = phase.process_groups_for_search_path_v2(config, None)
    assert len(result) == 1
    assert source.exists()
    assert any('RENAME_COMPLIANTLY_SUMMARY: renamed=0 skipped=1' in line for line in log_lines)
    assert any('Rename Compliantly: 0 renamed, 1 skipped' in line for line in console_lines)


def test_summary_log_includes_actual_rename_decision_counts(tmp_path):
    import tlo_postprocess
    logs = tmp_path / 'logs'
    logs.mkdir()
    (logs / 'tags0.txt').write_text(
        'RENAME_COMPLIANTLY_SUMMARY: renamed=2 skipped=3\n', encoding='utf-8')
    (logs / 'tagsA.txt').write_text(
        'RENAME_COMPLIANTLY_SUMMARY: renamed=1 skipped=4\n', encoding='utf-8')
    summary = Path(tlo_postprocess._write_conflict_summary_log(str(tmp_path)))
    assert 'Rename Compliantly: 3 renamed, 7 skipped' in summary.read_text(encoding='utf-8')
