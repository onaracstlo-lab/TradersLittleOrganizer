"""Build 703 independently exercised safety cases from Build 700 reviews."""
import json
from pathlib import Path
import pytest

from tlo_copy_requests import _physical_paths_for_volume_stored, source_status_for_show
from tlo_staging_recovery import record_same_volume_move, recover_interrupted_stage_moves
from tlo_unc import compose_unc_path
from tlo_text_utils import standard_ascii_text

pytestmark = pytest.mark.behavior


def test_copy_volume_rejects_traversal_and_symlink_ancestor(tmp_path):
    root = tmp_path / 'volume'
    root.mkdir()
    outside = tmp_path / 'private'
    outside.mkdir()
    (outside/'private.txt').write_text('SECRET')
    (root/'normal').mkdir()
    rows = {'testvolume': [str(root)]}
    for attack in ('../private', r'..\private', 'a/../../private', r'C:\private', '//elsewhere/share'):
        paths, _ = _physical_paths_for_volume_stored('testvolume', attack, rows)
        assert not paths
        selected, *_ = source_status_for_show('secret', [{'VolumePath': f'[testvolume] {attack}'}], rows)
        assert selected is None
    paths, _ = _physical_paths_for_volume_stored('testvolume', 'normal', rows)
    assert paths == [str(root/'normal')]
    try:
        (root/'alias').symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks not permitted')
    paths, _ = _physical_paths_for_volume_stored('testvolume', 'alias', rows)
    assert not paths


def test_legacy_unc_absolute_with_same_share_and_other_share():
    assert compose_unc_path('UNC:ONARACS/Music', r'\\onaracs\music\Band\Show').casefold() == r'\\onaracs\music\band\show'
    assert not compose_unc_path('UNC:ONARACS/Music', r'\\other\music\Band')
    assert not compose_unc_path('UNC:ONARACS/Music', r'..\private')


def test_forged_recovery_record_cannot_move_unrelated_directory(tmp_path, monkeypatch):
    import tlo_staging_recovery as r
    stage_parent = tmp_path/'dest'
    stage_parent.mkdir()
    suffix = '1234567890abcdef1234567890abcdef'
    stage = stage_parent/f'.tlo-partial-{suffix}'
    stage.mkdir()
    (stage/'show.txt').write_text('retained')
    source = tmp_path/'private'/'injected'
    source.parent.mkdir()
    journal = stage_parent/f'.tlo-move-{suffix}.json'
    payload = {'format':r._FORMAT, 'source':str(source), 'stage':str(stage), 'target':str(stage_parent/'show'), 'host':r.socket.gethostname(), 'pid':99999999}
    journal.write_text(json.dumps(payload))
    monkeypatch.setattr(r, '_pid_is_alive', lambda pid: False)
    result = recover_interrupted_stage_moves(str(stage_parent), dry_run=False)
    assert result['conflicts'] == 1
    assert stage.exists() and not source.exists()
    # Oversized data must not authorize a move or consume unbounded input.
    journal.write_bytes(b'x' * (r._MAX_JOURNAL_BYTES + 1))
    assert recover_interrupted_stage_moves(str(stage_parent), dry_run=False)['conflicts'] == 1


def test_changed_journal_is_rejected_by_original_issuance(tmp_path, monkeypatch):
    import tlo_staging_recovery as r
    source = tmp_path/'original'/'show'
    source.mkdir(parents=True)
    dest = tmp_path/'dest'
    dest.mkdir()
    stage = dest/'.tlo-partial-1234567890abcdef1234567890abcdef'
    journal = Path(record_same_volume_move(str(source),str(stage),str(dest/'show')))
    source.rename(stage)
    payload = json.loads(journal.read_text())
    payload['source'] = str(tmp_path/'different'/'show')
    journal.write_text(json.dumps(payload))
    monkeypatch.setattr(r, '_pid_is_alive', lambda pid: False)
    assert recover_interrupted_stage_moves(str(dest), dry_run=False)['conflicts'] == 1
    assert stage.exists()


def test_latin_ascii_alias_roundtrip():
    assert standard_ascii_text('Björk') == 'Bjork'
    assert standard_ascii_text('Straßenjungs') == 'Strassenjungs'
