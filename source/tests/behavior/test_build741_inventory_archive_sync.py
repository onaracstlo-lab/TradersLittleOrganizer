"""Inventory history ZIP finalization uses a writable durable handle."""
from __future__ import annotations

import builtins
import errno
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_inventory_guard as guard

pytestmark = pytest.mark.behavior


@pytest.fixture
def inventory_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "bootlist.csv").write_bytes(b"previous inventory\n")
    (home / "setlists").mkdir()
    (home / "setlists" / "previous.txt").write_bytes(b"previous setlist\n")
    return home


def test_metadata_zip_is_complete_and_synced_on_writable_handle(inventory_home, monkeypatch):
    """Model Windows _commit rejecting a read-only CRT descriptor on every OS."""
    config = SimpleNamespace(TLOHome=str(inventory_home), silent=True)
    opened = {}
    synced = []
    original_fsync = guard.os.fsync
    original_replace = guard.os.replace

    def tracking_open(*args, **kwargs):
        stream = builtins.open(*args, **kwargs)
        opened[stream.fileno()] = stream
        return stream

    def windows_fsync(fd):
        stream = opened[fd]
        if not stream.writable():
            raise OSError(errno.EBADF, "Bad file descriptor")
        # Verify the central directory and payload are already flushed before
        # requesting durability, but the writable descriptor is still open.
        with zipfile.ZipFile(stream.name) as arc:
            assert arc.testzip() is None
            assert arc.read("bootlist.csv") == b"previous inventory\n"
            assert arc.read("setlists/previous.txt") == b"previous setlist\n"
        original_fsync(fd)
        synced.append(stream)

    def checked_replace(source, destination):
        assert len(synced) == 1 and synced[0].closed
        assert Path(source).suffix == ".tmp"
        original_replace(source, destination)

    monkeypatch.setattr(guard, "open", tracking_open, raising=False)
    monkeypatch.setattr(guard.os, "fsync", windows_fsync)
    monkeypatch.setattr(guard.os, "replace", checked_replace)
    guard.archive_inventory_metadata(config)

    history = inventory_home / "logs" / "inventory-history"
    assert list(history.iterdir()) == [Path(config.inventory_metadata_backup)]
    assert Path(config.inventory_metadata_backup).suffix == ".zip"
    assert (inventory_home / "bootlist.csv").read_bytes() == b"previous inventory\n"


def test_metadata_zip_sync_failure_preserves_inventory_and_publishes_nothing(inventory_home, monkeypatch):
    config = SimpleNamespace(TLOHome=str(inventory_home), silent=True)

    def failed_sync(_fd):
        raise OSError(errno.EIO, "injected durability failure")

    def no_replace(*_args):
        pytest.fail("An unsynced ZIP must never be published")

    monkeypatch.setattr(guard.os, "fsync", failed_sync)
    monkeypatch.setattr(guard.os, "replace", no_replace)
    with pytest.raises(OSError, match="injected durability failure"):
        guard.archive_inventory_metadata(config)
    assert not getattr(config, "inventory_metadata_backup", "")
    assert not list((inventory_home / "logs" / "inventory-history").iterdir())
    assert (inventory_home / "bootlist.csv").read_bytes() == b"previous inventory\n"
    assert (inventory_home / "setlists" / "previous.txt").read_bytes() == b"previous setlist\n"
