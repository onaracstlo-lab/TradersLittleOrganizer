"""Build 585: opt-in tag-first corruption and full FLAC audio MD5 regression."""
from __future__ import annotations

import errno
import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.flac import FLAC

import tlo_corruption as C
from tlo_flac_fingerprint import FingerprintCorrupt, FingerprintUnverifiable, verify_flac_fingerprint

pytestmark = pytest.mark.behavior


@pytest.fixture
def ffmpeg():
    tool = shutil.which('ffmpeg')
    if not tool:
        pytest.skip('native FFmpeg not available')
    return tool


@pytest.fixture
def flac_tool():
    tool = shutil.which('flac')
    if not tool:
        pytest.skip('FLAC test-fixture encoder unavailable')
    return tool


def _make_flac(tmp_path: Path, bits: int, flac_tool: str) -> Path:
    import random
    rnd = random.Random(bits)
    bps = bits // 8
    raw = tmp_path / f'{bits}.raw'
    samples = [rnd.randrange(-2**(bits-2), 2**(bits-2)) for _ in range(3007)]
    raw.write_bytes(b''.join(v.to_bytes(bps, 'little', signed=True) for v in samples))
    path = tmp_path / f'{bits}.flac'
    subprocess.run([flac_tool, '-f', '--silent', '--force-raw-format', '--endian=little',
                    '--sign=signed', '--channels=1', f'--bps={bits}', '--sample-rate=44100',
                    '-o', str(path), str(raw)], check=True, timeout=25)
    return path


@pytest.mark.parametrize('bits', [8, 16, 24, 32])
def test_flac_md5_matches_native_encoder_all_supported_byte_depths(tmp_path, bits, ffmpeg, flac_tool):
    path = _make_flac(tmp_path, bits, flac_tool)
    assert verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20)


def test_corruption_detected_by_md5_not_just_decoder_exit(tmp_path, ffmpeg, flac_tool):
    path = _make_flac(tmp_path, 24, flac_tool)
    payload = bytearray(path.read_bytes())
    assert payload[:4] == b'fLaC'
    assert payload[26:42] != bytes(16)
    payload[26] ^= 0x7f
    path.write_bytes(payload)
    with pytest.raises(FingerprintCorrupt, match='fingerprint mismatch'):
        verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20)
    assert C._deep_audio_stream_status(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False) is False


def test_missing_md5_fails_even_when_audio_decodes(tmp_path, ffmpeg, flac_tool):
    path = _make_flac(tmp_path, 16, flac_tool)
    data = bytearray(path.read_bytes())
    data[26:42] = bytes(16)
    path.write_bytes(data)
    with pytest.raises(FingerprintCorrupt, match='missing'):
        verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20)


def test_truncated_audio_and_inaccurate_sample_count_rejected(tmp_path, ffmpeg, flac_tool):
    path = _make_flac(tmp_path, 16, flac_tool)
    original = path.read_bytes()
    # STREAMINFO total_samples occupies low 36 bits of bytes 18..25.
    bad_count = bytearray(original)
    bad_count[25] ^= 1
    path.write_bytes(bad_count)
    with pytest.raises(FingerprintCorrupt, match='sample count mismatch'):
        verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20)
    path.write_bytes(original[:len(original)//2])
    with pytest.raises(FingerprintCorrupt):
        verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20)


def test_cancel_and_missing_decoder_are_never_corrupt(tmp_path, ffmpeg, flac_tool):
    path = _make_flac(tmp_path, 16, flac_tool)
    with pytest.raises(FingerprintUnverifiable, match='missing|infrastructure'):
        verify_flac_fingerprint(path, ffmpeg_executable=str(tmp_path/'absent'), cancel_check=lambda: False)
    with pytest.raises(FingerprintUnverifiable, match='cancelled'):
        verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg, cancel_check=lambda: True)


def test_no_trigger_never_opens_audio_or_calls_tag_checker(monkeypatch, tmp_path):
    path = tmp_path/'junk.flac';path.write_bytes(b'not a FLAC')
    monkeypatch.setattr(C, '_preflight_audio_read', lambda _: pytest.fail('no inspection without opt-in'))
    monkeypatch.setattr(C, 'group_audio_snapshot', lambda _: pytest.fail('no scan without opt-in'))
    assert C.classify_audio_paths([str(path)]) == ([], [])
    decision = C.assess_group_corruption({'music_dirs':[str(tmp_path)]}, 'delete', 'threshold', 1)
    assert decision.action == 'none' and not decision.audio_files and not decision.corrupt_files


def test_tag_failure_short_circuits_decode(monkeypatch, tmp_path):
    path = tmp_path/'bad.flac';path.write_bytes(b'data')
    monkeypatch.setattr(C, '_validate_tag_write_round_trip', lambda _: (_ for _ in ()).throw(ValueError('bad tag container')))
    monkeypatch.setattr(C, '_deep_audio_stream_status', lambda _: pytest.fail('tag failed: must not decode'))
    assert C.classify_audio_paths([str(path)], deep_audio_check=True) == ([str(path)], [])


def test_deep_without_real_tagging_still_probes_and_restores(monkeypatch, tmp_path):
    path = tmp_path/'ok.flac';path.write_bytes(b'data')
    seen=[]
    monkeypatch.setattr(C,'_validate_tag_write_round_trip',lambda p: seen.append(('probe',p)))
    monkeypatch.setattr(C,'_deep_audio_stream_status',lambda p: seen.append(('deep',p)) or True)
    assert C.classify_audio_paths([str(path)], check_tag_write=False,deep_audio_check=True)==([],[])
    assert seen==[('probe',str(path)),('deep',str(path))]


def test_tag_access_error_unverifiable_not_corrupt(monkeypatch, tmp_path):
    path=tmp_path/'locked.flac';path.write_bytes(b'data')
    monkeypatch.setattr(C,'_validate_tag_write_round_trip',lambda _: (_ for _ in ()).throw(OSError(errno.EACCES,'locked')))
    monkeypatch.setattr(C,'_deep_audio_stream_status',lambda _: pytest.fail('no additional decode'))
    bad,unknown=C.classify_audio_paths([str(path)],check_tag_write=True,deep_audio_check=True)
    assert bad==[] and unknown and 'locked' in unknown[0][1]


def test_deletion_policies_stay_intact():
    assert C.corruption_action(20,5,'delete','threshold',25)=='trash_folder_threshold'
    assert C.corruption_action(20,4,'delete','threshold',25)!='trash_folder_threshold'
    assert C.corruption_action(20,20,'delete','all',100)=='trash_folder_all_corrupt'


def test_no_manual_tweaks_corruption_scan_contract():
    source=(Path(__file__).resolve().parents[2]/'tlo_manual_updates.py').read_text()
    assert 'manual_tweaks_tagging", True' in source
    assert 'standalone_tagger_corruption_enabled", False' in source
    assert 'handle_group_corruption' not in source


def test_native_recipe_has_matching_muxers_and_encoders():
    root=Path(__file__).resolve().parents[2]
    s=(root/'build_audio_ffmpeg.sh').read_text()
    assert '--enable-encoder=flac,pcm_s8,pcm_s16le,pcm_s24le,pcm_s32le' in s
    assert '--enable-muxer=flac,null,pcm_s8,pcm_s16le,pcm_s24le,pcm_s32le' in s
    assert '--enable-muxer=flac,null,framemd5' not in s


@pytest.mark.parametrize("bits,expected_md5", [
    (12, "3b8e898c6a51cae1b180961c1af67ac9"),
    (20, "958d5510f56df400e8e89709eaaa7475"),
])
def test_non_byte_aligned_bit_depth_static_flac_fixture(bits, expected_md5, ffmpeg):
    # These two tiny streams were encoded with libFLAC, not FFmpeg, and are
    # committed as static artifacts so release CI never needs that encoder.
    root = Path(__file__).resolve().parents[1] / "fixtures" / "build585_flac"
    path = root / f"valid_{bits}bit.flac"
    info = FLAC(path).info
    assert info.bits_per_sample == bits and info.total_samples == 2003
    assert int(info.md5_signature).to_bytes(16, "big").hex() == expected_md5
    assert verify_flac_fingerprint(path, ffmpeg_executable=ffmpeg,
                                   cancel_check=lambda: False, timeout_seconds=20)


def test_tag_only_does_not_decode_after_successful_probe(monkeypatch, tmp_path):
    file = tmp_path / "valid.flac"
    file.write_bytes(b"accessible fixture")
    seen = []
    monkeypatch.setattr(C, "_validate_tag_write_round_trip", lambda p: seen.append(p))
    monkeypatch.setattr(C, "_deep_audio_stream_status",
                        lambda _: pytest.fail("tag-only should not decode"))
    assert C.classify_audio_paths([str(file)], check_tag_write=True, deep_audio_check=False) == ([], [])
    assert seen == [str(file)]
