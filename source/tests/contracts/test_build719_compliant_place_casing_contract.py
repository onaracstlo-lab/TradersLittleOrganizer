"""Build 719: ensure macOS/Linux/Windows contract jobs exercise mixed-case String2."""
from __future__ import annotations

import pytest

from tlo_place_display import display_place_case

pytestmark = pytest.mark.contract


def test_raw_compliant_venue_with_upper_city_and_region_code():
    assert display_place_case("Calvin Theatre NORTHAMPTON, MA", kind="venue") == "Calvin Theatre Northampton, MA"
    assert display_place_case("Lincoln Theater W.HARTFORD, CT", kind="venue") == "Lincoln Theater W.Hartford, CT"
    assert display_place_case("THE GREAT MEADOW,FORT MASON, SAN FRANCSICO, CA", kind="venue") == "The Great Meadow,Fort Mason, San Francsico, CA"


def test_normalization_is_idempotent_without_rewriting_artist():
    raw = "Smith College NORTHAMPTON, MA"
    result = display_place_case(raw, kind="venue")
    assert result == "Smith College Northampton, MA"
    assert display_place_case(result, kind="venue") == result
    assert display_place_case("R.E.M.", kind="venue") == "R.E.M."
