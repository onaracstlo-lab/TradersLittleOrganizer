"""Build 691: Add Shows cross-device transfer must verify all bytes before deletion."""
from pathlib import Path
import errno

import pytest

import tlo_inventory_update as update

pytestmark = pytest.mark.behavior


def tree(tmp_path):
    src = tmp_path / 'source' / 'Music 1997-11-28'
    src.mkdir(parents=True)
    (src / 'disc1').mkdir()
    (src / 'disc1' / '01.flac').write_bytes(b'FLAC' * 100)
    (src / 'notes.txt').write_text('Notes for recording')
    (src / 'empty').mkdir()
    dest = tmp_path / 'destination'
    dest.mkdir()
    return src, dest


def cross_device(monkeypatch):
    monkeypatch.setattr(update, '_move_source_and_target_share_device', lambda *_: False)


def test_verified_cross_device_add_shows_move_copies_all_files_and_empty_folders(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    published = Path(update.move_folder_to(str(src), str(dest)))
    assert published.name == 'Music 1997-11-28'
    assert not src.exists()
    assert (published / 'disc1' / '01.flac').read_bytes() == b'FLAC' * 100
    assert (published / 'notes.txt').read_text() == 'Notes for recording'
    assert (published / 'empty').is_dir()
    assert not list(dest.glob('.tlo-partial-*'))


def test_copy_fails_verification_before_source_delete_or_visible_publication(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    import tlo_tag_lib
    def corrupt(_source, staged, **_kwargs):
        (Path(staged) / 'disc1').mkdir(parents=True)
        (Path(staged) / 'disc1' / '01.flac').write_bytes(b'WRONG' * 80)  # same byte count
        (Path(staged) / 'notes.txt').write_text('Notes for recording')
        (Path(staged) / 'empty').mkdir()
        return staged
    monkeypatch.setattr(update.shutil, 'copytree', corrupt)
    with pytest.raises(tlo_tag_lib.TaggerError, match='SHA-256'):
        update.move_folder_to(str(src), str(dest))
    assert src.is_dir() and (src / 'disc1' / '01.flac').read_bytes() == b'FLAC' * 100
    assert not list(dest.iterdir())


def test_interrupted_copy_never_deletes_source_or_exposes_destination(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    def interrupted(_source, staged, **_kw):
        (Path(staged) / 'only-half').write_bytes(b'partial')
        raise OSError(errno.EIO, 'disk full')
    monkeypatch.setattr(update.shutil, 'copytree', interrupted)
    with pytest.raises(OSError, match='disk full'):
        update.move_folder_to(str(src), str(dest))
    assert src.exists() and len(list(dest.iterdir())) == 0


def test_destination_collision_is_non_overwriting(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    existing = dest / src.name
    existing.mkdir()
    (existing / 'personal.txt').write_text('KEEP')
    published = Path(update.move_folder_to(str(src), str(dest)))
    assert published != existing
    assert (existing / 'personal.txt').read_text() == 'KEEP'
    assert (published / 'notes.txt').exists()


def test_failed_source_cleanup_preserves_verified_copy_with_clear_error(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    orig = update.shutil.rmtree
    def refuse(path, *args, **kwargs):
        if Path(path) == src:
            raise PermissionError('locked source')
        return orig(path, *args, **kwargs)
    monkeypatch.setattr(update.shutil, 'rmtree', refuse)
    with pytest.raises(update.InventoryUpdateError, match='reconcile manually'):
        update.move_folder_to(str(src), str(dest))
    assert src.exists() and (dest / src.name / 'disc1' / '01.flac').exists()


def test_same_device_move_keeps_atomic_rename_and_no_hash_copy(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    monkeypatch.setattr(update, '_move_source_and_target_share_device', lambda *_: True)
    def refuse_copy(*_args, **_kw):
        raise AssertionError('same device must never copy bytes')
    monkeypatch.setattr(update.shutil, 'copytree', refuse_copy)
    result = Path(update.move_folder_to(str(src), str(dest)))
    assert result.exists() and not src.exists()


def test_cross_device_symlink_fails_closed(tmp_path, monkeypatch):
    src, dest = tree(tmp_path)
    cross_device(monkeypatch)
    try:
        (src / 'external').symlink_to(tmp_path / 'source', target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symlink unsupported')
    with pytest.raises(update.InventoryUpdateError, match='symbolic links'):
        update.move_folder_to(str(src), str(dest))
    assert src.exists() and not list(dest.iterdir())
