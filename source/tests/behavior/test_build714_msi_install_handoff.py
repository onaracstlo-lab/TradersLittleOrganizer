"""Build 714: published update path is carried unchanged to MSI launch.

Reproduces the reported Build 685 situation: bytes reached Downloads but the
install step cannot locate the file. The code must never invent another path.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import tlo_github_updates as U
import tlo_msi_install_mode as Mode

pytestmark = pytest.mark.behavior


def _asset(contents: bytes) -> dict:
    return {'name': 'TLO_V1.7Build714_Windows_x64.msi',
            'browser_download_url': 'https://github.com/onaracstlo-lab/TradersLittleOrganizer/releases/download/tag/file.msi',
            'size': len(contents), 'digest': 'sha256:' + hashlib.sha256(contents).hexdigest()}


def _result(path: Path, contents: bytes) -> U.UpdateCheckResult:
    return U.UpdateCheckResult('downloaded', 'downloaded', '', path=str(path),
        asset_name=path.name, asset_digest=hashlib.sha256(contents).hexdigest(),
        package_kind='msi')


def test_published_msi_handoff_reuses_exact_filename_spaces_and_unicode(tmp_path, monkeypatch):
    name = 'TLO_V1.7Build714_Windows_x64.msi'
    downloads = tmp_path / 'My Downloads with spaces' / 'æ'
    downloads.mkdir(parents=True)
    payload = bytes.fromhex('d0cf11e0a1b11ae1') + b'msi fixture payload'
    asset = _asset(payload)
    monkeypatch.setattr(U, '_downloads_dir', lambda: downloads)
    monkeypatch.setattr(U, '_download_asset', lambda _a, dest: dest.write_bytes(payload))
    calls = []
    monkeypatch.setattr(U, 'is_msi_install', lambda: True)
    monkeypatch.setattr(U, 'launch_verified_msi_upgrade', lambda path, digest: calls.append((path, digest)))
    result = U._download_and_report_verified_asset(asset, tlo_home=None, latest_build=714,
        asset_name=name, package_kind='msi', platform_key='windows_msi')
    assert result.status == 'downloaded'
    assert result.path == str(downloads / name)
    U.install_downloaded_msi(result)
    assert calls == [(result.path, result.asset_digest)]
    assert list(downloads.iterdir()) == [downloads / name]


def test_after_download_file_removed_gives_path_not_false_success(tmp_path, monkeypatch):
    payload = bytes.fromhex('d0cf11e0a1b11ae1') + b'staged'
    asset = _asset(payload)
    downloads = tmp_path / 'Downloads'
    downloads.mkdir()
    monkeypatch.setattr(U, '_downloads_dir', lambda: downloads)
    monkeypatch.setattr(U, '_download_asset', lambda _a, dest: dest.write_bytes(payload))
    real_publish = U._publish_verified_download
    def publish_then_remove(staged, destination):
        real_publish(staged, destination)
        destination.unlink()  # antivirus or cleanup raced the publication
    monkeypatch.setattr(U, '_publish_verified_download', publish_then_remove)
    with pytest.raises(FileNotFoundError, match='final download path'):
        U._download_and_report_verified_asset(asset, tlo_home=None, latest_build=714,
            asset_name=asset['name'], package_kind='msi', platform_key='windows_msi')


def test_missing_after_download_refuses_launch_and_shows_actual_path(tmp_path, monkeypatch):
    file = tmp_path / 'Downloads' / 'TLO_V1.7Build714_Windows_x64.msi'
    file.parent.mkdir()
    payload = bytes.fromhex('d0cf11e0a1b11ae1') + b'fixture'
    file.write_bytes(payload)
    result = _result(file, payload)
    file.unlink()
    monkeypatch.setattr(U, 'launch_verified_portable_msi_install',
        lambda *_: pytest.fail('missing file must never launch'))
    with pytest.raises(FileNotFoundError, match='recorded path') as exc:
        U.install_downloaded_msi(result)
    assert str(file) in str(exc.value)
    assert 'No installer was launched' in str(exc.value)


def test_msi_handoff_refuses_modified_path_and_symlink(tmp_path, monkeypatch):
    file = tmp_path / 'TLO_V1.7Build714_Windows_x64.msi'
    payload = bytes.fromhex('d0cf11e0a1b11ae1') + b'original'
    file.write_bytes(payload)
    result = _result(file, payload)
    file.write_bytes(payload + b'changed')
    monkeypatch.setattr(U, 'launch_verified_msi_upgrade', lambda *_: pytest.fail('unverified MSI launched'))
    with pytest.raises(ValueError, match='changed after verification'):
        U.install_downloaded_msi(result)
    file.unlink()
    outside = tmp_path / 'outside.msi'
    outside.write_bytes(payload)
    try:
        file.symlink_to(outside)
    except OSError:
        pytest.skip('symlink creation not available here')
    with pytest.raises(ValueError, match='Untrusted update download path'):
        U.install_downloaded_msi(result)


def test_worker_uses_native_provider_path_and_instructive_windows_installer_codes():
    source = (Path(__file__).resolve().parents[2] / 'msi/TLO-MSI-Update-Worker.ps1').read_text(encoding='utf-8')
    assert '$resolvedMsi.ProviderPath' in source
    assert '(Resolve-Path -LiteralPath $MsiPath).Path' not in source
    assert 'Test-Path -LiteralPath $MsiPath -PathType Leaf' in source
    assert '1612' in source and 'previous installation source' in source
    assert '1619' in source and 'downloaded MSI' in source


def test_worker_arguments_pass_download_path_as_single_arg(tmp_path, monkeypatch):
    root = tmp_path / 'msi root'
    root.mkdir()
    worker = root / 'TLO-MSI-Update-Worker.ps1'
    worker.write_text('# test')
    file = tmp_path / 'download area' / 'TLO_V1.7Build714_Windows_x64.msi'
    file.parent.mkdir()
    file.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+b'1')
    calls = []
    import subprocess
    monkeypatch.setattr(Mode, 'msi_install_root', lambda _: root)
    monkeypatch.setattr(Mode, '_trusted_system32_executable', lambda _: 'powershell.exe')
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **kwargs: calls.append(args))
    assert Mode.launch_verified_msi_upgrade(file, 'a' * 64,
        executable=root / 'tlo-main.exe', worker=worker, restart=False)
    cmd = calls[0]
    assert cmd[cmd.index('-MsiPath') + 1] == str(file.resolve())
    assert cmd[cmd.index('-ExpectedSha256') + 1] == 'a' * 64
