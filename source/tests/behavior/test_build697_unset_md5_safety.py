"""Build 697: damaged unknown-length FLAC cannot masquerade as fully decoded."""
from __future__ import annotations
import shutil
import subprocess

import pytest

from mutagen.flac import FLAC
import tlo_corruption as corruption
from tlo_flac_fingerprint import FingerprintCorrupt, FingerprintUnverifiable, verify_flac_fingerprint

pytestmark = pytest.mark.behavior


def _piped_flac(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        pytest.skip('FFmpeg required for real-media corruption regression')
    command=[ffmpeg,'-v','error','-f','lavfi','-i','sine=frequency=440:duration=3',
             '-ac','2','-ar','44100','-sample_fmt','s16','-f','flac','pipe:1']
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25,check=True)
    path=tmp_path/'stream.flac';path.write_bytes(result.stdout)
    header=FLAC(path).info
    assert int(header.md5_signature)==0 and int(header.total_samples)==0
    return path,ffmpeg


def test_intact_unset_md5_and_unknown_sample_total_is_not_falsely_authenticated(tmp_path):
    path,ffmpeg=_piped_flac(tmp_path)
    with pytest.raises(FingerprintUnverifiable,match='MD5 and total_samples'):
        verify_flac_fingerprint(path,ffmpeg_executable=ffmpeg,allow_unset_md5=True)
    # Its inability to authenticate is not proof of corruption.
    assert corruption._deep_audio_stream_status(path,ffmpeg_executable=ffmpeg) is None


@pytest.mark.parametrize('damage',['truncate','xor'])
def test_damaged_unset_md5_never_gets_positive_audio_integrity_verdict(tmp_path,damage):
    path,ffmpeg=_piped_flac(tmp_path)
    data=bytearray(path.read_bytes())
    if damage=='truncate': data=data[:len(data)//2]
    else:
        center=len(data)//2
        for offset in range(center,center+64): data[offset] ^= 0x5a
    path.write_bytes(data)
    with pytest.raises((FingerprintUnverifiable, FingerprintCorrupt)):
        verify_flac_fingerprint(path,ffmpeg_executable=ffmpeg,allow_unset_md5=True)
    # Missing MD5 is not permission to delete. Corruption is not 'verified OK'.
    assert corruption._deep_audio_stream_status(path,ffmpeg_executable=ffmpeg) in (None, False)


def test_deep_check_blocks_tagging_on_unauthenticated_zero_zero_flac(tmp_path,monkeypatch):
    path,ffmpeg=_piped_flac(tmp_path)
    monkeypatch.setattr(corruption,'bundled_ffmpeg_executable',lambda:ffmpeg)
    bad,unknown=corruption.classify_audio_paths([str(path)],check_tag_write=True,deep_audio_check=True)
    assert bad==[] and len(unknown)==1
    assert 'MD5 and total_samples unset' in unknown[0][1]
    # Tag-only mode does not treat a missing FLAC checksum as corruption.
    bad,unknown=corruption.classify_audio_paths([str(path)],check_tag_write=True,deep_audio_check=False)
    assert bad==[] and unknown==[]
