"""Build 610: independent source failover with immutable hash and bounded outage."""
import hashlib
import io
import ssl
import urllib.error

import pytest

import ffmpeg_source_build as ff

pytestmark = pytest.mark.behavior


def _test_pin(monkeypatch, data):
    monkeypatch.delenv('TLO_FFMPEG_SOURCE_ARCHIVE', raising=False)
    monkeypatch.setattr(ff, 'SOURCE_SHA256', hashlib.sha256(data).hexdigest())
    sleeps = []
    monkeypatch.setattr(ff.time, 'sleep', sleeps.append)
    return sleeps


def test_canonical_official_mirror_round_robin_and_cache(tmp_path, monkeypatch):
    payload = b'source archive known pinned bytes'
    delays = _test_pin(monkeypatch, payload)
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if len(calls) < 3:
            raise urllib.error.URLError(TimeoutError('origin not responding'))
        return io.BytesIO(payload)

    monkeypatch.setattr(ff.urllib.request, 'urlopen', fake_urlopen)
    got = ff.get_source(tmp_path)
    assert got.read_bytes() == payload
    assert [url for url, _ in calls] == [ff.SOURCE_URL, ff.SOURCE_FALLBACK_URL, ff.SOURCE_MIRROR_URL]
    assert [timeout for _, timeout in calls] == [ff.SOURCE_SOCKET_TIMEOUT_SECONDS] * 3
    assert delays == [1, 2]
    assert ff.sha256(got) == ff.SOURCE_SHA256
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('cache hit should not download'))
    assert ff.get_source(tmp_path) == got


def test_all_outages_have_actionable_error_and_never_publish(tmp_path, monkeypatch):
    _test_pin(monkeypatch, b'expected')
    names = []

    def fake_urlopen(url, timeout):
        names.append(url)
        raise urllib.error.URLError(TimeoutError('connection timed out'))

    monkeypatch.setattr(ff.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(RuntimeError, match='failed after 6 network attempts across 3 hosts') as exc:
        ff.get_source(tmp_path)
    assert 'Required SHA-256:' in str(exc.value)
    assert names == list(ff.SOURCE_DOWNLOAD_URLS)
    assert not (tmp_path / ff.SOURCE_NAME).exists()
    assert not list(tmp_path.glob('*.downloading'))


def test_mirror_checksum_mismatch_does_not_promote(tmp_path, monkeypatch):
    expected = b'expected archive'
    sleeps = _test_pin(monkeypatch, expected)
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        if url != ff.SOURCE_MIRROR_URL:
            raise urllib.error.URLError(TimeoutError('origin down'))
        return io.BytesIO(b'corrupt from mirror')

    monkeypatch.setattr(ff.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(tmp_path)
    assert calls == list(ff.SOURCE_DOWNLOAD_URLS[:3])
    assert sleeps == [1, 2]
    assert not (tmp_path / ff.SOURCE_NAME).exists()


def test_corrupt_github_cache_fails_without_redownloading(tmp_path, monkeypatch):
    _test_pin(monkeypatch, b'expected')
    (tmp_path / ff.SOURCE_NAME).write_bytes(b'corrupt restored cache')
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('cache tamper must fail closed'))
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(tmp_path)


def test_bad_tls_certificate_stops_without_using_other_hosts(tmp_path, monkeypatch):
    _test_pin(monkeypatch, b'correct')
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        raise urllib.error.URLError(ssl.SSLCertVerificationError('bad certificate'))

    monkeypatch.setattr(ff.urllib.request, 'urlopen', fake_urlopen)
    with pytest.raises(urllib.error.URLError):
        ff.get_source(tmp_path)
    assert calls == [ff.SOURCE_URL]


def test_explicit_ci_shared_archive_remains_network_free(tmp_path, monkeypatch):
    payload = b'expected archive'
    _test_pin(monkeypatch, payload)
    shared = tmp_path / 'shared' / ff.SOURCE_NAME
    shared.parent.mkdir()
    shared.write_bytes(payload)
    monkeypatch.setenv('TLO_FFMPEG_SOURCE_ARCHIVE', str(shared))
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('native CI must never download'))
    assert ff.get_source(tmp_path / 'native').read_bytes() == payload
