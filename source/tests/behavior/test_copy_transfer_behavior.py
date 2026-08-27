"""Behavioral coverage for copy and Copy/Delete Original transfer verification."""

__version__ = "v407"

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


def _make_collision_tree(root, *, payload=b"same", add_empty=True):
    root.mkdir(parents=True, exist_ok=True)
    (root / "01 Song.flac").write_bytes(payload)
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / "info.txt").write_text("notes", encoding="utf-8")
    if add_empty:
        (root / "extras" / "empty").mkdir(parents=True, exist_ok=True)


def test_collision_name_uses_copy_only_for_byte_identical_tree(tmp_path):
    import tlo_tag_lib as tag

    destination = tmp_path / "destination"
    destination.mkdir()
    existing = destination / "Artist 1970-01-01 Venue City ST"
    incoming = tmp_path / "incoming"
    _make_collision_tree(existing, payload=b"identical")
    _make_collision_tree(incoming, payload=b"identical")

    allocated = tag._unique_destination_path(destination, existing.name, incoming)

    assert allocated == str(destination / f"{existing.name} (copy1)")


def test_collision_name_uses_alt_when_same_size_file_bytes_differ(tmp_path):
    import tlo_tag_lib as tag

    destination = tmp_path / "destination"
    destination.mkdir()
    existing = destination / "Artist 1970-01-01 Venue City ST"
    incoming = tmp_path / "incoming"
    _make_collision_tree(existing, payload=b"AAAA")
    _make_collision_tree(incoming, payload=b"BBBB")

    allocated = tag._unique_destination_path(destination, existing.name, incoming)

    assert allocated == str(destination / f"{existing.name} (alt1)")


def test_collision_name_uses_alt_when_folder_structure_differs(tmp_path):
    import tlo_tag_lib as tag

    destination = tmp_path / "destination"
    destination.mkdir()
    existing = destination / "Artist 1970-01-01 Venue City ST"
    incoming = tmp_path / "incoming"
    _make_collision_tree(existing, add_empty=True)
    _make_collision_tree(incoming, add_empty=False)

    allocated = tag._unique_destination_path(destination, existing.name, incoming)

    assert allocated == str(destination / f"{existing.name} (alt1)")


def test_collision_name_uses_alt_when_relative_file_set_differs(tmp_path):
    import tlo_tag_lib as tag

    destination = tmp_path / "destination"
    destination.mkdir()
    existing = destination / "Artist 1970-01-01 Venue City ST"
    incoming = tmp_path / "incoming"
    _make_collision_tree(existing)
    _make_collision_tree(incoming)
    (incoming / "artwork.jpg").write_bytes(b"art")

    allocated = tag._unique_destination_path(destination, existing.name, incoming)

    assert allocated == str(destination / f"{existing.name} (alt1)")


def test_collision_copy_classification_can_match_existing_family_member(tmp_path):
    import tlo_tag_lib as tag

    destination = tmp_path / "destination"
    destination.mkdir()
    base = "Artist 1970-01-01 Venue City ST"
    canonical = destination / base
    prior_alt = destination / f"{base} (alt1)"
    incoming = tmp_path / "incoming"
    _make_collision_tree(canonical, payload=b"different")
    _make_collision_tree(prior_alt, payload=b"incoming")
    _make_collision_tree(incoming, payload=b"incoming")

    allocated = tag._unique_destination_path(destination, base, incoming)

    assert allocated == str(destination / f"{base} (copy1)")


def test_tag_copy_collision_labels_exact_tree_copy(tmp_path):
    import tlo_tag_lib as tag

    source = tmp_path / "source" / "Original Name"
    destination = tmp_path / "copies"
    destination.mkdir(parents=True)
    source.mkdir(parents=True)
    _make_collision_tree(source)
    group, record = _group_and_record(source)
    record.show_name = "Artist 1970-01-01 Venue City ST"
    existing = destination / record.show_name
    _make_collision_tree(existing)

    copied_group, copied_record = tag.prepare_inventory_tagging_target(
        SimpleNamespace(
            tag_copy_during_inventory=True,
            tag_copy_destination=str(destination),
            rename_compliantly=True,
        ),
        group,
        record,
    )

    expected = destination / f"{record.show_name} (copy1)"
    assert copied_group["main_dir_path"] == str(expected)
    assert copied_record.main_dir_path == str(expected)
    assert expected.is_dir()


def test_rename_collision_labels_nonidentical_tree_alt(tmp_path):
    import tlo_tag_lib as tag

    parent = tmp_path / "shows"
    source = parent / "Original Name"
    source.mkdir(parents=True)
    _make_collision_tree(source, payload=b"incoming")
    group, record = _group_and_record(source)
    record.show_name = "Artist 1970-01-01 Venue City ST"
    existing = parent / record.show_name
    _make_collision_tree(existing, payload=b"existing")

    renamed_group, renamed_record = tag.prepare_inventory_tagging_target(
        SimpleNamespace(
            tag_copy_during_inventory=False,
            tag_copy_destination="",
            rename_compliantly=True,
        ),
        group,
        record,
    )

    expected = parent / f"{record.show_name} (alt1)"
    assert renamed_group["main_dir_path"] == str(expected)
    assert renamed_record.main_dir_path == str(expected)
    assert expected.is_dir()


def test_existing_copy_show_qualifier_requires_exact_sibling_tree(tmp_path):
    import tlo_phase23_v2 as phase

    base = tmp_path / "Artist 1970-01-01 Venue City ST"
    copied = tmp_path / "Artist 1970-01-01 Venue City ST (copy2)"
    _make_collision_tree(base, payload=b"same")
    _make_collision_tree(copied, payload=b"same")
    group = {"main_dir_path": str(copied), "main_dir_name": copied.name}

    assert phase._group_trailing_parentheticals(group) == "(copy2)"


def test_existing_copy_show_qualifier_becomes_alt_when_contents_differ(tmp_path):
    import tlo_phase23_v2 as phase

    base = tmp_path / "Artist 1970-01-01 Venue City ST"
    copied = tmp_path / "Artist 1970-01-01 Venue City ST (copy2)"
    _make_collision_tree(base, payload=b"AAAA")
    _make_collision_tree(copied, payload=b"BBBB")
    group = {"main_dir_path": str(copied), "main_dir_name": copied.name}

    assert phase._group_trailing_parentheticals(group) == "(alt2)"


def test_existing_copy_show_qualifier_becomes_alt_when_structure_differs(tmp_path):
    import tlo_phase23_v2 as phase

    base = tmp_path / "Artist 1970-01-01 Venue City ST"
    copied = tmp_path / "Artist 1970-01-01 Venue City ST (copy3)"
    _make_collision_tree(base, add_empty=True)
    _make_collision_tree(copied, add_empty=False)
    group = {"main_dir_path": str(copied), "main_dir_name": copied.name}

    assert phase._group_trailing_parentheticals(group) == "(alt3)"
