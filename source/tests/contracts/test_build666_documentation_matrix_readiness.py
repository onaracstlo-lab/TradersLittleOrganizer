"""Current docs present normative rules without release histories and a matrix-ready catalog."""
from pathlib import Path
import csv
import re
from docx import Document
import pytest
import tlo_version as V

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def test_no_historical_change_sections_in_either_user_document():
    d = Document(ROOT / f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx")
    content = "\n".join(p.text for p in d.paragraphs)
    assert "21. Revision Index" not in content
    assert "Appendix K - Historical Build Amendments" not in content
    assert "CHANGES_v" not in content
    assert not re.search(r"\bBuild\s+\d+\b", content)
    rtf = (ROOT / f"TLO_Inventory_User_Manual_{V.VERSION}.rtf").read_text(encoding="utf8")
    assert "What's New" not in rtf
    assert "Recent release changes" not in rtf
    assert "CHANGES_v" not in rtf
    assert rf"\title TLO Inventory User Manual {V.VERSION}" in rtf
    assert "update_downloads = msi" in rtf
    assert "update_downloads = zip" in rtf


def test_matrix_preparation_catalog_has_unique_locators_and_unfilled_test_fields():
    path = ROOT / f"TLO_Requirements_Catalog_{V.VERSION}.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 700
    assert len({r["Requirement_ID"] for r in rows}) == len(rows)
    assert all(r["Source_Locator"] and r["Section"] and r["Requirement_Text"] for r in rows)
    assert all(not r["Test_ID"] and not r["Verification_Status"] for r in rows)
    assert any(r["Needs_Atomization"] == "yes" for r in rows)
    assert any(r["Section"].startswith("20.") for r in rows)
