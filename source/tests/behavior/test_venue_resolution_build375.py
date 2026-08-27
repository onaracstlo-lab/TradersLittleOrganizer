"""Build 375 regressions for setlist correction of weak path venue/location evidence."""

__version__ = "v407"

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _config():
    return SimpleNamespace(compliant=False, tlo_dbs_dir="")


def _setlist_result():
    from tlo_setlist_metadata_lookup import SetlistVenueLocationResult

    return SetlistVenueLocationResult(
        venue="Camp Springs Bluegrass Festival",
        city="Reidsville",
        region="NC",
        country="",
        location="Reidsville, NC",
        source="setlist_metadata:LOCATION_TRAILING_REGION",
        raw="Camp Springs Bluegrass Festival | Reidsville, NC",
        confidence=92,
    )


def test_selected_setlist_overrides_weaker_path_venue_and_city(monkeypatch):
    import tlo_phase23_v2 as phase
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=944,
        main_dir_name="Country Gentlemen 1971-09-03 04 05.Reidsville, NC",
        main_dir_path=r"D:\boots\Country Gentlemen 1971-09-03 04 05.Reidsville, NC",
        setlist_file=r"D:\boots\Country Gentlemen\cg1971-09.txt",
        music_file_count=21,
    )
    evidence = {}
    observations = []
    path_part = "Camp Springs Bluegrass Festival.1971-09-03 04 05.Reidsville NC"
    phase._apply_string2_to_record(
        record,
        {"string2": "04 05.Reidsville NC", "part": path_part},
        evidence,
    )
    assert (record.venue, record.city, record.region, record.location) == (
        "",
        "Reidsville",
        "NC",
        "Reidsville, NC",
    )

    monkeypatch.setattr(phase, "extract_setlist_venue_location", lambda *_a, **_k: _setlist_result())
    applied = phase._apply_setlist_metadata_to_noncompliant_record(
        _config(), record, evidence, observations
    )

    assert applied is True
    assert record.venue == "Camp Springs Bluegrass Festival"
    assert record.city == "Reidsville"
    assert record.region == "NC"
    assert record.country == ""
    assert record.location == "Reidsville, NC"
    assert not any("04" in item and "venue" in item for item in observations)
    assert any(
        candidate.value == "Camp Springs Bluegrass Festival" and candidate.confidence == 92
        for candidate in evidence.get("venue", [])
    )
    assert any(
        candidate.value == "Reidsville" and candidate.confidence == 92
        for candidate in evidence.get("city", [])
    )


def test_selected_setlist_does_not_override_stronger_etree_venue_location(monkeypatch):
    import tlo_phase23_v2 as phase
    from tlo_models import Candidate, ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="Country Gentlemen",
        main_dir_path=r"D:\boots\Country Gentlemen",
        setlist_file=r"D:\boots\Country Gentlemen\cg.txt",
        music_file_count=1,
        venue="Different Verified Venue",
        city="Greensboro",
        region="NC",
        location="Greensboro, NC",
    )
    evidence = {
        "venue": [Candidate(record.venue, "etreedb", 95)],
        "city": [Candidate(record.city, "etreedb", 95)],
        "region": [Candidate(record.region, "etreedb", 95)],
    }
    observations = []
    monkeypatch.setattr(phase, "extract_setlist_venue_location", lambda *_a, **_k: _setlist_result())

    phase._apply_setlist_metadata_to_noncompliant_record(_config(), record, evidence, observations)

    assert record.venue == "Different Verified Venue"
    assert record.city == "Greensboro"
    assert record.region == "NC"
    assert record.location == "Greensboro, NC"
    assert any("did not override existing venue" in item for item in observations)
    assert any("did not override existing city" in item for item in observations)


def test_path_parser_strips_festival_day_number_noise_before_city():
    import tlo_phase23_v2 as phase

    assert phase._parse_string2("04 05.Reidsville NC") == ("", "Reidsville", "NC", "", "")
