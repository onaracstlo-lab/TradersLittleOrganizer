"""Pre-mutation audio corruption threshold handling for TLO."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import contextlib
import copy
import ctypes
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from mutagen import File as MutagenFile, MutagenError
from mutagen.id3 import ID3, TXXX
from mutagen.mp4 import MP4FreeForm, MP4Tags

from tlo_diagnostics import debug_suppressed_exception
from tlo_ffmpeg import bundled_ffmpeg_executable
from tlo_runtime_control import is_cancel_requested

try:
    from mutagen.flac import FLAC
except Exception:
    FLAC = None

try:
    from mutagen.mp3 import MP3
except Exception:
    MP3 = None

TRASH_SUBPROCESS_TIMEOUT_SECONDS = 60.0
DEEP_AUDIO_CHECK_TIMEOUT_SECONDS = 1800.0

MEDIA_EXTENSIONS = {
    ".flac", ".mp3", ".m4a", ".mp4", ".aac", ".alac", ".ogg", ".oga", ".opus", ".wav",
    ".aif", ".aiff", ".ape", ".wv", ".tta", ".wma",
}

# Match the formats the tagger currently attempts to mutate.  Corruption
# validation only performs the write round-trip when a real tagging mode is
# active; non-tagging inventory remains header/read validation only.
TAG_WRITE_CHECK_EXTENSIONS = {
    ".flac", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus",
    ".aiff", ".aif", ".ape", ".wv", ".alac",
}

_TAG_TEST_KEY = "TLO_CORRUPTION_TEST"
_TAG_TEST_ID3_DESC = "TLO_CORRUPTION_TEST"
_TAG_TEST_MP4_KEY = "----:com.apple.iTunes:TLO_CORRUPTION_TEST"
_TAG_MISSING = object()


class _TagWriteRestoreError(RuntimeError):
    """The temporary tag probe could not be restored/verified safely."""


class _DeepAudioCheckUnverifiable(RuntimeError):
    """The deep decoder could not produce a trustworthy corruption result."""


class _DeepAudioDecodeError(ValueError):
    """The complete audio stream failed to decode."""


def _tag_probe_style(tags):
    if isinstance(tags, ID3):
        return "id3"
    if isinstance(tags, MP4Tags):
        return "mp4"
    return "mapping"


def _snapshot_probe_value(tags, style):
    if style == "id3":
        return [
            copy.deepcopy(frame)
            for frame in tags.getall("TXXX")
            if str(getattr(frame, "desc", "")) == _TAG_TEST_ID3_DESC
        ]
    key = _TAG_TEST_MP4_KEY if style == "mp4" else _TAG_TEST_KEY
    if key not in tags:
        return _TAG_MISSING
    return copy.deepcopy(tags[key])


def _remove_id3_probe_frames(tags):
    for frame in list(tags.getall("TXXX")):
        if str(getattr(frame, "desc", "")) == _TAG_TEST_ID3_DESC:
            tags.delall(frame.HashKey)


def _write_probe_value(tags, style, marker):
    if style == "id3":
        _remove_id3_probe_frames(tags)
        tags.add(TXXX(encoding=3, desc=_TAG_TEST_ID3_DESC, text=[marker]))
        return
    if style == "mp4":
        tags[_TAG_TEST_MP4_KEY] = [MP4FreeForm(marker.encode("utf-8"))]
        return
    # Vorbis comments and APEv2 accept an application-specific text key.
    tags[_TAG_TEST_KEY] = [marker]


def _probe_value_matches(tags, style, marker):
    if tags is None:
        return False
    if style == "id3":
        values = [
            str(value)
            for frame in tags.getall("TXXX")
            if str(getattr(frame, "desc", "")) == _TAG_TEST_ID3_DESC
            for value in getattr(frame, "text", [])
        ]
        return values == [marker]
    key = _TAG_TEST_MP4_KEY if style == "mp4" else _TAG_TEST_KEY
    values = tags.get(key)
    if style == "mp4":
        return bool(values) and len(values) == 1 and bytes(values[0]).decode("utf-8") == marker
    if values is None:
        return False
    if isinstance(values, (list, tuple)):
        return [str(value) for value in values] == [marker]
    return str(values) == marker


def _restore_probe_value(tags, style, original):
    if style == "id3":
        _remove_id3_probe_frames(tags)
        for frame in original:
            tags.add(copy.deepcopy(frame))
        return
    key = _TAG_TEST_MP4_KEY if style == "mp4" else _TAG_TEST_KEY
    if original is _TAG_MISSING:
        try:
            del tags[key]
        except KeyError:
            pass
    else:
        tags[key] = copy.deepcopy(original)


def _probe_value_restored(tags, style, original):
    if style == "id3":
        current = [
            frame
            for frame in tags.getall("TXXX")
            if str(getattr(frame, "desc", "")) == _TAG_TEST_ID3_DESC
        ] if tags is not None else []
        return [repr(frame) for frame in current] == [repr(frame) for frame in original]
    key = _TAG_TEST_MP4_KEY if style == "mp4" else _TAG_TEST_KEY
    if original is _TAG_MISSING:
        return tags is None or key not in tags
    return tags is not None and key in tags and repr(tags[key]) == repr(original)


def _validate_tag_write_round_trip(path):
    """Write, read back, restore, and verify one temporary metadata value.

    The source file is restored before this function returns or raises.  The
    existing value of TLO's private probe tag is preserved exactly at the
    metadata-object level.  If the file originally had no tag container, the
    temporary container is removed after the probe.  mtime/atime are also
    restored on a best-effort basis after the metadata round trip.
    """
    before_stat = os.stat(path)
    audio = MutagenFile(path)
    if audio is None:
        raise ValueError("mutagen could not identify audio type for tag-write validation")
    had_tags = getattr(audio, "tags", None) is not None
    if not had_tags:
        audio.add_tags()
    tags = getattr(audio, "tags", None)
    if tags is None:
        raise ValueError("audio type did not provide a writable tag container")
    style = _tag_probe_style(tags)
    original = _snapshot_probe_value(tags, style)
    marker = "TLO-tag-write-check-" + uuid.uuid4().hex
    write_error = None
    restore_error = None
    try:
        _write_probe_value(tags, style, marker)
        audio.save()
        verify = MutagenFile(path)
        if verify is None or not _probe_value_matches(getattr(verify, "tags", None), style, marker):
            raise ValueError("temporary tag test value did not persist")
    except Exception as exc:
        write_error = exc
    finally:
        try:
            restored = MutagenFile(path)
            if restored is None:
                raise ValueError("audio type could not be reopened for tag restoration")
            if not had_tags:
                # Remove the tag container created solely for the probe.
                restored.delete()
                verify_restored = MutagenFile(path)
                if verify_restored is None or getattr(verify_restored, "tags", None) is not None:
                    raise ValueError("temporary tag container was not removed")
            else:
                if getattr(restored, "tags", None) is None:
                    restored.add_tags()
                _restore_probe_value(restored.tags, style, original)
                restored.save()
                verify_restored = MutagenFile(path)
                if verify_restored is None or not _probe_value_restored(
                    getattr(verify_restored, "tags", None), style, original
                ):
                    raise ValueError("original tag value was not restored")
        except Exception as exc:
            restore_error = exc
        finally:
            try:
                os.utime(path, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
            except Exception as exc:
                # Timestamp restoration is cosmetic; the tag-content restoration
                # above is the safety boundary.  Record only in debug diagnostics.
                debug_suppressed_exception(__name__, exc)

    if restore_error is not None:
        raise _TagWriteRestoreError(f"temporary tag restoration failed: {restore_error}") from restore_error
    if write_error is not None:
        raise write_error



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


def _hidden_windows_subprocess_kwargs():
    """Avoid opening an ffmpeg console window on native Windows."""
    if os.name != "nt":
        return {}
    creation_flag = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
    return {"creationflags": creation_flag} if creation_flag else {}


def _ffmpeg_failure_is_unverifiable(stderr_text):
    lowered = str(stderr_text or "").casefold()
    markers = (
        "permission denied",
        "operation not permitted",
        "no such file or directory",
        "input/output error",
        "device or resource busy",
        "too many open files",
        "stale file handle",
        "transport endpoint is not connected",
    )
    return any(marker in lowered for marker in markers)


def _flac_declared_sample_total(path):
    """Return (samples, sample_rate), or None if FLAC duration is unspecified.

    FLAC STREAMINFO's total_samples is authoritative for a fully present FLAC
    stream, but zero explicitly means unknown.  Unknown is *unverifiable*, not
    evidence that the source is corrupt or proof it is intact.
    """
    if FLAC is None:
        return None
    try:
        info = FLAC(path).info
        samples = int(getattr(info, "total_samples", 0) or 0)
        sample_rate = int(getattr(info, "sample_rate", 0) or 0)
    except (OSError, MutagenError, ValueError, TypeError, AttributeError):
        return None
    if samples <= 0 or sample_rate <= 0:
        return None
    return samples, sample_rate


def _flac_decoded_sample_total(framehash_file, sample_rate):
    """Count actual PCM samples from FFmpeg's framehash muxer, not its exit code.

    framehash produces one short record per decoded PCM frame; these records
    have timestamps/durations in the declared 1/sample_rate time base.  A
    temporary file bounds process pipe memory and is never put in the source
    collection.  Malformed/oversized output is unverifiable, not corruption.
    """
    try:
        framehash_file.seek(0, os.SEEK_END)
        if framehash_file.tell() > 64 * 1024 * 1024:
            return None
        framehash_file.seek(0)
        timebase_ok = False
        codec_ok = False
        total = 0
        frames = 0
        for raw in framehash_file:
            if len(raw) > 4096:
                return None
            line = raw.decode("ascii", errors="strict").strip()
            if line.startswith("#tb 0:"):
                timebase_ok = line.split(":", 1)[1].strip() == f"1/{sample_rate}"
            elif line.startswith("#codec_id 0:"):
                codec_ok = line.split(":", 1)[1].strip() == "pcm_s16le"
            elif line and not line.startswith("#"):
                fields = [field.strip() for field in line.split(",")]
                if len(fields) != 6 or fields[0] != "0":
                    return None
                duration = int(fields[3])
                if duration <= 0:
                    return None
                total += duration
                frames += 1
                if frames > 500000 or total > (1 << 56):
                    return None
        if not timebase_ok or not codec_ok or not frames:
            return None
        return total
    except (OSError, UnicodeError, ValueError, OverflowError):
        return None


def _deep_audio_stream_status(
    path,
    *,
    ffmpeg_executable=None,
    popen_factory=subprocess.Popen,
    timeout_seconds=DEEP_AUDIO_CHECK_TIMEOUT_SECONDS,
    cancel_check=is_cancel_requested,
):
    """Return True for verified decode, False for corruption, or None if unknown.

    FLAC additionally requires exact agreement between decoded PCM samples and
    the declared STREAMINFO total.  FFmpeg's successful exit alone can accept
    a truncated file whose last available frame happens to be complete.
    """
    executable = str(ffmpeg_executable or bundled_ffmpeg_executable() or "").strip()
    if not executable:
        return None
    normalized = os.path.abspath(os.path.normpath(str(path or "")))
    is_flac = Path(normalized).suffix.casefold() == ".flac"
    try:
        before_stat = os.stat(normalized) if is_flac else None
        declared = _flac_declared_sample_total(normalized) if is_flac else None
    except (OSError, MemoryError):
        return None
    if is_flac and declared is None:
        return None

    command = [
        executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
        "-protocol_whitelist", "file", "-i", normalized, "-map", "0:a:0",
    ]
    # framemd5 records per-frame decoded sample counts in a local output file,
    # without allocating or writing a full PCM copy of the recording.
    if is_flac:
        command += ["-c:a", "pcm_s16le", "-f", "framemd5", "-"]
    else:
        command += ["-f", "null", "-"]

    process = None
    try:
        with (tempfile.TemporaryFile(mode="w+b") if is_flac else contextlib.nullcontext(None)) as sample_records:
            process = popen_factory(
                command, stdin=subprocess.DEVNULL,
                stdout=sample_records if is_flac else subprocess.DEVNULL,
                stderr=subprocess.PIPE, text=True,
                env={**os.environ, "LC_ALL": "C"},
                **_hidden_windows_subprocess_kwargs(),
            )
            deadline = time.monotonic() + max(1.0, float(timeout_seconds))
            while process.poll() is None:
                if cancel_check and cancel_check():
                    try:
                        process.kill()
                    finally:
                        process.communicate()
                    return None
                if time.monotonic() >= deadline:
                    try:
                        process.kill()
                    finally:
                        process.communicate()
                    return None
                time.sleep(0.05)
            _stdout, stderr = process.communicate()
            if process.returncode != 0:
                return None if _ffmpeg_failure_is_unverifiable(stderr) else False
            if not is_flac:
                return True
            after_stat = os.stat(normalized)
            if (after_stat.st_size, after_stat.st_mtime_ns) != (before_stat.st_size, before_stat.st_mtime_ns):
                return None
            decoded = _flac_decoded_sample_total(sample_records, declared[1])
            if decoded is None:
                return None
            return decoded == declared[0]
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.kill()
        raise
    except (OSError, MemoryError):
        if process is not None and process.poll() is None:
            process.kill()
        return None
    except Exception as exc:
        if process is not None and process.poll() is None:
            process.kill()
        debug_suppressed_exception("deep audio corruption validation", exc)
        return None


def classify_audio_paths(paths, *, check_tag_write=False, deep_audio_check=False):
    """Return (proven_corrupt_paths, unverifiable_errors).

    Header/format validation always runs.  When ``check_tag_write`` is true,
    TLO also proves that taggable audio can accept and restore a temporary tag
    value.  When ``deep_audio_check`` is true, TLO additionally decodes the
    complete audio stream with its bundled ffmpeg.  Header, tag-format/write,
    or full-stream decode failures are corruption; filesystem/resource/validator
    failures remain unverifiable and suppress corruption-driven mutation.
    """
    bad = []
    unverifiable = []
    for path in list(paths or []):
        try:
            _preflight_audio_read(path)
            lowered = str(path).lower()
            if lowered.endswith(".flac") and FLAC is not None:
                FLAC(path)
            elif lowered.endswith(".mp3") and MP3 is not None:
                MP3(path)
            else:
                audio = MutagenFile(path)
                if audio is None:
                    raise ValueError("unrecognized audio format")
            if check_tag_write and Path(path).suffix.lower() in TAG_WRITE_CHECK_EXTENSIONS:
                _validate_tag_write_round_trip(path)
            if deep_audio_check:
                stream_status = _deep_audio_stream_status(path)
                if stream_status is None:
                    raise _DeepAudioCheckUnverifiable(
                        "full-stream decoder unavailable, cancelled, timed out, or encountered an access/infrastructure failure"
                    )
                if stream_status is False:
                    raise _DeepAudioDecodeError("full audio stream decode failed")
        except (_TagWriteRestoreError, _DeepAudioCheckUnverifiable) as exc:
            unverifiable.append((path, f"{type(exc).__name__}: {exc}"))
        except (PermissionError, OSError, MemoryError) as exc:
            unverifiable.append((path, f"{type(exc).__name__}: {exc}"))
        except (MutagenError, ValueError, TypeError, KeyError) as exc:
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
# A recycle request does not by itself establish that Windows can actually
# recycle the particular item.  Reject any situation in which that cannot be
# established conservatively, before invoking IFileOperation.  Never offer a
# permanent-delete fallback, including through a user confirmation prompt.

class _RecycleUnavailable(OSError):
    """Safe recycling was not positively established; retain the source."""


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64)]


def _recycle_candidate_size(path):
    """Bounded, non-following size walk; any unsafe path/error rejects recycling."""
    total = 0
    entries = 0
    if os.path.islink(path) or bool(getattr(os.path, "isjunction", lambda _p: False)(path)):
        raise _RecycleUnavailable("symlink/reparse path cannot be safely recycled")
    if os.path.isfile(path):
        return os.stat(path, follow_symlinks=False).st_size
    if not os.path.isdir(path):
        raise _RecycleUnavailable("Recycle Bin target is not a regular file/folder")
    if getattr(os.stat(path, follow_symlinks=False), "st_file_attributes", 0) & 0x400:
        raise _RecycleUnavailable("folder is a reparse point")
    for base, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            entries += 1
            if entries > 200000:
                raise _RecycleUnavailable("folder exceeds bounded recycling preflight")
            candidate = os.path.join(base, name)
            if os.path.islink(candidate) or bool(getattr(os.path, "isjunction", lambda _p: False)(candidate)):
                raise _RecycleUnavailable("folder contains a symlink/reparse entry")
            st = os.stat(candidate, follow_symlinks=False)
            if getattr(st, "st_file_attributes", 0) & 0x400:
                raise _RecycleUnavailable("folder contains a reparse point")
            if not os.path.isdir(candidate):
                total += st.st_size
    return total


def _windows_recycle_policy(root, volume_guid, size_bytes, recycled_bytes):
    """Require affirmative per-volume settings and no system/user no-recycle policy."""
    import winreg
    policy_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, policy_path) as key:
                value, _ = winreg.QueryValueEx(key, "NoRecycleFiles")
                if int(value) != 0:
                    raise _RecycleUnavailable("Recycle Bin disabled by Explorer policy")
        except FileNotFoundError:
            pass
    guid = str(volume_guid).strip().rstrip('\\')
    # Windows exposes volume names in the form \\?\Volume{GUID}\.
    marker = 'Volume{'
    i = guid.lower().find(marker.lower())
    if i < 0 or '}' not in guid[i:]:
        raise _RecycleUnavailable("volume GUID unavailable for Recycle Bin settings")
    key_name = guid[i + len('Volume'):guid.index('}', i) + 1]
    settings_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume" + key_name
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, settings_path) as key:
            nuke, _ = winreg.QueryValueEx(key, "NukeOnDelete")
            maximum_mb, _ = winreg.QueryValueEx(key, "MaxCapacity")
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise _RecycleUnavailable("per-volume Recycle Bin settings cannot be confirmed") from exc
    if int(nuke) != 0:
        raise _RecycleUnavailable("Recycle Bin is disabled for this volume")
    capacity = int(maximum_mb) * 1024 * 1024
    if capacity <= 0 or size_bytes + recycled_bytes >= capacity:
        raise _RecycleUnavailable("item exceeds available Recycle Bin quota")


def _windows_recycle_preflight(path):
    """Conservative preflight; failure is Keep-and-report, never permanent delete.

    Supports native Windows fixed local NTFS drives only.  SHQueryRecycleBin is
    necessary but not sufficient; also check Explorer settings, policy, and
    capacity before asking the Shell to recycle a file or directory.
    """
    if os.name != 'nt':
        raise _RecycleUnavailable("native Windows Recycle Bin validation unavailable")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if path.startswith('\\\\') or path.startswith('\\\\?\\'):
        raise _RecycleUnavailable("UNC/device paths are not safely recyclable")
    kernel32 = ctypes.windll.kernel32
    shell32 = ctypes.windll.shell32
    root_buf = ctypes.create_unicode_buffer(32768)
    get_path = kernel32.GetVolumePathNameW
    get_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_path.restype = ctypes.c_int
    if not get_path(path, root_buf, len(root_buf)):
        raise _RecycleUnavailable("cannot identify local volume root")
    root = root_buf.value
    get_type = kernel32.GetDriveTypeW
    get_type.argtypes = [ctypes.c_wchar_p]
    get_type.restype = ctypes.c_uint32
    if get_type(root) != 3:  # DRIVE_FIXED; exclude network, removable, optical
        raise _RecycleUnavailable("Recycle Bin availability on non-fixed media is not proven")
    get_info = kernel32.GetVolumeInformationW
    get_info.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_wchar_p, ctypes.c_uint32]
    get_info.restype = ctypes.c_int
    fsbuf = ctypes.create_unicode_buffer(64)
    if not get_info(root, None, 0, None, None, None, fsbuf, len(fsbuf)) or fsbuf.value.upper() != 'NTFS':
        raise _RecycleUnavailable("Recycle Bin not validated for this filesystem")
    get_guid = kernel32.GetVolumeNameForVolumeMountPointW
    get_guid.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    get_guid.restype = ctypes.c_int
    guid = ctypes.create_unicode_buffer(100)
    if not get_guid(root, guid, len(guid)):
        raise _RecycleUnavailable("cannot identify Recycle Bin volume settings")
    rb = _SHQUERYRBINFO()
    rb.cbSize = ctypes.sizeof(rb)
    query = shell32.SHQueryRecycleBinW
    query.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(_SHQUERYRBINFO)]
    query.restype = ctypes.c_long
    hr = query(root, ctypes.byref(rb))
    if _failed_hresult(hr) or rb.i64Size < 0:
        raise _RecycleUnavailable("Recycle Bin query failed")
    size_bytes = _recycle_candidate_size(path)
    _windows_recycle_policy(root, guid.value, size_bytes, rb.i64Size)
    free = ctypes.c_uint64()
    get_free = kernel32.GetDiskFreeSpaceExW
    get_free.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint64),
                         ctypes.c_void_p, ctypes.c_void_p]
    get_free.restype = ctypes.c_int
    if not get_free(root, ctypes.byref(free), None, None) or free.value < 1024 * 1024:
        raise _RecycleUnavailable("insufficient free space to verify safe recycling")
    return root


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
    _windows_recycle_preflight(path)

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
    FOF_SILENT = 0x0004
    FOF_ALLOWUNDO = 0x0040
    FOFX_ADDUNDORECORD = 0x20000000
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

        flags = (FOF_NOERRORUI | FOF_SILENT | FOF_ALLOWUNDO | FOFX_ADDUNDORECORD
                 | FOFX_RECYCLEONDELETE | FOFX_EARLYFAILURE)
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
                except Exception as release_exc:
                    debug_suppressed_exception("Windows Recycle Bin COM release", release_exc)
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
                ["/usr/bin/osascript", "-e", script, path],
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
    gio = "/usr/bin/gio"
    try:
        subprocess.run(
            [gio, "trash", "--", path],
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


def assess_group_corruption(group, corrupt_files="delete", corrupt_folders="all", folder_threshold=100, *, check_tag_write=False, deep_audio_check=False):
    """Return a deterministic pre-mutation corruption assessment.

    The original audio snapshot is authoritative for both folder and file policy
    decisions.  Any inspection/validator failure makes the logical show
    unverifiable and suppresses all corruption-driven mutation.
    """
    corrupt_files = str(corrupt_files or "delete").strip().lower()
    corrupt_folders = str(corrupt_folders or "all").strip().lower()
    folder_threshold = int(folder_threshold)
    audio_files, snapshot_errors = group_audio_snapshot(group)
    if check_tag_write or deep_audio_check:
        corrupt_paths, validator_errors = classify_audio_paths(
            audio_files, check_tag_write=bool(check_tag_write), deep_audio_check=bool(deep_audio_check)
        )
    else:
        # Preserve the long-standing one-argument classifier boundary for ordinary
        # header-only callers and historical test fixtures.
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
            assessment.unverifiable_details.append((record.main_dir_path, f"Recycle Bin unavailable: {exc}"))
            return outcome
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
            assessment.unverifiable_details.append((bad_dir, f"Trash unavailable: {exc}"))
            _prune_group_after_corruption_trash(group, record, outcome.trashed_dirs, outcome.trashed_files)
            return outcome
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
                assessment.unverifiable_details.append((bad_path, f"Trash unavailable: {exc}"))
                _prune_group_after_corruption_trash(group, record, outcome.trashed_dirs, outcome.trashed_files)
                return outcome
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


def handle_group_corruption(config, group, record, corrupt_files="delete", corrupt_folders="all", folder_threshold=100, *, check_tag_write=False, deep_audio_check=False):
    """Fail-closed assessment + mutation wrapper for inventory orchestration."""
    try:
        assessment = assess_group_corruption(
            group, corrupt_files=corrupt_files, corrupt_folders=corrupt_folders, folder_threshold=folder_threshold,
            check_tag_write=bool(check_tag_write),
            deep_audio_check=bool(deep_audio_check),
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

