from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import tlo_etree_lookup as ET
import tlo_setlistfm_lookup as SFM

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build537_setlistfm_api_key_is_unredirected(monkeypatch, tmp_path):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _amount=-1):
            return b'{}'

    def fake_urlopen(request, timeout=0):
        captured["request"] = request
        return Response()

    monkeypatch.setattr(SFM, "wait_for_rate_limit", lambda *a, **k: 1)
    monkeypatch.setattr(SFM.urllib.request, "urlopen", fake_urlopen)
    assert SFM.api_get("/search/setlists", {"artistName": "X"}, "secret-key", tlo_home=str(tmp_path)) == {}
    request = captured["request"]
    assert all(key.casefold() != "x-api-key" for key in request.headers)
    assert any(key.casefold() == "x-api-key" and value == "secret-key" for key, value in request.unredirected_hdrs.items())


def test_build537_etreedb_non_object_json_is_wrapped(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _amount=-1):
            return b'[]'

    monkeypatch.setattr(ET.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(ET.ETreeDBError, match="JSON was not an object"):
        ET.graphql_request("query X { x }", {})


def test_build537_gui_open_path_uses_trusted_windows_directory(monkeypatch, tmp_path):
    import tlo_ux as UX
    folder = tmp_path / "folder"
    folder.mkdir()
    calls = []
    monkeypatch.setattr(UX.os, "name", "nt")
    monkeypatch.setattr(UX, "windows_directory_from_api", lambda: r"C:\\Windows")
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv))
    assert UX.open_path(str(folder)) is True
    assert calls == [[os.path.join(r"C:\\Windows", "explorer.exe"), os.path.normpath(str(folder))]]


def test_build537_rate_limit_lock_is_file_and_releases_without_removal(tmp_path):
    lock_path = SFM._rate_limit_lock_dir(str(tmp_path))
    SFM._acquire_rate_limit_lock(lock_path, stale_after=0.0, timeout_seconds=1.0)
    try:
        assert os.path.isfile(lock_path)
        assert not os.path.isdir(lock_path)
        assert SFM.acquire_owned_lock(lock_path, {"pid": 999}) is False
    finally:
        assert SFM.release_owned_lock(lock_path) is True
    assert os.path.isfile(lock_path)
    assert SFM.acquire_owned_lock(lock_path, {"pid": 999}) is True
    assert SFM.release_owned_lock(lock_path) is True


def test_build537_tkinter_missing_collection_skips_cleanly(tmp_path):
    blocker = tmp_path / "tkinter.py"
    blocker.write_text('raise ModuleNotFoundError("No module named \\\'tkinter\\\'")\n', encoding="utf-8")
    env = os.environ.copy()
    env.pop("DISPLAY", None)
    env.pop("CI", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/behavior/test_build469_gui_tag_and_controls.py",
            "tests/behavior/test_build501_review_remediation.py",
            "tests/unit/test_build432_bounded_traversal_and_io.py",
            "tests/behavior/test_build537_portability_robustness.py::test_build537_etreedb_non_object_json_is_wrapped",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert "1 passed, 3 skipped" in completed.stdout
