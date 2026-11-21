"""Build 689: real log-token and deep-tree duplicate safety regressions."""
import importlib.util
import sys
from pathlib import Path

import pytest

import logging_lib

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _dup_module():
    spec = importlib.util.spec_from_file_location('tlo_delete_dupes_689', ROOT / 'tlo-deleteDupes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_single_character_tokens_remain_unchanged(tmp_path):
    assert logging_lib.allocate_log_tokens(str(tmp_path), 36) == list(logging_lib.LOG_TOKEN_CHARS)
    assert logging_lib.allocate_log_tokens(str(tmp_path), 0) == []


def test_existing_logs_survive_token_extension_and_new_logs_remain_distinct(tmp_path):
    logs = tmp_path / 'logs'
    logs.mkdir()
    for token in logging_lib.LOG_TOKEN_CHARS:
        (logs / f'tags{token}.txt').write_text(f'HISTORIC {token}\n', encoding='utf-8')
    proposed = logging_lib.allocate_log_tokens(str(tmp_path), 3)
    assert proposed == ['10', '11', '12']
    assert len(set(proposed)) == 3
    assert all(logging_lib.LOG_TOKEN_PATTERN.fullmatch('tags'+t+'.txt') for t in proposed)
    logging_lib.ensure_logs_dir(str(tmp_path))
    (logs / 'tags10.txt').write_text('NEW\n', encoding='utf-8')
    assert logging_lib.allocate_log_tokens(str(tmp_path), 2) == ['11', '12']
    assert all((logs / f'tags{t}.txt').read_text(encoding='utf-8') == f'HISTORIC {t}\n'
               for t in logging_lib.LOG_TOKEN_CHARS)
    # Cleanup targets the requested long token only.
    logging_lib.delete_logs_for_tokens(str(tmp_path), ['10'])
    assert not (logs / 'tags10.txt').exists()
    assert (logs / 'tags1.txt').exists()


def test_comparison_of_deep_directory_trees_is_iterative(tmp_path):
    module = _dup_module()
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    deep_a, deep_b = a, b
    for _ in range(75):
        deep_a = deep_a / 'd'
        deep_b = deep_b / 'd'
        deep_a.mkdir(); deep_b.mkdir()
    (deep_a / '01.flac').write_bytes(b'ABC')
    (deep_b / '01.flac').write_bytes(b'XYZ')
    prior_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(65)
        assert module.compare_directory_trees_for_duplicate_deletion(str(a), str(b)) == (True, '')
    finally:
        sys.setrecursionlimit(prior_limit)
    (deep_b / '01.flac').write_bytes(b'LONGER')
    same, reason = module.compare_directory_trees_for_duplicate_deletion(str(a), str(b))
    assert not same and 'sizes' in reason


def test_deep_tree_symlink_still_fails_closed(tmp_path):
    module = _dup_module()
    root = tmp_path / 'music'; root.mkdir()
    target = root / 'disc'; target.mkdir()
    try:
        (target / 'loop').symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip('symlinks unavailable')
    with pytest.raises(module.DeleteDupesError, match='symlink'):
        module._scan_tree(str(root))
