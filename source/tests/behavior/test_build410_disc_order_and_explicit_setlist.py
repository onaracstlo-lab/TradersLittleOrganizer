"""Build 410 regressions for disc ordering and explicit unnumbered setlists."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
import tlo_tag_lib as T

__version__ = "v414"


COUNTRY_JOE_INFO = """Country Joe Mcdonald-The Red Barn,Deposit,N.Y. U.S.A. 2001-05-26

Source:Sony Stereo Mic>Sony D8 Dat Master>Maxell HS-4 60 Meter DDS Dat Tape>Sony PCM R-300 Home Dat Deck(Playback)>

Edirol R-09 HR(24/44.1 KHZ)>Cd Wav Editor>Traders Little Helper>Flac Level 8.Sector Boundaries Aligned Using Traders

Little Helper.Taped By Boeditaper.

Setlist:

You And I
Superbird
Tricky Dick
Not So Sweet,Lorraine
Thank The Nurse That's Nursing You
Colorado Town
Flying High All The Way
The Baby Song
Yankee Doodle
What Wonderous Love Is This
Gunshot Wound
Who Am I
Joe's Blues
Happiness Is A (Porpoise Mouth?)
Trilogy
The Nuclear Submarine
Save The Whales
Fixin To Die A Rag
Enc:This Land Is Your Land

Notes:

1)Quality IS about A or A-(Subjective Of Course).Samples Included.

2)I'm Pretty Sure I Uploaded This Show Several Years Ago.However,I Believe That Version Was From The CD Version Copy

I Originally Made Using A Harmon Kardon CD Burner.This Version Here IS Direct Off The Dat Master.Using CD Wav Editor,

I Can Better Track The Show.

3)Very Intimate Show,Played On Memorial Day Weeknd In Front Of ABout Only 20 or 25 People.

Enjoy!!
"""

EXPECTED_TITLES = [
    "You And I",
    "Superbird",
    "Tricky Dick",
    "Not So Sweet,Lorraine",
    "Thank The Nurse That's Nursing You",
    "Colorado Town",
    "Flying High All The Way",
    "The Baby Song",
    "Yankee Doodle",
    "What Wonderous Love Is This",
    "Gunshot Wound",
    "Who Am I",
    "Joe's Blues",
    "Happiness Is A (Porpoise Mouth?)",
    "Trilogy",
    "The Nuclear Submarine",
    "Save The Whales",
    "Fixin To Die A Rag",
    "This Land Is Your Land",
]


def _write_info(tmp_path: Path) -> Path:
    path = tmp_path / "Country Joe Mcdonald-Deposit 2001-05-26 Text Document.txt"
    path.write_text(COUNTRY_JOE_INFO, encoding="utf-8")
    return path


def test_build410_comma_between_disc_and_track_tokens_sorts_disc_then_track(tmp_path: Path):
    names = [
        "CJM-Disc02,Track02.flac",
        "CJM-Disc01,Track01.flac",
        "CJM-Disc02,Track01.flac",
        "CJM-Disc01,Track03.flac",
        "CJM-Disc01,Track02.flac",
    ]
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"x")
        paths.append(str(path))

    ordered = [Path(path).name for path in sorted(paths, key=T._audio_track_order)]

    assert ordered == [
        "CJM-Disc01,Track01.flac",
        "CJM-Disc01,Track02.flac",
        "CJM-Disc01,Track03.flac",
        "CJM-Disc02,Track01.flac",
        "CJM-Disc02,Track02.flac",
    ]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("CJM-Disc01,Track07.flac", (0, 7)),
        ("CJM-Disk02-Track03.flac", (1, 3)),
        ("CJM-CD03_Track09.flac", (2, 9)),
        ("CJM-d04.t05.flac", (3, 5)),
    ],
)
def test_build410_disc_track_token_punctuation_permutations(name: str, expected: tuple[int, int]):
    key = T._audio_track_order(name)
    assert key[:2] == expected


def test_build410_numbered_notes_after_explicit_unnumbered_setlist_are_not_tracks(tmp_path: Path):
    info = _write_info(tmp_path)

    assert T.parse_setlist_tracks(str(info)) == []
    assert T._has_convincing_numbered_setlist_evidence(str(info)) is False


def test_build410_explicit_country_joe_setlist_preserves_all_19_titles(tmp_path: Path):
    info = _write_info(tmp_path)

    rows = T._explicit_unnumbered_track_section_candidate(str(info))

    assert [row["title"] for row in rows] == EXPECTED_TITLES
    assert "Thank The Nurse That's Nursing You" in EXPECTED_TITLES
    assert EXPECTED_TITLES[-1] == "This Land Is Your Land"


def test_build410_country_joe_tag_selection_uses_song_list_not_numbered_notes(tmp_path: Path):
    info = _write_info(tmp_path)
    audio_files = []
    # Use the collector's punctuation form and split the 19 songs over two discs.
    for disc, count in ((1, 10), (2, 9)):
        for track in range(1, count + 1):
            path = tmp_path / f"CJM-Disc{disc:02d},Track{track:02d}.flac"
            path.write_bytes(b"")
            audio_files.append(str(path))
    # Deliberately scramble the input; the live tagging path sorts using
    # _audio_track_order before it pairs files with selected titles.
    audio_files = list(reversed(audio_files))
    ordered_audio = sorted(audio_files, key=T._audio_track_order)

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    messages = []
    tracks, source, error = T._select_tracks_for_tagging(
        config,
        {"setlist_file": str(info), "path": str(tmp_path)},
        ordered_audio,
        emit=messages.append,
        record=None,
    )

    assert error is None
    assert source in {"unnumbered-lines", "explicit-unnumbered-section"}
    assert [row["title"] for row in tracks] == EXPECTED_TITLES
    assert [Path(path).name for path in ordered_audio[:3]] == [
        "CJM-Disc01,Track01.flac",
        "CJM-Disc01,Track02.flac",
        "CJM-Disc01,Track03.flac",
    ]
    assert Path(ordered_audio[9]).name == "CJM-Disc01,Track10.flac"
    assert Path(ordered_audio[10]).name == "CJM-Disc02,Track01.flac"


def test_build410_thanks_to_taper_still_terminates_but_thank_song_is_valid():
    assert T.TRACK_LIST_TERMINATOR_RE.match("Thanks to the taper.")
    assert not T.TRACK_LIST_TERMINATOR_RE.match("Thank The Nurse That's Nursing You")
    assert T._looks_like_unnumbered_song_title("Thank The Nurse That's Nursing You") is True

def test_build410_requirements_and_manual_document_reported_fix():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v414.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v414.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v414 (v1.4 Build 414)." in req_text
    assert "Build 410 explicit-setlist and disc-order rule" in req_text
    assert "CJM-Disc01,Track01.flac" in req_text
    assert "Thank The Nurse That's Nursing You" in req_text
    assert "later collector notes beginning 1), 2), 3)" in req_text
    assert "Version v1.4 Build 414" in manual_text
    assert "Build 410 - Explicit setlists and multi-disc track ordering" in manual_text
    assert "Country Joe 2001-05-26" in manual_text

