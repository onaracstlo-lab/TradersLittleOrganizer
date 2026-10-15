"""Build 588 regression: event-header metadata, numbered tracks and tag fallback."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

from tlo_setlist_metadata_lookup import extract_setlist_venue_location
from tlo_tag_lib import _clean_track_title, _parse_track_line, parse_setlist_tracks, _select_tracks_for_tagging


EXAMPLE = """The Bad Plus, Chris Potter, & Craig Taborn: Tribute to Keith Jarrett’s American Quartet
Tuesday, March 3, 2026
Lexington, KY @ Singletary Center For The Arts (Recital Hall) - University of Kentucky

Schoeps MK4 > NBob active cables > baby NBox > Zoom H6 essential > WAV (32/48) > Vegas Pro (slight eq) > CD Wave Editor (tracking) > FLAC (24/48)
Recorded by Funk It Blog

01. Introduction
02. (If the) Misfits (Wear It) [Keith Jarrett]
03. Gotta Get Some Sleep [Dewey Redman]
04. Le Mistral [Keith Jarrett]
05. Silence [Charlie Haden]
06. De Drums [Keith Jarrett]
07. Mushi Mushi [Dewey Redman]
Encore:
08. Encore (a-b-c)

Reid Anderson - double bass
Dave King - drums & percussion
Chris Potter - tenor saxophone
Craig Taborn - piano
"""


def test_exact_header_without_artist_database(tmp_path: Path):
    path = tmp_path / "info.txt"
    path.write_text(EXAMPLE, encoding="utf8")
    result = extract_setlist_venue_location(str(path), str(tmp_path / "empty-db"))
    assert result.artist == "The Bad Plus, Chris Potter, & Craig Taborn"
    assert result.artist_source == "setlist_metadata:CONFIRMED_EVENT_HEADER"
    assert result.city == "Lexington"
    assert result.region == "KY"
    assert result.location == "Lexington KY"
    assert result.venue == "Singletary Center For The Arts (Recital Hall) - University of Kentucky"


def test_exact_eight_song_setlist(tmp_path: Path):
    path = tmp_path / "info.txt"
    path.write_text(EXAMPLE, encoding="utf8")
    tracks = parse_setlist_tracks(str(path))
    assert len(tracks) == 8
    assert [row["original_number"] for row in tracks] == list(range(1, 9))
    assert [row["title"] for row in tracks] == [
        "Introduction", "(If the) Misfits (Wear It) [Keith Jarrett]",
        "Gotta Get Some Sleep [Dewey Redman]", "Le Mistral [Keith Jarrett]",
        "Silence [Charlie Haden]", "De Drums [Keith Jarrett]",
        "Mushi Mushi [Dewey Redman]", "Encore (a-b-c)",
    ]


def test_unknown_question_marks_only():
    for text in ["?", "??", "?????", " ? ? "]:
        assert _clean_track_title(text) == "unknown"
    assert _parse_track_line("04. ???") == (4, "unknown")
    assert _clean_track_title("Who? Why?") == "Who? Why?"


def test_event_header_not_inferred_without_confirmed_date_location(tmp_path: Path):
    path = tmp_path / "notes.txt"
    path.write_text("Mixing Desk: Test Performance\nAn unrelated note\nBooth @ Venue\n", encoding="utf8")
    result = extract_setlist_venue_location(str(path), str(tmp_path / "empty-db"))
    assert result.artist_source != "setlist_metadata:CONFIRMED_EVENT_HEADER"


def test_inventory_uses_local_eight_tracks_without_network(tmp_path: Path):
    path = tmp_path / "info.txt"
    path.write_text(EXAMPLE, encoding="utf8")
    audio = [str(tmp_path / f"{i:02d}.flac") for i in range(1, 9)]
    group = {"main_dir_path": str(tmp_path), "setlist_file": str(path)}
    config = SimpleNamespace(thorough_setlist_matching=False)
    tracks, source, error = _select_tracks_for_tagging(config, group, audio,
        fallback_to_filenames_on_track_problem=True,
        fallback_to_title_tags_on_track_problem=True)
    assert source == "setlist" and error is None
    assert len(tracks) == 8


def test_noncompliant_inventory_metadata_for_exact_folder(tmp_path: Path):
    from inventory_parser_lib import Config
    from tlo_phase23_v2 import _extract_metadata_for_group

    show = tmp_path / "Bad Plus, Chris Potter, and Craig Taborn 2026-03-03 Singletary Center For The Arts University of Kentucky Lexington KY (24)"
    show.mkdir()
    setlist = show / "info.txt"
    setlist.write_text(EXAMPLE, encoding="utf8")
    group = {
        "group_number": 1, "main_dir_name": show.name, "main_dir_path": str(show),
        "setlist_file": str(setlist), "setlist_files": [str(setlist)],
        "txt_files": [str(setlist)], "music_dirs": [str(show)],
        "music_files": [str(show / f"{idx:02d}.flac") for idx in range(1, 9)],
        "music_file_count": 8,
    }
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path),
                    current_search_path=str(show), tlo_dbs_dir=str(tmp_path / "TLO_DBs"))
    record, _, unresolved = _extract_metadata_for_group(config, group, None)
    assert record.artist == "The Bad Plus, Chris Potter, & Craig Taborn"
    assert record.date == "2026-03-03"
    assert record.venue == "Singletary Center For The Arts (Recital Hall) - University of Kentucky"
    assert record.location == "Lexington, KY"
    assert record.show_name and not unresolved


def test_eight_real_flacs_receive_artist_album_and_titles(tmp_path: Path):
    import shutil
    import subprocess

    from mutagen.flac import FLAC

    from inventory_parser_lib import Config
    from tlo_phase23_v2 import _extract_metadata_for_group
    from tlo_tag_lib import tag_group_with_record

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("Test needs an FFmpeg encoder to create temporary valid FLAC files")
    show = tmp_path / "Bad Plus, Chris Potter, and Craig Taborn 2026-03-03 Singletary Center For The Arts University of Kentucky Lexington KY (24)"
    show.mkdir()
    setlist = show / "info.txt"
    setlist.write_text(EXAMPLE, encoding="utf8")
    template = tmp_path / "one.flac"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "0.2", "-c:a", "flac", "-y", str(template)], check=True,
                   timeout=30, capture_output=True)
    audio = []
    for idx in range(1, 9):
        target = show / f"{idx:02d}.flac"
        shutil.copyfile(template, target)
        audio.append(str(target))
    group = {"group_number": 1, "main_dir_name": show.name, "main_dir_path": str(show),
             "setlist_file": str(setlist), "setlist_files": [str(setlist)], "txt_files": [str(setlist)],
             "music_dirs": [str(show)], "music_files": audio, "music_file_count": 8}
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path),
                    current_search_path=str(show), tlo_dbs_dir=str(tmp_path / "TLO_DBs"),
                    corrupt_files="keep", corrupt_folders="never", tag_during_inventory=True)
    record, _, problems = _extract_metadata_for_group(config, group, None)
    assert not problems
    stats = tag_group_with_record(config, group, record, allow_unknown_metadata=True,
                                  fallback_to_filenames_on_track_problem=True,
                                  fallback_to_title_tags_on_track_problem=True)
    assert stats["tagged"] == 8 and stats["errors"] == 0 and stats["skipped"] == 0
    for idx, filename in enumerate(audio, start=1):
        tags = FLAC(filename)
        assert tags["artist"][0] == record.artist
        assert "2026-03-03" in tags["album"][0]
        assert "Singletary Center" in tags["album"][0]
        assert tags["title"][0] == [
            "Introduction", "(If the) Misfits (Wear It) [Keith Jarrett]",
            "Gotta Get Some Sleep [Dewey Redman]", "Le Mistral [Keith Jarrett]",
            "Silence [Charlie Haden]", "De Drums [Keith Jarrett]",
            "Mushi Mushi [Dewey Redman]", "Encore (a-b-c)",
        ][idx - 1]
