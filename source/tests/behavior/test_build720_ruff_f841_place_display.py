"""Build 720: prevent F841 no-op state in place display and preserve output."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tlo_place_display import display_place_case

pytestmark = pytest.mark.behavior


def test_place_display_has_no_unused_wholly_upper_local():
    source = Path(__file__).resolve().parents[2] / "tlo_place_display.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "display_place_case"]
    assert len(funcs) == 1
    assignments = [name.id for node in ast.walk(funcs[0]) if isinstance(node, (ast.Assign, ast.AnnAssign))
                   for name in (node.targets if isinstance(node, ast.Assign) else [node.target]) if isinstance(name, ast.Name)]
    assert "wholly_upper" not in assignments


@pytest.mark.parametrize("raw,expected", [
    ("THE GREAT MEADOW,FORT MASON, SAN FRANCSICO, CA", "The Great Meadow,Fort Mason, San Francsico, CA"),
    ("Calvin Theatre NORTHAMPTON, MA", "Calvin Theatre Northampton, MA"),
    ("Lincoln Theater W.HARTFORD, CT", "Lincoln Theater W.Hartford, CT"),
    ("Smith College NORTHAMPTON, MA", "Smith College Northampton, MA"),
    ("franklin & marshall college LANCASTER, PA", "franklin & marshall college Lancaster, PA"),
    ("MGM GRAND GARDEN ARENA", "MGM Grand Garden Arena"),
    ("McMenamins Crystal Ballroom", "McMenamins Crystal Ballroom"),
    ("PORT CHESTER, NY", "Port Chester, NY"),
])
def test_build720_retains_place_display_contract(raw, expected):
    value = display_place_case(raw, kind="venue")
    assert value == expected
    assert display_place_case(value, kind="venue") == value
