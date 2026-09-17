"""Build 469 regressions for main-window Tag and related control semantics."""

__version__ = "v471"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_gui():
    spec = spec_from_file_location("tlo_ggi_build469", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_keep_report_disables_folder_removal_and_threshold_and_forces_never():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'folder_combo.configure(state=("disabled" if keep_report else "readonly"))' in source
    assert 'if keep_report:' in source
    assert 'self.vars["corrupt_folders"].set(CORRUPT_FOLDER_GUI_VALUES["never"])' in source
    assert '"never"\n                if CORRUPT_FILE_GUI_TO_POLICY.get(' in source


def test_issues_window_horizontal_scroll_has_nonstretch_overflow_columns():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'self.window.geometry("1050x520")' in source
    assert 'self.tree.column("message", width=720, minwidth=520, stretch=False)' in source
    assert 'self.tree.column("path", width=600, minwidth=360, stretch=False)' in source
    assert 'xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)' in source


def test_successful_parser_decisions_are_info_not_tagging_warnings():
    source = (ROOT / "tlo_tag_lib.py").read_text(encoding="utf-8")
    assert 'INFO: {folder} | selected {expected} contiguous setlist track row(s)' in source
    assert 'INFO: {folder} | selected {expected} reset-aware setlist track row(s)' in source
    assert 'INFO: {folder} | numbered song-sequence evidence found; not using unnumbered prose fallback' in source
    assert 'WARN: {folder} | numbered song-sequence evidence found; not using unnumbered prose fallback' not in source


def test_gui_tag_uses_master_paths_and_does_not_open_tagger_window():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("    def _start_tagging_from_main(self):")
    end = source.index("    def _open_add_to_inventory(self):", start)
    method = source[start:end]
    assert "TaggerWindow(" not in method
    assert 'search_status = validate_search_path(self.vars["search_path_override"].get(), tlo_home)' in method
    assert "config = self._build_config()" in method
    assert "jobs = self._main_tag_jobs(config)" in method
    assert "run_tagger_jobs(config, jobs, emit=self.queue.put)" in method
    assert "Select Tag in Place, Tag Copy, or Tag Copy/Delete Original" in method


def test_setlistfm_api_key_presence_is_detected_without_exposing_key(monkeypatch):
    import tlo_setlistfm_lookup as sfm

    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    assert sfm.api_key_available() is False
    monkeypatch.setenv(sfm.ENV_API_KEY, "secret-value")
    assert sfm.api_key_available() is True


def test_gui_disables_both_setlistfm_boxes_when_key_missing():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'for field in ("setlistfm_lookup", "setlistfm_upgrade"):' in source
    assert 'widget.configure(state=("normal" if available else "disabled"))' in source
    assert 'self.bool_vars[field].set(False)' in source


def test_max_workers_is_a_ceiling_while_performance_mode_can_use_fewer(monkeypatch):
    import walk_trees_lib as W

    config = SimpleNamespace(performance_mode="gentle", max_workers=12)
    monkeypatch.setattr(W.os, "cpu_count", lambda: 8)
    assert W._path_worker_count(config, 20) == 1

    config.performance_mode = "balanced"
    assert W._path_worker_count(config, 20) == 2

    config.performance_mode = "fast"
    assert W._path_worker_count(config, 20) == 8

    config.performance_mode = "extreme"
    assert W._path_worker_count(config, 20) == 12
    assert W._path_worker_count(config, 4) == 4

    gui = _load_gui()
    monkeypatch.setattr(gui.os, "cpu_count", lambda: 8)
    assert gui._default_max_workers_for_mode("gentle") == 8
    assert gui._default_max_workers_for_mode("extreme") == 8
