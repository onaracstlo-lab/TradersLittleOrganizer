"""Build 709: metadata-only undo type, size, path, and retry safety contracts."""
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
from mutagen.apev2 import APETextValue, APEBinaryValue, APEExtValue, TEXT, BINARY, EXTERNAL

import tlo_manual_undo as U
from tlo_rename_safety import safe_rename_target


def test_ape_text_binary_external_keep_types_and_values():
    for original in (APETextValue('one\x00two'), APEBinaryValue(b'\x00\xff'), APEExtValue('https://example.test')):
        new = U._decode(U._encode(original))
        assert type(new) is type(original)
        assert new.kind == original.kind
        assert bytes(new) == bytes(original)
    assert {TEXT, BINARY, EXTERNAL} == {0, 1, 2}


def test_record_size_checked_before_mutation(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    journal = home / 'record.json'
    monkeypatch.setattr(U, '_MAX_JOURNAL_BYTES', 300)
    with pytest.raises(U.ManualUndoError, match='exceeds'):
        U._write_journal(str(home), str(journal), {'data': 'x' * 500})
    assert not journal.exists()


def test_corrupt_neighbor_cannot_block_valid_matching_journal(tmp_path):
    home = tmp_path / 'home'
    output = Path(U._journal_dir(str(home)))
    output.mkdir(parents=True)
    wanted = tmp_path / 'music' / 'show'
    good = output / 'manual-update-good.json'
    U._write_journal(str(home), str(good), {'schema': 1, 'home': str(home), 'state': 'committed',
                                            'source': str(wanted), 'destination': str(wanted)})
    (output / 'manual-update-broken.json').write_text('garbled')
    assert U._matching_journals(str(home), str(wanted)) == [str(good)]


def test_restore_targets_must_reside_under_setlists(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    record = {'setlists_before': {str(tmp_path / 'other.txt'): {'exists': False}},
              'setlists_after': {}, 'bootlist_before': {}, 'bootlist_after': {},
              'unidentified_before': {}, 'unidentified_after': {}}
    with pytest.raises(U.ManualUndoError, match='outside'):
        U._validate_restore_targets(str(home), record)


def test_rename_guard_never_uses_date_digit_as_show_number():
    target, reason = safe_rename_target('Grateful Dead 1977-05-01 Barton Hall Show 1',
                                       'Grateful Dead 1977-05-01 Barton Hall',
                                       artist='Grateful Dead', date='1977-05-01')
    assert not target and ('numeric' in reason or 'source identifying' in reason)


def test_undo_folder_rename_failure_does_not_change_tags_or_catalog(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    (home / 'setlists').mkdir(parents=True)
    original = tmp_path / 'Old Show'
    new = tmp_path / 'New Show'
    new.mkdir()
    (new / 'track.txt').write_text('do not change')
    (home / 'bootlist.csv').write_text('new catalog')
    journal = U.begin_manual_undo(str(home), str(new), str(new), mode='unidentified', update_tags=False, setlist_paths=[])
    # A true folder undo requires pre/post data pointing to source (old) and destination (new).
    record = U._load_journal(str(home), journal)
    record['source'] = str(original)
    record['mode'] = 'inventory'
    record['source_parent_real'] = str(tmp_path)
    record['destination_parent_real'] = str(tmp_path)
    record['state'] = 'committed'
    record['tree_after'] = U._tree_stats(str(new))
    record['tags_after'] = {}
    record['bootlist_after'] = U._file_digest(str(home / 'bootlist.csv'))
    record['unidentified_after'] = U._file_digest(str(home / 'unidentifiedShows.txt'))
    record['setlists_after'] = {}
    U._write_journal(str(home), journal, record)
    def fail_rename(*args):
        raise OSError('locked')
    monkeypatch.setattr(U, 'rename_folder_exact_case', fail_rename)
    with pytest.raises(U.ManualUndoError, match='no tags/catalog changed'):
        U.reverse_manual_update(str(new), tlo_home=str(home))
    assert (home / 'bootlist.csv').read_text() == 'new catalog'
    assert new.exists() and not original.exists()
    assert U._load_journal(str(home), journal)['state'] == 'committed'


def test_cli_rejects_conflicting_modes(tmp_path):
    command = [os.sys.executable, str(Path(__file__).resolve().parents[2] / 'tlo-reverse.py'),
               str(tmp_path), '--manual-updates', '--recover-staging']
    finished = subprocess.run(command, text=True, capture_output=True, check=False)
    assert finished.returncode == 2 and 'not allowed' in finished.stderr
