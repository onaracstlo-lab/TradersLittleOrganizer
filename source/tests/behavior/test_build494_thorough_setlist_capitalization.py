"""Build 494 regression for Thorough Setlist Matching GUI capitalization."""
from tests._release_artifacts import release_history
from tests import _release_artifacts as RA


from pathlib import Path

import pytest

from tlo_options import OPTIONS_BY_FIELD

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.behavior


def test_build494_thorough_setlist_gui_label_is_capitalized_exactly():
    assert OPTIONS_BY_FIELD["thorough_setlist_matching"].gui_label == "Thorough Setlist Matching"
    source = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    assert 'checkbox_text = "Thorough Setlist\\nMatching"' in source
    assert "Thorough setlist Matching" not in source


def test_build494_documentation_records_display_only_change():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    assert "Build 494: Thorough Setlist Matching GUI capitalization" in req
    assert "Thorough Setlist Matching" in req
    assert 'Build 494 - The main-window checkbox label is now "Thorough Setlist Matching"' in release_history()
