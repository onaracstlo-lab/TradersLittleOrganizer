"""Build 421 regressions for validated Release (1)..(N) multipart track ordering."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
import tlo_tag_lib as T

__version__ = "v448"


def _make_part(tmp_path: Path, release: str, part: int, titles: list[str]) -> Path:
    folder = tmp_path / f"{release} ({part})"
    folder.mkdir()
    for track, title in enumerate(titles, start=1):
        (folder / f"{track:02d} - {title}.flac").write_bytes(b"x")
    return folder


def test_build421_parenthesized_release_parts_sort_part_then_track(tmp_path: Path):
    release = "Pink Floyd - 1988 Some More Secrets - Limited Edition Box Set"
    part1 = _make_part(tmp_path, release, 1, ["Introduction", "Song A", "Song B"])
    part2 = _make_part(tmp_path, release, 2, ["Echoes", "Song C"])
    part3 = _make_part(tmp_path, release, 3, ["Cymbaline", "Song D", "Song E"])

    files = [str(path) for folder in (part1, part2, part3) for path in folder.glob("*.flac")]
    ordered = [Path(path) for path in sorted(reversed(files), key=T._audio_track_order)]

    assert [(path.parent.name, path.name) for path in ordered] == [
        (f"{release} (1)", "01 - Introduction.flac"),
        (f"{release} (1)", "02 - Song A.flac"),
        (f"{release} (1)", "03 - Song B.flac"),
        (f"{release} (2)", "01 - Echoes.flac"),
        (f"{release} (2)", "02 - Song C.flac"),
        (f"{release} (3)", "01 - Cymbaline.flac"),
        (f"{release} (3)", "02 - Song D.flac"),
        (f"{release} (3)", "03 - Song E.flac"),
    ]


def test_build421_filename_fallback_track_numbers_do_not_interleave_parenthesized_parts(tmp_path: Path, monkeypatch):
    release = "Pink Floyd - 1988 Some More Secrets - Limited Edition Box Set"
    part1 = _make_part(tmp_path, release, 1, ["Introduction", "Song A", "Song B"])
    part2 = _make_part(tmp_path, release, 2, ["Echoes", "Song C"])
    part3 = _make_part(tmp_path, release, 3, ["Cymbaline", "Song D"])

    group = {
        "main_dir_path": str(tmp_path / release),
        "main_dir_name": release,
        "music_dirs": [str(part1), str(part2), str(part3)],
        "music_files": [],
        "setlist_file": "",
        "setlist_files": [],
    }
    record = SimpleNamespace(
        artist="Pink Floyd",
        date="",
        venue="",
        location="",
        parentheticals="",
        album_name="1988 Some More Secrets - Limited Edition Box Set",
        show_name=release,
    )
    written = []
    monkeypatch.setattr(
        T,
        "write_audio_tags",
        lambda path, artist, album, track_number, title, total_tracks=0: written.append(
            (Path(path).parent.name, Path(path).name, track_number, title)
        ),
    )

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    stats = T.tag_group_with_record(
        config,
        group,
        record,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
    )

    assert stats["errors"] == 0
    assert stats["tagged"] == 7
    assert [(folder, name, number) for folder, name, number, _title in written] == [
        (f"{release} (1)", "01 - Introduction.flac", "01"),
        (f"{release} (1)", "02 - Song A.flac", "02"),
        (f"{release} (1)", "03 - Song B.flac", "03"),
        (f"{release} (2)", "01 - Echoes.flac", "04"),
        (f"{release} (2)", "02 - Song C.flac", "05"),
        (f"{release} (3)", "01 - Cymbaline.flac", "06"),
        (f"{release} (3)", "02 - Song D.flac", "07"),
    ]


def test_build421_documentation_contract():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v448.docx")
    req_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v448.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v448 (v1.6 Build 448)." in req_text
    assert "Build 421 extends the same disc-first ordering" in req_text
    assert "Parent (1) through Parent (N)" in req_text
    assert "Version v1.6 Build 448" in manual_text
    assert "The same ordering applies to validated multipart release folders named Parent (1) through Parent (N)" in manual_text
    assert "stripe all track 01 files across the parts" in manual_text
