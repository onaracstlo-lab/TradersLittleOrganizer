"""Build 682: real-media, reversibility, and lossless-input regressions.

Use the actual FFmpeg binary for corrupt FLACs. Mocks in historical tests alone
could not detect the FFmpeg null-decoder false-negative reported for Build 681.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

import logging_lib
from tlo_bootlist_volume_policy import read_bootlist_rows
from tlo_inventory_update import read_bootlist
from tlo_reverse_folders import prepare_reverse_plan

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _dupes():
    spec = importlib.util.spec_from_file_location('tlo_deletedupes_build682', ROOT/'tlo-deleteDupes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flac(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('real FFmpeg unavailable (native build job must run this)')
    original = tmp_path/'valid.flac'
    subprocess.run([ffmpeg, '-nostdin', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'sine=frequency=440:duration=3', '-c:a', 'flac',
                    '-y', str(original)], check=True, timeout=25)
    return original, ffmpeg


def test_real_flac_bitflip_is_not_healthy_and_healthy_copy_repairs(tmp_path):
    dd = _dupes()
    clean, ffmpeg = _flac(tmp_path)
    keeper = tmp_path/'Keeper Show'
    copy = tmp_path/'Keeper Show (copy1)'
    keeper.mkdir(); copy.mkdir()
    (copy/'01.flac').write_bytes(clean.read_bytes())
    damaged = bytearray(clean.read_bytes())
    damaged[len(damaged)//2] ^= 0x40  # same-size frame damage
    (keeper/'01.flac').write_bytes(damaged)
    assert dd.flac_file_is_healthy(str(copy/'01.flac'), ffmpeg_executable=ffmpeg) is True
    assert dd.flac_file_is_healthy(str(keeper/'01.flac'), ffmpeg_executable=ffmpeg) is False
    repaired, unrepaired, unverified = dd.repair_corrupt_flacs_from_copies(
        str(keeper), [dd.CopyCandidate(number=1, path=str(copy))],
        ffmpeg_executable=ffmpeg, emit=lambda *a, **k: None,
    )
    assert (repaired, unrepaired, unverified) == (1, 0, False)
    assert (keeper/'01.flac').read_bytes() == (copy/'01.flac').read_bytes()


def test_unset_streaminfo_md5_is_unverifiable_not_corrupt(tmp_path):
    dd = _dupes()
    clean, ffmpeg = _flac(tmp_path)
    data = bytearray(clean.read_bytes())
    data[26:42] = bytes(16)
    clean.write_bytes(data)
    assert dd.flac_file_is_healthy(str(clean), ffmpeg_executable=ffmpeg) is None


def test_reinventory_log_truncation_preserves_reverse_history(tmp_path):
    logs = tmp_path/'logs'
    logs.mkdir()
    old = tmp_path/'Old Name'
    current = tmp_path/'New Name'
    current.mkdir()
    operation = f'RENAME_COMPLIANTLY: {old} -> {current}\n'
    tag = logs/'tags0.txt'
    tag.write_text(operation, encoding='utf-8')
    logging_lib.truncate_logs_for_tokens(str(tmp_path), ['0'])
    archive = logs/'folderOperations.log'
    assert archive.read_text(encoding='utf-8') == operation
    assert operation not in tag.read_text(encoding='utf-8')
    plan = prepare_reverse_plan(str(current), tlo_home=str(tmp_path))
    assert Path(plan.log_path) == archive
    assert any(op.source == str(old) and op.destination == str(current) for op in plan.operations)
    # A second re-inventory has no more history to archive.
    logging_lib.truncate_logs_for_tokens(str(tmp_path), ['0'])
    assert archive.read_text(encoding='utf-8') == operation


def test_log_archiving_failure_never_erases_tag_history(tmp_path):
    logs = tmp_path/'logs'
    logs.mkdir()
    tag = logs/'tags0.txt'
    tag.write_text('RENAME_COMPLIANTLY: /one -> /two\n', encoding='utf-8')
    (logs/'folderOperations.log').mkdir()  # deliberately invalid archive destination
    with pytest.raises(OSError):
        logging_lib.truncate_logs_for_tokens(str(tmp_path), ['0'])
    assert 'RENAME_COMPLIANTLY' in tag.read_text(encoding='utf-8')


@pytest.mark.parametrize('reader', [read_bootlist_rows, read_bootlist])
def test_cp1252_bootlist_refused_without_lossy_rewrite(tmp_path, reader):
    path = tmp_path/'bootlist.csv'
    original = 'sep=^\nBeyoncé 2013-05-05 Zénith Paris^[Disk] /Paris/Beyoncé\n'.encode('cp1252')
    path.write_bytes(original)
    with pytest.raises(UnicodeDecodeError):
        reader(str(tmp_path))
    assert path.read_bytes() == original
