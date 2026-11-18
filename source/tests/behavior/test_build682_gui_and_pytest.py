"""Build 682: user decisions are not cut short; plain pytest does not dirty source."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _gui_module():
    spec = importlib.util.spec_from_file_location('tlo_main_build682', ROOT/'tlo-main.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gui_prompt_can_take_longer_than_old_timeout(monkeypatch):
    gui = _gui_module()
    # Wait for a simulated human response after the earlier timeout would
    # have expired; do not require a real Tk event loop in this unit scenario.
    class Root:
        def after(self, _delay, callback):
            # Dispatch now; the human answer, not Tk dispatch, is slow.
            threading.Thread(target=callback, daemon=True).start()
    class Shell:
        root = Root()
    monkeypatch.setattr(gui, 'GUI_THREAD_CALLBACK_TIMEOUT_SECONDS', 0.2, raising=False)
    def human_answer():
        time.sleep(0.45)
        return 'skip'
    outcome = []
    t = threading.Thread(target=lambda: outcome.append(gui.App._run_on_gui_thread(Shell(), human_answer)))
    t.start(); t.join(timeout=3)
    assert not t.is_alive() and outcome == ['skip']


def test_closing_existing_volume_dialog_is_non_destructive():
    source = (ROOT/'tlo-main.py').read_text(encoding='utf-8')
    assert 'dialog.protocol("WM_DELETE_WINDOW", lambda: choose("skip"))' in source


def test_pytest_collection_disables_source_bytecode_writes():
    assert sys.dont_write_bytecode is True
