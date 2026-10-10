"""Offline source integrity and build-recipe policy tests."""
import io
import tarfile
import pytest

pytestmark = pytest.mark.behavior
import ffmpeg_source_build as src


def test_official_source_is_pinned():
    assert src.SOURCE_URL == 'https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz'
    assert len(src.SOURCE_SHA256) == 64
    assert 'enable-nonfree' not in ' '.join(src.CONFIGURE_FLAGS)
    assert 'enable-gpl' not in ' '.join(src.CONFIGURE_FLAGS)
    assert '--disable-everything' in src.CONFIGURE_FLAGS


def test_source_rejects_unsafe_archive_members(tmp_path):
    archive = tmp_path / 'source.tar.xz'
    with tarfile.open(archive, 'w:xz') as tar:
        data = b'not source'
        entry = tarfile.TarInfo('ffmpeg-9.0.2/../../escaped')
        entry.size = len(data)
        tar.addfile(entry, io.BytesIO(data))
    with pytest.raises(RuntimeError, match='safe extraction'):
        src.extract_source(archive, tmp_path / 'extract')


def test_source_rejects_symlinks(tmp_path):
    archive = tmp_path / 'source.tar.xz'
    with tarfile.open(archive, 'w:xz') as tar:
        item = tarfile.TarInfo('ffmpeg-9.0.2/configure')
        item.type = tarfile.SYMTYPE
        item.linkname = '/bin/bash'
        tar.addfile(item)
    with pytest.raises(RuntimeError, match='safe extraction'):
        src.extract_source(archive, tmp_path / 'extract')


def test_hash_gate_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(src, 'SOURCE_SHA256', '0' * 64)
    cached = tmp_path / src.SOURCE_NAME
    cached.write_bytes(b'unverified')
    with pytest.raises(RuntimeError, match='SHA-256'):
        src.get_source(tmp_path)


def test_audio_capability_manifest_complete():
    assert {'shorten', 'flac', 'ogg', 'mov', 'mp3', 'wav', 'ape', 'wv'} <= set(src.AUDIO_DEMUXERS)
    assert {'shorten', 'flac', 'aac', 'alac', 'opus', 'vorbis', 'ape', 'wavpack'} <= set(src.AUDIO_DECODERS)
    assert {'flac','null','framemd5'} <= set(src.AUDIO_MUXERS)
