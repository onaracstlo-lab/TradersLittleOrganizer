"""Build 563: generated Windows cleanup .bat volume-label fail-closed rules."""
from __future__ import annotations

import base64
import os
import re
import subprocess
from pathlib import Path

import pytest

import tlo_inventory_update as IU

pytestmark = pytest.mark.behavior


def _make(tmp_path: Path, *entries: tuple[str, str]) -> str:
    script = tmp_path / "deleteReplacedFolders.bat"
    for path, label in entries:
        assert IU._append_delete_command(str(script), path, label)
    return script.read_text(encoding="utf-8")


def _active_delete_lines(script: str) -> list[str]:
    return [line for line in script.splitlines() if line.lstrip().lower().startswith("rmdir /s /q ")]


def test_build559_labeled_volume_uses_encoded_exact_predelete_guard(tmp_path: Path):
    label = 'Backups & One (100%) | Croissants café ^ "Quoted"'
    path = r'D:\Live Archive\Grateful Dead (1977) 100%'
    text = _make(tmp_path, (path, label))
    expected_base64 = base64.b64encode(label.encode('utf-16le')).decode('ascii')
    assert f'set "TLO_DELETE_LABEL_B64={expected_base64}"' in text
    assert f'set "TLO_DELETE_TARGET={IU._batch_escape_literal(path)}"' in text
    assert 'set "TLO_DELETE_DRIVE=%TLO_DELETE_TARGET:~0,1%"' in text
    assert '[System.IO.DriveInfo]::new(' in text
    assert '[StringComparison]::Ordinal' in text
    assert 'IsNullOrEmpty($actual)' in text
    assert '-NoProfile -NonInteractive -Command' in text
    assert '%__APPDIR__%WindowsPowerShell\\v1.0\\powershell.exe' in text
    assert len(_active_delete_lines(text)) == 1
    assert text.index('if errorlevel 1 goto :TLO_SKIP_') < text.index(_active_delete_lines(text)[0])
    assert '100%%' in text
    assert text.count('TLO_DELETE_TARGET') >= 5
    # The drive probe and rmdir both consume the same editable path variable.
    assert 'set "TLO_DELETE_DRIVE=%TLO_DELETE_TARGET:~0,1%"' in text
    assert 'rmdir /s /q "%TLO_DELETE_TARGET%"' in text
    # Actual commands contain no untrusted label, only an encoded value.
    for line in text.splitlines():
        if not line.lstrip().startswith('REM'):
            assert label not in line
    assert '\r\n' in (tmp_path / 'deleteReplacedFolders.bat').read_bytes().decode('utf-8')


def test_build559_unlabeled_records_are_non_destructive(tmp_path: Path):
    text = _make(tmp_path, (r'F:\Music Folder', ''))
    assert 'REM "[]" "F:\\Music Folder"' in text
    assert 'SKIPPED: unlabeled volume' in text
    assert 'REM rmdir /s /q "F:\\Music Folder"' in text
    assert not _active_delete_lines(text)
    assert 'TLO_DELETE_LABEL_B64=' not in text


def test_build559_each_volume_is_checked_independently(tmp_path: Path):
    entries = [(r'E:\Music\A', 'Primary'), (r'F:\Music\B', ''), (r'G:\Music\C', 'Secondary')]
    text = _make(tmp_path, *entries)
    assert len(_active_delete_lines(text)) == 2
    assert text.count('set "TLO_DELETE_TARGET=') == 2
    assert text.count('set "TLO_DELETE_DRIVE=%TLO_DELETE_TARGET:~0,1%"') == 2
    assert text.count('if errorlevel 1 goto :TLO_SKIP_') == 2
    tokens = re.findall(r':TLO_SKIP_([0-9a-f]{32})', text)
    assert len(set(tokens)) == 2
    for token in set(tokens):
        assert text.count(f':TLO_SKIP_{token}') == 3  # two gotos plus label
        assert text.count(f':TLO_DONE_{token}') == 2  # goto plus label
    assert 'REM rmdir /s /q "F:\\Music\\B"' in text


def test_build559_wsl_paths_translate_for_windows_guard(tmp_path: Path):
    text = _make(tmp_path, ('/mnt/e/boots/Good Show', 'Juke 4'))
    assert 'set "TLO_DELETE_TARGET=E:\\boots\\Good Show"' in text
    assert 'rmdir /s /q "%TLO_DELETE_TARGET%"' in text


def test_build559_source_volume_label_does_not_inject_exec_syntax(tmp_path: Path):
    label = 'X & echo INJECTED | ( A < B > C ) ^ 50% " quote'
    text = _make(tmp_path, (r'Z:\Missing Archive', label))
    executable = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('REM'))
    assert 'INJECTED' not in executable
    assert '[X & echo INJECTED' in text  # visible, non-executable comment
    assert 'TLO_DELETE_LABEL_B64=' in executable


@pytest.mark.skipif(os.name != 'nt', reason='cmd.exe and actual-volume verification require native Windows')
def test_build559_wrong_label_never_deletes_and_correct_label_can_delete(tmp_path: Path):
    # The test deletes only its own disposable child directory, never another path.
    import ctypes
    from ctypes import wintypes
    drive = os.path.splitdrive(str(tmp_path))[0]
    if not drive or not os.path.isdir(drive + '\\'):
        pytest.skip('no local rooted test drive')
    buf = ctypes.create_unicode_buffer(256)
    serial = wintypes.DWORD()
    maximum = wintypes.DWORD()
    flags = wintypes.DWORD()
    fs = ctypes.create_unicode_buffer(256)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        drive + '\\', buf, len(buf), ctypes.byref(serial), ctypes.byref(maximum),
        ctypes.byref(flags), fs, len(fs)
    )
    if not ok or not buf.value:
        pytest.skip('test drive has no verifiable volume label')
    comspec = os.environ.get('ComSpec', r'C:\Windows\System32\cmd.exe')
    victim = tmp_path / 'disposable live show'
    victim.mkdir()
    (victim / 'song.txt').write_text('fixture')
    bad = _make(tmp_path, (str(victim), buf.value + '-DEFINITELY-NOT-THIS-LABEL'))
    assert 'rmdir' in bad
    cmd = [comspec, '/d', '/c', str(tmp_path / 'deleteReplacedFolders.bat')]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=45)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert victim.is_dir(), 'wrong label must never remove directory'
    assert 'SKIPPED' in completed.stdout
    (tmp_path / 'deleteReplacedFolders.bat').unlink()
    _make(tmp_path, (str(victim), buf.value))
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=45)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not victim.exists(), 'actual label match permits approved disposable cleanup'


@pytest.mark.skipif(os.name != 'nt', reason='native Windows required')
def test_build559_unlabeled_entry_never_runs_rmdir_even_if_target_exists(tmp_path: Path):
    target = tmp_path / 'unlabeled must survive'
    target.mkdir()
    _make(tmp_path, (str(target), ''))
    subprocess.run([os.environ.get('ComSpec', 'cmd.exe'), '/d', '/c', str(tmp_path / 'deleteReplacedFolders.bat')],
                   capture_output=True, text=True, check=True, timeout=20)
    assert target.is_dir()


def test_build559_invalid_batch_path_cannot_inject_commands(tmp_path: Path):
    script = tmp_path / 'deleteReplacedFolders.bat'
    assert not IU._append_delete_command(str(script), 'E:\\shows\\ok\r\necho INJECTED', 'Juke')
    assert not IU._append_delete_command(str(script), 'E:\\shows\\bad" & echo INJECTED', 'Juke')
    assert not script.exists()


def test_build559_control_characters_in_recorded_label_cannot_inject_commands(tmp_path: Path):
    body = _make(tmp_path, (r'E:\music\show', 'Juke\r\necho INJECTED'))
    assert 'REM "[Juke??echo INJECTED]"' in body
    assert '\r\necho INJECTED' not in body
