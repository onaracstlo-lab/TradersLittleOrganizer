__version__ = "v321"
# TLO-GI package version: v321
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.

import multiprocessing
import os
import sys
import threading
import time

_cancel_requested = threading.Event()
_pause_requested = threading.Event()
_lock = threading.RLock()
_active_executor = None
_active_pause_proxy = None
_priority_applied = False
_throttle_state = threading.local()

PERFORMANCE_MODES = {"gentle", "balanced", "fast", "extreme"}


def normalize_performance_mode(mode):
    value = str(mode or "balanced").strip().lower()
    if value not in PERFORMANCE_MODES:
        return "balanced"
    return value


def clear_cancel_request():
    _cancel_requested.clear()


def request_cancel():
    _cancel_requested.set()


def is_cancel_requested():
    return _cancel_requested.is_set()


def request_pause():
    _pause_requested.set()
    with _lock:
        proxy = _active_pause_proxy
    if proxy is not None:
        try:
            proxy.set()
        except Exception:
            pass


def clear_pause():
    _pause_requested.clear()
    with _lock:
        proxy = _active_pause_proxy
    if proxy is not None:
        try:
            proxy.clear()
        except Exception:
            pass


def register_active_pause_proxy(proxy):
    global _active_pause_proxy
    with _lock:
        _active_pause_proxy = proxy
        try:
            if _pause_requested.is_set():
                proxy.set()
            else:
                proxy.clear()
        except Exception:
            pass


def unregister_active_pause_proxy(proxy=None):
    global _active_pause_proxy
    with _lock:
        if proxy is None or _active_pause_proxy is proxy:
            _active_pause_proxy = None


def _proxy_pause_requested(config=None):
    proxy = getattr(config, "runtime_pause_proxy", None) if config is not None else None
    if proxy is None:
        with _lock:
            proxy = _active_pause_proxy
    if proxy is None:
        return False
    try:
        return bool(proxy.is_set())
    except Exception:
        return False


def is_pause_requested(config=None):
    return _pause_requested.is_set() or _proxy_pause_requested(config)


def wait_if_paused(config=None, sleep_seconds=0.10):
    while is_pause_requested(config):
        if is_cancel_requested() or bool(getattr(config, "cancel_requested", False)):
            raise KeyboardInterrupt
        time.sleep(sleep_seconds)


def register_active_executor(executor):
    global _active_executor
    with _lock:
        _active_executor = executor


def unregister_active_executor(executor=None):
    global _active_executor
    with _lock:
        if executor is None or _active_executor is executor:
            _active_executor = None


def _active_processes_for_executor(executor):
    processes = getattr(executor, "_processes", None)
    if isinstance(processes, dict):
        return list(processes.values())
    if processes:
        try:
            return list(processes)
        except TypeError:
            return []
    return []


def _terminate_process(process):
    try:
        if hasattr(process, "is_alive") and process.is_alive():
            process.terminate()
            return True
    except Exception:
        return False
    return False


def _kill_process(process):
    try:
        if hasattr(process, "is_alive") and process.is_alive() and hasattr(process, "kill"):
            process.kill()
            return True
    except Exception:
        return False
    return False


def request_cancel_and_terminate_active_executor(join_timeout=1.0):
    """Request cancellation and terminate the active ProcessPoolExecutor, if any."""
    request_cancel()
    with _lock:
        executor = _active_executor

    if executor is None:
        return 0

    process_count = 0

    for method_name in ("terminate_workers", "kill_workers"):
        method = getattr(executor, method_name, None)
        if method is not None:
            try:
                method()
                return 1
            except Exception:
                pass

    processes = _active_processes_for_executor(executor)
    for process in processes:
        if _terminate_process(process):
            process_count += 1

    for process in processes:
        try:
            if hasattr(process, "join"):
                process.join(timeout=join_timeout)
        except Exception:
            pass

    for process in processes:
        if _kill_process(process):
            process_count += 1

    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        try:
            executor.shutdown(wait=False)
        except Exception:
            pass
    except Exception:
        pass

    return process_count


def terminate_all_children(join_timeout=1.0, kill_timeout=0.5):
    """Best-effort terminate/join/kill sweep for multiprocessing children.

    This is the hard-exit backstop used before os._exit() and in CLI Ctrl-C
    handling.  It catches ProcessPoolExecutor workers plus multiprocessing.Manager
    server processes even if a caller forgot to register them with runtime_control.
    It intentionally does not manage subprocess.Popen children such as ffmpeg;
    those need their own timeout/kill handling at the subprocess call site.
    """
    try:
        children = list(multiprocessing.active_children())
    except Exception:
        return 0

    terminated = 0
    for child in children:
        try:
            if child.is_alive():
                child.terminate()
                terminated += 1
        except Exception:
            pass

    for child in children:
        try:
            child.join(timeout=join_timeout)
        except Exception:
            pass

    for child in children:
        try:
            if child.is_alive() and hasattr(child, "kill"):
                child.kill()
                terminated += 1
        except Exception:
            pass

    for child in children:
        try:
            child.join(timeout=kill_timeout)
        except Exception:
            pass

    return terminated


def flush_standard_streams():
    """Best-effort flush before a forced process exit."""
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        try:
            if stream is not None:
                stream.flush()
        except Exception:
            pass


def _windows_set_priority(priority_class):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetCurrentProcess()
        return bool(kernel32.SetPriorityClass(handle, priority_class))
    except Exception:
        return False


def apply_process_priority(config=None):
    """Lower process priority in gentle/balanced modes where supported.

    This is intentionally best-effort. If the OS refuses the request, inventory
    continues and relies on max-workers plus traversal throttling.
    """
    global _priority_applied
    mode = normalize_performance_mode(getattr(config, "performance_mode", "balanced"))
    if mode in {"fast", "extreme"}:
        return False

    if sys.platform.startswith("win"):
        # Win32 priority classes.
        IDLE_PRIORITY_CLASS = 0x00000040
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        priority = IDLE_PRIORITY_CLASS if mode == "gentle" else BELOW_NORMAL_PRIORITY_CLASS
        return _windows_set_priority(priority)

    # On POSIX, higher nice values mean lower priority. Do this once per process.
    if _priority_applied:
        return False
    increment = 10 if mode == "gentle" else 5
    try:
        os.nice(increment)
        _priority_applied = True
        return True
    except Exception:
        return False


def throttle_point(config=None, units=1):
    """Yield periodically during filesystem-heavy traversal in gentle/balanced modes."""
    if is_cancel_requested() or bool(getattr(config, "cancel_requested", False)):
        raise KeyboardInterrupt
    wait_if_paused(config)

    mode = normalize_performance_mode(getattr(config, "performance_mode", "balanced"))
    if mode in {"fast", "extreme"}:
        return

    if mode == "gentle":
        interval, seconds = 100, 0.05
    else:
        interval, seconds = 250, 0.01

    count = getattr(_throttle_state, "count", 0) + max(1, int(units or 1))
    if count >= interval:
        count = 0
        time.sleep(seconds)
    _throttle_state.count = count
