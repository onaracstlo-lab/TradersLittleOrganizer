"""Regression using exact source folder names from the user-provided logs."""
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher, _compressed_artist_key, _letters_only
from tlo_inventory_update import _rename_add_shows_folder_compliantly
from tlo_phase23_v2 import _extract_metadata_for_group
from tlo_rename_safety import safe_rename_target
from tlo_text_utils import compact_ws, split_trailing_parenthetical_groups

pytestmark = pytest.mark.behavior
DB = Path(__file__).resolve().parents[2] / 'TLO_DBs'

CASES = [
    ("Black Rebel Motorcycle Club", "2013-05-17 Vic Theatre Chicago IL (24)",
     "2013-05-17 The Vic Theatre Chicago IL (24)"),
    ("Camper Van Beethoven", "2012-01-15 The Middle East Cambridge MA (mtx) (24)",
     "2012-01-15 Middle East Cambridge MA (mtx) (24)"),
    ("Dave Davies", "1997-11-29 Bottom Line NYC (late)",
     "1997-11-29 The Bottom Line NYC (late)"),
    ("Hot Tuna", "2003-11-22 Rams Head Annapolis MD (early)",
     "2003-11-22 Ramshead Annapolis MD (early)"),
    ("Jackie Greene", "2011-09-17 Barrel House San Francisco CA (24)",
     "2011-09-17 Barrelhouse San Francisco CA (24)"),
    ("Karl Denson’s Tiny Universe", "2011-11-05 Mt. Tabor Theater Portland OR (24)",
     "2011-11-05 Mt Tabor Theater Portland OR (24)"),
]


def path_only_record(root, name, artist, compliant, db):
    """Use the recorded artist identity and real cities/venues catalogs.

    No audio, source setlist, real artist database, or remote services are
    available; this is explicitly a folder-name test, not a full replay.
    """
    folder = root / name
    folder.mkdir()
    cfg = SimpleNamespace(compliant=compliant, current_volume_label='', current_slam='',
                          as_is_artist_name=False, compliant_artist_mode='master',
                          etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(db),
                          TLOHome=str(root), debug=False, rename_compliantly=True)
    master = compact_ws(artist)
    matcher = ArtistMatcher(db_path='')
    matcher.exact_map = {master.casefold(): {master}}
    matcher.compressed_map = {_compressed_artist_key(master): {master}}
    matcher.master_aliases = {master: [master]}
    matcher.master_norms = {master: {_letters_only(master)}}
    group = dict(group_number=1, main_dir_name=name, main_dir_path=str(folder),
                 setlist_file='', setlist_files=[], music_dirs=[str(folder)],
                 music_file_count=1, flac_tag_samples=[], flac_tag_artist_values=[],
                 flac_tag_album_values=[], flac_tag_albumartist_values=[],
                 flac_tag_date_values=[])
    return cfg, folder, _extract_metadata_for_group(cfg, group, matcher)[0]


@pytest.mark.parametrize('artist,original_tail,expected_tail', CASES)
@pytest.mark.parametrize('compliant', [True, False])
@pytest.mark.parametrize('catalog', [True, False])
def test_reported_original_suffix_through_metadata_and_rename(
        tmp_path, artist, original_tail, expected_tail, compliant, catalog):
    db = DB
    if not catalog:
        db = tmp_path / 'legacy'
        db.mkdir()
        shutil.copyfile(DB / 'cities.sqlite', db / 'cities.sqlite')
    full_name = f'{artist} {original_tail}'
    cfg, folder, record = path_only_record(tmp_path, full_name, artist, compliant, db)
    expected_suffix = split_trailing_parenthetical_groups(full_name)[1]
    assert record.show_name
    assert split_trailing_parenthetical_groups(record.show_name)[1] == expected_suffix
    assert record.parentheticals == ' '.join(expected_suffix)
    if compliant and catalog:
        assert record.show_name == f'{compact_ws(artist)} {expected_tail}'
    # Exercise a real rename of the *temporary fixture only*. A core-name
    # alias change may be refused by the existing conservative rename guard;
    # in either case the real resulting folder must retain every qualifier.
    item = folder / 'fixture.txt'
    item.write_bytes(b'recording identity fixture')
    renamed = Path(_rename_add_shows_folder_compliantly(cfg, str(folder), {
        'show_name': record.show_name, 'parentheticals': record.parentheticals,
        'artist': record.artist, 'date': record.date, 'main_dir_path': str(folder),
    }))
    assert renamed.is_dir()
    assert split_trailing_parenthetical_groups(renamed.name)[1] == expected_suffix
    assert (renamed / item.name).read_bytes() == b'recording identity fixture'


@pytest.mark.parametrize('source_suffix,target_suffix', [
    ('(late)', ''),
    ('(AUD) (late)', '(late) (AUD)'),
    ('(AUD (Remaster))', '(AUD) (Remaster)'),
    ('(AUD) (AUD)', '(AUD)'),
])
def test_folder_rename_guard_cannot_lose_or_rearrange_parenthetical_groups(source_suffix, target_suffix):
    # The words already occur in the name's core, so a set-of-words guard
    # alone would accept these destructive changes.
    core = 'Phish 1997-01-02 Late AUD Remaster Hall Boston, MA'
    src = f'{core} {source_suffix}'
    dst = f'{core} {target_suffix}'.rstrip()
    accepted, reason = safe_rename_target(src, dst, artist='Phish', date='1997-01-02')
    assert not accepted
    assert 'parenthetical' in reason


def test_guard_permits_additional_groups_and_normal_folding():
    src = 'Phish 1997-01-02 Example Hall (Aud) (Fránco)'
    dst = 'Phish 1997-01-02 Example Hall (AUD) (Franco) (24)'
    assert safe_rename_target(src, dst, artist='Phish', date='1997-01-02') == (dst, '')
