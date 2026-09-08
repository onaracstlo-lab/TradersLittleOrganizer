"""Pre-mutation audio corruption threshold handling for TLO."""
from __future__ import annotations

__version__ = "v446"

import ctypes
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from mutagen import File as MutagenFile, MutagenError

try:
    from mutagen.flac import FLAC
except Exception:
    FLAC = None

TRASH_SUBPROCESS_TIMEOUT_SECONDS = 60.0

MEDIA_EXTENSIONS = {
    ".flac", ".mp3", ".m4a", ".mp4", ".ogg", ".oga", ".opus", ".wav",
    ".aif", ".aiff", ".ape", ".wv", ".tta", ".wma",
}


def _norm(path):
    return os.path.normcase(os.path.normpath(str(path or "")))


def group_audio_snapshot(group):
    """Return (audio_paths, read_errors) for one logical-show snapshot.

    A directory-listing failure is *unverifiable*, not evidence that its files are
    corrupt.  Callers performing corruption-driven mutations must refuse to
    mutate when read_errors is non-empty.
    """
    out = []
    errors = []
    seen = set()
    directories = list(group.get("music_dirs") or [group.get("main_dir_path", "")])
    for directory in directories:
        directory = str(directory or "")
        if not directory:
            continue
        try:
            names = os.listdir(directory)
        except (OSError, MemoryError) as exc:
            errors.append((directory, f"{type(exc).__name__}: {exc}"))
            continue
        except Exception as exc:
            errors.append((directory, f"{type(exc).__name__}: {exc}"))
            continue
        for name in names:
            path = os.path.join(directory, name)
            try:
                is_file = os.path.isfile(path)
            except Exception as exc:
                errors.append((path, f"{type(exc).__name__}: {exc}"))
                continue
            if is_file and Path(name).suffix.lower() in MEDIA_EXTENSIONS:
                key = _norm(path)
                if key not in seen:
                    seen.add(key)
                    out.append(path)
    return sorted(out, key=str.lower), errors


def group_audio_files(group):
    """Compatibility helper returning the readable directory snapshot paths."""
    return group_audio_snapshot(group)[0]


def _exception_chain(exc):
    """Yield one exception and its chained causes/contexts without looping."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _unverifiable_underlying_error(exc):
    """Return the filesystem/resource cause that makes validation unreliable."""
    for chained in _exception_chain(exc):
        if isinstance(chained, (PermissionError, OSError, MemoryError)):
            return chained
    return None


def _preflight_audio_read(path):
    """Prove that the path is presently stattable and readable before validation."""
    os.stat(path)
    with open(path, "rb") as handle:
        handle.read(1)


def classify_audio_paths(paths):
    """Return (proven_corrupt_paths, unverifiable_errors).

    Only a validator/format failure with no filesystem/resource cause is proof of
    corruption. Missing, locked, unreadable, disconnected, or resource-failed
    paths are unverifiable and therefore suppress all corruption-driven mutation.
    """
    bad = []
    unverifiable = []
    for path in list(paths or []):
        try:
            _preflight_audio_read(path)
            if str(path).lower().endswith(".flac") and FLAC is not None:
                FLAC(path)
            else:
                audio = MutagenFile(path)
                if audio is None:
                    raise ValueError("unrecognized audio format")
        except (PermissionError, OSError, MemoryError) as exc:
            unverifiable.append((path, f"{type(exc).__name__}: {exc}"))
        except (MutagenError, ValueError) as exc:
            cause = _unverifiable_underlying_error(exc)
            if cause is not None:
                unverifiable.append((path, f"{type(cause).__name__}: {cause}"))
            else:
                bad.append(path)
        except Exception as exc:
            # Unexpected validator failures are infrastructure/implementation
            # failures, not proof that the user's audio bytes are corrupt.
            unverifiable.append((path, f"{type(exc).__name__}: {exc}"))
    return bad, unverifiable


def corrupt_audio_paths(paths):
    """Return only paths positively identified as corrupt/unrecognized."""
    return classify_audio_paths(paths)[0]


def corrupt_audio_files(group):
    return corrupt_audio_paths(group_audio_files(group))


def fully_corrupt_music_dirs(group, audio_files=None, bad_files=None):
    """Return inventoried music directories whose direct audio files are all corrupt."""
    audio_files = list(group_audio_files(group) if audio_files is None else audio_files)
    bad_files = list(corrupt_audio_files(group) if bad_files is None else bad_files)
    bad_keys = {_norm(path) for path in bad_files}
    directories = list(group.get("music_dirs") or [])
    if not directories and group.get("main_dir_path"):
        directories = [group.get("main_dir_path")]
    result = []
    seen = set()
    for directory in directories:
        directory = os.path.normpath(str(directory or ""))
        if not directory:
            continue
        directory_key = _norm(directory)
        if directory_key in seen:
            continue
        seen.add(directory_key)
        direct_audio = [
            path for path in audio_files
            if _norm(os.path.dirname(path)) == directory_key
        ]
        if direct_audio and all(_norm(path) in bad_keys for path in direct_audio):
            result.append(directory)
    return sorted(result, key=str.lower)


def exceeds_threshold(total, bad, acceptable_percent):
    """Legacy strict-threshold helper retained for historical regression tests only."""
    return total > 0 and bad * 100 > int(acceptable_percent) * total


def meets_corruption_threshold(total, bad, threshold_percent):
    """Return True when proven corruption is at or above the configured percentage."""
    total = max(0, int(total or 0))
    bad = max(0, int(bad or 0))
    threshold_percent = int(threshold_percent)
    return total > 0 and bad > 0 and bad * 100 >= threshold_percent * total


def corruption_action(total, bad, corrupt_files="delete", corrupt_folders="all", folder_threshold=100):
    """Return the top-level action authorized by the independent corruption policies.

    Folder decisions are made from the original pre-mutation snapshot.  A folder
    action always takes precedence.  Individual corrupt-file handling is considered
    only when the logical-show folder is retained.
    """
    total = max(0, int(total or 0))
    bad = max(0, int(bad or 0))
    corrupt_files = str(corrupt_files or "delete").strip().lower()
    corrupt_folders = str(corrupt_folders or "all").strip().lower()
    folder_threshold = int(folder_threshold)

    if bad <= 0:
        return "none"
    if corrupt_folders == "all" and total > 0 and bad >= total:
        return "trash_folder_all_corrupt"
    if corrupt_folders == "threshold" and meets_corruption_threshold(total, bad, folder_threshold):
        return "trash_folder_threshold"
    if corrupt_files == "delete":
        return "trash_corrupt_files"
    return "report_only"


def qualifying_corrupt_music_dirs(group, audio_files, bad_files, corrupt_folders, folder_threshold):
    """Return direct music directories authorized for folder-level Trash handling."""
    policy = str(corrupt_folders or "all").strip().lower()
    if policy == "never":
        return []

    bad_keys = {_norm(path) for path in bad_files}
    directories = list(group.get("music_dirs") or [])
    if not directories and group.get("main_dir_path"):
        directories = [group.get("main_dir_path")]

    result = []
    seen = set()
    for directory in directories:
        directory = os.path.normpath(str(directory or ""))
        if not directory:
            continue
        directory_key = _norm(directory)
        if directory_key in seen:
            continue
        seen.add(directory_key)
        direct_audio = [path for path in audio_files if _norm(os.path.dirname(path)) == directory_key]
        if not direct_audio:
            continue
        bad_count = sum(1 for path in direct_audio if _norm(path) in bad_keys)
        if bad_count <= 0:
            continue
        if policy == "all" and bad_count == len(direct_audio):
            result.append(directory)
        elif policy == "threshold" and meets_corruption_threshold(len(direct_audio), bad_count, folder_threshold):
            result.append(directory)
    return sorted(result, key=str.lower)


# --- Windows fail-closed Recycle Bin implementation -----------------------
# IFileOperation is used instead of deprecated SHFileOperationW.  The
# FOFX_RECYCLEONDELETE flag explicitly requests recycling rather than permanent
# deletion.  Any COM failure/abort is raised; TLO never falls back to DeleteFile,
# rmtree, or a permanent shell delete on this path.

class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_text(cls, text):
        value = uuid.UUID(str(text))
        raw = value.bytes_le
        obj = cls()
        obj.Data1 = int.from_bytes(raw[0:4], "little")
        obj.Data2 = int.from_bytes(raw[4:6], "little")
        obj.Data3 = int.from_bytes(raw[6:8], "little")
        obj.Data4[:] = raw[8:16]
        return obj


def _failed_hresult(value):
    return int(value) < 0


def _com_method(ptr, index, restype, *argtypes):
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    address = vtable[index]
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(address)


def _trash_windows(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    HRESULT = ctypes.c_long
    DWORD = ctypes.c_uint32
    BOOL = ctypes.c_int
    LPVOID = ctypes.c_void_p

    CLSID_FileOperation = _GUID.from_text("3ad05575-8857-4850-9277-11b85bdb8e09")
    IID_IFileOperation = _GUID.from_text("947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8")
    IID_IShellItem = _GUID.from_text("43826d1e-e718-42ee-bc55-a1e261c37bfe")

    COINIT_APARTMENTTHREADED = 0x2
    CLSCTX_INPROC_SERVER = 0x1
    FOF_NOERRORUI = 0x0400
    FOFX_RECYCLEONDELETE = 0x00080000
    FOFX_EARLYFAILURE = 0x00100000

    ole32.CoInitializeEx.argtypes = [LPVOID, DWORD]
    ole32.CoInitializeEx.restype = HRESULT
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(_GUID), LPVOID, DWORD, ctypes.POINTER(_GUID), ctypes.POINTER(LPVOID)
    ]
    ole32.CoCreateInstance.restype = HRESULT
    shell32.SHCreateItemFromParsingName.argtypes = [
        ctypes.c_wchar_p, LPVOID, ctypes.POINTER(_GUID), ctypes.POINTER(LPVOID)
    ]
    shell32.SHCreateItemFromParsingName.restype = HRESULT

    init_hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    should_uninitialize = init_hr in (0, 1)  # S_OK / S_FALSE
    # RPC_E_CHANGED_MODE means COM is already initialized differently.  COM can
    # still be used on this thread, so do not fail solely for that condition.
    if _failed_hresult(init_hr) and (int(init_hr) & 0xFFFFFFFF) != 0x80010106:
        raise OSError(f"CoInitializeEx failed (0x{int(init_hr) & 0xFFFFFFFF:08X})")

    file_op = LPVOID()
    item = LPVOID()
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_FileOperation), None, CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IFileOperation), ctypes.byref(file_op),
        )
        if _failed_hresult(hr) or not file_op:
            raise OSError(f"IFileOperation creation failed (0x{int(hr) & 0xFFFFFFFF:08X})")

        hr = shell32.SHCreateItemFromParsingName(
            str(path), None, ctypes.byref(IID_IShellItem), ctypes.byref(item)
        )
        if _failed_hresult(hr) or not item:
            raise OSError(f"Shell item creation failed (0x{int(hr) & 0xFFFFFFFF:08X})")

        set_flags = _com_method(file_op, 5, HRESULT, DWORD)
        delete_item = _com_method(file_op, 18, HRESULT, LPVOID, LPVOID)
        perform = _com_method(file_op, 21, HRESULT)
        get_aborted = _com_method(file_op, 22, HRESULT, ctypes.POINTER(BOOL))

        flags = FOF_NOERRORUI | FOFX_RECYCLEONDELETE | FOFX_EARLYFAILURE
        hr = set_flags(file_op, flags)
        if _failed_hresult(hr):
            raise OSError(f"IFileOperation SetOperationFlags failed (0x{int(hr) & 0xFFFFFFFF:08X})")
        hr = delete_item(file_op, item, None)
        if _failed_hresult(hr):
            raise OSError(f"IFileOperation DeleteItem failed (0x{int(hr) & 0xFFFFFFFF:08X})")
        hr = perform(file_op)
        if _failed_hresult(hr):
            raise OSError(f"Recycle Bin operation failed (0x{int(hr) & 0xFFFFFFFF:08X})")
        aborted = BOOL(0)
        hr = get_aborted(file_op, ctypes.byref(aborted))
        if _failed_hresult(hr) or aborted.value:
            raise OSError("Recycle Bin operation was aborted")
        if os.path.exists(path):
            raise OSError("Recycle Bin operation reported success but the source still exists")
    finally:
        for ptr in (item, file_op):
            if ptr:
                try:
                    _com_method(ptr, 2, ctypes.c_ulong)(ptr)
                except Exception:
                    pass
        if should_uninitialize:
            ole32.CoUninitialize()


def move_to_trash(path):
    path = os.path.abspath(path)
    if sys.platform.startswith("win"):
        return _trash_windows(path)
    if sys.platform == "darwin":
        script = (
            'on run argv\n'
            'tell application "Finder" to delete POSIX file (item 1 of argv)\n'
            'end run'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script, path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=TRASH_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise OSError(f"Trash operation timed out for {path}") from exc
        if os.path.exists(path):
            raise OSError("Trash operation reported success but the source still exists")
        return
    try:
        subprocess.run(
            ["gio", "trash", "--", path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TRASH_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise OSError(f"Trash operation timed out for {path}") from exc
    if os.path.exists(path):
        raise OSError("Trash operation reported success but the source still exists")

@dataclass
class CorruptionAssessment:
    """Read-only corruption decision for one logical show before mutation."""
    audio_files: list[str] = field(default_factory=list)
    corrupt_files: list[str] = field(default_factory=list)
    unverifiable_details: list[tuple[str, str]] = field(default_factory=list)
    action: str = "none"
    corruption_percent: float = 0.0
    corrupt_files_policy: str = "delete"
    corrupt_folders_policy: str = "all"
    folder_threshold: int = 100
    folder_candidates: list[str] = field(default_factory=list)

    @property
    def unverifiable(self):
        return bool(self.unverifiable_details)


@dataclass
class CorruptionOutcome:
    """Mutation result returned to the inventory orchestrator."""
    assessment: CorruptionAssessment
    show_removed: bool = False
    whole_folder_trash_failed: bool = False
    trashed_dirs: list[str] = field(default_factory=list)
    trashed_files: list[str] = field(default_factory=list)
    unexpected_error: str = ""

    @property
    def unverifiable(self):
        return self.assessment.unverifiable


def assess_group_corruption(group, corrupt_files="delete", corrupt_folders="all", folder_threshold=100):
    """Return a deterministic pre-mutation corruption assessment.

    The original audio snapshot is authoritative for both folder and file policy
    decisions.  Any inspection/validator failure makes the logical show
    unverifiable and suppresses all corruption-driven mutation.
    """
    corrupt_files = str(corrupt_files or "delete").strip().lower()
    corrupt_folders = str(corrupt_folders or "all").strip().lower()
    folder_threshold = int(folder_threshold)
    audio_files, snapshot_errors = group_audio_snapshot(group)
    corrupt_paths, validator_errors = classify_audio_paths(audio_files)
    unverifiable_details = list(snapshot_errors) + list(validator_errors)
    action = "none"
    folder_candidates = []
    if not unverifiable_details:
        action = corruption_action(
            len(audio_files), len(corrupt_paths), corrupt_files, corrupt_folders, folder_threshold
        )
        if corrupt_paths and action not in {"trash_folder_all_corrupt", "trash_folder_threshold"}:
            folder_candidates = qualifying_corrupt_music_dirs(
                group, audio_files, corrupt_paths, corrupt_folders, folder_threshold
            )
    percent = (100.0 * len(corrupt_paths) / len(audio_files)) if audio_files else 0.0
    return CorruptionAssessment(
        audio_files=list(audio_files),
        corrupt_files=list(corrupt_paths),
        unverifiable_details=list(unverifiable_details),
        action=action,
        corruption_percent=percent,
        corrupt_files_policy=corrupt_files,
        corrupt_folders_policy=corrupt_folders,
        folder_threshold=folder_threshold,
        folder_candidates=list(folder_candidates),
    )


def _path_is_under(path_name, directory):
    try:
        return os.path.commonpath([os.path.abspath(path_name), os.path.abspath(directory)]) == os.path.abspath(directory)
    except (OSError, ValueError):
        return False


def _prune_group_after_corruption_trash(group, record, trashed_dirs, trashed_files):
    """Keep carried group/record paths consistent with successful Trash moves."""
    if not trashed_dirs and not trashed_files:
        return
    trashed_file_keys = {_norm(path) for path in trashed_files}

    def keep_path(path_name):
        normalized = os.path.normpath(str(path_name or ""))
        if not normalized or _norm(normalized) in trashed_file_keys:
            return False
        return not any(_path_is_under(normalized, directory) for directory in trashed_dirs)

    group["music_dirs"] = [path for path in (group.get("music_dirs", []) or []) if keep_path(path)]
    for key in ("music_files", "music_sample_files", "setlist_files", "txt_files"):
        group[key] = [path for path in (group.get(key, []) or []) if keep_path(path)]
    if group.get("setlist_file") and not keep_path(group.get("setlist_file")):
        group["setlist_file"] = next((path for path in group.get("setlist_files", []) if os.path.isfile(path)), "")

    remaining_audio = group_audio_files(group)
    group["music_file_count"] = len(remaining_audio)
    record.music_dirs = list(group.get("music_dirs", []) or [])
    record.music_file_count = len(remaining_audio)
    record.setlist_files = list(group.get("setlist_files", []) or [])
    if record.setlist_file and not keep_path(record.setlist_file):
        record.setlist_file = group.get("setlist_file", "")


def apply_corruption_assessment(config, group, record, assessment):
    """Apply one already-computed assessment and return a structured outcome.

    Folder decisions always use the original pre-mutation snapshot.  If the
    logical-show folder is retained, qualifying direct music folders are handled
    next; the individual-file policy is applied only to corrupt files that remain.
    """
    outcome = CorruptionOutcome(assessment=assessment)
    audio_files = list(assessment.audio_files)
    bad_files = list(assessment.corrupt_files)
    percent = assessment.corruption_percent
    file_policy = assessment.corrupt_files_policy
    folder_policy = assessment.corrupt_folders_policy
    threshold = assessment.folder_threshold

    if assessment.unverifiable:
        detail_text = "; ".join(f"{path}: {detail}" for path, detail in assessment.unverifiable_details[:8])
        if len(assessment.unverifiable_details) > 8:
            detail_text += f"; ... {len(assessment.unverifiable_details) - 8} more"
        config.logs.conflicts(
            "CORRUPTION_UNVERIFIABLE: %s | proven_corrupt=%s files_seen=%s | no corruption-driven Trash action; mutation steps skipped | %s",
            record.main_dir_path, len(bad_files), len(audio_files), detail_text,
        )
        config.logs.tag(
            "CORRUPTION_UNVERIFIABLE: %s | no Trash/rename/tag/copy-delete/SHN mutation | %s",
            record.main_dir_path, detail_text,
        )
        return outcome

    if assessment.action in {"trash_folder_all_corrupt", "trash_folder_threshold"}:
        reason = (
            "100% of logical-show audio is corrupt"
            if assessment.action == "trash_folder_all_corrupt"
            else f"logical-show corruption {percent:.2f}% is at or above folder threshold {threshold}%"
        )
        try:
            move_to_trash(record.main_dir_path)
        except Exception as exc:
            outcome.whole_folder_trash_failed = True
            config.logs.conflicts(
                "CORRUPTION_REMOVAL_FAILED: %s | files=%s corrupt=%s percent=%.2f folder_policy=%s folder_threshold=%s file_policy=%s reason=%s | %s",
                record.main_dir_path, len(audio_files), len(bad_files), percent, folder_policy, threshold, file_policy, reason, exc,
            )
        else:
            config.logs.conflicts(
                "REMOVED_CORRUPTION: %s | files=%s corrupt=%s corruption_percent=%.2f folder_policy=%s folder_threshold=%s file_policy=%s | %s | moved to Trash/Recycle Bin and omitted from inventory",
                record.main_dir_path, len(audio_files), len(bad_files), percent, folder_policy, threshold, file_policy, reason,
            )
            config.logs.tag(
                "REMOVED_CORRUPTION: %s | files=%s corrupt=%s corruption_percent=%.2f folder_policy=%s folder_threshold=%s file_policy=%s | %s",
                record.main_dir_path, len(audio_files), len(bad_files), percent, folder_policy, threshold, file_policy, reason,
            )
            config.current_search_corruption_groups_removed = int(getattr(config, "current_search_corruption_groups_removed", 0) or 0) + 1
            config.current_search_corruption_removed_paths = list(getattr(config, "current_search_corruption_removed_paths", []) or []) + [os.path.normpath(record.main_dir_path)]
            outcome.show_removed = True
            return outcome

    main_key = _norm(record.main_dir_path)
    music_dirs = [os.path.normpath(path) for path in (group.get("music_dirs", []) or []) if path]

    # A failed whole-show folder move does not silently change the user's file
    # policy.  Folder candidates are skipped for the failed root; independent
    # file deletion still runs below only when corrupt_files_policy == delete.
    for bad_dir in assessment.folder_candidates:
        bad_dir_key = _norm(bad_dir)
        if outcome.whole_folder_trash_failed and bad_dir_key == main_key:
            continue
        contains_other_music_dir = any(
            _norm(other_dir) != bad_dir_key and _path_is_under(other_dir, bad_dir)
            for other_dir in music_dirs
        )
        if contains_other_music_dir:
            config.logs.conflicts(
                "CORRUPT_FOLDER_RETAINED_NESTED: %s | logical_show=%s | folder_policy=%s | contains another inventoried music directory",
                bad_dir, record.main_dir_path, folder_policy,
            )
            continue
        try:
            move_to_trash(bad_dir)
        except Exception as exc:
            config.logs.conflicts(
                "CORRUPT_FOLDER_TRASH_FAILED: %s | logical_show=%s | folder_policy=%s folder_threshold=%s | %s",
                bad_dir, record.main_dir_path, folder_policy, threshold, exc,
            )
            config.logs.tag("CORRUPT_FOLDER_TRASH_FAILED: %s | %s", bad_dir, exc)
        else:
            outcome.trashed_dirs.append(os.path.normpath(bad_dir))
            config.logs.conflicts(
                "TRASHED_CORRUPT_FOLDER: %s | logical_show=%s | folder_policy=%s folder_threshold=%s",
                bad_dir, record.main_dir_path, folder_policy, threshold,
            )
            config.logs.tag("TRASHED_CORRUPT_FOLDER: %s", bad_dir)

    remaining_bad = [
        path for path in bad_files
        if not any(_path_is_under(path, directory) for directory in outcome.trashed_dirs)
    ]

    if file_policy == "delete":
        for bad_path in remaining_bad:
            try:
                move_to_trash(bad_path)
            except Exception as exc:
                config.logs.conflicts("CORRUPT_FILE_TRASH_FAILED: %s | %s", bad_path, exc)
                config.logs.tag("CORRUPT_FILE_TRASH_FAILED: %s | %s", bad_path, exc)
            else:
                outcome.trashed_files.append(os.path.normpath(bad_path))
                config.logs.conflicts(
                    "TRASHED_CORRUPT_FILE: %s | logical_show=%s | corruption_percent=%.2f file_policy=delete folder_policy=%s folder_threshold=%s",
                    bad_path, record.main_dir_path, percent, folder_policy, threshold,
                )
                config.logs.tag("TRASHED_CORRUPT_FILE: %s", bad_path)
    elif remaining_bad:
        config.logs.conflicts(
            "CORRUPTION_REPORTED: %s | corrupt_files_retained=%s files_seen=%s corruption_percent=%.2f file_policy=keep folder_policy=%s folder_threshold=%s",
            record.main_dir_path, len(remaining_bad), len(audio_files), percent, folder_policy, threshold,
        )
        config.logs.tag(
            "CORRUPTION_REPORTED: %s | %s corrupt file(s) retained by policy",
            record.main_dir_path, len(remaining_bad),
        )

    _prune_group_after_corruption_trash(group, record, outcome.trashed_dirs, outcome.trashed_files)
    return outcome


def handle_group_corruption(config, group, record, corrupt_files="delete", corrupt_folders="all", folder_threshold=100):
    """Fail-closed assessment + mutation wrapper for inventory orchestration."""
    try:
        assessment = assess_group_corruption(
            group, corrupt_files=corrupt_files, corrupt_folders=corrupt_folders, folder_threshold=folder_threshold
        )
        return apply_corruption_assessment(config, group, record, assessment)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        assessment = CorruptionAssessment(
            audio_files=[], corrupt_files=[],
            unverifiable_details=[(record.main_dir_path, detail)],
            action="none", corruption_percent=0.0,
            corrupt_files_policy=str(corrupt_files or "delete"),
            corrupt_folders_policy=str(corrupt_folders or "all"),
            folder_threshold=int(folder_threshold), folder_candidates=[],
        )
        config.logs.conflicts(
            "CORRUPTION_CHECK_FAILED_UNVERIFIABLE: %s | no corruption-driven Trash action; mutation steps skipped | %s",
            record.main_dir_path, exc,
        )
        return CorruptionOutcome(assessment=assessment, unexpected_error=detail)

