"""Build 427 regressions for show/format/part directory layouts."""

__version__ = "v446"

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _build_groups(tmp_path: Path, root: Path):
    import logging_lib
    import tlo_phase23_v2 as phase
    from initial_dir_walk_lib import initial_dir_walk

    config = SimpleNamespace(
        TLOHome=str(tmp_path / "home"),
        performance_mode="balanced",
        silent=True,
        compliant=False,
    )
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(root), 1, log_token="W")
    initial_dir_walk(config, str(root))
    return phase._build_groups_from_search_path(config, str(root))


@pytest.mark.parametrize(
    "part_names",
    [
        ("Set 1", "Set 2"),
        ("Disc 1", "Disc 2"),
        ("Disk1", "Disk2"),
        ("CD1", "CD2"),
        ("D1", "D2"),
    ],
)
def test_date_show_format_wrapper_and_numbered_parts_form_one_show(tmp_path: Path, part_names):
    root = tmp_path / "boots"
    show = root / "Suzi Quatro - 2020-02-26 - Vienna, Austria (AUD) FLAC"
    container = show / "FLAC"
    setlist = show / "Suzi Quatro - 2020-02-26 - Vienna, Austria.txt"
    setlist.parent.mkdir(parents=True)
    setlist.write_text(
        "Suzi Quatro\n\nStadthalle\nVienna, Austria\n2020-February-26\n\n"
        "SET 1:\n01. The Wild One\n02. Daytona Demon\n\n"
        "SET 2:\n01. Rock Hard\n02. Can The Can\n",
        encoding="utf-8",
    )
    expected_dirs = []
    for part_name in part_names:
        part = container / part_name
        part.mkdir(parents=True)
        expected_dirs.append(os.path.normpath(str(part)))
        (part / "01.flac").write_bytes(b"audio")
        (part / "02.flac").write_bytes(b"audio")

    groups = _build_groups(tmp_path, root)

    assert len(groups) == 1
    group = groups[0]
    assert group["main_dir_path"] == os.path.normpath(str(show))
    assert group["main_dir_name"] == show.name
    assert group["music_dirs"] == expected_dirs
    assert group["music_file_count"] == 4
    assert group["setlist_file"] == os.path.normpath(str(setlist))
    assert group["aggregation_reason"].startswith("nested_wrapper_container:FLAC/")

    import tlo_tag_lib as taglib
    from inventory_parser_lib import Config

    audio_files = taglib._rescan_group_audio_files(group)
    tracks, source, error = taglib._select_tracks_for_tagging(
        Config(debug=False, silent=True, TLOHome=str(tmp_path / "tag-home")),
        group,
        audio_files,
    )
    assert error is None
    assert source == "setlist"
    assert [Path(path).parent.name for path in audio_files] == [part_names[0]] * 2 + [part_names[1]] * 2
    assert [track["title"] for track in tracks] == [
        "The Wild One",
        "Daytona Demon",
        "Rock Hard",
        "Can The Can",
    ]


def test_nested_wrapper_promotion_does_not_absorb_sibling_shows(tmp_path: Path):
    root = tmp_path / "boots"
    expected = {}
    for artist, date in (("Artist One", "2020-02-26"), ("Artist Two", "2021-03-27")):
        show = root / f"{artist} {date} Venue City, ST"
        setlist = show / "setlist.txt"
        part = show / "FLAC" / "Set 1"
        part.mkdir(parents=True)
        (part / "01.flac").write_bytes(b"audio")
        setlist.write_text(f"{artist}\n{date}\n01 Song\n", encoding="utf-8")
        expected[os.path.normpath(str(show))] = os.path.normpath(str(setlist))

    groups = _build_groups(tmp_path, root)

    assert len(groups) == 2
    assert {group["main_dir_path"]: group["setlist_file"] for group in groups} == expected
    assert all(group["main_dir_path"] != os.path.normpath(str(root)) for group in groups)


def test_nested_wrapper_promotion_is_blocked_by_other_music_below_candidate_show(tmp_path: Path):
    root = tmp_path / "boots"
    show = root / "Artist 2020-02-26 Venue City, ST"
    part = show / "FLAC" / "Set 1"
    unrelated = show / "Opening Act 2020-02-26 Other Venue City, ST"
    part.mkdir(parents=True)
    unrelated.mkdir()
    (part / "01.flac").write_bytes(b"audio")
    (unrelated / "01.flac").write_bytes(b"audio")
    (show / "setlist.txt").write_text("Artist\n2020-02-26\n01 Song\n", encoding="utf-8")

    groups = _build_groups(tmp_path, root)

    assert len(groups) == 2
    assert all(group["main_dir_path"] != os.path.normpath(str(show)) for group in groups)
    assert {group["main_dir_path"] for group in groups} == {
        os.path.normpath(str(show / "FLAC")),
        os.path.normpath(str(unrelated)),
    }


def test_nested_wrapper_promotion_requires_date_bearing_show_folder(tmp_path: Path):
    root = tmp_path / "boots"
    archive = root / "Undated Archive"
    for part_name in ("Set 1", "Set 2"):
        part = archive / "FLAC" / part_name
        part.mkdir(parents=True)
        (part / "01.flac").write_bytes(b"audio")
    (archive / "setlist.txt").write_text("Artist\n01 Song\n", encoding="utf-8")

    groups = _build_groups(tmp_path, root)

    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == os.path.normpath(str(archive / "FLAC"))
    assert groups[0]["setlist_file"] == ""


def test_build427_documentation_contract():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = "\n".join(
        paragraph.text for paragraph in Document(root / "TLO_Inventory_Requirements_Working_v446.docx").paragraphs
    )
    manual = (root / "TLO_Inventory_User_Manual_v446.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v446 (v1.6 Build 446)." in requirements
    assert "Show/FLAC/Set 1 and Show/FLAC/Set 2" in requirements
    assert "must not enumerate or recursively revisit Show's sibling directories" in requirements
    assert "Version v1.6 Build 446" in manual
    assert "Show/FLAC/Set 1 and Show/FLAC/Set 2" in manual
    assert "It does not rescan sibling show folders" in manual
