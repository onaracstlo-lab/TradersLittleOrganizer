"""Build 475: Manual Updates can resolve persistent unidentified shows without moving files."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_manual_updates as MU
import tlo_bootlist_volume_policy as BP

pytestmark = pytest.mark.behavior


def _music_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    (path / "info.txt").write_text("Artist\nCollection notes\n", encoding="utf-8")
    return path


def test_unidentified_match_prefers_exact_path_then_unique_leaf(tmp_path):
    home = tmp_path / "TLOHome"
    home.mkdir()
    unresolved = home / "unidentifiedShows.txt"
    one = tmp_path / "old" / "Mystery Show"
    two = tmp_path / "elsewhere" / "Other Show"
    unresolved.write_text(f"{one}\n{two}\n", encoding="utf-8")
    assert MU.find_unidentified_show_path(str(home), str(one)) == str(one)
    assert MU.find_unidentified_show_path(str(home), str(tmp_path / "missing" / "Other Show")) == str(two)


def test_unidentified_duplicate_leaf_is_rejected(tmp_path):
    home = tmp_path / "TLOHome"
    home.mkdir()
    unresolved = home / "unidentifiedShows.txt"
    unresolved.write_text(
        f"{tmp_path / 'a' / 'Same'}\n{tmp_path / 'b' / 'Same'}\n",
        encoding="utf-8",
    )
    with pytest.raises(MU.ManualUpdateError, match="More than one unidentified show"):
        MU.find_unidentified_show_path(str(home), str(tmp_path / "x" / "Same"))


def test_destination_accepts_parent_or_final_folder(tmp_path):
    parent = tmp_path / "destination"
    final = _music_dir(parent / "New Name")
    p1, f1 = MU.resolve_unidentified_destination(str(parent), "New Name")
    p2, f2 = MU.resolve_unidentified_destination(str(final), "New Name")
    assert Path(p1) == parent
    assert Path(f1) == final
    assert Path(p2) == parent
    assert Path(f2) == final


def test_unidentified_manual_update_does_not_move_or_rename_and_updates_inventory(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    setlists = home / "setlists"
    setlists.mkdir(parents=True)
    original = tmp_path / "old-library" / "Mystery Original"
    original.parent.mkdir(parents=True)
    # The old path intentionally does not exist: the user already moved/renamed it manually.
    destination_parent = tmp_path / "new-library"
    final = _music_dir(destination_parent / "New Collection Name")
    other = tmp_path / "old-library" / "Still Unresolved"
    (home / "unidentifiedShows.txt").write_text(f"{original}\n{other}\n", encoding="utf-8")
    MU.write_bootlist(str(home), [{"Show": "Existing", "VolumePath": str(tmp_path / "existing")}])

    seen = {}
    def fake_identify(config, folder):
        seen["folder"] = folder
        return {"show_name": "Parser Guess", "main_dir_path": folder}
    def fake_setlist(tlo_home, record):
        target = Path(tlo_home) / "setlists" / "New Collection Name.txt"
        target.write_text("generated", encoding="utf-8")
        return str(target)
    monkeypatch.setattr(MU, "identify_folder_dict", fake_identify)
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", fake_setlist)

    result = MU.apply_unidentified_manual_update(
        SimpleNamespace(TLOHome=str(home)),
        str(original),
        "New Collection Name",
        str(destination_parent),
    )

    assert Path(result["new_path"]) == final
    assert seen["folder"] == str(final)
    assert final.is_dir()
    assert not original.exists()
    rows = MU.read_bootlist(str(home))
    assert {"Show": "New Collection Name", "VolumePath": BP.format_volume_path("", str(final))} in rows
    remaining = (home / "unidentifiedShows.txt").read_text(encoding="utf-8").splitlines()
    assert str(original) not in remaining
    assert str(other) in remaining
    assert (setlists / "New Collection Name.txt").is_file()


def test_batch_file_unidentified_line_uses_supplied_destination(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = tmp_path / "old" / "Mystery"
    dest_parent = tmp_path / "dest"
    final = _music_dir(dest_parent / "Named Show")
    (home / "unidentifiedShows.txt").write_text(str(original) + "\n", encoding="utf-8")
    ctl = tmp_path / "manual.txt"
    ctl.write_text(f"{original} ----> Named Show\n", encoding="utf-8")
    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home_, record: "")

    result = MU.apply_manual_updates_file(
        SimpleNamespace(TLOHome=str(home)),
        str(ctl),
        unidentified_destinations={1: str(dest_parent)},
    )
    assert result["updated"] == 1
    assert result["errors"] == []
    assert MU.read_bootlist(str(home)) == [{"Show": "Named Show", "VolumePath": BP.format_volume_path("", str(final))}]


def test_v17_gui_prompt_contract():
    root = Path(__file__).resolve().parents[2]
    source = (root / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'dialog.title("Where is the unidentified show going?")' in source
    assert 'text="Path"' in source
    assert "enable_folder_path_drop(" in source
    assert "apply_unidentified_manual_update(" in source
    assert "manual_update_source_kind(" in source
