"""Build 405 cancellation/log-token and CI display regressions."""

__version__ = "v411"

from pathlib import Path
from types import SimpleNamespace

import pytest

import logging_lib

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_delete_logs_rejects_path_traversal_before_any_deletion(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    victim = logs / "meta0.log"
    victim.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid log token"):
        logging_lib.delete_logs_for_tokens(str(tmp_path), ["0", "../outside"])
    assert victim.read_text(encoding="utf-8") == "keep"


def test_delete_logs_accepts_current_alphanumeric_tokens(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    victims = [logs / "meta0.log", logs / "tagsA.txt", logs / "tageA.txt"]
    for victim in victims:
        victim.write_text("x", encoding="utf-8")
    deleted = logging_lib.delete_logs_for_tokens(str(tmp_path), ["0", "A"])
    assert set(map(str, victims)) <= set(deleted)
    assert all(not victim.exists() for victim in victims)


def test_gui_cleanup_uses_only_newly_allocated_tokens():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("    def _cleanup_active_logs(self):")
    end = source.index("\n    def _run_on_gui_thread", start)
    body = source[start:end]
    assert "newly_allocated_log_tokens" in body
    assert "active_log_tokens" not in body


def test_duplicate_active_log_token_state_removed_from_runtime_config():
    assert "active_log_tokens" not in (ROOT / "walk_trees_lib.py").read_text(encoding="utf-8")
    assert "active_log_tokens" not in (ROOT / "inventory_parser_lib.py").read_text(encoding="utf-8")


def test_ci_conftest_has_xvfb_and_prominent_residual_skip_warning():
    source = (ROOT / "conftest.py").read_text(encoding="utf-8")
    assert '_display_is_usable()' in source
    assert 'shutil.which("Xvfb")' in source
    assert 'os.environ["DISPLAY"] = display' in source
    assert "CI COVERAGE WARNING" in source
    assert 'terminalreporter.stats.get("skipped", [])' in source
