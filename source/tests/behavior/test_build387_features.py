import pytest

pytestmark = pytest.mark.behavior
import tlo_phase23_v2 as phase

def test_build387_dash_string2_checks_date_and_location_before_album_fallback():
    parsed = phase._analyze_dash_string2_before_album("The Catalyst Santa Cruz CA 01-17-87")
    assert parsed["date"] == "1987-01-17"
    assert parsed["venue"] == "The Catalyst"
    assert parsed["city"] == "Santa Cruz"
    assert parsed["region"] == "CA"
    assert phase._analyze_dash_string2_before_album("A Spanner In The Works") == {}
