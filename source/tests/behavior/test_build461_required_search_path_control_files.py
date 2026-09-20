import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventory_list_lib as IL
from tlo_ux import _inventory_roots, validate_search_path

pytestmark = pytest.mark.behavior

__version__ = "v468"


def _touch_music(root: Path, name: str = "01.flac") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_bytes(b"x")
    return root


def test_build476_semicolon_search_path_uses_inventory_line_grammar(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    copies = tmp_path / "copies"
    copies.mkdir()

    value = f"{one} --$slam Artist One; {two} --$copy {copies} --$slam Artist Two"
    parsed = IL.parse_search_path_input(value)

    assert parsed[0] == (str(one), str(one), "Artist One", "")
    assert parsed[1] == (str(two), str(two), "Artist Two", "", "copy", str(copies))


def test_build461_separate_slam_field_remains_compatible_and_applies_to_direct_entries(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")

    parsed = IL.parse_search_path_input(f"{one};{two}", slam_override="Return to Forever")

    assert [item[2] for item in parsed] == ["Return to Forever", "Return to Forever"]


def test_build461_inline_and_separate_slam_are_rejected_as_ambiguous(tmp_path):
    one = _touch_music(tmp_path / "one")

    with pytest.raises(ValueError, match="separate Slam"):
        IL.parse_search_path_input(f"{one} --$slam One", slam_override="Two")


def test_build461_arbitrary_txt_search_path_uses_former_tobeinventoried_parser(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    copies = tmp_path / "copies"
    copies.mkdir()
    control = tmp_path / "my-next-run.txt"
    control.write_text(
        "# any .txt filename is valid\n"
        f"{one} --$slam Artist One\n"
        "REM second path follows\n"
        f"{two} --$copy-delete {copies} --$slam Artist Two\n",
        encoding="utf-8",
    )

    parsed = IL.parse_search_path_input(str(control))

    assert parsed[0] == (str(one), str(one), "Artist One", "")
    assert parsed[1] == (str(two), str(two), "Artist Two", "", "copy-delete", str(copies))


def test_build461_txt_control_file_can_be_combined_with_other_search_path_entries(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    three = _touch_music(tmp_path / "three")
    control = tmp_path / "roots.txt"
    control.write_text(f"{one}\n{two} --$slam Artist Two\n", encoding="utf-8")

    parsed = IL.parse_search_path_input(f"{control};{three}")

    assert [item[1] for item in parsed] == [str(one), str(two), str(three)]
    assert [item[2] for item in parsed] == ["", "Artist Two", ""]


def test_build461_global_directives_are_rejected_with_txt_control_file(tmp_path):
    one = _touch_music(tmp_path / "one")
    control = tmp_path / "roots.txt"
    control.write_text(f"{one}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"cannot be combined with a \.txt Search Path control file"):
        IL.parse_search_path_input(str(control), slam_override="Artist")


def test_build476_comma_inside_path_is_not_a_separator_and_quotes_are_optional(tmp_path):
    path_with_comma = _touch_music(tmp_path / "one,two")

    parsed_unquoted = IL.parse_search_path_input(str(path_with_comma))
    parsed_quoted = IL.parse_search_path_input(f'"{path_with_comma}"')

    assert len(parsed_unquoted) == 1
    assert parsed_unquoted[0][1] == str(path_with_comma)
    assert parsed_quoted[0][1] == str(path_with_comma)


def test_build461_tlohome_template_is_never_automatic_input(tmp_path):
    music = _touch_music(tmp_path / "music")
    (tmp_path / "toBeInventoried.txt").write_text(f"{music}\n", encoding="utf-8")

    status = validate_search_path("", str(tmp_path))
    assert status.valid is False
    assert "required" in status.message.lower()

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        search_path_override="",
        search_path_slam_override="",
        search_path_copy_override="",
        search_path_copy_delete_override="",
    )
    with pytest.raises(ValueError, match="Search Path is required"):
        IL.load_accessible_inventory_paths(config)


def test_build461_validate_search_path_accepts_multiple_roots_and_txt_file(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    direct = validate_search_path(f"{one};{two}", str(tmp_path))
    assert direct.valid is True
    assert "2 inventory roots" in direct.message

    control = tmp_path / "input.txt"
    control.write_text(f"{one}\n{two}\n", encoding="utf-8")
    from_file = validate_search_path(str(control), str(tmp_path))
    assert from_file.valid is True
    assert "2 inventory roots" in from_file.message


def test_build461_preview_roots_expand_txt_control_file(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    control = tmp_path / "whatever.txt"
    control.write_text(f"{one}\n{two}\n", encoding="utf-8")
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        search_path_override=str(control),
        search_path_slam_override="",
        search_path_copy_override="",
        search_path_copy_delete_override="",
    )

    assert _inventory_roots(config) == [
        (os.path.normpath(str(one)), "", ""),
        (os.path.normpath(str(two)), "", ""),
    ]


def test_build461_inventory_cli_requires_search_path(monkeypatch):
    import inventory_parser_lib as IPL

    monkeypatch.setattr(sys, "argv", ["tlo-gi.py"])
    with pytest.raises(SystemExit) as excinfo:
        IPL.parse_command_line()
    assert excinfo.value.code == 2


def test_build461_main_gui_label_and_slam_width_contract():
    source = Path(__file__).resolve().parents[2].joinpath("tlo-ggi.py").read_text(encoding="utf-8")

    assert 'text="Path(s)"' in source
    assert 'text="Search Path\\n(optional/override)"' not in source
    assert 'text="Slam (optional)"' not in source
    assert 'textvariable=self.vars["search_path_slam_override"]' not in source[source.index("    def _build(self):"):source.index("    def _enable_search_path_drag_drop")]


def test_build461_runtime_loader_expands_required_search_path_not_tlohome_template(tmp_path):
    one = _touch_music(tmp_path / "one")
    two = _touch_music(tmp_path / "two")
    stale = _touch_music(tmp_path / "stale")
    (tmp_path / "toBeInventoried.txt").write_text(f"{stale}\n", encoding="utf-8")
    control = tmp_path / "run-roots.txt"
    control.write_text(f"{two} --$slam Artist Two\n", encoding="utf-8")
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        search_path_override=f"{one};{control}",
        search_path_slam_override="",
        search_path_copy_override="",
        search_path_copy_delete_override="",
        tag_copy_and_delete_path="",
        tag_copy_during_inventory=False,
        tag_copy_destination="",
        silent=True,
    )

    loaded = IL.load_accessible_inventory_paths(config)

    assert [item[0] for item in loaded] == [str(one), str(two)]
    assert [item[1] for item in loaded] == ["", "Artist Two"]
    assert str(stale) not in [item[0] for item in loaded]


def test_build461_windows_search_path_drop_preserves_txt_control_file(tmp_path, monkeypatch):
    import tlo_dragdrop as DD

    control = tmp_path / "roots.txt"
    control.write_text("# template\n", encoding="utf-8")
    monkeypatch.setattr(DD, "is_windows_platform", lambda: True)

    class FakeTk:
        def splitlist(self, value):
            return (value,)

    class Widget:
        def __init__(self):
            self.tk = FakeTk()
            self.handler = None
        def drop_target_register(self, *_args):
            pass
        def dnd_bind(self, _name, handler):
            self.handler = handler
        def icursor(self, *_args):
            pass
        def focus_set(self):
            pass

    class Var:
        def __init__(self):
            self.value = ""
        def set(self, value):
            self.value = value

    widget = Widget()
    var = Var()
    status = DD.enable_search_path_folder_drop(widget, var)
    assert status.enabled is True
    assert widget.handler is not None
    widget.handler(SimpleNamespace(data=str(control)))
    assert var.value == os.path.normpath(str(control))
