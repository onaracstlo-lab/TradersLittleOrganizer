"""Build 412 regressions for explicit Set/CD/Disc/Disk song-region boundaries."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
import tlo_tag_lib as T

__version__ = "v446"


GARY_DAVIS_INFO = """Reverend Gary Davis
07/08/67
Friends' Center, Seattle, WA

SBD > ? > CDr > EAC > FLAC

Set 1
Introduction
Old Time Religion
Let Us Get Together
I'm Gonna Sit Down on the Banks of the River
The Reverend Speaks I
Feel Like My Time Ain't Long
The Reverend Speaks II
Teaching the audience the next song
Come Down to See Me Sometime
The Reverend Speaks III
She's Just Funny That Way
Make Believe Stunt
Cincinnati Flow Rag

on July 7, 1967:
The Reverend Speaks IV
I Heard the Angels Singing
Samson and Delilah

************************************************
DO NOT SELL OR CONVERT THIS TO ANY LOSSY FORMAT!
************************************************

1-01.flac:cb19df8322484dfddd4f690e10cbbee9
1-02.flac:f6d248f97939818bf5b6e0b35fdd868e
1-03.flac:9bb2fcd2ad22e1eae3d4859d69c5b59a
1-04.flac:fbfc6db80b4464b4a6291c7ae38cc94c
1-05.flac:e179b755d5046ace68e403cc03bbcfcc
1-06.flac:b7482dc1f0276b1c6987427da1334223
1-07.flac:28dfc27863b8ee0ac33de78abad8d9a3
1-08.flac:fa48d6415cf7a325f9e0a8a9d02aed41
1-09.flac:f3eb73b6d1a693e832e1c5c2e0fb1734
1-10.flac:bc89c5f6e8c1b982e9876d05aa467f77
1-11.flac:8fda09e0a88085607613944e77988c0b
1-12.flac:e2872584e95cd940104cdcdbd2612d40
1-13.flac:a53f230e236625dac09693f41e3887e3
1-14.flac:528ced31863c57acad57959463738064
1-15.flac:228336315d5c22730e92fce0eb50ac95
1-16.flac:c7f29d77be700fb5ebee8a8bc3e2fb65
-----------------------------------------------------
"""

GARY_DAVIS_TITLES = [
    "Introduction",
    "Old Time Religion",
    "Let Us Get Together",
    "I'm Gonna Sit Down on the Banks of the River",
    "The Reverend Speaks I",
    "Feel Like My Time Ain't Long",
    "The Reverend Speaks II",
    "Teaching the audience the next song",
    "Come Down to See Me Sometime",
    "The Reverend Speaks III",
    "She's Just Funny That Way",
    "Make Believe Stunt",
    "Cincinnati Flow Rag",
    "The Reverend Speaks IV",
    "I Heard the Angels Singing",
    "Samson and Delilah",
]


def _config(tmp_path: Path) -> Config:
    return Config(debug=False, silent=True, TLOHome=str(tmp_path))


def test_build412_reverend_gary_davis_uses_only_titles_after_set_boundary(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(GARY_DAVIS_INFO, encoding="utf-8")
    audio = []
    for idx in range(1, 17):
        path = tmp_path / f"1-{idx:02d}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    messages = []
    rows, source, error = T._select_tracks_for_tagging(
        _config(tmp_path),
        {"setlist_file": str(info), "path": str(tmp_path)},
        audio,
        emit=messages.append,
        record=None,
    )

    assert error is None
    assert source == "unnumbered-sections"
    assert [row["title"] for row in rows] == GARY_DAVIS_TITLES
    assert "Reverend Gary Davis" not in [row["title"] for row in rows]
    assert "Friends' Center, Seattle, WA" not in [row["title"] for row in rows]
    assert "SBD > ? > CDr > EAC > FLAC" not in [row["title"] for row in rows]
    assert any("unnumbered CD/Set section" in message for message in messages)


@pytest.mark.parametrize(
    "heading",
    ["Set 1", "Disc 1", "Disk 1", "CD 1", "Setlist 1", "Set List 1", "Track List 1"],
)
def test_build412_explicit_list_headings_start_song_region_and_discard_headers(tmp_path: Path, heading: str):
    info = tmp_path / "info.txt"
    info.write_text(
        f"Artist Header\nSeattle, WA\nSBD > DAT > FLAC\n\n{heading}\nSong Alpha\nSong Beta\n",
        encoding="utf-8",
    )

    rows, source = T.parse_unnumbered_section_tracks(str(info), expected_count=2)
    assert source == "unnumbered-sections"
    assert [row["title"] for row in rows] == ["Song Alpha", "Song Beta"]

    unstructured, unstructured_source = T.parse_unstructured_unnumbered_tracks(str(info), expected_count=2)
    assert unstructured_source in {"unnumbered-lines", "unnumbered-line-blocks"}
    assert [row["title"] for row in unstructured] == ["Song Alpha", "Song Beta"]


def test_build412_multiple_disc_boundaries_are_one_ordered_song_region(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "Artist Header\n\nDisc 1\nSong One\nSong Two\n\nDisc 2\nSong Three\nSong Four\n",
        encoding="utf-8",
    )
    rows, source = T.parse_unnumbered_section_tracks(str(info), expected_count=4)
    assert source == "unnumbered-sections"
    assert [row["title"] for row in rows] == ["Song One", "Song Two", "Song Three", "Song Four"]


def test_build412_date_labeled_filler_divider_inside_song_region_is_not_a_title(tmp_path: Path):
    info = tmp_path / "info.txt"
    info.write_text(
        "Set 1\nSong One\nSong Two\n\non July 7, 1967:\nFiller One\nFiller Two\n",
        encoding="utf-8",
    )
    rows, source = T.parse_unnumbered_section_tracks(str(info), expected_count=4)
    assert source == "unnumbered-sections"
    assert [row["title"] for row in rows] == ["Song One", "Song Two", "Filler One", "Filler Two"]


def test_build412_requirements_and_manual_document_explicit_track_region_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v446.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v446.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v446 (v1.6 Build 446)." in req_text
    assert "Build 412 explicit track-region boundary rule" in req_text
    assert "Reverend Gary Davis 1967-07-08" in req_text
    assert "Setlist 1" in req_text and "Track List 1" in req_text
    assert "Version v1.6 Build 446" in manual_text
    assert "on July 7, 1967:" in manual_text
    assert "on July 7, 1967:" in manual_text
