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


def seed_msi_data_home(home):
    """Copy missing DB master files only; never overwrite existing inventory data."""
    program = msi_install_root()
    if program is None:
        return
    source = program / "TLO_DBs"
    dest = Path(home) / "TLO_DBs"
    dest.mkdir(exist_ok=True, parents=True)
    import shutil
    for name in ("TLO-FAQ.txt", "tlo-preferences.ini"):
        existing = Path(home) / name
        if not existing.exists():
            original = program / name
            if original.is_file():
                try:
                    with original.open("rb") as reader, existing.open("xb") as writer:
                        shutil.copyfileobj(reader, writer)
                except FileExistsError:
                    pass
    for name in ("artists.sqlite", "venues.txt", "cities.csv"):
        base = source / name
        output = dest / name
        if not output.exists():
            if not base.is_file():
                raise FileNotFoundError(f"MSI database master missing: {base}")
            # Exclusive create ensures user data never gets overwritten if another
            # instance seeded the same TLOHome concurrently.
            try:
                with base.open("rb") as reader, output.open("xb") as writer:
                    shutil.copyfileobj(reader, writer)
            except FileExistsError:
                continue


def ensure_msi_tlo_home():
    """Ask on first MSI run for a persistent TLOHome OUTSIDE installer-owned files."""
    if not is_msi_install():
        return True
    configured = os.environ.get("TLOHome", "").strip()
    if configured:
        if Path(configured).is_dir():
            seed_msi_data_home(Path(configured).resolve())
        return True
    import winreg
    # Keep DataHome separate from the MSI-owned Installer registry values so
    # major upgrades, repairs and uninstall cannot erase the user's choice.
    key_path = r"Software\TradersLittleOrganizer\UserSettings"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            saved, _ = winreg.QueryValueEx(key, "DataHome")
        if Path(saved).is_dir():
            seed_msi_data_home(Path(saved).resolve())
            os.environ["TLOHome"] = str(Path(saved).resolve())
            return True
    except (OSError, ValueError):
        pass
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showinfo("TLO first-run setup",
            "Select your existing TLOHome folder, or create a new one in the chooser. "
            "Your inventory and preferences stay outside the installed program folder.", parent=root)
        path = filedialog.askdirectory(parent=root, title="Select TLOHome", mustexist=True)
        if not path:
            return False
        home = Path(path).resolve()
        program = msi_install_root()
        if not home.is_dir() or (program and (home == program or program in home.parents)):
            messagebox.showerror("TLO first-run setup", "Choose a folder outside the application install directory.", parent=root)
            return False
        if not os.access(home, os.W_OK):
            messagebox.showerror("TLO first-run setup", "TLOHome must be writable.", parent=root)
            return False
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DataHome", 0, winreg.REG_SZ, str(home))
        seed_msi_data_home(home)
        os.environ["TLOHome"] = str(home)
        return True
    finally:
        root.destroy()


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
