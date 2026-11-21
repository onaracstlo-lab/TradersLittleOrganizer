"""Build 694: date-range boundaries, including user-facing path parsing."""
from __future__ import annotations

from datetime import date

import pytest

import tlo_phase23_v2 as parser

pytestmark = pytest.mark.behavior


class DateOnNov18(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 18)


def test_date_range_checks_every_day_not_just_canonical_day(monkeypatch):
    monkeypatch.setattr(parser, 'date', DateOnNov18)
    assert parser._normalize_date('2026', '11', '19') == ''
    assert parser._normalize_same_month_day_range('2026', '11', '18-19') == ''
    assert parser._normalize_same_month_day_range('2026', '11', '17-18') == '2026-11-17'
    assert parser._normalize_same_month_day_range('2026', '12', '1-2') == ''


def test_future_ranges_are_not_accepted_by_real_path_parser(monkeypatch):
    monkeypatch.setattr(parser, 'date', DateOnNov18)
    for name in ('Wilco 2026-11-18-19 Manchester', 'Wilco November 18-19, 2026',
                 'Wilco 2026-12-01-02 Manchester'):
        assert parser._find_date_matches(name) == [], name
    earlier = parser._find_date_matches('Wilco 2026-11-17-18 Manchester')
    assert len(earlier) == 1
    assert earlier[0]['normalized'] == '2026-11-17'


def test_historic_ranges_and_simple_dates_keep_existing_behavior():
    # Preserve existing release behavior for known concerts and partial dates.
    assert parser._normalize_same_month_day_range('1970', '04', '12-13') == '1970-04-12'
    assert parser._normalize_date('1970', '04', '12') == '1970-04-12'
