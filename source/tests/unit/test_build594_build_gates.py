"""Build 594 regressions: pinned vulnerability fix and deferred macOS scan."""
from pathlib import Path
import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_build_dependency_lock_uses_fixed_hash_pinned_setuptools():
    lock = (ROOT / "requirements-build.txt").read_text()
    assert "setuptools==84.2.1" in lock
    assert "ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2" in lock
    assert "setuptools==84.0.0" not in lock
    assert '"setuptools": "84.2.1"' in (ROOT / "verify_build_environment.py").read_text()


def test_macos_scan_deferral_requires_ci_and_does_not_claim_clean_receipt():
    mac = (ROOT / "createMacOSDist.sh").read_text()
    assert 'TLO_DEFER_MACOS_SCAN_TO_PACKAGE' in mac
    assert 'GITHUB_ACTIONS:-false' in mac
    assert 'Unexpected preexisting macOS scan receipt' in mac
    assert '"$PYTHON_BIN" "$SCAN_SCRIPT"' in mac
