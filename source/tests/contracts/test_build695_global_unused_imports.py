"""Build 695: prevent an F401 slip across ALL application and test files."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def _audit_module():
    path = ROOT / "tools" / "audit_unused_imports.py"
    spec = importlib.util.spec_from_file_location("tlo_build695_unused_import_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_tree_unused_import_audit_includes_all_tests_and_production_files():
    inspected, errors = _audit_module().audit_tree(ROOT)
    assert inspected >= 400
    assert not errors, "\n".join(errors)


def test_offline_audit_catches_exact_build694_f401_and_test_imports():
    audit = _audit_module()
    for filename in ("tlo_postprocess.py", "tests/behavior/example_test.py"):
        result = audit.audit_source("import csv\nprint('hello')\n", filename=filename)
        assert len(result) == 1
        assert "unused import csv" in result[0]
    assert not audit.audit_source("import csv\nprint(csv.reader)\n")


def test_offline_audit_respects_explicit_reexport_and_documented_exception():
    audit = _audit_module()
    assert not audit.audit_source("from pathlib import Path as Path\n")
    assert not audit.audit_source("import tkinter  # noqa: F401 - optional probe\n")
    assert audit.audit_source("import csv  # noqa: F403\n")


def test_current_source_link_is_for_this_build_not_the_previous_one():
    import tlo_version as version
    source = (ROOT / "SOURCE.txt").read_text(encoding="utf-8")
    assert f"/releases/tag/v1.7-build{version.BUNDLE_BUILD}" in source
    assert f"/releases/tag/v1.7-build{version.BUNDLE_BUILD - 1}" not in source
