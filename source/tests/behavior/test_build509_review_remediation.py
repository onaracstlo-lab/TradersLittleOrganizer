import inspect
import os
import subprocess
import sys
import time
import zipfile

import pytest

pytestmark = pytest.mark.behavior

import tlo_copy_requests as CR
import tlo_github_updates as GU
import tlo_inventory_update as IU
import tlo_setlistfm_lookup as SFM
import tlo_text_utils as TU


def test_build509_pid_liveness_has_windows_specific_path_and_live_dead_distinction():
    source = inspect.getsource(CR._pid_is_alive)
    assert 'OpenProcess' in source and 'GetExitCodeProcess' in source and 'os.name == "nt"' in source
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])
    try:
        assert CR._pid_is_alive(child.pid) is True
    finally:
        child.kill(); child.wait()
    time.sleep(0.05)
    assert CR._pid_is_alive(child.pid) is False


def test_build509_owner_identity_rejects_recycled_pid(monkeypatch):
    payload = {'hostname': CR.socket.gethostname(), 'pid': os.getpid(), 'process_start_token': 'old-token'}
    monkeypatch.setattr(CR, '_pid_is_alive', lambda _pid: True)
    monkeypatch.setattr(CR, '_process_start_token', lambda _pid: 'new-token')
    assert CR._owner_is_live(payload) is False


def test_build509_rtf_symbol_words_are_preserved(tmp_path):
    p = tmp_path / 's.rtf'
    p.write_bytes(rb'{\rtf1\ansi Guns N\rquote Roses\par Madison\~Square\~Garden\par 01\emdash Intro\par \ldblquote Sweet Child\rdblquote\par}')
    text = TU.read_text_file_full(str(p))
    assert "Guns N'Roses" in text
    assert 'Madison Square Garden' in text
    assert '01-Intro' in text
    assert '"Sweet Child"' in text


def test_build509_delete_replaced_batch_identifies_volume_and_quotes_paths(tmp_path):
    script = tmp_path / 'deleteReplacedFolders.bat'
    assert IU._append_delete_command(str(script), r'E:\Simon & Garfunkel 100% Live ^ Set', 'Backup & One')
    assert IU._append_delete_command(str(script), r'F:\Unlabeled Show', '')
    body = script.read_text(encoding='utf-8')
    assert 'vol E:' not in body and 'findstr' not in body
    assert 'REM [Backup & One] "E:\\Simon & Garfunkel 100%% Live ^ Set"' in body
    assert 'rmdir /s /q "E:\\Simon & Garfunkel 100%% Live ^ Set"' in body
    assert 'REM [] "F:\\Unlabeled Show"' in body
    assert 'rmdir /s /q "F:\\Unlabeled Show"' in body
    assert '^&' not in body


def test_build509_windows_cleanup_script_name(monkeypatch, tmp_path):
    monkeypatch.setattr(IU.os, 'name', 'nt', raising=False)
    assert IU.updater_delete_script_path(str(tmp_path)).endswith('deleteReplacedFolders.bat')


def test_build509_wsl_label_probe_prefers_powershell(tmp_path):
    script = tmp_path / 'deleteBackupFolders.sh'
    IU._append_delete_command(str(script), '/mnt/e/Show', 'Backup')
    body = script.read_text(encoding='utf-8')
    assert body.index('powershell.exe') < body.index('findmnt')


def test_build509_normal_setlist_key_validation_happens_before_rate_slot(monkeypatch):
    called = {'rate': False}
    monkeypatch.setattr(SFM, 'wait_for_rate_limit', lambda *a, **k: called.__setitem__('rate', True))
    with pytest.raises(SFM.SetlistFMError, match='invalid characters'):
        SFM.api_get('/search/setlists', {'artistName': 'x'}, 'abc\u201d')
    assert called['rate'] is False


def test_build509_zip_rejects_duplicate_ads_and_windows_device_names(tmp_path):
    cases = [
        [('a.txt', b'1'), ('a.txt', b'2')],
        [('folder/file.txt:stream', b'x')],
        [('CON.txt', b'x')],
        [('folder/name. ', b'x')],
    ]
    for index, members in enumerate(cases):
        path = tmp_path / f'bad{index}.zip'
        with zipfile.ZipFile(path, 'w') as zf:
            for name, data in members:
                zf.writestr(name, data)
        with zipfile.ZipFile(path) as zf:
            with pytest.raises(ValueError):
                GU._validate_zip_members(zf)
