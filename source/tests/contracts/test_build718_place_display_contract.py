"""Build 718: cross-platform output normalization contract, included in macOS CI."""
from __future__ import annotations

import pytest

from tlo_models import ShowMetadata
from tlo_phase23_v2 import _build_show_name, _normalize_record_ascii_for_output
from tlo_place_display import display_place_case

pytestmark = pytest.mark.contract


def test_uppercase_place_fields_become_consistent_with_show_identity():
    rec = ShowMetadata(1, 'R.E.M. 1989-01-01 THE FILLMORE', '/shows/path', '', 0,
                       artist='R.E.M.', date='1989-01-01', venue='THE FILLMORE',
                       city='SAN FRANCISCO', region='CA', location='SAN FRANCISCO CA')
    rec.show_name = _build_show_name(rec)
    _normalize_record_ascii_for_output(rec)
    assert (rec.artist, rec.venue, rec.city, rec.location) == (
        'R.E.M.', 'The Fillmore', 'San Francisco', 'San Francisco CA')
    assert rec.show_name == 'R.E.M. 1989-01-01 The Fillmore San Francisco CA'
    assert rec.main_dir_name == 'R.E.M. 1989-01-01 THE FILLMORE'


def test_mixed_case_names_and_known_acronyms_are_not_corrupted():
    assert display_place_case('McMenamins Crystal Ballroom') == 'McMenamins Crystal Ballroom'
    assert display_place_case('MGM GRAND GARDEN ARENA') == 'MGM Grand Garden Arena'
    assert display_place_case('CBGB') == 'CBGB'
    assert display_place_case('LOS ANGELES', kind='city') == 'Los Angeles'
