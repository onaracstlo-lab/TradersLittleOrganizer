"""Build 409 regressions for numbered-setlist gaps and unsafe prose fallback."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

import tlo_tag_lib as T

__version__ = "v413"


CHICK_COREA_INFO = """Chick Corea & Gary Burton
Berlin, Germany
Philharmonie
Berliner Jazztage
1972-11-04

01
02 Day Waves
03 Desert Air
04 Crystal Silence
05 Children Song No. 1
06 La Fiesta

Gary Burton(vib)
Chick Corea (p)

min 38:24

MDR Kultur
Konzert
2021-02-16

digital broadcast (cable) - Vistron VT 855 - Audacity - xACT
(MPEG-1 Audio Layer 2 / 192 kbit/s)

Support the artists by buying their records.
---------------------------
"""


def _write_info(tmp_path: Path, text: str = CHICK_COREA_INFO) -> Path:
    path = tmp_path / "info.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_build409_leading_bare_track_one_is_unknown_when_track_two_confirms_list(tmp_path: Path):
    path = _write_info(tmp_path)

    tracks = T.parse_setlist_tracks(str(path))

    assert [(row["original_number"], row["title"]) for row in tracks] == [
        (1, "Unknown"),
        (2, "Day Waves"),
        (3, "Desert Air"),
        (4, "Crystal Silence"),
        (5, "Children Song No. 1"),
        (6, "La Fiesta"),
    ]


def test_build409_isolated_bare_number_before_prose_is_not_manufactured_as_track(tmp_path: Path):
    path = _write_info(tmp_path, "01\nVenue Name\n02 Day Waves\n03 Desert Air\n")

    tracks = T.parse_setlist_tracks(str(path))

    assert not tracks or tracks[0]["title"] != "Unknown"


def test_build409_numeric_song_names_remain_plausible_but_bare_number_cannot_start_unstructured_block(tmp_path: Path):
    assert T._looks_like_unnumbered_song_title("69") is True
    assert T._looks_like_unnumbered_song_title("1999") is True

    path = _write_info(tmp_path, "01\n\nAlpha\nBeta\nGamma\nDelta\nEpsilon\n")
    tracks, source = T.parse_unstructured_unnumbered_tracks(str(path), 6)
    assert tracks == []
    assert source == ""


@pytest.mark.parametrize(
    "line",
    [
        "Gary Burton(vib)",
        "Chick Corea (p)",
        "Player Name (g)",
        "Player Name (bass)",
        "Player Name (drums)",
        "Player Name (sax)",
    ],
)
def test_build409_parenthetical_instrument_credits_are_not_song_titles(line: str):
    assert T._looks_like_personnel_or_credit_line(line) is True


def test_build409_normal_song_parenthetical_is_not_misclassified_as_personnel():
    assert T._looks_like_personnel_or_credit_line("The Song (Live)") is False


@pytest.mark.parametrize(
    "line",
    ["min 38:24", "mins 38:24", "38:24 min", "total time 38:24", "time: 38:24"],
)
def test_build409_duration_summary_lines_are_not_song_titles(line: str):
    assert T._looks_like_duration_summary_line(line) is True
    assert T._looks_like_unnumbered_song_title(line) is False


def test_build409_convincing_numbered_sequence_blocks_unnumbered_prose_fallback(tmp_path: Path):
    # Begin at 02 without the missing 01 so the primary numbered parser rejects
    # the list; later prose deliberately contains six short candidate lines.
    path = _write_info(
        tmp_path,
        """02 Day Waves
03 Desert Air
04 Crystal Silence
05 Children Song No. 1
06 La Fiesta

Alpha
Beta
Gamma
Delta
Epsilon
Zeta
""",
    )

    assert T.parse_setlist_tracks(str(path)) == []
    assert T._has_convincing_numbered_setlist_evidence(str(path)) is True
    tracks, source = T._local_setlist_fallback_tracks(str(path), 6, "test-folder")
    assert tracks == []
    assert source == ""


def test_build409_exact_reported_info_never_falls_back_to_six_prose_titles(tmp_path: Path):
    path = _write_info(tmp_path)

    tracks = T.parse_setlist_tracks(str(path))
    assert len(tracks) == 6
    assert [row["title"] for row in tracks] == [
        "Unknown",
        "Day Waves",
        "Desert Air",
        "Crystal Silence",
        "Children Song No. 1",
        "La Fiesta",
    ]

    fallback, source = T._local_setlist_fallback_tracks(str(path), 6, "test-folder")
    assert fallback == []
    assert source == ""


def test_build409_requirements_and_manual_document_numbered_setlist_safety_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v413.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v413.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v413 (v1.4 Build 413)." in req_text
    assert "Build 409 numbered-setlist safety rule" in req_text
    assert "short number is more likely to be a bare track number" in req_text
    assert "titles such as 69 and 1999 must remain valid" in req_text
    assert "Gary Burton(vib) and Chick Corea (p)" in req_text
    assert "convincing run of at least three consecutive numbered song rows" in req_text
    assert "Version v1.4 Build 413" in manual_text
    assert "Build 409 - Numbered setlist safety and blank tracks" in manual_text
    assert "Gary Burton(vib) or Chick Corea (p)" in manual_text
