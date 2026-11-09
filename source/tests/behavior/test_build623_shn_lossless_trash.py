"""Build 623 SHN verification and non-destructive failure policy."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_tag_lib as tag

pytestmark = pytest.mark.behavior


def _fake_conversion(monkeypatch, source, fingerprints=None, trash=None, errors=""):
    calls = []
    monkeypatch.setattr(tag, "_bundled_ffmpeg_executable", lambda: "/app/ffmpeg")

    def run(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"fake output")
        return SimpleNamespace(returncode=0, stderr=errors, stdout="")

    monkeypatch.setattr(tag.subprocess, "run", run)
    values = iter(fingerprints or [("0123456789abcdef0123456789abcdef", 4000)] * 2)
    monkeypatch.setattr(tag, "_verified_pcm_fingerprint", lambda *args: next(values))
    monkeypatch.setattr(tag, "_trash_converted_shn_original", trash or (lambda s: Path(s).unlink()))
    return calls


def test_matching_pcm_verified_then_original_trashed(tmp_path, monkeypatch):
    src = tmp_path / "song.shn"
    src.write_bytes(b"original")
    calls = _fake_conversion(monkeypatch, src)
    log = []
    target = tag.convert_shn_to_flac(str(src), emit=log.append)
    assert Path(target).exists() and not src.exists()
    assert "-xerror" in calls[0] and "-v" in calls[0]
    assert "verified_pcm_md5=" in log[0] and "original=Trash" in log[0]


@pytest.mark.parametrize("fingerprints", [
    [("a", 4000), ("b", 4000)],
    [("a", 4000), ("a", 3996)],
])
def test_different_pcm_or_length_keeps_shn(tmp_path, monkeypatch, fingerprints):
    src = tmp_path / "song.shn"
    src.write_bytes(b"original")
    trash = []
    _fake_conversion(monkeypatch, src, fingerprints, trash=lambda _s: trash.append(True))
    with pytest.raises(tag.TaggerError, match="PCM mismatch"):
        tag.convert_shn_to_flac(str(src))
    assert src.read_bytes() == b"original"
    assert not (tmp_path / "song.flac").exists()
    assert not trash


def test_decoder_error_keeps_shn(tmp_path, monkeypatch):
    src = tmp_path / "song.shn"
    src.write_bytes(b"original")
    monkeypatch.setattr(tag, "_bundled_ffmpeg_executable", lambda: "/app/ffmpeg")
    def bad_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"partial")
        return SimpleNamespace(returncode=0, stderr="invalid sample found", stdout="")
    monkeypatch.setattr(tag.subprocess, "run", bad_run)
    with pytest.raises(tag.TaggerError, match="failed"):
        tag.convert_shn_to_flac(str(src))
    assert src.exists() and not (tmp_path / "song.flac").exists()


def test_trash_and_holding_failure_rolls_back_flac(tmp_path, monkeypatch):
    src = tmp_path / "song.shn"
    src.write_bytes(b"original")
    def fail_trash(_s):
        raise OSError("Trash unavailable")
    _fake_conversion(monkeypatch, src, trash=fail_trash)
    # An injected test callback bypasses the real Trash->holding fallback.
    with pytest.raises(OSError, match="Trash unavailable"):
        tag.convert_shn_to_flac(str(src))
    assert src.exists() and not (tmp_path / "song.flac").exists()


def test_verification_failure_does_not_touch_source(tmp_path, monkeypatch):
    src = tmp_path / "song.shn"
    src.write_bytes(b"original")
    _fake_conversion(monkeypatch, src)
    def decoder(*_args):
        raise tag.TaggerError("unverifiable")
    monkeypatch.setattr(tag, "_verified_pcm_fingerprint", decoder)
    with pytest.raises(tag.TaggerError, match="unverifiable"):
        tag.convert_shn_to_flac(str(src))
    assert src.exists() and not (tmp_path / "song.flac").exists()
