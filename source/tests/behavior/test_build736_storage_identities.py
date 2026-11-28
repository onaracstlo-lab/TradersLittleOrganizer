"""Storage identity and destructive reconciliation contracts (all platforms)."""
from types import SimpleNamespace
import json
import shutil

import pytest

pytestmark = pytest.mark.behavior

import inventory_list_lib as inventory
import tlo_inventory_guard as guard
import tlo_storage_identities as storage
import tlo_copy_requests as copies
from tlo_bootlist_volume_policy import write_bootlist_rows, read_bootlist_rows


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / "tlo"
    home.mkdir()
    disk = tmp_path / "disk"
    disk.mkdir()
    root = disk / "Music"
    root.mkdir()
    hardware = {"label": "Archive", "mount": str(disk), "disk_serial": "SERIAL-A",
                "partition_guid": "part-1", "filesystem_uuid": "fs-1", "kind": "local"}
    monkeypatch.setattr(storage, "capture_storage", lambda _path: dict(hardware))
    return home, disk, root, hardware


def _register(home, path):
    return storage.resolve_root(str(home), str(path), register=True)


def test_label_change_and_new_mount_recognized(setup):
    home, disk, root, hardware = setup
    ident, entry = _register(home, root)
    target = disk.parent / "new-mount"
    disk.rename(target)
    hardware.update(mount=str(target), label="Renamed")
    now = target / "Music"
    again, updated = _register(home, now)
    assert again == ident
    assert updated["name"] == entry["name"] == "Archive"
    assert updated["volume_id"] == entry["volume_id"]
    assert updated["hardware"]["label"] == "Renamed"
    old = storage.stored_path(str(home), entry["name"], str(now / "show"))
    assert old == entry["prefix"] + "/show"
    assert storage.physical_path(updated, str(now), old) == str(now / "show")


def test_two_partitions_and_two_roots_do_not_share_inventory(setup):
    home, disk, root, hardware = setup
    first, a = _register(home, root)
    other = disk / "Other"
    other.mkdir()
    second, b = _register(home, other)
    assert first != second and a["name"] != b["name"]
    assert a["volume_id"] == b["volume_id"]
    hardware.update(partition_guid="part-2", filesystem_uuid="fs-2")
    third_root = disk / "Third"
    third_root.mkdir()
    _, c = _register(home, third_root)
    assert c["volume_id"] != a["volume_id"]


def test_same_share_name_different_folder_gets_different_identity(setup):
    home, disk, root, hardware = setup
    hardware.clear()
    hardware.update(label="UNC:server/music", mount=str(root), kind="network")
    a, old = _register(home, root)
    (root / "old show").mkdir()
    root.rename(disk / "offline")
    root.mkdir()
    (root / "new show").mkdir()
    b, new = _register(home, root)
    assert a != b and old["name"] != new["name"]
    verified = storage.verified_roots(str(home))
    assert not verified[old["name"].casefold()][1]
    assert verified[new["name"].casefold()][1] == str(root)


def test_clone_conflict_then_register_backup(setup):
    home, disk, root, hardware = setup
    original, old = _register(home, root)
    clone = disk / "Clone"
    shutil.copytree(root, clone)
    with pytest.raises(storage.StorageIdentityError, match="two connected folders"):
        _register(home, clone)
    new, replica = storage.resolve_root(str(home), str(clone), register=True,
                                        separate=True, collection_id=old["collection_id"])
    assert new != original and replica["collection_id"] == old["collection_id"]
    assert storage.read_marker(str(root)) == original
    assert storage.read_marker(str(clone)) == new


def test_clone_new_hardware_same_marker_refused(setup):
    home, _disk, root, hardware = setup
    _register(home, root)
    hardware["disk_serial"] = "SERIAL-B"
    with pytest.raises(storage.StorageIdentityError, match="clone or replacement"):
        _register(home, root)


def test_confirmed_replacement_retains_existing_inventory_name(setup):
    home, disk, root, hardware = setup
    ident, old = _register(home, root)
    root.rename(disk / "old")
    root.mkdir()
    hardware.update(disk_serial="SERIAL-B", partition_guid="part-B", filesystem_uuid="fs-B")
    new, replacement = storage.resolve_root(str(home), str(root), register=True, replacement_id=ident)
    assert new == ident
    assert replacement["name"] == old["name"]
    assert replacement["volume_id"] != old["volume_id"]
    assert replacement["previous_locations"][-1]["hardware"]["disk_serial"] == "SERIAL-A"


def test_readonly_unknown_identity_refuses_without_creating_registry(setup, monkeypatch):
    home, _disk, root, hardware = setup
    hardware.clear()
    hardware.update(label="network", mount=str(root), kind="network")
    monkeypatch.setattr(storage, "_create_marker", lambda *_a, **_k: False)
    with pytest.raises(storage.StorageIdentityError, match="read-only"):
        _register(home, root)
    assert not storage.load_registry(str(home))


def test_legacy_binding_requires_consent(setup):
    home, _disk, root, _hardware = setup
    write_bootlist_rows(str(home), [{"Show": "Old show", "Volume": "Archive", "Path": str(root / "old")}])
    _, item = storage.register_inventory_root(str(home), str(root), lambda message: True)
    assert item["name"] == "Archive"
    assert len(read_bootlist_rows(str(home))) == 1


def _prior_rows(home, root, item, count=4):
    rows = []
    for i in range(count):
        path = root / f"show{i}"
        path.mkdir()
        rows.append({"Show": f"Artist 2000-01-0{i+1}", "Volume": item["name"],
                     "Path": storage.stored_path(str(home), item["name"], str(path))})
    write_bootlist_rows(str(home), rows)
    return read_bootlist_rows(str(home))


def _config(home, root, item, callback):
    return SimpleNamespace(TLOHome=str(home), silent=True, storage_identity_enabled=True,
                           inventory_loss_callback=callback, inventory_path_actions=[{
                               "path": item["prefix"], "physical_path": str(root), "volume": item["name"],
                               "volume_key": item["name"].casefold(), "action": "reinventory",
                               "root_id": item["collection_id"]}],
                           inventory_loss_preapproved={})


def test_exact_25_percent_preflight_decline_keeps_bootlist(setup):
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    old = _prior_rows(home, root, item)
    (root / "show0").rmdir()
    seen = []
    config = _config(home, root, item, lambda message: seen.append(message) or False)
    with pytest.raises(storage.StorageIdentityError, match="not approved"):
        guard.preflight_inventory_loss(config, config.inventory_path_actions)
    assert "25.0%" in seen[0]
    assert read_bootlist_rows(str(home)) == old


def test_new_content_cannot_mask_loss_of_prior_performances(setup):
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    old = _prior_rows(home, root, item)
    messages = []
    config = _config(home, root, item, lambda msg: messages.append(msg) or False)
    records = [{"show_name": row["Show"], "artist": "Artist", "volume_label": item["name"],
                "main_dir_path": str(root / f"show{i}")} for i, row in enumerate(old)]
    records[0]["show_name"] = "Different Artist 2015-01-01"
    with pytest.raises(storage.StorageIdentityError, match="not approved"):
        guard.check_final_inventory_loss(config, old, records)
    assert "25.0%" in messages[0]
    assert read_bootlist_rows(str(home)) == old


def test_below_threshold_does_not_prompt(setup):
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    _prior_rows(home, root, item, 5)
    (root / "show0").rmdir()
    config = _config(home, root, item, lambda _msg: pytest.fail("20% is below threshold"))
    guard.preflight_inventory_loss(config, config.inventory_path_actions)


def test_scope_registration_uses_fresh_tokens_before_reconciliation(setup, monkeypatch):
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    _prior_rows(home, root, item)
    logs = home / "logs"
    logs.mkdir(exist_ok=True)
    original = logs / "groups1.log"
    original.write_text(f"SEARCH_PATH: [{item['name']}] {item['prefix']}\n", encoding="utf-8")
    config = SimpleNamespace(TLOHome=str(home), silent=True, storage_identity_enabled=True)
    monkeypatch.setattr(inventory, "_prepare_log_reuse_for_decision", lambda *_: pytest.fail("Prior logs must not be mutated"))
    out = inventory.apply_existing_volume_actions(config, [(str(root), "", "Archive", "disk")])
    assert out[0][4:6] == ("", "w")
    assert config.inventory_path_actions[0]["action"] == "reinventory"
    assert original.is_file()


def test_metadata_backup_and_restore_never_copies_audio(setup):
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    rows = _prior_rows(home, root, item)
    (root / "song.flac").write_bytes(b"music")
    config = SimpleNamespace(TLOHome=str(home), silent=True)
    guard.archive_inventory_metadata(config)
    write_bootlist_rows(str(home), [])
    guard.restore_inventory_metadata(config)
    assert read_bootlist_rows(str(home)) == rows
    import zipfile
    with zipfile.ZipFile(config.inventory_metadata_backup) as arc:
        assert not any(name.endswith(".flac") for name in arc.namelist())


def test_copy_resolution_never_falls_back_to_unverified_registered_label(setup):
    home, disk, root, hardware = setup
    _, item = _register(home, root)
    path = root / "show"
    path.mkdir()
    stored = storage.stored_path(str(home), item["name"], str(path))
    roots = copies._request_roots(str(home), {"archive": [str(disk)]})
    assert copies._physical_paths_for_volume_stored("Archive", stored, roots) == ([str(path)], True)
    hardware["disk_serial"] = "different"
    roots = copies._request_roots(str(home), {"archive": [str(disk)]})
    assert copies._physical_paths_for_volume_stored("Archive", stored, roots) == ([], False)


@pytest.mark.parametrize("style", ["GPT", "MBR"])
def test_windows_adapter_includes_hardware_and_partition(monkeypatch, style):
    monkeypatch.setattr(storage, "_wsl_drive_letter_for_path", lambda _: "E")
    monkeypatch.setattr(storage.shutil, "which", lambda _: "powershell.exe")
    data = {"disk_serial": "abc", "disk_unique_id": "unique", "partition_style": style,
            "partition_guid": "id" if style == "GPT" else "", "partition_offset": 4096,
            "partition_size": 1000000}
    monkeypatch.setattr(storage, "_run", lambda args: json.dumps(data))
    result = storage._windows_info("/mnt/e", wsl=True)
    assert result["disk_serial"] == "abc"
    assert result["partition_offset"] == "4096"
    assert result["partition_style"] == style
    assert ("partition_guid" in result) == (style == "GPT")


def test_wsl_failed_interop_is_optional(monkeypatch):
    monkeypatch.setattr(storage, "_wsl_drive_letter_for_path", lambda _: "E")
    monkeypatch.setattr(storage.shutil, "which", lambda _: "powershell.exe")
    monkeypatch.setattr(storage, "_run", lambda args: "")
    assert storage._windows_info("/mnt/e", wsl=True) == {}


def test_linux_adapter_uses_parent_disk_serial(monkeypatch):
    def run(args):
        if args[0] == "findmnt":
            return "/dev/sdb2"
        if args[-1] == "/dev/sdb2":
            return json.dumps({"blockdevices": [{"pkname": "sdb", "partuuid": "part-2", "uuid": "fs-2", "start": 200, "size": 500}]})
        return json.dumps({"blockdevices": [{"serial": "abc", "wwn": "xyz", "model": "disk", "size": 1000}]})
    monkeypatch.setattr(storage, "_run", run)
    result = storage._linux_info("/media/music")
    assert result["disk_serial"] == "abc"
    assert result["partition_guid"] == "part-2"


def test_mac_adapter_uses_partition_and_volume_uuid(monkeypatch):
    import plistlib
    def run(args, binary=False):
        assert binary
        data = {"ParentWholeDisk": "disk2", "DiskUUID": "partition", "VolumeUUID": "volume"} if args[-1] == "/Volumes/Music" else {"SerialNumber": "abc", "MediaName": "disk"}
        return plistlib.dumps(data)
    monkeypatch.setattr(storage, "_run", run)
    result = storage._mac_info("/Volumes/Music")
    assert result["disk_serial"] == "abc"
    assert result["partition_guid"] == "partition"
    assert result["filesystem_uuid"] == "volume"


def test_reverse_fails_closed_on_replacement_storage(setup):
    home, disk, root, hardware = setup
    ident, _entry = _register(home, root)
    (home / "logs").mkdir(exist_ok=True)
    source, dest = root / "old", root / "new"
    dest.mkdir()
    storage.record_folder_operation(str(home), f"RENAME_COMPLIANTLY: {source} -> {dest}")
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(source), str(dest), {})
    root.rename(disk / "former")
    root.mkdir()
    dest.mkdir()
    hardware.update(disk_serial="replacement", partition_guid="other", filesystem_uuid="newfs")
    storage.resolve_root(str(home), str(root), register=True, replacement_id=ident)
    assert not storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(source), str(dest), {})


def test_native_marker_round_trip(tmp_path):
    home = tmp_path / "tlo"
    root = tmp_path / "collection"
    root.mkdir()
    identity, record = storage.resolve_root(str(home), str(root), register=True)
    assert storage.read_marker(str(root)) == identity
    assert storage.resolve_root(str(home), str(root))[0] == identity
    assert record["volume_id"] and record["collection_id"]


def test_postprocess_decline_preserves_all_existing_metadata(setup):
    from tlo_postprocess import postprocess_metadata_outputs
    home, _disk, root, _hardware = setup
    _, item = _register(home, root)
    _prior_rows(home, root, item)
    setlists = home / "setlists"
    setlists.mkdir()
    old_setlist = setlists / "previous.txt"
    old_setlist.write_text("Previous setlist", encoding="utf-8")
    old_bootlist = (home / "bootlist.csv").read_bytes()
    config = _config(home, root, item, lambda _msg: False)
    config.current_metadata_records_ready = True
    config.current_metadata_records = []
    with pytest.raises(storage.StorageIdentityError, match="not approved"):
        postprocess_metadata_outputs(config)
    assert (home / "bootlist.csv").read_bytes() == old_bootlist
    assert old_setlist.read_text(encoding="utf-8") == "Previous setlist"
    config.inventory_loss_callback = lambda _msg: True
    postprocess_metadata_outputs(config)
    assert read_bootlist_rows(str(home)) == []
    guard.restore_inventory_metadata(config)
    assert (home / "bootlist.csv").read_bytes() == old_bootlist
    assert old_setlist.read_text(encoding="utf-8") == "Previous setlist"


def test_replaced_local_root_without_marker_never_reuses_old_identity(setup):
    home, disk, root, _hardware = setup
    old_id, old = _register(home, root)
    (root / "Old content").mkdir()
    root.rename(disk / "old-folder")
    root.mkdir()
    (root / "Different content").mkdir()
    assert not storage.verified_roots(str(home))[old["name"].casefold()][1]
    new_id, new = _register(home, root)
    assert new_id != old_id
    assert new["name"] != old["name"]
    assert new["volume_id"] == old["volume_id"]
    assert storage.read_marker(str(root)) == new_id


def test_readonly_known_partition_keeps_markerless_identity(setup, monkeypatch):
    home, _disk, root, _hardware = setup
    monkeypatch.setattr(storage, "_create_marker", lambda *_a, **_k: False)
    ident, item = _register(home, root)
    assert not item["marker_required"]
    assert _register(home, root)[0] == ident
