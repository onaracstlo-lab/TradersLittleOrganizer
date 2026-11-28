"""Log-owned storage identity: physical evidence, migration, archive and safety."""
import json
import shutil
import sqlite3
from contextlib import closing

import pytest

import logging_lib as logs
import tlo_storage_identities as storage
from tlo_bootlist_volume_policy import read_group_log_volume_rows

pytestmark = pytest.mark.behavior


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / "tlo"
    home.mkdir()
    disk = tmp_path / "disk"
    disk.mkdir()
    root = disk / "music"
    root.mkdir()
    hardware = dict(label="Archive", mount=str(disk), kind="local",
                    disk_serial="disk-123", disk_unique_id="wwn-1",
                    partition_guid="partition-1", filesystem_serial="aabbccdd",
                    model="unneeded", disk_size="1000000", partition_number="3",
                    partition_size="4000", partition_offset="4096", partition_style="GPT")
    monkeypatch.setattr(storage, "capture_storage", lambda _p: dict(hardware))
    return home, disk, root, hardware


def read_header(path):
    return [json.loads(line[len(storage.IDENTITY_PREFIX):]) for line in path.read_text().splitlines()
            if line.startswith(storage.IDENTITY_PREFIX)]


def test_log_identity_minimal_fields_and_reopen_updates_only_header(setup):
    home, disk, root, hardware = setup
    ident, initial = storage.resolve_root(str(home), str(root), register=True)
    assert not (home / storage.REGISTRY).exists()
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=initial["name"])
    manager.groups("GROUP_NUMBER: 1")
    manager.groups("MAIN_DIR_PATH: %s", root / "old")
    manager.groups("END_GROUP")
    from pathlib import Path
    group = Path(manager.paths.groups)
    records = read_header(group)
    assert len(records) == 1 and records[0]["root_id"] == ident
    fields = records[0]["entry"]["hardware"]
    assert set(fields) == {"label", "mount", "kind", "disk_serial", "disk_unique_id",
                           "partition_guid", "filesystem_serial"}
    assert fields["disk_serial"] == "disk-123"
    for path in (manager.paths.dead_end, manager.paths.duplicate, manager.paths.complete_paths,
                 manager.paths.conflicts, manager.paths.show_metadata, manager.paths.tag_success, manager.paths.tag_error):
        assert read_header(Path(path))[0]["root_id"] == ident
    prior = group.read_bytes()
    assert storage.load_registry(str(home))[ident]["name"] == "Archive"
    assert group.read_bytes() == prior  # read-only lookup
    manager._close_scope_handlers()
    newdisk = disk.parent / "newmount"
    disk.rename(newdisk)
    hardware.update(mount=str(newdisk), label="Renamed")
    newroot = newdisk / "music"
    manager.start_search_path(str(newroot), log_token="1", volume_label=initial["name"], log_mode="a")
    assert len(read_header(group)) == 1
    entry = read_header(group)[0]["entry"]
    assert entry["path"] == str(newroot) and entry["hardware"]["label"] == "Renamed"
    assert entry["last_seen"] >= initial["last_seen"]
    assert "GROUP_NUMBER: 1\nMAIN_DIR_PATH:" in group.read_text()
    assert read_group_log_volume_rows(str(home))[0]["Volume"] == "Archive"
    assert storage.load_registry(str(home))[ident]["path"] == str(newroot)
    manager._close_scope_handlers()


def test_same_label_different_disk_refuses_reuse_of_existing_header(setup):
    home, _disk, root, hardware = setup
    _, item = storage.resolve_root(str(home), str(root), register=True)
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=item["name"])
    manager._close_scope_handlers()
    from pathlib import Path
    group = Path(manager.paths.groups)
    before = group.read_bytes()
    hardware.update(disk_serial="other", disk_unique_id="other", partition_guid="other")
    with pytest.raises(storage.StorageIdentityError):
        manager.start_search_path(str(root), log_token="1", volume_label=item["name"], log_mode="a")
    assert group.read_bytes() == before
    assert read_header(group)[0]["entry"]["hardware"]["disk_serial"] == "disk-123"


def test_unregistered_scope_observation_never_adopts_or_guesses(setup):
    home, _disk, root, hardware = setup
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="F", volume_label="Archive")
    manager._close_scope_handlers()
    from pathlib import Path
    group = Path(manager.paths.groups)
    assert storage.OBSERVATION_PREFIX in group.read_text()
    assert not storage.load_registry(str(home))
    assert not (root / storage.MARKER).exists()
    hardware.update(disk_serial="other", partition_guid="other")
    manager.start_search_path(str(root), log_token="F", volume_label="Archive", log_mode="a")
    manager._close_scope_handlers()
    assert group.read_text().count(storage.OBSERVATION_PREFIX) == 2


def test_mbr_geometry_only_when_guid_unavailable_and_conflict(setup):
    home, _disk, root, hardware = setup
    hardware.pop("partition_guid")
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    assert item["hardware"]["partition_offset"] == "4096"
    assert item["hardware"]["partition_size"] == "4000"
    assert "partition_number" not in item["hardware"]
    hardware["partition_offset"] = "8192"
    with pytest.raises(storage.StorageIdentityError):
        storage.resolve_root(str(home), str(root), register=True)
    assert storage.load_registry(str(home))[ident]["hardware"]["partition_offset"] == "4096"


def test_legacy_json_and_sqlite_migrate_exactly_once_without_touching_originals(setup):
    home, _disk, root, _hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    durable = home / "logs" / storage.JOURNAL
    durable.unlink()
    legacy = home / storage.REGISTRY
    item["hardware"]["model"] = "old display-only field"
    legacy.write_text(json.dumps({"schema": 1, "roots": {ident: item}}))
    source, target = root / "before", root / "after"
    target.mkdir()
    evidence = [[ident, item["volume_id"], item["generation"]]] * 2
    db = home / "logs" / storage.LEGACY_OPERATIONS
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE operations (code TEXT, source TEXT, destination TEXT, identities TEXT)")
        conn.execute("INSERT INTO operations VALUES (?,?,?,?)",
                     ("RENAME_COMPLIANTLY", storage._path_key(source), storage._path_key(target), json.dumps(evidence)))
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")
    old_json, old_db = legacy.read_bytes(), db.read_bytes()
    assert storage.load_registry(str(home))[ident]["name"] == item["name"]
    assert not durable.exists()  # inspection never migrates
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(source), str(target), {})
    storage.resolve_root(str(home), str(root), register=True)
    assert durable.read_text().count(storage.MIGRATED) == 1
    assert durable.read_text().count(storage.OPERATION_PREFIX) == 1
    assert legacy.read_bytes() == old_json and db.read_bytes() == old_db
    storage.resolve_root(str(home), str(root), register=True)
    assert durable.read_text().count(storage.OPERATION_PREFIX) == 1
    legacy.unlink()
    db.unlink()
    assert storage.load_registry(str(home))[ident]["name"] == item["name"]
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(source), str(target), {})


def test_operation_evidence_survives_token_prune_truncate_and_copy(setup):
    home, _disk, root, _hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=item["name"])
    before, after = root / "before", root / "after"
    after.mkdir()
    manager.tag_success("RENAME_COMPLIANTLY: %s -> %s", before, after)
    manager._close_scope_handlers()
    assert not (home / "logs" / storage.LEGACY_OPERATIONS).exists()
    from pathlib import Path
    tag = Path(manager.paths.tag_success)
    assert storage.OPERATION_PREFIX in tag.read_text()
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(before), str(after), {})
    # Copy just the numbered tag log to a new TLOHome: its header carries identity.
    restored = home.parent / "restored"
    (restored / "logs").mkdir(parents=True)
    shutil.copy2(tag, restored / "logs" / tag.name)
    assert storage.load_registry(str(restored))[ident]["name"] == item["name"]
    assert storage.check_folder_operation(str(restored), "RENAME_COMPLIANTLY", str(before), str(after), {})
    logs.prune_logs_for_tokens_and_paths(str(home), ["1"], [str(root)])
    durable = home / "logs" / storage.JOURNAL
    assert storage.OPERATION_PREFIX in durable.read_text()
    logs.truncate_logs_for_tokens(str(home), ["1"])
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(before), str(after), {})
    assert storage.load_registry(str(home))[ident]["name"] == item["name"]


def test_failed_migration_does_not_destroy_legacy_data(setup, monkeypatch):
    home, _disk, root, _hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    journal = home / "logs" / storage.JOURNAL
    journal.unlink()
    legacy = home / storage.REGISTRY
    legacy.write_text(json.dumps({"schema": 1, "roots": {ident: item}}))
    before = legacy.read_bytes()
    def denied(*_args):
        raise PermissionError("test disk locked")
    monkeypatch.setattr(logs, "_atomic_rewrite_log", denied)
    with pytest.raises(PermissionError):
        storage.resolve_root(str(home), str(root), register=True)
    assert legacy.read_bytes() == before
    assert not journal.exists()
    assert storage.load_registry(str(home))[ident]["name"] == item["name"]


def test_copy_of_identity_header_does_not_override_newer_registration(setup):
    home, disk, root, hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=item["name"])
    manager._close_scope_handlers()
    root.rename(disk / "old")
    root.mkdir()
    hardware.update(disk_serial="replacement", disk_unique_id="wwn-new", partition_guid="part-new",
                    filesystem_serial="newfs")
    storage.resolve_root(str(home), str(root), replacement_id=ident, register=True)
    logs.truncate_logs_for_tokens(str(home), ["1"])
    assert storage.load_registry(str(home))[ident]["hardware"]["disk_serial"] == "replacement"


def test_conflicting_copied_generations_require_durable_log(setup):
    home, disk, root, hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=item["name"])
    manager._close_scope_handlers()
    root.rename(disk / "former")
    root.mkdir()
    hardware.update(disk_serial="other", disk_unique_id="other", partition_guid="newpart",
                    filesystem_serial="newfs")
    storage.resolve_root(str(home), str(root), replacement_id=ident, register=True)
    manager.start_search_path(str(root), log_token="2", volume_label=item["name"])
    manager._close_scope_handlers()
    recovered = home.parent / "recovered"
    (recovered / "logs").mkdir(parents=True)
    for name in ("groups1.log", "groups2.log"):
        shutil.copy2(home / "logs" / name, recovered / "logs" / name)
    with pytest.raises(storage.StorageIdentityError, match="conflicting storage generations"):
        storage.load_registry(str(recovered))
    shutil.copy2(home / "logs" / storage.JOURNAL, recovered / "logs" / storage.JOURNAL)
    assert storage.load_registry(str(recovered))[ident]["hardware"]["disk_serial"] == "other"


def test_archive_handles_legacy_last_line_without_newline(setup):
    home, _disk, root, _hardware = setup
    ident, item = storage.resolve_root(str(home), str(root), register=True)
    journal = home / "logs" / storage.JOURNAL
    # Historical file ending without a newline must not merge records.
    with journal.open("a", encoding="utf-8") as out:
        out.write("RENAME_COMPLIANTLY: /old -> /new")
    manager = logs.LogManager(str(home))
    manager.start_search_path(str(root), log_token="1", volume_label=item["name"])
    before, after = root / "before", root / "after"
    after.mkdir()
    manager.tag_success("RENAME_COMPLIANTLY: %s -> %s", before, after)
    manager._close_scope_handlers()
    logs.truncate_logs_for_tokens(str(home), ["1"])
    assert "RENAME_COMPLIANTLY: /old -> /new\n" in journal.read_text()
    assert storage.load_registry(str(home))[ident]["name"] == item["name"]
    assert storage.check_folder_operation(str(home), "RENAME_COMPLIANTLY", str(before), str(after), {})


@pytest.mark.parametrize("invalid_json", [False, True])
def test_legacy_read_closes_connection_on_success_and_failure(setup, monkeypatch, invalid_json):
    """Retain handles so POSIX also detects leaks that prevent Windows unlink."""
    home, _disk, _root, _hardware = setup
    directory = home / "logs"
    directory.mkdir()
    db = directory / storage.LEGACY_OPERATIONS
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("CREATE TABLE operations (code TEXT, source TEXT, destination TEXT, identities TEXT)")
        conn.execute("INSERT INTO operations VALUES (?,?,?,?)",
                     ("RENAME_COMPLIANTLY", "before", "after", "invalid" if invalid_json else "[]"))
    original_connect = sqlite3.connect
    opened = []

    def tracking_connect(*args, **kwargs):
        assert kwargs.get("uri") is True and args[0].endswith("?mode=ro")
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    try:
        if invalid_json:
            with pytest.raises(json.JSONDecodeError):
                storage._legacy_operation_records(str(home))
        else:
            assert storage._legacy_operation_records(str(home)) == [
                {"code": "RENAME_COMPLIANTLY", "source": "before", "destination": "after", "identities": []}
            ]
        assert len(opened) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            opened[0].execute("SELECT 1")
        db.rename(directory / "legacy-backup.sqlite")
    finally:
        for connection in opened:
            connection.close()
