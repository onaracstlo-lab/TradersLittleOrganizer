"""Build 644: verify published instructions match current safety behavior."""
import pytest
pytestmark = pytest.mark.behavior
from pathlib import Path
from docx import Document
from tlo_version import VERSION, DISPLAY_VERSION

ROOT=Path(__file__).resolve().parents[2]

def test_faq_corruption_and_duplicate_policy_current():
    faq=(ROOT/'TLO-FAQ.txt').read_text(encoding='utf-8')
    assert 'the default corruption policies are Keep and report for files and Never for folders' in faq
    assert 'Content hashes and byte comparisons are not used for duplicate identification' in faq
    assert "every file's byte contents must all match" not in faq


def test_city_and_shn_recovery_documentation_current():
    faq=(ROOT/'TLO-FAQ.txt').read_text(encoding='utf-8')
    assert 'adds valid non-conflicting city records' in faq
    assert '.tlo-shn-originals/<unique-id>/<original-filename>' in faq
    assert 'atomic no-overwrite rename' in faq
    manual=(ROOT/f'TLO_Inventory_User_Manual_{VERSION}.rtf').read_text(encoding='utf-8')
    assert 'Defaults are Delete corrupt files and 100% corrupt only' not in manual
    assert 'the current clipboard/paste buffer' not in manual
    assert 'Optional city reference' in manual
    assert f'Version {DISPLAY_VERSION}' in manual


def test_requirements_no_stale_current_default_or_document_revision():
    doc=Document(ROOT/f'TLO_Inventory_Requirements_Working_{VERSION}.docx')
    alltext='\n'.join(p.text for p in doc.paragraphs)
    assert f'Current document version: {VERSION}' in alltext
    assert 'REQ-CORR-000  Full Inventory defaults are Corrupt files = Delete' not in alltext
    assert 'REQ-CORR-000  Full Inventory and standalone tlo-tag default to Corrupt files = Keep' in alltext
    assert 'earlier release live cosmetic-preference application' not in alltext
    assert doc.core_properties.subject == f'Consolidated current specification for TLO {DISPLAY_VERSION}'


def test_source_build_gate_runner_is_not_a_pass_claim():
    verifier=(ROOT/'tools/verify_release_gates.py').read_text(encoding='utf-8')
    assert 'ruff' in verifier and 'pytest' in verifier
    assert 'return 1' in verifier
