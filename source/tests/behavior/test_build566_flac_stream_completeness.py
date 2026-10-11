"""Build 566: live FLAC decoded-sample completeness and fail-closed boundary."""
from __future__ import annotations

import shutil
import subprocess

import pytest
from mutagen.flac import FLAC

import tlo_corruption as corruption

pytestmark = pytest.mark.behavior


def _ffmpeg():
    executable = shutil.which("ffmpeg")
    if not executable:
        pytest.skip("real FFmpeg required for live FLAC regression")
    return executable


def _make_flac(tmp_path, seconds):
    ffmpeg = _ffmpeg()
    intact = tmp_path / f"intact-{seconds}.flac"
    subprocess.run(
        [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=230:duration={seconds}", "-c:a", "flac", "-y", str(intact)],
        check=True, timeout=30,
    )
    return intact, ffmpeg


@pytest.mark.parametrize("seconds", [4, 8, 11])
def test_build566_intact_and_truncated_real_flac_are_distinguished(tmp_path, seconds):
    intact, executable = _make_flac(tmp_path, seconds)
    truncated = tmp_path / "truncated.flac"
    original = intact.read_bytes()
    truncated.write_bytes(original[: len(original) // 2])
    # Both files still advertise the complete original sample count.
    assert FLAC(truncated).info.total_samples == FLAC(intact).info.total_samples > 0
    check = lambda path: corruption._deep_audio_stream_status(
        str(path), ffmpeg_executable=executable, cancel_check=lambda: False, timeout_seconds=30
    )
    assert check(intact) is True
    assert check(truncated) is False
    bad, unknown = corruption.classify_audio_paths([str(truncated)], deep_audio_check=False)
    assert bad == [] and unknown == []  # ordinary header validation is unchanged
    # No header-only classification side effects; full checks opt in.


def test_build566_real_frame_aligned_truncation_in_classification(tmp_path, monkeypatch):
    intact, executable = _make_flac(tmp_path, 8)
    partial = tmp_path / "partial.flac"
    data = intact.read_bytes()
    partial.write_bytes(data[: len(data) // 2])
    monkeypatch.setattr(corruption, "bundled_ffmpeg_executable", lambda: executable)
    bad, unknown = corruption.classify_audio_paths([str(partial)], deep_audio_check=True)
    assert bad == [str(partial)]
    assert unknown == []
    assert intact.exists() and partial.exists()  # classification never removes anything


def test_build585_missing_stored_md5_is_corrupt(monkeypatch, tmp_path):
    intact, executable = _make_flac(tmp_path, 8)
    data = bytearray(intact.read_bytes())
    data[26:42] = bytes(16)
    intact.write_bytes(data)
    assert corruption._deep_audio_stream_status(
        str(intact), ffmpeg_executable=executable, cancel_check=lambda: False
    ) is False
    monkeypatch.setattr(corruption, "bundled_ffmpeg_executable", lambda: executable)
    monkeypatch.setattr(corruption, "_validate_tag_write_round_trip", lambda path: None)
    bad, unknown = corruption.classify_audio_paths([str(intact)], deep_audio_check=True)
    assert bad == [str(intact)] and unknown == []


def test_build566_failed_decoder_is_not_misclassified_as_corruption(tmp_path):
    intact, _executable = _make_flac(tmp_path, 8)
    assert corruption._deep_audio_stream_status(
        str(intact), ffmpeg_executable=str(tmp_path / "missing-ffmpeg"),
        cancel_check=lambda: False
    ) is None


def test_build566_cancel_before_decoder_completion_is_unverifiable(tmp_path):
    intact, executable = _make_flac(tmp_path, 8)
    assert corruption._deep_audio_stream_status(
        str(intact), ffmpeg_executable=executable,
        cancel_check=lambda: True, timeout_seconds=30
    ) is None


def test_build585_incomplete_pcm_hash_data_is_corrupt():
    from io import BytesIO
    from tlo_flac_fingerprint import _fingerprint_from_pcm, FingerprintCorrupt
    with pytest.raises(FingerprintCorrupt):
        _fingerprint_from_pcm(BytesIO(b""), 16, 16, 1)
    with pytest.raises(FingerprintCorrupt):
        _fingerprint_from_pcm(BytesIO(b"\x00"), 16, 16, 1)
    with pytest.raises(FingerprintCorrupt):
        _fingerprint_from_pcm(BytesIO(b"\x00\x00\x00\x00"), 16, 16, 3)


def test_build566_non_flac_continues_to_use_original_decoder_contract(tmp_path):
    flac, executable = _make_flac(tmp_path, 4)
    mp3 = tmp_path / "track.mp3"
    subprocess.run([executable, "-nostdin", "-v", "error", "-i", str(flac), "-c:a", "libmp3lame", "-y", str(mp3)],
                   check=True, timeout=30)
    assert corruption._deep_audio_stream_status(
        str(mp3), ffmpeg_executable=executable, cancel_check=lambda: False,
    ) is True
