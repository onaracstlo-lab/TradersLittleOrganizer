"""Build 614: report truthful independent skip counts for headless GUI and Linux CI."""
from pathlib import Path

import pytest
from tests import _release_artifacts as RA
import tlo_version as V

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build614_headless_gui_contract_is_explicit_and_not_confused_with_full_ci():
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert report.startswith(f"TLO {V.DISPLAY_VERSION} — NOT RELEASE-ATTESTED")
    assert "No display (DISPLAY and CI unset):" in report
    assert "50 passed, 6 skipped" in report  # Standalone Build 532 GUI subset.
    assert "26 skipped" in report  # Build 613 full Linux CI job (different population).
    assert "full GitHub Actions run" in report
    assert "Xvfb display (CI=1)" in report
    assert "Ruff lint:" in report and "lint not attested" in report
    assert "Ruff lint: passed" not in report


def test_build614_preserves_original_headless_gui_assertion_as_release_guard():
    source = (ROOT / "tests/behavior/test_build532_verification_integrity.py").read_text(encoding="utf-8")
    assert 'assert "6 skipped" in report' in source
    assert 'assert "50 passed, 6 skipped" in completed.stdout' in source
