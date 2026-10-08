"""Build 563: live staged Copy/Delete Original, verification and recovery."""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def setup_show(tmp_path):
    src = tmp_path / 'source' / 'Artist 2001-01-01 Venue'
    parent = tmp_path / 'dest'
    src.mkdir(parents=True)
    parent.mkdir()
    (src / 'disc1').mkdir()
    (src / 'disc1' / '01.flac').write_bytes(b'audio!' * 30)
    (src / 'empty').mkdir()
    group = {'main_dir_path':str(src), 'main_dir_name':src.name, 'music_dirs':[str(src/'disc1')], 'music_files':[str(src/'disc1'/'01.flac')], 'setlist_files':[], 'txt_files':[]}
    rec = SimpleNamespace(main_dir_path=str(src),main_dir_name=src.name,show_name=src.name,parentheticals='',setlist_file='',music_dirs=[str(src/'disc1')],setlist_files=[])
    conf=SimpleNamespace(tag_copy_and_delete_path=str(parent),rename_compliantly=False)
    return src,parent,group,rec,conf


def test_cross_volume_full_verification_in_stage_before_publish_or_delete(tmp_path, monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:False)
    steps=[]
    size=t._verify_copy_by_file_size
    sha=t._verify_copy_exact
    pub=t._publish_staged_directory_noreplace
    def verify_size(a,b):
        assert src.is_dir() and Path(b).name.startswith('.tlo-partial-')
        assert not (dst/src.name).exists()
        steps.append('size')
        return size(a,b)
    def verify_hash(a,b):
        assert steps == ['size'] and src.is_dir() and not (dst/src.name).exists()
        steps.append('sha256')
        return sha(a,b)
    def publish(a,b):
        assert steps == ['size','sha256'] and src.is_dir()
        steps.append('publish')
        return pub(a,b)
    monkeypatch.setattr(t,'_verify_copy_by_file_size',verify_size)
    monkeypatch.setattr(t,'_verify_copy_exact',verify_hash)
    monkeypatch.setattr(t,'_publish_staged_directory_noreplace',publish)
    result,record=t.prepare_inventory_copy_delete_target(c,g,r)
    assert steps == ['size','sha256','publish']
    assert not src.exists() and (dst/src.name/'empty').is_dir()
    assert result['main_dir_path']==record.main_dir_path==str(dst/src.name)
    assert result['music_files']==[str(dst/src.name/'disc1'/'01.flac')]
    assert not list(dst.glob('.tlo-partial-*'))


def test_cross_volume_hash_mismatch_keeps_source_and_no_published_tree(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:False)
    def fail_hash(a,b):
        assert src.exists() and Path(b).name.startswith('.tlo-partial-')
        raise t.TaggerError('SHA-256 mismatch')
    monkeypatch.setattr(t,'_verify_copy_exact',fail_hash)
    with pytest.raises(t.TaggerError,match='SHA-256'):
        t.prepare_inventory_copy_delete_target(c,g,r)
    assert (src/'disc1'/'01.flac').exists()
    assert list(dst.iterdir()) == []


def test_cross_volume_cancellation_cleans_owned_partial_and_preserves_source(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:False)
    def partial(a,b):
        Path(b,'incomplete.bin').write_bytes(b'part')
        raise InterruptedError('cancelled')
    monkeypatch.setattr(t,'_copy_tree_into_reserved_directory',partial)
    with pytest.raises(t.TaggerError,match='cancelled'):
        t.prepare_inventory_copy_delete_target(c,g,r)
    assert src.exists() and list(dst.iterdir())==[]


def test_cross_volume_abrupt_worker_exit_leaves_pruned_stage(tmp_path):
    src,dst,g,r,c=setup_show(tmp_path)
    script='''import os,sys
import tlo_tag_lib as t
from types import SimpleNamespace
source,dest=sys.argv[1:]
t._paths_on_same_filesystem=lambda *_:False
def die(_s,stage):
    with open(os.path.join(stage,'partial.flac'),'wb') as f:f.write(b'half')
    os._exit(49)
t._copy_tree_into_reserved_directory=die
r=SimpleNamespace(main_dir_path=source,show_name=os.path.basename(source),main_dir_name=os.path.basename(source),parentheticals='',setlist_file='',music_dirs=[],setlist_files=[])
t.prepare_inventory_copy_delete_target(SimpleNamespace(tag_copy_and_delete_path=dest,rename_compliantly=False),{'main_dir_path':source},r)
'''
    p=subprocess.run([sys.executable,'-c',script,str(src),str(dst)],cwd=Path(__file__).resolve().parents[2],timeout=15,check=False,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    assert p.returncode==49
    assert src.exists() and not (dst/src.name).exists()
    staging=list(dst.glob('.tlo-partial-*'))
    assert len(staging)==1 and (staging[0]/'partial.flac').read_bytes()==b'half'
    from tlo_path_policy import is_phase1_pruned_directory
    assert is_phase1_pruned_directory(staging[0].name)


def test_same_volume_move_is_atomic_through_staging_without_copy_or_hash(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:True)
    monkeypatch.setattr(t,'_copy_tree_into_reserved_directory',lambda *_:(_ for _ in ()).throw(AssertionError('must rename not copy')))
    monkeypatch.setattr(t,'_verify_copy_exact',lambda *_:(_ for _ in ()).throw(AssertionError('must not SHA256 verify same-volume move')))
    calls=[]
    publish=t._publish_staged_directory_noreplace
    def track(a,b):
        calls.append((a,b))
        return publish(a,b)
    monkeypatch.setattr(t,'_publish_staged_directory_noreplace',track)
    result,record=t.prepare_inventory_copy_delete_target(c,g,r)
    assert len(calls)==2
    assert calls[0][0]==str(src) and Path(calls[0][1]).name.startswith('.tlo-partial-')
    assert calls[1][0]==calls[0][1] and calls[1][1]==str(dst/src.name)
    assert not src.exists() and not list(dst.glob('.tlo-partial-*'))
    assert result['main_dir_path']==record.main_dir_path==str(dst/src.name)


def test_same_volume_publish_failure_rolls_back_source(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:True)
    def fail(*_args):
        assert not src.exists() and len(list(dst.glob('.tlo-partial-*')))==1
        raise t.TaggerError('failed publication')
    monkeypatch.setattr(t,'_publish_verified_transfer',fail)
    with pytest.raises(t.TaggerError,match='failed publication'):
        t.prepare_inventory_copy_delete_target(c,g,r)
    assert (src/'disc1'/'01.flac').exists() and list(dst.iterdir())==[]


def test_same_volume_collision_race_keeps_existing_foreign_directory(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:True)
    publish=t._publish_staged_directory_noreplace
    n=[0]
    def race(stage,target):
        if str(stage).startswith(str(dst)) and n[0]==0:
            n[0]+=1
            Path(target).mkdir()
            (Path(target)/'other.txt').write_bytes(b'not ours')
        return publish(stage,target)
    monkeypatch.setattr(t,'_publish_staged_directory_noreplace',race)
    result,_=t.prepare_inventory_copy_delete_target(c,g,r)
    assert n==[1] and (dst/src.name/'other.txt').read_bytes()==b'not ours'
    assert Path(result['main_dir_path']).name.endswith('(alt1)')
    assert not src.exists() and not list(dst.glob('.tlo-partial-*'))


def test_same_volume_abrupt_worker_exit_still_has_complete_recoverable_tree(tmp_path):
    src,dst,g,r,c=setup_show(tmp_path)
    script='''import os,sys
import tlo_tag_lib as t
from types import SimpleNamespace
source,dest=sys.argv[1:]
t._paths_on_same_filesystem=lambda *_:True
def die(*_):
    os._exit(57)
t._publish_verified_transfer=die
r=SimpleNamespace(main_dir_path=source,show_name=os.path.basename(source),main_dir_name=os.path.basename(source),parentheticals='',setlist_file='',music_dirs=[],setlist_files=[])
t.prepare_inventory_copy_delete_target(SimpleNamespace(tag_copy_and_delete_path=dest,rename_compliantly=False),{'main_dir_path':source},r)
'''
    p=subprocess.run([sys.executable,'-c',script,str(src),str(dst)],cwd=Path(__file__).resolve().parents[2],timeout=15,check=False,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    assert p.returncode==57 and not src.exists() and not (dst/src.name).exists()
    staging=list(dst.glob('.tlo-partial-*'))
    assert len(staging)==1 and (staging[0]/'disc1'/'01.flac').read_bytes()==b'audio!'*30
    from tlo_path_policy import is_phase1_pruned_directory
    assert is_phase1_pruned_directory(staging[0].name)


def test_same_volume_failed_rollback_reports_recovery_path(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:True)
    monkeypatch.setattr(t,'_publish_verified_transfer',lambda *_:(_ for _ in ()).throw(t.TaggerError('no publish')))
    publish=t._publish_staged_directory_noreplace
    def fail_rollback(a,b):
        if b == str(src):
            raise OSError('rollback impossible')
        return publish(a,b)
    monkeypatch.setattr(t,'_publish_staged_directory_noreplace',fail_rollback)
    with pytest.raises(t.TaggerError,match='source rollback failed.*excluded staging folder'):
        t.prepare_inventory_copy_delete_target(c,g,r)
    assert not src.exists()
    staging=list(dst.glob('.tlo-partial-*'))
    assert len(staging)==1 and (staging[0]/'disc1'/'01.flac').exists()


def test_copy_delete_rejects_source_symlinks_before_move(tmp_path,monkeypatch):
    import tlo_tag_lib as t
    src,dst,g,r,c=setup_show(tmp_path)
    try:
        (src/'link').symlink_to(src/'disc1',target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip('symlinks not supported')
    monkeypatch.setattr(t,'_paths_on_same_filesystem',lambda *_:True)
    with pytest.raises(t.TaggerError,match='symbolic links'):
        t.prepare_inventory_copy_delete_target(c,g,r)
    assert src.exists() and not list(dst.iterdir())
