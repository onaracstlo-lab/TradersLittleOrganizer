"""Build 468 regression coverage for active Tagger cancellation cleanup."""

__version__ = "v468"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _load_gui():
    spec = spec_from_file_location("tlo_ggi_build468", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _Worker:
    def __init__(self, alive):
        self.alive = bool(alive)

    def is_alive(self):
        return self.alive


class _GoneWindow:
    def winfo_exists(self):
        return False


class _Root:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        return len(self.after_calls)


def test_closed_tagger_window_remains_logically_active_until_worker_stops():
    gui = _load_gui()
    app = gui.App.__new__(gui.App)
    worker = _Worker(True)
    tagger = SimpleNamespace(window=_GoneWindow(), worker=worker, _processing=True)
    app.active_tagger_window = tagger

    assert app._tagger_is_open() is True
    assert app.active_tagger_window is tagger

    tagger._processing = False
    worker.alive = False
    assert app._tagger_is_open() is False
    assert app.active_tagger_window is None


def test_closed_tagger_poll_releases_main_window_when_worker_finishes():
    gui = _load_gui()
    root = _Root()
    updates = []
    parent = SimpleNamespace(root=root, active_tagger_window=None)
    parent._update_main_action_states = lambda: updates.append("updated")

    tagger = gui.TaggerWindow.__new__(gui.TaggerWindow)
    tagger.parent_app = parent
    tagger.worker = _Worker(True)
    tagger._processing = True
    parent.active_tagger_window = tagger

    tagger._poll_closed_worker()
    assert parent.active_tagger_window is tagger
    assert root.after_calls and root.after_calls[-1][0] == 100
    assert updates == []

    tagger.worker.alive = False
    _delay, callback = root.after_calls[-1]
    callback()

    assert tagger.worker is None
    assert tagger._processing is False
    assert parent.active_tagger_window is None
    assert updates == ["updated"]
