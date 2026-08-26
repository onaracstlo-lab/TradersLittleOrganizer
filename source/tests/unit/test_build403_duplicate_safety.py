import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _load_delete_dupes():
    source = Path(__file__).resolve().parents[2] / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build403", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validator_oserror_is_unverifiable(tmp_path):
    module = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    def broken(*_a, **_k):
        raise OSError("device unavailable")
    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=broken) is None


def test_validator_memory_error_is_unverifiable(tmp_path):
    module = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    def broken(*_a, **_k):
        raise MemoryError("resource pressure")
    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=broken) is None


def test_validator_nonzero_exit_is_proven_corrupt(tmp_path):
    module = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    class Result:
        returncode = 1
    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=lambda *_a, **_k: Result()) is False


def test_transactional_repair_stages_exact_copy_before_replacement(tmp_path):
    module = _load_delete_dupes()
    src = tmp_path / "copy.flac"
    dst = tmp_path / "keeper.flac"
    src.write_bytes(b"HEALTHY BYTES")
    dst.write_bytes(b"BAD BYTES")
    module._replace_file_from_copy(str(src), str(dst))
    assert dst.read_bytes() == b"HEALTHY BYTES"
    assert not list(tmp_path.glob(".tlo-deleteDupes-repair-*.flac"))
    assert not list(tmp_path.glob(".tlo-deleteDupes-backup-*.flac"))


def test_delete_new_keep_old_uses_trash_and_fails_closed(monkeypatch, tmp_path):
    import tlo_inventory_update as U
    folder = tmp_path / "incoming"
    folder.mkdir()
    called = []
    monkeypatch.setattr(U, "move_to_trash", lambda path: called.append(path))
    U.delete_new_keep_old({"folder": str(folder)})
    assert called == [str(folder)]

    def fail(_path):
        raise OSError("no recycle support")
    monkeypatch.setattr(U, "move_to_trash", fail)
    with pytest.raises(U.InventoryUpdateError, match="remains in place"):
        U.delete_new_keep_old({"folder": str(folder)})
    assert folder.exists()
