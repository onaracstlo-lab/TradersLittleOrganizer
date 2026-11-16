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
    assert paragraphs[0] == "Traders Little Organizer (TLO) — Functional and Technical Requirements"
    assert paragraphs[1].startswith("Purpose. TLO inventories, tags, searches, updates, manages")
    assert "City and State/Region" in paragraphs[1]
    assert paragraphs[2] == "Location convention: omit Country for United States performances."


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


def test_current_requirements_have_no_revision_index_or_change_log():
    paragraphs = _paragraphs()
    text = "\n".join(paragraphs)
    assert "21. Revision Index" not in text
    assert "Appendix K - Historical Build Amendments" not in text
    assert "Appendix A - Requirements Traceability Matrix" in text
    assert "Appendix K - Supplemental Current Operational Requirements" in text
    assert "TLO_Requirements_Catalog_v" in text
    assert "release notes outside this specification" not in text


def test_build502_current_package_names_and_version_are_aligned():
    assert REQ.is_file()
    assert (ROOT / RA.MANUAL_FILENAME).is_file()
    assert (ROOT / RA.SOURCE_README_FILENAME).is_file()
    assert (ROOT / RA.CHANGES_FILENAME).is_file()
