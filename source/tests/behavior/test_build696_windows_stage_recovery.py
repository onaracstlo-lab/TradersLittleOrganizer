"""Build 696 Windows recovery: never send CTRL_C_EVENT to probe a PID."""
from __future__ import annotations
import ctypes
import os
import subprocess
import sys

import pytest

import tlo_staging_recovery as recovery

pytestmark = pytest.mark.behavior


class _Call:
    def __init__(self, fn):
        self.fn = fn
        self.argtypes = None
        self.restype = None
    def __call__(self, *args):
        return self.fn(*args)


class _Kernel:
    def __init__(self, handle=1, code=259, success=True):
        self.closed = []
        self.OpenProcess = _Call(lambda access, inherit, pid: handle)
        self.GetExitCodeProcess = _Call(
            lambda h, ptr: self._read(ptr, code, success))
        self.CloseHandle = _Call(lambda h: self.closed.append(h) or 1)
    @staticmethod
    def _read(ptr, code, success):
        if success:
            ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ulong)).contents.value = code
        return 1 if success else 0


def test_windows_pid_query_detects_dead_and_active_without_signal():
    for code, expected in ((0, False), (259, True)):
        kernel = _Kernel(code=code)
        assert recovery._windows_pid_is_alive(1234, kernel32=kernel) is expected
        assert len(kernel.closed) == 1


def test_windows_pid_query_fails_closed_on_unknown_or_denied():
    assert recovery._windows_pid_is_alive(123, kernel32=_Kernel(handle=0), last_error=lambda:87) is False
    assert recovery._windows_pid_is_alive(123, kernel32=_Kernel(handle=0), last_error=lambda:5) is True
    assert recovery._windows_pid_is_alive(123, kernel32=_Kernel(success=False)) is True


def test_recovery_liveness_does_not_use_os_kill_on_windows(monkeypatch):
    # Replacing os.name itself changes pathlib behavior globally, so invoke the
    # Windows-only helper directly with a fake kernel and forbid the POSIX probe.
    def forbidden(*args):
        raise AssertionError('os.kill must not probe a Windows PID')
    monkeypatch.setattr(recovery.os, 'kill', forbidden)
    assert recovery._windows_pid_is_alive(177, kernel32=_Kernel(code=0)) is False


@pytest.mark.skipif(os.name != 'nt', reason='native Win32 PID behavior')
def test_native_windows_completed_pid_is_not_considered_active():
    proc = subprocess.Popen([sys.executable, '-c', 'pass'])
    proc.wait(timeout=15)
    assert recovery._pid_is_alive(proc.pid) is False
