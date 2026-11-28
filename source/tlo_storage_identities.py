"""Persistent inventory-root identity, independent of labels and mount paths.

Existing text logs hold authoritative registration and operation evidence.
Numbered log headers carry self-contained snapshots; the durable folderOperations.log
keeps registrations after numbered logs are retired. The small root marker is
a fallback when hardware information is incomplete.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import ctypes
import copy
import json
import os
import platform
import plistlib
import posixpath
import re
import shutil
import subprocess
import tempfile
import uuid
from contextlib import closing
from datetime import datetime
from functools import lru_cache

from tlo_unc import unc_root
from tlo_volume_label import (
    resolve_volume_label, _running_on_wsl, _wsl_drive_letter_for_path,
    _trusted_native_powershell_executable, _hidden_windows_subprocess_kwargs,
)
from tlo_bootlist_volume_policy import (
    storage_path_without_drive, read_bootlist_rows, read_group_log_volume_rows,
    normalize_volume_label, normalize_path_for_compare, path_is_same_or_under,
)

MARKER = ".tlo-root-id.json"
REGISTRY = "storage-identities.json"  # read-only legacy migration input
JOURNAL = "folderOperations.log"
LEGACY_OPERATIONS = "folderOperationIdentities.sqlite"
IDENTITY_PREFIX = "# STORAGE_IDENTITY: "
OBSERVATION_PREFIX = "# STORAGE_OBSERVATION: "
ARCHIVED_PREFIX = "# STORAGE_ARCHIVED_IDENTITY: "
OPERATION_PREFIX = "# STORAGE_OPERATION: "
MIGRATED = "# STORAGE_LEGACY_MIGRATED: 1"
SCHEMA = 1


class StorageIdentityError(RuntimeError):
    pass


def _now():
    return datetime.now().isoformat(timespec="microseconds")


def _uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise StorageIdentityError("Invalid TLO storage identity. Use Manage Storage Identities.") from exc


def _atomic_json(path, data):
    fd, temp = tempfile.mkstemp(prefix=".tlo-id-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _journal_path(home):
    return os.path.join(home, "logs", JOURNAL)


def _signature(path):
    try:
        stat = os.stat(path)
        return stat.st_mtime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return None


def _minimal_hardware(data):
    """Keep only useful identification evidence and the present label/mount."""
    keys = ("disk_serial", "disk_unique_id", "partition_guid", "partition_offset",
            "partition_start_sector", "partition_size", "filesystem_uuid",
            "filesystem_serial", "label", "mount", "kind")
    result = {k: v for k, v in data.items() if k in keys and v not in (None, "")}
    # A GUID is the preferred partition ID. Offset/start and size are the
    # fallback only when the operating system cannot provide a GUID.
    if result.get("partition_guid"):
        for key in ("partition_offset", "partition_start_sector", "partition_size"):
            result.pop(key, None)
    return result


def _minimal_entry(item):
    entry = copy.deepcopy(item)
    entry["hardware"] = _minimal_hardware(entry.get("hardware", {}))
    for location in entry.get("previous_locations", []):
        location["hardware"] = _minimal_hardware(location.get("hardware", {}))
    return entry


def _encode(prefix, value):
    # JSON is single-line ASCII: metadata cannot forge a subsequent log record.
    return prefix + json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"


def _decode(line, prefix):
    try:
        value = json.loads(line[len(prefix):])
    except (ValueError, TypeError) as exc:
        raise StorageIdentityError("Invalid storage identity evidence in a TLO log. Restore the log from backup.") from exc
    if not isinstance(value, dict):
        raise StorageIdentityError("Invalid storage identity evidence in a TLO log.")
    return value


def _identity_record(line, prefix):
    value = _decode(line, prefix)
    ident, item = value.get("root_id"), value.get("entry")
    if not isinstance(item, dict) or _uuid(ident) != ident:
        raise StorageIdentityError("Invalid inventory identity in TLO log.")
    if not all(isinstance(item.get(k), str) and item[k] for k in ("name", "path", "prefix", "volume_id", "collection_id")):
        raise StorageIdentityError("Incomplete inventory identity in TLO log.")
    return ident, _minimal_entry(item)


@lru_cache(maxsize=16)
def _journal_state(path, signature):
    roots, archived, migrated = {}, {}, False
    if signature is None:
        return roots, archived, migrated
    with open(path, encoding="utf-8", errors="surrogateescape") as src:
        for line in src:
            if line.startswith(IDENTITY_PREFIX):
                ident, item = _identity_record(line, IDENTITY_PREFIX)
                roots[ident] = item
            elif line.startswith(ARCHIVED_PREFIX):
                ident, item = _identity_record(line, ARCHIVED_PREFIX)
                # Archive copies must never override an explicit registration.
                if ident not in archived or item.get("last_seen", "") > archived[ident].get("last_seen", ""):
                    archived[ident] = item
            elif line.rstrip("\r\n") == MIGRATED:
                migrated = True
    return roots, archived, migrated


def _token_logs(home):
    from logging_lib import LOG_TOKEN_PATTERN
    folder = os.path.join(home, "logs")
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, name) for name in os.listdir(folder)
                  if LOG_TOKEN_PATTERN.fullmatch(name) and os.path.isfile(os.path.join(folder, name)))


def _header_identities(path):
    with open(path, encoding="utf-8", errors="surrogateescape") as src:
        for line in src:
            if line.startswith(IDENTITY_PREFIX):
                yield _identity_record(line, IDENTITY_PREFIX)
            elif not (line.startswith(("#", "SEARCH_PATH:")) or not line.strip()):
                break


@lru_cache(maxsize=64)
def _cached_headers(path, _signature_value):
    return tuple(_header_identities(path))


def _legacy_registry(home):
    try:
        with open(os.path.join(home, REGISTRY), encoding="utf-8") as src:
            data = json.load(src)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise StorageIdentityError("Legacy storage identity data cannot be read. Restore it from backup.") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("roots"), dict):
        raise StorageIdentityError("Unrecognized legacy storage identity data.")
    return data["roots"]


def load_registry(home):
    """Read log-based identities; old files are migration inputs, never updated."""
    path = _journal_path(home)
    current, archived, migrated = _journal_state(path, _signature(path))
    roots = {} if migrated else _legacy_registry(home)
    legacy_ids = set(roots)
    # Copies of standalone numbered logs can restore registrations in a new
    # home. Once durable registrations exist, they are authoritative over old
    # copies of numbered logs.
    if not current:
        for token_path in _token_logs(home):
            for ident, item in _cached_headers(token_path, _signature(token_path)):
                if ident in legacy_ids:
                    continue  # verified legacy state takes precedence until migrated
                old = roots.get(ident)
                if old is not None and (old.get("generation", ident) != item.get("generation", ident)
                                        or _conflict(old.get("hardware", {}), item.get("hardware", {}))):
                    raise StorageIdentityError("Copied logs contain conflicting storage generations. Restore folderOperations.log before using them.")
                if old is None or item.get("last_seen", "") > old.get("last_seen", ""):
                    roots[ident] = item
    for ident, item in archived.items():
        roots.setdefault(ident, item)
    roots.update(current)
    aliases = set()
    for key, item in roots.items():
        if _uuid(key) != key or not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
            raise StorageIdentityError("Invalid inventory identity in TLO logs.")
        if item["name"].casefold() in aliases:
            raise StorageIdentityError("Duplicate inventory identity in TLO logs.")
        aliases.add(item["name"].casefold())
    return {key: _minimal_entry(item) for key, item in roots.items()}


def _legacy_operation_records(home):
    """Read legacy SQLite without creating or modifying it."""
    path = os.path.join(home, "logs", LEGACY_OPERATIONS)
    if not os.path.isfile(path):
        return []
    from tlo_catalog_io import open_catalog_readonly
    # sqlite3.Connection.__exit__ completes a transaction but does not close
    # the handle. Explicit close is required on success and failure (Windows).
    with closing(open_catalog_readonly(path)) as connection:
        return [{"code": code, "source": source, "destination": destination,
                 "identities": json.loads(ids)}
                for code, source, destination, ids in connection.execute(
                    "SELECT code, source, destination, identities FROM operations")]


def _append_journal(home, records):
    """One atomic durable update; used only by the locked controlling process."""
    if not records:
        return
    from logging_lib import ensure_logs_dir, _atomic_rewrite_log, _suspend_file_log_handlers
    ensure_logs_dir(home)
    path = _journal_path(home)
    with _suspend_file_log_handlers(path):
        try:
            with open(path, encoding="utf-8", errors="surrogateescape", newline="") as src:
                lines = src.readlines()
        except FileNotFoundError:
            lines = []
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        _atomic_rewrite_log(path, lines + records)
    _journal_state.cache_clear()
    _cached_headers.cache_clear()
    _current_roots.cache_clear()


def save_registry(home, roots):
    """Write registrations to the existing durable log and migrate legacy evidence once."""
    path = _journal_path(home)
    current, _archived, migrated = _journal_state(path, _signature(path))
    lines = []
    for ident, item in roots.items():
        entry = _minimal_entry(item)
        if current.get(ident) != entry:
            lines.append(_encode(IDENTITY_PREFIX, {"root_id": ident, "entry": entry}))
    if not migrated:
        lines.extend(_encode(OPERATION_PREFIX, record) for record in _legacy_operation_records(home))
        # The legacy originals remain untouched as recovery evidence, never as
        # active stores after this atomic commit.
        lines.append(MIGRATED + "\n")
    _append_journal(home, lines)


def has_storage_identities(home):
    return bool(load_registry(home))


def storage_log_header(home, path, volume_label="", *, refresh=True):
    """Observe once when a real writable log scope opens, never during log reads.

    Inventory workers use the already registered scope and write only their
    numbered logs. Standalone controlling operations may refresh the durable
    registration under the existing operation lock.
    """
    if not os.path.isdir(path):
        return ""
    info = _minimal_hardware(capture_storage(path))
    roots = load_registry(home)
    result = resolve_root(home, path, _info=info) if roots else None
    if result:
        ident, item = result
        if refresh:
            ident, item = resolve_root(home, path, register=True, _info=info)
        else:
            item = _minimal_entry(item)
            item["hardware"] = {**item.get("hardware", {}), **info}
            item["last_seen"] = _now()
        return _encode(IDENTITY_PREFIX, {"root_id": ident, "entry": _minimal_entry(item)})
    # Merely opening a tag or update scope never silently adopts an old
    # collection. A same-path conflict is not a verified registration.
    if any(_relative(path, item["path"]) is not None or
           (volume_label and item["name"].casefold() == volume_label.casefold())
           for item in roots.values()):
        raise StorageIdentityError("Log scope does not match its registered storage. Reconnect or register the correct collection.")
    return _encode(OBSERVATION_PREFIX, {"scope": os.path.abspath(path), "hardware": info, "last_seen": _now()})


def merge_storage_headers(lines, new_line):
    """Refresh a verified generation in place; retain conflicting/other scopes."""
    if not new_line:
        return list(lines)
    def key(line):
        if line.startswith(IDENTITY_PREFIX):
            ident, item = _identity_record(line, IDENTITY_PREFIX)
            return ("root", ident, item.get("generation", ident))
        value = _decode(line, OBSERVATION_PREFIX)
        hardware = value.get("hardware", {})
        return ("observation", value.get("scope"), tuple(sorted((k, v) for k, v in hardware.items()
                if k not in ("label", "mount"))))
    fingerprint = key(new_line)
    return [line for line in lines if key(line) != fingerprint] + [new_line]


def _run(args, *, binary=False):
    try:
        result = subprocess.run(
            args, capture_output=True, timeout=8, check=True,
            **_hidden_windows_subprocess_kwargs(),
        )
        return result.stdout if binary else result.stdout.decode("utf-8-sig", errors="replace").strip()
    except (OSError, subprocess.SubprocessError):
        return b"" if binary else ""


def _clean_fields(data):
    return {k: str(v).strip().strip("{}") for k, v in data.items()
            if v is not None and str(v).strip() and str(v).strip() not in ("0", "00000000-0000-0000-0000-000000000000")}


def _windows_info(path, wsl=False):
    # Native executable path is trusted; WSL interop failure is a normal fallback.
    letter = _wsl_drive_letter_for_path(path) if wsl else os.path.splitdrive(os.path.abspath(path))[0][:1].upper()
    if not re.fullmatch("[A-Z]", letter):
        return {}
    ps = shutil.which("powershell.exe") if wsl else _trusted_native_powershell_executable()
    data = {}
    if not wsl:
        try:
            root = letter + ":\\"
            serial, flags, max_len = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
            if ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), None, 0,
                    ctypes.byref(serial), ctypes.byref(max_len), ctypes.byref(flags), None, 0):
                data["filesystem_serial"] = f"{serial.value:08x}"
        except (AttributeError, OSError):
            pass
    if not ps:
        return data
    script = (
        "$ErrorActionPreference='Stop'; "
        f"$p=Get-Partition -DriveLetter '{letter}'; $d=Get-Disk -Number $p.DiskNumber; "
        f"$fs=$null; try {{ $fs=(Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='{letter}:'\").VolumeSerialNumber }} catch {{}}; "
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "[pscustomobject]@{filesystem_serial=$fs; disk_serial=$d.SerialNumber; disk_unique_id=$d.UniqueId; "
        "partition_guid=$p.Guid; partition_offset=$p.Offset; partition_size=$p.Size} | ConvertTo-Json -Compress"
    )
    try:
        result = json.loads(_run([ps, "-NoProfile", "-NonInteractive", "-Command", script]))
        if isinstance(result, dict):
            fields = _clean_fields(result)
            if fields.get("filesystem_serial"):
                fields["filesystem_serial"] = fields["filesystem_serial"].replace("-", "").lower()
            data.update(fields)
    except (ValueError, TypeError):
        pass
    return data


def _linux_info(path):
    source = _run(["findmnt", "-n", "-o", "SOURCE", "-T", path])
    if not source.startswith("/dev/"):
        return {}
    source = source.split("[", 1)[0]
    try:
        rows = json.loads(_run(["lsblk", "-J", "-b", "-o",
            "NAME,TYPE,PKNAME,SERIAL,WWN,SIZE,PARTUUID,UUID,START", source]))["blockdevices"]
        part = rows[0]
        parent = part.get("pkname")
        disk = part
        if parent:
            disk = json.loads(_run(["lsblk", "-J", "-b", "-d", "-o",
                "NAME,SERIAL,WWN", "/dev/" + parent]))["blockdevices"][0]
        return _clean_fields({
            "disk_serial": disk.get("serial"), "disk_unique_id": disk.get("wwn"),
            "partition_guid": part.get("partuuid"), "filesystem_uuid": part.get("uuid"),
            "partition_start_sector": part.get("start"), "partition_size": part.get("size"),
        })
    except (KeyError, IndexError, ValueError, TypeError):
        return {}


def _mac_info(path):
    try:
        info = plistlib.loads(_run(["/usr/sbin/diskutil", "info", "-plist", path], binary=True))
        whole = info.get("ParentWholeDisk") or info.get("DeviceIdentifier")
        disk = plistlib.loads(_run(["/usr/sbin/diskutil", "info", "-plist", whole], binary=True)) if whole else {}
        return _clean_fields({
            "disk_serial": disk.get("SerialNumber"), "disk_unique_id": disk.get("DiskUUID"),
            "partition_guid": info.get("DiskUUID"), "filesystem_uuid": info.get("VolumeUUID"),
            "partition_offset": info.get("PartitionMapPartitionOffset"),
            "partition_size": info.get("TotalSize"),
        })
    except (ValueError, TypeError, OSError, plistlib.InvalidFileException):
        return {}


def capture_storage(path):
    """Best-effort stable hardware data; never report a drive number as a serial."""
    info = resolve_volume_label(path)
    base = info.volume_key or path
    data = {"label": normalize_volume_label(info.label), "mount": str(base)}
    if unc_root(path):
        return {**data, "kind": "network"}
    if os.name == "nt":
        details = _windows_info(path)
    elif _running_on_wsl() and _wsl_drive_letter_for_path(path):
        details = _windows_info(path, wsl=True)
    elif platform.system() == "Darwin":
        details = _mac_info(base)
    else:
        details = _linux_info(path)
    return _minimal_hardware({**data, **details, "kind": "local"})


def _path_key(path):
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _relative(path, root):
    try:
        if os.path.commonpath((_path_key(path), _path_key(root))) != _path_key(root):
            return None
        return os.path.relpath(path, root).replace(os.sep, "/")
    except (OSError, ValueError):
        return None


def _partition_relative(path, info):
    return _relative(path, info.get("mount") or path)


def _same_value(a, b, key):
    left, right = str(a.get(key) or "").casefold(), str(b.get(key) or "").casefold()
    return bool(left and left == right and left not in {"unknown", "none", "n/a", "0", "00000000", "not specified"})


def _conflict(a, b):
    # Missing hardware data isn't a contradiction. Never accept a known changed
    # partition/filesystem (e.g. a clone, reformat, or different partition).
    if any(a.get(k) and b.get(k) and not _same_value(a, b, k) for k in (
        "disk_serial", "partition_guid", "filesystem_uuid", "filesystem_serial",
    )):
        return True
    if not _same_value(a, b, "disk_serial") and a.get("disk_unique_id") and b.get("disk_unique_id"):
        if not _same_value(a, b, "disk_unique_id"):
            return True
    if not _same_value(a, b, "partition_guid"):
        return any(a.get(k) and b.get(k) and not _same_value(a, b, k)
                   for k in ("partition_offset", "partition_start_sector", "partition_size"))
    return False


def _strong_partition_match(a, b):
    if _conflict(a, b):
        return False
    hardware = _same_value(a, b, "disk_serial") or _same_value(a, b, "disk_unique_id")
    partition = _same_value(a, b, "partition_guid") or (
        (_same_value(a, b, "partition_offset") or _same_value(a, b, "partition_start_sector"))
        and _same_value(a, b, "partition_size"))
    return hardware and partition


def read_marker(root):
    file = os.path.join(root, MARKER)
    try:
        if os.path.islink(file):
            raise StorageIdentityError("Storage identification file is a link; refusing to use it.")
        with open(file, encoding="utf-8") as src:
            data = json.load(src)
    except FileNotFoundError:
        return ""
    except PermissionError:
        return ""
    except (OSError, ValueError) as exc:
        raise StorageIdentityError(f"Cannot read storage identification file in {root}.") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise StorageIdentityError(f"Invalid storage identification file in {root}.")
    return _uuid(data.get("root_id"))


def _create_marker(root, root_id, *, replace=False):
    path = os.path.join(root, MARKER)
    try:
        if replace:
            if os.path.islink(path):
                raise StorageIdentityError("Cannot replace a linked identification file.")
            _atomic_json(path, {"schema": SCHEMA, "root_id": root_id})
        else:
            with open(path, "x", encoding="utf-8") as out:
                json.dump({"schema": SCHEMA, "root_id": root_id}, out)
                out.flush()
                os.fsync(out.fileno())
        return True
    except FileExistsError:
        if read_marker(root) == root_id:
            return True
        raise StorageIdentityError("Another storage identification file appeared; please retry.")
    except OSError:
        return False


def _find_marker(path, mount):
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        root = os.path.dirname(root)
    while True:
        ident = read_marker(root)
        if ident:
            return root, ident
        if _path_key(root) == _path_key(mount):
            return "", ""
        parent = os.path.dirname(root)
        if parent == root or _relative(parent, mount) is None:
            return "", ""
        root = parent


def _root_record(roots, name):
    return next(((key, item) for key, item in roots.items()
                 if item["name"].casefold() == str(name).casefold()), ("", None))


def _verified(item, root, info, marker_id, root_id):
    if _conflict(item.get("hardware", {}), info):
        return False
    if marker_id:
        return marker_id == root_id
    return (not item.get("marker_required", False)
            and _strong_partition_match(item.get("hardware", {}), info)
            and item.get("partition_relative") == _partition_relative(root, info))


def resolve_root(home, path, *, register=False, legacy_name=None, replacement_id="", separate=False, collection_id="", _info=None, suggested_name=""):
    """Locate or register a managed root. Explicit replacement never merges rows."""
    path = os.path.abspath(os.path.normpath(path))
    if not os.path.isdir(path):
        raise StorageIdentityError(f"Storage folder is not accessible: {path}")
    roots = load_registry(home)
    info = _minimal_hardware(capture_storage(path) if _info is None else _info)
    mount = info.get("mount") or path
    marked_root, marker = _find_marker(path, mount)
    marker_written = bool(marker)
    if not marker and not replacement_id:
        for key, item in roots.items():
            prior = item.get("path", "")
            if prior and _path_key(prior) != _path_key(path) and _relative(prior, path) is not None and os.path.isdir(prior):
                if read_marker(prior) == key:
                    raise StorageIdentityError("This folder contains another registered inventory. Select that inventory root or its subfolders instead.")
    if replacement_id:
        if replacement_id not in roots:
            raise StorageIdentityError("Select an existing inventory in Manage Storage Identities.")
        if marker and marked_root != path:
            raise StorageIdentityError("Choose the registered root itself, not a folder inside another inventory.")
        if marker and marker != replacement_id and marker in roots:
            raise StorageIdentityError("This folder belongs to a different registered inventory.")
        root, ident = path, replacement_id
        old = roots[ident]
        previous = old.get("path", "")
        if previous and _path_key(previous) != _path_key(root) and os.path.isdir(previous) and read_marker(previous) == ident:
            try:
                same = os.path.samefile(previous, root)
            except OSError:
                same = False
            if not same:
                raise StorageIdentityError("The original folder is still connected. Register this as a separate copy instead.")
        marker_written = marker == ident or _create_marker(root, ident, replace=bool(marker))
        if not marker_written and not (not old.get("marker_required", False)
                                       and _strong_partition_match(old.get("hardware", {}), info)):
            raise StorageIdentityError("Replacement requires a writable identification file.")
        old.setdefault("previous_locations", []).append({"path": old["path"], "hardware": old.get("hardware", {})})
    elif marker and not separate:
        root, ident = marked_root, marker
        old = roots.get(ident)
        if old:
            if not _verified(old, root, info, marker, ident):
                raise StorageIdentityError("Storage may be a clone or replacement. Use Manage Storage Identities to register it separately or reconnect the previous inventory.")
            # If both locations remain connected, the same UUID must not identify
            # two distinct directories (including clones on one disk).
            previous = old.get("path", "")
            if previous and _path_key(previous) != _path_key(root) and os.path.isdir(previous):
                try:
                    same = os.path.samefile(previous, root)
                except OSError:
                    same = False
                if not same and read_marker(previous) == ident:
                    raise StorageIdentityError("The same identification file exists on two connected folders. Register the copy separately in Manage Storage Identities.")
        elif not register:
            return None
    else:
        root = path
        ident = ""
        old = None
        if marker and separate and marker in roots and _path_key(roots[marker]["path"]) == _path_key(path) and not _conflict(roots[marker].get("hardware", {}), info):
            raise StorageIdentityError("This is already the registered original folder. Choose the separate copy instead.")
        if marker and separate and marked_root != path:
            raise StorageIdentityError("Choose the copied inventory root itself.")
        if not separate:
            candidates = [(key, item) for key, item in roots.items()
                          if not item.get("marker_required", False)
                          and _strong_partition_match(item.get("hardware", {}), info)
                          and item.get("partition_relative") == _partition_relative(root, info)]
            if len(candidates) == 1:
                ident, old = candidates[0]
            elif len(candidates) > 1:
                raise StorageIdentityError("More than one inventory matches this storage. Use Manage Storage Identities.")
        if not ident:
            if not register:
                return None
            ident = str(uuid.uuid4())
            marker_written = _create_marker(root, ident, replace=bool(marker and separate))
            if not marker_written:
                if marker or not _strong_partition_match(info, info):
                    raise StorageIdentityError("Cannot identify this read-only folder reliably. Choose a writable inventory root or connect the drive locally.")
    if legacy_name is not None and old is not None and old["name"].casefold() != str(legacy_name).casefold():
        raise StorageIdentityError("This folder already has a different inventory name. Its existing inventory is preserved; select the original unregistered folder instead.")
    if not register and not replacement_id:
        return (ident, {**old, "path": root}) if old else None
    if old is None:
        # Register a new root without silently taking over any legacy label.
        all_names = {item["name"].casefold() for item in roots.values()}
        legacy_rows = read_bootlist_rows(home) + read_group_log_volume_rows(home)
        legacy_names = {str(row.get("Volume", "")).casefold() for row in legacy_rows}
        suggested = str(info.get("label") or suggested_name or os.path.basename(root.rstrip(os.sep)) or "Storage").replace("[", "(").replace("]", ")")
        prefix = storage_path_without_drive(root) or "/"
        if legacy_name is not None:
            name = str(legacy_name).strip()
            if not name or name.casefold() in all_names or name.casefold() not in legacy_names:
                raise StorageIdentityError("Select an unused historical inventory name.")
            if any(str(row.get("Volume", "")).casefold() == name.casefold()
                   and not path_is_same_or_under(row.get("Path", ""), prefix)
                   for row in legacy_rows):
                raise StorageIdentityError("Select a containing folder that covers all paths in the historical inventory.")
        else:
            name = suggested
            if name.casefold() in all_names | legacy_names:
                name += " ~" + ident[:8]
        old = {"name": name, "prefix": prefix, "collection_id": collection_id or ident,
               "created": _now(), "previous_locations": []}
    if old.get("path") and old["path"] != root and not replacement_id:
        old.setdefault("previous_locations", []).append({"path": old["path"], "hardware": old.get("hardware", {})})
    old["marker_required"] = marker_written
    if replacement_id or not old.get("generation"):
        old["generation"] = str(uuid.uuid4())
    same_partition = _strong_partition_match(old.get("hardware", {}), info)
    # Keep previously known hardware details when an enclosure or WSL hides them.
    old["hardware"] = _minimal_hardware(dict(info) if replacement_id else {**old.get("hardware", {}), **info})
    # Capture the physical partition separately; multiple registered roots on
    # the same partition share a volume ID when the OS provides enough evidence.
    if (replacement_id and not same_partition) or not old.get("volume_id"):
        old["volume_id"] = next((item.get("volume_id") for key, item in roots.items()
                                if key != ident and item.get("volume_id")
                                and _strong_partition_match(item.get("hardware", {}), info)), None) or str(uuid.uuid4())
    old["path"] = root
    old["partition_relative"] = _partition_relative(root, info)
    old["last_seen"] = _now()
    if collection_id:
        old["collection_id"] = collection_id
    roots[ident] = old
    save_registry(home, roots)
    return ident, old


def register_inventory_root(home, path, confirm_legacy=None, suggested_name=""):
    info = capture_storage(path)
    result = resolve_root(home, path, _info=info)
    if result:
        return resolve_root(home, path, register=True, _info=info, suggested_name=suggested_name)
    label = info.get("label", "")
    rows = read_bootlist_rows(home) + read_group_log_volume_rows(home)
    old = [row for row in rows if label and str(row.get("Volume", "")).casefold() == label.casefold()]
    prefix = storage_path_without_drive(path)
    roots = load_registry(home)
    if (old and not _root_record(roots, label)[1]
            and all(path_is_same_or_under(row.get("Path", ""), prefix) for row in old)
            and callable(confirm_legacy)
            and confirm_legacy(f"Connect {path} to the existing inventory [{label}]? "
                               "Choose Yes only if this is the same collection. No creates a separate inventory and preserves the old one.") is True):
        return resolve_root(home, path, register=True, legacy_name=label, _info=info)
    return resolve_root(home, path, register=True, _info=info, suggested_name=suggested_name)


@lru_cache(maxsize=16)
def _current_roots(home, _journal_signature):
    return load_registry(home)


def _read_roots(home):
    path = _journal_path(home)
    signature = _signature(path)
    current, _archived, migrated = _journal_state(path, signature)
    if current and migrated:
        return _current_roots(home, signature)
    return load_registry(home)


def registered_entry(home, name):
    item = _root_record(_read_roots(home), name)[1]
    return copy.deepcopy(item) if item is not None else None


def stored_path(home, name, path, *, entry=None):
    item = entry if entry is not None else registered_entry(home, name)
    if item is None:
        return storage_path_without_drive(path)
    relative = _relative(path, item["path"])
    if relative is None:
        return storage_path_without_drive(path)
    return posixpath.normpath(posixpath.join(item["prefix"], relative))


def registered_name_for_path(home, path):
    probe = path if os.path.isdir(path) else os.path.dirname(path)
    result = resolve_root(home, probe)
    return result[1]["name"] if result else ""


def verified_roots(home, mounted=()):
    """Resolve registry entries at their current or relocated mounts, read-only."""
    roots = load_registry(home)
    found = {}
    for ident, item in roots.items():
        candidates = [item["path"]]
        rel = item.get("partition_relative")
        if rel is not None:
            candidates += [os.path.join(base, *rel.split("/")) for base in mounted]
        matches = []
        for candidate in dict.fromkeys(candidates):
            try:
                if not os.path.isdir(candidate):
                    continue
                marker = read_marker(candidate)
                if marker and marker != ident:
                    continue
                if not marker and not _strong_partition_match(item.get("hardware", {}), item.get("hardware", {})):
                    continue
                info = capture_storage(candidate)
                if _verified(item, candidate, info, marker, ident):
                    if not any(os.path.samefile(candidate, match) for match in matches):
                        matches.append(candidate)
            except (StorageIdentityError, OSError):
                continue
        found[item["name"].casefold()] = (item, matches[0] if len(matches) == 1 else "")
    return found


def physical_path(item, actual_root, stored):
    # Canonical stored paths are based on the initial root, not current mount.
    prefix = normalize_path_for_compare(item["prefix"])
    value = normalize_path_for_compare(stored)
    if not actual_root or not prefix or not value or not path_is_same_or_under(value, prefix):
        return ""
    if ".." in str(stored).replace("\\", "/").split("/") or "\x00" in str(stored):
        return ""
    relative = posixpath.relpath(value, prefix)
    candidate = os.path.normpath(os.path.join(actual_root, *relative.split("/")))
    if _relative(os.path.realpath(candidate), os.path.realpath(actual_root)) is None:
        return ""
    return candidate


def storage_name_and_path(home, path):
    """Use a registered root when available; retain legacy path format otherwise."""
    from tlo_bootlist_volume_policy import os_volume_label_for_path
    roots = load_registry(home)
    if not roots:
        return os_volume_label_for_path(path), path
    result = resolve_root(home, path if os.path.isdir(path) else os.path.dirname(path))
    if result:
        _ident, item = result
        relative = _relative(path, item["path"])
        if relative is not None:
            return item["name"], posixpath.normpath(posixpath.join(item["prefix"], relative))
    label = os_volume_label_for_path(path)
    if registered_entry(home, label) or (label and any(
            str(item.get("hardware", {}).get("label", "")).casefold() == label.casefold()
            for item in roots.values())):
        raise StorageIdentityError("This folder is not the registered inventory. Open Manage Storage Identities.")
    return label, path


def folder_operation_roots(home, source, destination):
    """Identify registered endpoints of a logged folder operation, without probing disks per show."""
    roots = _read_roots(home)
    result = []
    for path in (source, destination):
        matches = [(ident, item) for ident, item in roots.items()
                   if _relative(path, item["path"]) is not None]
        if matches:
            ident, item = max(matches, key=lambda pair: len(pair[1]["path"]))
            result.append([ident, item["volume_id"], item.get("generation", ident)])
        else:
            result.append(None)
    return result


def folder_operation_key(line):
    match = re.fullmatch(r"(RENAME_COMPLIANTLY|TAG_COPY(?:_DELETE_(?:MOVE|COPY))?):\s+(.+?)\s+->\s+(.+)", line.strip(), re.I)
    if not match:
        return None
    code, source, destination = match.groups()
    return code.upper(), _path_key(source), _path_key(destination)


def operation_evidence_key(line):
    record = _decode(line, OPERATION_PREFIX)
    return record["code"], record["source"], record["destination"]


def folder_operation_identity_line(home, line):
    """Encode evidence adjacent to the operation in its existing tag log."""
    key = folder_operation_key(line)
    if not key:
        return ""
    code, source, destination = key
    ids = folder_operation_roots(home, source, destination)
    if not any(ids):
        return ""
    return _encode(OPERATION_PREFIX, {"code": code, "source": source,
                   "destination": destination, "identities": ids})


def record_folder_operation(home, line):
    """Compatibility entry point for operation records outside a token logger."""
    evidence = folder_operation_identity_line(home, line)
    if evidence:
        _append_journal(home, [evidence])


def _operation_evidence(home, extra_path=""):
    records = {}
    path = _journal_path(home)
    _roots, _archived, migrated = _journal_state(path, _signature(path))
    candidates = [_journal_path(home)] + [p for p in _token_logs(home)
        if os.path.basename(p).startswith(("tag", "tags"))]
    if extra_path:
        candidates.append(extra_path)
    def add(value):
        key = (value["code"], value["source"], value["destination"])
        ids = value["identities"]
        if not isinstance(ids, list) or len(ids) != 2:
            raise StorageIdentityError("Invalid storage operation evidence.")
        bucket = records.setdefault(key, [])
        if ids not in bucket:
            bucket.append(ids)
    for candidate in dict.fromkeys(candidates):
        if os.path.isfile(candidate):
            with open(candidate, encoding="utf-8", errors="surrogateescape") as src:
                for line in src:
                    if line.startswith(OPERATION_PREFIX):
                        add(_decode(line, OPERATION_PREFIX))
    if not migrated:
        for record in _legacy_operation_records(home):
            add(record)
    return records


def check_folder_operation(home, code, source, destination, verified, evidence_path=""):
    """Refuse to reverse unverified/reused registered paths."""
    roots = folder_operation_roots(home, source, destination)
    key = ("storage-operation-evidence", os.path.abspath(home), evidence_path)
    if key not in verified:
        verified[key] = _operation_evidence(home, evidence_path)
    evidence = verified[key].get((code.upper(), _path_key(source), _path_key(destination)), [])
    if not evidence and not any(roots):
        return True
    if len(evidence) != 1 or evidence[0] != roots:
        return False
    for endpoint, root in zip((source, destination), roots):
        if not root:
            continue
        ident, _volume_id, _generation = root
        entry = load_registry(home).get(ident)
        if not entry:
            return False
        if ident not in verified:
            probe = resolve_root(home, entry["path"])
            verified[ident] = bool(probe and probe[0] == ident)
        if not verified[ident]:
            return False
        marker = read_marker(entry["path"])
        if (marker or entry.get("marker_required")) and marker != ident:
            return False
        if _relative(os.path.realpath(endpoint), os.path.realpath(entry["path"])) is None:
            return False
    return True
