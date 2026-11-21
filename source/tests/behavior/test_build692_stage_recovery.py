"""Build 692: recover only journaled, inactive same-volume staged moves."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import tlo_tag_lib as tag
from tlo_staging_recovery import recover_interrupted_stage_moves, record_same_volume_move

pytestmark = pytest.mark.behavior


def build_pair(tmp_path):
    original = tmp_path / 'original' / 'Wilco 1997-11-28 Worcester'
    original.mkdir(parents=True)
    (original / 'disc1').mkdir()
    (original / 'disc1' / 'track.flac').write_bytes(b'audio' * 100)
    dest = tmp_path / 'destination'
    dest.mkdir()
    return original, dest


def test_completed_same_volume_move_cleans_durable_record(tmp_path):
    original, dest = build_pair(tmp_path)
    target = tag._move_via_owned_stage(str(original), str(dest), original.name)
    assert Path(target).is_dir() and not original.exists()
    assert list(dest.glob('.tlo-move-*.json')) == []


def test_abrupt_crash_after_first_rename_can_be_recovered_with_reverse_cli(tmp_path):
    original, dest = build_pair(tmp_path)
    script = '''import os,sys
import tlo_tag_lib as tag
source,dest=sys.argv[1:]
def crash(*_args): os._exit(61)
tag._publish_verified_transfer=crash
tag._move_via_owned_stage(source,dest,os.path.basename(source))
'''
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}
    result=subprocess.run([sys.executable, '-c', script, str(original), str(dest)], cwd=root, env=env, timeout=15, check=False)
    assert result.returncode == 61
    assert not original.exists() and len(list(dest.glob('.tlo-partial-*'))) == 1
    assert len(list(dest.glob('.tlo-move-*.json'))) == 1
    preview=subprocess.run([sys.executable, str(root/'tlo-reverse.py'), str(dest), '--recover-staging', '--dry-run'], cwd=root, env=env, capture_output=True, text=True, timeout=15, check=False)
    assert preview.returncode == 0 and 'WOULD_RESTORE' in preview.stdout
    assert not original.exists()
    recovery=subprocess.run([sys.executable, str(root/'tlo-reverse.py'), str(dest), '--recover-staging'],cwd=root,env=env,capture_output=True,text=True,timeout=15,check=False)
    assert recovery.returncode == 0 and 'RESTORED' in recovery.stdout
    assert (original/'disc1'/'track.flac').read_bytes() == b'audio'*100
    assert not list(dest.iterdir())


def test_restoration_refuses_overwrite_of_occupied_original(tmp_path, monkeypatch):
    original, dest = build_pair(tmp_path)
    stage = tag._owned_partial_copy_path(str(dest / original.name))
    journal = record_same_volume_move(str(original),stage,str(dest/original.name))
    tag._publish_staged_directory_noreplace(str(original),stage)
    original.mkdir()
    (original/'different.txt').write_text('KEEP')
    monkeypatch.setattr('tlo_staging_recovery._pid_is_alive',lambda _pid:False)
    emitted=[]
    result=recover_interrupted_stage_moves(str(dest),dry_run=False,emit=emitted.append)
    assert result['conflicts']==1
    assert (original/'different.txt').read_text()=='KEEP'
    assert Path(stage).exists() and Path(journal).exists()


def test_does_not_guess_where_unjournaled_staging_belongs(tmp_path):
    original, dest = build_pair(tmp_path)
    stage=dest/'.tlo-partial-1234567890abcdef1234567890abcdef'
    original.rename(stage)
    msg=[]
    result=recover_interrupted_stage_moves(str(dest),dry_run=False,emit=msg.append)
    assert result['found']==0 and stage.exists()
    assert not original.exists() and 'manual' in msg[0]


def test_active_worker_record_is_never_recovered(tmp_path):
    original,dest=build_pair(tmp_path)
    stage=tag._owned_partial_copy_path(str(dest/original.name))
    journal=record_same_volume_move(str(original),stage,str(dest/original.name))
    tag._publish_staged_directory_noreplace(str(original),stage)
    result=recover_interrupted_stage_moves(str(dest),dry_run=False)
    assert result['conflicts']==1 and not original.exists()
    assert Path(stage).exists() and Path(journal).exists()


def test_malformed_journal_cannot_escape_the_destination(tmp_path):
    original,dest=build_pair(tmp_path)
    stage=tag._owned_partial_copy_path(str(dest/original.name))
    journal=record_same_volume_move(str(original),stage,str(dest/original.name))
    data=json.loads(Path(journal).read_text())
    data['stage']=str(tmp_path/'elsewhere')
    Path(journal).write_text(json.dumps(data))
    result=recover_interrupted_stage_moves(str(dest),dry_run=False)
    assert result['conflicts']==1 and original.exists()


def test_failed_publication_rolls_back_and_removes_journal(tmp_path, monkeypatch):
    original,dest=build_pair(tmp_path)
    def fail(*_args):
        raise tag.TaggerError('synthetic publish error')
    monkeypatch.setattr(tag,'_publish_verified_transfer',fail)
    with pytest.raises(tag.TaggerError,match='synthetic publish error'):
        tag._move_via_owned_stage(str(original),str(dest),original.name)
    assert original.exists() and not list(dest.iterdir())
