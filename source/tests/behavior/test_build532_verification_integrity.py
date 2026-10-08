from __future__ import annotations
from tests import _release_artifacts as RA

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _run_pytest_without_display(*paths: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("CI", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *paths],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def test_build532_no_display_gui_subset_has_six_real_skips():
    try:
        __import__("tkinter")
    except (ImportError, ModuleNotFoundError):
        pytest.skip("Tkinter is not installed; the no-display distinction requires Tkinter itself to be available")
    completed = _run_pytest_without_display(
        "tests/behavior/test_build407_artist_and_research_gui.py",
        "tests/behavior/test_build501_review_remediation.py",
        "tests/behavior/test_gui_behavior.py",
        "tests/behavior/test_research_behavior.py",
    )
    assert completed.returncode == 0, completed.stdout
    assert "50 passed, 6 skipped" in completed.stdout


def test_build532_verification_report_distinguishes_xvfb_from_no_display():
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert "Xvfb display (CI=1)" in report
    assert "No display (DISPLAY and CI unset)" in report
    assert "6 skipped" in report
    assert "Genuine headless run with DISPLAY unset:\n      1698 passed, 0 skipped" not in report


def test_build532_ruff_contract_passes_when_ruff_is_available():
    if importlib.util.find_spec("ruff") is None:
        release_verify = str(os.environ.get("TLO_RELEASE_VERIFY", "")).strip().lower() in {"1", "true", "yes", "on"}
        if release_verify:
            pytest.fail("Ruff is required for release verification; install requirements-build.txt before running the release suite")
        pytest.skip("Ruff is not installed in this non-release test environment")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
    )
    assert completed.returncode == 0, completed.stdout


def test_build532_source_tree_contains_no_compiled_python_artifacts():
    bad = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.pyc") if ".git" not in p.parts]
    assert bad == []
