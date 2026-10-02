"""Build 494 regression for Thorough Setlist Matching GUI capitalization."""

__version__ = "v497"

from pathlib import Path

import pytest

from tlo_options import OPTIONS_BY_FIELD

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.behavior


def test_build494_thorough_setlist_gui_label_is_capitalized_exactly():
    assert OPTIONS_BY_FIELD["thorough_setlist_matching"].gui_label == "Thorough Setlist Matching"
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'checkbox_text = "Thorough Setlist\\nMatching"' in source
    assert "Thorough setlist Matching" not in source


def test_build494_documentation_records_display_only_change():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v518.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v518.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "Current document version: v518 (TLO v1.7)." in req
    assert "Build 494: Thorough Setlist Matching GUI capitalization" in req
    assert "Thorough Setlist Matching" in req
    assert "Version v1.7 Build 518" in manual
    assert 'Build 494: The main-window checkbox label is now "Thorough Setlist Matching"' in manual
