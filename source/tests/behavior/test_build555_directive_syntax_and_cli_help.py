import importlib.util
from pathlib import Path

import pytest

import inventory_list_lib as IL
import inventory_parser_lib as IPL
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _load_main_module():
    spec = importlib.util.spec_from_file_location("tlo_main_build555", ROOT / "tlo-main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build555_inline_slash_directives_parse_in_any_order(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "01.flac").write_bytes(b"x")

    parsed = IL.parse_search_path_input(
        f'{source} --/copy {destination} --/slam "Artist Name"'
    )

    assert len(parsed) == 1
    assert parsed[0][1] == str(source)
    assert parsed[0][2] == "Artist Name"
    assert parsed[0][4:] == ("copy", str(destination))


def test_build555_copy_delete_slash_directive_parses(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "01.flac").write_bytes(b"x")

    parsed = IL.parse_search_path_input(
        f"{source} --/copy-delete {destination} --/slam Artist Name"
    )

    assert parsed[0][2] == "Artist Name"
    assert parsed[0][4:] == ("copy-delete", str(destination))


def test_build555_inventory_cli_accepts_only_slash_directive_options(tmp_path):
    parser = IPL.build_inventory_parser()
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    args = parser.parse_args(
        [
            "--search-path",
            str(source),
            "--/slam",
            "Artist Name",
            "--/copy",
            str(destination),
        ]
    )
    assert args.search_path_slam_override == "Artist Name"
    assert args.search_path_copy_override == str(destination)

    old_slam = "--" + chr(36) + "slam"
    with pytest.raises(SystemExit):
        parser.parse_args(["--search-path", str(source), old_slam, "Artist Name"])


def test_build555_main_gui_parser_accepts_slash_directives_and_rejects_old_marker(tmp_path):
    main = _load_main_module()
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    args = main._parse_gui_command_line(
        ["--search-path", str(source), "--/slam", "Artist", "--/copy", str(destination)]
    )
    assert args.search_path_slam_override == "Artist"
    assert args.search_path_copy_override == str(destination)

    old_copy = "--" + chr(36) + "copy"
    with pytest.raises(SystemExit):
        main._parse_gui_command_line(["--search-path", str(source), old_copy, str(destination)])


def test_build555_inventory_help_uses_slash_directives_and_clean_defaults():
    help_text = IPL.build_inventory_parser().format_help()
    compact = " ".join(help_text.split())

    assert "--/slam STRING" in compact
    assert "--/copy DIR" in compact
    assert "--/copy-delete DIR" in compact
    assert "(default: True)" not in help_text
    assert "(default: )" not in help_text
    assert "(default: None)" not in help_text
    assert "By default, Album tags begin with the artist name" in compact


def test_build555_shared_cli_help_is_not_gui_instruction_text():
    from tlo_options import OPTIONS_BY_FIELD

    assert "GUI" not in OPTIONS_BY_FIELD["tag_copy_destination"].help
    assert "GUI" not in OPTIONS_BY_FIELD["tag_copy_and_delete_enabled"].help
    assert "--tag-copy-during-inventory" in OPTIONS_BY_FIELD["tag_copy_destination"].help


def test_build555_live_sources_do_not_advertise_dollar_directives():
    needle_slam = chr(36) + "slam"
    needle_copy = chr(36) + "copy"
    checked = [
        ROOT / "inventory_list_lib.py",
        ROOT / "inventory_parser_lib.py",
        ROOT / "tlo-main.py",
        ROOT / "tlo_options.py",
        ROOT / "TLO-FAQ.txt",
        ROOT / RA.MANUAL_FILENAME,
    ]
    for path in checked:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert needle_slam not in text, path.name
        assert needle_copy not in text, path.name
