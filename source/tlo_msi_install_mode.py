"""Importable helper for TLO's existing update dispatcher.

Do not use only an untrusted marker file. Require the MSI-owned HKCU path and
matching actual executable directory. Non-MSI installations keep ZIP updater.
"""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from pathlib import Path
import json
import os
import sys
import shutil
import tempfile


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
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(worker), "-MsiPath", str(msi),
            "-ExpectedSha256", trusted_expected_sha256,
            "-WaitForPid", str(os.getpid()),
            "-InstallRoot", str(install_root)]
    if restart:
        args += ["-RestartExe", str(current_exe)]
    subprocess.Popen(args, close_fds=True,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return True


# The only files that MSI may replace in TLOHome. Everything else, including
# preferences, inventory, logs, and setlists, remains user-managed.
MSI_MANAGED_DATABASES = ("artists.sqlite", "venues.txt", "cities.csv")
MSI_DATABASE_BUILD_MARKER = ".tlo-msi-db-build"
MSI_USER_SETTINGS_KEY = r"Software\TradersLittleOrganizer\UserSettings"


def _write_atomic_from_file(source, dest):
    """Replace one installer-managed database atomically on its own volume."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tlo-msi-db-", dir=dest.parent,
                                         delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as reader:
                shutil.copyfileobj(reader, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, dest)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_atomic_text(dest, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".tlo-msi-state-", dir=dest.parent,
                                         mode="w", encoding="utf-8", delete=False) as out:
            temporary = Path(out.name)
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, dest)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def seed_msi_data_home(home):
    """Seed user files once; synchronize managed database masters per MSI build.

    A new MSI release may replace everything in TLOHome/TLO_DBs that it owns.
    User changes to these managed database masters are not guaranteed to be
    preserved or backward-compatible. Non-DB files are never overwritten.
    """
    program = msi_install_root()
    if program is None:
        return
    home = Path(home)
    source = program / "TLO_DBs"
    dest = home / "TLO_DBs"
    dest.mkdir(exist_ok=True, parents=True)
    for name in ("TLO-FAQ.txt", "tlo-preferences.ini"):
        target = home / name
        if not target.exists():
            original = program / name
            if original.is_file():
                try:
                    with original.open("rb") as reader, target.open("xb") as writer:
                        shutil.copyfileobj(reader, writer)
                except FileExistsError:
                    pass

    # Marker is in the installer-managed DB folder. A new program build causes
    # one synchronized replacement at the first subsequent TLO launch, not on
    # every launch; modifications during the same build are not policed.
    from tlo_version import BUNDLE_BUILD
    desired = str(BUNDLE_BUILD)
    marker = dest / MSI_DATABASE_BUILD_MARKER
    current = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    missing = any(not (dest / name).is_file() for name in MSI_MANAGED_DATABASES)
    if current == desired and not missing:
        return
    for name in MSI_MANAGED_DATABASES:
        master = source / name
        if not master.is_file() or master.stat().st_size == 0:
            raise FileNotFoundError(f"MSI database master missing: {master}")
    # Never advance the build marker until all master database replacements
    # have completed. A partial write/lock failure retries on next launch.
    for name in MSI_MANAGED_DATABASES:
        _write_atomic_from_file(source / name, dest / name)
    _write_atomic_text(marker, desired + "\n")


def _validated_msi_home(value, program):
    """Accept existing or new writable folders; reject the program tree."""
    text = str(value or "").strip().strip('"')
    if not text:
        raise ValueError("TLOHome must not be empty")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        raise ValueError("TLOHome must be an absolute directory path")
    candidate = candidate.resolve()
    program = Path(program).resolve()
    if candidate == program or program in candidate.parents:
        raise ValueError("TLOHome must be outside the application installation directory")
    candidate.mkdir(parents=True, exist_ok=True)
    # A real write probe is safer than os.access on Windows and network shares.
    with tempfile.TemporaryFile(dir=candidate):
        pass
    return candidate


def _remember_msi_home(home):
    """Persist the selected folder without UAC and notify future processes."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MSI_USER_SETTINGS_KEY) as key:
        winreg.SetValueEx(key, "DataHome", 0, winreg.REG_SZ, str(home))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
        winreg.SetValueEx(key, "TLOHome", 0, winreg.REG_SZ, str(home))
    os.environ["TLOHome"] = str(home)
    # Windows' user environment registry changes do not update processes that
    # are already running. Broadcast to Explorer for newly launched processes.
    if sys.platform == "win32":
        try:
            import ctypes
            result = ctypes.c_size_t()
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000,
                ctypes.byref(result))
        except (AttributeError, OSError):
            pass


def ensure_msi_tlo_home():
    """Use installer-selected TLOHome, with a safe fallback for legacy installs."""
    program = msi_install_root()
    if program is None:
        return True
    import winreg
    configured = os.environ.get("TLOHome", "").strip()
    saved = ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MSI_USER_SETTINGS_KEY) as key:
            saved, _ = winreg.QueryValueEx(key, "DataHome")
    except OSError:
        pass
    last_error = ""
    for candidate in dict.fromkeys([configured, str(saved).strip()]):
        if not candidate:
            continue
        try:
            home = _validated_msi_home(candidate, program)
            _remember_msi_home(home)
            seed_msi_data_home(home)
            return True
        except (OSError, ValueError) as exc:
            last_error = str(exc)
    # Only legacy or invalid setups reach this fallback. New MSI installation
    # captures the folder in the installer and sets HKCU\Environment itself.
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    root = tk.Tk()
    root.withdraw()
    proposed = configured or saved or r"C:\.tlo"
    try:
        while True:
            if last_error:
                messagebox.showwarning("TLOHome folder", "The selected TLOHome folder is unavailable or not writable: "
                                       + last_error + "\nChoose another folder.", parent=root)
            chosen = simpledialog.askstring("TLOHome folder",
                        "Enter a writable folder for TLO preferences, inventory, and databases.",
                        initialvalue=proposed, parent=root)
            if chosen is None:
                return False
            proposed = chosen
            try:
                home = _validated_msi_home(chosen, program)
                _remember_msi_home(home)
                seed_msi_data_home(home)
                return True
            except (OSError, ValueError) as exc:
                last_error = str(exc)
    finally:
        root.destroy()


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
