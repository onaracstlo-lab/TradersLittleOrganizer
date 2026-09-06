"""Build 432 iterative traversal and bounded-wait/network regressions."""
__version__ = "v440"

import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

import initial_dir_walk_lib as W
import tlo_network_io as N
import tlo_phase23_v2 as P

pytestmark = pytest.mark.unit


class _Logs:
    def __init__(self):
        self.complete=[]; self.dead=[]
    def complete_paths(self, value, *args): self.complete.append(value % args if args else value)
    def dead_end(self, value, *args): self.dead.append(value % args if args else value)


def _deep_tree(tmp_path, depth=1050):
    cur=tmp_path
    for _ in range(depth):
        cur=cur/'d'
        cur.mkdir()
    (cur/'01.flac').write_bytes(b'audio')
    return cur


def test_phase1_deep_tree_does_not_depend_on_python_recursion_limit(tmp_path):
    leaf=_deep_tree(tmp_path)
    cfg=SimpleNamespace(logs=_Logs(), performance_mode='balanced', pause_event=None, cancel_requested=False)
    count=W.initial_dir_walk(cfg, str(tmp_path))
    assert count == 1051
    assert cfg.logs.complete and cfg.logs.complete[-1].endswith('01.flac')


def test_phase23_deep_tree_does_not_depend_on_python_recursion_limit(tmp_path):
    leaf=_deep_tree(tmp_path)
    cfg=SimpleNamespace(logs=_Logs())
    found=P._discover_music_dirs(cfg, str(tmp_path))
    assert len(found)==1
    assert Path(found[0]['music_dir']) == leaf


def test_bounded_response_rejects_one_byte_over_limit():
    assert N.read_bounded_text(io.BytesIO(b'abc'), 3) == 'abc'
    with pytest.raises(N.ResponseTooLargeError):
        N.read_bounded_text(io.BytesIO(b'abcd'), 3, label='fixture')


def test_gui_thread_wait_has_finite_timeout(monkeypatch):
    path=Path(__file__).resolve().parents[2]/'tlo-ggi.py'
    spec=importlib.util.spec_from_file_location('tlo_ggi_build432', path)
    gui=importlib.util.module_from_spec(spec); spec.loader.exec_module(gui)
    monkeypatch.setattr(gui, 'GUI_THREAD_CALLBACK_TIMEOUT_SECONDS', 0.01)

    class Root:
        def after(self, delay, callback):
            return 'scheduled-but-never-run'
    obj=SimpleNamespace(root=Root())
    method=gui.App._run_on_gui_thread
    with pytest.raises(RuntimeError, match='GUI closed'):
        # Force worker-thread branch by calling from a short-lived real thread.
        import threading
        result=[]
        def run():
            try: method(obj, lambda: 1)
            except Exception as e: result.append(e)
        t=threading.Thread(target=run); t.start(); t.join(1)
        if result: raise result[0]
        pytest.fail('worker did not return')
