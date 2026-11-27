"""Recording qualifiers are retained while matching only the venue/location."""
import shutil

import pytest

from tests.behavior.test_build726_venue_catalog import DB, case
from tlo_phase23_v2 import _merge_parenthetical_items
from tlo_place_display import replace_place_in_show_tail
from tlo_text_utils import split_trailing_parenthetical_groups

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize('compliant', [False, True])
@pytest.mark.parametrize('catalog', [False, True])
@pytest.mark.parametrize('venue,suffix', [
    ('Pauley Pavillion Los Angeles, CA', '(AUD (Remaster)) (24)'),
    ('PAULEY PAVILION Los Angeles, CA', '(PAULEY PAVILION source) (24)'),
    ('Quux Community Hall Unknownshire, NH', '(mtx) (24)'),
    ('Pauley Pavillion Los Angeles, CA', '(late)'),
    ('Pauley Pavillion Los Angeles, CA', '(24) (SBD)'),
])
def test_recording_suffix_survives(tmp_path, compliant, catalog, venue, suffix):
    db = DB
    if not catalog:
        db = tmp_path / 'legacy'
        db.mkdir()
        shutil.copyfile(DB / 'cities.sqlite', db / 'cities.sqlite')
    record = case(tmp_path, f'Phish 1997-01-02 {venue} {suffix}', compliant, db)
    assert record.show_name.endswith(' ' + suffix)
    assert record.parentheticals == suffix
    if catalog and venue.startswith('Pauley'):
        assert 'Pauley Pavilion Los Angeles, CA' in record.show_name
    if 'Quux' in venue:
        assert 'Quux Community Hall' in record.show_name


@pytest.mark.parametrize('compliant', [False, True])
def test_venue_only_path_with_qualifier(tmp_path, compliant):
    record = case(tmp_path, 'Phish 1997-01-02 TDGarden (SBD)', compliant, DB)
    assert record.show_name == 'Phish 1997-01-02 TD Garden (SBD)'


def test_balanced_groups_and_nonterminal_parentheses():
    assert split_trailing_parenthetical_groups('Room (East) Hall (AUD (Remaster)) (24)') == (
        'Room (East) Hall', ('(AUD (Remaster))', '(24)'))
    assert split_trailing_parenthetical_groups('Room (East) Hall') == ('Room (East) Hall', ())
    assert split_trailing_parenthetical_groups('Room (unfinished') == ('Room (unfinished', ())
    assert _merge_parenthetical_items('(AUD (Remaster)) (24)', '(24)', '(late)') == '(AUD (Remaster)) (24) (late)'


def test_place_replacement_leaves_suffix_and_artist_unchanged():
    name = 'Pauley Pavillion 1997-01-02 Pauley Pavillion (Pauley Pavillion source (AUD))'
    assert replace_place_in_show_tail(name, 'Pauley Pavillion', (('Pauley Pavillion', 'Pauley Pavilion'),)) == (
        'Pauley Pavillion 1997-01-02 Pauley Pavilion (Pauley Pavillion source (AUD))')
