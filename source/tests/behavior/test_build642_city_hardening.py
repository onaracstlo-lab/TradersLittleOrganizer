"""Build 642: layered city catalog and risk-averse collision handling."""
import pytest
pytestmark = pytest.mark.behavior
from tlo_cities import catalog_for_tlo

from tests._city_fixture import city_db


def test_configured_sqlite_is_sole_reference(tmp_path):
    city_db(tmp_path/'cities.sqlite', [('New Testington','NH',('New Testing',))])
    (tmp_path/'cities.csv').write_text('city,region,country,aliases\nFake City,MA,USA,\n')
    cat=catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('London') is None
    assert cat.lookup_exact('Fake City') is None
    assert cat.lookup_exact('New Testing').city=='New Testington'


def test_corrupt_sqlite_falls_back_to_non_database_parsing(tmp_path):
    (tmp_path/'cities.sqlite').write_bytes(b'bad file')
    seen=[]
    assert catalog_for_tlo(str(tmp_path),on_warning=seen.append) is None
    assert seen and 'original parsing retained' in seen[0]


def test_ambiguous_alias_cannot_assign_geography(tmp_path):
    city_db(tmp_path/'cities.sqlite', [('Berlin','Germany',('New Berlin',)), ('Berlin','NH',())])
    cat=catalog_for_tlo(str(tmp_path))
    assert cat.lookup_exact('Berlin').country==''
    assert cat.lookup_exact('New Berlin').country=='Germany'


def test_concert_city_recognition_does_not_impute_geography():
    cat=catalog_for_tlo()
    for name in ('Bristol','Brighton','Aberdeen','York','Coventry','Perth'):
        row=cat.lookup_exact(name)
        assert row, name
        result=cat.suggest_for_known_artist(f'Phish, {name} 1997-07-01',artist='Phish',date='1997-07-01')
        assert result and result.city==name

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
