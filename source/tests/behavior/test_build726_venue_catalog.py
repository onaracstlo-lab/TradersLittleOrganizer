"""Paired real-catalog and no-catalog regressions; no user files are mutated."""
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
from tlo_phase23_v2 import _extract_metadata_for_group, _known_venue_exact
from tlo_setlist_metadata_lookup import extract_setlist_venue_location
from tlo_venue_sqlite import match_full_venue, normalized_venue

pytestmark = pytest.mark.behavior
DB = Path(__file__).resolve().parents[2] / 'TLO_DBs'


def case(tmp_path, name, compliant, db, text=''):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    path = folder / 'info.txt'
    if text:
        path.write_text(text, encoding='utf-8')
    cfg = SimpleNamespace(compliant=compliant, current_volume_label='', current_slam='',
                          as_is_artist_name=False, compliant_artist_mode='master',
                          etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(db),
                          TLOHome=str(tmp_path), debug=False)
    matcher = ArtistMatcher(db_path='')
    matcher.exact_map = {'phish': {'Phish'}}
    matcher.master_aliases = {'Phish': ['Phish']}
    matcher.master_norms = {'Phish': {'phish'}}
    group = dict(group_number=1, main_dir_name=name, main_dir_path=str(folder),
                 setlist_file=str(path) if text else '', setlist_files=[str(path)] if text else [],
                 music_dirs=[str(folder)], music_file_count=1, flac_tag_samples=[],
                 flac_tag_artist_values=[], flac_tag_album_values=[],
                 flac_tag_albumartist_values=[], flac_tag_date_values=[])
    return _extract_metadata_for_group(cfg, group, matcher)[0]


CASES = [
    ('typo_venue', 'Phish 1997-01-02 Pauley Pavillion Los Angeles, CA', False, ''),
    ('typo_compliant', 'Phish 1997-01-02 Pauley Pavillion Los Angeles, CA', True, ''),
    ('historical_boston', 'Phish 1997-01-02 Boston Garden Boston, MA', False, ''),
    ('historical_fleet', 'Phish 1997-01-02 Fleet Center Boston, MA', False, ''),
    ('historical_td', 'Phish 1997-01-02 TD Garden Boston, MA', False, ''),
    ('unknown_venue', 'Phish 1997-01-02 Quux Community Hall Unknownshire, NH', False, ''),
    ('opaque_compliant', 'Phish 1997-01-02 The Fillmore (late)', True, ''),
    ('numeric_room', 'Phish 1997-01-02 ABC Studio 211 New York, NY', False, ''),
    ('acronym', 'Phish 1997-01-02 PNC Bank Arts Center Holmdel, NJ', False, ''),
    ('bad_punctuation', 'Phish 1997-01-02 The Spectrum Philadelphia, PA', False, ''),
    ('fused_ordinal', 'Phish 1997-01-02 1st Bank Center Broomfield, CO', False, ''),
    ('no_geography', 'Phish 1997-01-02 TDGarden', False, ''),
    ('room_expansion', 'Phish 1997-01-02 UCLA Harpies Lounge', False, ''),
    ('opaque_album', 'Phish - Tower Theatre', False, ''),
    ('setlist_typo', 'Phish 1997-01-02', False, 'Artist: Phish\nDate: 1997-01-02\nVenue: Pauley Pavillion\nLocation: Los Angeles, CA\n\n01. Song\n'),
    ('setlist_unknown', 'Phish 1997-01-02', False, 'Artist: Phish\nDate: 1997-01-02\nVenue: Quux Community Hall\nLocation: Unknownshire, NH\n\n01. Song\n'),
    ('source_precedence', 'Phish 1997-01-02 Fleet Center Boston, MA', False, 'Artist: Phish\nDate: 1997-01-02\nVenue: TD Garden\nLocation: Boston, MA\n\n01. Song\n'),
]


@pytest.mark.parametrize('label,name,compliant,text', CASES, ids=[c[0] for c in CASES])
def test_paired_names(tmp_path, label, name, compliant, text):
    old_db = tmp_path / 'no_venue_catalog'
    old_db.mkdir()
    shutil.copyfile(DB / 'cities.sqlite', old_db / 'cities.sqlite')
    old = case(tmp_path, name, compliant, old_db, text)
    new = case(tmp_path, name, compliant, DB, text)
    assert (old.artist, old.date) == (new.artist, new.date)
    assert old.parentheticals == new.parentheticals
    if label in {'typo_venue', 'typo_compliant', 'setlist_typo'}:
        assert 'Pauley Pavilion' in new.show_name and 'Pauley Pavillion' in old.show_name
    elif label == 'no_geography':
        assert 'TD Garden' in new.show_name
    elif label == 'room_expansion':
        assert 'UCLA Harpies Lounge' in new.show_name
    else:
        assert new.show_name == old.show_name


def test_explicit_room_numeric_historical_and_noise_guards():
    for name in ['Boston Garden', 'Fleet Center', 'TD Garden', 'Studio 54', '812 Club', 'Billings Lounge', 'UCLA Harpies Lounge', 'Harpies Lounge UCLA']:
        assert normalized_venue(name, str(DB), explicit=True) == name
        assert match_full_venue(name, str(DB), explicit=True) is not None
    for name in ['013', 'Preservation Hall Jazz Band', 'The Fillmore (late)', 'Quux Never Existed']:
        assert match_full_venue(name, str(DB)) is None
    for name in ['The Spectrum', '1st Bank Center', 'ABC Studio 211', 'PNC Bank Arts Center', '930 Club']:
        assert normalized_venue(name, str(DB), explicit=True) == name
    assert normalized_venue('Calvin Theatre', str(DB), city='Northampton', state='MA', explicit=True) == 'Calvin Theatre'
    assert normalized_venue('Lincoln Theater', str(DB), city='Hartford', state='CT', explicit=True) == 'Lincoln Theater'
    assert normalized_venue('TDGarden', str(DB), explicit=True) == 'TD Garden'
    assert normalized_venue('Pauley Pavillion', str(DB), explicit=True) == 'Pauley Pavilion'
    assert match_full_venue('812club', str(DB)) is None


def test_missing_corrupt_catalog_and_legacy_fallback(tmp_path):
    cfg = SimpleNamespace(tlo_dbs_dir=str(tmp_path))
    (tmp_path / 'venues.txt').write_text('Legacy Hall\n', encoding='utf-8')
    assert _known_venue_exact(cfg, 'Legacy Hall') == 'Legacy Hall'
    (tmp_path / 'venues.sqlite').write_text('invalid', encoding='utf-8')
    assert _known_venue_exact(cfg, 'Legacy Hall') == 'Legacy Hall'
    assert normalized_venue('Pauley Pavillion', str(tmp_path), explicit=True) == 'Pauley Pavillion'
    p = tmp_path / 'info.txt'
    p.write_text('Artist: Phish\nVenue: A Quux Hall\nLocation: Unknownshire, NH\nDate: 1997-01-02\n', encoding='utf-8')
    assert extract_setlist_venue_location(str(p), str(tmp_path)).venue == 'A Quux Hall'


def test_venue_master_staging_and_integrity(tmp_path):
    from tools.stage_venue_database import stage, validate
    src = tmp_path / 'source'
    dist = tmp_path / 'distribution'
    (src / 'TLO_DBs').mkdir(parents=True)
    dist.mkdir()
    master = src / 'TLO_DBs' / 'venues.sqlite'
    shutil.copyfile(DB / 'venues.sqlite', master)
    _, staged = stage(src, dist)
    assert staged.read_bytes() == master.read_bytes()
    master.write_bytes(b'invalid venue database')
    with pytest.raises(ValueError):
        validate(master)
    with pytest.raises(ValueError):
        stage(src, dist)
    assert staged.read_bytes() == (DB / 'venues.sqlite').read_bytes()


def test_venue_database_zip_manifest_and_hash(tmp_path):
    import json
    import zipfile
    from tools.verify_city_database_release import verify
    archive = tmp_path / 'candidate.zip'
    def make_zip(included, wrong=False):
        masters = ['artists.sqlite', 'venues.txt', 'cities.sqlite', 'venues.sqlite'] if included else []
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('UPDATE_MANIFEST.json', json.dumps({'kind': 'update', 'build_number': 726, 'databases_included': included, 'database_files': masters}))
            for name in masters:
                content = (DB / name).read_bytes() if (DB / name).is_file() else b'fixture'
                z.writestr('TLO_DBs/' + name, b'incorrect' if wrong and name == 'venues.sqlite' else content)
    make_zip(True)
    assert verify(archive, DB.parent, 726)['databases_included']
    make_zip(False)
    assert not verify(archive, DB.parent, 726)['databases_included']
    make_zip(True, wrong=True)
    with pytest.raises(ValueError, match='venue database contents'):
        verify(archive, DB.parent, 726)
