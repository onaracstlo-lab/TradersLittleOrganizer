"""Build 597: official FFmpeg source resilience without weakening integrity gates."""
import hashlib
import io
import ssl
import urllib.error

import pytest
import ffmpeg_source_build as ff

pytestmark = pytest.mark.behavior


class InterruptedStream(io.BytesIO):
    def __init__(self, payload, exception):
        super().__init__(payload)
        self.exception = exception
        self.read_calls = 0

    def read(self, n=-1):
        self.read_calls += 1
        if self.read_calls > 1:
            raise self.exception
        return super().read(n)


def _pin(monkeypatch, payload):
    monkeypatch.setattr(ff, 'SOURCE_SHA256', hashlib.sha256(payload).hexdigest())
    delays = []
    monkeypatch.setattr(ff.time, 'sleep', delays.append)
    return delays


def test_reset_during_read_restarts_from_scratch_and_publishes_verified_cache(tmp_path, monkeypatch):
    payload = b'ffmpeg source archive for test'
    delays = _pin(monkeypatch, payload)
    calls = []

    def open_url(url, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            return InterruptedStream(b'broken partial', ConnectionResetError(54, 'reset'))
        return io.BytesIO(payload)

    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    output = ff.get_source(tmp_path)
    assert output.read_bytes() == payload
    assert calls == [(ff.SOURCE_URL, 90), (ff.SOURCE_URL, 90)]
    assert delays == [1]
    assert not list(tmp_path.glob('*.downloading'))
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('cache should not redownload'))
    assert ff.get_source(tmp_path) == output


def test_two_failed_primary_requests_fallback_to_official_www_hostname(tmp_path, monkeypatch):
    payload = b'good source archive'
    delays = _pin(monkeypatch, payload)
    hosts = []

    def open_url(url, timeout):
        hosts.append(url)
        if len(hosts) < 3:
            raise urllib.error.URLError(ConnectionResetError(54, 'reset'))
        return io.BytesIO(payload)

    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    assert ff.get_source(tmp_path).read_bytes() == payload
    assert hosts == [ff.SOURCE_URL, ff.SOURCE_URL, ff.SOURCE_FALLBACK_URL]
    assert delays == [1, 2]
    assert ff.SOURCE_FALLBACK_URL.startswith('https://www.ffmpeg.org/releases/')


def test_all_transient_attempts_exhaust_and_leave_no_cached_source(tmp_path, monkeypatch):
    delays = _pin(monkeypatch, b'good archive')
    hosts = []

    def open_url(url, timeout):
        hosts.append(url)
        raise urllib.error.URLError(ConnectionResetError(54, 'reset'))

    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    with pytest.raises(urllib.error.URLError):
        ff.get_source(tmp_path)
    assert len(hosts) == 5
    assert hosts == [ff.SOURCE_URL] * 2 + [ff.SOURCE_FALLBACK_URL] * 3
    assert delays == [1, 2, 4, 8]
    assert list(tmp_path.iterdir()) == []


def test_corrupted_download_fails_without_promoting_cache_or_retrying(tmp_path, monkeypatch):
    delays = _pin(monkeypatch, b'correct')
    attempts = []

    def open_url(url, timeout):
        attempts.append(url)
        return io.BytesIO(b'invalid')

    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(tmp_path)
    assert len(attempts) == 1
    assert delays == []
    assert list(tmp_path.iterdir()) == []


def test_corrupt_cached_archive_is_rejected_without_network(tmp_path, monkeypatch):
    _pin(monkeypatch, b'correct')
    (tmp_path / ff.SOURCE_NAME).write_bytes(b'corrupt')
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('no network for invalid cache'))
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(tmp_path)
    assert (tmp_path / ff.SOURCE_NAME).read_bytes() == b'corrupt'


@pytest.mark.parametrize('status, expected_attempts', [(404, 1), (503, 5), (429, 5)])
def test_retryable_and_permanent_http_errors(tmp_path, monkeypatch, status, expected_attempts):
    delays = _pin(monkeypatch, b'correct')
    calls = []

    def open_url(url, timeout):
        calls.append(url)
        raise urllib.error.HTTPError(url, status, 'HTTP error', {}, None)

    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    with pytest.raises(urllib.error.HTTPError):
        ff.get_source(tmp_path)
    assert len(calls) == expected_attempts
    assert len(delays) == expected_attempts - 1
    assert list(tmp_path.iterdir()) == []


def test_tls_certificate_error_is_not_retried(tmp_path, monkeypatch):
    delays = _pin(monkeypatch, b'correct')
    calls = []
    def open_url(url, timeout):
        calls.append(url)
        raise urllib.error.URLError(ssl.SSLCertVerificationError('invalid certificate'))
    monkeypatch.setattr(ff.urllib.request, 'urlopen', open_url)
    with pytest.raises(urllib.error.URLError):
        ff.get_source(tmp_path)
    assert len(calls) == 1
    assert delays == []


def test_download_budget_exceeded_fails_closed(tmp_path, monkeypatch):
    delays = _pin(monkeypatch, b'correct')
    monkeypatch.setattr(ff, 'MAX_SOURCE_DOWNLOAD_BYTES', 4)
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: io.BytesIO(b'oversized'))
    with pytest.raises(RuntimeError, match='allowed download size'):
        ff.get_source(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert delays == []


def test_local_filesystem_error_is_not_retried(tmp_path, monkeypatch):
    delays = _pin(monkeypatch, b'correct')
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: io.BytesIO(b'correct'))
    def no_replace(*_args):
        raise PermissionError('read only cache')
    monkeypatch.setattr(ff.os, 'replace', no_replace)
    with pytest.raises(PermissionError, match='read only cache'):
        ff.get_source(tmp_path)
    assert list(tmp_path.iterdir()) == []
    assert delays == []
