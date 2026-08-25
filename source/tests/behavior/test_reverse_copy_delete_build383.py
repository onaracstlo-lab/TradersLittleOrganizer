from pathlib import Path
import os

import pytest

pytestmark = pytest.mark.behavior

import tlo_reverse_copy_delete as R


def _write_log(tlo_home: Path, body: str, name: str = "tags1.txt") -> Path:
    logs = tlo_home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / name
    path.write_text(body, encoding="utf-8")
    return path


def _combined_log(source: Path, destination: Path) -> str:
    return (
        "# tagSuccessLog for search path: [ORIGINAL] /Music\n"
        "SEARCH_PATH: [ORIGINAL] /Music\n"
        "TAG_DURING_INVENTORY: mode=copy-and-delete | convert shn=no | rename compliantly=yes | copy destination=/moved\n"
        "TAG_COPY_AND_DELETE: enabled | destination=/moved\n"
        f"TAG_COPY_DELETE_MOVE: {source} -> {destination}\n"
    )


def test_find_reverse_records_uses_shared_tlohome_environment_and_filters_combined_run(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    original_root = tmp_path / "original"
    moved_root = tmp_path / "moved"
    original_root.mkdir()
    moved_root.mkdir()
    source = original_root / "Old Folder Name"
    destination = moved_root / "Artist 1987-01-17 Venue City ST"
    _write_log(
        tlo_home,
        _combined_log(source, destination)
        + "TAG_DURING_INVENTORY: mode=copy-and-delete | convert shn=no | rename compliantly=no | copy destination=/moved\n"
        + f"TAG_COPY_DELETE_MOVE: {source} -> {moved_root / 'plain-copy-delete'}\n",
        "tags1.txt",
    )
    monkeypatch.setenv("TLOHome", str(tlo_home))

    resolved, original, moved, records = R.find_reverse_records(
        original_partition=str(original_root), moved_to=str(moved_root)
    )

    assert resolved == os.path.normpath(str(tlo_home))
    assert original == os.path.normpath(str(original_root))
    assert moved == os.path.normpath(str(moved_root))
    assert [(r.original_path, r.current_path) for r in records] == [
        (os.path.normpath(str(source)), os.path.normpath(str(destination)))
    ]


def test_reverse_restores_exact_original_name_and_location_without_touching_files(tmp_path):
    tlo_home = tmp_path / "home"
    original_root = tmp_path / "original"
    moved_root = tmp_path / "moved"
    original_parent = original_root / "x" / "F" / "Friedman, Kinky"
    original_parent.mkdir(parents=True)
    moved_root.mkdir()
    original = original_parent / "Kinky Friedman 1980s Lone Star Cafe NYC"
    current = moved_root / "Kinky Friedman xxxx-xx-xx Lone Star Cafe New York, NY"
    current.mkdir()
    audio = current / "02 Dan Daniel Kinky Friedman - Country Sessions #55 Intro and interview.flac"
    audio.write_bytes(b"unchanged-tagged-file-bytes")
    _write_log(tlo_home, _combined_log(original, current))

    result = R.reverse_copy_delete_and_rename(
        tlo_home=str(tlo_home),
        original_partition=str(original_root),
        moved_to=str(moved_root),
    )

    assert result.restored == 1
    assert original.is_dir()
    assert not current.exists()
    assert (original / audio.name).read_bytes() == b"unchanged-tagged-file-bytes"
    reverse_log = (tlo_home / "logs" / "reverseCopyDelete.log").read_text(encoding="utf-8")
    assert "RESTORED_MOVE:" in reverse_log
    assert str(original) in reverse_log


def test_reverse_refuses_to_overwrite_existing_original(tmp_path):
    tlo_home = tmp_path / "home"
    original_root = tmp_path / "original"
    moved_root = tmp_path / "moved"
    original_root.mkdir()
    moved_root.mkdir()
    original = original_root / "Old Name"
    current = moved_root / "New Name"
    original.mkdir()
    current.mkdir()
    (original / "keep.txt").write_text("original", encoding="utf-8")
    (current / "keep.txt").write_text("moved", encoding="utf-8")
    _write_log(tlo_home, _combined_log(original, current))

    result = R.reverse_copy_delete_and_rename(
        tlo_home=str(tlo_home),
        original_partition=str(original_root),
        moved_to=str(moved_root),
    )

    assert result.restored == 0
    assert result.conflicts == 1
    assert original.is_dir() and current.is_dir()
    assert (original / "keep.txt").read_text(encoding="utf-8") == "original"
    assert (current / "keep.txt").read_text(encoding="utf-8") == "moved"


def test_reverse_cross_filesystem_copies_verifies_then_deletes_current(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    original_root = tmp_path / "original"
    moved_root = tmp_path / "moved"
    original_root.mkdir()
    moved_root.mkdir()
    original = original_root / "Original Folder"
    current = moved_root / "Compliant Folder"
    (current / "notes").mkdir(parents=True)
    (current / "song.flac").write_bytes(b"abc123")
    (current / "notes" / "setlist.txt").write_text("song", encoding="utf-8")
    _write_log(tlo_home, _combined_log(original, current).replace("TAG_COPY_DELETE_MOVE", "TAG_COPY_DELETE_COPY"))
    monkeypatch.setattr(R, "_same_filesystem", lambda *_args: False)

    result = R.reverse_copy_delete_and_rename(
        tlo_home=str(tlo_home),
        original_partition=str(original_root),
        moved_to=str(moved_root),
    )

    assert result.restored == 1
    assert not current.exists()
    assert (original / "song.flac").read_bytes() == b"abc123"
    assert (original / "notes" / "setlist.txt").read_text(encoding="utf-8") == "song"
    assert any("RESTORED_COPY_DELETE:" in line for line in result.messages)


def test_reverse_requires_destination_and_original_partition_to_match_logged_mapping(tmp_path):
    tlo_home = tmp_path / "home"
    original_a = tmp_path / "original-a"
    original_b = tmp_path / "original-b"
    moved_a = tmp_path / "moved-a"
    moved_b = tmp_path / "moved-b"
    for path in (original_a, original_b, moved_a, moved_b):
        path.mkdir()
    source = original_a / "Old"
    destination = moved_a / "New"
    _write_log(tlo_home, _combined_log(source, destination))

    with pytest.raises(R.ReverseCopyDeleteError, match="No combined Copy/Delete"):
        R.find_reverse_records(
            tlo_home=str(tlo_home), original_partition=str(original_b), moved_to=str(moved_a)
        )

    # Once the original path itself identifies the log, a destination with no
    # exact folder match is allowed through discovery and will be skipped safely
    # by execution rather than causing a search through unrelated logs.
    _home, _original, _moved, records = R.find_reverse_records(
        tlo_home=str(tlo_home), original_partition=str(original_a), moved_to=str(moved_b)
    )
    assert len(records) == 1
    assert records[0].current_path == os.path.normpath(str(moved_b / "New"))


def test_named_original_partition_resolves_current_mount_and_remaps_logged_root(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    old_volume_root = tmp_path / "old-drive"
    current_volume_root = tmp_path / "current-drive"
    moved_root = tmp_path / "moved"
    current_volume_root.mkdir()
    moved_root.mkdir()
    logged_original = old_volume_root / "Music" / "Old Folder Name"
    current = moved_root / "Artist 1987-01-17 Venue City ST"
    current.mkdir()
    (current / "song.flac").write_bytes(b"tagged-bytes-stay-unchanged")
    _write_log(tlo_home, _combined_log(logged_original, current))

    monkeypatch.setattr(
        R,
        "_mounted_roots_for_label",
        lambda label: [str(current_volume_root)] if str(label).casefold() == "original" else [],
    )
    monkeypatch.setattr(R, "_logged_volume_root", lambda _path: os.path.normpath(str(old_volume_root)))

    resolved, original_root, moved, records = R.find_reverse_records(
        tlo_home=str(tlo_home), original_partition="ORIGINAL", moved_to=str(moved_root)
    )
    expected_original = current_volume_root / "Music" / "Old Folder Name"
    assert resolved == os.path.normpath(str(tlo_home))
    assert original_root == os.path.normpath(str(current_volume_root))
    assert moved == os.path.normpath(str(moved_root))
    assert len(records) == 1
    assert records[0].logged_original_path == os.path.normpath(str(logged_original))
    assert records[0].original_path == os.path.normpath(str(expected_original))

    result = R.reverse_copy_delete_and_rename(
        tlo_home=str(tlo_home), original_partition="ORIGINAL", moved_to=str(moved_root)
    )
    assert result.restored == 1
    assert not current.exists()
    assert (expected_original / "song.flac").read_bytes() == b"tagged-bytes-stay-unchanged"


def test_named_original_partition_refuses_ambiguous_mounted_labels(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    moved_root = tmp_path / "moved"
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    for path in (tlo_home, moved_root, root_a, root_b):
        path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(R, "_mounted_roots_for_label", lambda _label: [str(root_a), str(root_b)])

    with pytest.raises(R.ReverseCopyDeleteError, match="More than one mounted partition/volume"):
        R.find_reverse_records(
            tlo_home=str(tlo_home), original_partition="ARCHIVE", moved_to=str(moved_root)
        )
