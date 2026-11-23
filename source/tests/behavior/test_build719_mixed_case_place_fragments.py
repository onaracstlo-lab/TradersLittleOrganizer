"""Build 719: path-only String2 may mix title-case venue and caps city."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
from tlo_phase23_v2 import _extract_metadata_for_group_compliant, _normalize_record_ascii_for_output
from tlo_place_display import display_place_case
from tlo_models import ShowMetadata

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize(("raw", "expected"), [
    (
        "Albert King w Santana 1986-09-14 THE GREAT MEADOW,FORT MASON, SAN FRANCSICO, CA",
        "Albert King w Santana 1986-09-14 The Great Meadow,Fort Mason, San Francsico, CA",
    ),
    (
        "Indigo Girls 2003-08-11 Calvin Theatre NORTHAMPTON, MA",
        "Indigo Girls 2003-08-11 Calvin Theatre Northampton, MA",
    ),
    (
        "Indigo Girls 2009-04-18 Lincoln Theater W.HARTFORD, CT",
        "Indigo Girls 2009-04-18 Lincoln Theater W.Hartford, CT",
    ),
    (
        "Indigo Girls 1990-12-08 Smith College NORTHAMPTON, MA",
        "Indigo Girls 1990-12-08 Smith College Northampton, MA",
    ),
    (
        "Indigo Girls 1993-05-07 franklin & marshall college LANCASTER, PA",
        "Indigo Girls 1993-05-07 franklin & marshall college Lancaster, PA",
    ),
])
def test_actual_examples_compliant_folder_no_setlist(raw, expected):
    """Do not infer new city structure in compliant mode; fix display only."""
    config = SimpleNamespace(
        compliant=True, compliant_artist_mode="as-is", current_volume_label="",
        etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir="TLO_DBs",
    )
    group = {
        "group_number": 1, "main_dir_name": raw,
        "main_dir_path": "/shows/" + raw, "music_file_count": 0,
        "setlist_file": "", "setlist_files": [], "music_dirs": [],
    }
    record, _, unresolved = _extract_metadata_for_group_compliant(
        config, group, ArtistMatcher(db_path="")
    )
    assert not unresolved
    assert record.show_name == expected
    assert record.main_dir_name == raw
    assert record.city == ""  # compliant mode deliberately preserves raw String2
    assert record.location == ""
    assert record.venue == expected.split(record.date + " ", 1)[1]
    assert record.album_name == record.venue
    original_evidence = record.evidence["venue"][0].value
    assert original_evidence in raw
    _normalize_record_ascii_for_output(record)
    assert record.show_name == expected  # idempotent
    assert record.evidence["venue"][0].value == original_evidence


@pytest.mark.parametrize(("source", "want"), [
    ("Calvin Theatre NORTHAMPTON, MA", "Calvin Theatre Northampton, MA"),
    ("Lincoln Theater W.HARTFORD, CT", "Lincoln Theater W.Hartford, CT"),
    ("franklin & marshall college LANCASTER, PA", "franklin & marshall college Lancaster, PA"),
    ("THE GREAT MEADOW,FORT MASON, SAN FRANCSICO, CA", "The Great Meadow,Fort Mason, San Francsico, CA"),
    ("The BEACON THEATRE", "The Beacon Theatre"),
    ("The MGM GRAND", "The MGM Grand"),
    ("AT&T CENTER BOSTON, MA", "AT&T Center Boston, MA"),
    ("Garden NEW YORK NY", "Garden New York NY"),
    ("Garden INDIANAPOLIS, IN", "Garden Indianapolis, IN"),
    ("iHeartRadio Festival", "iHeartRadio Festival"),
    ("McMenamins Crystal Ballroom", "McMenamins Crystal Ballroom"),
    ("the fillmore", "the fillmore"),
    ("北京 CITY HALL", "北京 CITY HALL"),
])
def test_only_uppercase_place_fragments_change(source, want):
    assert display_place_case(source, kind="venue") == want
    assert display_place_case(want, kind="venue") == want


def test_partially_uppercase_location_from_setlist_is_consistent():
    rec = ShowMetadata(1, "original", "/shows/original", "", 0,
        artist="Indigo Girls", date="2003-08-11", venue="Calvin Theatre",
        city="NORTHAMPTON", region="MA", location="NORTHAMPTON, MA",
        album_name="Collector MIX", show_name="Indigo Girls 2003-08-11 Calvin Theatre NORTHAMPTON, MA")
    _normalize_record_ascii_for_output(rec)
    assert rec.city == "Northampton"
    assert rec.region == "MA"
    assert rec.location == "Northampton, MA"
    assert rec.show_name == "Indigo Girls 2003-08-11 Calvin Theatre Northampton, MA"
    assert rec.album_name == "Collector MIX"  # independent album is not overwritten
