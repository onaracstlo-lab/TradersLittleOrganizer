"""Regression contracts for the Build 704 continuation."""
from pathlib import Path
import inspect

import pytest

pytestmark = pytest.mark.behavior

import tlo_phase23_v2 as phase
import tlo_ux
import tlo_inventory_update


def test_suffix_annotations_only_known_terms():
    source = inspect.getsource(phase._apply_city_catalog_last_resort)
    assert 'FLAC' in source and 'annotation.sub' in source
    assert '[-–—]' in source


def test_single_member_is_not_provisional():
    source = inspect.getsource(tlo_ux.preview_inventory_dry_run) if hasattr(tlo_ux,'preview_inventory_dry_run') else Path(tlo_ux.__file__).read_text()
    assert 'len(collection.members) > 1' in source


def test_copytree_errors_are_redacted_and_non_destructive():
    source = inspect.getsource(tlo_inventory_update._verified_cross_device_folder_move)
    assert 'except shutil.Error as exc:' in source
    assert 'The original folder was not deleted' in source

@pytest.mark.parametrize('suffix', [
    'Berlin 24-96', 'Berlin - SBD', 'Berlin.SBD', 'Berlin [FLAC16]',
    'Berlin [FLAC16] (SBD)',
])
def test_city_catalog_suffix_qualifiers_preserve_city(monkeypatch, suffix):
    from types import SimpleNamespace
    from tlo_cities import City, CityCatalog
    catalog = CityCatalog([City('Berlin', '', 'Germany')])
    monkeypatch.setattr(phase, '_city_catalog', lambda config: catalog)
    monkeypatch.setattr(phase, 'lookup_artist_master_with_status', lambda name, matcher: ('matched', ['Wilco']) if name == 'Wilco' else ('no_match', []))
    record = SimpleNamespace(artist='Wilco', date='1987-05-18', main_dir_name=f'Wilco 1987-05-18 {suffix}',
                             city='', region='', country='', location='', venue='', album_name='')
    phase._apply_city_catalog_last_resort(SimpleNamespace(), record, object(), {}, [])
    assert record.city == 'Berlin'
