"""Build 502 contracts for the consolidated current requirements specification."""
from tests import _release_artifacts as RA


from pathlib import Path

import pytest
from docx import Document

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
REQ = ROOT / RA.REQUIREMENTS_FILENAME


def _paragraphs():
    return [p.text.strip() for p in Document(REQ).paragraphs if p.text.strip()]


def _text():
    return "\n".join(_paragraphs())


def test_build502_page1_title_purpose_and_country_note_are_current():
    paragraphs = _paragraphs()
    assert paragraphs[0] == "Traders Little Organizer Requirements - Consolidated Current Specification"
    assert paragraphs[1] == (
        "Purpose: To provide a set of functions for music traders and collectors who want to inventory, tag, search, update, manage and share a collection of music performances. "
        "The goal is to identify performance Artist, Date, Venue, Location (City, State/Region, and Country*) and disk storage location of each show, provide a collection of setlist files and make the data linked and searchable."
    )
    assert paragraphs[2] == "*Only if the country is not the United States"


def test_build502_removes_development_and_relative_wording_from_normative_text():
    text = _text()
    for obsolete in [
        "Do not implement unrequested fallback approaches",
        "Continue updating the current implementation of phases 2 and 3",
        "If faster, keep a cache",
        "Voting logic may be added later",
        "30 percent shorter than the prior oversized version",
        "If possible, reuse tlo-gi.py",
        "Spread out text input box lines slightly more horizontally than before",
        "extract the adjacent decision into a named, directly testable helper",
        "Build 383 reversal regression:",
        "Build 384 reversal regression:",
    ]:
        assert obsolete not in text
    assert "The User Manual must warn that OS-specific aliases" in text
    assert "16.2 Availability, Timeout, and External Command Safety" in text
    assert "16.4 Diagnostic Logging and Exception-Handling Policy" in text


def test_build502_revision_index_is_navigational_and_bounded():
    paragraphs = _paragraphs()
    heading = next(x for x in paragraphs if x.startswith("21. Revision Index (Build 398-"))
    idx = paragraphs.index(heading)
    appendix_idx = paragraphs.index("Appendix A - Requirements Traceability Matrix")
    tail = paragraphs[idx:appendix_idx]
    text = "\n".join(tail)
    assert "This index is navigational rather than normative." in text
    assert "Build 501:" in text
    assert "Build 502:" in text
    # The Build 500 review measured the old index at roughly 63k characters.
    # Keep the consolidated pointer index materially smaller than that history dump.
    assert len(text) < 20000
    assert "detailed historical build narratives are archived in old-change-logs.zip" in text.lower()


def test_build502_current_package_names_and_version_are_aligned():
    assert REQ.is_file()
    assert (ROOT / RA.MANUAL_FILENAME).is_file()
    assert (ROOT / RA.SOURCE_README_FILENAME).is_file()
    assert (ROOT / RA.CHANGES_FILENAME).is_file()
