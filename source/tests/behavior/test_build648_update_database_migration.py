"""Build 648 fixtures, updated in 649 for signed-whole-archive validation."""
from pathlib import Path
import json
import zipfile

import pytest

import tlo_github_updates as updates
from tlo_version import BUNDLE_BUILD

pytestmark = pytest.mark.behavior


def make_package(path: Path, *, build: int, kind: str = 'update',
                 database_files: tuple[str, ...] | None = None,
                 declare: object = 'normal', extra_members: tuple[str, ...] = ()) -> None:
    if database_files is None:
        files = ('artists.sqlite', 'venues.txt') + (('cities.csv',) if build >= 646 else ())
    else:
        files = database_files
    includes_databases = bool(files)
    manifest = {
        'kind': kind,
        'platform_key': 'windows',
        'build': build,
        'build_number': build,
        'databases_included': includes_databases,
        'packaging_mode': 'hybrid',
    }
    if declare == 'normal':
        manifest['database_files'] = list(files)
    elif declare != 'absent':
        manifest['database_files'] = declare
    if kind == 'update':
        manifest.update(safe_update=True, requires_complete_install=False,
                        protected_paths=list(updates.UPDATE_PROTECTED_PATHS) +
                        ([] if includes_databases else ['TLO_DBs/']))
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('UPDATE_MANIFEST.json' if kind == 'update' else 'manifest.json', json.dumps(manifest))
        for file in files:
            archive.writestr('TLO_DBs/' + file, b'audited fixture data')
        for file in extra_members:
            archive.writestr(file, b'unexpected')


def inspect(path: Path, *, build: int, kind: str = 'update') -> dict:
    return updates._inspect_downloaded_package(
        path, expected_kind=kind, expected_platform_key='windows', expected_build=build)


@pytest.mark.parametrize('build', (591, 614, 645))
def test_legacy_two_database_releases_still_validate(tmp_path, build):
    path = tmp_path / 'legacy.zip'
    make_package(path, build=build)
    assert inspect(path, build=build)['databases_included'] is True


def test_legacy_two_database_manifest_may_omit_old_declaration(tmp_path):
    path = tmp_path / 'legacy.zip'
    make_package(path, build=614, declare='absent')
    assert inspect(path, build=614)['databases_included'] is True


@pytest.mark.parametrize('build', (646, 647, 648))
def test_current_three_database_releases_validate(tmp_path, build):
    path = tmp_path / 'modern.zip'
    make_package(path, build=build)
    assert inspect(path, build=build)['databases_included'] is True


@pytest.mark.parametrize('build', (591, 648))
def test_database_free_bridge_preserves_database_folder(tmp_path, build):
    path = tmp_path / 'bridge.zip'
    make_package(path, build=build, database_files=())
    assert inspect(path, build=build)['databases_included'] is False
    assert 'TLO_DBs/' in json.loads(zipfile.ZipFile(path).read('UPDATE_MANIFEST.json'))['protected_paths']


def test_complete_package_requires_databases_included_flag(tmp_path):
    path = tmp_path / 'complete.zip'
    make_package(path, build=648, kind='complete')
    assert inspect(path, build=648, kind='complete')['databases_included'] is True
    missing = tmp_path / 'missing.zip'
    make_package(missing, build=648, kind='complete', database_files=())
    with pytest.raises(ValueError, match='required databases'):
        inspect(missing, build=648, kind='complete')


@pytest.mark.parametrize('files', (
    ('artists.sqlite', 'venues.txt'),
    ('artists.sqlite', 'cities.csv'),
    ('artists.sqlite', 'venues.txt', 'cities.csv', 'extra.db'),
))
def test_signed_database_layout_not_constrained_by_old_file_list(tmp_path, files):
    # Under the new policy it is the publisher's responsibility to validate
    # complete/DB-inclusive masters BEFORE signing the whole ZIP.
    path = tmp_path / 'package.zip'
    make_package(path, build=648, database_files=files)
    assert inspect(path, build=648)['databases_included'] is True


@pytest.mark.parametrize('extra_member', ('TLO_DBs/extra.db', 'tlo_dbs/extra.sqlite'))
def test_authentic_unlisted_database_members_do_not_block_updater(tmp_path, extra_member):
    path = tmp_path / 'extra.zip'
    make_package(path, build=648, extra_members=(extra_member,))
    assert inspect(path, build=648)['databases_included'] is True


@pytest.mark.parametrize('declaration', (
    ['artists.sqlite', 'venues.txt'],
    ['artists.sqlite', 'venues.txt', 'cities.csv', 'cities.csv'],
    'artists.sqlite,venues.txt,cities.csv',
    'absent',
))
def test_database_files_declaration_is_informational_only_for_downloader(tmp_path, declaration):
    path = tmp_path / 'declaration.zip'
    make_package(path, build=648, declare=declaration)
    assert inspect(path, build=648)['databases_included'] is True


def test_database_free_update_prohibits_even_one_city_file(tmp_path):
    path = tmp_path / 'bad.zip'
    make_package(path, build=648, database_files=(), extra_members=('TLO_DBs/cities.csv',))
    with pytest.raises(ValueError, match='protected user-data path'):
        inspect(path, build=648)


def test_build648_release_version():
    assert BUNDLE_BUILD >= 648


def test_database_refresh_message_depends_on_release_era():
    assert 'TLO_DBs database files' in updates._package_message('update', True, 614)[1]
    assert 'TLO_DBs database files' in updates._package_message('update', True, 648)[1]
    assert 'existing TLO_DBs files are preserved' in updates._package_message('update', False, 648)[1]
