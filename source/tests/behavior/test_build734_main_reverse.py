"""Main Reverse requires affirmative approval and uses the existing locked engine."""
import importlib.util
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import tlo_reverse_folders as reverse
from tlo_runtime_control import inventory_operation_lock

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fixture(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("main734", ROOT / "tlo-main.py")
    gui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gui)
    home = tmp_path / "TLO Home"
    logs = home / "logs"
    logs.mkdir(parents=True)
    original = tmp_path / "Original show"
    current = tmp_path / "Current show"
    current.mkdir()
    (current / "audio.flac").write_bytes(b"unchanged audio data")
    (logs / "tags734.txt").write_text(f"RENAME_COMPLIANTLY: {original} -> {current}\n", encoding="utf-8")
    app = gui.App.__new__(gui.App)
    app.worker = None
    app.full_inventory_active = app.tag_active = app.reverse_active = False
    app.root = Mock()
    app.vars = {"search_path_override": SimpleNamespace(get=lambda: str(current))}
    app.dry_run_var = SimpleNamespace(get=lambda: False)
    app._resolve_gui_tlo_home = lambda **_kw: str(home)
    app._update_main_action_states = Mock()
    app._update_progress_display = Mock()
    app._consume_inventory_queue = Mock()
    app.progress_stage_var = Mock()
    app.progress_bar = Mock()
    app.output = Mock()
    app.queue = Queue()
    # Dispatch worker and Tk completion inline; all I/O and the actual lock
    # and reversal engine remain real on the host filesystem.
    class InlineThread:
        def __init__(self, *, target, daemon):
            assert daemon is False
            self.target = target
        def start(self):
            self.target()

    monkeypatch.setattr(gui.threading, "Thread", InlineThread)
    monkeypatch.setattr(gui, "schedule_tk_after", lambda widget, delay, callback: (callback(), True)[1])
    for name in ("askyesno", "showerror", "showinfo", "showwarning"):
        monkeypatch.setattr(gui.messagebox, name, Mock(return_value=True))
    return gui, app, home, original, current


@pytest.mark.parametrize("answer", [False, None])
def test_no_or_closed_confirmation_never_plans_or_changes_files(fixture, monkeypatch, answer):
    gui, app, home, original, current = fixture
    gui.messagebox.askyesno.return_value = answer
    forbidden = Mock(side_effect=AssertionError("planning before approval"))
    monkeypatch.setattr(reverse, "prepare_reverse_plan", forbidden)
    app._open_reverse()
    forbidden.assert_not_called()
    assert gui.messagebox.askyesno.call_args.kwargs["default"] == gui.messagebox.NO
    assert str(current) in gui.messagebox.askyesno.call_args.args[1]
    assert current.is_dir() and not original.exists()
    assert not (home / "logs" / "reverseFolders.log").exists()
    assert not app.reverse_active and app.worker is None


def test_confirmed_reverse_restores_original_and_reports_result(fixture):
    gui, app, home, original, current = fixture
    app._open_reverse()
    assert not current.exists()
    assert (original / "audio.flac").read_bytes() == b"unchanged audio data"
    assert "RESTORED_RENAME" in (home / "logs" / "reverseFolders.log").read_text()
    assert "Reversed: 1" in gui.messagebox.showinfo.call_args.args[1]
    assert not app.reverse_active and app.worker is None


def test_confirmed_dry_run_keeps_folders_and_reports_preview(fixture):
    gui, app, home, original, current = fixture
    app.dry_run_var = SimpleNamespace(get=lambda: True)
    app._open_reverse()
    assert current.is_dir() and not original.exists()
    assert "WOULD_RESTORE_RENAME" in (home / "logs" / "reverseFolders.log").read_text()
    assert "Would reverse: 1" in gui.messagebox.showinfo.call_args.args[1]


@pytest.mark.parametrize("invalid", ["", "relative", "missing.txt", "/a;/b", '"/a";"/b"', "/a/*", "/a --/slam artist"])
def test_invalid_input_never_confirms_or_executes(fixture, invalid):
    gui, app, home, original, current = fixture
    app.vars["search_path_override"] = SimpleNamespace(get=lambda: invalid)
    app._open_reverse()
    gui.messagebox.askyesno.assert_not_called()
    gui.messagebox.showerror.assert_called_once()
    assert current.exists() and not original.exists()
    assert not (home / "logs" / "reverseFolders.log").exists()


def test_quoted_literal_semicolon_is_supported(fixture):
    gui, app, home, original, current = fixture
    renamed = current.with_name("Current; show")
    current.rename(renamed)
    (home / "logs" / "tags734.txt").write_text(f"RENAME_COMPLIANTLY: {original} -> {renamed}\n")
    app.vars["search_path_override"] = SimpleNamespace(get=lambda: '"' + str(renamed) + '"')
    app._open_reverse()
    gui.messagebox.askyesno.assert_called_once()
    assert original.is_dir() and not renamed.exists()


def test_active_operation_blocks_reverse(fixture):
    gui, app, home, original, current = fixture
    app.full_inventory_active = True
    app._open_reverse()
    gui.messagebox.askyesno.assert_not_called()
    gui.messagebox.showwarning.assert_called_once()
    assert current.exists() and not original.exists()


def test_cross_application_lock_blocks_reverse_after_confirmation(fixture):
    gui, app, home, original, current = fixture
    with inventory_operation_lock(str(home)):
        app._open_reverse()
    assert "already active" in gui.messagebox.showerror.call_args.args[1]
    assert current.exists() and not original.exists()
    assert not app.reverse_active and app.worker is None


def test_running_reverse_refuses_quit_and_other_mutations(fixture):
    gui, app, home, original, current = fixture
    app.reverse_active = True
    assert app._main_operation_is_running()
    for fn in (app._on_quit, app._start, app._start_tagging_from_main,
               app._open_add_to_inventory, app._open_manual_updates,
               app._open_copy_requests, app._open_redundancy_groups):
        fn()
    assert gui.messagebox.showwarning.call_count == 7
    app.root.destroy.assert_not_called()
    assert current.exists() and not original.exists()
