from tests import _release_artifacts as RA
from pathlib import Path

from docx import Document
import pytest


pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_build538_compatibility_entry_point_is_explicitly_not_release_gate():
    text = (ROOT / "test_tlo_requirements.py").read_text(encoding="utf-8")
    assert "Backward-compatibility subset entry point" in text
    assert "must not be used as the sole official release gate" in text
    assert "python -m pytest -q -p no:cacheprovider" in text


def test_build538_requirements_define_full_suite_as_release_contract():
    doc = Document(ROOT / RA.REQUIREMENTS_FILENAME)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "test_tlo_requirements.py" in text
    assert "backward-compatibility subset" in text
    assert "must not be used as the sole official release-test gate" in text
    assert "full categorized pytest suite" in text


