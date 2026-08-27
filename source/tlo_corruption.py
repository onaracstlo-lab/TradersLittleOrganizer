"""Pre-mutation audio corruption threshold handling for TLO."""
from __future__ import annotations

__version__ = "v407"

import ctypes
import os
import subprocess
import sys
import uuid
from pathlib import Path

from mutagen import File as MutagenFile, MutagenError

try:
    from mutagen.flac import FLAC
except Exception:
    FLAC = None

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


def classify_audio_paths(paths):
    """Return (proven_corrupt_paths, unverifiable_errors).

    Parse/format failures are corruption.  Filesystem/resource/infrastructure
    failures are unverifiable and must never be promoted to corruption merely
    because the validator could not read the file.
    """
    bad = []
    unverifiable = []
    for path in list(paths or []):
        try:
            if str(path).lower().endswith(".flac") and FLAC is not None:
                FLAC(path)
            else:
                audio = MutagenFile(path)
                if audio is None:
                    raise ValueError("unrecognized audio format")
        except (PermissionError, OSError, MemoryError) as exc:
            unverifiable.append((path, f"{type(exc).__name__}: {exc}"))
        except (MutagenError, ValueError) as exc:
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
    return total > 0 and bad * 100 > int(acceptable_percent) * total


def corruption_action(total, bad, acceptable_percent):
    """Return the Trash/Recycle action for *proven* corruption.

    Build 398's policy remains in force: an all-proven-corrupt logical show is
    removed regardless of acceptable_corruption_percent.  Build 400 changes
    classification, not that policy: unverifiable files are never included in
    ``bad`` and callers must not trash anything when verification is incomplete.
    """
    total = max(0, int(total or 0))
    bad = max(0, int(bad or 0))
    if total > 0 and bad >= total:
        return "trash_folder_all_corrupt"
    if exceeds_threshold(total, bad, acceptable_percent):
        return "trash_folder_threshold"
    if bad > 0:
        return "trash_corrupt_files"
    return "none"


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
        subprocess.run(
            ["osascript", "-e", script, path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return
    subprocess.run(
        ["gio", "trash", path],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
