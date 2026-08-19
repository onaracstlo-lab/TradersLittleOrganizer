from pathlib import Path

from inventory_parser_lib import Config
import tlo_tag_lib as T


FOGHAT_EAC_SAMPLE = r"""Foghat
Superstar Concert Series
95-07

This is from an original copy of the radio show. It has not been altered. It includes national commercials and the songs are grouped as they were in the broadcast. Nothing has been changed. This particular one says it was recorded at the House of Blues in Hollywood, Ca - 21 October 1994. No date given. CD > EAC > FLAC 8.

Songs:

Fool For The City
Louisiana Blues
Stone Blue
Jump That Train
Slowride

Track01.flac:fe1a1457532a40026785cccf17b3ab84
Track02.flac:1a1c45a7d38b9d2dc8ccaa292ebe8f95
Track03.flac:695539659ee2a1717cb661a4f9bbc6bf
Track04.flac:c7d0ae54baf58d1adfde013156afbd53

Exact Audio Copy V0.99 prebeta 3 from 28. July 2007

EAC extraction logfile from 2. May 2008, 14:11

Foghat / 9507

TOC of the extracted CD

     Track |   Start  |  Length  | Start sector | End sector
    ---------------------------------------------------------
        1  |  0:00.00 | 13:17.25 |         0    |    59799
        2  | 13:17.25 | 15:04.72 |     59800    |   127671
        3  | 28:22.22 | 10:02.48 |    127672    |   172869
        4  | 38:24.70 |  1:04.30 |    172870    |   177699

Track  1

     Filename G:\\Track01.wav
     Peak level 94.8 %
     Track quality 100.0 %
     Copy CRC AA66DE7A
     Copy OK

Track  2

     Filename G:\\Track02.wav
     Peak level 92.9 %
     Track quality 100.0 %
     Copy CRC 272F6198
     Copy OK

Track  3

     Filename G:\\Track03.wav
     Peak level 94.2 %
     Track quality 100.0 %
     Copy CRC DEB0A79A
     Copy OK

Track  4

     Filename G:\\Track04.wav
     Peak level 100.0 %
     Track quality 99.8 %
     Copy CRC 598CD72B
     Copy OK

No errors occurred
End of status report
"""


def _write_sample(tmp_path: Path) -> Path:
    path = tmp_path / "Foghat 1994-10-21 info.txt"
    path.write_text(FOGHAT_EAC_SAMPLE, encoding="utf-8")
    return path


def test_build379_eac_toc_row_is_not_a_song_title():
    row = "1  |  0:00.00 | 13:17.25 |         0    |    59799"
    assert T._parse_track_line(row) is None
    assert T._is_non_song_technical_track_line(row)


def test_build379_eac_log_tail_does_not_become_numbered_setlist(tmp_path):
    setlist = _write_sample(tmp_path)
    assert T.parse_setlist_tracks(str(setlist)) == []


def test_build379_explicit_songs_block_is_preserved_as_real_candidate(tmp_path):
    setlist = _write_sample(tmp_path)
    rows = T._explicit_unnumbered_track_section_candidate(str(setlist))
    assert [row["title"] for row in rows] == [
        "Fool For The City",
        "Louisiana Blues",
        "Stone Blue",
        "Jump That Train",
        "Slowride",
    ]


def test_build379_five_song_block_is_not_forced_onto_four_audio_files(tmp_path):
    setlist = _write_sample(tmp_path)
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    audio_files = []
    for number in range(1, 5):
        path = audio_dir / f"Track{number:02d}.flac"
        path.write_bytes(b"")
        audio_files.append(str(path))

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    messages = []
    tracks, source, error = T._select_tracks_for_tagging(
        config,
        {"setlist_file": str(setlist), "path": str(audio_dir)},
        audio_files,
        emit=messages.append,
        record=None,
    )

    assert tracks == []
    assert source == ""
    assert error and "no parseable tracks" in error
    joined = "".join(messages)
    assert "explicit local Songs/Tracks section with 5 plausible title(s) for 4 audio file(s)" in joined
    assert "not mapping titles because the counts do not match" in joined
    assert "0:00.00" not in joined


def test_build379_normal_numbered_song_list_still_wins(tmp_path):
    setlist = tmp_path / "normal.txt"
    setlist.write_text(
        "Songs:\n1 Fool For The City\n2 Louisiana Blues\n3 Stone Blue\n4 Slowride\n",
        encoding="utf-8",
    )
    rows = T.parse_setlist_tracks(str(setlist))
    assert [row["title"] for row in rows] == [
        "Fool For The City",
        "Louisiana Blues",
        "Stone Blue",
        "Slowride",
    ]
