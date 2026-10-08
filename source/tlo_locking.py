"""Cross-platform advisory file locks used by TLO long-lived operations."""

from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import json
import os
import threading
import time
from typing import BinaryIO, Mapping

_ACTIVE_LOCKS: dict[str, BinaryIO] = {}
_GUARD = threading.RLock()


def _key(path_name: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path_name or ""))))


def _lock_file(handle: BinaryIO, *, blocking: bool = False) -> bool:
    """Acquire an exclusive OS advisory lock on the first byte of *handle*."""
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(handle.fileno(), mode, 1)
        else:
            import fcntl

            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(handle.fileno(), flags)
        return True
    except (OSError, IOError):
        return False


def _unlock_file(handle: BinaryIO) -> None:
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, IOError):
        pass


def _open_lock_file(path_name: str) -> BinaryIO:
    os.makedirs(os.path.dirname(path_name) or ".", exist_ok=True)
    handle = open(path_name, "a+b")
    # msvcrt byte-range locking requires the byte to exist.
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    handle.seek(0)
    return handle


def _open_lock_probe_file(path_name: str) -> BinaryIO:
    """Open an existing lock file without creating directories or mutating bytes."""
    return open(path_name, "rb")


def _probe_lock_available(handle: BinaryIO) -> bool:
    """Return True when a non-mutating shared probe lock can be acquired."""
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBRLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
        return True
    except (OSError, IOError):
        return False


def _lock_file_with_short_retry(handle: BinaryIO, *, attempts: int = 3, delay_seconds: float = 0.01) -> bool:
    """Retry a non-blocking acquisition briefly to avoid probe-induced false busy results."""
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        if _lock_file(handle, blocking=False):
            return True
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(delay_seconds)))
    return False


def acquire_owned_lock(path_name: str, payload: Mapping[str, object]) -> bool:
    """Acquire and retain a non-blocking exclusive lock, then publish owner JSON.

    The lock file is deliberately retained after release. Correctness comes from
    the OS-held advisory lock rather than file existence, so a crashed process
    cannot leave a stale-file remove/recreate race behind.
    """
    path_name = str(path_name or "")
    key = _key(path_name)
    with _GUARD:
        if key in _ACTIVE_LOCKS:
            return False
        handle = _open_lock_file(path_name)
        if not _lock_file_with_short_retry(handle):
            handle.close()
            return False
        try:
            encoded = (json.dumps(dict(payload), sort_keys=True) + "\n").encode("utf-8")
            handle.seek(0)
            handle.truncate(0)
            handle.write(encoded)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
            handle.seek(0)
            _ACTIVE_LOCKS[key] = handle
            return True
        except Exception:
            _unlock_file(handle)
            handle.close()
            raise


def release_owned_lock(path_name: str) -> bool:
    """Release a lock held by this process. The lock file itself remains."""
    key = _key(path_name)
    with _GUARD:
        handle = _ACTIVE_LOCKS.pop(key, None)
    if handle is None:
        return False
    _unlock_file(handle)
    try:
        handle.close()
    except OSError:
        pass
    return True


def lock_is_held(path_name: str) -> bool:
    """Return True when another owner currently holds the advisory lock."""
    key = _key(path_name)
    with _GUARD:
        if key in _ACTIVE_LOCKS:
            return True
    if not os.path.exists(path_name):
        return False
    try:
        handle = _open_lock_probe_file(path_name)
    except OSError:
        # Inability to inspect an existing lock must fail closed.
        return True
    try:
        if not _probe_lock_available(handle):
            return True
        _unlock_file(handle)
        return False
    finally:
        try:
            handle.close()
        except OSError:
            pass


def clear_unheld_lock_payload(path_name: str) -> bool:
    """Clear stale owner metadata only if no process currently holds the lock."""
    key = _key(path_name)
    with _GUARD:
        if key in _ACTIVE_LOCKS:
            return False
    if not os.path.exists(path_name):
        return True
    try:
        handle = _open_lock_file(path_name)
    except OSError:
        return False
    try:
        if not _lock_file(handle, blocking=False):
            return False
        handle.seek(0)
        handle.truncate(0)
        handle.write(b"{}\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
        _unlock_file(handle)
        return True
    finally:
        try:
            handle.close()
        except OSError:
            pass
