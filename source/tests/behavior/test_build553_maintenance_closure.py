"""Build 553: low-risk maintenance closure for residual review items."""

from __future__ import annotations
from tests._release_artifacts import release_history

import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest

import tlo_security as SEC

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build553_helper_modules_have_real_module_docstrings():
    for name in (
        "prepare_ffmpeg.py",
        "audit_build_requirements.py",
        "verify_build_environment.py",
        "tlo_dragdrop.py",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=name)
        doc = ast.get_docstring(tree, clean=False)
        assert doc, f"{name} must have a real module docstring"
        assert tree.body[0].__class__ is ast.Expr


@pytest.mark.parametrize(
    ("script", "description"),
    [
        ("prepare_ffmpeg.py", "Fetch and verify the exact ffmpeg binary used by TLO native builds."),
        ("audit_build_requirements.py", "Run pip-audit 2.10.1 from TLO's hash-locked audit tool environment."),
        ("verify_build_environment.py", "Fail closed when a native TLO build uses an unapproved toolchain."),
    ],
)
def test_build553_command_helper_help_includes_module_description(script, description):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(ROOT / script), "--help"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    normalized = " ".join(result.stdout.split())
    assert description in normalized


def test_build553_dead_updater_verification_note_is_removed():
    source = (ROOT / "tlo_github_updates.py").read_text(encoding="utf-8")
    assert "verification_note" not in source
    assert 'f"{lead}\\n\\n{destination}\\n\\n{extra}"' in source


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (r"\\server\share", True),
        (r"\\?\C:\Windows\file.txt", True),
        (r"\\.\pipe\name", True),
        (r"C:\local\file.txt", False),
        ("/tmp/local", False),
    ],
)
def test_build553_network_device_path_cleanup_preserves_behavior(value, expected):
    assert SEC.is_network_or_device_path(value) is expected


def test_build553_network_device_helper_has_no_redundant_prefix_checks():
    source = (ROOT / "tlo_security.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "is_network_or_device_path")
    segment = ast.get_source_segment(source, fn) or ""
    assert segment.count("startswith") == 1
    assert 'lowered.startswith("\\\\\\\\")' in segment


def test_build553_lock_skew_is_explicitly_documented_in_both_locks():
    for name in ("requirements-build.txt", "requirements-audit.txt"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "independently pinned dependency closures" in text
        assert "may intentionally use different versions" in text
        assert "Do not align those versions merely for cosmetic consistency" in text


def test_build553_version_and_documentation_contract():
    from docx import Document
    from tests import _release_artifacts as A


    changes = (ROOT / A.CHANGES_FILENAME).read_text(encoding="utf-8")
    req_doc = Document(ROOT / A.REQUIREMENTS_FILENAME)
    req = "\n".join(p.text for p in req_doc.paragraphs)

    assert "TLO v1.7 Build 553" in changes
    assert "Build 553 - " in release_history()
    assert "Build 553: low-risk maintenance closure" in req
