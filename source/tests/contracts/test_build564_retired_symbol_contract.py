"""Reviewed dead-helper retirements; intentionally avoids speculative whole-repo vulture gate."""
from pathlib import Path
import ast
import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('source, symbol', [
    ('tlo_inventory_update.py', 'open_paths'),
    ('tlo_inventory_update.py', '_is_safe_delete_rooted_path'),
    ('tlo_github_updates.py', '_detect_platform_key'),
    ('tlo_setlistfm_lookup.py', '_environment_value'),
])
def test_retired_dead_helper_is_absent_from_production_module(source, symbol):
    tree = ast.parse((ROOT / source).read_text(encoding='utf-8'))
    assert all(getattr(node, 'name', None) != symbol
               for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def test_single_live_gui_path_opener_is_exported():
    import tlo_ux
    assert callable(tlo_ux.open_path)
