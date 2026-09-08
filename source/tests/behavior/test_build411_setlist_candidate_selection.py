"""Build 411 regressions for competing numbered and unnumbered setlist candidates."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
import tlo_tag_lib as T

__version__ = "v446"


CRAMPS_INFO = """The Cramps
San Diego, CA
Adams Ave. Theater
June 25th, 1984

SBD Recording

Too tired to write much. But, I had to three things with my copy of this show to fix it up for Dimeadozen:

1) Boost the volume
2) Adjust the speed
3) Retrack the entire show

Good quality show. Some unrecorded gems (at least, with the two-guitar/no bass line-up). A little weak on the guitars, but still fun. Cuts in with "Devil". Might be missing a song between "Mad Daddy" and "She Said" (based on other shows from this tour, they sometimes did "Human Fly" at this point). Also, they sometimes encored after "She Said" with "Rumble" (or "Rumble Blues" as The Cramps dubbed it on "How To Make A Monster"). But this is the fullest recording of the show I've found.

Devil With A Blue Dress On
You Got Good Taste
Call Of The Wighat
Thee Most Exalted Potentate Of Love
You'll Never Change Me
Sinners
Bacon Fat
Domino
I Ain't Nuthin' But A Gorehound
Zombie Dance
What's Inside A Girl?
Faster Pussycat
Psychotic Reaction
Garbageman
TV Set
The Mad Daddy
She Said
"""

CRAMPS_TITLES = [
    "Devil With A Blue Dress On",
    "You Got Good Taste",
    "Call Of The Wighat",
    "Thee Most Exalted Potentate Of Love",
    "You'll Never Change Me",
    "Sinners",
    "Bacon Fat",
    "Domino",
    "I Ain't Nuthin' But A Gorehound",
    "Zombie Dance",
    "What's Inside A Girl?",
    "Faster Pussycat",
    "Psychotic Reaction",
    "Garbageman",
    "TV Set",
    "The Mad Daddy",
    "She Said",
]

AMBIGUOUS_THREE = """Collector checklist before the actual songs:

1) Boost the volume
2) Adjust the speed
3) Retrack the show

Song Alpha
Song Beta
Song Gamma
"""


def _config(tmp_path: Path) -> Config:
    return Config(debug=False, silent=True, TLOHome=str(tmp_path))


def _select(tmp_path: Path, text: str, filenames: list[str], monkeypatch=None, tag_map=None):
    info = tmp_path / "info.txt"
    info.write_text(text, encoding="utf-8")
    files = []
    for name in filenames:
        path = tmp_path / name
        path.write_bytes(b"")
        files.append(str(path))
    if monkeypatch is not None and tag_map is not None:
        monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: tag_map.get(Path(path).name, ""))
    messages = []
    rows, source, error = T._select_tracks_for_tagging(
        _config(tmp_path),
        {"setlist_file": str(info), "path": str(tmp_path)},
        files,
        emit=messages.append,
        record=None,
    )
    return rows, source, error, messages


def test_build411_cramps_exact_count_song_block_beats_three_numbered_notes(tmp_path: Path):
    filenames = [f"track{i:02d}.flac" for i in range(1, 18)]
    rows, source, error, messages = _select(tmp_path, CRAMPS_INFO, filenames)

    assert error is None
    assert source in {"unnumbered-lines", "unnumbered-line-blocks"}
    assert [row["title"] for row in rows] == CRAMPS_TITLES
    assert any("17 title(s) while numbered candidate has 3" in message for message in messages)


def test_build411_equal_count_filename_matches_reinforce_real_unnumbered_list(tmp_path: Path):
    filenames = ["01 Song Alpha.flac", "02 Song Beta.flac", "03 Song Gamma.flac"]
    rows, source, error, messages = _select(tmp_path, AMBIGUOUS_THREE, filenames)

    assert error is None
    assert source.startswith("unnumbered")
    assert [row["title"] for row in rows] == ["Song Alpha", "Song Beta", "Song Gamma"]
    assert any("positive filename/title-tag reinforcement" in message for message in messages)


def test_build411_equal_count_existing_tags_reinforce_real_unnumbered_list(tmp_path: Path, monkeypatch):
    filenames = ["track01.flac", "track02.flac", "track03.flac"]
    tag_map = {
        "track01.flac": "Song Alpha",
        "track02.flac": "Song Beta",
        "track03.flac": "Song Gamma",
    }
    rows, source, error, _messages = _select(tmp_path, AMBIGUOUS_THREE, filenames, monkeypatch, tag_map)

    assert error is None
    assert source.startswith("unnumbered")
    assert [row["title"] for row in rows] == ["Song Alpha", "Song Beta", "Song Gamma"]


def test_build411_equal_count_filename_matches_can_reinforce_numbered_candidate(tmp_path: Path):
    filenames = ["01 Boost the volume.flac", "02 Adjust the speed.flac", "03 Retrack the show.flac"]
    rows, source, error, messages = _select(tmp_path, AMBIGUOUS_THREE, filenames)

    assert error is None
    assert source == "setlist"
    assert [row["title"] for row in rows] == ["Boost the volume", "Adjust the speed", "Retrack the show"]
    assert any("numbered candidate retained by positive" in message for message in messages)


def test_build411_unrelated_filename_and_tag_values_are_neutral_not_negative(tmp_path: Path, monkeypatch):
    text = """1) First Song
2) Second Song
3) Third Song

Other Alpha
Other Beta
Other Gamma
"""
    filenames = ["track01.flac", "track02.flac", "track03.flac"]
    tag_map = {
        "track01.flac": "Completely Different A",
        "track02.flac": "Completely Different B",
        "track03.flac": "Completely Different C",
    }
    rows, source, error, _messages = _select(tmp_path, text, filenames, monkeypatch, tag_map)

    # No filename/tag title matches either candidate, so those external values
    # contribute zero rather than penalizing the normal numbered precedence.
    assert error is None
    assert source == "setlist"
    assert [row["title"] for row in rows] == ["First Song", "Second Song", "Third Song"]


def test_build411_short_numbered_notes_embedded_in_prose_lose_equal_count_tie_without_negative_matching(tmp_path: Path, monkeypatch):
    text = """I made several processing changes before sharing this recording, and these are the three things that I changed:

1) Boost the volume
2) Adjust the speed
3) Retrack the show

Song Alpha
Song Beta
Song Gamma
"""
    filenames = ["track01.flac", "track02.flac", "track03.flac"]
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda _path: "")
    rows, source, error, messages = _select(tmp_path, text, filenames)

    assert error is None
    assert source.startswith("unnumbered")
    assert [row["title"] for row in rows] == ["Song Alpha", "Song Beta", "Song Gamma"]
    assert any("embedded in prose/notes" in message for message in messages)


def test_build411_requirements_and_manual_document_candidate_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v446.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v446.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v446 (v1.6 Build 446)." in req_text
    assert "Build 411 competing-track-list candidate rule" in req_text
    assert "positive corroboration" in req_text
    assert "missing, generic, unreadable, or unrelated filename/tag value contributes zero" in req_text
    assert "Cramps 1984-06-25" in req_text
    assert "Version v1.6 Build 446" in manual_text
    assert "missing or unrelated filename/tag values are neutral" in manual_text
