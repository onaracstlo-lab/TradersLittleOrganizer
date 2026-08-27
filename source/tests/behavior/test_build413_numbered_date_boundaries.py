"""Build 413 regressions for dated subsection headings and numbering continuity."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
import tlo_tag_lib as T

__version__ = "v413"


TADD_DAMERON_INFO = """TADD DAMERON BAND SOUND IMPROVED AND FLAMBAY PITCH FIXED re-seed
Complete Royal Roost Broadcast 1948 (29 August) - 1949 (21 April)
Vol. 2 Historical Series Vol. 135, Philology W 5134

16.10.1948 - Royal Roost, NY - WMCA Radio broadcast
Tadd Dameron (ldr), Fats Navarro (t), Allen Eager (ts)
01 Jumpin' With Symphony Sid/Anthropology 4'48 normal .
02 Our Delight 4'00
03 The Tadd Walk 5'1923.10.1948 - Royal Roost, NY - WMCA Radio broadcast
Tadd Dameron (ldr), Fats Navarro (t), Allen Eager (ts)
04 Our Delight 4'14 One click removed
05 Good Bait 5'41 One click removed
06 Eb Pob 5'53 One click removed
07 The Squirrell 4'21

30.10.1948 - Royal Roost, NY - WMCA Radio broadcast
Tadd Dameron (ldr), Kai Winding (tb), Allen Eager (ts)
08 Tadd's Chase/ 3'42
09 Wahoo/ 5:47
10 LADY BE GOOD / 5:06
11 The Squirrell 03:24

06.11.1948 - Royal Roost, NY - WMCA Radio broadcast
Tadd Dameron (ldr), Kai Winding (tb), Allen Eager (ts)
12 Antropology 5'20
13 Wahoo 6'19
14 Tiny's Blues 3'28 7-8 clicks removed

total time : 67'30
Enjoy
"""


def _config(tmp_path: Path) -> Config:
    return Config(debug=False, silent=True, TLOHome=str(tmp_path))


def test_build413_tadd_dameron_dated_broadcast_sections_keep_1_through_14(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(TADD_DAMERON_INFO, encoding="utf-8")

    rows = T.parse_setlist_tracks(str(info))

    assert [row["original_number"] for row in rows] == list(range(1, 15))
    assert [row["normalized_number"] for row in rows] == list(range(1, 15))
    assert rows[7]["title"].startswith("Tadd's Chase")
    assert rows[8]["title"].startswith("Wahoo")
    assert rows[9]["title"].startswith("LADY BE GOOD")
    assert rows[13]["title"].startswith("Tiny's Blues")
    assert all("Royal Roost" not in row["title"] for row in rows)
    assert all(row["original_number"] != 30 for row in rows)


def test_build413_selection_does_not_turn_date_30_into_normalized_track_8(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(TADD_DAMERON_INFO, encoding="utf-8")
    audio = []
    for idx in range(1, 15):
        path = tmp_path / f"2-{idx:02d}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    rows, source, error = T._select_tracks_for_tagging(
        _config(tmp_path),
        {"setlist_file": str(info), "path": str(tmp_path)},
        audio,
        record=None,
    )

    assert error is None
    assert source == "setlist"
    assert len(rows) == 14
    assert [row["original_number"] for row in rows] == list(range(1, 15))
    assert not any(row["title"].casefold() == "unknown" for row in rows)


def test_build413_valid_numeric_date_with_context_is_boundary_not_track():
    assert T._is_track_subsection_date_heading("30.10.1948 - Royal Roost, NY - WMCA Radio broadcast") is True
    assert T._is_track_subsection_date_heading("06.11.1948: Royal Roost broadcast") is True
    assert T._is_track_subsection_date_heading("1948-10-30 - Royal Roost, NY") is True
    assert T._is_track_subsection_date_heading("31.02.1948 - impossible calendar date") is False


def test_build413_high_false_positive_is_discarded_when_expected_number_resumes(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "01 Song One\n02 Song Two\n03 Song Three\n04 Song Four\n05 Song Five\n06 Song Six\n07 Song Seven\n"
        "30. Not really track thirty\n"
        "08 Song Eight\n09 Song Nine\n",
        encoding="utf-8",
    )

    rows = T.parse_setlist_tracks(str(info))
    assert [row["original_number"] for row in rows] == list(range(1, 10))
    assert [row["title"] for row in rows][-2:] == ["Song Eight", "Song Nine"]
    assert "Not really track thirty" not in [row["title"] for row in rows]


def test_build413_confirmed_large_forward_number_gap_remains_supported(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "01 Song One\n02 Song Two\n30 Song Thirty\n31 Song Thirty One\n",
        encoding="utf-8",
    )

    rows = T.parse_setlist_tracks(str(info))
    assert [row["original_number"] for row in rows] == [1, 2, 30, 31]
    assert [row["title"] for row in rows] == ["Song One", "Song Two", "Song Thirty", "Song Thirty One"]


def test_build413_lost_newline_after_apostrophe_duration_drops_attached_date_heading():
    parsed = T._parse_track_line("03 The Tadd Walk 5'1923.10.1948 - Royal Roost, NY - WMCA Radio broadcast")
    assert parsed is not None
    number, title = parsed
    assert number == 3
    assert title == "The Tadd Walk 5'19"


def test_build413_requirements_and_manual_document_date_boundary_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v413.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v413.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v413 (v1.4 Build 413)." in req_text
    assert "Build 413 numbered-date-boundary and continuity rule" in req_text
    assert "30.10.1948" in req_text
    assert "01, 02, 30, 31" in req_text
    assert "Version v1.4 Build 413" in manual_text
    assert "Build 413 - Dated subsection boundaries and numbering continuity" in manual_text
    assert "30.10.1948 - Royal Roost, NY - WMCA Radio broadcast" in manual_text
    assert "Confirmed large gaps remain valid" in manual_text
