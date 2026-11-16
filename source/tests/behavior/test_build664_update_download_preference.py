"""Build 664: Windows download format is explicit, MSI by default for all installs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

import tlo_github_updates as U
import tlo_msi_install_mode as Mode
import tlo_preferences as P

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def release(build=664, *, onedir=True):
    assets = [
        {'name': f'TLO_V1.7Build{build}_Windows_x64.msi'},
        {'name': f'TLO_V1.7Build{build}_update_Windows.zip'},
        {'name': f'TLO_V1.7Build{build}_complete_Windows.zip'},
    ]
    if onedir:
        assets.append({'name': f'TLO_V1.7Build{build}_update_Windows_onedir.zip'})
    return {'assets': assets}


def windows(monkeypatch, *, is_msi=False, layout='windows_onedir'):
    monkeypatch.setattr(U.sys, 'platform', 'win32')
    monkeypatch.setattr(U, 'is_msi_install', lambda: is_msi)
    monkeypatch.setattr(U, '_detect_installed_platform_key', lambda _: layout)


def test_approved_template_and_first_launch_default(tmp_path):
    assert P.default_text() == (ROOT / P.FILENAME).read_text(encoding='utf-8')
    assert '# update_downloads : msi | zip (msi = Download .msi update; zip = Download .zip update)' in P.default_text()
    values = P.parse_text(P.default_text())
    assert values['general']['update_downloads'] == 'msi'
    assert P.load(tmp_path)['general']['update_downloads'] == 'msi'


@pytest.mark.parametrize('content,expected', [
    ('', 'msi'),
    ('[general]\nauto_update = false\n', 'msi'),
    ('[general]\nupdate_downloads = msi\n', 'msi'),
    ('[general]\nupdate_downloads = zip\n', 'zip'),
    ('[GENERAL]\nUPDATE_DOWNLOADS = ZIP\n', 'zip'),
    ('[general]\nupdate_downloads = invalid\n', 'msi'),
    ('[general]\nupdate_downloads = zip\nunknown_option = true\n', 'msi'),
])
def test_missing_old_valid_and_invalid_ini_handling(tmp_path, content, expected):
    p = tmp_path / P.FILENAME
    if content:
        p.write_text(content)
    assert U.update_download_preference(tmp_path) == expected
    if not content:
        assert not p.exists()  # Update selection must not generate an INI.


@pytest.mark.parametrize('msi,layout', [(False,'windows'), (False,'windows_onedir'), (True,'windows_onedir')])
def test_windows_default_is_msi_irrespective_of_install_method(tmp_path, monkeypatch, msi, layout):
    windows(monkeypatch, is_msi=msi, layout=layout)
    chosen, kind, key = U._choose_asset(release(), 664, tmp_path)
    assert (kind, key) == ('msi', 'windows_msi')
    assert chosen['name'].endswith('Windows_x64.msi')


@pytest.mark.parametrize('layout,suffix', [
    ('windows', 'update_Windows.zip'),
    ('windows_onedir', 'update_Windows_onedir.zip'),
])
@pytest.mark.parametrize('msi_installed', [True,False])
def test_explicit_zip_preference_wins_regardless_of_install_method(tmp_path, monkeypatch, layout, suffix, msi_installed):
    (tmp_path / P.FILENAME).write_text('[general]\nupdate_downloads = zip\n')
    windows(monkeypatch, is_msi=msi_installed, layout=layout)
    chosen, kind, key = U._choose_asset(release(), 664, tmp_path)
    assert (kind, key) == ('update', layout)
    assert chosen['name'].endswith(suffix)


def test_msi_does_not_silently_fallback_to_zip(tmp_path, monkeypatch):
    windows(monkeypatch)
    only_zip = release()
    only_zip['assets'] = [a for a in only_zip['assets'] if not a['name'].endswith('.msi')]
    assert U._choose_asset(only_zip, 664, tmp_path) == (None, '', 'windows_msi')


def test_explicit_zip_does_not_silently_fallback_to_msi(tmp_path, monkeypatch):
    (tmp_path / P.FILENAME).write_text('[general]\nupdate_downloads = zip\n')
    windows(monkeypatch)
    only_msi = {'assets': [release()['assets'][0]]}
    assert U._choose_asset(only_msi, 664, tmp_path) == (None, '', 'windows_onedir')


def test_zip_complete_fallback_remains_if_explicitly_requested(tmp_path, monkeypatch):
    (tmp_path / P.FILENAME).write_text('[general]\nupdate_downloads = zip\n')
    windows(monkeypatch, layout='windows')
    only_complete = {'assets': [release()['assets'][2]]}
    assert U._choose_asset(only_complete, 664, tmp_path)[1:] == ('complete','windows')


@pytest.mark.parametrize('platform,layout', [('linux','linux'),('darwin','macos')])
def test_non_windows_updater_remains_zip_based(monkeypatch, tmp_path, platform, layout):
    monkeypatch.setattr(U.sys, 'platform', platform)
    rel = {'assets': [{'name': f'TLO_V1.7Build664_update_{"Linux" if platform == "linux" else "macOS"}.zip'}]}
    chosen, kind, key = U._choose_asset(rel, 664, tmp_path)
    assert (kind,key) == ('update', layout)
    assert chosen is not None


def test_preferences_reject_unknown_enum_and_preserve_file(tmp_path):
    P.load(tmp_path)
    original = (tmp_path / P.FILENAME).read_text()
    with pytest.raises(ValueError, match='update_downloads'):
        P.save_text(tmp_path, original.replace('update_downloads = msi','update_downloads = exe'))
    assert (tmp_path / P.FILENAME).read_text() == original


def test_verified_msi_portable_handoff_checks_digest_and_launches_interactive_setup(monkeypatch, tmp_path):
    file = tmp_path / 'official.msi'
    file.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+b'a'*16)
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    launched = []
    monkeypatch.setattr(Mode.sys, 'platform', 'win32')
    monkeypatch.setattr('subprocess.Popen', lambda args, **kwargs: launched.append((args,kwargs)))
    assert Mode.launch_verified_portable_msi_install(file, digest)
    assert launched[0][0] == ['msiexec.exe', '/i', str(file)]
    with pytest.raises(ValueError, match='no longer matches'):
        Mode.launch_verified_portable_msi_install(file, '0'*64)
    assert len(launched) == 1


def test_downloaded_msi_dispatches_portable_or_msi_owned_worker(monkeypatch,tmp_path):
    file = tmp_path / 'official.msi'
    file.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1') + b'a'*8)
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    result = U.UpdateCheckResult('downloaded','','',path=str(file),asset_digest=digest,package_kind='msi')
    calls=[]
    monkeypatch.setattr(U, 'launch_verified_portable_msi_install', lambda *args: calls.append(('portable',args)))
    monkeypatch.setattr(U, 'launch_verified_msi_upgrade', lambda *args: calls.append(('msi',args)))
    monkeypatch.setattr(U, 'is_msi_install',lambda: False)
    U.install_downloaded_msi(result)
    monkeypatch.setattr(U, 'is_msi_install',lambda: True)
    U.install_downloaded_msi(result)
    assert [call[0] for call in calls] == ['portable', 'msi']
