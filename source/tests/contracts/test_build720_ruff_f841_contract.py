"""Build 720: lint-remediation contract for cross-platform source jobs."""
import ast
from pathlib import Path
import pytest

pytestmark = pytest.mark.contract

def test_display_case_does_not_retain_unused_wholly_upper_binding():
    file = Path(__file__).resolve().parents[2] / "tlo_place_display.py"
    syntax = ast.parse(file.read_text(encoding="utf-8"))
    func = next(x for x in syntax.body if isinstance(x, ast.FunctionDef) and x.name == "display_place_case")
    assert all(not (isinstance(t, ast.Name) and t.id == "wholly_upper")
               for x in ast.walk(func) if isinstance(x, ast.Assign) for t in x.targets)
