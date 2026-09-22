"""Build 489 Help > About support email wording."""

__version__ = "v490"

from pathlib import Path
from docx import Document
import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_build489_about_uses_support_email_and_removes_placeholder():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert '"Contact me at: support@traderslittleorganizer.com"' in source
    assert "onaracs.tlo of gmail" not in source
    assert "onaracs.tlo of g.mail" not in source


def test_build489_documents_record_about_contact_change():
    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v490.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v490.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8", errors="ignore")
    assert "Current document version: v490 (v1.7 Build 490)." in req
    assert "support@traderslittleorganizer.com" in req
    assert "Build 489" in manual and "support@traderslittleorganizer.com" in manual
    assert "Build 489" in faq and "support@traderslittleorganizer.com" in faq
