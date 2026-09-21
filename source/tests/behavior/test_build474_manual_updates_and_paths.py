import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventory_list_lib as IL
import tlo_manual_updates as MU
import tlo_bootlist_volume_policy as BP

pytestmark = pytest.mark.behavior


def _music_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    return path


def test_build476_path_field_uses_semicolon_separated_tobeinventoried_grammar(tmp_path):
    one = _music_dir(tmp_path / "one")
    two = _music_dir(tmp_path / "two")
    dest = tmp_path / "dest"
    dest.mkdir()
    parsed = IL.parse_search_path_input(f'{one} --$slam "Artist, One";{two} --$copy {dest}')
    assert parsed[0][1] == str(one)
    assert parsed[0][2] == "Artist, One"
    assert parsed[1][1] == str(two)
    assert parsed[1][4:] == ("copy", str(dest))


def test_build474_manual_file_comments_and_path_arrow_name(tmp_path):
    one = tmp_path / "one"
    two = tmp_path / "two"
    ctl = tmp_path / "manual.txt"
    ctl.write_text(
        "# comment\nREM another comment\n\n"
        f'"{one}" ----> New One\n'
        f"{two} ----> New Two\n",
        encoding="utf-8",
    )
    items = MU.parse_manual_updates_file(str(ctl))
    assert [(x.original_path, x.new_name) for x in items] == [
        (os.path.normpath(str(one)), "New One"),
        (os.path.normpath(str(two)), "New Two"),
    ]


def test_build474_manual_file_rejects_bad_data_line(tmp_path):
    ctl = tmp_path / "manual.txt"
    ctl.write_text("C:/one -> New One\n", encoding="utf-8")
    with pytest.raises(MU.ManualUpdateError, match="Path ----> Folder Name"):
        MU.parse_manual_updates_file(str(ctl))


def test_build474_folder_save_renames_in_place_replaces_bootlist_and_setlist(tmp_path, monkeypatch):
    tlohome = tmp_path / "TLOHome"
    setlists = tlohome / "setlists"
    setlists.mkdir(parents=True)
    original = _music_dir(tmp_path / "library" / "Old Folder")
    old_setlist = setlists / "OldShow.txt"
    old_setlist.write_text("old", encoding="utf-8")
    MU.write_bootlist(str(tlohome), [{"Show": "Old Show", "VolumePath": BP.format_volume_path("", str(original))}])

    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {
        "show_name": "Ignored Parser Name",
        "main_dir_path": folder,
        "setlist_file": str(folder / Path("info.txt")) if isinstance(folder, Path) else "",
    })
    def fake_create(home, record):
        target = Path(home) / "setlists" / f"{record['show_name'].replace(' ', '')}.txt"
        target.write_text("new", encoding="utf-8")
        return str(target)
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", fake_create)

    result = MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(tlohome)), str(original), "New Folder")
    new_path = original.parent / "New Folder"
    assert Path(result["new_path"]) == new_path
    assert new_path.is_dir() and not original.exists()
    rows = MU.read_bootlist(str(tlohome))
    assert rows == [{"Show": "New Folder", "VolumePath": BP.format_volume_path("", str(new_path))}]
    assert not old_setlist.exists()
    assert (setlists / "NewFolder.txt").is_file()


def test_build474_folder_save_accepts_already_renamed_target(tmp_path, monkeypatch):
    tlohome = tmp_path / "TLOHome"
    (tlohome / "setlists").mkdir(parents=True)
    parent = tmp_path / "library"
    parent.mkdir()
    original = parent / "Old Folder"
    target = _music_dir(parent / "New Folder")
    MU.write_bootlist(str(tlohome), [{"Show": "Old Folder", "VolumePath": str(original)}])
    monkeypatch.setattr(MU, "identify_folder_dict", lambda config, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home, record: "")
    result = MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(tlohome)), str(original), "New Folder")
    assert Path(result["new_path"]) == target
    assert MU.read_bootlist(str(tlohome))[0]["Show"] == "New Folder"


def test_build474_main_gui_contracts():
    source = Path(__file__).resolve().parents[2].joinpath("tlo-ggi.py").read_text(encoding="utf-8")
    block = source[source.index("    def _build(self):"):source.index("    def _enable_search_path_drag_drop")]
    assert 'text="Add New\\nShows"' in block
    assert 'text="Manual\\nTweaks"' in block
    assert 'command=self._open_manual_updates' in block
    assert 'text="Slam (optional)"' not in block
    assert 'style.configure("Main.Compact.TButton"' in source
    assert 'self.window.title("Manual Updates")' in source
    assert 'text="Original (to be edited)"' in source
    assert 'text="New Name"' in source
