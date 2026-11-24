"""Build 690: conservative date-to-city adaptation and foreign month ambiguity."""
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_cities import City, CityCatalog, refine_parsed_fields

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize('folder,canonical', [
    ('Phish 1987.05.08 Berlin', '1987-05-08'),
    ('Phish 5-8-87 Berlin', '1987-05-08'),
    ('Phish 8 May 1987 Berlin', '1987-05-08'),
    ('Phish 1987-05-08 Berlin', '1987-05-08'),
])
def test_city_candidate_uses_only_already_parsed_raw_date(folder, canonical):
    catalog = CityCatalog([City('Berlin', '', 'Germany')])
    matches = [v for v in phase._find_date_matches(folder) if v['normalized'] == canonical]
    assert matches, folder
    fields = refine_parsed_fields(folder_name=folder, artist='Phish', date=canonical,
                                  raw_date=matches[0]['raw'], catalog=catalog)
    assert fields['city'] == 'Berlin'
    assert fields['venue'] == ''
    # Without independent evidence of this source spelling the city adapter
    # must not infer its own alternative date.
    if canonical not in folder:
        fields_no_raw = refine_parsed_fields(folder_name=folder, artist='Phish', date=canonical,
                                             catalog=catalog)
        assert fields_no_raw['city'] == ''


def test_catalog_never_overrides_established_geography():
    catalog = CityCatalog([City('Berlin', '', 'Germany')])
    fields = refine_parsed_fields(folder_name='Phish 8 May 1987 Berlin', artist='Phish',
                                  date='1987-05-08', raw_date='8 May 1987',
                                  city='Paris', catalog=catalog)
    assert fields['city'] == 'Paris'


def test_inventory_city_fallback_receives_parser_confirmed_date(monkeypatch):
    catalog = CityCatalog([City('Berlin', '', 'Germany')])
    record = SimpleNamespace(artist='Phish', date='1987-05-08', main_dir_name='Phish 8 May 1987 Berlin',
                             city='', region='', country='', location='', venue='', album_name='')
    monkeypatch.setattr(phase, '_city_catalog', lambda _cfg: catalog)
    monkeypatch.setattr(phase, 'lookup_artist_master_with_status', lambda *_args: ('matched', []))
    phase._apply_city_catalog_last_resort(SimpleNamespace(), record, object(), {}, [])
    assert record.city == 'Berlin'
    assert record.location == 'Berlin'


def test_mars_and_juli_are_not_partial_months_without_day():
    for text in ('Bruno Mars 2017 Tokyo Dome', 'Juli 2005'):
        assert not any(item['normalized'] in {'2017-03-xx','2005-07-xx'}
                       for item in phase._find_date_matches(text))


def test_ambiguous_french_month_artist_name_not_mistaken_for_full_date():
    assert not any(item['normalized'] == '2017-03-12'
                   for item in phase._find_date_matches('Bruno Mars 12 2017'))
    # Unambiguous day-first spelling is still supported.
    assert any(item['normalized'] == '2017-03-12'
               for item in phase._find_date_matches('Phish 12 Mars 2017'))


def test_two_complete_date_range_has_no_cross_boundary_hybrid():
    pairs = phase._find_date_matches('Phish Dec 31 1999 - Jan 1 2000')
    assert [p['normalized'] for p in pairs] == ['1999-12-31', '2000-01-01']
