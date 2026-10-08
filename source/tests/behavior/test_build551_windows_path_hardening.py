"""Build 551: Windows device-name and trusted helper-path hardening."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_github_updates as GU
import tlo_security as SEC
import tlo_ux as UX

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "name",
    [
        "CON",
        "PRN.txt",
        "COM1",
        "LPT9.log",
        "COM¹.txt",
        "COM²",
        "COM³.bin",
        "LPT¹",
        "LPT².log",
        "LPT³.dat",
    ],
)
def test_build551_shared_windows_reserved_name_helper_covers_superscript_devices(name):
    assert SEC.windows_reserved_folder_name(name) is True


@pytest.mark.parametrize("name", ["COM⁴.txt", "LPT⁹.log", "XCOM¹.txt", "COM10", "LPT10"])
def test_build551_reserved_name_helper_does_not_overmatch(name):
    assert SEC.windows_reserved_folder_name(name) is False


@pytest.mark.parametrize("member", ["COM¹.txt", "folder/LPT².log", "folder/COM³.bin"])
def test_build551_zip_validation_rejects_superscript_windows_devices(member):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, b"x")
    payload.seek(0)
    with zipfile.ZipFile(payload, "r") as archive:
        with pytest.raises(ValueError, match="reserved Windows device name"):
            GU._validate_zip_members(archive)


def test_build551_zip_validation_uses_shared_reserved_name_helper(monkeypatch):
    seen = []

    def fake_reserved(name):
        seen.append(name)
        return name == "shared-helper-sentinel.txt"

    monkeypatch.setattr(GU, "windows_reserved_folder_name", fake_reserved)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("folder/shared-helper-sentinel.txt", b"x")
    payload.seek(0)
    with zipfile.ZipFile(payload, "r") as archive:
        with pytest.raises(ValueError, match="reserved Windows device name"):
            GU._validate_zip_members(archive)
    assert "shared-helper-sentinel.txt" in seen


def test_build551_windows_directory_comes_from_windows_api(monkeypatch):
    class FakeGetter:
        argtypes = None
        restype = None

        def __call__(self, buffer, size):
            value = r"C:\Windows"
            assert size > len(value)
            buffer.value = value
            return len(value)

    getter = FakeGetter()
    fake_kernel32 = SimpleNamespace(GetSystemWindowsDirectoryW=getter)
    monkeypatch.setattr(SEC.os, "name", "nt")
    monkeypatch.setattr(SEC.ctypes, "WinDLL", lambda *_a, **_k: fake_kernel32, raising=False)
    monkeypatch.setenv("SystemRoot", r"Z:\Untrusted")

    assert SEC.windows_directory_from_api() == r"C:\Windows"
    assert getter.argtypes == [SEC.ctypes.c_wchar_p, SEC.ctypes.c_uint]
    assert getter.restype is SEC.ctypes.c_uint


def test_build551_live_gui_opener_ignores_systemroot(monkeypatch, tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    calls = []
    monkeypatch.setattr(UX.os, "name", "nt")
    monkeypatch.setenv("SystemRoot", r"Z:\Untrusted")
    monkeypatch.setattr(UX, "windows_directory_from_api", lambda: r"C:\Windows")
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv))
    assert UX.open_path(str(folder)) is True
    assert calls == [[os.path.join(r"C:\Windows", "explorer.exe"), os.path.normpath(str(folder))]]
    assert all(r"Z:\Untrusted" not in argv[0] for argv in calls)


def test_build551_issue_open_path_ignores_systemroot_and_uses_api_directory(monkeypatch, tmp_path):
    target = tmp_path / "issue.txt"
    target.write_text("x", encoding="utf-8")
    calls = []

    monkeypatch.setattr(UX.os, "name", "nt")
    monkeypatch.setenv("SystemRoot", r"Z:\Untrusted")
    monkeypatch.setattr(UX, "windows_directory_from_api", lambda: r"C:\Windows")
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv) or SimpleNamespace())

    assert UX.open_path(str(target)) is True
    assert calls == [[os.path.join(r"C:\Windows", "explorer.exe"), "/select,", os.path.normpath(str(target))]]
    assert r"Z:\Untrusted" not in calls[0][0]


def test_build551_live_opener_windows_api_failure_fails_closed(monkeypatch, tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    calls = []
    monkeypatch.setattr(UX.os, "name", "nt")
    monkeypatch.setattr(UX, "windows_directory_from_api", lambda: (_ for _ in ()).throw(OSError("no API")))
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv))
    assert UX.open_path(str(folder)) is False
    assert calls == []


def test_build551_static_contract_has_no_systemroot_helper_trust():
    inventory_source = (ROOT / "tlo_inventory_update.py").read_text(encoding="utf-8")
    ux_source = (ROOT / "tlo_ux.py").read_text(encoding="utf-8")
    security_source = (ROOT / "tlo_security.py").read_text(encoding="utf-8")
    updater_source = (ROOT / "tlo_github_updates.py").read_text(encoding="utf-8")

    assert "SystemRoot" not in inventory_source
    assert "SystemRoot" not in ux_source
    assert "def open_paths(" not in inventory_source
    assert "windows_directory_from_api()" in ux_source
    assert "GetSystemWindowsDirectoryW" in security_source
    assert "windows_reserved_folder_name(part)" in updater_source
    assert "COM{i}" not in updater_source
    assert "LPT{i}" not in updater_source
