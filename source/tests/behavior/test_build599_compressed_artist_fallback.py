"""Build 599: unique compressed Artist DB lookup for etree-style show folders."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher, load_artist_matcher, lookup_artist_master_with_status
import tlo_phase23_v2 as phase

pytestmark = pytest.mark.behavior

FOLDER = "weather-report1975-10-07.146696.sbd.mee.flac1644"


def _db_matcher(tmp_path: Path, monkeypatch) -> ArtistMatcher:
    database = tmp_path / "artists.sqlite"
    with sqlite3.connect(database) as conn:
        conn.executescript("""
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, master_name TEXT NOT NULL);
        CREATE TABLE terms (term_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL,
                            term_text TEXT NOT NULL, term_type TEXT NOT NULL,
                            term_order INTEGER NOT NULL);
        INSERT INTO artists VALUES (1, 'Weather Report');
        INSERT INTO terms VALUES (1, 1, 'Weather Report', 'master', 0);
        INSERT INTO terms VALUES (2, 1, 'weatherreport', 'compressed', 1);
        """)
    monkeypatch.setattr('tlo_artist_db.validate_artist_sqlite', lambda config: str(database))
    return load_artist_matcher(SimpleNamespace())


def _group(tmp_path: Path, *, with_setlist: bool) -> dict:
    folder = tmp_path / FOLDER
    folder.mkdir()
    setlist = folder / 'info.txt'
    if with_setlist:
        setlist.write_text('Artist: Weather Report\nDate: 1975-10-07\n\n01. Original Tune\n', encoding='utf-8')
    return {
        'group_number': 1, 'main_dir_name': FOLDER, 'main_dir_path': str(folder),
        'setlist_file': str(setlist) if with_setlist else '',
        'setlist_files': [str(setlist)] if with_setlist else [],
        'txt_files': [str(setlist)] if with_setlist else [],
        'music_dirs': [str(folder)], 'music_files': [str(folder / '01.flac')],
        'music_file_count': 1,
    }


def _config(tmp_path: Path, *, compliant: bool) -> SimpleNamespace:
    return SimpleNamespace(
        compliant=compliant, current_volume_label='', current_slam='',
        as_is_artist_name=False, compliant_artist_mode='master',
        etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(tmp_path),
        TLOHome=str(tmp_path), debug=False,
    )


def test_artist_db_uses_stored_lowercase_compressed_term(tmp_path, monkeypatch):
    matcher = _db_matcher(tmp_path, monkeypatch)
    assert matcher.compressed_map['weatherreport'] == {'Weather Report'}
    assert lookup_artist_master_with_status('weather-report', matcher) == ('matched', ['Weather Report'])
    assert lookup_artist_master_with_status('WEATHER_REPORT', matcher) == ('matched', ['Weather Report'])
    assert lookup_artist_master_with_status('Weather Report', matcher) == ('matched', ['Weather Report'])
    assert lookup_artist_master_with_status('weather-report1975', matcher) == ('no_match', [])


def test_exact_master_beats_compressed_collision_and_ambiguous_fallback_is_rejected():
    matcher = ArtistMatcher('')
    matcher.exact_map = {'a-b': {'A-B'}, 'ab': {'AB'}}
    matcher.master_aliases = {'A-B': ['A-B'], 'AB': ['AB']}
    matcher.compressed_map = {'ab': {'A-B', 'AB'}}
    assert lookup_artist_master_with_status('A-B', matcher) == ('matched', ['A-B'])
    assert lookup_artist_master_with_status('AB', matcher) == ('matched', ['AB'])
    assert lookup_artist_master_with_status('A B', matcher) == ('collision', ['A-B', 'AB'])


def test_compressed_normalization_retains_artist_digits():
    matcher = ArtistMatcher('')
    matcher.exact_map = {'10cc': {'10cc'}, 'cc': {'CC'}}
    matcher.master_aliases = {'10cc': ['10cc'], 'CC': ['CC']}
    matcher.compressed_map = {'10cc': {'10cc'}, 'cc': {'CC'}}
    assert lookup_artist_master_with_status('10-cc', matcher) == ('matched', ['10cc'])
    assert lookup_artist_master_with_status('c-c', matcher) == ('matched', ['CC'])


def test_setlist_folder_agreement_allows_compressed_prefix_only_when_date_immediately_follows():
    assert phase._artist_agrees_with_leading_show_folder('Weather Report', FOLDER)
    assert not phase._artist_agrees_with_leading_show_folder('Weather Report', 'weather-reporter1975-10-07.sbd')
    assert not phase._artist_agrees_with_leading_show_folder('Weather Report', 'other-weather-report1975-10-07.sbd')
    assert not phase._artist_agrees_with_leading_show_folder('Weather Report', 'weather-report1975.sbd')
    assert not phase._artist_agrees_with_leading_show_folder('Other Artist', FOLDER)


@pytest.mark.parametrize('compliant', [False, True])
@pytest.mark.parametrize('with_setlist', [False, True])
def test_actual_etree_folder_identifies_weather_report_and_date(
    tmp_path, monkeypatch, compliant, with_setlist
):
    matcher = _db_matcher(tmp_path, monkeypatch)
    group = _group(tmp_path, with_setlist=with_setlist)
    record, date_matches, unresolved = phase._extract_metadata_for_group(
        _config(tmp_path, compliant=compliant), group, matcher
    )
    assert record.artist == 'Weather Report'
    assert record.date == '1975-10-07'
    assert record.show_name.startswith('Weather Report 1975-10-07')
    assert not record.artist_not_in_database
    assert 'unable to identify artist' not in unresolved
    assert any(item['normalized'] == '1975-10-07' for item in date_matches)


def test_as_is_artist_mode_preserves_raw_folder_spelling(tmp_path, monkeypatch):
    matcher = _db_matcher(tmp_path, monkeypatch)
    group = _group(tmp_path, with_setlist=False)
    config = _config(tmp_path, compliant=True)
    config.as_is_artist_name = True
    record, _, unresolved = phase._extract_metadata_for_group(config, group, matcher)
    assert record.artist == 'weather-report'
    assert 'unable to identify artist' not in unresolved
