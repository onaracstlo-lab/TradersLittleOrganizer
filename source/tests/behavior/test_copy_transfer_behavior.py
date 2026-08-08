"""Behavioral coverage for copy and Copy/Delete Original transfer verification."""

__version__ = "v361"

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _group_and_record(source):
    audio = source / "01 Song.flac"
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "setlist_files": [],
        "txt_files": [],
    }
    record = SimpleNamespace(
        main_dir_path=str(source),
        main_dir_name=source.name,
        show_name=source.name,
        setlist_file="",
        music_dirs=[str(source)],
        setlist_files=[],
    )
    return group, record


def test_same_partition_copy_delete_capacity_preflight_does_not_total_source(tmp_path, monkeypatch):
    import inventory_list_lib as inventory

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")

    monkeypatch.setattr(inventory, "_paths_on_same_filesystem", lambda _a, _b: True)
    monkeypatch.setattr(
        inventory,
        "_folder_size_bytes",
        lambda _path: (_ for _ in ()).throw(AssertionError("same-partition move must not total file sizes")),
    )

    requirements = inventory._collect_copy_capacity_requirements(
        SimpleNamespace(tag_copy_and_delete_path="", tag_copy_during_inventory=False, tag_copy_destination=""),
        [(str(source), "", "", "", "copy-delete", str(destination))],
    )

    assert requirements == {}


def test_same_partition_copy_delete_renames_without_size_verification(tmp_path, monkeypatch):
    import tlo_tag_lib as tag

    source = tmp_path / "Artist 1970-01-01 Venue City ST"
    destination = tmp_path / "processed"
    source.mkdir()
    destination.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    group, record = _group_and_record(source)

    monkeypatch.setattr(tag, "_paths_on_same_filesystem", lambda _a, _b: True)
    monkeypatch.setattr(
        tag,
        "_verify_copy_by_file_size",
        lambda _a, _b: (_ for _ in ()).throw(AssertionError("same-partition move must not compare file sizes")),
    )
    monkeypatch.setattr(
        tag.shutil,
        "move",
        lambda _a, _b: (_ for _ in ()).throw(AssertionError("same-partition transfer must use a directory rename")),
    )

    moved_group, moved_record = tag.prepare_inventory_copy_delete_target(
        SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=False),
        group,
        record,
    )

    moved_root = destination / source.name
    assert moved_root.is_dir()
    assert not source.exists()
    assert moved_record.main_dir_path == str(moved_root)
    assert moved_group["music_files"] == [str(moved_root / "01 Song.flac")]


def test_cross_partition_copy_delete_verifies_sizes_before_deleting_source(tmp_path, monkeypatch):
    import tlo_tag_lib as tag

    source = tmp_path / "Cross Partition Show"
    destination = tmp_path / "processed"
    source.mkdir()
    destination.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    group, record = _group_and_record(source)

    monkeypatch.setattr(tag, "_paths_on_same_filesystem", lambda _a, _b: False)
    original_verify = tag._verify_copy_by_file_size
    calls = []

    def verify(source_root, destination_root):
        calls.append((source_root, destination_root, source.exists()))
        original_verify(source_root, destination_root)

    monkeypatch.setattr(tag, "_verify_copy_by_file_size", verify)

    tag.prepare_inventory_copy_delete_target(
        SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=False),
        group,
        record,
    )

    assert calls == [(str(source), str(destination / source.name), True)]
    assert not source.exists()


def test_tag_copy_always_verifies_sizes_even_on_same_partition(tmp_path, monkeypatch):
    import tlo_tag_lib as tag

    source = tmp_path / "Tag Copy Show"
    destination = tmp_path / "copies"
    source.mkdir()
    destination.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    group, record = _group_and_record(source)

    original_verify = tag._verify_copy_by_file_size
    calls = []

    def verify(source_root, destination_root):
        calls.append((source_root, destination_root))
        original_verify(source_root, destination_root)

    monkeypatch.setattr(tag, "_verify_copy_by_file_size", verify)

    copied_group, copied_record = tag.prepare_inventory_tagging_target(
        SimpleNamespace(
            tag_copy_during_inventory=True,
            tag_copy_destination=str(destination),
            rename_compliantly=False,
        ),
        group,
        record,
    )

    copied_root = destination / source.name
    assert calls == [(str(source), str(copied_root))]
    assert source.is_dir()
    assert copied_root.is_dir()
    assert copied_record.main_dir_path == str(copied_root)
    assert copied_group["music_files"] == [str(copied_root / "01 Song.flac")]


def test_ordinary_copy_capacity_preflight_totals_source_on_same_partition(tmp_path, monkeypatch):
    import inventory_list_lib as inventory

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    monkeypatch.setattr(inventory, "_paths_on_same_filesystem", lambda _a, _b: True)
    monkeypatch.setattr(inventory, "_folder_size_bytes", lambda _path: 12345)

    requirements = inventory._collect_copy_capacity_requirements(
        SimpleNamespace(tag_copy_and_delete_path="", tag_copy_during_inventory=False, tag_copy_destination=""),
        [(str(source), "", "", "", "copy", str(destination))],
    )

    detail = requirements[str(destination)]
    assert detail["required"] == 12345
    assert detail["sources"][0]["size"] == 12345
    assert detail["sources"][0]["required"] == 12345


def test_cross_partition_copy_delete_capacity_preflight_totals_source(tmp_path, monkeypatch):
    import inventory_list_lib as inventory

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    monkeypatch.setattr(inventory, "_paths_on_same_filesystem", lambda _a, _b: False)
    monkeypatch.setattr(inventory, "_folder_size_bytes", lambda _path: 67890)

    requirements = inventory._collect_copy_capacity_requirements(
        SimpleNamespace(tag_copy_and_delete_path="", tag_copy_during_inventory=False, tag_copy_destination=""),
        [(str(source), "", "", "", "copy-delete", str(destination))],
    )

    detail = requirements[str(destination)]
    assert detail["required"] == 67890
    assert detail["sources"][0]["size"] == 67890
    assert detail["sources"][0]["required"] == 67890


def _populate_full_folder_tree(source):
    (source / "01 Song.flac").write_bytes(b"audio")
    (source / "notes").mkdir()
    (source / "notes" / "info.txt").write_text("show notes", encoding="utf-8")
    (source / "artwork" / "scans").mkdir(parents=True)
    (source / "artwork" / "cover.jpg").write_bytes(b"cover")
    (source / "artwork" / "scans" / "back.jpg").write_bytes(b"back")
    (source / "extras" / "empty-folder").mkdir(parents=True)


def _assert_full_folder_tree(root):
    assert (root / "01 Song.flac").read_bytes() == b"audio"
    assert (root / "notes" / "info.txt").read_text(encoding="utf-8") == "show notes"
    assert (root / "artwork" / "cover.jpg").read_bytes() == b"cover"
    assert (root / "artwork" / "scans" / "back.jpg").read_bytes() == b"back"
    assert (root / "extras" / "empty-folder").is_dir()


def test_same_partition_copy_delete_moves_entire_folder_tree(tmp_path, monkeypatch):
    import tlo_tag_lib as tag

    source = tmp_path / "Complete Show Folder"
    destination = tmp_path / "processed"
    source.mkdir()
    destination.mkdir()
    _populate_full_folder_tree(source)
    group, record = _group_and_record(source)

    monkeypatch.setattr(tag, "_paths_on_same_filesystem", lambda _a, _b: True)
    moved_group, moved_record = tag.prepare_inventory_copy_delete_target(
        SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=False),
        group,
        record,
    )

    moved_root = destination / source.name
    assert not source.exists()
    _assert_full_folder_tree(moved_root)
    assert moved_group["main_dir_path"] == str(moved_root)
    assert moved_record.main_dir_path == str(moved_root)


def test_cross_partition_copy_delete_copies_entire_folder_tree_before_delete(tmp_path, monkeypatch):
    import tlo_tag_lib as tag

    source = tmp_path / "Complete Cross Partition Folder"
    destination = tmp_path / "processed"
    source.mkdir()
    destination.mkdir()
    _populate_full_folder_tree(source)
    group, record = _group_and_record(source)

    monkeypatch.setattr(tag, "_paths_on_same_filesystem", lambda _a, _b: False)
    tag.prepare_inventory_copy_delete_target(
        SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=False),
        group,
        record,
    )

    copied_root = destination / source.name
    assert not source.exists()
    _assert_full_folder_tree(copied_root)


def test_tag_copy_copies_entire_folder_tree_and_keeps_source(tmp_path):
    import tlo_tag_lib as tag

    source = tmp_path / "Complete Tag Copy Folder"
    destination = tmp_path / "copies"
    source.mkdir()
    destination.mkdir()
    _populate_full_folder_tree(source)
    group, record = _group_and_record(source)

    tag.prepare_inventory_tagging_target(
        SimpleNamespace(
            tag_copy_during_inventory=True,
            tag_copy_destination=str(destination),
            rename_compliantly=False,
        ),
        group,
        record,
    )

    copied_root = destination / source.name
    _assert_full_folder_tree(source)
    _assert_full_folder_tree(copied_root)
