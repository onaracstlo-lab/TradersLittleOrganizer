"""Build 478: Manual Updates optionally refresh tags before inventory commit."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_manual_updates as MU
from tlo_bootlist_volume_policy import format_volume_path, os_volume_label_for_path

pytestmark = pytest.mark.behavior
__version__ = "v478"


def _music_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    return path


def _inventory_volume_path(path: Path) -> str:
    """Use the canonical VolumePath format emitted by Full Inventory."""
    text = str(path)
    return format_volume_path(os_volume_label_for_path(text), text)


def test_build478_gui_update_tags_is_default_on_and_propagated_to_all_save_paths():
    source = Path(__file__).resolve().parents[2].joinpath("tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("class ManualUpdatesWindow:")
    end = source.index("class AddToInventoryWindow:", start)
    block = source[start:end]
    assert "self.update_tags_var = tk.BooleanVar(value=True)" in block
    assert 'text="Update Tags"' in block
    assert "update_tags = bool(self.update_tags_var.get())" in block
    assert "update_tags=update_tags" in block
    assert "self.update_tags_check.configure(state=state)" in block


def test_build478_existing_manual_update_tags_before_setlist_and_bootlist_commit(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = _music_dir(tmp_path / "library" / "Old Folder")
    MU.write_bootlist(str(home), [{"Show": "Old Folder", "VolumePath": _inventory_volume_path(original)}])
    events = []

    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {
        "show_name": "parser name", "main_dir_path": folder, "artist": "Artist", "album_name": "Album"
    })
    monkeypatch.setattr(MU, "_update_manual_folder_tags", lambda config, folder, record: (events.append("tags") or {"errors": 0, "skipped": 0}, []))
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home_, record: events.append("setlist") or "")
    real_write = MU.write_bootlist

    def tracked_write(home_, rows):
        events.append("bootlist")
        return real_write(home_, rows)

    monkeypatch.setattr(MU, "write_bootlist", tracked_write)
    result = MU.apply_folder_manual_update(
        SimpleNamespace(TLOHome=str(home)), str(original), "New Folder", update_tags=True
    )
    assert events[:3] == ["tags", "setlist", "bootlist"]
    assert result["update_tags"] == "yes"


def test_build478_unidentified_manual_update_tags_before_inventory_finalization(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = tmp_path / "old" / "Mystery"
    final = _music_dir(tmp_path / "dest" / "Named Show")
    (home / "unidentifiedShows.txt").write_text(str(original) + "\n", encoding="utf-8")
    events = []

    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {
        "show_name": "parser name", "main_dir_path": folder, "artist": "Artist", "album_name": "Album"
    })
    monkeypatch.setattr(MU, "_update_manual_folder_tags", lambda config, folder, record: (events.append("tags") or {"errors": 0, "skipped": 0}, []))
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home_, record: events.append("setlist") or "")
    real_write = MU.write_bootlist

    def tracked_write(home_, rows):
        events.append("bootlist")
        return real_write(home_, rows)

    monkeypatch.setattr(MU, "write_bootlist", tracked_write)
    result = MU.apply_unidentified_manual_update(
        SimpleNamespace(TLOHome=str(home)), str(original), "Named Show", str(final.parent), update_tags=True
    )
    assert events[:3] == ["tags", "setlist", "bootlist"]
    assert result["new_path"] == str(final)
    assert result["update_tags"] == "yes"


def test_build478_unchecked_update_tags_skips_tagging(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = _music_dir(tmp_path / "library" / "Old Folder")
    MU.write_bootlist(str(home), [{"Show": "Old Folder", "VolumePath": _inventory_volume_path(original)}])
    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home_, record: "")

    def should_not_run(*args, **kwargs):
        raise AssertionError("tagging should be skipped when Update Tags is unchecked")

    monkeypatch.setattr(MU, "_update_manual_folder_tags", should_not_run)
    result = MU.apply_folder_manual_update(
        SimpleNamespace(TLOHome=str(home)), str(original), "New Folder", update_tags=False
    )
    assert result["update_tags"] == "no"
    assert result["tag_stats"] == {}


def test_build478_batch_passes_update_tags_to_each_item(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    home.mkdir()
    one = tmp_path / "One"
    ctl = tmp_path / "manual.txt"
    ctl.write_text(f"{one} ----> New One\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(MU, "manual_update_source_kind", lambda home_, path: "inventory")
    monkeypatch.setattr(
        MU,
        "apply_folder_manual_update",
        lambda config, original, new_name, *, update_tags=False: calls.append(update_tags) or {
            "new_path": str(one), "tag_warnings": []
        },
    )
    result = MU.apply_manual_updates_file(SimpleNamespace(TLOHome=str(home)), str(ctl), update_tags=True)
    assert calls == [True]
    assert result["update_tags"] == "yes"
