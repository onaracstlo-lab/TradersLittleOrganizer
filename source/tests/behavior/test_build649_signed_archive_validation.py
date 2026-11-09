"""Build 649: authentic whole-ZIP policy, protected data and separate DB build gate."""
import json
from pathlib import Path
import zipfile
import hashlib
import pytest

import tlo_github_updates as updater
from tlo_version import BUNDLE_BUILD
from tools.verify_city_database_release import verify as verify_release_db

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def package(path: Path, *, build: int = 649, databases: bool = True,
            files: tuple[str, ...] = ('artists.sqlite','venues.txt','cities.csv'),
            kind: str = 'update', extra: tuple[str, ...] = ()):
    manifest = dict(kind=kind, build=build, build_number=build,
                    platform_key='windows', packaging_mode='hybrid',
                    databases_included=databases, database_files=list(files))
    if kind == 'update':
        manifest.update(safe_update=True, requires_complete_install=False,
                        protected_paths=list(updater.UPDATE_PROTECTED_PATHS) +
                        ([] if databases else ['TLO_DBs/']))
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('UPDATE_MANIFEST.json' if kind=='update' else 'manifest.json', json.dumps(manifest))
        for name in files:
            if databases:
                data = (ROOT/'cities.csv').read_bytes() if name=='cities.csv' else b'fixture DB'
                z.writestr('TLO_DBs/'+name,data)
        for name in extra:z.writestr(name,b'fixture')


def inspect(path, *, kind='update', build=649):
    return updater._inspect_downloaded_package(path,expected_kind=kind,
        expected_platform_key='windows',expected_build=build)


def test_build649_version():
    assert BUNDLE_BUILD == 649


def test_new_database_filename_does_not_break_authentic_signed_zip(tmp_path):
    p=tmp_path/'release.zip'
    package(p,files=('artists.sqlite','venues.txt','cities.csv','future-db.sqlite'))
    assert inspect(p)['databases_included'] is True


def test_database_manifest_membership_no_longer_inspected(tmp_path):
    p=tmp_path/'release.zip'
    package(p,files=('cities.csv',),extra=('TLO_DBs/new_reference.db',))
    assert inspect(p)['databases_included'] is True


def test_build_time_db_gate_remains_strict_and_separate(tmp_path):
    p=tmp_path/'release.zip'
    package(p,files=('artists.sqlite','venues.txt'),kind='complete')
    with pytest.raises(ValueError,match='database files mismatch'):
        verify_release_db(p,ROOT,649)


def test_database_free_update_protects_all_database_files(tmp_path):
    p=tmp_path/'release.zip'
    package(p,databases=False,files=(),extra=('TLO_DBs/cities.csv',))
    with pytest.raises(ValueError,match='protected user-data path'):
        inspect(p)


def test_casefold_protected_path_still_rejected(tmp_path):
    p=tmp_path/'release.zip'
    package(p,databases=False,files=(),extra=('tlo_dbs/CITIES.CSV',))
    with pytest.raises(ValueError,match='protected user-data path'):
        inspect(p)


def test_zip_traversal_still_rejected(tmp_path):
    p=tmp_path/'release.zip'
    package(p,extra=('../user/file',))
    with pytest.raises(ValueError):
        inspect(p)


def test_wrong_release_build_still_rejected(tmp_path):
    p=tmp_path/'release.zip'
    package(p,build=650)
    with pytest.raises(ValueError,match='expected Build 649'):
        inspect(p)


def test_signed_asset_hash_authorizes_whole_zip_not_database_list(tmp_path):
    p=tmp_path/'release.zip'
    package(p)
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    assert updater._file_matches_asset(p,{'size':p.stat().st_size,'digest':'sha256:'+h})
    assert not updater._file_matches_asset(p,{'size':p.stat().st_size,'digest':'sha256:'+'0'*64})


def test_complete_requires_database_inclusion_flag(tmp_path):
    p=tmp_path/'release.zip'
    package(p,kind='complete',databases=False,files=())
    with pytest.raises(ValueError,match='required databases'):
        inspect(p,kind='complete')
