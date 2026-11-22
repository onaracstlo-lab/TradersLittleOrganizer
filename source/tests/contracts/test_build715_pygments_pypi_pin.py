"""Build 715: published Pygments wheel digest is checked before pip installs."""
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract

from verify_build_lock import check_build_lock, EXPECTED_SHA256, EXPECTED_RUFF_LINUX_X64_SHA256

ROOT = Path(__file__).resolve().parents[2]
TRUSTED_PYPI_WHEEL_SHA256 = "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9"
TRUSTED_PYPI_RUFF_LINUX_X64_SHA256 = "f33f43a864a8483eebd160e713336c8bab02c934feaff0a33cf5ccb41546d09a"


def test_official_pygments_wheel_hash_is_pin_and_not_a_typo():
    assert EXPECTED_SHA256 == TRUSTED_PYPI_WHEEL_SHA256
    assert EXPECTED_RUFF_LINUX_X64_SHA256 == TRUSTED_PYPI_RUFF_LINUX_X64_SHA256
    assert check_build_lock(ROOT / "requirements-build.txt") == []


def test_modified_wheel_pin_fails_closed(tmp_path):
    bad = tmp_path / "requirements-build.txt"
    bad.write_text((ROOT / "requirements-build.txt").read_text().replace(TRUSTED_PYPI_WHEEL_SHA256, "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377147d9"))
    assert "pin mismatch" in check_build_lock(bad)[0]
    result = subprocess.run([sys.executable, str(ROOT / "verify_build_lock.py"), str(bad)], capture_output=True, text=True)
    assert result.returncode != 0 and "ERROR:" in result.stdout


def test_missing_wheel_pin_fails_closed(tmp_path):
    bad = tmp_path / "requirements-build.txt"
    bad.write_text("pytest==9.1.1 \\n--hash=sha256:" + "0" * 64 + "\n")
    assert check_build_lock(bad)


def test_corrupt_ruff_platform_wheel_fails_before_pip(tmp_path):
    bad = tmp_path / "requirements-build.txt"
    bad.write_text((ROOT / "requirements-build.txt").read_text().replace(TRUSTED_PYPI_RUFF_LINUX_X64_SHA256, "f33f43a864a8483eebd160e714336c8bab02c934feaff0a33cf5ccb41546d09a"))
    errors = check_build_lock(bad)
    assert len(errors) == 1 and "Ruff Linux x64 wheel hash" in errors[0]
