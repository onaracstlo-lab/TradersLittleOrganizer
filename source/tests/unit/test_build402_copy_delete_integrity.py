"""Build 402 irreversible copy/delete verification regressions."""
__version__ = "v448"

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

import tlo_reverse_copy_delete as R
import tlo_tag_lib as T


def _group_record(source: Path):
    audio = source / "01.flac"
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "txt_files": [],
        "setlist_files": [],
        "setlist_file": "",
    }
    record = SimpleNamespace(
        main_dir_path=str(source), main_dir_name=source.name, show_name=source.name,
        artist="Artist", date="2000-01-01", venue="Venue", location="City ST",
        parentheticals=[], music_dirs=[str(source)], setlist_files=[], setlist_file="",
    )
    return group, record


def test_build402_exact_verify_rejects_same_size_different_bytes(tmp_path):
    left = tmp_path / "left"; right = tmp_path / "right"
    left.mkdir(); right.mkdir()
    (left / "a.bin").write_bytes(b"abc")
    (right / "a.bin").write_bytes(b"xyz")
    with pytest.raises(T.TaggerError, match="SHA-256"):
        T._verify_copy_exact(str(left), str(right))
    with pytest.raises(R.ReverseCopyDeleteError, match="SHA-256"):
        R._verify_copy(str(left), str(right))


def test_build402_size_stat_failure_aborts_verification(monkeypatch, tmp_path):
    root = tmp_path / "tree"; root.mkdir(); target = root / "a.bin"; target.write_bytes(b"abc")
    real = T.os.path.getsize
    def fail(path):
        if str(path) == str(target):
            raise OSError("stat unavailable")
        return real(path)
    monkeypatch.setattr(T.os.path, "getsize", fail)
    with pytest.raises(T.TaggerError, match="could not stat"):
        T._file_size_map(str(root))


def test_build402_cross_partition_hash_failure_keeps_source_and_rolls_back_destination(monkeypatch, tmp_path):
    source = tmp_path / "show"; dest_parent = tmp_path / "dest"
    source.mkdir(); dest_parent.mkdir(); (source / "01.flac").write_bytes(b"abc")
    group, record = _group_record(source)
    monkeypatch.setattr(T, "_paths_on_same_filesystem", lambda *_: False)
    monkeypatch.setattr(T, "_verify_copy_exact", lambda *_: (_ for _ in ()).throw(T.TaggerError("SHA-256 mismatch")))
    with pytest.raises(T.TaggerError, match="SHA-256"):
        T.prepare_inventory_copy_delete_target(
            SimpleNamespace(tag_copy_and_delete_path=str(dest_parent), rename_compliantly=False),
            group, record,
        )
    assert source.is_dir()
    assert not (dest_parent / source.name).exists()
    assert not list(dest_parent.glob(".*.tlo-partial-*"))


def test_build402_reverse_containment_precedes_parent_creation_and_never_rolls_back_original():
    source = inspect.getsource(R.reverse_copy_delete_and_rename)
    containment = source.index("if not _same_or_under(original, allowed_root)")
    mkdir = source.index("os.makedirs(original_parent, exist_ok=True)")
    assert containment < mkdir
    assert "shutil.rmtree(original" not in source
    assert "temp_restore" in source


def test_build402_same_partition_forward_move_still_avoids_hashing():
    source = inspect.getsource(T.prepare_inventory_copy_delete_target)
    same_branch = source[source.index("if _paths_on_same_filesystem"):source.index("else:", source.index("if _paths_on_same_filesystem"))]
    assert "_verify_copy_exact" not in same_branch
    assert "_verify_copy_by_file_size" not in same_branch
