"""Build 707: exception type must be available on every tlo-reverse branch."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tlo-reverse.py"


def test_build707_manual_undo_error_is_bound_before_branch_dispatch():
    module = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    top_level = [
        alias.name for node in module.body
        if isinstance(node, ast.ImportFrom) and node.module == "tlo_manual_undo"
        for alias in node.names
    ]
    assert top_level.count("ManualUndoError") == 1
    for node in ast.walk(next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "main")):
        if isinstance(node, ast.ImportFrom) and node.module == "tlo_manual_undo":
            assert "ManualUndoError" not in [alias.name for alias in node.names]


@pytest.mark.parametrize("branch", ["folder", "manual", "recovery"])
def test_build707_reverse_error_paths_have_no_unbound_local(tmp_path, branch):
    missing = tmp_path / "not-present"
    home = tmp_path / "home"
    command = [sys.executable, str(SCRIPT), str(missing), "--TLOHome", str(home)]
    if branch == "manual":
        command.append("--manual-updates")
    if branch == "recovery":
        command.append("--recover-staging")
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=20, check=False)
    assert proc.returncode != 0
    assert "UnboundLocalError" not in proc.stderr
    assert "Traceback" not in proc.stderr
    assert "ERROR:" in proc.stderr or "conflicts:" in proc.stdout
