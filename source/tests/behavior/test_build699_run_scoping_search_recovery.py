"""Executable regressions for run-scoped summaries, Boolean grammar and recovery preview."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import tlo_postprocess

pytestmark = pytest.mark.behavior


def _module(name: str, filename: str):
    path = Path(__file__).resolve().parents[2] / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_run_scoped_rename_summary_ignores_other_volume(tmp_path: Path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "tags0.txt").write_text("RENAME_COMPLIANTLY_SUMMARY: renamed=0 skipped=6\n", encoding="utf-8")
    (logs / "tags1.txt").write_text("RENAME_COMPLIANTLY_SUMMARY: renamed=2 skipped=1\n", encoding="utf-8")
    summary = Path(tlo_postprocess._write_conflict_summary_log(str(tmp_path), current_tokens=["1"]))
    assert "Rename Compliantly: 2 renamed, 1 skipped" in summary.read_text(encoding="utf-8")
    assert "0 renamed, 6 skipped" not in summary.read_text(encoding="utf-8")
    summary = Path(tlo_postprocess._write_conflict_summary_log(str(tmp_path), current_tokens=[]))
    assert "Rename Compliantly:" not in summary.read_text(encoding="utf-8")


def test_legacy_summary_can_still_aggregate_when_unscoped(tmp_path: Path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "tags0.txt").write_text("RENAME_COMPLIANTLY_SUMMARY: renamed=1 skipped=3\n", encoding="utf-8")
    path = Path(tlo_postprocess._write_conflict_summary_log(str(tmp_path)))
    assert "1 renamed, 3 skipped" in path.read_text(encoding="utf-8")


def test_boolean_search_unexpected_closing_parenthesis_has_clear_error():
    search = _module("search_build699", "tlo-search.py")
    with pytest.raises(search.SearchExpressionError, match="closing parenthesis"):
        search.build_search_predicate("Phish |AND| 1997)")


def test_literal_pasted_title_still_allows_parentheses():
    search = _module("search_literals_build699", "tlo-search.py")
    pred = search.build_search_predicate("Phish 1997 (Early Show)")
    assert pred("Phish 1997 (Early Show) at Centrum")


def test_staging_recovery_dry_run_summary_includes_would_restore(monkeypatch, capsys):
    reverse = _module("reverse_build699", "tlo-reverse.py")
    recovery = __import__("tlo_staging_recovery")
    def fake_recover(path, *, dry_run, emit):
        assert path == "/some/destination"
        assert dry_run is True
        return {"found": 2, "restored": 0, "conflicts": 1, "would_restore": 1}
    monkeypatch.setattr(recovery, "recover_interrupted_stage_moves", fake_recover)
    assert reverse.main(["/some/destination", "--recover-staging", "--dry-run"]) == 2
    assert "would restore: 1" in capsys.readouterr().out
