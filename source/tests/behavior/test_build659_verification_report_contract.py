"""Build 659: preserve truthful, exact CI verification-report contract text."""
from pathlib import Path

import pytest

import tlo_version as V
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build659_report_retains_literal_contract_and_fail_closed_status():
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert report.startswith(f"TLO {V.DISPLAY_VERSION} — NOT RELEASE-ATTESTED")
    assert "Ruff lint: lint not attested" in report
    assert "full GitHub Actions run" in report
    assert "Ruff lint: passed" not in report
    assert "NOT ATTESTED for Build 659" in report


def test_build659_is_versioned_separately_and_preserves_hosted_failure_evidence():
    assert V.BUNDLE_BUILD == 659
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert "43327144040" in report
    assert "3 failed, 2,544 passed, 26 skipped" in report
    history = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert history.startswith("TLO v1.7 Build 659")
    assert "TLO v1.7 Build 658" in history
