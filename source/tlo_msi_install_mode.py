"""Importable helper for TLO's existing update dispatcher.

Do not use only an untrusted marker file. Require the MSI-owned HKCU path and
matching executable directory to use the MSI-owned upgrade worker. Portable
Windows installations can also download a verified MSI by default.
"""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from pathlib import Path
import json
import ntpath
import os
import sys


def _trusted_system32_executable(name):
    """Fail closed to Windows' API-reported System32, never PATH or CWD."""
    if name not in {"powershell.exe", "msiexec.exe"}:
        raise ValueError("Unsupported Windows helper")
    from tlo_security import windows_directory_from_api
    return ntpath.join(windows_directory_from_api(), "System32", name)


def msi_install_root(executable=None):
    """Return verified MSI-owned installation root or None."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # Tests may simulate Windows on a non-Windows host.
        return None
    executable = Path(executable or sys.executable).resolve()
    if executable.name.casefold() not in {"tlo-main.exe", "tlo-search.exe"}:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\TradersLittleOrganizer\Installer") as key:
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            mode, _ = winreg.QueryValueEx(key, "InstallMethod")
    except OSError:
        return None
    if str(mode).casefold() != "msi":
        return None
    install_root = Path(path).resolve()
    try:
        executable.relative_to(install_root)
    except ValueError:
        return None
    marker = install_root / "tlo-install-method.json"
    try:
        if json.loads(marker.read_text(encoding="utf-8")).get("installer") == "msi":
            return install_root
    except (OSError, ValueError):
        pass
    return None


def is_msi_install(executable=None):
    return msi_install_root(executable) is not None


def launch_verified_msi_upgrade(msi_file, trusted_expected_sha256, *,
                                executable=None, worker=None, restart=True):
    """Call ONLY after the existing pinned-key signature verification of release metadata.

    The caller must ensure release is stable (not draft/prerelease), newest,
    the asset is listed in authenticated metadata, and the local .msi was
    downloaded using the existing temporary-file-then-rename strategy.

    Returns after spawning the independent worker; caller MUST exit TLO.
    """
    install_root = msi_install_root(executable)
    if install_root is None:
        raise RuntimeError("MSI updater invoked on non-MSI installation")
    import re
    import subprocess
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", trusted_expected_sha256):
        raise ValueError("Expected SHA-256 from authenticated manifest")
    current_exe = Path(executable or sys.executable).resolve()
    worker = Path(worker or install_root / "TLO-MSI-Update-Worker.ps1")
    if not worker.is_file():
        raise RuntimeError("MSI updater helper is missing")
    msi = Path(msi_file).resolve(strict=True)
    if msi.suffix.casefold() != ".msi":
        raise ValueError("MSI asset required")
    args = [_trusted_system32_executable("powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(worker), "-MsiPath", str(msi),
            "-ExpectedSha256", trusted_expected_sha256,
            "-WaitForPid", str(os.getpid()),
            "-InstallRoot", str(install_root)]
    if restart:
        args += ["-RestartExe", str(current_exe)]
    subprocess.Popen(args, close_fds=True,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return True


def launch_verified_portable_msi_install(msi_file, trusted_expected_sha256):
    """Launch the interactive Windows installer for an existing ZIP installation.

    Authentication of the official release manifest and the exact download
    hash occurs before this boundary. An MSI worker tied to an existing
    registered installation is intentionally not used for portable TLO.
    """
    import hashlib
    import re
    import subprocess
    if sys.platform != 'win32':
        raise RuntimeError('MSI installation is supported on Windows only')
    if not re.fullmatch(r'[A-Fa-f0-9]{64}', trusted_expected_sha256):
        raise ValueError('Missing authenticated MSI SHA-256 hash')
    msi = Path(msi_file).resolve(strict=True)
    if msi.suffix.casefold() != '.msi':
        raise ValueError('MSI asset required')
    with msi.open('rb') as handle:
        if handle.read(8) != bytes.fromhex('d0cf11e0a1b11ae1'):
            raise ValueError('Downloaded MSI has an invalid Installer database header')
    hasher = hashlib.sha256()
    with msi.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest.casefold() != trusted_expected_sha256.casefold():
        raise ValueError('Downloaded MSI no longer matches signed release metadata')
    subprocess.Popen([_trusted_system32_executable('msiexec.exe'), '/i', str(msi)], close_fds=True)
    return True


# The MSI owns database installation. Applications only resolve configured
# TLOHome and read its databases; they must not seed or repair installed files.
MSI_USER_SETTINGS_KEY = r"Software\TradersLittleOrganizer\UserSettings"


def open_tlo_home_folder(home):
    """Open TLOHome in the system file manager (Windows, macOS, Linux)."""
    import subprocess
    folder = Path(home).expanduser().resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"TLOHome does not exist: {folder}")
    if sys.platform == "win32":
        os.startfile(str(folder))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)], close_fds=True)
    else:
        subprocess.Popen(["xdg-open", str(folder)], close_fds=True)


def saved_msi_data_home_for_executable(executable=None):
    """CLI executables can reuse the same per-user TLOHome selected in Main/Search.

    Unlike updater ownership detection, any executable directly under the verified
    MSI install root can read DataHome; explicit CLI/env inputs still override it.
    """
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        executable_path = Path(executable or sys.executable).resolve()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\TradersLittleOrganizer\Installer") as key:
            root, _ = winreg.QueryValueEx(key, "InstallPath")
            method, _ = winreg.QueryValueEx(key, "InstallMethod")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\TradersLittleOrganizer\UserSettings") as key:
            home, _ = winreg.QueryValueEx(key, "DataHome")
        program = Path(root).resolve()
        data = Path(home).resolve()
        if method != "msi" or data == program or program in data.parents or not data.is_dir():
            return ""
        if executable_path.parent != program:
            return ""
        marker = program / "tlo-install-method.json"
        if json.loads(marker.read_text(encoding="utf-8")).get("installer") != "msi":
            return ""
        return str(data)
    except (ImportError, OSError, ValueError, TypeError):
        return ""
