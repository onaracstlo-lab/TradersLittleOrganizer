"""Build 740: stale/contaminated evidence must fail local source hygiene."""
import json
from pathlib import Path

import pytest

from tlo_version import BUNDLE_BUILD
from tools.check_release_hygiene import BUILD_681_FINDINGS, remediation_evidence_errors

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def evidence():
    return json.loads((ROOT / 'TLO_RELEASE_REMEDIATION.json').read_text(encoding='utf-8'))


def test_current_remediation_evidence_is_release_ready():
    current = evidence()
    assert len(BUILD_681_FINDINGS) == 25
    assert current['build'] == BUNDLE_BUILD
    assert set(current['findings']) == BUILD_681_FINDINGS
    assert remediation_evidence_errors(current, ROOT, BUNDLE_BUILD) == []
    assert current['supplemental_findings']['STORAGE736']['test'] == 'tests/behavior/test_build736_storage_identities.py'
    assert current['supplemental_findings']['RENAME737']['test'] == 'tests/behavior/test_build737_numeric_trading_alias.py'
    for record in current['supplemental_findings'].values():
        assert (ROOT / record['test']).is_file()
    assert {'738', '739', 'open'}.issubset(current['review_732_remediation'])


def test_stale_build_and_extra_finding_reproduce_reported_failure():
    current = evidence()
    current['build'] = BUNDLE_BUILD - 1
    current['findings']['STORAGE736'] = current['supplemental_findings']['STORAGE736']
    errors = remediation_evidence_errors(current, ROOT, BUNDLE_BUILD)
    assert 'Remediation evidence build mismatch' in errors
    assert any('Each Build 681 review ID' in message and 'STORAGE736' in message for message in errors)


@pytest.mark.parametrize('issue,record,error', [
    ('H1', {'status': 'deferred', 'rationale': 'not verified'}, 'high-severity safety issue'),
    ('M1', {'status': 'deferred'}, 'document rationale'),
    ('M2', {'status': 'fixed', 'test': 'tests/nonexistent.py::test_missing'}, 'missing cited regression test'),
    ('M3', {'status': 'fixed', 'test': 'tests/contracts/test_build740_remediation_evidence.py::test_does_not_exist'}, 'missing actual pytest function'),
    ('M4', None, 'disposition must be a JSON object'),
])
def test_invalid_dispositions_remain_blocked(issue, record, error):
    current = evidence()
    current['findings'][issue] = record
    errors = remediation_evidence_errors(current, ROOT, BUNDLE_BUILD)
    assert any(issue in message and error in message for message in errors)
