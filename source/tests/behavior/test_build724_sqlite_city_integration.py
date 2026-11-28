"""Build 724: the SQLite city prototype augments, but never replaces, legacy parsing."""
from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
from contextlib import closing

import pytest

from tlo_city_sqlite import corrected_city, isolated_city_suffix, resolve_city, split_city_suffix
from tlo_phase23_v2 import _parse_string2
from tlo_setlist_metadata_lookup import _SupportData, _parse_location_from_text, extract_setlist_venue_location
from tlo_cities import catalog_for_tlo
from tools.stage_city_database import stage

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'TLO_DBs' / 'cities.sqlite'


def test_valid_shipping_sqlite_has_proto_schema():
    assert DB.stat().st_size > 1_000_000
    with closing(sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)) as conn, conn:
        assert conn.execute("select value from metadata where key='schema_version'").fetchone()[0] == '1'
        assert conn.execute('pragma quick_check').fetchone()[0] == 'ok'


def test_explicit_geography_corrects_only_approved_typo():
    assert resolve_city('San Fransisco', 'CA', str(DB.parent))['status'] == 'FUZZY_HIGH'
    assert corrected_city('San Fransisco', 'CA', 'USA', str(DB.parent)) == 'San Francisco'
    assert corrected_city('San Fransisco', 'NY', 'USA', str(DB.parent)) == 'San Fransisco'
    assert corrected_city('Abbottsford', 'BC', 'Canada', str(DB.parent)) == 'Abbottsford'  # valid alias preserved
    assert corrected_city('Unknownshire', 'NH', 'USA', str(DB.parent)) == 'Unknownshire'
    assert corrected_city('San Fransisco', '', '', str(DB.parent)) == 'San Fransisco'
    assert resolve_city('Portland', '', str(DB.parent))['status'] == 'AMBIGUOUS'


def test_folder_parser_recovers_multiword_city_boundary_without_swallowing_venue():
    assert _parse_string2('Great Hall San Fransisco CA', tlo_dbs_dir=str(DB.parent))[:3] == (
        'Great Hall', 'San Francisco', 'CA')
    assert _parse_string2('San Fransisco, CA', tlo_dbs_dir=str(DB.parent))[:3] == ('', 'San Francisco', 'CA')
    assert _parse_string2('Arena San Francisco CA', tlo_dbs_dir=str(DB.parent))[:3] == (
        'Arena', 'San Francisco', 'CA')
    assert _parse_string2('Mystery Town, NH', tlo_dbs_dir=str(DB.parent)) == _parse_string2('Mystery Town, NH')
    assert _parse_string2('Arena San Fransisco CA', tlo_dbs_dir='') == _parse_string2('Arena San Fransisco CA')


def test_setlist_parser_does_not_confuse_colombia_with_colorado():
    support = _SupportData(str(DB.parent))
    got = _parse_location_from_text('Bogota, Colombia', support)
    assert got[0] == 'Bogota'
    assert got[2] == 'Colombia'
    assert got[1] == ''


def test_selected_setlist_corrects_anchored_typo_and_keeps_raw_evidence(tmp_path):
    setlist = tmp_path / 'concert.txt'
    setlist.write_text('Artist: Phish\nDate: 1997-01-02\nVenue: Civic Center\nLocation: San Fransisco, CA\n\n01. First Song\n', encoding='utf-8')
    result = extract_setlist_venue_location(str(setlist), str(DB.parent))
    assert (result.venue, result.city, result.region, result.location) == ('Civic Center', 'San Francisco', 'CA', 'San Francisco CA')
    assert 'San Fransisco' in result.raw
    untouched = extract_setlist_venue_location(str(setlist), str(tmp_path / 'no-db'))
    assert untouched.city == 'San Fransisco'


def test_missing_invalid_sqlite_do_not_abort_or_suppress_legacy_parsing(tmp_path):
    assert corrected_city('San Fransisco', 'CA', '', str(tmp_path)) == 'San Fransisco'
    (tmp_path / 'cities.sqlite').write_bytes(b'not sqlite' * 1024)
    assert resolve_city('San Fransisco', 'CA', str(tmp_path)) is None
    assert _parse_string2('Civic Hall, Boston MA', tlo_dbs_dir=str(tmp_path)) == _parse_string2('Civic Hall, Boston MA')


def test_city_without_geography_must_be_unique_and_complete():
    assert isolated_city_suffix('Portland', str(DB.parent)) == ''
    assert isolated_city_suffix('San Fransisco', str(DB.parent)) == ''
    assert isolated_city_suffix('San Francisco', str(DB.parent)) in {'', 'San Francisco'}
    assert split_city_suffix('Red Rocks Boulder', 'CO', '') is None


def test_sqlite_catalog_provides_exact_city_index():
    catalog = catalog_for_tlo(str(DB.parent))
    assert catalog and catalog.lookup_exact('Cologne') is not None
    assert catalog.lookup_exact('London') is not None


def test_stage_sqlite_read_only_without_modifying_master(tmp_path):
    source = tmp_path / 'source'; dist = tmp_path / 'distribution'
    (source / 'TLO_DBs').mkdir(parents=True); dist.mkdir()
    shutil.copy2(DB, source / 'TLO_DBs' / 'cities.sqlite')
    original = (source / 'TLO_DBs' / 'cities.sqlite').read_bytes()
    targets = stage(source, dist)
    assert dist / 'TLO_DBs' / 'cities.sqlite' in targets
    assert (dist / 'TLO_DBs' / 'cities.sqlite').read_bytes() == original
    assert (source / 'TLO_DBs' / 'cities.sqlite').read_bytes() == original


def test_prototype_cli_uses_runtime_TLO_DBs_default():
    import json
    import subprocess
    import sys
    completed = subprocess.run([sys.executable, '-B', str(ROOT / 'match_city.py'),
                                '--TLOHome', str(ROOT), '--city', 'San Fransisco', '--state', 'CA', '--json'],
                               capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload['status'] == 'FUZZY_HIGH'
    assert payload['canonical_city'] == 'San Francisco'
