"""Build 425 regressions for qualified artist headers and venue-name collisions."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
from tlo_models import ShowMetadata
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior

__version__ = "v448"


SETLIST = """The Travelin' McCoury's - Early Show
Eddie's Attic
Decatur, Georgia
11/4/2022

Source: Schoeps CCM4V'S>Lunatec V2>Sound Devices 722

Disc I

01 Greeting
02 Walk Out In The Rain
03 The Shaker

Disc II

01 St. James Hospital
02 Why Oh Why
"""


def _matcher(*, ambiguous_apostrophe=False):
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "attic": {"Attic"},
        "the travelin' mccourys": {"The Travelin' McCourys"},
    }
    matcher.master_aliases = {
        "Attic": ["Attic"],
        "The Travelin' McCourys": ["The Travelin' McCourys"],
    }
    matcher.master_norms = {
        "Attic": {"attic"},
        "The Travelin' McCourys": {"thetravelinmccourys"},
    }
    if ambiguous_apostrophe:
        matcher.master_aliases["Travelin McCourys Alternate"] = ["The Travelin' McCourys"]
        matcher.master_norms["Travelin McCourys Alternate"] = {"thetravelinmccourys"}
    return matcher


def _config(tmp_path: Path):
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
        tlo_dbs_dir=str(tmp_path),
        debug=False,
    )


def _group(show_dir: Path, setlist: Path, tag_artist=""):
    samples = [{"artist": tag_artist, "albumartist": ""}] if tag_artist else []
    return {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
        "music_dirs": [str(show_dir)],
        "music_file_count": 5,
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": samples,
        "flac_tag_artist_values": [tag_artist] if tag_artist else [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": ["11/4/2022"] if tag_artist else [],
    }


def _write_show(tmp_path: Path):
    (tmp_path / "venues.txt").write_text("Eddie's Attic\n", encoding="utf-8")
    show_dir = tmp_path / "The Travelin' McCoury's - Early Show 2022-11-04 Eddie's Attic Decatur, GA"
    show_dir.mkdir()
    setlist = show_dir / "traveling2022-11-04e.txt"
    setlist.write_text(SETLIST, encoding="utf-8")
    return show_dir, setlist


def test_build425_terminal_show_qualifier_is_removed_only_with_explicit_structure():
    assert P._split_terminal_performance_qualifier_from_artist(
        "The Travelin' McCoury's - Early Show"
    ) == ("The Travelin' McCoury's", "Early Show")
    assert P._split_terminal_performance_qualifier_from_artist(
        "The Travelin' McCoury's (Late Show)"
    ) == ("The Travelin' McCoury's", "Late Show")
    assert P._split_terminal_performance_qualifier_from_artist("The Early Show") == (
        "The Early Show",
        "",
    )


def test_build425_apostrophe_retry_requires_one_unique_artist():
    detail, used = P._lookup_artist_detail_with_apostrophe_fallback(
        "The Travelin' McCoury's", _matcher()
    )
    assert used is True
    assert detail["status"] == "matched"
    assert detail["masters"] == ["The Travelin' McCourys"]

    detail, used = P._lookup_artist_detail_with_apostrophe_fallback(
        "The Travelin' McCoury's", _matcher(ambiguous_apostrophe=True)
    )
    assert used is True
    assert detail["status"] == "collision"
    assert len(detail["masters"]) == 2


def test_build425_artist_inside_parsed_venue_tail_is_not_a_path_artist():
    folder = "The Travelin' McCoury's - Early Show 2022-11-04 Eddie's Attic Decatur, GA"
    assert P._path_artist_hit_is_location_tail(folder, "Attic") is True
    hits, _collisions = P._db_backed_artist_hits_for_path_part(folder, _matcher())
    assert ("Attic", "Attic") not in hits

    exact_hits, _collisions = P._db_backed_artist_hits_for_path_part("Attic", _matcher())
    assert ("Attic", "Attic") in exact_hits


def test_build425_tag_artist_is_cleaned_and_db_confirmed_before_path_fallback(tmp_path: Path):
    record = ShowMetadata(
        group_number=1,
        main_dir_name="show",
        main_dir_path=str(tmp_path / "show"),
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[
            {"artist": "The Travelin' McCoury's - Early Show", "albumartist": ""}
        ]
    )
    evidence = {}
    observations = []

    artist = P._resolve_artist_from_tags(
        record,
        _matcher(),
        evidence,
        [],
        observations,
        config=_config(tmp_path),
        allow_unmatched=False,
    )

    assert artist == "The Travelin' McCourys"
    assert record.qualifier == "Early Show"
    assert evidence["artist"][0].confidence == 95
    assert any("terminal performance qualifier removed from tag artist" in item for item in observations)
    assert any("apostrophe-insensitive Artist DB match" in item for item in observations)


def test_build425_setlist_only_qualifier_survives_artist_correction(tmp_path: Path):
    (tmp_path / "venues.txt").write_text("Eddie's Attic\n", encoding="utf-8")
    setlist = tmp_path / "traveling2022-11-04e.txt"
    setlist.write_text(SETLIST, encoding="utf-8")
    record = ShowMetadata(
        group_number=1,
        main_dir_name="Unlabelled Show 2022-11-04",
        main_dir_path=str(tmp_path / "Unlabelled Show 2022-11-04"),
        setlist_file=str(setlist),
        music_file_count=5,
        artist="Attic",
        date="2022-11-04",
    )
    evidence = {"artist": [P.Candidate("Attic", "subdirectory:Attic", 60)]}
    observations = []

    changed = P._apply_setlist_metadata_to_noncompliant_record(
        _config(tmp_path), record, evidence, observations, _matcher(), []
    )

    assert changed is True
    assert record.artist == "The Travelin' McCourys"
    assert record.qualifier == "Early Show"
    assert any(candidate.source.endswith("_terminal_qualifier") for candidate in evidence["qualifier"])


def test_build425_full_setlist_case_corrects_artist_and_preserves_qualifier(tmp_path: Path):
    show_dir, setlist = _write_show(tmp_path)

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir, setlist), _matcher()
    )

    assert record.artist == "The Travelin' McCourys"
    assert record.date == "2022-11-04"
    assert record.venue == "Eddie's Attic"
    assert record.location == "Decatur, GA"
    assert record.qualifier == "Early Show"
    assert record.show_name == (
        "The Travelin' McCourys 2022-11-04 Eddie's Attic Decatur, GA (Early Show)"
    )
    assert not unresolved
    assert any("terminal performance qualifier removed from setlist artist" in item for item in record.observations)
    assert any("apostrophe-insensitive Artist DB match" in item for item in record.observations)


def test_build425_requirements_and_manual_document_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v448.docx")
    requirements_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v448.rtf").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "Current document version: v448 (v1.6 Build 448)." in requirements_text
    assert "unique apostrophe-insensitive retry" in requirements_text
    assert "Attic inside Eddie's Attic" in requirements_text
    assert "final Show identity must end with (Early Show)" in requirements_text
    assert "Version v1.6 Build 448" in manual_text
    assert "unique-only apostrophe retry" in manual_text
    assert "Attic inside Eddie's Attic" in manual_text
    assert "retained as a parenthesized suffix" in manual_text
