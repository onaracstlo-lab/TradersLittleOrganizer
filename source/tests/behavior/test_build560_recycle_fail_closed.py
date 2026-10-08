"""Build 560: prevent corruption cleanup from attempting permanent deletion."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

import tlo_corruption as C

pytestmark = pytest.mark.behavior


class _Log:
    def __init__(self):
        self.messages = []

    def conflicts(self, fmt, *args):
        self.messages.append(fmt % args)

    def tag(self, fmt, *args):
        self.messages.append(fmt % args)


def _assessment(paths, action, policy='delete', folders=None):
    return C.CorruptionAssessment(
        audio_files=list(paths), corrupt_files=list(paths), action=action,
        corruption_percent=100, corrupt_files_policy=policy,
        corrupt_folders_policy='all', folder_threshold=100,
        folder_candidates=list(folders or []),
    )


def _group(folder, bads):
    return {'main_dir_path': str(folder), 'music_dirs': [str(folder)],
            'music_files': list(map(str, bads)), 'music_sample_files': [],
            'setlist_files': [], 'txt_files': [], 'setlist_file': ''}


def _record(folder):
    return SimpleNamespace(main_dir_path=str(folder), music_dirs=[str(folder)],
                           music_file_count=1, setlist_files=[], setlist_file='')


def test_windows_entrypoint_preflights_before_any_shell_com(monkeypatch, tmp_path):
    path = tmp_path / 'retained.flac'
    path.write_bytes(b'original')
    def reject(_path):
        raise C._RecycleUnavailable('No Recycle Bin: keep and report')
    monkeypatch.setattr(C, '_windows_recycle_preflight', reject)
    with pytest.raises(C._RecycleUnavailable, match='keep and report'):
        C._trash_windows(str(path))
    assert path.read_bytes() == b'original'


def test_preflight_is_not_available_outside_native_windows(tmp_path):
    if os.name == 'nt':
        pytest.skip('non-Windows protective branch')
    path = tmp_path / 'retained.flac'
    path.write_bytes(b'keep')
    with pytest.raises(C._RecycleUnavailable, match='native Windows'):
        C._windows_recycle_preflight(str(path))
    assert path.read_bytes() == b'keep'


def test_preflight_size_rejects_symlinks_and_unbounded_tree(tmp_path, monkeypatch):
    base = tmp_path / 'dir'
    base.mkdir()
    (base / 'file').write_bytes(b'12345')
    assert C._recycle_candidate_size(str(base)) == 5
    link = base / 'link'
    try:
        link.symlink_to(base / 'file')
    except OSError:
        pytest.skip('cannot create symlinks')
    with pytest.raises(C._RecycleUnavailable, match='symlink'):
        C._recycle_candidate_size(str(base))


def test_disabled_per_volume_registry_setting_blocks_deletion(monkeypatch):
    class Key:
        def __init__(self, name): self.name = name
        def __enter__(self): return self
        def __exit__(self, *args): return None

    def open_key(hive, name):
        if 'Policies' in name:
            raise FileNotFoundError(name)
        return Key(name)

    class FakeRegistry:
        HKEY_CURRENT_USER = 1
        HKEY_LOCAL_MACHINE = 2
        OpenKey = staticmethod(open_key)

        @staticmethod
        def QueryValueEx(key, name):
            return ({'NukeOnDelete': 1, 'MaxCapacity': 200}[name], 4)

    monkeypatch.setitem(sys.modules, 'winreg', FakeRegistry)
    with pytest.raises(C._RecycleUnavailable, match='disabled for this volume'):
        C._windows_recycle_policy('C:\\', '\\\\?\\Volume{12345678-0000-0000-0000-123456789012}\\', 42, 0)


def test_capacity_and_missing_registry_fail_closed(monkeypatch):
    class Key:
        def __init__(self, name): self.name = name
        def __enter__(self): return self
        def __exit__(self, *args): return None

    class FakeRegistry:
        HKEY_CURRENT_USER = 1
        HKEY_LOCAL_MACHINE = 2

        @staticmethod
        def OpenKey(hive, name):
            if 'Policies' in name: raise FileNotFoundError(name)
            return Key(name)

        @staticmethod
        def QueryValueEx(key, name):
            return ({'NukeOnDelete': 0, 'MaxCapacity': 1}[name], 4)

    monkeypatch.setitem(sys.modules, 'winreg', FakeRegistry)
    guid = '\\\\?\\Volume{12345678-0000-0000-0000-123456789012}\\'
    with pytest.raises(C._RecycleUnavailable, match='quota'):
        C._windows_recycle_policy('C:\\', guid, 512 * 1024, 700 * 1024)
    FakeRegistry.OpenKey = staticmethod(lambda hive, name: (_ for _ in ()).throw(FileNotFoundError(name)))
    with pytest.raises(C._RecycleUnavailable, match='cannot be confirmed'):
        C._windows_recycle_policy('C:\\', guid, 1, 0)


def test_policy_avoids_permanent_deletion_for_group_when_recycle_fails(monkeypatch, tmp_path):
    folder = tmp_path / 'show'
    folder.mkdir()
    file = folder / '01.flac'
    file.write_bytes(b'original')
    attempts = []
    def fail(path):
        attempts.append(path)
        raise C._RecycleUnavailable('no recycling possible')
    monkeypatch.setattr(C, 'move_to_trash', fail)
    assessment = _assessment([str(file)], 'trash_folder_all_corrupt')
    logs = _Log()
    out = C.apply_corruption_assessment(SimpleNamespace(logs=logs), _group(folder, [file]),
                                         _record(folder), assessment)
    assert attempts == [str(folder)]  # No secondary file-level Trash fallback
    assert out.unverifiable
    assert out.whole_folder_trash_failed
    assert not out.show_removed
    assert file.read_bytes() == b'original'
    assert any('CORRUPTION_REMOVAL_FAILED' in x for x in logs.messages)


def test_file_failure_marks_unverifiable_and_skips_remaining(monkeypatch, tmp_path):
    folder = tmp_path / 'show'
    folder.mkdir()
    files = [folder / f'0{i}.flac' for i in (1, 2)]
    for f in files: f.write_bytes(b'original')
    attempts = []
    def fail(path):
        attempts.append(path)
        raise C._RecycleUnavailable('quota unavailable')
    monkeypatch.setattr(C, 'move_to_trash', fail)
    assessment = _assessment(list(map(str, files)), 'trash_corrupt_files')
    out = C.apply_corruption_assessment(SimpleNamespace(logs=_Log()), _group(folder, files),
                                         _record(folder), assessment)
    assert out.unverifiable and len(attempts) == 1
    assert all(f.read_bytes() == b'original' for f in files)


def test_legacy_windows_flags_do_not_auto_confirm_permanent_delete():
    import inspect
    body = inspect.getsource(C._trash_windows)
    assert 'FOFX_RECYCLEONDELETE' in body
    assert 'FOFX_EARLYFAILURE' in body
    assert 'FOF_NOCONFIRMATION' not in body
    assert '_windows_recycle_preflight(path)' in body


@pytest.mark.skipif(sys.platform != 'win32', reason='requires native Windows with real Recycle Bin')
def test_native_windows_unavailable_recycle_bin_does_not_delete_real_file(tmp_path):
    # The clean Linux build cannot claim an end-to-end Windows COM execution.
    # Manually exercise this on fixed / removable / Recycle Bin disabled volumes.
    f = tmp_path / 'real-test-file.flac'
    f.write_bytes(b'do-not-delete')
    # Never attempt to recycle this fixture on a machine where the preflight
    # succeeds: the native integration contract is negative-path only.
    try:
        C._windows_recycle_preflight(str(f))
    except C._RecycleUnavailable:
        assert f.read_bytes() == b'do-not-delete'
    else:
        assert f.read_bytes() == b'do-not-delete'
