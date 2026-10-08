from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_copy_requests as CR
import tlo_runtime_control as RC
import tlo_setlistfm_lookup as SFM

pytestmark = pytest.mark.behavior


def _copy_lock_holder(path_name: str, ready, release) -> None:
    import tlo_copy_requests as child_cr

    child_cr._acquire_exclusive_lock(path_name, "holder")
    ready.set()
    release.wait(10)
    child_cr._release_exclusive_lock(path_name)


def _copy_lock_crash(path_name: str, ready) -> None:
    import os as child_os
    import tlo_copy_requests as child_cr

    child_cr._acquire_exclusive_lock(path_name, "crasher")
    ready.set()
    child_os._exit(0)


def _inventory_lock_holder(home: str, ready, release) -> None:
    import tlo_runtime_control as child_rc

    lock_path = child_rc.acquire_inventory_lock(home)
    ready.set()
    release.wait(10)
    child_rc.release_inventory_lock(lock_path)


def test_build527_windows_priority_transitions_restore_original(monkeypatch):
    calls = []
    monkeypatch.setattr(RC.sys, "platform", "win32")
    monkeypatch.setattr(RC, "_windows_original_priority", None)
    monkeypatch.setattr(RC, "_windows_get_priority", lambda: 0x20)
    monkeypatch.setattr(RC, "_windows_set_priority", lambda value: calls.append(value) or True)

    assert RC.apply_process_priority(SimpleNamespace(performance_mode="gentle")) is True
    assert RC.apply_process_priority(SimpleNamespace(performance_mode="fast")) is True
    assert RC.apply_process_priority(SimpleNamespace(performance_mode="balanced")) is True
    assert RC.apply_process_priority(SimpleNamespace(performance_mode="extreme")) is True

    assert calls == [0x40, 0x20, 0x4000, 0x20]


def test_build527_posix_parent_priority_is_not_permanently_niced(monkeypatch):
    monkeypatch.setattr(RC.sys, "platform", "linux")
    monkeypatch.setattr(RC.os, "nice", lambda _value: pytest.fail("parent process must not be niced"))

    assert RC.apply_process_priority(SimpleNamespace(performance_mode="gentle")) is False
    assert RC.apply_process_priority(SimpleNamespace(performance_mode="balanced")) is False
    assert RC.apply_process_priority(SimpleNamespace(performance_mode="fast")) is False


def test_build527_posix_worker_priority_applies_once(monkeypatch):
    calls = []
    monkeypatch.setattr(RC.sys, "platform", "linux")
    monkeypatch.setattr(RC, "_worker_priority_applied", False)
    monkeypatch.setattr(RC.os, "nice", lambda value: calls.append(value) or 0)

    assert RC.apply_worker_process_priority("gentle") is True
    assert RC.apply_worker_process_priority("balanced") is False
    assert calls == [10]


def test_build527_rate_limit_wait_is_clamped_and_future_state_is_corrupt():
    wait, corrupt = SFM._bounded_rate_limit_wait(100.4, 100.0, 0.6)
    assert wait == pytest.approx(0.6)
    assert corrupt is False

    wait, corrupt = SFM._bounded_rate_limit_wait(500.0, 100.0, 0.6)
    assert wait == 0.0
    assert corrupt is True

    wait, corrupt = SFM._bounded_rate_limit_wait(50.0, 100.0, 0.6)
    assert wait == 0.0
    assert corrupt is False


def test_build527_future_rate_state_does_not_sleep(monkeypatch, tmp_path):
    state_file = Path(SFM._rate_limit_state_file(str(tmp_path)))
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"last_request": 9999999999.0, "counts": {}, "daily": {}}), encoding="utf-8")
    sleeps = []
    monkeypatch.setattr(SFM.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(SFM.time, "time", lambda: 1000.0)

    number = SFM.wait_for_rate_limit(0.6, max_calls=10, run_id="build527", tlo_home=str(tmp_path))

    assert number == 1
    assert sleeps == []
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["last_request"] == 1000.0


def test_build527_inventory_lock_blocks_second_mutating_run_but_recovers_after_exit(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    holder = ctx.Process(target=_inventory_lock_holder, args=(str(tmp_path), ready, release))
    holder.start()
    assert ready.wait(10)

    with pytest.raises(RuntimeError, match="Another inventory-mutating TLO run"):
        RC.acquire_inventory_lock(str(tmp_path))

    release.set()
    holder.join(10)
    assert holder.exitcode == 0

    lock_path = RC.acquire_inventory_lock(str(tmp_path))
    RC.release_inventory_lock(lock_path)


def test_build527_copy_request_lock_blocks_live_owner_without_remove_recreate_race(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    release = ctx.Event()
    lock_path = str(tmp_path / "copy.lock")
    holder = ctx.Process(target=_copy_lock_holder, args=(lock_path, ready, release))
    holder.start()
    assert ready.wait(10)

    with pytest.raises(CR.CopyRequestError, match="already active"):
        CR._acquire_exclusive_lock(lock_path, "contender")
    assert Path(lock_path).exists()

    release.set()
    holder.join(10)
    assert holder.exitcode == 0


def test_build527_copy_request_lock_recovers_crashed_owner_without_deleting_lock_file(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Event()
    lock_path = str(tmp_path / "copy.lock")
    holder = ctx.Process(target=_copy_lock_crash, args=(lock_path, ready))
    holder.start()
    assert ready.wait(10)
    holder.join(10)
    assert holder.exitcode == 0
    assert Path(lock_path).exists()

    assert CR._acquire_exclusive_lock(lock_path, "recovered") == lock_path
    CR._release_exclusive_lock(lock_path)
    assert Path(lock_path).exists()


def test_build527_main_gui_mutating_workflows_use_inventory_lock():
    source = (Path(__file__).resolve().parents[2] / "tlo-main.py").read_text(encoding="utf-8")
    assert source.count("with inventory_operation_lock(self.config.TLOHome):") >= 3
    assert "return process_new_shows(" in source
    assert "result = process_duplicate_folder(" in source
    assert "result = apply_manual_updates_file(" in source
