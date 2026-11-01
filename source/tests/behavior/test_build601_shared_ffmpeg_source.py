"""Build 601: native FFmpeg source archive is transferred once, verified, and used offline."""
import hashlib
import io
from pathlib import Path

import pytest

import ffmpeg_source_build as ff

pytestmark = pytest.mark.behavior


def _source(tmp_path, monkeypatch, payload=b'verified upstream ffmpeg archive'):
    upstream = tmp_path / 'shared' / ff.SOURCE_NAME
    upstream.parent.mkdir(parents=True)
    upstream.write_bytes(payload)
    monkeypatch.setenv('TLO_FFMPEG_SOURCE_ARCHIVE', str(upstream))
    monkeypatch.setattr(ff, 'SOURCE_SHA256', hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(ff.urllib.request, 'urlopen', lambda *_a, **_k: pytest.fail('CI must not make an upstream request'))
    return upstream, tmp_path / 'build-cache'


def test_valid_shared_source_copies_to_compilation_and_license_cache(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    destination = ff.get_source(cache)
    assert destination == cache / ff.SOURCE_NAME
    assert destination.read_bytes() == supplied.read_bytes()
    assert destination != supplied
    assert not list(cache.glob('*.downloading'))
    assert ff.get_source(cache) == destination


def test_shared_source_missing_aborts_without_network(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    supplied.unlink()
    with pytest.raises(RuntimeError, match='CI FFmpeg source artifact'):
        ff.get_source(cache)
    assert not (cache / ff.SOURCE_NAME).exists()


def test_shared_source_corrupt_aborts_without_network(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    supplied.write_bytes(b'tampered archive')
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(cache)
    assert not (cache / ff.SOURCE_NAME).exists()


def test_shared_source_misnamed_aborts_without_network(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    renamed = supplied.with_name('ffmpeg-unpinned.tar.xz')
    supplied.rename(renamed)
    monkeypatch.setenv('TLO_FFMPEG_SOURCE_ARCHIVE', str(renamed))
    with pytest.raises(RuntimeError, match='misnamed'):
        ff.get_source(cache)


def test_shared_source_oversized_aborts_without_network(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    monkeypatch.setattr(ff, 'MAX_SOURCE_DOWNLOAD_BYTES', supplied.stat().st_size - 1)
    with pytest.raises(RuntimeError, match='oversized'):
        ff.get_source(cache)


def test_shared_source_does_not_accept_valid_old_cache_if_new_artifact_invalid(tmp_path, monkeypatch):
    supplied, cache = _source(tmp_path, monkeypatch)
    cache.mkdir()
    (cache / ff.SOURCE_NAME).write_bytes(supplied.read_bytes())
    supplied.write_bytes(b'bad new artifact')
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(cache)


def test_corrupted_cache_rejected_even_with_valid_shared_artifact(tmp_path, monkeypatch):
    _, cache = _source(tmp_path, monkeypatch)
    cache.mkdir()
    (cache / ff.SOURCE_NAME).write_bytes(b'bad cache')
    with pytest.raises(RuntimeError, match='SHA-256 mismatch'):
        ff.get_source(cache)


def test_local_mode_still_fetches_verified_upstream(tmp_path, monkeypatch):
    payload = b'normal verified local build source'
    monkeypatch.delenv('TLO_FFMPEG_SOURCE_ARCHIVE', raising=False)
    monkeypatch.setattr(ff, 'SOURCE_SHA256', hashlib.sha256(payload).hexdigest())
    calls = []
    def urlopen(url, timeout):
        calls.append(url)
        return io.BytesIO(payload)
    monkeypatch.setattr(ff.urllib.request, 'urlopen', urlopen)
    assert ff.get_source(tmp_path).read_bytes() == payload
    assert calls == [ff.SOURCE_URL]


def test_failed_cache_copy_does_not_promote_partial_source(tmp_path, monkeypatch):
    _, cache = _source(tmp_path, monkeypatch)
    def bad_copy(*args):
        Path(args[1]).write_bytes(b'partial')
    monkeypatch.setattr(ff.shutil, 'copyfile', bad_copy)
    with pytest.raises(RuntimeError, match='copied source SHA-256 mismatch'):
        ff.get_source(cache)
    assert not (cache / ff.SOURCE_NAME).exists()
    assert not list(cache.iterdir())
