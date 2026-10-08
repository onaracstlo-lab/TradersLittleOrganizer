from __future__ import annotations

import subprocess

import pytest

import tlo_inventory_update as IU

pytestmark = pytest.mark.behavior


def test_build531_called_process_error_is_wrapped_and_duplicate_remains(tmp_path, monkeypatch):
    folder = tmp_path / "new-duplicate"
    folder.mkdir()
    marker = folder / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    def fail_trash(_path):
        raise subprocess.CalledProcessError(1, ["gio", "trash"])

    monkeypatch.setattr(IU, "move_to_trash", fail_trash)
    with pytest.raises(IU.InventoryUpdateError, match="it remains in place"):
        IU.delete_new_keep_old({"folder": str(folder)})

    assert folder.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep"
