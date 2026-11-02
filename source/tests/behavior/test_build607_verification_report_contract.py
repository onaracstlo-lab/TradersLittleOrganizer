"""Build 607: preserve truthful lint evidence expected by hosted release CI."""
from pathlib import Path

import pytest
import tlo_version as version
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build607_lint_field_has_literal_contract_and_truthful_status():
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert report.startswith(f"TLO {version.DISPLAY_VERSION} — NOT RELEASE-ATTESTED")
    assert "Ruff lint:" in report
    assert "lint not attested" in report
    assert "Ruff lint: passed" not in report
    assert "Ruff is NOT EXECUTED LOCALLY if unavailable" not in report


def test_build607_preserves_hosted_mandatory_lint_gate():
    build_process = (ROOT / "tests" / "behavior" / "test_build532_verification_integrity.py").read_text(encoding="utf-8")
    assert 'pytest.fail("Ruff is required for release verification' in build_process
    assert 'os.environ.get("TLO_RELEASE_VERIFY", "")' in build_process
    assert (ROOT / "requirements-build.txt").read_text(encoding="utf-8").find("ruff==0.16.10") >= 0


def test_build607_no_application_or_preferences_changes_from_fix():
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "Build 606 Weather Report" in changes
    assert (ROOT / "tlo-preferences.ini").is_file()


def test_build608_prior_regression_test_has_no_shadowing_path_import():
    source = (ROOT / "tests" / "behavior" / "test_build607_verification_report_contract.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    assert lines.count("from pathlib import Path") == 1
    assert not any(line.startswith("    from pathlib import ") for line in lines)
