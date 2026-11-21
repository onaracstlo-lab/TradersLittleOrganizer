"""Build 688: unset-MD5/tag-write, read-only collection preview, and POSIX path fixtures."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

import tlo_corruption
from tlo_flac_fingerprint import DECODE_ONLY_UNSET_MD5, FingerprintUnverifiable, verify_flac_fingerprint
from tlo_ux import preview_operation

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _flac(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('real FFmpeg unavailable; hosted native build must exercise')
    path = tmp_path / '01 Song.flac'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'sine=duration=1',
                    '-y', str(path)], check=True, timeout=20)
    data = bytearray(path.read_bytes())
    # FLAC STREAMINFO stores an optional 16-byte MD5 at byte offset 26.
    data[26:42] = b'\0' * 16
    path.write_bytes(data)
    return path, ffmpeg


def _dupes():
    spec = importlib.util.spec_from_file_location('delete_dupes_688', ROOT/'tlo-deleteDupes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unset_md5_is_taggable_decode_only_not_corrupt(tmp_path, monkeypatch):
    file, ffmpeg = _flac(tmp_path)
    original = file.read_bytes()
    # DeleteDupes must still demand real authenticated integrity before moving copies.
    with pytest.raises(FingerprintUnverifiable, match='MD5 is unset'):
        verify_flac_fingerprint(str(file), ffmpeg_executable=ffmpeg)
    assert verify_flac_fingerprint(str(file), ffmpeg_executable=ffmpeg,
                                   allow_unset_md5=True) == DECODE_ONLY_UNSET_MD5
    monkeypatch.setattr(tlo_corruption, 'bundled_ffmpeg_executable', lambda: ffmpeg)
    decoded = []
    bad, unknown = tlo_corruption.classify_audio_paths(
        [str(file)], check_tag_write=True, deep_audio_check=True,
        decode_only_details=decoded)
    assert bad == [] and unknown == []
    assert len(decoded) == 1 and 'MD5 unset' in decoded[0][1]
    assert file.read_bytes()[26:42] == b'\0' * 16
    # A reversible probe may reorganize the tag container, but must not alter PCM.
    assert verify_flac_fingerprint(str(file), ffmpeg_executable=ffmpeg,
                                   allow_unset_md5=True) == DECODE_ONLY_UNSET_MD5
    assessment = tlo_corruption.assess_group_corruption(
        {'music_dirs': [str(tmp_path)]}, check_tag_write=True, deep_audio_check=True)
    assert not assessment.unverifiable and not assessment.corrupt_files
    assert len(assessment.decode_only_details) == 1
    assert original[26:42] == file.read_bytes()[26:42]


def test_missing_md5_tag_write_failure_remains_corruption(tmp_path, monkeypatch):
    file, ffmpeg = _flac(tmp_path)
    monkeypatch.setattr(tlo_corruption, 'bundled_ffmpeg_executable', lambda: ffmpeg)
    def fail_tag(_path):
        raise ValueError('reversible tag write failed')
    monkeypatch.setattr(tlo_corruption, '_validate_tag_write_round_trip', fail_tag)
    bad, unknown = tlo_corruption.classify_audio_paths(
        [str(file)], check_tag_write=True, deep_audio_check=True)
    assert bad == [str(file)] and unknown == []


def test_missing_md5_dupes_skips_with_file_specific_reason(tmp_path):
    file, ffmpeg = _flac(tmp_path)
    keeper = tmp_path/'Example 2001-01-01'
    copy = tmp_path/'Example 2001-01-01 (copy1)'
    keeper.mkdir(); copy.mkdir()
    (keeper/'01.flac').write_bytes(file.read_bytes())
    (copy/'01.flac').write_bytes(file.read_bytes())
    dd = _dupes()
    emitted = []
    result = dd.repair_corrupt_flacs_from_copies(
        str(keeper), [dd.CopyCandidate(number=1,path=str(copy))],
        ffmpeg_executable=ffmpeg,
        emit=lambda text, **kwargs: emitted.append(text))
    assert result == (0, 0, True)
    assert any('STREAMINFO MD5 is unset' in message and '01.flac' in message for message in emitted)
    assert (copy/'01.flac').is_file()


def test_preview_sibling_collection_is_read_only_and_named(tmp_path):
    from tests._legacy_suite import _v345_preview_config
    root = tmp_path/'music'; root.mkdir()
    for n in (1, 2):
        folder = root/f'Grateful Dead - Europe 72 Disc {n}'
        folder.mkdir()
        (folder/f'0{n} Unique Track.flac').write_bytes(b'audio')
        (folder/'info.txt').write_text(f'0{n} Unique Track {n}\n', encoding='utf-8')
    before = sorted(p.as_posix() for p in root.rglob('*'))
    config = _v345_preview_config(tmp_path, root, tag_during_inventory=False)
    result = preview_operation(config, operation='Full Inventory Dry Run')
    collections = [item for item in result.samples if 'WOULD CONSOLIDATE' in ' '.join(item.actions)]
    assert len(collections) == 1, [(item.path, item.actions) for item in result.samples]
    assert collections[0].show_name == 'Grateful Dead - Europe 72'
    assert len(list(root.iterdir())) == 2
    assert sorted(p.as_posix() for p in root.rglob('*')) == before
    assert any('TLO Reverse does not undo' in issue.message for issue in result.issues)


@pytest.mark.skipif(os.name == 'nt', reason='POSIX surrogateescaped path fixture')
def test_invalid_utf8_folder_is_explicitly_unidentified(tmp_path):
    from initial_dir_walk_lib import initial_dir_walk
    root = tmp_path/'music'; root.mkdir()
    path = os.fsencode(str(root)) + b'/Wilco 1997-11-28 Caf\xe9 Worcester'
    os.mkdir(path)
    with open(path + b'/01.flac', 'wb') as f:
        f.write(b'flac')
    class Logs:
        def __init__(self):
            self.unidentified = []
            self.paths = []
        def dead_end(self, message, *args):
            self.unidentified.append(message % args if args else message)
        def complete_paths(self, message, *args):
            self.paths.append(message % args if args else message)
    logs = Logs()
    config = SimpleNamespace(logs=logs,TLOHome=str(tmp_path),performance_mode='balanced')
    initial_dir_walk(config, str(root))
    text = (tmp_path/'unidentifiedShows.txt').read_text(encoding='utf-8')
    assert 'UNIDENTIFIED_NON_UTF8_PATH' in text
    assert os.fsencode(path).hex() in text
    assert 'invalid UTF-8 filename' in logs.unidentified[0]
    assert not logs.paths
    # Repeat does not flood unidentifiedShows.txt with the same unsafe path.
    initial_dir_walk(config, str(root))
    assert (tmp_path/'unidentifiedShows.txt').read_text(encoding='utf-8').count('UNIDENTIFIED_NON_UTF8_PATH') == 1


@pytest.mark.skipif(os.name == 'nt', reason='POSIX surrogateescaped path fixture')
def test_invalid_utf8_preview_never_writes_unidentified_file(tmp_path):
    from initial_dir_walk_lib import initial_dir_walk
    root = tmp_path/'music'; root.mkdir()
    raw = os.fsencode(str(root)) + b'/Caf\xe9'
    os.mkdir(raw)
    with open(raw+b'/01.flac','wb') as outfile:
        outfile.write(b'flac')
    class Logs:
        def __init__(self):
            self.warnings = []
        def dead_end(self, message, *args):
            self.warnings.append(message % args if args else message)
        def complete_paths(self, message, *args):
            raise AssertionError('raw surrogate path must not enter inventory')
    logs = Logs()
    cfg = SimpleNamespace(TLOHome=str(tmp_path), logs=logs, dry_run=True, performance_mode='balanced')
    initial_dir_walk(cfg, str(root))
    assert logs.warnings and 'UNIDENTIFIED_NON_UTF8_PATH' in logs.warnings[0]
    assert not (tmp_path/'unidentifiedShows.txt').exists()
