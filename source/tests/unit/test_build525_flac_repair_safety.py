"""Build 525 FLAC repair data-loss and validation regressions."""

from __future__ import annotations

import errno
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def _load_delete_dupes():
    source = Path(__file__).resolve().parents[2] / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build525", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _files(tmp_path: Path):
    source = tmp_path / "healthy.flac"
    keeper = tmp_path / "keeper.flac"
    source.write_bytes(b"HEALTHY" * 4096)
    keeper.write_bytes(b"ORIGINAL-KEEPER" * 4096)
    return source, keeper, keeper.read_bytes()


def _assert_keeper_unchanged(keeper: Path, original: bytes, tmp_path: Path):
    assert keeper.read_bytes() == original
    assert not list(tmp_path.glob(".tlo-deleteDupes-repair-*.flac"))
    assert not list(tmp_path.glob(".tlo-deleteDupes-backup-*.flac"))


def test_build525_staging_copy_failure_never_changes_keeper(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)
    real_copy2 = D.shutil.copy2

    def fail_stage(src, dst, *args, **kwargs):
        if str(src) == str(source):
            Path(dst).write_bytes(b"PARTIAL-STAGE")
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(D.shutil, "copy2", fail_stage)
    with pytest.raises(OSError, match="No space"):
        D._replace_file_from_copy(str(source), str(keeper))
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_partial_backup_copy_is_never_restored_over_keeper(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)
    real_copy2 = D.shutil.copy2
    calls = 0

    def fail_backup(src, dst, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            Path(dst).write_bytes(original[:10])
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(D.shutil, "copy2", fail_backup)
    with pytest.raises(OSError, match="No space"):
        D._replace_file_from_copy(str(source), str(keeper))
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_unverified_backup_is_never_used_for_rollback(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)
    real_copy2 = D.shutil.copy2
    calls = 0

    def corrupt_backup(src, dst, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            Path(dst).write_bytes(b"NOT-THE-KEEPER")
            return str(dst)
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(D.shutil, "copy2", corrupt_backup)
    with pytest.raises(D.DeleteDupesError, match="backup failed byte verification"):
        D._replace_file_from_copy(str(source), str(keeper))
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_atomic_install_failure_leaves_keeper_unchanged(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)

    def fail_replace(_src, _dst):
        raise OSError(errno.EIO, "replace failed")

    monkeypatch.setattr(D.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        D._replace_file_from_copy(str(source), str(keeper))
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_post_install_verification_failure_rolls_back_original(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)
    source_bytes = source.read_bytes()
    real_hash = D._sha256_file
    forced = False

    def fail_first_installed_hash(path):
        nonlocal forced
        path = Path(path)
        if path == keeper and path.read_bytes() == source_bytes and not forced:
            forced = True
            return "0" * 64
        return real_hash(str(path))

    monkeypatch.setattr(D, "_sha256_file", fail_first_installed_hash)
    with pytest.raises(D.DeleteDupesError, match="Installed FLAC repair failed byte verification"):
        D._replace_file_from_copy(str(source), str(keeper))
    assert forced is True
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_safe_repair_requires_space_for_stage_and_verified_backup(monkeypatch, tmp_path):
    D = _load_delete_dupes()
    source, keeper, original = _files(tmp_path)
    monkeypatch.setattr(D.shutil, "disk_usage", lambda _path: SimpleNamespace(free=1))

    with pytest.raises(D.DeleteDupesError, match="Insufficient free space"):
        D._replace_file_from_copy(str(source), str(keeper))
    _assert_keeper_unchanged(keeper, original, tmp_path)


def test_build525_ffmpeg_permission_failure_is_unverifiable(tmp_path):
    D = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    result = SimpleNamespace(returncode=1, stderr="Error opening input file: Permission denied")
    assert D.flac_file_is_healthy(
        str(flac), ffmpeg_executable="ffmpeg", run_func=lambda *_a, **_k: result
    ) is None


def test_build525_ffmpeg_decode_failure_remains_proven_corrupt(tmp_path):
    D = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    result = SimpleNamespace(returncode=1, stderr="Invalid data found when processing input")
    assert D.flac_file_is_healthy(
        str(flac), ffmpeg_executable="ffmpeg", run_func=lambda *_a, **_k: result
    ) is False
