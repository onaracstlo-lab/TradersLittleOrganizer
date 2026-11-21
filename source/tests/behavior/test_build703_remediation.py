"""Focused regression checks for Build 703 follow-on review remediation."""
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

from tlo_copy_requests import _acquire_exclusive_lock, _release_exclusive_lock, _copy_owner_payload
from tlo_locking import lock_is_held
from tlo_manual_updates import ManualUpdateError, _validate_new_leaf
import tlo_staging_recovery as recovery


def _search_module():
    spec = importlib.util.spec_from_file_location('tlo_search_703', Path(__file__).resolve().parents[2] / 'tlo-search.py')
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_non_latin_search_marks_are_preserved():
    norm = _search_module().normalize_search_text
    assert norm('Björk') == norm('Bjork')
    assert norm('Straßenjungs') == norm('Strassenjungs')
    assert norm('Мой') != norm('Мои')
    assert norm('ёж') != norm('еж')
    assert norm('किताब') != norm('कताब')


@pytest.mark.parametrize('name', ['CON', 'con.txt', 'LPT1', 'bad?', 'foo.', 'x ', 'bad:show', 'x\x01y'])
def test_manual_tweaks_rejects_windows_unsafe_names_on_all_hosts(name):
    with pytest.raises(ManualUpdateError):
        _validate_new_leaf(name)


def test_manual_tweaks_preserves_unicode_safe_names():
    assert _validate_new_leaf('Кино') == 'Кино'


def test_copy_destination_lock_leaves_no_host_identity(tmp_path):
    lock = str(tmp_path / '.tlo-lock-copy-destination.lock')
    _acquire_exclusive_lock(lock, 'request-1')
    try:
        assert Path(lock).is_file()
        assert lock_is_held(lock)
        # Windows msvcrt locks byte zero exclusively. Reading the live lock
        # file from another handle is not portable (PermissionError on Win11).
        # Verify the owner payload contract without violating that lock.
        assert _copy_owner_payload('request-1')['hostname']
    finally:
        _release_exclusive_lock(lock)
    assert not lock_is_held(lock)
    assert json.loads(Path(lock).read_text()) == {}


def test_pid_creation_id_mismatch_allows_safe_restore(tmp_path, monkeypatch):
    source = tmp_path / 'source' / 'show'
    source.mkdir(parents=True)
    dest = tmp_path / 'dest'
    dest.mkdir()
    stage = dest / ('.tlo-partial-' + '1234' * 8)
    recovery.record_same_volume_move(str(source), str(stage), str(dest / 'show'))
    source.rename(stage)
    monkeypatch.setattr(recovery, '_pid_is_alive', lambda pid: True)
    monkeypatch.setattr(recovery, '_process_creation_identity', lambda pid: 'recycled-pid')
    result = recovery.recover_interrupted_stage_moves(str(dest), dry_run=False)
    assert result['restored'] == 1
    assert source.exists()


def test_pid_without_reliable_birth_identity_stays_blocked(tmp_path, monkeypatch):
    source = tmp_path / 'source' / 'show'
    source.mkdir(parents=True)
    dest = tmp_path / 'dest'
    dest.mkdir()
    stage = dest / ('.tlo-partial-' + 'abcd' * 8)
    recovery.record_same_volume_move(str(source), str(stage), str(dest / 'show'))
    source.rename(stage)
    monkeypatch.setattr(recovery, '_pid_is_alive', lambda pid: True)
    monkeypatch.setattr(recovery, '_process_creation_identity', lambda pid: None)
    result = recovery.recover_interrupted_stage_moves(str(dest), dry_run=False)
    assert result['conflicts'] == 1
    assert stage.exists()
