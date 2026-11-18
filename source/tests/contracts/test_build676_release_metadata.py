"""Build 676: the corresponding-source tag and notices are release-build contracts."""
from pathlib import Path
import pytest
pytestmark = pytest.mark.contract
from docx import Document
from tlo_version import BUNDLE_BUILD, VERSION
ROOT=Path(__file__).resolve().parents[2]

def test_corresponding_source_and_notices_match_current_build():
    source=(ROOT/'SOURCE.txt').read_text(encoding='utf8')
    notices=(ROOT/'THIRD_PARTY_NOTICES.txt').read_text(encoding='utf8')
    assert source.count(f'/releases/tag/v1.7-build{BUNDLE_BUILD}')==1
    assert f'Traders Little Organizer Build {BUNDLE_BUILD}' in notices
    assert f'/releases/tag/v1.7-build{BUNDLE_BUILD-1}' not in source

def test_requirements_document_has_safety_and_duplicate_contract():
    d=Document(ROOT/f'TLO_Inventory_Requirements_Working_{VERSION}.docx')
    text='\n'.join(p.text for p in d.paragraphs)
    assert d.core_properties.version==str(BUNDLE_BUILD)
    assert '--duplicates-dir DIR' in text
    assert 'REQ-SAFE-676' in text and 'REQ-DND-676' in text
