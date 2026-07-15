__version__ = "v336"
# TLO-GI package version: v336
__version_summary__ = 'Restricts standalone Tag to direct tagging and hides undocumented myTLO help.'
# TLO-GI version summary: Restricts standalone Tag to direct tagging and hides undocumented myTLO help.
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


def _hidden_windows_subprocess_kwargs(platform_name=None):
    """Return subprocess options that keep Windows helper commands invisible."""
    if (platform_name or os.name) != "nt":
        return {}
    kwargs = {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creationflags:
        kwargs["creationflags"] = creationflags
    startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
    startf_use_showwindow = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    if startupinfo_type is not None and startf_use_showwindow:
        startupinfo = startupinfo_type()
        startupinfo.dwFlags |= startf_use_showwindow
        if hasattr(startupinfo, "wShowWindow"):
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=False, **_hidden_windows_subprocess_kwargs())
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



def _windows_drive_letter_for_path(path_text: str) -> str:
    drive, _tail = os.path.splitdrive(os.path.abspath(path_text))
    if drive and len(drive) >= 2 and drive[1] == ':':
        return drive[0].upper()
    return ''


def _wsl_drive_letter_for_path(path_text: str) -> str:
    root = _wsl_drive_root(path_text)
    if root:
        return root[-1].upper()
    return ''


def _powershell_disk_number_for_drive(drive_letter: str, executable: str = 'powershell') -> str:
    drive_letter = (drive_letter or '').strip().upper()[:1]
    if not drive_letter:
        return ''
    ps = shutil.which(executable) or (shutil.which(executable + '.exe') if not executable.endswith('.exe') else '')
    if not ps:
        return ''
    command_text = (
        "$p = Get-Partition -DriveLetter '%s' -ErrorAction SilentlyContinue; "
        "if ($p) { ($p | Select-Object -First 1 | Get-Disk).Number }"
    ) % drive_letter
    output = _run_command([ps, '-NoProfile', '-Command', command_text])
    match = re.search(r'\d+', output or '')
    return match.group(0) if match else ''


def _windows_physical_drive_id(path_text: str) -> str:
    disk = _powershell_disk_number_for_drive(_windows_drive_letter_for_path(path_text), 'powershell')
    return f"windows-disk:{disk}" if disk else ''


def _wsl_physical_drive_id(path_text: str) -> str:
    disk = _powershell_disk_number_for_drive(_wsl_drive_letter_for_path(path_text), 'powershell.exe')
    return f"windows-disk:{disk}" if disk else ''


def _linux_physical_drive_id(path_text: str) -> str:
    findmnt = shutil.which('findmnt')
    source = ''
    if findmnt:
        source = _run_command([findmnt, '-no', 'SOURCE', '-T', path_text]).strip()
    if not source:
        return ''
    source = os.path.realpath(source)
    lsblk = shutil.which('lsblk')
    if lsblk:
        parent = _run_command([lsblk, '-no', 'PKNAME', source]).strip().splitlines()
        if parent and parent[0].strip():
            return f"linux-block:{parent[0].strip()}"
        name = _run_command([lsblk, '-no', 'NAME', source]).strip().splitlines()
        if name and name[0].strip():
            return f"linux-block:{name[0].strip()}"
    base = os.path.basename(source)
    # Fallback for common /dev/sda1, /dev/nvme0n1p1, and /dev/mmcblk0p1 names.
    base = re.sub(r'p?\d+$', '', base)
    return f"linux-block:{base}" if base else ''


def _mac_physical_drive_id(path_text: str) -> str:
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
        if key.strip().lower() == 'part of whole':
            whole = value.strip()
            if whole:
                return f"mac-disk:{whole}"
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        if key.strip().lower() == 'device identifier':
            ident = re.sub(r's\d+$', '', value.strip())
            if ident:
                return f"mac-disk:{ident}"
    return ''


def resolve_physical_drive_id(path_text: str) -> str:
    """Return a best-effort physical disk identity for scheduling only.

    The value is intentionally not persisted.  Empty means the current platform
    could not determine a stable enough physical disk id, in which case callers
    should fall back to visible-volume grouping.
    """
    try:
        if _running_on_windows():
            return _windows_physical_drive_id(path_text)
        if _running_on_wsl():
            return _wsl_physical_drive_id(path_text) or _linux_physical_drive_id(path_text)
        if os.name == 'posix':
            return _mac_physical_drive_id(path_text) or _linux_physical_drive_id(path_text)
    except Exception:
        return ''
    return ''

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
