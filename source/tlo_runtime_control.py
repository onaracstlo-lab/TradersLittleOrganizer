from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from tlo_diagnostics import debug_suppressed_exception
import multiprocessing
import os
import sys
import threading
import time
import json
import socket
from datetime import datetime, timezone
from contextlib import contextmanager

from tlo_locking import acquire_owned_lock, release_owned_lock

_cancel_requested = threading.Event()
_pause_requested = threading.Event()
_lock = threading.RLock()
_active_executor = None
_active_pause_proxy = None
_worker_priority_applied = False
_windows_original_priority = None
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
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)


def clear_pause():
    _pause_requested.clear()
    with _lock:
        proxy = _active_pause_proxy
    if proxy is not None:
        try:
            proxy.clear()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)


def register_active_pause_proxy(proxy):
    global _active_pause_proxy
    with _lock:
        _active_pause_proxy = proxy
        try:
            if _pause_requested.is_set():
                proxy.set()
            else:
                proxy.clear()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)


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
            except Exception as exc:  # noqa: BLE001 - best-effort boundary
                debug_suppressed_exception(__name__, exc)

    processes = _active_processes_for_executor(executor)
    for process in processes:
        if _terminate_process(process):
            process_count += 1

    for process in processes:
        try:
            if hasattr(process, "join"):
                process.join(timeout=join_timeout)
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    for process in processes:
        if _kill_process(process):
            process_count += 1

    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        try:
            executor.shutdown(wait=False)
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)
    except Exception as exc:  # noqa: BLE001 - best-effort boundary
        debug_suppressed_exception(__name__, exc)

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
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    for child in children:
        try:
            child.join(timeout=join_timeout)
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    for child in children:
        try:
            if child.is_alive() and hasattr(child, "kill"):
                child.kill()
                terminated += 1
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    for child in children:
        try:
            child.join(timeout=kill_timeout)
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)

    return terminated


def flush_standard_streams():
    """Best-effort flush before a forced process exit."""
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        try:
            if stream is not None:
                stream.flush()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)


def _windows_get_priority():
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetCurrentProcess()
        value = int(kernel32.GetPriorityClass(handle) or 0)
        return value or None
    except Exception:
        return None


def _windows_set_priority(priority_class):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetCurrentProcess()
        return bool(kernel32.SetPriorityClass(handle, priority_class))
    except Exception:
        return False


def apply_process_priority(config=None):
    """Apply reversible parent-process priority behavior.

    Windows permits the GUI/CLI process priority class to be restored, so every
    mode transition explicitly sets the appropriate class. POSIX niceness cannot
    normally be raised back without privilege; the long-lived parent therefore
    remains at normal priority and gentle/balanced niceness is applied only by
    worker-process initialization.
    """
    global _windows_original_priority
    mode = normalize_performance_mode(getattr(config, "performance_mode", "balanced"))
    if not sys.platform.startswith("win"):
        return False

    IDLE_PRIORITY_CLASS = 0x00000040
    BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
    NORMAL_PRIORITY_CLASS = 0x00000020
    if _windows_original_priority is None:
        _windows_original_priority = _windows_get_priority() or NORMAL_PRIORITY_CLASS

    if mode == "gentle":
        target = IDLE_PRIORITY_CLASS
    elif mode == "balanced":
        target = BELOW_NORMAL_PRIORITY_CLASS
    else:
        target = _windows_original_priority or NORMAL_PRIORITY_CLASS
    return _windows_set_priority(target)


def apply_worker_process_priority(mode="balanced"):
    """Lower only worker-process priority for gentle/balanced POSIX work."""
    global _worker_priority_applied
    mode = normalize_performance_mode(mode)
    if sys.platform.startswith("win"):
        # Windows workers inherit the parent's class; make the intended mode
        # explicit in case the start method/platform does not preserve it.
        class _Config:
            performance_mode = mode
        return apply_process_priority(_Config())
    if mode in {"fast", "extreme"} or _worker_priority_applied:
        return False
    increment = 10 if mode == "gentle" else 5
    try:
        os.nice(increment)
        _worker_priority_applied = True
        return True
    except Exception:
        return False


def _inventory_lock_path(tlo_home):
    return os.path.join(os.path.abspath(str(tlo_home or "")), "logs", ".inventory-run.lock")


def acquire_inventory_lock(tlo_home):
    """Enforce one inventory-mutating run per TLOHome."""
    raw_home = str(tlo_home or "").strip()
    if not raw_home:
        raise RuntimeError("TLOHome is required before inventory can start.")
    home = os.path.abspath(raw_home)
    path_name = _inventory_lock_path(home)
    payload = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "operation": "inventory",
    }
    try:
        acquired = acquire_owned_lock(path_name, payload)
    except OSError as exc:
        raise RuntimeError(f"Cannot create inventory lock under TLOHome: {exc}") from exc
    if not acquired:
        owner = ""
        try:
            with open(path_name, "r", encoding="utf-8") as infile:
                data = json.load(infile)
            if isinstance(data, dict):
                host = str(data.get("hostname", "") or "")
                pid = str(data.get("pid", "") or "")
                owner = f" (owner: {host or 'unknown host'} pid {pid or 'unknown'})"
        except (OSError, ValueError):
            pass
        raise RuntimeError(
            "Another inventory-mutating TLO run is already active for this TLOHome" + owner + ". "
            "Search and other read-only operations may still run."
        )
    return path_name


def release_inventory_lock(path_name):
    if path_name:
        release_owned_lock(path_name)


@contextmanager
def inventory_operation_lock(tlo_home):
    """Context manager for inventory-output mutating GUI operations."""
    path_name = acquire_inventory_lock(tlo_home)
    try:
        yield path_name
    finally:
        release_inventory_lock(path_name)


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
