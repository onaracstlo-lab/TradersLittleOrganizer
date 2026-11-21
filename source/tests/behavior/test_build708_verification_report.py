"""Build 708: packaged source verification report must retain fail-closed contracts."""
from pathlib import Path

import pytest
import tlo_version as V
from tests import _release_artifacts as A

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build708_verification_header_and_lint_evidence():
    record = (ROOT / A.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert record.startswith(f"TLO {V.DISPLAY_VERSION} — NOT RELEASE-ATTESTED")
    assert "Ruff lint: lint not attested" in record
    assert "Ruff lint: passed" not in record
    assert "full GitHub Actions run" in record
    assert f"NOT ATTESTED for Build {V.BUNDLE_BUILD}" in record
