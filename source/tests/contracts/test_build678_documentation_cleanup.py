"""Documentation-only release: verify current artifacts and no obsolete examples."""
from pathlib import Path
import csv
import re
from docx import Document
import pytest
import tlo_version as V
from tests import _release_artifacts as RA

ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.contract

def test_current_readme_contents_and_source_pointer():
    text=(ROOT/RA.SOURCE_README_FILENAME).read_text(encoding='utf-8')
    assert text.splitlines()[0].startswith(f'TLO Source Bundle v{V.BUNDLE_BUILD}')
    assert 'Native GitHub Build Process: v168' in text
    assert f'-bnumber {V.BUNDLE_BUILD}' in text and '-bnumber 672' not in text
    for name in ('SOURCE.txt','THIRD_PARTY_NOTICES.txt','LICENSE',
                 f'TLO_Inventory_Requirements_Working_v{V.BUNDLE_BUILD}.docx',
                 f'TLO_Inventory_User_Manual_v{V.BUNDLE_BUILD}.rtf',
                 f'RELEASE_NOTES_v{V.BUNDLE_BUILD}.txt','WINDOWS_TEST_REMEDIATION_v677.csv'):
        assert name in text and (ROOT/name).is_file()
    assert f'/releases/tag/v1.7-build{V.BUNDLE_BUILD}' in (ROOT/'SOURCE.txt').read_text()


def test_requirements_are_normative_not_a_revision_log():
    doc=Document(ROOT/RA.REQUIREMENTS_FILENAME)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert doc.core_properties.revision==V.BUNDLE_BUILD
    assert doc.core_properties.version==str(V.BUNDLE_BUILD)
    assert not re.search(r'\bBuild\s+\d+\b',text)
    assert 'Windows SHALL run its native GUI' in text
    assert 'Appendix K - Supplemental Current Operational Requirements' in text


def test_historical_docs_separated_and_windows_status_truthful():
    assert (ROOT/'docs/history/PHASE_REMEDIATION_v670.md').is_file()
    assert not (ROOT/'PHASE_REMEDIATION_v670.md').exists()
    rows=list(csv.DictReader((ROOT/'WINDOWS_TEST_REMEDIATION_v677.csv').open(encoding='utf8',newline='')))
    assert len(rows)==71 and all(row['Native acceptance']=='pending Windows hosted CI' for row in rows)
    assert (ROOT/f'CHANGES_v{V.BUNDLE_BUILD}.txt').read_text(encoding='utf-8').startswith(f'TLO {V.DISPLAY_VERSION}')
