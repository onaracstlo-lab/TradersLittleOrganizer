"""Build 665: regression checks for the five Build 664 hosted Linux release failures."""
from pathlib import Path
import re
from docx import Document
import pytest
import tlo_preferences as pref
import tlo_version as V

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def test_all_choice_comments_allow_approved_spacing_and_list_all_values():
    text = pref.default_text()
    assert text == (ROOT / pref.FILENAME).read_text(encoding="utf-8")
    assert "# update_downloads : msi | zip (msi = Download .msi update; zip = Download .zip update)" in text
    assert pref.parse_text(text)["general"]["update_downloads"] == "msi"
    for (section, key), choices in pref.CHOICES.items():
        pattern = rf"(?m)^# {re.escape(key)}\s*:\s*{re.escape(' | '.join(choices))}"
        assert re.search(pattern, text), (section, key)


def test_current_readme_process_matches_verification_not_historical_literal():
    readme = (ROOT / f"SOURCE_BUNDLE_README_{V.VERSION}.txt").read_text(encoding="utf-8")
    verification = (ROOT / f"BUILD_VERIFICATION_{V.VERSION}.txt").read_text(encoding="utf-8")
    match = re.search(r"Native GitHub Build Process: (v\d+)", readme)
    assert match
    assert f"GitHub Build Process {match.group(1)}" in verification


def test_requirements_index_and_current_change_references_track_version():
    doc = Document(ROOT / f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx")
    paragraphs = [par.text for par in doc.paragraphs]
    index_heading = f"21. Revision Index (Build 398-{V.BUNDLE_BUILD})"
    assert index_heading in paragraphs
    ix = paragraphs.index(index_heading)
    appendix = next(i for i, par in enumerate(paragraphs) if par.startswith("Appendix A -"))
    revision_text = "\n".join(paragraphs[ix:appendix])
    assert f"Build {V.BUNDLE_BUILD}:" in revision_text
    assert f"current CHANGES_{V.VERSION}.txt" in revision_text
    assert f"CHANGES_v{V.BUNDLE_BUILD-1}.txt" not in revision_text
    assert doc.core_properties.revision == V.BUNDLE_BUILD
    assert f"Build {V.BUNDLE_BUILD}" in doc.core_properties.title
