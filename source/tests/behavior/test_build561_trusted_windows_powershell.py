"""Build 563: native Windows physical-disk detection cannot execute PATH code."""
import ntpath
import os
from pathlib import Path

import pytest

import tlo_volume_label as volume

pytestmark = pytest.mark.behavior


def test_native_disk_resolution_ignores_planted_current_dir_and_path(monkeypatch, tmp_path):
    planted = tmp_path / 'powershell.exe'
    planted.write_text('untrusted', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.setenv('windir', str(tmp_path))
    monkeypatch.setenv('SystemRoot', str(tmp_path))
    monkeypatch.setattr(volume, 'windows_directory_from_api', lambda: r'C:\Windows')
    monkeypatch.setattr(volume, '_windows_drive_letter_for_path', lambda path: 'F')
    monkeypatch.setattr(volume.shutil, 'which', lambda *a, **k: pytest.fail('PATH search during native disk resolution'))
    seen = []
    def capture(args):
        seen.append(args)
        return '42'
    monkeypatch.setattr(volume, '_run_command', capture)
    assert volume._windows_physical_drive_id(r'F:\Boots') == 'windows-disk:42'
    assert len(seen) == 1
    assert seen[0][0] == r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    assert '-NoProfile' in seen[0]
    assert "-DriveLetter 'F'" in seen[0][-1]
    assert not planted.read_text(encoding='utf-8').startswith('executed')


def test_unavailable_windows_directory_fails_closed_without_path_fallback(monkeypatch):
    def no_api():
        raise OSError('GetSystemWindowsDirectoryW unavailable')
    monkeypatch.setattr(volume, 'windows_directory_from_api', no_api)
    monkeypatch.setattr(volume, '_windows_drive_letter_for_path', lambda path: 'E')
    monkeypatch.setattr(volume.shutil, 'which', lambda *a, **k: pytest.fail('fallback searched PATH'))
    monkeypatch.setattr(volume, '_run_command', lambda *a, **k: pytest.fail('attempted execution'))
    assert volume._windows_physical_drive_id(r'E:\Boots') == ''


@pytest.mark.parametrize('directory', ['Windows', r'\\server\share\Windows', r'\Windows', '', '/tmp/Windows', r'C:Windows'])
def test_malformed_api_directory_is_rejected(monkeypatch, directory):
    monkeypatch.setattr(volume, 'windows_directory_from_api', lambda: directory)
    monkeypatch.setattr(volume, '_windows_drive_letter_for_path', lambda path: 'E')
    monkeypatch.setattr(volume, '_run_command', lambda *a: pytest.fail('untrusted executable launched'))
    assert volume._windows_physical_drive_id(r'E:\show') == ''


def test_untrusted_executable_cannot_be_passed_as_native(monkeypatch):
    monkeypatch.setattr(volume.shutil, 'which', lambda *a, **k: pytest.fail('PATH fallback'))
    monkeypatch.setattr(volume, '_run_command', lambda *a: pytest.fail('relative executable launched'))
    assert volume._powershell_disk_number_for_drive('F', 'powershell.exe', native_trusted=True) == ''
    assert volume._powershell_disk_number_for_drive('F', r'\\evil\share\powershell.exe', native_trusted=True) == ''
    assert volume._powershell_disk_number_for_drive('F', r'C:powershell.exe', native_trusted=True) == ''
    assert volume._powershell_disk_number_for_drive('F; echo hacked', r'C:\Windows\powershell.exe', native_trusted=True) == ''


def test_wsl_interop_resolution_is_unchanged(monkeypatch):
    monkeypatch.setattr(volume, 'windows_directory_from_api', lambda: pytest.fail('WSL must not call native API'))
    monkeypatch.setattr(volume, '_wsl_drive_letter_for_path', lambda path: 'E')
    monkeypatch.setattr(volume.shutil, 'which', lambda executable: '/usr/bin/powershell.exe' if executable == 'powershell.exe' else None)
    seen = []
    monkeypatch.setattr(volume, '_run_command', lambda command: (seen.append(command), '9')[1])
    assert volume._wsl_physical_drive_id('/mnt/e/boots') == 'windows-disk:9'
    assert seen[0][0] == '/usr/bin/powershell.exe'


@pytest.mark.skipif(os.name != 'nt', reason='Requires native Windows host')
def test_native_windows_api_executable_location():
    trusted = volume._trusted_native_powershell_executable()
    assert trusted
    assert ntpath.isabs(trusted)
    assert ntpath.basename(trusted).lower() == 'powershell.exe'
    assert '\\system32\\windowspowershell\\v1.0\\' in trusted.lower()
    assert Path(trusted).is_file()
