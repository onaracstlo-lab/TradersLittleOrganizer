"""Build 564: executable assurance for real updater, corruption, and transfer paths."""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.flac import FLAC

import tlo_corruption as corrupt
import tlo_github_updates as updater
import tlo_tag_lib as tag

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('new_download', [True, False])
def test_shared_updater_finalization_inspects_package_before_recording_success(tmp_path, monkeypatch, new_download):
    stages = []
    monkeypatch.setattr(updater, '_downloads_dir', lambda: tmp_path)
    def download(asset, target):
        stages.append(('download', asset['name']))
        return new_download
    def inspect(path, **kwargs):
        stages.append(('inspect', kwargs))
        assert path == tmp_path / 'artifact.zip'
        return {'databases_included': False, 'packaging_mode': 'onedir'}
    def settings(*args, **kwargs):
        stages.append(('settings', kwargs))
        return ''
    monkeypatch.setattr(updater, '_download_asset', download)
    monkeypatch.setattr(updater, '_inspect_downloaded_package', inspect)
    monkeypatch.setattr(updater, '_update_download_settings', settings)
    asset = {'name': 'artifact.zip', 'browser_download_url': 'https://github.com/x.zip', 'size': 1}
    result = updater._download_and_report_verified_asset(
        asset, tlo_home=tmp_path, latest_build=565, asset_name='artifact.zip',
        package_kind='update', platform_key='linux',
    )
    assert [stage[0] for stage in stages] == ['download', 'inspect', 'settings']
    assert stages[1][1] == {'expected_kind': 'update', 'expected_platform_key': 'linux', 'expected_build': 565}
    assert stages[2][1]['packaging_mode'] == 'onedir'
    assert result.status == ('downloaded' if new_download else 'already_downloaded')
    assert result.path == str(tmp_path / 'artifact.zip')
    assert result.databases_included is False
    assert 'This update does not contain your inventory' in result.message


def test_rejected_update_package_never_persists_last_download(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, '_downloads_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, '_download_asset', lambda *_args: True)
    monkeypatch.setattr(updater, '_inspect_downloaded_package', lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('SHA-256 rejected')))
    monkeypatch.setattr(updater, '_update_download_settings', lambda *_args, **_kwargs: pytest.fail('rejected update must not be persisted'))
    with pytest.raises(ValueError, match='SHA-256 rejected'):
        updater._download_and_report_verified_asset(
            {}, tlo_home=tmp_path, latest_build=565, asset_name='artifact.zip',
            package_kind='update', platform_key='linux',
        )


def _show(tmp_path, mode):
    source = tmp_path / 'source' / 'Artist 2001-01-01 Venue'
    source.mkdir(parents=True)
    (source / 'disc1').mkdir()
    (source / 'disc1' / '01.flac').write_bytes(b'audio' * 30)
    destination = tmp_path / 'destination'
    destination.mkdir()
    group = {'main_dir_path': str(source), 'main_dir_name': source.name,
             'music_dirs': [str(source / 'disc1')], 'music_files': [str(source / 'disc1' / '01.flac')],
             'setlist_files': [], 'txt_files': []}
    record = SimpleNamespace(main_dir_path=str(source), main_dir_name=source.name,
                             show_name=source.name, parentheticals='', setlist_file='',
                             music_dirs=[str(source / 'disc1')], setlist_files=[])
    config = SimpleNamespace(rename_compliantly=False, tag_copy_during_inventory=(mode == 'tag_copy'),
                             tag_copy_destination=str(destination), tag_copy_and_delete_path=str(destination))
    return source, destination, group, record, config


@pytest.mark.parametrize('mode', ['tag_copy', 'copy_delete'])
def test_both_live_transfer_modes_refuse_publication_when_size_verification_fails(tmp_path, monkeypatch, mode):
    source, destination, group, record, config = _show(tmp_path, mode)
    if mode == 'copy_delete':
        monkeypatch.setattr(tag, '_paths_on_same_filesystem', lambda *_args: False)
    def broken_verify(_src, staged):
        assert Path(staged).name.startswith('.tlo-partial-')
        assert not (destination / source.name).exists()
        raise tag.TaggerError('size mismatch')
    monkeypatch.setattr(tag, '_verify_copy_by_file_size', broken_verify)
    transfer = tag.prepare_inventory_tagging_target if mode == 'tag_copy' else tag.prepare_inventory_copy_delete_target
    with pytest.raises(tag.TaggerError, match='size mismatch'):
        transfer(config, group, record)
    assert (source / 'disc1' / '01.flac').read_bytes() == b'audio' * 30
    assert not (destination / source.name).exists()
    assert not list(destination.glob('.tlo-partial-*'))


def test_real_flac_corruption_validation_restores_tags_without_touching_existing_value(tmp_path):
    file = tmp_path / 'song.flac'
    shutil.copy2(ROOT / 'tests/fixtures/build543_silence.flac', file)
    audio = FLAC(file)
    audio[corrupt._TAG_TEST_KEY] = ['original-one', 'original-two']
    audio['artist'] = ['Artist']
    audio.save()
    before = dict(FLAC(file))
    bad, unverifiable = corrupt.classify_audio_paths([str(file)], check_tag_write=True)
    assert (bad, unverifiable) == ([], [])
    assert dict(FLAC(file)) == before


def test_non_tagging_corruption_does_not_attempt_write(tmp_path, monkeypatch):
    file = tmp_path / 'song.flac'
    shutil.copy2(ROOT / 'tests/fixtures/build543_silence.flac', file)
    monkeypatch.setattr(corrupt, '_validate_tag_write_round_trip', lambda *_: pytest.fail('no write for header only'))
    assert corrupt.classify_audio_paths([str(file)], check_tag_write=False) == ([], [])
