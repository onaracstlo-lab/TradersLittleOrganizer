"""Build 489 Help > About support email wording."""
from tests._release_artifacts import release_history
from tests import _release_artifacts as RA


from pathlib import Path
from docx import Document
import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_build489_about_uses_support_email_and_removes_placeholder():
    source = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    assert '"Contact me at: support@traderslittleorganizer.com"' in source
    assert "onaracs.tlo of gmail" not in source
    assert "onaracs.tlo of g.mail" not in source


def test_build489_documents_record_about_contact_change():
    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8", errors="ignore")
    assert "support@traderslittleorganizer.com" in req
    assert "Build 489" in release_history() and "support@traderslittleorganizer.com" in release_history()
    assert "Help > About lists support@traderslittleorganizer.com as the TLO contact email." in faq
