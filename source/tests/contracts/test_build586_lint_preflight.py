"""Build 586: prevent unused-import regressions in the Build 585 FLAC checker."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('relative_path', [
    'tlo_flac_fingerprint.py',
    'tests/behavior/test_build585_corruption_ffp.py',
])
def test_new_ffp_modules_have_no_unused_imports(relative_path):
    """Check imports used within the file without requiring a Ruff install."""
    tree = ast.parse((ROOT / relative_path).read_text(encoding='utf-8'))
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Load)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.asname or alias.name.partition('.')[0]
                     for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module == '__future__':
                continue
            names = [alias.asname or alias.name for alias in node.names
                     if alias.name != '*']
        else:
            continue
        for name in names:
            assert name in used, f'{relative_path}: unused import {name}'
