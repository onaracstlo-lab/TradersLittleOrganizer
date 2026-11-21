"""Journal and explicit recovery for interrupted same-volume Tag Copy/Delete moves.

Only journaled, validated, owner-inactive moves may be recovered. Never infer
ownership of an unjournaled .tlo-partial-* directory from its folder name.
"""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import json
import os
import re
import socket
import sys
import stat
from typing import Callable


_JOURNAL_NAME = re.compile(r"^\.tlo-move-([0-9a-f]{32})\.json$")
_FORMAT = "TLO_STAGED_SAME_VOLUME_MOVE_V1"
_MAX_JOURNAL_BYTES = 16384


def _journal_for_stage(stage: str) -> str:
    basename = os.path.basename(os.path.normpath(stage))
    prefix = ".tlo-partial-"
    suffix = basename[len(prefix):] if basename.startswith(prefix) else ""
    if not re.fullmatch(r"[a-f0-9]{32}", suffix):
        raise ValueError(f"Not an owned staging path: {stage}")
    return os.path.join(os.path.dirname(stage), f".tlo-move-{suffix}.json")


def _fsync_directory_of(path: str) -> None:
    """Persist parent-directory entry changes where the platform supports it."""
    try:
        fd = os.open(os.path.dirname(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return  # Native Windows does not normally permit directory fsync.
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _issuance_for(source: str, suffix: str) -> str:
    """Independent record in the original source parent, not staging area."""
    return os.path.join(os.path.dirname(os.path.abspath(source)), f".tlo-issued-{suffix}.json")


def _write_exclusive_json(path: str, payload: dict) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write((json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    _fsync_directory_of(path)


def record_same_volume_move(source: str, stage: str, intended_target: str) -> str:
    """Persist original-path recovery metadata before renaming source to stage."""
    journal = _journal_for_stage(stage)
    payload = {
        "format": _FORMAT,
        "source": os.path.abspath(source),
        "stage": os.path.abspath(stage),
        "target": os.path.abspath(intended_target),
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "pid_created": _process_creation_identity(os.getpid()),
    }
    suffix = _JOURNAL_NAME.fullmatch(os.path.basename(journal)).group(1)
    issuance = _issuance_for(source, suffix)
    _write_exclusive_json(issuance, payload)
    try:
        _write_exclusive_json(journal, payload)
    except BaseException:
        os.unlink(issuance)
        raise
    return journal


def clear_move_journal(journal: str) -> None:
    """Removing stale metadata is best effort after a known complete move."""
    try:
        # Only a matching validated issuance may be removed, never an arbitrary
        # source path copied from an attacker-controlled journal.
        try:
            entry = _journal_data(journal, os.path.dirname(os.path.abspath(journal)))
            issuance = _issuance_for(entry["source"], _JOURNAL_NAME.fullmatch(os.path.basename(journal)).group(1))
            os.unlink(issuance)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        os.unlink(journal)
        _fsync_directory_of(journal)
    except FileNotFoundError:
        pass
    except OSError:
        # An orphan journal with no stage can be reconciled explicitly later.
        pass


def _windows_pid_is_alive(pid: int, *, kernel32=None, last_error=None) -> bool:
    """Non-destructive Windows process query; unknown status is treated as alive.

    Windows os.kill(pid, 0) is NOT a process probe: signal zero can deliver
    CTRL_C_EVENT. Never call os.kill from the Windows recovery path.
    """
    import ctypes
    from ctypes import wintypes

    if kernel32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if last_error is None:
        last_error = getattr(ctypes, "get_last_error", lambda: 0)
    query = kernel32.OpenProcess
    exit_code = kernel32.GetExitCodeProcess
    close = kernel32.CloseHandle
    query.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    query.restype = wintypes.HANDLE
    exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    exit_code.restype = wintypes.BOOL
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = query(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # ERROR_INVALID_PARAMETER: PID does not designate an existing process.
        # Access-denied and unknown failures must prevent recovery.
        return int(last_error()) != 87
    try:
        code = wintypes.DWORD()
        if not exit_code(handle, ctypes.byref(code)):
            return True  # Could not establish termination; fail closed.
        return int(code.value) == 259  # STILL_ACTIVE
    finally:
        close(handle)


def _process_creation_identity(pid: int) -> str | None:
    """Return a stable PID birth identity when the OS supports one.

    Linux /proc/<pid>/stat starttime counts ticks since boot. On Windows,
    GetProcessTimes exposes a 64-bit process creation FILETIME. If the probe
    fails the unknown identity is deliberately not proof of termination.
    """
    if sys.platform.startswith("linux"):
        try:
            stat_text = open(f"/proc/{pid}/stat", encoding="ascii").read()
            return "linux:" + stat_text.rsplit(") ", 1)[1].split()[19]
        except (OSError, ValueError, IndexError):
            return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return None
            try:
                created = wintypes.FILETIME()
                exited = wintypes.FILETIME()
                kernel_time = wintypes.FILETIME()
                user_time = wintypes.FILETIME()
                if not kernel.GetProcessTimes(handle, ctypes.byref(created),
                                               ctypes.byref(exited), ctypes.byref(kernel_time),
                                               ctypes.byref(user_time)):
                    return None
                value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
                return f"win:{value}"
            finally:
                kernel.CloseHandle(handle)
        except (OSError, AttributeError, ValueError):
            return None
    return None


def _pid_is_alive(pid: int) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == 'nt':
        try:
            return _windows_pid_is_alive(pid)
        except Exception:
            return True  # Do not recover when process status is unknown.
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True


def _journal_data(journal: str, destination_parent: str) -> dict:
    if os.path.islink(journal):
        raise ValueError("Recovery journal is a symlink")
    match = _JOURNAL_NAME.fullmatch(os.path.basename(journal))
    if match is None:
        raise ValueError("Unrecognized recovery journal name")
    fd = os.open(journal, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Recovery journal is not a regular file")
        if os.fstat(stream.fileno()).st_size > _MAX_JOURNAL_BYTES:
            raise ValueError("Recovery journal exceeds size limit")
        payload = json.loads(stream.read(_MAX_JOURNAL_BYTES + 1))
    if not isinstance(payload, dict) or payload.get("format") != _FORMAT:
        raise ValueError("Unrecognized staging record format")
    expected_stage = os.path.join(destination_parent, f".tlo-partial-{match.group(1)}")
    stage = payload.get("stage")
    source = payload.get("source")
    target = payload.get("target")
    if not all(isinstance(v, str) and os.path.isabs(v) for v in (stage, source, target)):
        raise ValueError("Staging record contains incomplete paths")
    if os.path.normcase(os.path.normpath(stage)) != os.path.normcase(expected_stage):
        raise ValueError("Staging path does not match its journal")
    if os.path.normcase(os.path.dirname(os.path.normpath(target))) != os.path.normcase(destination_parent):
        raise ValueError("Target is not inside the recorded destination")
    if not isinstance(payload.get("pid"), int) or not isinstance(payload.get("host"), str):
        raise ValueError("Staging record has invalid owner information")
    if os.path.islink(expected_stage):
        raise ValueError("Staging directory is a symbolic link")
    # A journal alone cannot authorize a move: require its independently
    # recorded identical issuance from the original source parent.
    issuance = _issuance_for(source, match.group(1))
    if os.path.islink(issuance):
        raise ValueError("Issuance record is a symbolic link")
    try:
        with open(issuance, "rb") as record:
            if not stat.S_ISREG(os.fstat(record.fileno()).st_mode):
                raise ValueError("Issuance is not a regular file")
            if os.fstat(record.fileno()).st_size > _MAX_JOURNAL_BYTES:
                raise ValueError("Issuance exceeds size limit")
            issued = json.loads(record.read(_MAX_JOURNAL_BYTES + 1))
    except FileNotFoundError as exc:
        raise ValueError("Missing independent issuance record; manual inspection required") from exc
    if issued != payload:
        raise ValueError("Recovery journal does not match original issuance")
    parent = os.path.abspath(os.path.dirname(source))
    cursor = parent
    while True:
        if os.path.islink(cursor):
            raise ValueError("Recovery source parent contains a symbolic-link component")
        ancestor = os.path.dirname(cursor)
        if ancestor == cursor:
            break
        cursor = ancestor
    return payload


def recover_interrupted_stage_moves(
    destination_parent: str, *, dry_run: bool = True, emit: Callable[[str], None] | None = None
) -> dict[str, int]:
    """Inspect/restore only verified, inactive same-volume move journals.

    The caller must deliberately opt in to actual recovery. Existing sources,
    active owners, foreign hosts and ambiguous states are never overwritten.
    """
    parent = os.path.abspath(destination_parent)
    if not os.path.isdir(parent):
        raise ValueError(f"Staging recovery requires an existing directory: {parent}")
    totals = {"found": 0, "restored": 0, "cleaned": 0, "conflicts": 0, "would_restore": 0}
    for filename in sorted(os.listdir(parent)):
        if not _JOURNAL_NAME.fullmatch(filename):
            continue
        totals["found"] += 1
        journal = os.path.join(parent, filename)
        try:
            entry = _journal_data(journal, parent)
            source, stage, target = (entry[key] for key in ("source", "stage", "target"))
            if entry["host"] != socket.gethostname():
                raise ValueError(f"Foreign worker host {entry['host']!r}; source={source}, stage={stage}")
            if _pid_is_alive(entry["pid"]):
                current_created = _process_creation_identity(entry["pid"])
                recorded_created = entry.get("pid_created")
                if (recorded_created is not None and current_created is not None and
                        recorded_created != current_created):
                    # The original owner exited; this PID belongs to another
                    # process. An independently matched issuance is required.
                    pass
                else:
                    raise ValueError(f"Worker PID {entry['pid']} is active or unknown; source={source}, stage={stage}; close TLO before manual recovery")
            src_present = os.path.lexists(source)
            stage_present = os.path.lexists(stage)
            target_present = os.path.lexists(target)
            if stage_present and not src_present and not target_present and os.path.isdir(stage):
                if dry_run:
                    totals["would_restore"] += 1
                    if emit:
                        emit(f"WOULD_RESTORE: {stage} -> {source}")
                else:
                    # Lazily import the same native no-replace primitive used to move the show.
                    from tlo_tag_lib import _publish_staged_directory_noreplace
                    _publish_staged_directory_noreplace(stage, source)
                    clear_move_journal(journal)
                    totals["restored"] += 1
                    if emit:
                        emit(f"RESTORED: {stage} -> {source}")
            elif not stage_present and (src_present != target_present):
                if not dry_run:
                    clear_move_journal(journal)
                    totals["cleaned"] += 1
                if emit:
                    emit(f"{'WOULD_CLEAN' if dry_run else 'CLEANED'}: completed move record {journal}")
            else:
                raise ValueError("Ambiguous source, stage and destination state; no automatic repair")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            totals["conflicts"] += 1
            if emit:
                emit(f"RECOVERY_CONFLICT: {journal} | {exc}")
    if totals["found"] == 0 and emit:
        emit("No recorded staged moves found; unjournaled partial folders must be reviewed manually.")
    return totals
