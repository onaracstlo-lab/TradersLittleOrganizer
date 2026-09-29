"""Build 508 regression coverage for removal of the unused TaggerWindow GUI."""

__version__ = "v512"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import inspect

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_gui():
    spec = spec_from_file_location("tlo_ggi_build508", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_dead_tagger_window_and_scaffolding_are_removed():
    gui = _load_gui()
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert not hasattr(gui, "TaggerWindow")
    assert "class TaggerWindow" not in source
    assert "active_tagger_window" not in source
    assert "_tagger_is_open" not in source
    assert "_focus_active_tagger" not in source
    assert "TAGGER_DISPLAY_VERSION" not in source
    assert "TAGGER_PATH_ENTRY_WIDTH" not in source
    assert "TAGGER_OUTPUT_TEXT_WIDTH" not in source


def test_main_window_tag_remains_the_only_gui_tag_execution_path():
    gui = _load_gui()
    source = inspect.getsource(gui.App._start_tagging_from_main)
    assert "config = self._build_config()" in source
    assert "jobs = self._main_tag_jobs(config)" in source
    assert "_show_operation_review_and_log" in source
    assert "PreviewWindow" in source
    assert "run_tagger_jobs(config, jobs, emit=self.queue.put)" in source
    assert "self.tag_active = True" in source


def test_main_window_tag_still_uses_live_checkbox_values_and_shared_logging():
    gui = _load_gui()
    source = inspect.getsource(gui.App._start_tagging_from_main)
    assert "config.main_window_checkbox_values = self._current_main_checkbox_values()" in source
    assert 'action="Tag Dry Run" if dry_run else "Tag"' in source
    assert 'operation="Tag"' in source
