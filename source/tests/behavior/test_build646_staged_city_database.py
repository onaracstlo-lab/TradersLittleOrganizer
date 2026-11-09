"""Build 646: city reference ships alongside database masters, not just inside EXEs."""
from pathlib import Path
import json
import zipfile

import pytest
import tlo_github_updates as updater
from tlo_cities import catalog_for_tlo
from tools.stage_city_database import stage

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_source_bundle_contains_matching_staged_city_catalog():
    assert not (ROOT / 'tlo_cities_embedded.py').exists()
    assert (ROOT / 'TLO_DBs/cities.csv').read_bytes() == (ROOT / 'cities.csv').read_bytes()


def test_build_distribution_stage_puts_csv_beside_masters_and_preserves_them(tmp_path):
    source, dist = tmp_path/'source',tmp_path/'release'
    source.mkdir();dist.mkdir()
    (source/'cities.csv').write_bytes((ROOT / 'cities.csv').read_bytes())
    (source/'TLO_DBs').mkdir()
    (source/'TLO_DBs/artists.sqlite').write_bytes(b'artist db master')
    (source/'TLO_DBs/venues.txt').write_text('venue master')
    assert len(stage(source,dist)) == 2
    for place in (source,dist):
        assert (place/'TLO_DBs/cities.csv').read_bytes() == (ROOT / 'cities.csv').read_bytes()
    assert (source/'TLO_DBs/artists.sqlite').read_bytes() == b'artist db master'
    assert (source/'TLO_DBs/venues.txt').read_text() == 'venue master'


def test_bad_city_source_refused_without_overwriting_stage(tmp_path):
    source = tmp_path
    (source/'cities.csv').write_text('city,region,country,aliases\nWrong City,,,\n')
    (source/'TLO_DBs').mkdir()
    (source/'TLO_DBs/cities.csv').write_bytes(b'untouched')
    with pytest.raises(ValueError,match='unexpectedly small'):
        stage(source)
    assert (source/'TLO_DBs/cities.csv').read_bytes() == b'untouched'


def test_shipped_city_catalog_does_not_mark_every_match_as_user_corroborated(tmp_path):
    (tmp_path/'cities.csv').write_bytes((ROOT / 'cities.csv').read_bytes())
    cat = catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('London') is not None
    assert 'london' not in cat.local_names


def test_distributor_scripts_stage_into_tlo_dbs():
    for name in ('createWindowsDist.ps1','createLinuxDist.sh','createMacOSDist.sh'):
        s = (ROOT / name).read_text(encoding='utf8')
        assert 'stage_city_database.py' in s


def _make_zip(path,build=646,with_cities=True):
    files=['artists.sqlite','venues.txt']+(['cities.csv'] if with_cities else [])
    manifest=dict(kind='complete',platform_key='linux',build_number=build,
                  databases_included=True,database_files=files,packaging_mode='native')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('manifest.json',json.dumps(manifest))
        for f in files:
            z.writestr('TLO_DBs/'+f, (ROOT / 'cities.csv').read_bytes() if f=='cities.csv' else b'master')


def test_post_646_complete_zip_must_include_city_master(tmp_path):
    bad=tmp_path/'bad.zip'; good=tmp_path/'good.zip'
    _make_zip(bad,with_cities=False);_make_zip(good,with_cities=True)
    # The final packaging verifier (publisher) owns the exact city-file check;
    # the downloader checks the independently signed whole-ZIP digest instead.
    from tools.verify_city_database_release import verify
    with pytest.raises(ValueError,match='database files mismatch'):
        verify(bad,ROOT,646)
    assert updater._inspect_downloaded_package(
        bad,expected_kind='complete',expected_platform_key='linux',expected_build=646
    )['databases_included'] is True
    result=updater._inspect_downloaded_package(good,expected_kind='complete',expected_platform_key='linux',expected_build=646)
    assert result['databases_included'] is True


def test_no_internal_fallback_and_external_executable_directory(tmp_path, monkeypatch):
    import sys
    from tlo_cities import _cached_layered
    exe = tmp_path / 'apps' / 'Windows' / 'tlo-main.exe'
    exe.parent.mkdir(parents=True)
    with monkeypatch.context() as patch:
        patch.setattr(sys,'frozen',True,raising=False)
        patch.setattr(sys,'executable',str(exe),raising=False)
        _cached_layered.cache_clear()
        assert catalog_for_tlo() is None
        dbdir=tmp_path/'TLO_DBs'
        dbdir.mkdir()
        (dbdir/'cities.csv').write_bytes((ROOT/'cities.csv').read_bytes())
        citycat=catalog_for_tlo()
        assert citycat.lookup_exact('London') is not None
        assert citycat.lookup_exact('Köln') == citycat.lookup_exact('Cologne')
    _cached_layered.cache_clear()


def test_build_process_zip_verifier_rejects_missing_city(tmp_path):
    from tools.verify_city_database_release import verify
    bad,good=tmp_path/'bad.zip',tmp_path/'good.zip'
    _make_zip(bad,with_cities=False)
    _make_zip(good,with_cities=True)
    with pytest.raises(ValueError,match='database files mismatch'):
        verify(bad,ROOT,646)
    result=verify(good,ROOT,646)
    assert result['city_sha256']


def test_stage_scripts_never_embed_city_data_in_executables():
    for name in ('createWindowsDist.ps1','createLinuxDist.sh','createMacOSDist.sh'):
        script=(ROOT/name).read_text(encoding='utf-8')
        for line in script.splitlines():
            if 'cities.csv' in line:
                assert '--add-data' not in line, (name,line)
    assert not (ROOT/'tlo_cities_embedded.py').exists()
