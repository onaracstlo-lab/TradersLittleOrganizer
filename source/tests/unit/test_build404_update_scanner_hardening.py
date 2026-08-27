"""Build 404 updater and scanner hardening regressions."""
__version__ = "v411"

import hashlib
import importlib.util
from pathlib import Path
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.unit


def _load_scanner():
    import importlib
    import scan_release_artifacts
    return importlib.reload(scan_release_artifacts)


def test_windows_custom_scanner_path_is_not_interpolated_into_cmd_text():
    S = _load_scanner()
    path = Path(r"C:\Build 100% & artifacts")
    command, env = S._custom_scanner_command("scanner.exe {path}", path, windows=True)
    assert str(path) not in command
    assert command == 'scanner.exe "%TLO_SCAN_ARTIFACT_PATH%"'
    assert env["TLO_SCAN_ARTIFACT_PATH"] == str(path)


def test_redirect_handler_rejects_non_github_destination():
    import tlo_github_updates as U
    handler = U._GitHubOnlyRedirectHandler()
    req = urllib.request.Request("https://github.com/a/b/file.zip")
    with pytest.raises(urllib.error.HTTPError, match="outside the GitHub"):
        handler.redirect_request(req, None, 302, "Found", {}, "https://evil.example/payload.zip")


def test_missing_digest_fails_closed_before_download(tmp_path, monkeypatch):
    import tlo_github_updates as U
    monkeypatch.setattr(U, "_open_download_url", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("network")))
    asset = {"name":"TLO.zip", "browser_download_url":"https://github.com/a/b/TLO.zip", "size":3}
    with pytest.raises(ValueError, match="SHA-256 digest"):
        U._download_asset(asset, tmp_path / "TLO.zip")


def test_existing_file_without_digest_is_not_accepted(tmp_path):
    import tlo_github_updates as U
    path = tmp_path / "TLO.zip"; path.write_bytes(b"abc")
    assert U._file_matches_asset(path, {"size":3}) is False


def test_valid_digest_download_is_verified_and_committed(tmp_path, monkeypatch):
    import tlo_github_updates as U
    payload=b"abc"
    class Response:
        headers={"Content-Length": str(len(payload))}
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,_n):
            if getattr(self,"done",False): return b""
            self.done=True; return payload
    monkeypatch.setattr(U, "_open_download_url", lambda *_a, **_k: Response())
    asset={"name":"TLO.zip","browser_download_url":"https://github.com/a/b/TLO.zip","size":3,"digest":"sha256:"+hashlib.sha256(payload).hexdigest()}
    dest=tmp_path/"TLO.zip"
    assert U._download_asset(asset,dest) is True
    assert dest.read_bytes()==payload
