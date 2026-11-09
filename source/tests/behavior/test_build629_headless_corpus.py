"""Build 629: headless preference imports and frozen parsing guard examples."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as phase

ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((ROOT / 'tests/fixtures/golden_folder_parsing_v629.json').read_text())


def test_preference_parse_does_not_need_a_tk_root():
    pref = importlib.import_module('tlo_preferences')
    assert pref.parse_text(pref.default_text())['main']['artist_in_album']
    assert pref.edit.__name__ == 'edit'


@pytest.mark.parametrize('case', CORPUS, ids=[item['folder'][:30] for item in CORPUS])
def test_frozen_folder_name_expectations(case, tmp_path):
    folder = tmp_path / case['folder']; folder.mkdir()
    names = {
        'Jethro Tull': ['Jethro Tull'], 'The Kinks': ['The Kinks', 'Kinks', 'Kinks, The'],
        'The Who': ['The Who', 'Who', 'Who, The'], 'Twiddle': ['Twiddle'],
        'Grateful Dead': ['Grateful Dead'], 'Lucinda Williams': ['Lucinda Williams'],
    }
    matcher = ArtistMatcher(db_path='')
    matcher.master_aliases = names
    matcher.exact_map = {alias.casefold(): {master} for master, aliases in names.items() for alias in aliases}
    matcher.master_norms = {master: {''.join(c for c in alias.casefold() if c.isalnum())
                                   for alias in aliases} for master, aliases in names.items()}
    config = SimpleNamespace(compliant=False, current_slam='', current_volume_label='',
        as_is_artist_name=False, compliant_artist_mode='master', etree_lookup=False,
        setlistfm_lookup=False, TLOHome=str(tmp_path), tlo_dbs_dir=str(tmp_path), debug=False)
    group = {'group_number': 1, 'main_dir_name': case['folder'], 'main_dir_path': str(folder),
             'setlist_file': '', 'setlist_files': [], 'music_dirs': [str(folder)],
             'music_file_count': 1, 'flac_tag_samples': [], 'flac_tag_artist_values': [],
             'flac_tag_album_values': [], 'flac_tag_albumartist_values': [], 'flac_tag_date_values': []}
    record = phase._extract_metadata_for_group(config, group, matcher)[0]
    assert record.artist == case['artist']
    if case.get('date'):
        assert record.date == case['date']
    if case.get('city'):
        assert record.city == case['city']
    if case.get('not_city'):
        assert record.city != case['not_city']
    if case.get('not_date'):
        assert record.date != case['not_date']


pytestmark = pytest.mark.behavior
