"""Build 650: precisely the current three release documents, no old archive."""
from pathlib import Path
from docx import Document
import pytest
from tests import _release_artifacts as A
import tlo_version as V

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_exactly_one_current_manual_specification_and_changelog():
    expected = {A.MANUAL_FILENAME, A.REQUIREMENTS_FILENAME, A.CHANGES_FILENAME}
    present = {p.name for p in ROOT.iterdir() if p.is_file() and (
        p.name.startswith('TLO_Inventory_User_Manual_v')
        or p.name.startswith('TLO_Inventory_Requirements_Working_v')
        or p.name.startswith('CHANGES_v')
        or p.name == 'old-change-logs.zip')}
    assert present == expected


def test_current_specification_is_complete_and_normative():
    doc = Document(ROOT / A.REQUIREMENTS_FILENAME)
    body = '\n'.join(p.text for p in doc.paragraphs)
    assert len(body) > 400_000
    assert len(doc.tables) >= 10
    assert 'Appendix K - Historical Build Amendments (Reference Only)' in body
    assert f'Current document version: {V.VERSION} (TLO v{V.PUBLIC_VERSION}).' in body
    assert doc.core_properties.subject == f'Consolidated current specification for TLO {V.DISPLAY_VERSION}'
    assert doc.core_properties.revision == V.BUNDLE_BUILD
    assert 'consolidated Requirements Specification DOCX' in body
    assert 'current CHANGES file' in body
    assert 'old-change-logs.zip' not in body


def test_current_manual_and_historical_changelog_consistent():
    manual = (ROOT / A.MANUAL_FILENAME).read_text(encoding='utf8')
    history = (ROOT / A.CHANGES_FILENAME).read_text(encoding='utf8')
    readme = (ROOT / A.SOURCE_README_FILENAME).read_text(encoding='utf8')
    assert f'Version {V.DISPLAY_VERSION}' in manual
    assert rf'\title TLO Inventory User Manual v{V.BUNDLE_BUILD}' in manual
    assert history.startswith(f'TLO {V.DISPLAY_VERSION}')
    assert 'Historical record: CHANGES_v353.txt' in history
    assert f'Bundle v{V.BUNDLE_BUILD}' in readme.splitlines()[0]
    assert 'Native GitHub Build Process: v129' in readme
