"""Build 549: small robustness fixes from the Build 540 review."""

from __future__ import annotations
from tests._release_artifacts import release_history

import importlib.util
import io
import os
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_etree_lookup as etree
import tlo_locking as locking
import tlo_network_io as network_io
import tlo_setlistfm_lookup as setlistfm
from tests import _release_artifacts as release_artifacts

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_delete_dupes():
    path = ROOT / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build549", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build549_etree_textual_date_rejects_oversized_day_without_overflow():
    assert etree.normalize_etree_date('x April 19702026202613 2026') is None
    assert etree.normalize_etree_date('19702026202613 April 2026') is None
    assert etree.normalize_etree_date('April 13 2026') == '2026-04-13'
    assert etree.normalize_etree_date('13 April 2026') == '2026-04-13'


def test_build549_etree_oversized_http_error_body_stays_etree_error(monkeypatch):
    error = urllib.error.HTTPError(
        etree.GRAPHQL_URL,
        502,
        "Bad Gateway",
        hdrs=None,
        fp=io.BytesIO(b"x" * (network_io.MAX_ERROR_RESPONSE_BYTES + 1)),
    )
    monkeypatch.setattr(etree.urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(error))
    with pytest.raises(etree.ETreeDBError, match=r"HTTP 502 from eTreeDB GraphQL$"):
        etree.graphql_request("query { x }", {})


def test_build549_setlistfm_oversized_http_error_body_stays_domain_error(monkeypatch):
    error = urllib.error.HTTPError(
        f"{setlistfm.API_BASE}/search/setlists",
        429,
        "Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(b"x" * (network_io.MAX_ERROR_RESPONSE_BYTES + 1)),
    )
    monkeypatch.setattr(setlistfm, "wait_for_rate_limit", lambda *_a, **_k: None)
    monkeypatch.setattr(setlistfm.urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(error))
    with pytest.raises(setlistfm.SetlistFMError, match=r"HTTP 429 Too Many Requests$"):
        setlistfm.api_get("/search/setlists", {}, "key")


def test_build549_delete_dupes_missing_return_code_is_unverifiable_and_locale_is_stable(tmp_path):
    module = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    seen = {}

    def fake_run(_command, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=None, stderr="")

    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=fake_run) is None
    assert seen["env"]["LC_ALL"] == "C"


def test_build549_lock_probe_does_not_create_or_modify_lock_file(tmp_path):
    missing = tmp_path / "missing-parent" / "operation.lock"
    assert locking.lock_is_held(str(missing)) is False
    assert not missing.exists()
    assert not missing.parent.exists()

    existing = tmp_path / "existing.lock"
    existing.write_bytes(b"")
    before_stat = existing.stat()
    assert locking.lock_is_held(str(existing)) is False
    assert existing.read_bytes() == b""
    after_stat = existing.stat()
    assert after_stat.st_size == before_stat.st_size == 0


def test_build549_owned_lock_retries_brief_probe_collision(monkeypatch, tmp_path):
    path = tmp_path / "retry.lock"
    calls = []
    original = locking._lock_file

    def flaky(handle, *, blocking=False):
        calls.append(blocking)
        if len(calls) == 1:
            return False
        return original(handle, blocking=blocking)

    monkeypatch.setattr(locking, "_lock_file", flaky)
    monkeypatch.setattr(locking.time, "sleep", lambda _seconds: None)
    assert locking.acquire_owned_lock(str(path), {"pid": os.getpid()}) is True
    try:
        assert len(calls) >= 2
    finally:
        locking.release_owned_lock(str(path))


def test_build549_version_and_documentation_contract():
    assert (ROOT / release_artifacts.REQUIREMENTS_FILENAME).is_file()
    assert (ROOT / release_artifacts.MANUAL_FILENAME).is_file()
    assert "Build 549 - " in release_history()


def test_build549_requirements_record_the_robustness_contracts():
    from docx import Document

    doc = Document(ROOT / release_artifacts.REQUIREMENTS_FILENAME)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Build 549: robustness closure" in text
    assert "missing validator return code is validator-infrastructure failure" in text
    assert "Lock-status probes must not create directories or modify lock-file contents" in text
    assert "oversized HTTP error body must still be reported as an eTreeDB lookup error" in text
    assert "Oversized HTTP error bodies must remain contained within the setlist.fm lookup error boundary" in text
