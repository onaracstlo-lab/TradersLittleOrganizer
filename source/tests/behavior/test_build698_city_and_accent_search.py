"""Build 698: preserve cities before qualifiers and search across Latin accents."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_cities import City, CityCatalog

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def search_mod():
    spec = importlib.util.spec_from_file_location('tlo_search_build698', ROOT/'tlo-search.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('original',[
    'Wilco 1987-05-11 Berlin (set 2)',
    'Wilco 1987-05-12 Berlin (SBD)',
    'Wilco 1987-05-17 Berlin [24-96]',
    'Wilco 1987-05-20 Berlin (24-96)',
])
def test_known_artist_date_city_retained_before_recording_qualifier(original,monkeypatch):
    catalog=CityCatalog([City('Berlin','','Germany')])
    record=SimpleNamespace(artist='Wilco',date=original.split()[1],main_dir_name=original,
                           city='',region='',country='',location='',venue='',album_name='')
    monkeypatch.setattr(phase,'_city_catalog',lambda _cfg:catalog)
    monkeypatch.setattr(phase,'lookup_artist_master_with_status',lambda *_args:('matched',[]))
    evidence={}; observations=[]
    phase._apply_city_catalog_last_resort(SimpleNamespace(), record, object(), evidence, observations)
    assert record.city=='Berlin'
    assert record.location=='Berlin'
    assert evidence['city'][0].value=='Berlin'


def test_unknown_artist_does_not_gain_unverified_city(monkeypatch):
    record=SimpleNamespace(artist='Unknown',date='1987-05-11',main_dir_name='Unknown 1987-05-11 Berlin (SBD)',
                           city='',region='',country='',location='',venue='',album_name='')
    monkeypatch.setattr(phase,'lookup_artist_master_with_status',lambda *_args:('no_match',[]))
    phase._apply_city_catalog_last_resort(SimpleNamespace(),record,object(),{},[])
    assert not record.city


@pytest.mark.parametrize('query,stored',[
    ('Björk 2007-08-20 Paris','Bjork 2007-08-20 Paris'),
    ('Sigur Rós','Sigur Ros 2008-06-10 London'),
    ('Røyksopp','Royksopp 2009-05-01 Oslo'),
    ('Motörhead','Motorhead 1980-07-01'),
    ('Straßenjungs','Strassenjungs 1979-01-01'),
    ('Æther','AEther 2001-01-01 Oslo'),
])
def test_search_matches_ascii_show_from_accented_query(query,stored):
    search=search_mod()
    row=search.CsvRow(show=stored, volume_path='/music/a')
    assert search.search_rows([row],query)==[row]
    assert search.normalize_search_text(query) in search.normalize_search_text(stored)


def test_non_latin_script_remains_distinct_in_search():
    search=search_mod()
    assert search.normalize_search_text('Кино') == 'кино'
    assert search.normalize_search_text('Кино') != search.normalize_search_text('Wilco')
