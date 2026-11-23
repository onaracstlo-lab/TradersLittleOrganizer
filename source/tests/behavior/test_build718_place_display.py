"""Build 720: all-uppercase venue/city output without rewriting source metadata."""

from __future__ import annotations

import pytest

from tlo_models import Candidate, ShowMetadata
from tlo_phase23_v2 import _build_show_name, _normalize_record_ascii_for_output
from tlo_place_display import display_place_case
from tlo_setlist_metadata_lookup import extract_setlist_venue_location

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize(("source", "kind", "want"), [
    ("CAPITOL THEATRE", "venue", "Capitol Theatre"),
    ("PORT CHESTER", "city", "Port Chester"),
    ("THE HOUSE OF BLUES", "venue", "The House of Blues"),
    ("9:30 CLUB", "venue", "9:30 Club"),
    ("MGM GRAND GARDEN ARENA", "venue", "MGM Grand Garden Arena"),
    ("CBGB", "venue", "CBGB"),
    ("ST. LOUIS", "city", "St. Louis"),
    ("LA PAZ", "city", "La Paz"),
    ("JOE'S PUB", "venue", "Joe's Pub"),
    ("MCDONALD'S PARK", "venue", "McDonald's Park"),
    ("THE O'BRIEN THEATRE", "venue", "The O'Brien Theatre"),
    ("МОСКВА", "city", "МОСКВА"),
    ("ROME", "city", "Rome"),
    ("AT&T CENTER", "venue", "AT&T Center"),
    ("MCMENAMINS CRYSTAL BALLROOM", "venue", "McMenamins Crystal Ballroom"),
    ("L’OLYMPIA", "venue", "L’Olympia"),
    ("NEW YORK NY", "location", "New York NY"),
    ("NY", "region", "NY"),
    ("McMenamins Crystal Ballroom", "venue", "McMenamins Crystal Ballroom"),
    ("iHeartRadio Theater", "venue", "iHeartRadio Theater"),
    ("Madison Square Garden", "venue", "Madison Square Garden"),
    ("the fillmore", "venue", "the fillmore"),
    ("北京", "city", "北京"),
])
def test_all_uppercase_display_only(source, kind, want):
    assert display_place_case(source, kind=kind) == want
    assert display_place_case(want, kind=kind) == want


def _record(*, artist="Bob Dylan", venue="CAPITOL THEATRE", city="PORT CHESTER",
            region="NY", country="", location="PORT CHESTER NY", setlist_file=""):
    rec = ShowMetadata(1, "original", "/shows/original", setlist_file, 0,
                       artist=artist, date="2015-05-22", venue=venue, city=city,
                       region=region, country=country, location=location)
    rec.show_name = _build_show_name(rec)
    return rec


def test_uppercase_folder_without_setlist_updates_all_final_fields():
    rec = _record()
    rec.evidence = {"venue": [Candidate("CAPITOL THEATRE", "path", 40)]}
    _normalize_record_ascii_for_output(rec)
    assert rec.venue == "Capitol Theatre"
    assert rec.city == "Port Chester"
    assert rec.region == "NY"
    assert rec.location == "Port Chester NY"
    assert rec.show_name == "Bob Dylan 2015-05-22 Capitol Theatre Port Chester NY"
    assert rec.evidence["venue"][0].value == "CAPITOL THEATRE"  # Original matching evidence is untouched.
    before = (rec.venue, rec.city, rec.location, rec.show_name)
    _normalize_record_ascii_for_output(rec)
    assert (rec.venue, rec.city, rec.location, rec.show_name) == before


def test_all_caps_artist_and_descriptor_are_not_modified():
    rec = _record(artist="R.E.M.")
    rec.descriptor = "SBD MASTER"
    rec.show_name = _build_show_name(rec)
    _normalize_record_ascii_for_output(rec)
    assert rec.artist == "R.E.M."
    assert rec.descriptor == "SBD MASTER"
    assert rec.show_name == "R.E.M. 2015-05-22 Capitol Theatre Port Chester NY SBD MASTER"


def test_artist_prefix_not_replaced_when_artist_name_matches_city():
    rec = _record(artist="PORT CHESTER", venue="THE ROXY", city="PORT CHESTER")
    _normalize_record_ascii_for_output(rec)
    assert rec.show_name.startswith("PORT CHESTER 2015-05-22")
    assert rec.show_name.endswith("The Roxy Port Chester NY")


def test_mixed_case_and_existing_punctuation_are_preserved():
    rec = _record(venue="McMenamins Crystal Ballroom", city="Port Chester", location="Port Chester, NY")
    original_show = rec.show_name
    _normalize_record_ascii_for_output(rec)
    assert rec.show_name == original_show
    assert rec.location == "Port Chester, NY"


def test_compliant_dash_format_remains_a_dash_not_a_date():
    rec = _record(venue="THE FILLMORE", city="", region="", location="")
    rec.date = ""
    rec.show_name = "Bob Dylan - THE FILLMORE"
    _normalize_record_ascii_for_output(rec)
    assert rec.show_name == "Bob Dylan - The Fillmore"


def test_uppercase_setlist_header_flows_to_all_output_fields(tmp_path):
    setlist = tmp_path / "setlist.txt"
    setlist.write_text(
        "Bob Dylan\nDate: 2015-05-22\nVenue: CAPITOL THEATRE\nCity: PORT CHESTER\nState: NY\n\n"
        "01. Song One\n02. Song Two\n", encoding="utf-8",
    )
    source = setlist.read_text(encoding="utf-8")
    extracted = extract_setlist_venue_location(str(setlist), str(tmp_path))
    assert extracted.venue == "CAPITOL THEATRE"
    assert extracted.city == "PORT CHESTER"
    rec = _record(venue=extracted.venue, city=extracted.city, location=extracted.location,
                  setlist_file=str(setlist))
    _normalize_record_ascii_for_output(rec)
    assert rec.show_name == "Bob Dylan 2015-05-22 Capitol Theatre Port Chester NY"
    assert source == setlist.read_text(encoding="utf-8")
