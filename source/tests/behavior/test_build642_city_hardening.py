"""Build 642: layered city catalog and risk-averse collision handling."""
import pytest
pytestmark = pytest.mark.behavior
from tlo_cities import catalog_for_tlo

def test_layering_keeps_bundled_cities_and_adds_local(tmp_path):
    p=tmp_path/'cities.csv'
    p.write_text('city,region,country,aliases\nNew Testington,,United States,New Testing\n',encoding='utf-8')
    cat=catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('London') is not None
    assert cat.lookup_exact('New Testing').city=='New Testington'

def test_malformed_rows_ignored_without_losing_valid_entries(tmp_path):
    p=tmp_path/'cities.csv'
    p.write_text('city^region^country^aliases\nBadly broken\nTest Town^^Canada^Town Test^extra_reason\n^^Attribution^\n',encoding='utf-8')
    cat=catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('London') is not None
    assert cat.lookup_exact('Town Test').city=='Test Town'
    assert cat.warnings

def test_local_collision_does_not_override_bundled_city(tmp_path):
    p=tmp_path/'cities.csv'
    p.write_text('city,region,country,aliases\nBerlin,,United States,New Berlin\n',encoding='utf-8')
    cat=catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('Berlin').country=='Germany'
    assert cat.lookup_exact('New Berlin') is None

def test_concert_cities_retained_but_country_unknown():
    cat=catalog_for_tlo()
    for name in ('Bristol','Brighton','Aberdeen','York','Coventry','Perth'):
        row=cat.lookup_exact(name)
        assert row and row.country == '', name

def test_hyphen_within_word_not_explicit_separator():
    cat=catalog_for_tlo()
    assert cat.suggest_for_known_artist('Phish Soundboard-London 1997-07-01',artist='Phish',date='1997-07-01') is None

def test_aliases_not_rewritten():
    cat=catalog_for_tlo()
    cand=cat.suggest_for_known_artist('The Who, Cologne 1970-04-01',artist='The Who',date='1970-04-01')
    assert cand.city=='Cologne'

def test_inverted_artist_firstname_is_not_city():
    from types import SimpleNamespace
    from tlo_artist_db import ArtistMatcher
    import tlo_phase23_v2 as phase
    matcher=ArtistMatcher(db_path='')
    matcher.exact_map={'moore':{'Gary Moore'}}
    matcher.master_aliases={'Gary Moore':['Moore']}
    matcher.master_norms={'Gary Moore':{'garymoore'}}
    group={'main_dir_name':'Moore, Gary 1990-05-05'}
    config=SimpleNamespace(tlo_dbs_dir='',TLOHome='',as_is_artist_name=False)
    assert phase._match_comma_artist_city_date(group,matcher,config) is None
