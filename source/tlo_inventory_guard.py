"""Safeguards for replacement of existing inventory metadata."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

from console_output_lib import console_print
from tlo_bootlist_volume_policy import (
    read_bootlist_rows, read_group_log_volume_rows, path_is_same_or_under,
    normalize_path_for_compare, volume_key,
)
from tlo_storage_identities import (
    registered_entry, physical_path, stored_path, StorageIdentityError, resolve_root,
)


def _scope_rows(rows, decision):
    return [r for r in rows if volume_key(r.get("Volume", "")) == decision["volume_key"]
            and path_is_same_or_under(r.get("Path", ""), decision["path"])]


def _confirm(config, decision, total, missing, stage):
    # Integer math gives an exact, inclusive 25% threshold.
    if not total or missing * 4 < total:
        return
    message = (
        f"Significant inventory change: {decision.get('physical_path', decision['path'])}\n"
        f"Previously inventoried: {total}\n"
        f"Previous performances missing or changed: {missing} ({missing / total:.1%})\n\n"
        "Check that the correct drive/folder is connected. "
        + ("No scan has started. " if stage == "before scan" else
           "The scan has completed; any media changes already made are not undone. ")
        + "The old inventory is retained unless you choose Continue. "
        "If you continue, TLO saves the previous inventory metadata before replacing it."
    )
    console_print(config, message, error=True)
    callback = getattr(config, "inventory_loss_callback", None)
    if callable(callback):
        accepted = callback(message) is True
    elif not getattr(config, "silent", False) and sys.stdin.isatty():
        try:
            accepted = input("Continue replacing this inventory? Type YES: ").strip() == "YES"
        except (EOFError, KeyboardInterrupt):
            accepted = False
    else:
        accepted = False
    if not accepted:
        raise StorageIdentityError("Significant inventory loss not approved. Previous inventory retained.")
    config.inventory_loss_approved = True


def preflight_inventory_loss(config, decisions):
    """Check missing old performance directories before starting any scan."""
    rows = read_bootlist_rows(config.TLOHome)
    approvals = {}
    for decision in decisions:
        if decision["action"] != "reinventory":
            continue
        previous = _scope_rows(rows, decision)
        item = registered_entry(config.TLOHome, decision["volume"])
        if not item or not previous:
            continue
        # A failed access check is indistinguishable from a missing directory.
        missing = sum(not os.path.isdir(physical_path(item, item["path"], row["Path"]))
                      for row in previous)
        _confirm(config, decision, len(previous), missing, "before scan")
        if missing * 4 >= len(previous):
            approvals[(decision["volume_key"], decision["path"])] = missing
    config.inventory_loss_preapproved = approvals


def check_final_inventory_loss(config, replaced, records):
    """Compare the prior population, not just the net number of new rows."""
    from tlo_postprocess import _prepare_record_for_bootlist_export
    for decision in getattr(config, "inventory_path_actions", []):
        if decision.get("root_id"):
            identity = resolve_root(config.TLOHome, decision["physical_path"])
            if not identity or identity[0] != decision["root_id"]:
                raise StorageIdentityError("Storage identity changed during inventory. Previous inventory retained.")
    # New shows cannot mask the disappearance of prior shows. Include the
    # original path so a rename made by this run doesn't count as a loss.
    current = {}
    for record in records:
        prepared = _prepare_record_for_bootlist_export(record)
        if prepared.get("_postprocess_skip_row") == "yes":
            continue
        name = prepared.get("volume_label", "")
        show = prepared.get("show_name", "").casefold()
        paths = {normalize_path_for_compare(stored_path(config.TLOHome, name, p))
                 for p in (prepared.get("main_dir_path"), prepared.get("original_main_dir_path")) if p}
        for path in paths:
            current.setdefault((volume_key(name), path), Counter())[show] += 1
    approvals = getattr(config, "inventory_loss_preapproved", {})
    for decision in getattr(config, "inventory_path_actions", []):
        if decision["action"] != "reinventory":
            continue
        previous = _scope_rows(replaced, decision)
        if not previous:
            continue
        expected = Counter((normalize_path_for_compare(row.get("Path", "")),
                            row.get("Show", "").casefold()) for row in previous)
        missing = sum(max(0, count - current.get((decision["volume_key"], path), {}).get(show, 0))
                      for (path, show), count in expected.items())
        if missing <= approvals.get((decision["volume_key"], decision["path"]), -1):
            continue
        _confirm(config, decision, len(previous), missing, "after scan")


def _history_dir(home):
    folder = Path(home) / "logs" / "inventory-history"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _unique_name(prefix):
    return f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"


def archive_inventory_metadata(config):
    """Durable ZIP of the previous inventory, not the audio collection."""
    home = Path(config.TLOHome)
    target = _history_dir(home) / (_unique_name("inventory") + ".zip")
    pending = target.with_suffix(".tmp")
    try:
        # Keep the writable stream open through ZIP finalization and fsync.
        # Windows CRT _commit (os.fsync) can reject a read-only descriptor.
        # Closing the ZipFile writes its central directory before we flush;
        # close the underlying file before the Windows-compatible replace.
        with open(pending, "wb") as stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as out:
                for name in ("bootlist.csv", "setlist-index.json", "unidentifiedShows.txt", "artistsNotInDatabase.txt"):
                    path = home / name
                    if path.is_file():
                        out.write(path, name)
                # The durable identity and reversal trail is now an existing log.
                journal = home / "logs" / "folderOperations.log"
                if journal.is_file():
                    out.write(journal, "logs/folderOperations.log")
                folder = home / "setlists"
                if folder.is_dir():
                    for path in folder.iterdir():
                        if path.is_file() and not path.is_symlink():
                            out.write(path, path.relative_to(home).as_posix())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
    finally:
        if pending.exists():
            pending.unlink()
    config.inventory_metadata_backup = str(target)
    console_print(config, f"Previous inventory metadata saved: {target}")


def restore_inventory_metadata(config):
    """Restore metadata outputs after an exception during finalization."""
    backup = getattr(config, "inventory_metadata_backup", "")
    if not backup:
        return
    home = Path(config.TLOHome)
    with zipfile.ZipFile(backup) as src:
        # Only our explicitly enumerated files are restored. Storage identity history
        # is not rolled back; it may include a valid new registration.
        managed = ("bootlist.csv", "setlist-index.json", "unidentifiedShows.txt", "artistsNotInDatabase.txt")
        names = set(src.namelist())
        for name in managed:
            dest = home / name
            if name in names:
                tmp = dest.with_name(dest.name + ".restore")
                tmp.write_bytes(src.read(name))
                os.replace(tmp, dest)
            elif dest.is_file():
                dest.unlink()
        folder = home / "setlists"
        folder.mkdir(exist_ok=True)
        for path in folder.iterdir():
            if path.is_file() and not path.is_symlink() and path.relative_to(home).as_posix() not in names:
                path.unlink()
        for name in names:
            if name.startswith("setlists/") and "/" not in name[len("setlists/"):]:
                dest = home / name
                tmp = dest.with_name(dest.name + ".restore")
                tmp.write_bytes(src.read(name))
                os.replace(tmp, dest)


def _archive_tokens(home, tokens, prefix):
    from logging_lib import LOG_FILE_PREFIXES, _log_path_for_prefix, _suspend_file_log_handlers, archive_folder_operations
    if not tokens:
        return
    archive_folder_operations(home, tokens)
    target = _history_dir(home) / _unique_name(prefix)
    target.mkdir()
    for token in tokens:
        if not str(token).isalnum():
            raise ValueError("Invalid inventory log token.")
        for log_prefix in set(LOG_FILE_PREFIXES.values()):
            path = _log_path_for_prefix(str(Path(home) / "logs"), log_prefix, token)
            if os.path.isfile(path):
                with _suspend_file_log_handlers(path):
                    shutil.copy2(path, target / os.path.basename(path))
                    os.unlink(path)


def preserve_aborted_logs(config):
    restore_inventory_metadata(config)
    tokens = getattr(config, "newly_allocated_log_tokens", [])
    _archive_tokens(config.TLOHome, tokens, "incomplete")


def retire_previous_logs(config):
    """Only retire previous scope logs after successful metadata output."""
    if not getattr(config, "storage_identity_enabled", False):
        return
    from logging_lib import prune_logs_for_tokens_and_paths
    old_rows = read_group_log_volume_rows(config.TLOHome)
    decisions = [d for d in getattr(config, "inventory_path_actions", []) if d.get("action") == "reinventory"]
    new_tokens = set(getattr(config, "current_run_log_tokens", []))
    old_tokens = {token for d in decisions for token in d.get("related_tokens", [])} - new_tokens
    for token in sorted(old_tokens):
        related = [r for r in old_rows if r["Token"] == token]
        applicable = [d for d in decisions if token in d.get("related_tokens", [])]
        if related and all(any(volume_key(row["Volume"]) == d["volume_key"] and
                                path_is_same_or_under(row["Path"], d["path"]) for d in applicable)
                           for row in related):
            _archive_tokens(config.TLOHome, [token], "previous-logs")
        else:
            # The token also owns an unrelated/parent scope. Keep its headers
            # and prune only the replaced subtree, using prior mount spellings.
            paths = []
            for d in applicable:
                paths.append(d.get("physical_path", d["path"]))
                item = registered_entry(config.TLOHome, d["volume"])
                if item:
                    for location in item.get("previous_locations", []):
                        p = physical_path(item, location["path"], d["path"])
                        if p:
                            paths.append(p)
            prune_logs_for_tokens_and_paths(config.TLOHome, [token], paths)
