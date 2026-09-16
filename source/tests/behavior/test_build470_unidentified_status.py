"""Build 470: normal unidentifiedShows.txt housekeeping is not a GUI warning."""

__version__ = "v470"

import pytest

from tlo_ux import classify_issue_line

pytestmark = pytest.mark.behavior


def test_unidentified_shows_file_write_status_is_not_an_issue():
    assert classify_issue_line("POSTPROCESS: writing unidentifiedShows.txt...") is None


def test_zero_unidentified_shows_completion_status_is_not_an_issue():
    assert (
        classify_issue_line(
            "POSTPROCESS: writing unidentifiedShows.txt complete: 0 unresolved path(s) (0.00 sec)"
        )
        is None
    )


def test_real_unidentified_show_condition_remains_an_issue():
    issue = classify_issue_line(
        r"TAG_SKIP: C:\Shows\Unknown | show unidentified; leaving original folder untouched"
    )
    assert issue is not None
    assert issue.category == "Unidentified show"
