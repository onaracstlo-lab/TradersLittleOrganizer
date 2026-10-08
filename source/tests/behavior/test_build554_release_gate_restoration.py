"""Build 554: restore the pinned Ruff gate and truthful verification labeling."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def test_build554_reported_f401_imports_are_removed():
    assert "RA" not in _imported_names(ROOT / "tests/behavior/test_build524_closure_audit.py")
    assert "SimpleNamespace" not in _imported_names(ROOT / "tests/behavior/test_build543_corrupt_input_isolation.py")
    assert "os" not in _imported_names(ROOT / "tests/behavior/test_build547_remove_dead_reverse_copy_delete.py")


def test_build554_pinned_ruff_gate_remains_exact():
    lock = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "ruff==0.16.10" in lock
    config = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    assert "F" in config


def test_build554_verification_record_cannot_misstate_incomplete_attestation():
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    first_line = report.splitlines()[0]
    incomplete = "lint not attested" in report or "release gate not executed" in report.lower()
    if incomplete:
        assert "NOT RELEASE-ATTESTED" in first_line
    else:
        assert "RELEASE-ATTESTED" in first_line


def test_build554_current_versioned_artifacts_and_scope():
    for name in (
        RA.REQUIREMENTS_FILENAME,
        RA.MANUAL_FILENAME,
        RA.SOURCE_README_FILENAME,
        RA.CHANGES_FILENAME,
        RA.BUILD_VERIFICATION_FILENAME,
    ):
        assert (ROOT / name).is_file(), name
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    first = changes.split("TLO v1.7 Build 553", 1)[0]
    assert "Release-gate restoration (F-01)" in first
    assert "runtime behavior" in first
    assert "GitHub Build Process remains v108 unchanged" in first
