"""Build 722: native Windows Recycle Bin defaults and duplicate operations."""
from __future__ import annotations

import base64
import re
import sys

import pytest

import tlo_corruption as C
import tlo_inventory_update as IU

pytestmark = pytest.mark.behavior


class _Key:
    def __init__(self, values):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def _registry(monkeypatch, values=None, *, missing=False, inaccessible=False):
    class Fake:
        HKEY_CURRENT_USER = 1
        HKEY_LOCAL_MACHINE = 2

        @staticmethod
        def OpenKey(_hive, name):
            if 'Policies' in name or missing:
                raise FileNotFoundError(name)
            if inaccessible:
                raise PermissionError(name)
            return _Key(values or {})

        @staticmethod
        def QueryValueEx(key, name):
            if name not in key.values:
                raise FileNotFoundError(name)
            return (key.values[name], 4)

    monkeypatch.setitem(sys.modules, 'winreg', Fake)


GUID = '\\\\?\\Volume{12345678-0000-0000-0000-123456789012}\\'


def test_missing_volume_key_uses_native_recycle_defaults(monkeypatch):
    _registry(monkeypatch, missing=True)
    C._windows_recycle_policy('C:\\', GUID, 123, 0)


def test_missing_individual_values_use_native_recycle_defaults(monkeypatch):
    _registry(monkeypatch)
    C._windows_recycle_policy('C:\\', GUID, 123, 0)


def test_explicit_permanent_delete_and_quota_still_block(monkeypatch):
    _registry(monkeypatch, {'NukeOnDelete': 1})
    with pytest.raises(C._RecycleUnavailable, match='disabled'):
        C._windows_recycle_policy('C:\\', GUID, 1, 0)
    _registry(monkeypatch, {'NukeOnDelete': 0, 'MaxCapacity': 1})
    with pytest.raises(C._RecycleUnavailable, match='quota'):
        C._windows_recycle_policy('C:\\', GUID, 2 * 1024 * 1024, 0)


def test_registry_access_denied_still_blocks(monkeypatch):
    _registry(monkeypatch, inaccessible=True)
    with pytest.raises(C._RecycleUnavailable, match='inspect'):
        C._windows_recycle_policy('C:\\', GUID, 123, 0)


def test_new_duplicate_not_deleted_on_recycle_failure(monkeypatch, tmp_path):
    folder = tmp_path / 'new show'
    folder.mkdir()
    (folder / '01.flac').write_bytes(b'keep')

    def reject(path):
        assert path == str(folder)
        raise C._RecycleUnavailable('recycling blocked')

    monkeypatch.setattr(IU, 'move_to_trash', reject)
    with pytest.raises(IU.InventoryUpdateError, match='remains in place'):
        IU.delete_new_keep_old({'folder': str(folder)})
    assert (folder / '01.flac').read_bytes() == b'keep'


def test_old_duplicate_batch_is_permanent_rmdir_and_label_guarded(tmp_path):
    script = tmp_path / 'deleteReplacedFolders.bat'
    assert IU._append_delete_command(str(script), r'D:\\Backup Shows\\My Band (alt1)', 'Backup Disk')
    body = script.read_text(encoding='utf-8')
    assert 'rmdir /s /q "%TLO_DELETE_TARGET%"' in body
    assert 'Remove-Item' not in body
    assert 'TLO_DELETE_LABEL_B64' in body
    encoded = re.search(r'-EncodedCommand ([A-Za-z0-9+/=]+)', body).group(1)
    payload = base64.b64decode(encoded).decode('utf-16le')
    assert 'SendToRecycleBin' not in payload
    assert 'DriveInfo' in payload and '[StringComparison]::Ordinal' in payload
    assert '$env:TLO_DELETE_TARGET' in payload
    assert 'rmdir' not in payload and 'Remove-Item' not in payload
    assert '[IO.FileAttributes]::ReparsePoint' in payload


def test_unlabeled_old_duplicate_never_gets_a_recycle_command(tmp_path):
    script = tmp_path / 'deleteReplacedFolders.bat'
    assert IU._append_delete_command(str(script), r'F:\\Unlabeled Show', '')
    body = script.read_text(encoding='utf-8')
    assert 'SKIPPED: unlabeled volume' in body
    assert '-EncodedCommand ' not in body
    assert 'rmdir /s /q' not in body
