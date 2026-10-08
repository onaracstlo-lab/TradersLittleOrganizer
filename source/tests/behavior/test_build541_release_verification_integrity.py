from __future__ import annotations
from tests import _release_artifacts as RA

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.update(alias.asname or alias.name for alias in node.names)
    return found


def test_build541_version_and_versioned_artifacts():
    for name in (
        RA.REQUIREMENTS_FILENAME,
        RA.MANUAL_FILENAME,
        RA.SOURCE_README_FILENAME,
        RA.CHANGES_FILENAME,
        RA.BUILD_VERIFICATION_FILENAME,
    ):
        assert (ROOT / name).is_file(), name


def test_build541_reported_f401_imports_are_removed():
    assert {"os", "subprocess", "sys"}.isdisjoint(
        _imports(ROOT / "tests/behavior/test_build530_verification_accuracy.py")
    )
    assert {"json", "SimpleNamespace"}.isdisjoint(
        _imports(ROOT / "tests/behavior/test_build537_portability_robustness.py")
    )


def test_build541_release_mode_missing_ruff_is_fail_closed_by_contract():
    text = (ROOT / "tests/behavior/test_build532_verification_integrity.py").read_text(encoding="utf-8")
    assert 'os.environ.get("TLO_RELEASE_VERIFY", "")' in text
    assert 'pytest.fail("Ruff is required for release verification' in text
    assert 'pytest.skip("Ruff is not installed in this non-release test environment")' in text
    lock = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "ruff==0.16.10" in lock


def test_build541_requirements_and_verification_reporting_contract():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    assert "TLO_RELEASE_VERIFY=1" in req
    assert "lint was not attested" in req
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    assert "Ruff lint:" in report
    assert ("ATTESTED" in report) or ("lint not attested" in report)
    assert "Ruff is NOT EXECUTED LOCALLY if unavailable" not in report


def test_build541_changes_keep_scope_to_h01():
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    first = changes.split("TLO v1.7 Build 540", 1)[0]
    assert "Addresses review finding H-01 only" in first
    assert "Application runtime behavior is unchanged" in first
    assert "GitHub Build Process remains v108" in first
