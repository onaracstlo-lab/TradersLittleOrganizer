"""Build 637: name/size duplicates, rename-only release, same-volume SHN holding."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import tlo_github_updates as updater
import tlo_tag_lib as tag
from tlo_path_policy import is_phase1_pruned_directory

pytestmark = pytest.mark.behavior


def test_no_hashing_equal_size_and_nested_names(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / 'tlo-deleteDupes.py'
    spec = importlib.util.spec_from_file_location('dup637', script)
    dup = importlib.util.module_from_spec(spec); spec.loader.exec_module(dup)
    a, b = tmp_path/'a', tmp_path/'b'
    for root, payload in [(a, b'aaaa'), (b, b'bbbb')]:
        (root/'disc').mkdir(parents=True)
        (root/'disc'/'01.shn').write_bytes(payload)
    monkeypatch.setattr(dup.os, 'open', lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected content read')))
    assert dup.compare_directory_trees_for_duplicate_deletion(str(a), str(b)) == (True, '')
    (b/'disc'/'01.shn').write_bytes(b'larger')
    assert dup.compare_directory_trees_for_duplicate_deletion(str(a), str(b))[0] is False


def test_atomic_rename_publishes_without_hardlink(tmp_path, monkeypatch):
    staged, dest = tmp_path/'temporary.pending', tmp_path/'package.zip'
    staged.write_bytes(b'verified')
    monkeypatch.setattr(updater.os, 'link', lambda *a,**k: (_ for _ in ()).throw(AssertionError('hard links forbidden')))
    updater._publish_verified_download(staged, dest)
    assert dest.read_bytes() == b'verified' and not staged.exists()


def test_atomic_rename_does_not_overwrite_racing_file(tmp_path):
    staged, dest = tmp_path/'temporary.pending', tmp_path/'package.zip'
    staged.write_bytes(b'verified'); dest.write_bytes(b'user file')
    with pytest.raises(FileExistsError):
        updater._publish_verified_download(staged, dest)
    assert dest.read_bytes() == b'user file' and staged.read_bytes() == b'verified'


def _fake_verified_conversion(monkeypatch):
    monkeypatch.setattr(tag, '_bundled_ffmpeg_executable', lambda: '/fake/ffmpeg')
    def run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b'generated flac')
        return SimpleNamespace(returncode=0, stderr='', stdout='')
    monkeypatch.setattr(tag.subprocess, 'run', run)
    monkeypatch.setattr(tag, '_verified_pcm_fingerprint', lambda *_args: ('abc', 4096))


def test_shn_native_trash_failure_uses_same_volume_holding(tmp_path, monkeypatch):
    _fake_verified_conversion(monkeypatch)
    import tlo_corruption
    monkeypatch.setattr(tlo_corruption, 'move_to_trash', lambda p: (_ for _ in ()).throw(OSError('not supported')))
    src = tmp_path/'track.shn'; src.write_bytes(b'original shn')
    lines = []
    dest = tag.convert_shn_to_flac(str(src), emit=lines.append)
    originals = list((tmp_path/'.tlo-shn-originals').glob('*/track.shn'))
    assert Path(dest).exists() and not src.exists()
    assert len(originals) == 1 and originals[0].read_bytes() == b'original shn'
    assert originals[0].name == 'track.shn' and len(originals[0].parent.name) == 32
    assert 'original=' + str(originals[0]) in lines[-1]
    assert is_phase1_pruned_directory('.tlo-shn-originals')
    assert originals[0].stat().st_dev == Path(dest).stat().st_dev


def test_shn_holding_collision_preserves_prior_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tag.uuid, 'uuid4', lambda: SimpleNamespace(hex='fixed'))
    holder=tmp_path/'.tlo-shn-originals';holder.mkdir()
    (holder/'fixed').mkdir()
    old=holder/'fixed'/'track.shn';old.write_bytes(b'old')
    src=tmp_path/'track.shn';src.write_bytes(b'new')
    with pytest.raises(tag.TaggerError, match='collision-free'):
        tag._hold_converted_shn_original(str(src))
    assert old.read_bytes() == b'old' and src.read_bytes() == b'new'


def test_shn_holding_unavailable_preserves_original_and_removes_flac(tmp_path, monkeypatch):
    _fake_verified_conversion(monkeypatch)
    import tlo_corruption
    monkeypatch.setattr(tlo_corruption, 'move_to_trash', lambda p: (_ for _ in ()).throw(OSError('no Trash')))
    src=tmp_path/'track.shn';src.write_bytes(b'original shn')
    (tmp_path/'.tlo-shn-originals').write_text('not a directory')
    with pytest.raises(tag.TaggerError):
        tag.convert_shn_to_flac(str(src))
    assert src.read_bytes() == b'original shn'
    assert not (tmp_path/'track.flac').exists()


def test_shn_holding_does_not_follow_symlink(tmp_path):
    outside=tmp_path/'outside';outside.mkdir()
    holder=tmp_path/'.tlo-shn-originals'
    try: holder.symlink_to(outside, target_is_directory=True)
    except OSError: pytest.skip('symlinks unavailable')
    src=tmp_path/'track.shn';src.write_bytes(b'original')
    with pytest.raises(tag.TaggerError, match='symbolic link'):
        tag._hold_converted_shn_original(str(src))
    assert src.read_bytes() == b'original' and list(outside.iterdir()) == []


def test_duplicate_collision_naming_uses_names_sizes_not_bytes(tmp_path):
    import tlo_tag_lib as tag_lib
    dest=tmp_path/'dest';dest.mkdir()
    existing=dest/'Artist 2000-01-01 Venue City ST'; existing.mkdir()
    incoming=tmp_path/'incoming'; incoming.mkdir()
    (existing/'01.flac').write_bytes(b'AAAA')
    (incoming/'01.flac').write_bytes(b'BBBB')
    assert tag_lib._unique_destination_path(str(dest), existing.name, str(incoming)).endswith(' (copy1)')


def test_update_download_no_rename_overwrite_after_staging(tmp_path, monkeypatch):
    import hashlib
    payload=b'verified zip data'
    asset={'name':'release.zip','browser_download_url':'https://github.com/a/b',
           'size':len(payload),'digest':'sha256:'+hashlib.sha256(payload).hexdigest()}
    monkeypatch.setattr(updater,'_downloads_dir',lambda:tmp_path)
    monkeypatch.setattr(updater,'_download_asset',lambda _a,d:d.write_bytes(payload))
    monkeypatch.setattr(updater,'_inspect_downloaded_package',lambda *a,**k:{'databases_included':False,'packaging_mode':'test'})
    monkeypatch.setattr(updater,'_update_download_settings',lambda *a,**k:'')
    dest=tmp_path/'release.zip'
    original_publish=updater._publish_verified_download
    def racing_publish(stage,final):
        final.write_bytes(b'foreign')
        original_publish(stage,final)
    monkeypatch.setattr(updater,'_publish_verified_download',racing_publish)
    with pytest.raises(FileExistsError):
        updater._download_and_report_verified_asset(asset,tlo_home=None,latest_build=637,
            asset_name='release.zip',package_kind='update',platform_key='windows')
    assert dest.read_bytes()==b'foreign'
    assert list(tmp_path.iterdir())==[dest]


def test_shn_native_trash_noop_uses_holding(tmp_path,monkeypatch):
    _fake_verified_conversion(monkeypatch)
    import tlo_corruption
    monkeypatch.setattr(tlo_corruption,'move_to_trash',lambda _p: None)
    src=tmp_path/'silent.shn';src.write_bytes(b'recoverable')
    target=tag.convert_shn_to_flac(str(src))
    assert Path(target).exists() and not src.exists()
    assert next((tmp_path/'.tlo-shn-originals').glob('*/silent.shn')).read_bytes() == b'recoverable'
