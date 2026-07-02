__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.
import ctypes
import os
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeLabelInfo:
    volume_key: str
    label: str
    label_source: str


def _running_on_windows():
    return os.name == 'nt'


def _running_on_wsl():
    if _running_on_windows():
        return False
    try:
        with open('/proc/version', 'r', encoding='utf-8') as infile:
            version_text = infile.read().lower()
        return 'microsoft' in version_text or 'wsl' in version_text
    except OSError:
        return False


def _normalize_drive_root(path_text: str) -> str:
    drive, _tail = os.path.splitdrive(os.path.abspath(path_text))
    if drive:
        return drive.rstrip("\\/") + os.sep
    return os.path.abspath(path_text)


def _wsl_drive_root(path_text: str) -> str:
    normalized = os.path.normpath(path_text)
    match = re.match(r'^/mnt/([a-zA-Z])(?:/.*)?$', normalized)
    if match:
        return f"/mnt/{match.group(1).lower()}"
    return ''


def _mount_point_for_path(path_text: str) -> str:
    path_text = os.path.abspath(path_text)
    probe = path_text
    while True:
        parent = os.path.dirname(probe)
        if parent == probe:
            return probe
        try:
            if os.path.ismount(probe):
                return probe
        except OSError:
            pass
        probe = parent


def _run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False)
    except Exception:
        return ''
    output = (result.stdout or '').strip()
    if not output:
        output = (result.stderr or '').strip()
    return output


def _windows_volume_label(root_path: str) -> str:
    try:
        kernel32 = ctypes.windll.kernel32
    except Exception:
        return ''

    volume_name = ctypes.create_unicode_buffer(261)
    fs_name = ctypes.create_unicode_buffer(261)
    serial_number = ctypes.c_ulong()
    max_component_len = ctypes.c_ulong()
    fs_flags = ctypes.c_ulong()

    ok = kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root_path),
        volume_name,
        len(volume_name),
        ctypes.byref(serial_number),
        ctypes.byref(max_component_len),
        ctypes.byref(fs_flags),
        fs_name,
        len(fs_name),
    )
    if not ok:
        return ''
    return volume_name.value.strip()


def _wsl_windows_volume_label(path_text: str) -> str:
    drive_root = _wsl_drive_root(path_text)
    if not drive_root:
        return ''
    drive_letter = drive_root[-1].upper()
    cmd_exe = shutil.which('cmd.exe')
    if not cmd_exe:
        return ''
    output = _run_command([cmd_exe, '/c', 'vol', f'{drive_letter}:'])
    if not output:
        return ''
    lowered = output.lower()
    if 'has no label' in lowered:
        return ''
    match = re.search(rf'Volume in drive\s+{re.escape(drive_letter)}\s+is\s+(.+)', output, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''


def _linux_filesystem_label(path_text: str) -> str:
    findmnt = shutil.which('findmnt')
    if findmnt:
        output = _run_command([findmnt, '-no', 'LABEL', '-T', path_text])
        if output and output != '-':
            return output.strip()
    return ''


def _mac_volume_label(path_text: str) -> str:
    diskutil = shutil.which('diskutil')
    if not diskutil:
        return ''
    output = _run_command([diskutil, 'info', path_text])
    if not output:
        return ''
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key.strip().lower() == 'volume name':
            return value.strip()
    return ''


def _base_volume_key(path_text: str) -> str:
    if _running_on_windows():
        return _normalize_drive_root(path_text)
    if _running_on_wsl():
        drive_root = _wsl_drive_root(path_text)
        if drive_root:
            return drive_root
    return _mount_point_for_path(path_text)


def resolve_volume_label(path_text: str) -> VolumeLabelInfo:
    volume_key = _base_volume_key(path_text)
    label = ''
    source = ''

    if _running_on_windows():
        label = _windows_volume_label(volume_key)
        source = 'windows_volume'
    elif _running_on_wsl():
        label = _wsl_windows_volume_label(path_text)
        if label:
            source = 'wsl_windows_volume'
        else:
            label = _linux_filesystem_label(path_text)
            source = 'filesystem_label'
    elif os.name == 'posix':
        label = _mac_volume_label(path_text)
        if label:
            source = 'mac_volume'
        else:
            label = _linux_filesystem_label(path_text)
            source = 'filesystem_label'

    return VolumeLabelInfo(volume_key=volume_key, label=(label or '').strip(), label_source=source if label else '')
