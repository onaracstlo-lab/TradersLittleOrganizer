from tests._release_artifacts import release_history
from tests import _release_artifacts as RA
from pathlib import Path

from docx import Document

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_build539_version_and_documents_are_current():
    assert (ROOT / RA.REQUIREMENTS_FILENAME).is_file()
    assert (ROOT / RA.MANUAL_FILENAME).is_file()


def test_build539_requirements_and_changes_record_process_v107_action_pinning():
    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    for text in (req, changes):
        assert "GitHub Build Process v107" in text
    assert "Build 540" in release_history()
    assert "full 40-character commit SHA" in changes
    assert "Application runtime behavior is unchanged" in changes
