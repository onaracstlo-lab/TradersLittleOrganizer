"""Build 723: reusable permanent-cleanup template and automatic Add Shows review."""
from __future__ import annotations

import base64
import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_inventory_update as updater

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _main_module():
    spec = importlib.util.spec_from_file_location("tlo_main_build723", ROOT / "tlo-main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Value:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


def test_deferred_windows_batch_is_permanent_and_reusable(tmp_path):
    script = tmp_path / "deleteReplacedFolders.bat"
    one = r"E:\Archive\Band & Band 100% ! Mix"
    two = r"F:\Backup\Second Show"
    assert updater._append_delete_command(str(script), one, "Backup & One")
    assert updater._append_delete_command(str(script), two, "Backup 2")
    text = script.read_text(encoding="utf-8")
    assert text.count('rmdir /s /q "%TLO_DELETE_TARGET%"') == 2
    assert text.count('set "TLO_DELETE_TARGET=') == 2
    assert 'DisableDelayedExpansion' in text
    assert 'VolumeLabel' not in text  # label checks are encoded, not embedded in cmd
    assert 'SendToRecycleBin' not in text and 'RESTORE' not in text.upper()
    guard = re.search(r"-EncodedCommand ([A-Za-z0-9+/=]+)", text)
    assert guard
    ps = base64.b64decode(guard.group(1)).decode("utf-16le")
    assert 'VolumeLabel' in ps and '[StringComparison]::Ordinal' in ps
    assert 'ReparsePoint' in ps
    assert 'Remove-Item' not in ps and 'DeleteDirectory' not in ps
    assert text.index('-EncodedCommand ') < text.index('rmdir /s /q')
    assert '100%% ! Mix' in text


def test_unverified_windows_volume_does_not_receive_delete(tmp_path):
    script = tmp_path / "deleteReplacedFolders.bat"
    assert updater._append_delete_command(str(script), r"E:\Show", "")
    text = script.read_text(encoding="utf-8")
    assert 'rmdir /s /q' not in text
    assert '-EncodedCommand ' not in text
    assert 'SKIPPED: unlabeled volume' in text


def test_add_shows_progress_counts_all_results(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    incoming = home / "readyForXfer"
    incoming.mkdir(parents=True)
    for leaf in ("A 2001-01-01 Here", "B 2001-01-02 There"):
        (incoming / leaf).mkdir()
        (incoming / leaf / "01.flac").write_bytes(b"a")
    cfg = SimpleNamespace(TLOHome=str(home), compliant=True, rename_compliantly=False, tag_during_inventory=False, logs=None)
    monkeypatch.setattr(updater, "prepare_updater_config", lambda config: config)
    monkeypatch.setattr(updater, "load_artist_matcher", lambda config: object())
    monkeypatch.setattr(updater, "identify_folder", lambda *args, **kwargs: object())
    monkeypatch.setattr(updater, "_record_dict_for_new_folder", lambda _cfg, folder, *_: {
        "show_name": Path(folder).name, "main_dir_path": folder,
        "artist": Path(folder).name[:1], "date": "2001-01-01", "setlist_file": "",
    })
    monkeypatch.setattr(updater, "find_potential_duplicate_rows_for_folder", lambda _cfg, folder, *_: (
        [{"Show": "Existing B", "VolumePath": "[Backup] E:\\B"}] if Path(folder).name.startswith("B ") else []
    ))
    monkeypatch.setattr(updater, "_add_shows_audio_phase", lambda *_args, **_kwargs: {
        "accepted": True, "removed": False, "excluded": 0, "stats": {}, "reason": "",
    })
    monkeypatch.setattr(updater, "_log_add_shows_metadata", lambda *_a, **_k: None)
    messages = []
    result = updater.process_new_shows(cfg, "[Backup]E:", progress_callback=messages.append)
    assert result["processed"] == 2
    assert result["staged"] == result["duplicates"] == 1
    assert messages[0]["stage"] == "start" and messages[0]["total"] == 2
    assert [v["stage"] for v in messages] == ["start", "processing", "staged", "processing", "duplicate", "complete"]
    assert messages[-1]["processed"] == 2 and messages[-1]["staged"] == 1
    assert messages[-1]["duplicates"] == 1 and messages[-1]["errors"] == 0
    assert (home / "dups" / "B 2001-01-02 There").exists()
    assert (home / "staged" / "A 2001-01-01 Here").exists()


def test_gui_progress_drain_uses_only_main_thread_state():
    gui = _main_module()
    import queue
    view = gui.AddToInventoryWindow.__new__(gui.AddToInventoryWindow)
    view._add_shows_events = queue.SimpleQueue()
    view.add_shows_progress_var = _Value()
    view._add_shows_events.put({"stage": "processing", "folder": "Bob Dylan 1970", "processed": 2,
                                 "total": 3, "staged": 1, "duplicates": 0, "held": 0, "errors": 0})
    view._drain_add_shows_progress()
    assert "2/3" in view.add_shows_progress_var.value
    assert "Bob Dylan 1970" in view.add_shows_progress_var.value


def test_auto_review_starts_only_with_pending_folders_and_keeps_button(tmp_path):
    gui = _main_module()
    view = gui.AddToInventoryWindow.__new__(gui.AddToInventoryWindow)
    view.config = SimpleNamespace(TLOHome=str(tmp_path))
    view.status_var = _Value()
    queued = []
    view._start_background_task = lambda *args: queued.append(args)
    view._start_automatic_duplicate_review()
    assert not queued
    dups = tmp_path / "dups"; dups.mkdir()
    (dups / "Unresolved Show").mkdir()
    view._start_automatic_duplicate_review()
    assert len(queued) == 1
    assert queued[0][2] == view._show_duplicate_work_items
    # Existing user-invoked workflow must remain available for later review.
    assert callable(view._process_duplicates)
    assert "Process Potential" in queued[0][0] or "Scan Potential" in queued[0][0]


def test_skipped_duplicate_review_is_not_marked_completed():
    gui = _main_module()
    view = gui.AddToInventoryWindow.__new__(gui.AddToInventoryWindow)
    view.child_windows = ["unresolved"]
    view._duplicate_batch_active = True
    view._duplicate_batch_reported_complete = False
    view._remove_child("unresolved", completed_action=False)
    assert not view.child_windows
    assert view._duplicate_batch_reported_complete is False
