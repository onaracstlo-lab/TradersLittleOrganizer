"""Build 717 retains prior fail-closed report format after CI run 45067649844."""
from pathlib import Path
import pytest
import tlo_version as V
from tests import _release_artifacts as A

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]

def test_report_keeps_exact_unattested_header_and_lint():
    report=(ROOT/A.BUILD_VERIFICATION_FILENAME).read_text(encoding='utf-8')
    assert report.startswith(f'TLO {V.DISPLAY_VERSION} — NOT RELEASE-ATTESTED')
    assert 'Ruff lint: lint not attested' in report
    assert 'Ruff lint: passed' not in report
    assert f'NOT ATTESTED for Build {V.BUNDLE_BUILD}' in report

def test_report_labels_old_gui_skips_as_historical_not_new_ci():
    report=(ROOT/A.BUILD_VERIFICATION_FILENAME).read_text(encoding='utf-8')
    assert 'Xvfb display (CI=1)' in report
    assert 'No display (DISPLAY and CI unset):' in report
    assert '50 passed, 6 skipped' in report
    assert '26 skipped' in report
    assert 'Historical Build 532 / Build 613' in report
    assert 'full GitHub Actions run' in report

def test_current_report_records_failed_hosted_build():
    report=(ROOT/A.BUILD_VERIFICATION_FILENAME).read_text(encoding='utf-8')
    assert '45067649844' in report
    assert 'FAILED' in report
    assert 'native Windows/Linux/macOS tests' in report
