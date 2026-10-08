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


def test_build566_unknown_declared_flac_sample_count_is_unverifiable(monkeypatch, tmp_path):
    intact, executable = _make_flac(tmp_path, 8)
    monkeypatch.setattr(corruption, "_flac_declared_sample_total", lambda _path: None)
    assert corruption._deep_audio_stream_status(
        str(intact), ffmpeg_executable=executable, cancel_check=lambda: False
    ) is None
    monkeypatch.setattr(corruption, "bundled_ffmpeg_executable", lambda: executable)
    bad, unknown = corruption.classify_audio_paths([str(intact)], deep_audio_check=True)
    assert bad == [] and len(unknown) == 1


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


def test_build566_bad_or_missing_framehash_is_unverifiable(tmp_path):
    intact, executable = _make_flac(tmp_path, 8)
    from tempfile import TemporaryFile
    with TemporaryFile() as stream:
        stream.write(b"#tb 0: 1/44100\n#codec_id 0: pcm_s16le\n")
        assert corruption._flac_decoded_sample_total(stream, 44100) is None
    with TemporaryFile() as stream:
        stream.write(b"#tb 0: 1/44100\n#codec_id 0: pcm_s16le\n0, 0, 0, missing, 2, ff\n")
        assert corruption._flac_decoded_sample_total(stream, 44100) is None
    with TemporaryFile() as stream:
        stream.write(b"#tb 0: 1/48000\n#codec_id 0: pcm_s16le\n0, 0, 0, 99, 198, ff\n")
        assert corruption._flac_decoded_sample_total(stream, 44100) is None


def test_build566_non_flac_continues_to_use_original_decoder_contract(tmp_path):
    flac, executable = _make_flac(tmp_path, 4)
    mp3 = tmp_path / "track.mp3"
    subprocess.run([executable, "-nostdin", "-v", "error", "-i", str(flac), "-c:a", "libmp3lame", "-y", str(mp3)],
                   check=True, timeout=30)
    assert corruption._deep_audio_stream_status(
        str(mp3), ffmpeg_executable=executable, cancel_check=lambda: False,
    ) is True
