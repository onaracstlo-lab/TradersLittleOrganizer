"""Build 640: conservative city aliases and exact source-spelling output."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher
from tlo_cities import CityCatalog, catalog_for_tlo, refine_parsed_fields
from tlo_setlist_metadata_lookup import _SupportData, _parse_location_from_text

pytestmark = pytest.mark.behavior


def _matcher(include_city_artist=False):
    names = ['Jethro Tull', 'The Who', 'King Crimson', 'NRBQ', 'Chicago', 'Boston', 'Twiddle', 'The Kinks']
    if include_city_artist:
        names.append('Miami Beach')
    m = ArtistMatcher(db_path='')
    m.exact_map = {name.casefold(): {name} for name in names}
    m.master_aliases = {name: [name] for name in names}
    m.master_norms = {name: {''.join(c for c in name.casefold() if c.isalnum())} for name in names}
    return m


def _parse(tmp_path, name, *, compliant=False, matcher=None, setlist=''):
    folder = tmp_path / name
    folder.mkdir()
    info = folder / 'info.txt'
    if setlist:
        info.write_text(setlist, encoding='utf-8')
    config = SimpleNamespace(
        compliant=compliant, current_volume_label='', current_slam='',
        as_is_artist_name=False, compliant_artist_mode='master',
        etree_lookup=False, setlistfm_lookup=False,
        TLOHome=str(tmp_path), tlo_dbs_dir=str(tmp_path), debug=False,
    )
    group = {
        'group_number': 1, 'main_dir_name': name, 'main_dir_path': str(folder),
        'setlist_file': str(info) if setlist else '', 'setlist_files': [str(info)] if setlist else [],
        'music_dirs': [str(folder)], 'music_file_count': 1, 'flac_tag_samples': [],
        'flac_tag_artist_values': [], 'flac_tag_album_values': [],
        'flac_tag_albumartist_values': [], 'flac_tag_date_values': [],
    }
    record, *_ = phase._extract_metadata_for_group(config, group, matcher or _matcher())
    return record


@pytest.mark.parametrize('compliant', [False, True])
def test_explicit_artist_city_date_recognizes_london_without_inventing_country(tmp_path, compliant):
    r = _parse(tmp_path, 'Jethro Tull, London 2007-02-04', compliant=compliant)
    assert (r.artist, r.date, r.city, r.country, r.region) == (
        'Jethro Tull', '2007-02-04', 'London', '', '')
    assert r.show_name == 'Jethro Tull 2007-02-04 London'


@pytest.mark.parametrize('alias', ['Cologne', 'Koln'])
def test_folder_alias_is_output_not_canonical_city(tmp_path, alias):
    r = _parse(tmp_path, f'The Who, {alias} 1970-04-01')
    assert r.city == alias
    assert r.show_name.endswith(f' {alias}')
    assert r.country == ''  # No auto-imputed country


def test_full_unicode_city_is_normalized_only_at_normal_output_boundary(tmp_path):
    r = _parse(tmp_path, 'The Who, Köln 1970-04-01')
    assert r.city == 'Koln'  # normal TLO print-safe ASCII normalization
    assert r.show_name.endswith(' Koln')


def test_postdate_city_is_not_venue(tmp_path):
    r = _parse(tmp_path, 'King Crimson 1974-06-28 Amsterdam')
    assert (r.venue, r.city, r.location) == ('', 'Amsterdam', 'Amsterdam')


def test_multitoken_city_with_known_artist_and_venue(tmp_path):
    r = _parse(tmp_path, 'NRBQ The Stephen Talkhouse Miami Beach 1994-12-10')
    assert (r.artist, r.venue, r.city, r.region, r.country) == (
        'NRBQ', 'The Stephen Talkhouse', 'Miami Beach', '', '')
    assert 'The Stephen Talkhouse Miami Beach' in r.show_name


def test_artist_collision_retains_known_leading_artist_but_neither_city_nor_venue(tmp_path):
    r = _parse(tmp_path, 'NRBQ The Stephen Talkhouse Miami Beach 1994-12-10', matcher=_matcher(True))
    assert r.artist == 'NRBQ'
    assert not r.venue and not r.city and not r.location


@pytest.mark.parametrize('bad', ['Nice', 'Bowie', 'Reading', 'Woodstock', 'Mobile', 'Soundboard', 'Matrix'])
def test_unsafe_music_and_word_city_tokens_stay_unknown(tmp_path, bad):
    r = _parse(tmp_path, f'NRBQ, {bad} 1994-12-10')
    assert not r.city


def test_chicago_artist_never_becomes_city(tmp_path):
    r = _parse(tmp_path, 'Chicago 1971-03-01')
    assert r.artist == 'Chicago' and r.city == ''


def test_existing_path_city_precedence_over_setlist_is_unchanged(tmp_path):
    # Existing TLO precedence: path City is stronger than selected setlist City.
    r = _parse(tmp_path, 'Jethro Tull, London 2007-02-04',
               setlist='Jethro Tull\nDate: 2007-02-04\nVenue: Hall\nCity: Paris\nCountry: France\n01 Song\n')
    assert r.city == 'London'
    assert r.country == ''


def test_combined_index_name_alias_equivalence_and_full_text_guard():
    cat = catalog_for_tlo()
    assert cat.lookup_exact('Cologne') == cat.lookup_exact('Köln')
    assert cat.lookup_exact('Cologne Germany') is None
    assert cat.lookup_exact('Nice') is None
    assert cat.lookup_exact('Bowie') is None


def test_conventional_csv_and_caret_compatibility(tmp_path):
    p = tmp_path / 'cities.csv'
    p.write_text('city,region,country,aliases\nKöln,,Germany,Cologne|Koln\n', encoding='utf-8')
    assert CityCatalog.from_csv(p).lookup_exact('Cologne').city == 'Köln'
    p.write_text('city^region^country^aliases\nKöln^^Germany^Cologne|Koln\n', encoding='utf-8')
    assert CityCatalog.from_csv(p).lookup_exact('Cologne').city == 'Köln'
    p.write_text('city^region^country\nKöln^^Germany\n', encoding='utf-8')
    assert CityCatalog.from_csv(p).lookup_exact('Köln').city == 'Köln'


def test_malformed_local_file_does_not_disable_packaged_catalog(tmp_path):
    (tmp_path / 'cities.csv').write_text('city,region\nLondon,UK\n', encoding='utf-8')
    assert catalog_for_tlo(str(tmp_path)).lookup_exact('Cologne') is not None
    r = _parse(tmp_path, 'The Who, Cologne 1970-04-01')
    assert r.city == 'Cologne'


def test_setlist_parser_keeps_explicit_alias_spelling(tmp_path):
    support = _SupportData(str(tmp_path))
    r = _parse_location_from_text('Gürzenich, Cologne, Germany', support)
    assert r[:3] == ('Cologne', '', 'Germany')
    assert _parse_location_from_text('Indianapolis, in', support)[:3] == ('', '', '')


def test_packaged_city_data_on_all_platforms(tmp_path, monkeypatch):
    """External TLO_DBs data must be discoverable without a Python copy."""
    import sys
    from tlo_cities import catalog_for_tlo, _cached_layered
    root = Path(__file__).resolve().parents[2]
    assert (root / 'TLO_DBs/cities.csv').read_bytes() == (root / 'cities.csv').read_bytes()
    for name in ['createWindowsDist.ps1', 'createMacOSDist.sh', 'createLinuxDist.sh']:
        script = (root / name).read_text(encoding='utf-8')
        assert 'stage_city_database.py' in script
        assert '--add-data' not in '\n'.join(x for x in script.splitlines() if 'cities.csv' in x)
    with monkeypatch.context() as patch:
        patch.setattr(sys, 'frozen', True, raising=False)
        patch.setattr(sys, 'executable', str(tmp_path / 'apps' / 'Linux' / 'tlo-main'), raising=False)
        _cached_layered.cache_clear()
        assert catalog_for_tlo() is None
        db = tmp_path / 'TLO_DBs'
        db.mkdir()
        (db / 'cities.csv').write_bytes((root / 'cities.csv').read_bytes())
        assert catalog_for_tlo().lookup_exact('London') is not None
    _cached_layered.cache_clear()


def test_refiner_preserves_alias_and_does_not_invent_country(tmp_path):
    out = refine_parsed_fields(folder_name='The Who, Cologne 1970-04-01',
                              artist='The Who', date='1970-04-01',
                              csv_path=Path(__file__).resolve().parents[2] / 'cities.csv')
    assert out == {'city': 'Cologne', 'region': '', 'country': '', 'venue': ''}
