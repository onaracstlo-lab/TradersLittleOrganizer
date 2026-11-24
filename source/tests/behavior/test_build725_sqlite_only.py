"""Regression contract for the sole SQLite city master and retained fallbacks."""
from pathlib import Path
import shutil
import json
import zipfile

import pytest

from tlo_cities import catalog_for_tlo
from tlo_city_sqlite import corrected_city
from tlo_phase23_v2 import _parse_string2
from tlo_setlist_metadata_lookup import _SupportData, _parse_location_from_text
from tools.stage_city_database import stage
from tools.verify_city_database_release import verify
from tests._city_fixture import city_db

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / 'TLO_DBs' / 'cities.sqlite'


def test_unknown_location_keeps_positional_geography(tmp_path):
    city_db(tmp_path / 'cities.sqlite', [('Boston', 'MA', ())])
    for raw in ('Community Hall, Unknownshire NH', 'Unknownshire, England', 'Unknownshire, BC'):
        assert _parse_string2(raw, tlo_dbs_dir=str(tmp_path)) == _parse_string2(raw)
    support = _SupportData(str(tmp_path))
    assert _parse_location_from_text('Unknownshire, NH', support)[:2] == ('Unknownshire', 'NH')


def test_old_city_csv_cannot_override_sqlite_or_supply_new_alias(tmp_path):
    path = city_db(tmp_path / 'cities.sqlite', [('Boston', 'MA', ())])
    stale = tmp_path / 'cities.csv'
    stale.write_text('city,region,country,aliases\nBoston,TX,USA,Wrong Alias\nFakeville,MA,USA,\n')
    original = path.read_bytes()
    catalog = catalog_for_tlo(str(tmp_path))
    assert catalog.lookup_exact('Boston').region == 'MA'
    assert catalog.lookup_exact('Wrong Alias') is None
    assert catalog.lookup_exact('Fakeville') is None
    assert corrected_city('Boston','MA','USA',str(tmp_path)) == 'Boston'
    assert path.read_bytes() == original


def test_catalog_cache_refreshes_after_master_replacement(tmp_path):
    path = city_db(tmp_path / 'cities.sqlite', [('Boston', 'MA', ())])
    before = catalog_for_tlo(str(tmp_path))
    replacement = city_db(tmp_path / 'replacement.sqlite', [('Lowell','MA',())])
    replacement.replace(path)
    after = catalog_for_tlo(str(tmp_path))
    assert before.lookup_exact('Boston') and not after.lookup_exact('Boston')
    assert after.lookup_exact('Lowell')


def test_staging_ignores_old_csv_and_preserves_master_bytes(tmp_path):
    source = tmp_path / 'src'; dist = tmp_path / 'dist'
    (source / 'TLO_DBs').mkdir(parents=True); dist.mkdir()
    shutil.copy2(MASTER, source / 'TLO_DBs' / 'cities.sqlite')
    (source / 'cities.csv').write_bytes(b'obsolete root')
    (source / 'TLO_DBs' / 'cities.csv').write_bytes(b'obsolete staged')
    stage(source, dist)
    assert {p.name for p in (dist / 'TLO_DBs').iterdir()} == {'cities.sqlite'}
    assert (dist / 'TLO_DBs' / 'cities.sqlite').read_bytes() == MASTER.read_bytes()


def test_release_db_gate_rejects_legacy_extra_and_wrong_sqlite_bytes(tmp_path):
    files = ['artists.sqlite', 'venues.txt', 'cities.sqlite']
    for extra, bad, expected in [(True, False, 'database files mismatch'), (False, True, 'contents do not match')]:
        path = tmp_path / 'release.zip'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('manifest.json', json.dumps(dict(kind='complete', build_number=725, databases_included=True, database_files=files)))
            for name in files:
                z.writestr('TLO_DBs/' + name, MASTER.read_bytes() if name == 'cities.sqlite' and not bad else b'fixture')
            if extra:
                z.writestr('TLO_DBs/cities.csv', b'obsolete')
        with pytest.raises(ValueError, match=expected):
            verify(path, ROOT, 725)


@pytest.mark.parametrize('included', [True, False])
def test_real_update_manifest_layout(tmp_path, included):
    path = tmp_path / 'update.zip'
    files = ['artists.sqlite', 'venues.txt', 'cities.sqlite'] if included else []
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('UPDATE_MANIFEST.json', json.dumps(dict(kind='update', build=725, databases_included=included, database_files=files)))
        for name in files:
            z.writestr('TLO_DBs/' + name, MASTER.read_bytes() if name == 'cities.sqlite' else b'fixture')
    assert verify(path, ROOT, 725)['databases_included'] is included
